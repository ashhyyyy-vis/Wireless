"""
UE lifecycle: Poisson arrivals, hotspot intensity, call duration, and
spatial positioning.

Paper reference: Section V-C
"""
import math
import numpy as np
from dataclasses import dataclass, field
from typing import Optional, List, Tuple, Dict

from .config import (
    LAMBDA_ARRIVAL, CALL_DURATION_MEAN_S,
    HOTSPOT_RADIUS_M, ENVIRONMENT, ISD,
)


# ---------------------------------------------------------------------------
# UE data class
# ---------------------------------------------------------------------------

@dataclass
class UE:
    """Represents an active call / user equipment."""
    ue_id: int
    x: float                    # 2-D position (metres)
    y: float
    z: float = 1.5              # UE height (ground level)
    arrival_time: float = 0.0
    duration: float = 0.0       # call duration (seconds)
    serving_cell_id: Optional[int] = None   # None = unserved
    in_csr_scope: bool = False  # True if UE is in the CSR measurement area
    in_hotspot: bool = False
    resource_fraction: float = 0.0  # fraction of cell resources allocated
    # Cached RSRP values from stationary terrestrial cells: cell_id -> RSRP (dBm)
    terrestrial_rsrp_cache: Dict[int, float] = field(default_factory=dict)

    @property
    def departure_time(self) -> float:
        """
        Why use this function: Calculates the absolute time when the UE's call will complete.

        Args:
            None

        Returns:
            float: Simulated time in seconds when the call departs.
        """
        return self.arrival_time + self.duration

    def is_covered(self) -> bool:
        """
        Why use this function: Determines if the UE is successfully connected to a serving cell.

        Args:
            None

        Returns:
            bool: True if the UE has a serving cell, False otherwise.
        """
        return self.serving_cell_id is not None


# ---------------------------------------------------------------------------
# Hotspot geometry
# ---------------------------------------------------------------------------

@dataclass
class Hotspot:
    """Circular traffic hotspot."""
    cx: float           # centre x (metres)
    cy: float           # centre y (metres)
    radius: float = HOTSPOT_RADIUS_M
    rho: float = 1.0    # traffic intensity multiplier (ρ)
    active: bool = False

    def contains(self, x: float, y: float) -> bool:
        """
        Why use this function: Checks if a given 2D coordinate falls within the hotspot's radius.

        Args:
            x (float): X coordinate to check.
            y (float): Y coordinate to check.

        Returns:
            bool: True if the point is inside the hotspot, False otherwise.
        """
        dx, dy = x - self.cx, y - self.cy
        return math.sqrt(dx * dx + dy * dy) <= self.radius

    def move(self, dx: float, dy: float) -> None:
        """
        Why use this function: Moves the hotspot center by a given displacement.

        Args:
            dx (float): Displacement in the X direction.
            dy (float): Displacement in the Y direction.

        Returns:
            None
        """
        self.cx += dx
        self.cy += dy


# ---------------------------------------------------------------------------
# Traffic generator
# ---------------------------------------------------------------------------

