"""
Network topology: 12 three-sectorized sites on a hexagonal grid with
wraparound (periodic boundary conditions) to mimic an infinite network.

Paper reference: Section V-A
"""
import math
import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple

from simulation.config import (
    ISD, NUM_SITES, NUM_SECTORS, SECTOR_BORESIGHTS_DEG,
    BS_HEIGHT, FAILING_SITE_ID, ENVIRONMENT,
)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Cell:
    """One sector-cell of a base station."""
    cell_id: int              # global cell index (site_id * 3 + sector_idx)
    site_id: int
    sector_idx: int           # 0, 1, 2
    boresight_deg: float      # azimuth boresight (30, 150, or 270 degrees)

    # State
    active: bool = True       # False when parent site has failed
    assigned_ues: List = field(default_factory=list)   # list of UE ids
    load: float = 0.0         # fraction of resources in use [0, 1]

    def reset_load(self):
        self.load = 0.0

    @property
    def num_ues(self) -> int:
        return len(self.assigned_ues)


@dataclass
class Site:
    """One base-station site with three sector cells."""
    site_id: int
    x: float          # metres (2D)
    y: float
    height: float     # antenna height (metres)
    cells: List[Cell] = field(default_factory=list)
    active: bool = True

    def fail(self):
        """Mark site and all its cells as inactive."""
        self.active = False
        for c in self.cells:
            c.active = False
            c.assigned_ues.clear()

    def restore(self):
        self.active = True
        for c in self.cells:
            c.active = True


# ---------------------------------------------------------------------------
# Hex grid generation
# ---------------------------------------------------------------------------

def _hex_sites(isd: float) -> List[Tuple[float, float]]:
    """
    Why use this function: Generates the 2D coordinates for a 12-site hexagonal cluster.

    Args:
        isd (float): Inter-site distance in meters.

    Returns:
        List[Tuple[float, float]]: A list of (x, y) coordinates for each site.
    """
    # Hex lattice basis vectors
    d = isd
    # Row-based hex positions for a 12-site cluster:
    # Layer 0: centre (1 site)
    # Layer 1: first ring (6 sites)
    # Outer partial: 5 more sites to reach 12
    # We place them in a standard hexagonal arrangement.

    positions = []
    # All 12 canonical hex positions (flat-top hex, ISD = d)
    # Using axial coordinates converted to Cartesian
    hex_axial = [
        (0, 0),                          # site 0 – centre (failing)
        (1, 0), (0, 1), (-1, 1),         # ring 1 part A
        (-1, 0), (0, -1), (1, -1),       # ring 1 part B
        (2, 0), (1, 1), (0, 2),          # ring 2 partial
        (-1, 2), (-2, 1),                # ring 2 cont.
    ]
    for (q, r) in hex_axial:
        x = d * (q + r * 0.5)
        y = d * (r * math.sqrt(3) / 2)
        positions.append((x, y))

    return positions


# ---------------------------------------------------------------------------
# Wraparound helper
# ---------------------------------------------------------------------------

def _cluster_basis_vectors(isd: float) -> List[Tuple[float, float]]:
    """
    Why use this function: Calculates the 6 periodic shift vectors for the wraparound 
    boundary condition in the 12-site cluster, simulating an infinite network.

    Args:
        isd (float): Inter-site distance in meters.

    Returns:
        List[Tuple[float, float]]: A list of 6 (dx, dy) shift vectors.
    """
    # For a cluster of N_sites ~ 12, the repeat vectors are roughly
    # the diagonal of the cluster bounding box.  A standard 7-cell
    # cluster has period vectors |v| = sqrt(7)*ISD; for 12 cells
    # we use |v| = sqrt(12)*ISD * unit directions.
    L = math.sqrt(12) * isd
    angles = [k * 60.0 for k in range(6)]
    return [(L * math.cos(math.radians(a)), L * math.sin(math.radians(a)))
            for a in angles]


def get_distance_2d(
    ax: float, ay: float,
    bx: float, by: float,
    shift_vectors: List[Tuple[float, float]],
) -> Tuple[float, float, float]:
    """
    Why use this function: Computes the shortest 2D distance between two points A and B 
    accounting for periodic wraparound boundaries.

    Args:
        ax (float): X coordinate of point A.
        ay (float): Y coordinate of point A.
        bx (float): X coordinate of point B.
        by (float): Y coordinate of point B.
        shift_vectors (List[Tuple[float, float]]): The cluster's periodic shift vectors.

    Returns:
        Tuple[float, float, float]: The shortest distance, dx, and dy.
    """
    best = math.inf
    best_dx, best_dy = bx - ax, by - ay
    # Check original + 6 images
    for (svx, svy) in [(0, 0)] + shift_vectors:
        dx = (bx + svx) - ax
        dy = (by + svy) - ay
        d = math.sqrt(dx * dx + dy * dy)
        if d < best:
            best, best_dx, best_dy = d, dx, dy
    return best, best_dx, best_dy


