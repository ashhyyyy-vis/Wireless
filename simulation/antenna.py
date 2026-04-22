"""
Antenna gain models for regular BS and drone BS.

Paper reference: Section V-A, Equations (1), (2), (3)
"""
import math
from .config import (
    ANTENNA_HPBW_H_DEG, ANTENNA_HPBW_V_DEG,
    ANTENNA_MAX_GAIN_DBI, ANTENNA_FBR_DB, ANTENNA_SLL_DB,
    ANTENNA_ETILT_DEG,
    DRONE_ANT_HPBW_DEG, DRONE_ANT_A_MAX_DB, DRONE_ANT_GAIN_DBI,
)


# ---------------------------------------------------------------------------
# Regular BS antenna  (Gunnarsson et al., 3GPP TR 36.942)
# ---------------------------------------------------------------------------

def bs_horizontal_gain(phi_deg: float) -> float:
    """
    Why use this function: Calculates the horizontal component of the base station 
    antenna gain according to Equation (1).

    Args:
        phi_deg (float): Horizontal angle relative to boresight (degrees), [-180, 180].

    Returns:
        float: Horizontal gain component in dBi.
    """
    ratio = phi_deg / ANTENNA_HPBW_H_DEG
    att = min(12.0 * ratio * ratio, ANTENNA_FBR_DB)
    return -att + ANTENNA_MAX_GAIN_DBI


def bs_vertical_gain(theta_deg: float) -> float:
    """
    Why use this function: Calculates the vertical component of the base station 
    antenna gain according to Equation (2).

    Args:
        theta_deg (float): Negative elevation angle relative to horizontal (degrees).
                           Positive = antenna looking downward.

    Returns:
        float: Vertical gain contribution in dB (<= 0 always, SLL is the floor).
    """
    ratio = (theta_deg - ANTENNA_ETILT_DEG) / ANTENNA_HPBW_V_DEG
    att = -12.0 * ratio * ratio
    return max(att, ANTENNA_SLL_DB)


def bs_antenna_gain(phi_deg: float, theta_deg: float) -> float:
    """
    Why use this function: Computes the total 3D base station antenna gain by 
    adding the horizontal and vertical components.

    Args:
        phi_deg (float): Horizontal deviation from boresight (degrees).
        theta_deg (float): Elevation angle, positive = looking downward (degrees).

    Returns:
        float: Total base station antenna gain in dBi.
    """
    return bs_horizontal_gain(phi_deg) + bs_vertical_gain(theta_deg)


# ---------------------------------------------------------------------------
# Drone antenna  (3GPP TR 38.901 Table 7.3-1, rotated for circular footprint)
# ---------------------------------------------------------------------------

def drone_antenna_gain(phi_deg: float) -> float:
    """
    Why use this function: Computes the single-element drone antenna gain adapted 
    so its footprint is circular according to Equation (3).

    Args:
        phi_deg (float): Angle from the drone's main beam direction (degrees). 
                         0° = directly below the drone.

    Returns:
        float: Drone antenna gain in dBi.
    """
    ratio = phi_deg / DRONE_ANT_HPBW_DEG
    att = min(12.0 * ratio * ratio, DRONE_ANT_A_MAX_DB)
    return -att + DRONE_ANT_GAIN_DBI


def drone_off_axis_angle(
    drone_x: float, drone_y: float, drone_z: float,
    ue_x: float, ue_y: float, ue_z: float = 1.5,
    d2d: float | None = None,
) -> float:
    """
    Why use this function: Computes the off-axis angle φ between the drone's downward 
    beam and the direction to the User Equipment (UE).

    Args:
        drone_x (float): Drone X position (meters).
        drone_y (float): Drone Y position (meters).
        drone_z (float): Drone Z position (meters).
        ue_x (float): UE X position (meters).
        ue_y (float): UE Y position (meters).
        ue_z (float): UE Z position (meters). Defaults to 1.5.
        d2d (float | None): Optional pre-computed 2D distance.

    Returns:
        float: Off-axis angle in [0, 90] degrees.
    """
    if d2d is None:
        dx = ue_x - drone_x
        dy = ue_y - drone_y
        d2d = math.sqrt(dx * dx + dy * dy)

    dz = drone_z - ue_z   # height difference (positive: drone above UE)
    if dz <= 0:
        # UE above drone – unusual; treat as 90 degrees off-axis
        return 90.0

    # Elevation angle from drone toward UE (measured from vertical/down axis)
    phi = math.degrees(math.atan2(d2d, dz))
    return phi
