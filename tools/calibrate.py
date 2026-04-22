"""
Calibration script to find LAMBDA_ARRIVAL that yields target CSR in a FAILED SITE scenario.
Tests no_drone mode with disaster to calibrate for realistic post-failure conditions.
"""
import sys
sys.path.insert(0, ".")
import numpy as np
from runners import run_one

ENV = "urban"
# Test range from 3 to 12 with 0.25 increments for post-disaster conditions
LAMBDAS=[round(1 + i*0.25, 2) for i in range(int((12-3)/0.25) + 1)]  # 3.0, 3.25, 3.5, ..., 12.0

TARGET_CSR = 0.85  # Target CSR for failed site scenario (lower than healthy 98%)

print(f"Calibrating lambda for {ENV} environment (FAILED SITE scenario)...")
print(f"Target CSR: {TARGET_CSR:.2f}")
print(f"{'Lambda':<10} {'CSR':<10} {'Status':<15}")

closest_lambda = None
closest_diff = float('inf')

for l in LAMBDAS:
    # Run simulation with disaster (failed site)
    res = run_one(
        env=ENV,
        mode="no_drone",
        sim_duration_s=1800,  # 30 minutes: 5min warmup + 25min post-disaster
        phase2_start_s=300,    # Disaster at 5 minutes
        seed=42,
        lambda_override=l,
        verbose=False
    )
    
    csr = res['final_csr']
    diff = abs(csr - TARGET_CSR)
    
    if diff < closest_diff:
        closest_diff = diff
        closest_lambda = l
    
    status = "CLOSEST" if l == closest_lambda else ""
    print(f"{l:<10} {csr:<10.4f} {status:<15}")

print(f"\n=== Calibration Results ===")
print(f"Recommended lambda: {closest_lambda}")
print(f"CSR at recommended lambda: {res['final_csr']:.4f}")
print(f"Difference from target: {closest_diff:.4f}")
