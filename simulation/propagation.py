"""
Path loss and shadow fading models.

Paper reference: Section V-B, Equations (4) and (5)
  - UE ↔ Regular BS:  3GPP TR 38.901 Tables 7.4.1 / 7.4.2
  - UE ↔ Drone BS:    Al-Hourani et al. air-to-ground model
  - Shadow fading:     Fraile et al. spatially correlated map
"""
import math
import numpy as np
from typing import Dict, Optional, Tuple

from .config import (
    ENVIRONMENT, CARRIER_FREQ_HZ, C_LIGHT,
    ETA_LOS_DB, ETA_NLOS_DB,
    DRONE_ENV_PARAMS,
    MIN_COUPLING_LOSS_DB,
    SHADOW_FADING_SIGMA_DB, SHADOW_DECORR_DIST_M, SHADOW_SITE_TO_SITE_CORR,
    ISD,
)


# ---------------------------------------------------------------------------
# Helper: free-space path loss (dB)
# ---------------------------------------------------------------------------

def free_space_pl(dist_3d_m: float, freq_hz: float = CARRIER_FREQ_HZ) -> float:
    """
    Why use this function: Computes Free Space Path Loss (FSPL) in dB, preventing 
    log(0) by bounding distance to 1.0m min.

    Args:
        dist_3d_m (float): 3D distance between Tx and Rx in meters.
        freq_hz (float): Carrier frequency in Hertz. Defaults to CARRIER_FREQ_HZ.

    Returns:
        float: Free space path loss in dB.
    """
    if dist_3d_m < 1.0:
        dist_3d_m = 1.0
    return 20.0 * math.log10(4.0 * math.pi * dist_3d_m * freq_hz / C_LIGHT)


# ---------------------------------------------------------------------------
# LoS probability helpers derived from Al-Hourani / ITU-R P.1410
# ξ and ψ are computed from environmental parameters α, β, γ
# ---------------------------------------------------------------------------

def _compute_xi_psi(env: str) -> Tuple[float, float]:
    """
    Why use this function: Computes parameters ξ and ψ representing the environmental 
    characteristics as required by the Al-Hourani Air-to-Ground LoS probability model.

    Args:
        env (str): The environment type ("urban" or "rural").

    Returns:
        Tuple[float, float]: A tuple containing (ξ, ψ).
    """
    p = DRONE_ENV_PARAMS[env]
    alpha = p["alpha"]
    beta  = p["beta"]
    gamma = p["gamma"]

    # From Al-Hourani (2014), simplified analytical expressions:
    #   ξ = a₁ * exp(-a₂ * alpha) ... (curve-fitted)
    # We use representative published values for urban / rural directly.
    # Urban (dense): ξ ≈ 9.61,  ψ ≈ 0.16  (Al-Hourani 2014 Table I, suburban)
    # For simplicity we use the closed-form from the paper's reference [20]:
    #   p_LOS = 1 / (1 + A*exp(-B*(theta - A)))
    # where A = a, B = b are environment-specific fitted constants.
    # Urban: a=9.61, b=0.16;  Rural: a=0.01, b=0.0
    # But the paper uses the three-parameter model above.  We use
    # published curve-fitted values (Al-Hourani 2014):
    if env == "urban":
        xi  = 9.61
        psi = 0.16
    else:   # rural / suburban
        xi  = 0.01
        psi = 0.0   # p_LoS ≈ 1 for most rural angles

    return xi, psi


_XI_PSI: Dict[str, Tuple[float, float]] = {
    env: _compute_xi_psi(env) for env in ("urban", "rural")
}