class TrafficGenerator:
    """
    Generates UE arrivals as a Poisson process over the cluster area.
    Inside the hotspot the arrival rate is scaled by ρ.

    The cluster area is approximated as a square with side = 3.5 × ISD,
    and UEs are placed uniformly within it (rejection method for hotspot).
    """

    def __init__(
        self,
        env: str = ENVIRONMENT,
        hotspot: Optional[Hotspot] = None,
        rng: Optional[np.random.Generator] = None,
        lambda_override: Optional[float] = None,
    ) -> None:
        """
        Why use this function: Initializes the traffic generator with specific 
        arrival rates and hotspot configurations.

        Args:
            env (str): The environment type.
            hotspot (Optional[Hotspot]): A circular area with higher traffic intensity.
            rng (Optional[np.random.Generator]): Random number generator instance.
            lambda_override (Optional[float]): Custom arrival rate.

        Returns:
            None
        """
        self.env = env
        self.hotspot = hotspot
        self.rng = rng if rng is not None else np.random.default_rng()
        self._lambda = lambda_override if lambda_override else LAMBDA_ARRIVAL[env]
        self._ue_counter = 0

        # Cluster bounding box
        isd = ISD[env]
        self._half = 2.0 * isd   # cluster half-side (generous)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def next_arrival_time(self, current_time: float) -> float:
        """
        Why use this function: Determines the time of the next UE arrival by sampling 
        from an exponential distribution based on the effective arrival rate.

        Args:
            current_time (float): The current simulation time in seconds.

        Returns:
            float: The absolute simulation time of the next arrival.
        """
        base_area = (2 * self._half) ** 2
        hs_area = (math.pi * HOTSPOT_RADIUS_M ** 2
                   if (self.hotspot and self.hotspot.active) else 0.0)
        rho = self.hotspot.rho if (self.hotspot and self.hotspot.active) else 1.0

        # Effective total rate = λ * (base_area + (ρ-1)*hs_area) / base_area
        # We simplify: assume density λ/m² outside, ρ*λ/m² inside.
        density_outside = self._lambda / base_area
        total_rate = (density_outside * (base_area - hs_area)
                      + density_outside * rho * hs_area)
        if total_rate <= 0:
            total_rate = self._lambda

        inter_arrival = self.rng.exponential(1.0 / total_rate)
        return current_time + inter_arrival

    def generate_ue(
        self,
        arrival_time: float,
        csr_scope_cell_ids: Optional[List[int]] = None,
        pre_incident_best_server: Optional[dict] = None,
    ) -> UE:
        """
        Why use this function: Creates a new UE object, distributing its location inside or 
        outside the hotspot probabilistically based on the hotspot intensity (ρ).

        Args:
            arrival_time (float): The simulated time the UE call starts.
            csr_scope_cell_ids (Optional[List[int]]): Ignored in current model.
            pre_incident_best_server (Optional[dict]): Ignored in current model.

        Returns:
            UE: A new UE instance with an assigned position and duration.
        """
        rho = self.hotspot.rho if (self.hotspot and self.hotspot.active) else 1.0

        # Decide whether this UE is in the hotspot
        in_hotspot = False
        if self.hotspot and self.hotspot.active:
            # Probability ∝ area * density
            base_area = (2 * self._half) ** 2
            hs_area = math.pi * HOTSPOT_RADIUS_M ** 2
            p_hotspot = (rho * hs_area) / (base_area - hs_area + rho * hs_area)
            in_hotspot = self.rng.random() < p_hotspot

        if in_hotspot:
            x, y = self._sample_in_hotspot()
        else:
            x, y = self._sample_outside_hotspot()

        duration = self.rng.exponential(CALL_DURATION_MEAN_S)

        self._ue_counter += 1
        ue = UE(
            ue_id=self._ue_counter,
            x=x,
            y=y,
            arrival_time=arrival_time,
            duration=duration,
            in_hotspot=in_hotspot,
        )
        return ue

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _sample_uniform(self) -> Tuple[float, float]:
        x = self.rng.uniform(-self._half, self._half)
        y = self.rng.uniform(-self._half, self._half)
        return x, y

    def _sample_in_hotspot(self) -> Tuple[float, float]:
        """
        Why use this function: Rejection samples a coordinate that is strictly inside 
        the active hotspot circle.

        Args:
            None

        Returns:
            Tuple[float, float]: Random (x, y) coordinates inside the hotspot.
        """
        if not (self.hotspot and self.hotspot.active):
            return self._sample_uniform()
        for _ in range(1000):
            r = self.rng.uniform(0, HOTSPOT_RADIUS_M)
            theta = self.rng.uniform(0, 2 * math.pi)
            x = self.hotspot.cx + r * math.cos(theta)
            y = self.hotspot.cy + r * math.sin(theta)
            return x, y
        # Fallback
        return self.hotspot.cx, self.hotspot.cy

    def _sample_outside_hotspot(self) -> Tuple[float, float]:
        """
        Why use this function: Rejection samples a coordinate uniformly from the 
        cluster area that is explicitly outside the active hotspot.

        Args:
            None

        Returns:
            Tuple[float, float]: Random (x, y) coordinates outside the hotspot.
        """
        if not (self.hotspot and self.hotspot.active):
            return self._sample_uniform()
        for _ in range(10000):
            x, y = self._sample_uniform()
            if not self.hotspot.contains(x, y):
                return x, y
        # Fallback: return a point far from hotspot
        return -self._half * 0.5, -self._half * 0.5
