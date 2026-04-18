"""
Quick validation script: runs a short simulation with high lambda
to verify that CSR drops after the disaster and the algorithm
recovers better than no-drone.
"""
import sys
sys.path.insert(0, ".")

from run_simulation import run_one
from simulation.algorithm import CMType

PHASE1 = 30 * 60       # 30 min warm-up
PHASE3 = 2 * 3600      # 2 h recovery
TOTAL  = PHASE1 + PHASE3
LAM    = 11           # high load to create congestion

print("=" * 55)
print("  Validation: urban, rho=8, hotspot 200m NE, lam=0.5")
print("=" * 55)

for mode in ("no_drone", "static_drone", "algorithm"):
    result = run_one(
        env="urban",
        hotspot_cx=200.0, hotspot_cy=0.0,
        rho=8,
        mode=mode,
        sim_duration_s=TOTAL,
        phase2_start_s=PHASE1,
        seed=99,
        lambda_override=LAM,
        verbose=True,
    )
    print()
    print(f"[{mode}] Post-disaster CSR snapshots:")
    for t, c in result["csr_series"]:
        if t >= PHASE1:
            print(f"  t={t/60:5.1f}min  CSR={c:.4f}")
    print(f"  --> final_csr = {result['final_csr']:.4f}")
    if mode == "algorithm" and result["trajectory"]:
        last = result["trajectory"][-1]
        print(f"  --> final drone pos: ({last[1]:.1f}, {last[2]:.1f}), CM={last[3]:.4f}")