def get_distance_3d(
    ax: float, ay: float, az: float,
    bx: float, by: float, bz: float,
    shift_vectors: List[Tuple[float, float]],
) -> float:
    """
    Why use this function: Computes the 3D distance between point A and B with 2D wraparound.

    Args:
        ax (float): X coordinate of point A.
        ay (float): Y coordinate of point A.
        az (float): Z coordinate (height) of point A.
        bx (float): X coordinate of point B.
        by (float): Y coordinate of point B.
        bz (float): Z coordinate (height) of point B.
        shift_vectors (List[Tuple[float, float]]): The cluster's periodic shift vectors.

    Returns:
        float: The 3D distance accounting for wraparound.
    """
    d2d, _, _ = get_distance_2d(ax, ay, bx, by, shift_vectors)
    dz = bz - az
    return math.sqrt(d2d * d2d + dz * dz)


# ---------------------------------------------------------------------------
# Network class
# ---------------------------------------------------------------------------

class Network:
    """
    Holds all sites/cells and provides lookup helpers.
    """

    def __init__(self, env: str = ENVIRONMENT) -> None:
        """
        Why use this function: Initializes the network topology with 12 sites 
        and 36 cells, setting up coordinates and wraparound shift vectors.

        Args:
            env (str): The environment type ("urban" or "rural"). Defaults to ENVIRONMENT.

        Returns:
            None
        """
        self.env = env
        self.isd = ISD[env]
        self.bs_height = BS_HEIGHT[env]

        # Build sites
        positions = _hex_sites(self.isd)
        self.sites: List[Site] = []
        self.cells: List[Cell] = []

        for site_id, (x, y) in enumerate(positions):
            site_cells = []
            for sec_idx, boresight in enumerate(SECTOR_BORESIGHTS_DEG):
                cell_id = site_id * NUM_SECTORS + sec_idx
                c = Cell(
                    cell_id=cell_id,
                    site_id=site_id,
                    sector_idx=sec_idx,
                    boresight_deg=boresight,
                )
                site_cells.append(c)
                self.cells.append(c)
            site = Site(
                site_id=site_id,
                x=x,
                y=y,
                height=self.bs_height,
                cells=site_cells,
            )
            self.sites.append(site)

        # Wraparound shift vectors
        self.shift_vectors = _cluster_basis_vectors(self.isd)

        # Neighbour cell IDs of the failing site (for CSR scope)
        self._neighbour_cell_ids: Optional[List[int]] = None

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    def get_site(self, site_id: int) -> Site:
        """
        Why use this function: Retrieves a Site object by its ID.

        Args:
            site_id (int): The ID of the site.

        Returns:
            Site: The Site object.
        """
        return self.sites[site_id]

    def get_cell(self, cell_id: int) -> Cell:
        """
        Why use this function: Retrieves a Cell object by its ID.

        Args:
            cell_id (int): The ID of the cell.

        Returns:
            Cell: The Cell object.
        """
        return self.cells[cell_id]

    def active_cells(self) -> List[Cell]:
        """
        Why use this function: Returns a list of all active cells in the network.

        Args:
            None

        Returns:
            List[Cell]: A list of Cell objects that are currently active.
        """
        return [c for c in self.cells if c.active]

    def failing_site(self) -> Site:
        """
        Why use this function: Retrieves the pre-configured failing site.

        Args:
            None

        Returns:
            Site: The Site object representing the failing site.
        """
        return self.sites[FAILING_SITE_ID]

    def fail_site(self, site_id: int = FAILING_SITE_ID) -> None:
        """
        Why use this function: Disables a specific site to simulate a failure.

        Args:
            site_id (int): The ID of the site to fail. Defaults to FAILING_SITE_ID.

        Returns:
            None
        """
        self.sites[site_id].fail()

    # ------------------------------------------------------------------
    # Neighbour detection (cells adjacent to the failing site)
    # ------------------------------------------------------------------

    def neighbour_cell_ids_of_failing_site(self) -> List[int]:
        """
        Why use this function: Retrieves the cell IDs of all immediate neighbours
        surrounding the failing site, which is used to define the area for CSR measurement.

        Args:
            None

        Returns:
            List[int]: A list of neighbouring cell IDs.
        """
        if self._neighbour_cell_ids is not None:
            return self._neighbour_cell_ids

        fs = self.failing_site()
        result = []
        for site in self.sites:
            if site.site_id == FAILING_SITE_ID:
                continue
            d2d, _, _ = get_distance_2d(
                fs.x, fs.y, site.x, site.y, self.shift_vectors
            )
            if d2d <= 1.5 * self.isd:
                for c in site.cells:
                    result.append(c.cell_id)

        self._neighbour_cell_ids = result
        return result

    # ------------------------------------------------------------------
    # CSR-scope cell IDs (failing site cells + neighbour cells)
    # ------------------------------------------------------------------

    def csr_scope_cell_ids(self) -> List[int]:
        """
        Why use this function: Computes the full set of cell IDs that are within the 
        Call Success Rate (CSR) performance scope (failing site + its neighbours).

        Args:
            None

        Returns:
            List[int]: The list of cell IDs in the CSR scope.
        """
        failing_cell_ids = [c.cell_id for c in self.failing_site().cells]
        return failing_cell_ids + self.neighbour_cell_ids_of_failing_site()

    # ------------------------------------------------------------------
    # Distance helpers (delegating to module-level functions)
    # ------------------------------------------------------------------

    def dist_2d(self, ax: float, ay: float, bx: float, by: float) -> Tuple[float, float, float]:
        """
        Why use this function: Instance wrapper for getting the wraparound 2D distance.

        Args:
            ax (float): X coordinate of point A.
            ay (float): Y coordinate of point A.
            bx (float): X coordinate of point B.
            by (float): Y coordinate of point B.

        Returns:
            Tuple[float, float, float]: Shortest distance, dx, and dy.
        """
        return get_distance_2d(ax, ay, bx, by, self.shift_vectors)

    def dist_3d(self, ax: float, ay: float, az: float, bx: float, by: float, bz: float) -> float:
        """
        Why use this function: Instance wrapper for getting the wraparound 3D distance.

        Args:
            ax (float): X coordinate of point A.
            ay (float): Y coordinate of point A.
            az (float): Z coordinate of point A.
            bx (float): X coordinate of point B.
            by (float): Y coordinate of point B.
            bz (float): Z coordinate of point B.

        Returns:
            float: Shortest 3D distance.
        """
        return get_distance_3d(ax, ay, az, bx, by, bz, self.shift_vectors)

    # ------------------------------------------------------------------
    # Angle helpers (for antenna gain calculation)
    # ------------------------------------------------------------------

    def azimuth_angle_to_cell(
        self, ue_x: float, ue_y: float,
        cell: Cell,
    ) -> float:
        """
        Why use this function: Calculates the horizontal azimuth angle from the cell's boresight to a UE.

        Args:
            ue_x (float): UE X coordinate.
            ue_y (float): UE Y coordinate.
            cell (Cell): The Cell object targeting.

        Returns:
            float: Azimuth angle mapped to [-180, 180] degrees.
        """
        site = self.sites[cell.site_id]
        _, dx, dy = get_distance_2d(
            site.x, site.y, ue_x, ue_y, self.shift_vectors
        )
        angle_to_ue = math.degrees(math.atan2(dy, dx))
        phi = angle_to_ue - cell.boresight_deg
        # Wrap to [-180, 180]
        phi = (phi + 180) % 360 - 180
        return phi

    def elevation_angle_to_ue(
        self,
        site_x: float, site_y: float, site_z: float,
        ue_x: float, ue_y: float, ue_z: float = 1.5,
    ) -> float:
        """
        Why use this function: Computes the vertical elevation angle from the site down to a UE.

        Args:
            site_x (float): Site X coordinate.
            site_y (float): Site Y coordinate.
            site_z (float): Site Z coordinate (height).
            ue_x (float): UE X coordinate.
            ue_y (float): UE Y coordinate.
            ue_z (float): UE Z coordinate (height). Defaults to 1.5.

        Returns:
            float: Elevation angle in degrees (> 0 means looking downward).
        """
        d2d, _, _ = get_distance_2d(
            site_x, site_y, ue_x, ue_y, self.shift_vectors
        )
        dz = site_z - ue_z   # height difference (bs above UE → positive)
        if d2d < 1e-3:
            return 90.0   # directly below
        theta = math.degrees(math.atan2(dz, d2d))
        return theta   # positive = looking downward
