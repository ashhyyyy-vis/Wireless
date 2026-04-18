"""
Radio resource management: RSRP computation, cell selection, admission
control, proportional-fair scheduling, SINR, handover, and CSR tracking.

Paper reference: Section V-D, Equations in Section V-B/C
"""
import math
import numpy as np
from typing import Dict, List, Optional, Tuple

from simulation.config import (
    P_TX_BS_DBM, COVERAGE_THRESHOLD_DBM,
    THERMAL_NOISE_DBM, NOISE_FIGURE_DB,
    BANDWIDTH_HZ, CTRL_OVERHEAD_KAPPA,
    MIN_BITRATE_MBPS, HANDOVER_HYSTERESIS_DB, HANDOVER_TTT_S,
    ENVIRONMENT, BS_HEIGHT, NUM_SITES,
)
from simulation.network import Network, Cell
from simulation.antenna import bs_antenna_gain
from simulation.propagation import bs_path_loss, ShadowFadingService
from simulation.traffic import UE
from simulation.drone import Drone


# ---------------------------------------------------------------------------
# Noise floor (dBm)
# ---------------------------------------------------------------------------
NOISE_FLOOR_DBM = THERMAL_NOISE_DBM + NOISE_FIGURE_DB   # ≈ -98.94 dBm
NOISE_FLOOR_W   = 10 ** (NOISE_FLOOR_DBM / 10.0) * 1e-3


# ---------------------------------------------------------------------------
# Radio engine
# ---------------------------------------------------------------------------

class RadioEngine:
    """
    Computes received signal strengths and manages radio resources.
    """

    def __init__(
        self,
        network: Network,
        drone: Drone,
        shadow_svc: ShadowFadingService,
        env: str = ENVIRONMENT,
    ) -> None:
        """
        Why use this function: Initializes the radio engine with network data 
        and propagation models to enable signal strength and SINR calculations.

        Args:
            network (Network): The simulated network infrastructure.
            drone (Drone): The drone base station.
            shadow_svc (ShadowFadingService): The service providing shadow fading maps.
            env (str): The simulation environment. Defaults to ENVIRONMENT.

        Returns:
            None
        """
        self.net = network
        self.drone = drone
        self.shadow = shadow_svc
        self.env = env
        self.h_bs = BS_HEIGHT[env]

    # ------------------------------------------------------------------
    # RSRP from a regular BS cell to a UE
    # ------------------------------------------------------------------

    def cell_rsrp(self, cell: Cell, ue: UE) -> float:
        """
        Why use this function: Computes the Reference Signal Received Power (RSRP) from 
        a terrestrial cell to a UE, incorporating antenna gains, path loss, and shadow fading.

        Args:
            cell (Cell): The terrestrial cell transmitting the signal.
            ue (UE): The receiving User Equipment.

        Returns:
            float: RSRP in dBm.
        """
        site = self.net.sites[cell.site_id]

        d2d, dx, dy = self.net.dist_2d(site.x, site.y, ue.x, ue.y)
        d3d = math.sqrt(d2d**2 + (site.height - ue.z)**2)

        # Angles
        phi   = self.net.azimuth_angle_to_cell(ue.x, ue.y, cell)
        theta = self.net.elevation_angle_to_ue(
            site.x, site.y, site.height, ue.x, ue.y, ue.z
        )

        gain = bs_antenna_gain(phi, theta)
        pl   = bs_path_loss(d2d, d3d, self.h_bs, ue.z, self.env)
        sf   = self.shadow.get(cell.site_id, ue.x, ue.y)

        return P_TX_BS_DBM + gain - pl - sf

    # ------------------------------------------------------------------
    # RSRP from drone to UE
    # ------------------------------------------------------------------

    def drone_rsrp(self, ue: UE) -> float:
        """
        Why use this function: Computes the RSRP from the active drone base station to a UE.

        Args:
            ue (UE): The receiving User Equipment.

        Returns:
            float: RSRP in dBm, or -math.inf if the drone is inactive.
        """
        if not self.drone.active:
            return -math.inf
        d2d, _, _ = self.net.dist_2d(self.drone.x, self.drone.y, ue.x, ue.y)
        return self.drone.rsrp(ue.x, ue.y, ue.z, d2d=d2d, env=self.env)

    # ------------------------------------------------------------------
    # RSRP table for all active cells + drone
    # Returns dict: cell_id -> RSRP (dBm)
    # Drone is represented by cell_id = drone.cell_id
    # ------------------------------------------------------------------

    def rsrp_table(self, ue: UE) -> Dict[int, float]:
        """
        Why use this function: Generates a complete RSRP mapping from all active cells 
        (including the drone if active) to the UE. Used for cell selection and SINR calc.

        Args:
            ue (UE): The receiving User Equipment.

        Returns:
            Dict[int, float]: A dictionary mapping cell_id to its received RSRP in dBm.
        """
        table: Dict[int, float] = {}
        for cell in self.net.active_cells():
            table[cell.cell_id] = self.cell_rsrp(cell, ue)
        if self.drone.active:
            table[self.drone.cell_id] = self.drone_rsrp(ue)
        return table

    # ------------------------------------------------------------------
    # Cell selection: highest RSRP + CIO
    # CIO is 0 dB for regular cells, drone.cio for the drone
    # ------------------------------------------------------------------

    def select_cell(self, rsrp_table: Dict[int, float]) -> Optional[int]:
        """
        Why use this function: Performs cell selection for a UE by picking the cell with the 
        highest combined RSRP + CIO (Cell Individual Offset) that is above the coverage threshold.

        Args:
            rsrp_table (Dict[int, float]): Dictionary mapping cell IDs to RSRP values in dBm.

        Returns:
            Optional[int]: The cell_id of the best serving cell, or None if no cell provides coverage.
        """
        best_cell_id = None
        best_val = COVERAGE_THRESHOLD_DBM - 1e-9   # just below threshold

        for cell_id, rsrp in rsrp_table.items():
            # CIO: drone may have its own; regular cells have 0 dB
            cio = self.drone.cio if cell_id == self.drone.cell_id else 0.0
            val = rsrp + cio
            if val > best_val:
                best_val = val
                best_cell_id = cell_id

        return best_cell_id

    # ------------------------------------------------------------------
    # SINR computation
    # ------------------------------------------------------------------

    def sinr_db(self, serving_cell_id: int, ue: UE, rsrp_table: Dict[int, float]) -> float:
        """
        Why use this function: Computes the Signal-to-Interference-plus-Noise Ratio (SINR) 
        for a UE connected to a specific serving cell.

        Args:
            serving_cell_id (int): The ID of the UE's serving cell.
            ue (UE): The User Equipment (presently unused but available for extensions).
            rsrp_table (Dict[int, float]): The previously calculated RSRP table for this UE.

        Returns:
            float: The SINR in dB. Returns -math.inf if the signal is zero.
        """
        signal_dbm = rsrp_table.get(serving_cell_id, -math.inf)
        signal_w   = 10 ** (signal_dbm / 10.0) * 1e-3

        interf_w = 0.0
        for cell_id, rsrp_dbm in rsrp_table.items():
            if cell_id == serving_cell_id:
                continue
            interf_w += 10 ** (rsrp_dbm / 10.0) * 1e-3

        sinr_w = signal_w / (interf_w + NOISE_FLOOR_W)
        if sinr_w <= 0:
            return -math.inf
        return 10.0 * math.log10(sinr_w)

    # ------------------------------------------------------------------
    # Required resource fraction for a new UE
    # ------------------------------------------------------------------

    def required_resource_fraction(self, sinr_db: float) -> float:
        """
        Why use this function: Calculates what fraction of a cell's bandwidth must be allocated 
        to a UE to meet the minimum required bitrate (MIN_BITRATE_MBPS) given its SINR.

        Args:
            sinr_db (float): The SINR of the UE in dB.

        Returns:
            float: Resource fraction between 0.0 and 1.0. Returns 1.0 if conditions are too poor to serve.
        """
        sinr_lin = 10 ** (sinr_db / 10.0)
        effective_bw_mbps = (
            (1.0 - CTRL_OVERHEAD_KAPPA)
            * BANDWIDTH_HZ / 1e6
            * math.log2(1.0 + sinr_lin)
        )
        if effective_bw_mbps <= 0:
            return 1.0   # cannot serve
        frac = MIN_BITRATE_MBPS / effective_bw_mbps
        return min(frac, 1.0)


