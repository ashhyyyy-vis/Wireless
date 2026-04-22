"""
Drone base station object: position, channel computation.

Paper reference: Section V-A (drone model), Section IV (CIO)
"""
import math
import numpy as np
from dataclasses import dataclass, field

from .config import (
    DRONE_ALTITUDE_M, DRONE_CIO_DB,
    P_TX_DRONE_DBM, ENVIRONMENT,
)
from .antenna import drone_antenna_gain, drone_off_axis_angle
from .propagation import drone_path_loss


@dataclass
class Drone:
    """
    Drone base station.

    Position (x, y) is optimized by the algorithm.
    Altitude z and CIO are fixed per Section VI-D findings.
    """
    x: float = 0.0
    y: float = 0.0
    z: float = DRONE_ALTITUDE_M
    cio: float = DRONE_CIO_DB
    active: bool = False

    # Cell ID assigned to the drone (set externally, = NUM_CELLS)
    cell_id: int = -1

    def activate(self, x: float = 0.0, y: float = 0.0) -> None:
        """
        Why use this function: Places the drone at specific (x, y) coordinates and marks it active.

        Args:
            x (float): Initial X coordinate.
            y (float): Initial Y coordinate.

        Returns:
            None
        """
        self.x = x
        self.y = y
        self.z = DRONE_ALTITUDE_M
        self.active = True

    def move_to(self, x: float, y: float) -> None:
        """
        Why use this function: Updates the drone's position to new coordinates.

        Args:
            x (float): Target X coordinate.
            y (float): Target Y coordinate.

        Returns:
            None
        """
        self.x = x
        self.y = y

    def rsrp(
        self,
        ue_x: float,
        ue_y: float,
        ue_z: float = 1.5,
        d2d: float | None = None,
        env: str = ENVIRONMENT,
        rng: np.random.Generator | None = None,
    ) -> float:
        """
        Why use this function: Calculates the Reference Signal Received Power (RSRP) 
        from the drone to a specific UE position.
        """
        if not self.active:
            return -math.inf

        if d2d is None:
            dx = ue_x - self.x
            dy = ue_y - self.y
            d2d = math.sqrt(dx * dx + dy * dy)

        # Off-axis angle for drone antenna
        phi = drone_off_axis_angle(
            self.x, self.y, self.z,
            ue_x, ue_y, ue_z,
            d2d=d2d,
        )
        gain = drone_antenna_gain(phi)

        # Path loss (dB)
        pl = drone_path_loss(
            self.x, self.y, self.z,
            ue_x, ue_y, ue_z,
            d2d=d2d,
            env=env,
            rng=rng,
        )

        return P_TX_DRONE_DBM + gain - pl

    def rsrp_plus_cio(
        self,
        ue_x: float,
        ue_y: float,
        ue_z: float = 1.5,
        d2d: float | None = None,
        env: str = ENVIRONMENT,
    ) -> float:
        """
        Why use this function: Calculates RSRP including the Cell Individual Offset (CIO).

        Args:
            ue_x (float): UE X position.
            ue_y (float): UE Y position.
            ue_z (float): UE Z position. Defaults to 1.5.
            d2d (float | None): Optional pre-calculated 2D distance.
            env (str): Environment type.

        Returns:
            float: RSRP + CIO in dBm.
        """
        return self.rsrp(ue_x, ue_y, ue_z, d2d, env) + self.cio