def p_los(h_diff_m: float, r_horiz_m: float, env: str = ENVIRONMENT) -> float:
    """
    Why use this function: Calculates the Line-of-Sight (LoS) probability between a drone 
    and a UE based on the Al-Hourani elevation-dependent model (Equation 5).

    Args:
        h_diff_m (float): Height difference between drone and UE in meters (> 0).
        r_horiz_m (float): Horizontal 2D distance in meters.
        env (str): The environment type ("urban" or "rural"). Defaults to ENVIRONMENT.

    Returns:
        float: Probability of LoS in the range [0, 1].
    """
    xi, psi = _XI_PSI[env]
    if r_horiz_m < 1e-3:
        return 1.0   # directly below → always LoS
    theta_rad = math.atan2(h_diff_m, r_horiz_m)   # elevation in radians
    if psi == 0.0:
        return 1 / (1 + xi * math.exp(-xi))       # constant (rural)
    exponent = -psi * (math.degrees(theta_rad) - xi)
    return 1.0 / (1.0 + xi * math.exp(exponent))


# ---------------------------------------------------------------------------
# Drone ↔ UE path loss  (Equation 4)
# ---------------------------------------------------------------------------

def drone_path_loss(
    drone_x: float, drone_y: float, drone_z: float,
    ue_x: float, ue_y: float, ue_z: float = 1.5,
    d2d: float | None = None,
    env: str = ENVIRONMENT,
    rng: np.random.Generator | None = None,
) -> float:
    """
    Why use this function: Computes the Air-to-Ground path loss from the drone to a UE.
    If rng is provided, it samples the LoS/NLoS state stochastically (Paper §V-B).
    Otherwise, it uses the expected value (weighted average).
    """
    if d2d is None:
        dx = ue_x - drone_x
        dy = ue_y - drone_y
        d2d = math.sqrt(dx * dx + dy * dy)

    dz = abs(drone_z - ue_z)
    d3d = math.sqrt(d2d * d2d + dz * dz)
    if d3d < 1.0:
        d3d = 1.0

    fspl = free_space_pl(d3d)
    p = p_los(dz, d2d, env)
    eta_los  = ETA_LOS_DB[env]
    eta_nlos = ETA_NLOS_DB[env]

    if rng is not None:
        # Stochastic sampling (Paper implementation)
        is_los = rng.random() < p
        pl = fspl + (eta_los if is_los else eta_nlos)
    else:
        # Deterministic weighted average
        pl = fspl + p * eta_los + (1.0 - p) * eta_nlos

    # Apply minimum coupling loss
    return max(pl, MIN_COUPLING_LOSS_DB[env])


# ---------------------------------------------------------------------------
# Regular BS ↔ UE path loss  (3GPP TR 38.901 Tables 7.4.1/7.4.2, simplified)
# ---------------------------------------------------------------------------

def _p_los_urban_macro(d2d_m: float, h_bs: float = 25.0, h_ut: float = 1.5) -> float:
    """
    Why use this function: Computes the Line-of-Sight probability for 3GPP Urban Macro (UMa).
    """
    if d2d_m <= 18.0:
        return 1.0
    # Simplified 3GPP UMa formula
    term1 = (18.0 / d2d_m)
    term2 = math.exp(-d2d_m / 63.0) * (1.0 - 18.0 / d2d_m)
    return term1 + term2


def _p_los_rural_macro(d2d_m: float) -> float:
    """
    Why use this function: Computes the Line-of-Sight probability for 3GPP Rural Macro (RMa).
    """
    if d2d_m <= 10.0:
        return 1.0
    return math.exp(-(d2d_m - 10.0) / 1000.0)


