"""
Calibrating lambda for rural environment.
"""
import sys
import time
sys.path.insert(0, ".")
import numpy as np
from run_simulation import run_one

ENV = "rural"
LAMBDAS=[round(0.1 + i*0.05, 2) for i in range(int((5.0-0.1)/0.05) + 1)]  # 0.1, 0.15, 0.2, ..., 5.0

print(f"Calibrating lambda for {ENV} environment...")
print(f"{'Lambda':<10} {'CSR':<10}")
timers=[]
for l in LAMBDAS:
    start = time.time()
    res = run_one(
        env=ENV,
        mode="no_drone",
        sim_duration_s=1200,
        phase2_start_s=99999,
        seed=42,
        lambda_override=l,
        verbose=False
    )
    timers.append(time.time() - start)
    print(f"{l:<10} {res['final_csr']:<10.4f}")
print(f"Average time per simulation: {np.mean(timers):.2f} s")