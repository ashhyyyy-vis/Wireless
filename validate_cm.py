import sys
import csv
import numpy as np
from multiprocessing import Pool, cpu_count

sys.path.insert(0, ".")

from run_simulation import run_one
from simulation.algorithm import CMType


# -----------------------------
# Config
# -----------------------------
PHASE1 = 30 * 60
PHASE3 = 2 * 3600
TOTAL  = PHASE1 + PHASE3

ENV = "urban"
HOTSPOT_X = 200.0
HOTSPOT_Y = 0.0
RHO = 8
LAMBDA = 11

N_RUNS = 5   # now parallel makes this worth it


# -----------------------------
# Worker wrapper (required)
# -----------------------------
def run_job(args):
    mode, cm, seed = args

    result = run_one(
        env=ENV,
        hotspot_cx=HOTSPOT_X,
        hotspot_cy=HOTSPOT_Y,
        rho=RHO,
        mode=mode,
        cm_type=cm,
        sim_duration_s=TOTAL,
        phase2_start_s=PHASE1,
        seed=seed,
        lambda_override=LAMBDA,
        verbose=False,
    )

    return result["final_csr"]


# -----------------------------
# Run validation
# -----------------------------
results = []

print("=" * 60)
print(" Parallel validation (ALL CM + baselines) ")
print("=" * 60)

NUM_WORKERS = 10


# -----------------------------
# Helper to run batch
# -----------------------------
def run_batch(mode, cm=None):
    print(f"\n>> Testing {mode if cm is None else cm.name}")

    jobs = [
        (mode, cm, 100 + i)
        for i in range(N_RUNS)
    ]

    with Pool(NUM_WORKERS) as p:
        csr_values = p.map(run_job, jobs)

    mean_csr = float(np.mean(csr_values))
    std_csr  = float(np.std(csr_values))

    print(f"   --> mean CSR = {mean_csr:.4f} ± {std_csr:.4f}")

    results.append({
        "cm": mode if cm is None else cm.name,
        "mean_csr": mean_csr,
        "std_csr": std_csr,
    })

if __name__ == "__main__":
    # -----------------------------
    # 1. Baselines
    # -----------------------------
    run_batch("no_drone")
    run_batch("static_drone")


    # -----------------------------
    # 2. All CM metrics
    # -----------------------------
    for cm in CMType:
        run_batch("algorithm", cm)


    # -----------------------------
    # Save to CSV
    # -----------------------------
    out_file = "results/cm_validation.csv"

    with open(out_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["cm", "mean_csr", "std_csr"])
        writer.writeheader()
        for r in results:
            writer.writerow({
                "cm": r["cm"],
                "mean_csr": f"{r['mean_csr']:.6f}",
                "std_csr": f"{r['std_csr']:.6f}",
            })

    print("\nSaved results to:", out_file)  