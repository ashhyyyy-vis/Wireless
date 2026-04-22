import sys
import csv
import time
import math
import argparse
import numpy as np
from multiprocessing import Pool, cpu_count

sys.path.insert(0, ".")

from runners import run_one
from simulation.algorithm import CMType
from simulation.config import LAMBDA_ARRIVAL


# -----------------------------
# Worker
# -----------------------------
def run_job(args):
    mode, cm, seed, env, cx, cy, rho, total, phase1, lam = args

    result = run_one(
        env=env,
        hotspot_cx=cx,
        hotspot_cy=cy,
        rho=rho,
        mode=mode,
        cm_type=cm,
        sim_duration_s=total,
        phase2_start_s=phase1,
        seed=seed,
        lambda_override=lam,
        verbose=False,
    )

    return result["final_csr"]


# -----------------------------
# Batch runner
# -----------------------------
def run_batch(mode, env, cx, cy, rho, total, phase1, lam, n_runs, workers, cm=None):
    name = mode if cm is None else cm.name
    print(f"\n>> {name}")

    jobs = [
        (mode, cm, 100 + i, env, cx, cy, rho, total, phase1, lam)
        for i in range(n_runs)
    ]

    with Pool(workers) as p:
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
# MAIN
# -----------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Metric Comparison Script")
    parser.add_argument("--scenario", default="RU-0-60-25", help="Scenario identifier (e.g. RU-0-60-25)")
    parser.add_argument("--lambda_", type=float, default=None, help="Override arrival rate lambda")
    parser.add_argument("--runs", type=int, default=3, help="Number of simulation runs")
    parser.add_argument("--phase1", type=float, default=30.0, help="Phase 1 duration")
    parser.add_argument("--phase3", type=float, default=120.0, help="Phase 3 duration")
    
    args = parser.parse_args()

    np.random.seed(100)
    start_time = time.time()

    env, cx, cy, rho = parse_scenario(args.scenario)
    lam = args.lambda_ if args.lambda_ is not None else LAMBDA_ARRIVAL[env]
    total_duration = args.phase1 + args.phase3
    num_workers = max(1, cpu_count() - 1)

    print("=" * 60)
    print(f"Scenario: {args.scenario}")
    print(f"Parsed: env={env}, hotspot=({cx:.1f},{cy:.1f}), rho={rho}")
    print(f"Config: lambda={lam}, runs={args.runs}, duration={total_duration}s")
    print("=" * 60)

    results = []

    # -----------------------------
    # Baselines
    # -----------------------------
    results.append(run_batch("no_drone", env, cx, cy, rho, total_duration, args.phase1, lam, args.runs, num_workers))
    results.append(run_batch("static_drone", env, cx, cy, rho, total_duration, args.phase1, lam, args.runs, num_workers))

    # -----------------------------
    # All CM metrics
    # -----------------------------
    for cm in CMType:
        results.append(run_batch("algorithm", env, cx, cy, rho, total_duration, args.phase1, lam, args.runs, num_workers, cm))

    # -----------------------------
    # Save CSV
    # -----------------------------
    import os
    os.makedirs("results", exist_ok=True)
    out_file = f"results/{args.scenario}_results.csv"

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
    print(f"{time.time() - start_time:.2f} seconds run time")