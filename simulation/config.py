"""
Simulation parameters from Table II of:
"Online Positioning of a Drone-Mounted Base Station in Emergency Scenarios"
Pijnappel et al., IEEE TVT 2024.
"""
import math

# ---------------------------------------------------------------------------
# Network topology
# ---------------------------------------------------------------------------
NUM_SITES = 12          # 12 three-sectorized sites
NUM_SECTORS = 3
NUM_CELLS = NUM_SITES * NUM_SECTORS   # 36 regular cells
SECTOR_BORESIGHTS_DEG = [30.0, 150.0, 270.0]   # azimuth boresights per sector

FAILING_SITE_ID = 0     # Site 0 is the site that fails in Phase II

# ---------------------------------------------------------------------------
# Environment selection  ("urban" | "rural")
# ---------------------------------------------------------------------------
ENVIRONMENT = "urban"

# ---------------------------------------------------------------------------
# ISD & geometry
# ---------------------------------------------------------------------------
ISD = {
    "urban": 500.0,    # metres
    "rural": 3500.0,
}

BS_HEIGHT = {
    "urban": 25.0,     # metres
    "rural": 35.0,
}

# ---------------------------------------------------------------------------
# Carrier / bandwidth
# ---------------------------------------------------------------------------
CARRIER_FREQ_HZ = 3.5e9        # 3.5 GHz
BANDWIDTH_HZ = 5e6             # 5 MHz per cell
CTRL_OVERHEAD_KAPPA = 0.1      # fraction of BW for control signals

# ---------------------------------------------------------------------------
# Transmit powers
# ---------------------------------------------------------------------------
P_TX_BS_W = 20.0               # 20 W  (43 dBm)
P_TX_BS_DBM = 10 * math.log10(P_TX_BS_W * 1e3)   # ≈ 43 dBm

P_TX_DRONE_W = 20             # 20 W (33 dBm)
P_TX_DRONE_DBM = 10 * math.log10(P_TX_DRONE_W * 1e3)   # ≈ 33 dBm

# ---------------------------------------------------------------------------
# Drone fixed parameters (Section VI-D finding)
# ---------------------------------------------------------------------------
DRONE_ALTITUDE_M = 120.0       # fixed at 120 m
DRONE_CIO_DB = 0.0             # fixed at 0 dB

# ---------------------------------------------------------------------------
# BS Antenna model (Gunnarsson et al. / 3GPP)
# ---------------------------------------------------------------------------
ANTENNA_HPBW_H_DEG = 65.0     # horizontal half-power beam width
ANTENNA_HPBW_V_DEG = 7.5      # vertical   half-power beam width
ANTENNA_MAX_GAIN_DBI = 18.0    # G_r (max gain, dBi)
ANTENNA_FBR_DB = 25.0          # front-back ratio
ANTENNA_SLL_DB = -20.0         # side-lobe level (negative means attenuation)
ANTENNA_ETILT_DEG = 10.0       # electrical downtilt

# ---------------------------------------------------------------------------
# Drone antenna model (3GPP TR 38.901 Table 7.3-1, rotated / simplified)
# ---------------------------------------------------------------------------
DRONE_ANT_HPBW_DEG = 65.0
DRONE_ANT_A_MAX_DB = 30.0     # max attenuation
DRONE_ANT_GAIN_DBI = 5.0      # G_d

# ---------------------------------------------------------------------------
# Propagation — drone channel (Al-Hourani et al., Eq 4-5 in paper)
# ---------------------------------------------------------------------------
# Urban environment constants (from [20] / ITU-R P.1410)
_URBAN_ALPHA  = 0.3            # ratio built-up to total land area
_URBAN_BETA   = 500.0          # buildings/km²
_URBAN_GAMMA  = 15.0           # Rayleigh scale for building heights

# Rural environment constants
_RURAL_ALPHA  = 0.1
_RURAL_BETA   = 100.0
_RURAL_GAMMA  = 8.0

