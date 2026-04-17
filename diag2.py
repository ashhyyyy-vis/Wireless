"""
Debug: count how many UEs actually get flagged in_scope.
"""
import sys
sys.path.insert(0, ".")
import numpy as np
from simulation.network import Network
from simulation.propagation import ShadowFadingService
from simulation.traffic import TrafficGenerator, Hotspot, UE
from simulation.resource import RadioEngine, AdmissionController

rng = np.random.default_rng(42)
net = Network("urban")

# Pre-disaster scenario (all sites active)
csr_scope = set(net.csr_scope_cell_ids())
print(f"csr_scope has {len(csr_scope)} cell IDs: {sorted(csr_scope)}")
print(f"Total cells: {len(net.cells)}")
print(f"Failing site cells: {[c.cell_id for c in net.sites[0].cells]}")
print()

hotspot = Hotspot(cx=200, cy=0, rho=8, active=True)
traffic = TrafficGenerator("urban", hotspot=hotspot, rng=rng, lambda_override=0.5)
shadow  = ShadowFadingService(12, "urban", rng)
from simulation.drone import Drone
drone = Drone(cell_id=36, active=False)
radio = RadioEngine(net, drone, shadow, "urban")

# Simulate post-disaster: fail site 0
net.fail_site(0)

n_inscope = 0
n_total   = 100
for _ in range(n_total):
    ue = traffic.generate_ue(0.0)
    # Pre-incident: evaluate all 36 cells (ignoring failure state)
    full_rsrp = {cell.cell_id: radio.cell_rsrp(cell, ue) for cell in net.cells}
    best_pre = max(full_rsrp, key=lambda k: full_rsrp[k])
    if best_pre in csr_scope:
        n_inscope += 1

print(f"In-scope UEs: {n_inscope}/{n_total} ({100*n_inscope/n_total:.1f}%)")
print("(Expected ~33% since scope covers 1 site + 6 neighbours = 7/12 sites)")