# ---------------------------------------------------------------------------
# CSR tracker
# ---------------------------------------------------------------------------

class CSRTracker:
    """
    Tracks call attempts and successes for the CSR metric.
    Only considers UEs originating in the CSR scope cells
    (pre-incident best-server areas of the failing site + neighbours).
    """

    def __init__(self) -> None:
        """
        Why use this function: Initializes the tracker to monitor call 
        attempts and successes within the pre-defined CSR scope.

        Args:
            None

        Returns:
            None
        """
        self.attempts = 0
        self.successes = 0
        self._history: List[Tuple[float, float]] = []   # (time, csr)

    def record_attempt(self, success: bool, sim_time: float) -> None:
        """
        Why use this function: Logs a call admission event for tracking the success rate.

        Args:
            success (bool): True if the call was admitted, False if dropped or blocked.
            sim_time (float): The current simulation time (unused internally but kept for compatibility).

        Returns:
            None
        """
        self.attempts += 1
        if success:
            self.successes += 1

    @property
    def csr(self) -> float:
        """
        Why use this function: Calculates the Call Success Rate based on recorded attempts.

        Args:
            None

        Returns:
            float: Call Success Rate between 0.0 and 1.0. Defaults to 1.0 if no attempts made.
        """
        if self.attempts == 0:
            return 1.0
        return self.successes / self.attempts

    def snapshot(self, sim_time: float):
        self._history.append((sim_time, self.csr))

    def reset(self) -> None:
        """
        Why use this function: Clears the call history metrics, typically used when shifting
        from Phase I to Phase II to capture purely post-disaster stats.

        Args:
            None

        Returns:
            None
        """
        self.attempts = 0
        self.successes = 0


