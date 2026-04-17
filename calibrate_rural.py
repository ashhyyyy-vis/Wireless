"""
Calibrating lambda for rural environment.
"""
import sys
sys.path.insert(0, ".")
import numpy as np
from run_simulation import run_one

ENV = "rural"
LAMBDAS = [0.1, 0.5, 1.0, 1.5, 2.0]

print(f"Calibrating lambda for {ENV} environment...")
print(f"{'Lambda':<10} {'CSR':<10}")

for l in LAMBDAS:
    res = run_one(
        env=ENV,
        mode="no_drone",
        sim_duration_s=1200,
        phase2_start_s=99999,
        seed=42,
        lambda_override=l,
        verbose=False
    )
    print(f"{l:<10} {res['final_csr']:<10.4f}")
