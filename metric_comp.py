import sys
import csv
import time
import math
import numpy as np
from multiprocessing import Pool, cpu_count

sys.path.insert(0, ".")

from run_simulation import run_one
from simulation.algorithm import CMType


# -----------------------------
# CONFIG
# -----------------------------
PHASE1 = 30 
PHASE3 = 2 * 60
TOTAL  = PHASE1 + PHASE3

LAMBDA = 11
N_RUNS = 5
NUM_WORKERS = max(1, cpu_count() - 1)


# -----------------------------
# SCENARIO STRING (HARDCODE HERE)
# -----------------------------
SCENARIO = "DU-100-60-4"


# -----------------------------
# Scenario parser
# -----------------------------
def parse_scenario(s: str):
    parts = s.split("-")
    if len(parts) != 4:
        raise ValueError(f"Invalid scenario format: {s}")

    env_code, d_str, phi_str, rho_str = parts

    env_map = {
        "DU": "urban",
        "RU": "rural",
    }

    if env_code not in env_map:
        raise ValueError(f"Unknown env code: {env_code}")

    env = env_map[env_code]

    d = float(d_str)
    phi = math.radians(float(phi_str))
    rho = float(rho_str)

    cx = d * math.cos(phi)
    cy = d * math.sin(phi)

    return env, cx, cy, rho


# -----------------------------
# Worker
# -----------------------------
def run_job(args):
    mode, cm, seed, env, cx, cy, rho = args

    result = run_one(
        env=env,
        hotspot_cx=cx,
        hotspot_cy=cy,
        rho=rho,
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
# Batch runner
# -----------------------------
def run_batch(mode, env, cx, cy, rho, cm=None):
    name = mode if cm is None else cm.name
    print(f"\n>> {name}")

    jobs = [
        (mode, cm, 100 + i, env, cx, cy, rho)
        for i in range(N_RUNS)
    ]

    with Pool(NUM_WORKERS) as p:
        csr_vals = p.map(run_job, jobs)

    mean = float(np.mean(csr_vals))
    std  = float(np.std(csr_vals))

    print(f"   --> {mean:.4f} ± {std:.4f}")

    return {
        "cm": name,
        "mean_csr": mean,
        "std_csr": std,
    }


# -----------------------------
# MAIN
# -----------------------------
if __name__ == "__main__":
    start=time.time()

    env, cx, cy, rho = parse_scenario(SCENARIO)

    print("=" * 60)
    print(f"Scenario: {SCENARIO}")
    print(f"Parsed: env={env}, hotspot=({cx:.1f},{cy:.1f}), rho={rho}")
    print("=" * 60)

    results = []

    # -----------------------------
    # Baselines
    # -----------------------------
    results.append(run_batch("no_drone", env, cx, cy, rho))
    results.append(run_batch("static_drone", env, cx, cy, rho))

    # -----------------------------
    # All CM metrics
    # -----------------------------
    for cm in CMType:
        results.append(run_batch("algorithm", env, cx, cy, rho, cm))

    # -----------------------------
    # Save CSV
    # -----------------------------
    out_file = f"results/{SCENARIO}_results.csv"

    with open(out_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["cm", "mean_csr", "std_csr"])
        writer.writeheader()
        for r in results:
            writer.writerow({
                "cm": r["cm"],
                "mean_csr": f"{r['mean_csr']:.6f}",
                "std_csr": f"{r['std_csr']:.6f}",
            })

    print(f"\nSaved -> {out_file}")
    print(f"{time.time()-start} seconds run time")