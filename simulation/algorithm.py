"""
Online drone positioning algorithm with Control Metrics CM1–CM7.

Paper reference: Section VII (Algorithm) + Section VII-C (Control Metrics)

The algorithm (Figure 6 in paper):
  - Measures a CM over a 200 ms window.
  - At each decision point moves the drone 1 m in x or y.
  - If CM improved → repeat same action.
  - If CM degraded  → reverse direction.
  - After reversing, if CM degrades again → switch to the other coordinate.
  - Goal: MINIMIZE CM (lower load ≈ more resources ≈ better CSR).
"""
import math
from enum import Enum, auto
from typing import Optional, Callable, Dict

from simulation.network import Network
from simulation.drone import Drone
from simulation.resource import AdmissionController
from simulation.config import DRONE_STEP_M, CONTROL_INTERVAL_S


# ---------------------------------------------------------------------------
# Control Metrics
# ---------------------------------------------------------------------------

class CMType(Enum):
    CM1 = 1
    CM2 = 2
    CM3 = 3
    CM4 = 4
    CM5 = 5
    CM6 = 6
    CM7 = 7


def compute_cm(
    cm_type: CMType,
    drone_cell_id: int,
    network: Network,
    admission: AdmissionController,
) -> float:
    """
    Why use this function: Calculates one of the seven Control Metrics (CM1-CM7) used 
    to guide the drone's positioning algorithm.

    Args:
        cm_type (CMType): The specific CM metric to compute.
        drone_cell_id (int): ID of the cell served by the drone.
        network (Network): The network object to query site status.
        admission (AdmissionController): The controller to query resource loads.

    Returns:
        float: The value of the requested Control Metric.
    """
    # --- Drone metrics ---
    drone_load     = admission.cell_load(drone_cell_id)
    drone_lpu      = admission.cell_load_per_ue(drone_cell_id)
    drone_n        = admission.num_ues(drone_cell_id)

    # --- Most-loaded regular neighbour cell ---
    neighbour_ids  = network.neighbour_cell_ids_of_failing_site()

    best_id, best_load, best_lpu, best_n = None, 0.0, 0.0, 0
    for cid in neighbour_ids:
        cell = network.get_cell(cid)
        if not cell.active:
            continue
        load = admission.cell_load(cid)
        if load > best_load:
            best_load = load
            best_lpu  = admission.cell_load_per_ue(cid)
            best_n    = admission.num_ues(cid)
            best_id   = cid

    # Guard: if no neighbour found
    if best_id is None:
        best_load, best_lpu, best_n = 0.0, 0.0, 0

    if cm_type == CMType.CM1:
        return drone_load

    elif cm_type == CMType.CM2:
        return best_load

    elif cm_type == CMType.CM3:
        return drone_load + best_load

    elif cm_type == CMType.CM4:
        return drone_lpu

    elif cm_type == CMType.CM5:
        return best_lpu

    elif cm_type == CMType.CM6:
        return (drone_lpu + best_lpu) / 2.0

    elif cm_type == CMType.CM7:
        total_n = drone_n + best_n
        if total_n == 0:
            return 0.0
        return (drone_n * drone_lpu + best_n * best_lpu) / total_n

    raise ValueError(f"Unknown CM type: {cm_type}")


# ---------------------------------------------------------------------------
# Algorithm state machine (Figure 6)
# ---------------------------------------------------------------------------

class Axis(Enum):
    X = auto()
    Y = auto()


class DronePositioningAlgorithm:
    """
    Online gradient-free positioning algorithm from Section VII-B.

    State machine:
        - Optimise one axis (x or y) at a time.
        - Move +1 m, measure CM, compare with previous CM.
        - If improved: continue same direction.
        - If degraded:  reverse direction; if then degraded again → switch axis.
    """

    def __init__(
        self,
        drone: Drone,
        network: Network,
        admission: AdmissionController,
        cm_type: CMType = CMType.CM7,
        step_m: float = DRONE_STEP_M,
        x_bounds: Tuple[float, float] = (-2000.0, 2000.0),
        y_bounds: Tuple[float, float] = (-2000.0, 2000.0),
    ) -> None:
        """
        Why use this function: Initializes the gradient-free positioning algorithm 
        controller, setting up state variables for tracking the drone's movement history.

        Args:
            drone (Drone): The drone object to be moved.
            network (Network): The network infrastructure.
            admission (AdmissionController): Source for resource load data.
            cm_type (CMType): The objective Control Metric to minimize. Defaults to CM7.
            step_m (float): Step size per update. Defaults to DRONE_STEP_M.
            x_bounds (Tuple[float, float]): Horizontal movement boundaries.
            y_bounds (Tuple[float, float]): Vertical movement boundaries.

        Returns:
            None
        """
        self.drone    = drone
        self.network  = network
        self.admission = admission
        self.cm_type  = cm_type
        self.step     = step_m
        self.x_bounds = x_bounds
        self.y_bounds = y_bounds

        # Internal state
        self._axis: Axis = Axis.X
        self._direction: float = +1.0        # +1 or -1
        self._prev_cm: Optional[float] = None
        self._reversed_this_axis: bool = False

        # Trajectory log: list of (x, y, cm) tuples
        self.trajectory = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def step_algorithm(self) -> Dict:
        """
        Why use this function: Executes one iteration of the gradient-free positioning 
        cycle: measures the CM, compares against history, and moves the drone accordingly.

        Args:
            None

        Returns:
            Dict: Current state data (coordinates, metric, axis, etc.) for logging.
        """
        cm_now = compute_cm(
            self.cm_type,
            self.drone.cell_id,
            self.network,
            self.admission,
        )

        if self._prev_cm is None:
            # First step: just record, no move yet
            self._prev_cm = cm_now
            self.trajectory.append((self.drone.x, self.drone.y, cm_now))
            return {"x": self.drone.x, "y": self.drone.y, "cm": cm_now}

        improved = cm_now <= self._prev_cm   # lower CM = better

        if improved:
            # Good move — keep going in the same direction
            self._reversed_this_axis = False
        else:
            if not self._reversed_this_axis:
                # First degradation on this axis → reverse
                self._direction *= -1.0
                self._reversed_this_axis = True
            else:
                # Degraded again after reversing → switch axis
                self._switch_axis()

        # Execute the move
        self._move()
        self._prev_cm = cm_now
        self.trajectory.append((self.drone.x, self.drone.y, cm_now))

        return {
            "x":        self.drone.x,
            "y":        self.drone.y,
            "cm":       cm_now,
            "axis":     self._axis.name,
            "direction": self._direction,
            "improved": improved,
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _move(self) -> None:
        """
        Why use this function: Moves the drone 1 meter (step size) along the currently active axis.

        Args:
            None

        Returns:
            None
        """
        delta = self._direction * self.step
        if self._axis == Axis.X:
            new_x = self.drone.x + delta
            self.drone.x = max(self.x_bounds[0], min(self.x_bounds[1], new_x))
        else:
            new_y = self.drone.y + delta
            self.drone.y = max(self.y_bounds[0], min(self.y_bounds[1], new_y))

    def _switch_axis(self) -> None:
        """
        Why use this function: Rotates the optimization axis (X to Y or Y to X) 
        when the current axis yields no further improvements.

        Args:
            None

        Returns:
            None
        """
        self._axis = Axis.Y if self._axis == Axis.X else Axis.X
        self._direction = +1.0
        self._reversed_this_axis = False
        self._prev_cm = None   # reset comparison after axis switch