def bs_path_loss(
    d2d_m: float,
    d3d_m: float,
    h_bs: float,
    h_ut: float = 1.5,
    env: str = ENVIRONMENT,
    rng: np.random.Generator | None = None,
) -> float:
    """
    Why use this function: Calculates the path loss between a regular Base Station and a UE.
    If rng is provided, it samples the LoS/NLoS state stochastically.
    """
    f_ghz = CARRIER_FREQ_HZ / 1e9

    if env == "urban":
        # UMa LoS  (3GPP TR 38.901 Table 7.4.1-1, formula 1)
        if d3d_m < 1.0:
            d3d_m = 1.0
        pl_los = (28.0
                  + 22.0 * math.log10(d3d_m)
                  + 20.0 * math.log10(f_ghz))

        # UMa NLoS (Table 7.4.1-1, formula 2)
        pl_nlos_candidate = (13.54
                             + 39.08 * math.log10(d3d_m)
                             + 20.0 * math.log10(f_ghz)
                             - 0.6 * (h_ut - 1.5))
        pl_nlos = max(pl_los, pl_nlos_candidate)

        p = _p_los_urban_macro(d2d_m, h_bs, h_ut)

    else:  # rural
        if d3d_m < 1.0:
            d3d_m = 1.0
        # RMa LoS  (3GPP TR 38.901 Table 7.4.1-1)
        h = 5.0   # average building height (rural)
        W = 20.0  # street width (m)
        d_bp = 2.0 * math.pi * h_bs * h_ut * f_ghz * 1e9 / C_LIGHT

        if d2d_m < d_bp:
            pl_los = (20.0 * math.log10(40.0 * math.pi * d3d_m * f_ghz / 3.0)
                      + min(0.03 * h**1.72, 10.0) * math.log10(d3d_m)
                      - min(0.044 * h**1.72, 14.77)
                      + 0.002 * math.log10(h) * d3d_m)
        else:
            pl_los = (20.0 * math.log10(40.0 * math.pi * d_bp * f_ghz / 3.0)
                      + min(0.03 * h**1.72, 10.0) * math.log10(d_bp)
                      - min(0.044 * h**1.72, 14.77)
                      + 0.002 * math.log10(h) * d_bp
                      + 40.0 * math.log10(d3d_m / d_bp))

        # RMa NLoS
        pl_nlos_candidate = (161.04
                             - 7.1 * math.log10(W)
                             + 7.5 * math.log10(h)
                             - (24.37 - 3.7 * (h / h_bs)**2) * math.log10(h_bs)
                             + (43.42 - 3.1 * math.log10(h_bs)) * (math.log10(d3d_m) - 3.0)
                             + 20.0 * math.log10(f_ghz)
                             - (3.2 * (math.log10(11.75 * h_ut))**2 - 4.97))
        pl_nlos = max(pl_los, pl_nlos_candidate)

        p = _p_los_rural_macro(d2d_m)

    if rng is not None:
        # Stochastic sampling
        is_los = rng.random() < p
        pl = pl_los if is_los else pl_nlos
    else:
        # Deterministic weighted average
        pl = p * pl_los + (1.0 - p) * pl_nlos

    # Apply minimum coupling loss
    return max(pl, MIN_COUPLING_LOSS_DB[env])


# ---------------------------------------------------------------------------
# Shadow fading map (Fraile et al. spatially correlated)
# ---------------------------------------------------------------------------

