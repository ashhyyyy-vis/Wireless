"""
Diagnostic: check what is happening with admission and SINR.
"""
import sys, math
sys.path.insert(0, ".")

from simulation.network import Network
from simulation.propagation import ShadowFadingService
from simulation.traffic import TrafficGenerator, Hotspot, UE
from simulation.resource import RadioEngine, AdmissionController, NOISE_FLOOR_DBM
from simulation.drone import Drone
from simulation.config import BANDWIDTH_HZ, CTRL_OVERHEAD_KAPPA, MIN_BITRATE_MBPS
import numpy as np

rng = np.random.default_rng(42)
net = Network("urban")
hotspot = Hotspot(cx=200, cy=0, rho=8, active=True)
shadow  = ShadowFadingService(12, "urban", rng)
drone   = Drone(cell_id=36, active=False)
radio   = RadioEngine(net, drone, shadow, "urban")
adm     = AdmissionController(net, drone)

# Fail site 0
net.fail_site(0)

# Generate 50 UEs near the failing site and report stats
traffic = TrafficGenerator("urban", hotspot=hotspot, rng=rng, lambda_override=0.5)
ue_counter = 0

print(f"Noise floor: {NOISE_FLOOR_DBM:.2f} dBm")
print(f"BW = {BANDWIDTH_HZ/1e6:.0f} MHz, kappa={CTRL_OVERHEAD_KAPPA}, R={MIN_BITRATE_MBPS} Mbps")
print()

n_covered = 0
n_blocked = 0
n_admitted = 0
req_fracs = []

for _ in range(200):
    ue = traffic.generate_ue(0.0)
    rsrp_tbl = radio.rsrp_table(ue)
    cid = radio.select_cell(rsrp_tbl)
    if cid is None:
        n_blocked += 1
        continue
    n_covered += 1
    rsrp = rsrp_tbl[cid]
    sinr = radio.sinr_db(cid, ue, rsrp_tbl)
    req_frac = radio.required_resource_fraction(sinr)
    req_fracs.append(req_frac)

    admitted = adm.try_admit(ue, cid, req_frac)
    if admitted:
        n_admitted += 1

print(f"Out of 200 UEs near failed site:")
print(f"  Covered:   {n_covered}")
print(f"  No coverage: {n_blocked}")
print(f"  Admitted:  {n_admitted}")
print(f"  Blocked by capacity: {n_covered - n_admitted}")
if req_fracs:
    print(f"  avg req_frac: {sum(req_fracs)/len(req_fracs):.4f}")
    print(f"  min req_frac: {min(req_fracs):.4f}")
    print(f"  max req_frac: {max(req_fracs):.4f}")

# Check total load on the busiest cell
print()
print("Cell loads (top 5):")
loads = [(adm.cell_load(c.cell_id), c.cell_id) for c in net.cells if c.active]
loads.sort(reverse=True)
for load, cid in loads[:5]:
    print(f"  cell {cid}: load={load:.3f}, UEs={adm.num_ues(cid)}")