# ---------------------------------------------------------------------------
# Admission controller + scheduler
# ---------------------------------------------------------------------------

class AdmissionController:
    """
    Proportional-fair admission and scheduling.
    Tracks per-cell resource utilisation.
    """

    def __init__(self, network: Network, drone: Drone) -> None:
        """
        Why use this function: Initializes the admission controller to manage 
        resource allocations across all terrestrial cells and the drone.

        Args:
            network (Network): The network object.
            drone (Drone): The drone base station object.

        Returns:
            None
        """
        self.net = network
        self.drone = drone
        # cell_id -> {ue_id -> resource_fraction}
        self._allocations: Dict[int, Dict[int, float]] = {}

        # Initialize allocation tables for all cells + drone
        for cell in network.cells:
            self._allocations[cell.cell_id] = {}
        # Drone cell allocated separately
        if drone.cell_id >= 0:
            self._allocations[drone.cell_id] = {}

    def _ensure_cell(self, cell_id: int):
        if cell_id not in self._allocations:
            self._allocations[cell_id] = {}

    def cell_load(self, cell_id: int) -> float:
        """
        Why use this function: Calculates the total fraction of resources currently in use by all UEs in a cell.

        Args:
            cell_id (int): The ID of the cell to query.

        Returns:
            float: Total resource load fraction.
        """
        self._ensure_cell(cell_id)
        return sum(self._allocations[cell_id].values())

    def cell_load_per_ue(self, cell_id: int) -> float:
        """
        Why use this function: Calculates the average resource fraction per UE in a given cell. 
        This is heavily used by the positioning algorithm (CM4-CM7).

        Args:
            cell_id (int): The ID of the cell to query.

        Returns:
            float: Average load per UE. Defaults to 0.0 if empty.
        """
        self._ensure_cell(cell_id)
        allocs = self._allocations[cell_id]
        if not allocs:
            return 0.0
        return sum(allocs.values()) / len(allocs)

    def num_ues(self, cell_id: int) -> int:
        """
        Why use this function: Fetches the number of User Equipments currently admitted to a cell.

        Args:
            cell_id (int): The ID of the cell to query.

        Returns:
            int: The number of active UEs in the cell.
        """
        self._ensure_cell(cell_id)
        return len(self._allocations[cell_id])

    def try_admit(
        self,
        ue: UE,
        cell_id: int,
        req_fraction: float,
    ) -> bool:
        """
        Why use this function: Attempts to admit a UE to a cell, succeeding only if the 
        cell has enough unused capacity to cover req_fraction.

        Args:
            ue (UE): The UE instance to admit.
            cell_id (int): The target cell ID.
            req_fraction (float): The fraction [0.0 - 1.0] of bandwidth the UE needs.

        Returns:
            bool: True if admitted, False if blocked by capacity.
        """
        self._ensure_cell(cell_id)
        current_load = self.cell_load(cell_id)
        if current_load + req_fraction <= 1.0:
            self._allocations[cell_id][ue.ue_id] = req_fraction
            ue.serving_cell_id = cell_id
            ue.resource_fraction = req_fraction
            # Update cell's UE list
            cell_or_drone = self._get_cell_obj(cell_id)
            if cell_or_drone and ue.ue_id not in cell_or_drone.assigned_ues:
                cell_or_drone.assigned_ues.append(ue.ue_id)
            return True
        return False

    def release(self, ue: UE) -> None:
        """
        Why use this function: Frees the cell resources allocated to a UE when its call finishes or drops.

        Args:
            ue (UE): The User Equipment whose resources need releasing.

        Returns:
            None
        """
        if ue.serving_cell_id is None:
            return
        cell_id = ue.serving_cell_id
        self._ensure_cell(cell_id)
        self._allocations[cell_id].pop(ue.ue_id, None)
        cell_or_drone = self._get_cell_obj(cell_id)
        if cell_or_drone and ue.ue_id in cell_or_drone.assigned_ues:
            cell_or_drone.assigned_ues.remove(ue.ue_id)
        ue.serving_cell_id = None

    def release_all_in_cell(self, cell_id: int) -> None:
        """
        Why use this function: Forcibly drops/releases all UEs currently attached to a cell. 
        Used when a site fails during the simulated disaster.

        Args:
            cell_id (int): The affected cell's ID.

        Returns:
            None
        """
        self._ensure_cell(cell_id)
        self._allocations[cell_id].clear()

    def _get_cell_obj(self, cell_id: int):
        """Return Cell or a drone proxy with assigned_ues list."""
        if cell_id == self.drone.cell_id:
            return self.drone if hasattr(self.drone, 'assigned_ues') else None
        if 0 <= cell_id < len(self.net.cells):
            return self.net.cells[cell_id]
        return None

    def update_loads(self) -> None:
        """
        Why use this function: Refreshes the `load` attribute on all Network cell objects. 
        Important for metrics calculated just before an algorithm tick.

        Args:
            None

        Returns:
            None
        """
        for cell in self.net.cells:
            cell.load = self.cell_load(cell.cell_id)
