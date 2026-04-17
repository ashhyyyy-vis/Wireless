"""
Calibration script to find LAMBDA_ARRIVAL that yields ~98% CSR in a healthy network.
"""
import sys
sys.path.insert(0, ".")
import numpy as np
from run_simulation import run_one

ENV = "urban"
LAMBDAS = [2.0, 4.0, 6.0, 8.0, 10.0]

print(f"Calibrating lambda for {ENV} environment...")
print(f"{'Lambda':<10} {'CSR':<10}")

for l in LAMBDAS:
    # Run a short 20-minute simulation in healthy state
    res = run_one(
        env=ENV,
        mode="no_drone",
        sim_duration_s=1200,
        phase2_start_s=99999, # Never trigger disaster
        seed=42,
        lambda_override=l,
        verbose=False
    )
    # Since disaster never triggered, we use the tracker directly
    # But wait, run_one snaps every minute. Let's just look at final_csr
    print(f"{l:<10} {res['final_csr']:<10.4f}")