class ShadowFadingMap:
    """
    Pre-generated spatially correlated log-normal shadow fading map.
    Uses a 2-D Gaussian filter to impose spatial correlation.
    One map per (site, env); all maps share site-to-site correlation ω.
    """

    def __init__(
        self,
        env: str = ENVIRONMENT,
        grid_size_m: float | None = None,
        resolution_m: float = 5.0,
        rng: np.random.Generator | None = None,
    ) -> None:
        """
        Why use this function: Initializes a spatially correlated shadow fading 
        map for a specific geographical area and applies Gaussian filtering.

        Args:
            env (str): The environment type.
            grid_size_m (float | None): Total size of the map in meters.
            resolution_m (float): Distance between grid points. Defaults to 5.0.
            rng (np.random.Generator | None): Random number generator.

        Returns:
            None
        """
        self.env = env
        self.sigma = SHADOW_FADING_SIGMA_DB[env]
        self.d_decorr = SHADOW_DECORR_DIST_M[env]
        self.omega = SHADOW_SITE_TO_SITE_CORR
        self.resolution = resolution_m
        self.rng = rng if rng is not None else np.random.default_rng()

        # Grid extent: 2× cluster radius
        isd = ISD[env]
        if grid_size_m is None:
            grid_size_m = 4.0 * isd
        self.grid_size = grid_size_m

        # Pre-generate a correlated map using 2-D low-pass filtering
        self._map: Optional[np.ndarray] = None
        self._origin = (-grid_size_m / 2.0, -grid_size_m / 2.0)
        self._nx = int(grid_size_m / resolution_m) + 1
        self._ny = int(grid_size_m / resolution_m) + 1
        self._generate()

    def _generate(self) -> None:
        """
        Why use this function: Generates the 2D array of spatially correlated shadow 
        fading using Gaussian low-pass filtering.

        Args:
            None

        Returns:
            None
        """
        from scipy.ndimage import gaussian_filter
        white = self.rng.standard_normal((self._nx, self._ny))
        # σ for Gaussian filter in grid cells: d_decorr / resolution
        sigma_cells = self.d_decorr / self.resolution
        correlated = gaussian_filter(white, sigma=sigma_cells)
        # Normalize so final std ≈ self.sigma
        correlated = correlated / correlated.std() * self.sigma
        self._map = correlated

    def get(self, x: float, y: float) -> float:
        """
        Why use this function: Interpolates the pre-generated shadow fading map to find the fading 
        value (in dB) at a specific (x, y) location.

        Args:
            x (float): X coordinate in meters.
            y (float): Y coordinate in meters.

        Returns:
            float: Interpolated shadow fading value in dB, or 0.0 if outside map.
        """
        if self._map is None:
            return 0.0
        ix = (x - self._origin[0]) / self.resolution
        iy = (y - self._origin[1]) / self.resolution
        ix = int(round(ix))
        iy = int(round(iy))
        if 0 <= ix < self._nx and 0 <= iy < self._ny:
            return float(self._map[ix, iy])
        return 0.0


class ShadowFadingService:
    """
    Manages one shadow fading map per site with inter-site correlation.
    """

    def __init__(
        self,
        num_sites: int,
        env: str = ENVIRONMENT,
        rng: np.random.Generator | None = None,
    ) -> None:
        """
        Why use this function: Initializes the shadow fading service by 
        pre-generating spatially correlated fading maps with inter-site 
        correlation ω.
        
        Shadow fading is modeled as S_i = sqrt(ω) * Z_common + sqrt(1-ω) * Z_site_i
        where both Z terms are spatially correlated log-normal maps.

        Args:
            num_sites (int): Total number of sites requiring a fading map.
            env (str): The simulation environment.
            rng (np.random.Generator | None): Random number generator.

        Returns:
            None
        """
        self.rng = rng if rng is not None else np.random.default_rng()
        self.omega = SHADOW_SITE_TO_SITE_CORR
        
        # Common map (shared by all sites)
        self._common_map = ShadowFadingMap(env=env, rng=self.rng)
        
        # Independent maps for each site
        self._site_maps = [
            ShadowFadingMap(env=env, rng=self.rng) for _ in range(num_sites)
        ]
        
        self.sqrt_omega = math.sqrt(self.omega)
        self.sqrt_one_minus_omega = math.sqrt(1.0 - self.omega)

    def get(self, site_id: int, ue_x: float, ue_y: float) -> float:
        """
        Why use this function: Retrieves the shadow fading value (dB) for a specific site-to-UE link,
        combining common and site-specific components for inter-site correlation.

        Args:
            site_id (int): The ID of the serving site.
            ue_x (float): UE X coordinate in meters.
            ue_y (float): UE Y coordinate in meters.

        Returns:
            float: Simulated shadow fading value in dB.
        """
        common_val = self._common_map.get(ue_x, ue_y)
        site_val   = self._site_maps[site_id].get(ue_x, ue_y)
        
        return self.sqrt_omega * common_val + self.sqrt_one_minus_omega * site_val
