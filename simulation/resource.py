"""
Radio resource management: RSRP computation, cell selection, admission
control, proportional-fair scheduling, SINR, handover, and CSR tracking.

Paper reference: Section V-D, Equations in Section V-B/C
"""
import math
import numpy as np
from typing import Dict, List, Optional, Tuple

from .config import (
    P_TX_BS_DBM, COVERAGE_THRESHOLD_DBM,
    THERMAL_NOISE_DBM, NOISE_FIGURE_DB,
    BANDWIDTH_HZ, CTRL_OVERHEAD_KAPPA,
    MIN_BITRATE_MBPS, HANDOVER_HYSTERESIS_DB, HANDOVER_TTT_S,
    ENVIRONMENT, BS_HEIGHT, NUM_SITES,
)
from .network import Network, Cell
from .antenna import bs_antenna_gain
from .propagation import bs_path_loss, ShadowFadingService
from .traffic import UE
from .drone import Drone


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

    def dbm_to_watts(self, dbm: float) -> float:
        """Helper to convert dBm to linear Watts."""
        if dbm == -math.inf:
            return 0.0
        return (10 ** (dbm / 10.0)) * 1e-3

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
        pl   = bs_path_loss(d2d, d3d, self.h_bs, ue.z, self.env, rng=self.shadow.rng)
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
        return self.drone.rsrp(ue.x, ue.y, ue.z, d2d=d2d, env=self.env, rng=self.shadow.rng)

    # ------------------------------------------------------------------
    # Optimized RSRP table using cache
    # ------------------------------------------------------------------

    def get_optimized_rsrp_table(self, ue: UE) -> Dict[int, float]:
        """
        Why use this function: Retrieves the RSRP table using cached terrestrial values 
        to avoid redundant stationary calculations, only computing the new drone RSRP.
        """
        if not ue.terrestrial_rsrp_cache:
            # Populate cache if empty
            for cell in self.net.active_cells():
                dbm = self.cell_rsrp(cell, ue)
                ue.terrestrial_rsrp_cache[cell.cell_id] = dbm
                ue.terrestrial_watts_cache[cell.cell_id] = self.dbm_to_watts(dbm)
        
        # Start with cached terrestrial values
        table = ue.terrestrial_rsrp_cache.copy()
        
        # Add dynamic drone RSRP
        if self.drone.active:
            table[self.drone.cell_id] = self.drone_rsrp(ue)
            
        return table

    # ------------------------------------------------------------------
    # Update UE's resource fraction based on latest conditions
    # ------------------------------------------------------------------
    
    def update_ue_resource_fraction(self, ue: UE) -> float:
        """
        Recalculates the resource fraction a UE needs based on current positions.
        """
        if ue.serving_cell_id is None:
            return 0.0
        
        rsrp_tbl = self.get_optimized_rsrp_table(ue)
        sinr = self.sinr_db(ue.serving_cell_id, ue, rsrp_tbl)
        new_frac = self.required_resource_fraction(sinr)
        
        ue.resource_fraction = new_frac
        return new_frac

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
        """
        signal_dbm = rsrp_table.get(serving_cell_id, -math.inf)
        signal_w   = self.dbm_to_watts(signal_dbm)

        interf_w = 0.0
        for cell_id, rsrp_dbm in rsrp_table.items():
            if cell_id == serving_cell_id:
                continue
            
            # Optimization: Use cached Watts for terrestrial cells
            if cell_id in ue.terrestrial_watts_cache:
                interf_w += ue.terrestrial_watts_cache[cell_id]
            else:
                interf_w += self.dbm_to_watts(rsrp_dbm)

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
        """
        self.attempts = 0
        self.successes = 0
        self._history: List[Tuple[float, float]] = []   # (time, csr)

    def record_attempt(self, sim_time: float) -> None:
        """
        Why use this function: Logs a call initiation attempt.
        """
        self.attempts += 1

    def record_success(self, sim_time: float) -> None:
        """
        Why use this function: Logs a call that finished successfully (not dropped).
        """
        self.successes += 1

    @property
    def csr(self) -> float:
        """
        Why use this function: Calculates the Call Success Rate based on recorded attempts.

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
        """
        self.net = network
        self.drone = drone
        # cell_id -> {ue_id -> resource_fraction}
        self._allocations: Dict[int, Dict[int, float]] = {}
        # Incremental load tracking: cell_id -> total_fraction
        self._cell_loads: Dict[int, float] = {}

        # Initialize allocation tables for all cells + drone
        for cell in network.cells:
            cid = cell.cell_id
            self._allocations[cid] = {}
            self._cell_loads[cid] = 0.0
            
        # Drone cell allocated separately
        if drone.cell_id >= 0:
            cid = drone.cell_id
            self._allocations[cid] = {}
            self._cell_loads[cid] = 0.0

    def _ensure_cell(self, cell_id: int):
        if cell_id not in self._allocations:
            self._allocations[cell_id] = {}
            self._cell_loads[cell_id] = 0.0

    def cell_load(self, cell_id: int) -> float:
        """
        Why use this function: Calculates the total fraction of resources currently in use.
        """
        self._ensure_cell(cell_id)
        return self._cell_loads[cell_id]

    def cell_load_per_ue(self, cell_id: int) -> float:
        """
        Why use this function: Calculates the average resource fraction per UE.
        """
        self._ensure_cell(cell_id)
        allocs = self._allocations[cell_id]
        if not allocs:
            return 0.0
        return self._cell_loads[cell_id] / len(allocs)

    def num_ues(self, cell_id: int) -> int:
        """
        Why use this function: Fetches the number of active UEs in the cell.
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
        Attempts to admit a UE to a cell.
        """
        self._ensure_cell(cell_id)
        if self._cell_loads[cell_id] + req_fraction <= 1.0:
            self._allocations[cell_id][ue.ue_id] = req_fraction
            self._cell_loads[cell_id] += req_fraction
            ue.serving_cell_id = cell_id
            ue.resource_fraction = req_fraction
            # Update cell's UE list
            cell_or_drone = self._get_cell_obj(cell_id)
            if cell_or_drone and ue.ue_id not in cell_or_drone.assigned_ues:
                cell_or_drone.assigned_ues.append(ue.ue_id)
            return True
        return False

    def rebalance_all_cells(self, radio: RadioEngine, active_ues: Dict[int, UE]) -> List[int]:
        """
        Why use this function: Implements Dynamic Dropping (Paper §V-D). 
        Updates required fractions for all UEs and drops the 'hungriest' if load > 1.0.
        
        Returns: List of ue_ids that were dropped during rebalancing.
        """
        dropped_ues = []
        
        # 1. Update all fractions and recalculate totals
        for cid in self._allocations:
            new_total = 0.0
            for uid in list(self._allocations[cid].keys()):
                ue = active_ues.get(uid)
                if ue:
                    new_frac = radio.update_ue_resource_fraction(ue)
                    self._allocations[cid][uid] = new_frac
                    new_total += new_frac
            self._cell_loads[cid] = new_total
        
        # 2. Check each cell for overload
        for cid in list(self._allocations.keys()):
            if self._cell_loads[cid] > 1.000001:
                # Sort UEs by fraction ascending (Paper: "unsatisfied UE that requires the least ... amount")
                uids_sorted = sorted(self._allocations[cid].keys(), 
                                     key=lambda u: self._allocations[cid][u])
                
                new_load = 0.0
                to_keep = []
                for uid in uids_sorted:
                    f = self._allocations[cid][uid]
                    if new_load + f <= 1.0:
                        new_load += f
                        to_keep.append(uid)
                    else:
                        dropped_ues.append(uid)
                
                # Apply changes to allocations
                self._allocations[cid] = {uid: self._allocations[cid][uid] for uid in to_keep}
                self._cell_loads[cid] = new_load
                
                # Update cell object's assigned_ues
                cell_obj = self._get_cell_obj(cid)
                if cell_obj:
                    cell_obj.assigned_ues = list(to_keep)
                    
        return dropped_ues

    def release(self, ue: UE) -> None:
        """
        Why use this function: Frees the cell resources allocated to a UE.
        """
        if ue.serving_cell_id is None:
            return
        cell_id = ue.serving_cell_id
        self._ensure_cell(cell_id)
        
        old_frac = self._allocations[cell_id].pop(ue.ue_id, 0.0)
        self._cell_loads[cell_id] = max(0.0, self._cell_loads[cell_id] - old_frac)

        cell_or_drone = self._get_cell_obj(cell_id)
        if cell_or_drone and ue.ue_id in cell_or_drone.assigned_ues:
            cell_or_drone.assigned_ues.remove(ue.ue_id)
        ue.serving_cell_id = None

    def release_all_in_cell(self, cell_id: int) -> None:
        """
        Why use this function: Forcibly drops/releases all UEs currently attached to a cell.
        """
        self._ensure_cell(cell_id)
        self._allocations[cell_id].clear()
        self._cell_loads[cell_id] = 0.0

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
        """
        for cell in self.net.cells:
            cell.load = self.cell_load(cell.cell_id)
