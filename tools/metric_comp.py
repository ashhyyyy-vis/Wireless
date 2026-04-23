import sys
import csv
import time as wall_time
import argparse
import numpy as np
from multiprocessing import Pool, cpu_count

from runners import run_one, parse_scenario
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
def run_batch(pool, mode, env, cx, cy, rho, total, phase1, lam, n_runs, cm=None):
    name = mode if cm is None else cm.name
    print(f"\n>> {name}")

    jobs = [
        (mode, cm, 100 + i, env, cx, cy, rho, total, phase1, lam)
        for i in range(n_runs)
    ]

    csr_vals = pool.map(run_job, jobs)

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
def run_metric_comp(parser: argparse.ArgumentParser):
    parser.add_argument("--scenario", default="RU-0-60-25", help="Scenario identifier (e.g. RU-0-60-25)")
    parser.add_argument("--lambda_", type=float, default=None, help="Override arrival rate lambda")
    parser.add_argument("--runs", type=int, default=3, help="Number of simulation runs")
    parser.add_argument("--phase1", type=float, default=30.0, help="Phase 1 duration")
    parser.add_argument("--phase3", type=float, default=120.0, help="Phase 3 duration")
    
    args = parser.parse_args()

    np.random.seed(100)
    start_time = wall_time.time()

    env, cx, cy, rho = parse_scenario(args.scenario)
    lam = args.lambda_ if args.lambda_ is not None else LAMBDA_ARRIVAL[env]
    total_duration = args.phase1 + args.phase3
    num_workers = max(1, cpu_count())

    print("=" * 60)
    print(f"Scenario: {args.scenario}")
    print(f"Parsed: env={env}, hotspot=({cx:.1f},{cy:.1f}), rho={rho}")
    print(f"Config: lambda={lam}, runs={args.runs}, duration={total_duration}s")
    print("=" * 60)

    results = []

    with Pool(num_workers) as pool:
        # -----------------------------
        # Baselines
        # -----------------------------
        results.append(run_batch(pool, "no_drone", env, cx, cy, rho, total_duration, args.phase1, lam, args.runs))
        results.append(run_batch(pool, "static_drone", env, cx, cy, rho, total_duration, args.phase1, lam, args.runs))

        # -----------------------------
        # All CM metrics
        # -----------------------------
        for cm in CMType:
            results.append(run_batch(pool, "algorithm", env, cx, cy, rho, total_duration, args.phase1, lam, args.runs, cm))

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
    print(f"{wall_time.time() - start_time:.2f} seconds run time")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Metric Comparison Script")
    run_metric_comp(parser)