# Derived ξ, ψ from Al-Hourani (computed at runtime in propagation.py)
ETA_LOS_DB = {
    "urban": 1.0,      # excessive path loss for LoS (dB)
    "rural": 0.1,
}
ETA_NLOS_DB = {
    "urban": 20.0,     # excessive path loss for NLoS (dB)
    "rural": 21.0,
}

DRONE_ENV_PARAMS = {
    "urban": {"alpha": _URBAN_ALPHA, "beta": _URBAN_BETA, "gamma": _URBAN_GAMMA},
    "rural": {"alpha": _RURAL_ALPHA, "beta": _RURAL_BETA, "gamma": _RURAL_GAMMA},
}

# ---------------------------------------------------------------------------
# Shadow fading (Fraile et al. model)
# ---------------------------------------------------------------------------
SHADOW_FADING_SIGMA_DB = {
    "urban": 8.0,
    "rural": 8.0,
}
SHADOW_DECORR_DIST_M = {
    "urban": 50.0,
    "rural": 120.0,
}
SHADOW_SITE_TO_SITE_CORR = 0.5   # ω

# ---------------------------------------------------------------------------
# Minimum coupling loss
# ---------------------------------------------------------------------------
MIN_COUPLING_LOSS_DB = {
    "urban": 70.0,
    "rural": 80.0,
}

# ---------------------------------------------------------------------------
# Link budget thresholds
# ---------------------------------------------------------------------------
COVERAGE_THRESHOLD_DBM = -120.0   # min RSRP for coverage
THERMAL_NOISE_DBM = -106.94       # thermal noise power (dBm)
NOISE_FIGURE_DB = 8.0             # UE noise figure

# ---------------------------------------------------------------------------
# Traffic
# ---------------------------------------------------------------------------
MIN_BITRATE_MBPS = 0.384          # minimum required bit rate per call (R)
CALL_DURATION_MEAN_S = 120.0      # mean call duration (τ), exponential

# Arrival rate λ (calls/s over the whole cluster area) — tuned per env.
# Set so that healthy CSR ≈ 98 %.  Adjust during calibration.
LAMBDA_ARRIVAL = {
    "urban": 5,   # starting guess; calibrate in Phase I
    "rural": 1.3,
}

# Hotspot
HOTSPOT_RADIUS_M = 100.0          # fixed at 100 m
HOTSPOT_RHO = {                    # traffic intensity multiplier options
    "urban": [2, 4, 8],
    "rural": [10, 25, 50],
}

# ---------------------------------------------------------------------------
# Resource management
# ---------------------------------------------------------------------------
HANDOVER_HYSTERESIS_DB = 3.0      # A3-event offset
HANDOVER_TTT_S = 0.200            # time-to-trigger (s)

# ---------------------------------------------------------------------------
# Algorithm / drone movement
# ---------------------------------------------------------------------------
MEASUREMENT_PERIOD_S = 0.200      # CM measurement window
DRONE_STEP_M = 1.0                # step size per decision (metres)
DRONE_SPEED_MPS = 24.0 / 3.6     # 24 km/h → m/s  ≈ 6.67 m/s

# Control interval = measurement + TTT (both 200 ms each)
CONTROL_INTERVAL_S = MEASUREMENT_PERIOD_S + HANDOVER_TTT_S

# ---------------------------------------------------------------------------
# Simulation timing
# ---------------------------------------------------------------------------
PHASE1_DURATION_S = 3600.0        # 1 hour warm-up
PHASE2_START_S    = PHASE1_DURATION_S
PHASE3_START_S    = PHASE1_DURATION_S   # drone activates immediately after disaster

RESULTS_WINDOW_S  = 300.0         # 5-minute rolling CSR window
SIM_RUNS          = 25            # runs for averaging (paper uses 25)

# ---------------------------------------------------------------------------
# Speed of light
# ---------------------------------------------------------------------------
C_LIGHT = 3e8   # m/s
