"""
Calibrating lambda for rural environment.
"""
import sys
import time
sys.path.insert(0, ".")
import numpy as np
from run_simulation import run_one

ENV = "rural"
LAMBDAS = [i for i in np.linspace(0.5, 3, 10)]  # range of λ to test

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