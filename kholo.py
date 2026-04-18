import math
import csv
import numpy as np
from multiprocessing import Pool, cpu_count

from run_simulation import run_one
from simulation.algorithm import CMType


# -----------------------------
# Scenario parser
# -----------------------------
def parse_scenario(s: str):
    env_code, d, phi, rho = s.split("-")

    env_map = {
        "DU": "urban",
        "RU": "rural",
    }

    env = env_map[env_code]

    d = float(d)
    phi = math.radians(float(phi))
    rho = float(rho)

    cx = d * math.cos(phi)
    cy = d * math.sin(phi)

    return env, cx, cy, rho


# -----------------------------
# Worker
# -----------------------------
def _run_job(args):
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
def _run_batch(mode, env, cx, cy, rho, cm, n_runs, workers, total, phase1, lam):
    name = mode if cm is None else cm.name

    jobs = [
        (mode, cm, 100 + i, env, cx, cy, rho, total, phase1, lam)
        for i in range(n_runs)
    ]

    with Pool(workers) as p:
        vals = p.map(_run_job, jobs)

    return {
        "cm": name,
        "mean_csr": float(np.mean(vals)),
        "std_csr": float(np.std(vals)),
    }


# -----------------------------
# PUBLIC FUNCTION
# -----------------------------
def run_all_scenarios(
    scenarios,
    out_file="results/all_scenarios_results.csv",
    n_runs=5,
    lambda_val=11,
    phase1=30,
    phase3=2 * 60,
    workers=None,
):
    """
    Run all scenarios and save results to CSV.

    Args:
        scenarios (list[str]): List like ["DU-100-60-4", ...]
        out_file (str): Output CSV path
        n_runs (int): Runs per config
        lambda_val (float): Traffic intensity
        phase1 (int): Phase 1 duration
        phase3 (int): Phase 3 duration
        workers (int): Number of parallel workers

    Returns:
        list[dict]: results
    """

    total = phase1 + phase3
    workers = workers or max(1, cpu_count() - 1)

    all_results = []

    for scenario in scenarios:
        print("\n" + "=" * 60)
        print(f"Scenario: {scenario}")
        print("=" * 60)

        env, cx, cy, rho = parse_scenario(scenario)

        # Baselines
        for mode in ["no_drone", "static_drone"]:
            res = _run_batch(
                mode, env, cx, cy, rho,
                cm=None,
                n_runs=n_runs,
                workers=workers,
                total=total,
                phase1=phase1,
                lam=lambda_val
            )
            all_results.append({"scenario": scenario, **res})

        # CM metrics
        for cm in CMType:
            res = _run_batch(
                "algorithm", env, cx, cy, rho,
                cm=cm,
                n_runs=n_runs,
                workers=workers,
                total=total,
                phase1=phase1,
                lam=lambda_val
            )
            all_results.append({"scenario": scenario, **res})

    # Save CSV
    with open(out_file, "w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["scenario", "cm", "mean_csr", "std_csr"]
        )
        writer.writeheader()

        for r in all_results:
            writer.writerow({
                "scenario": r["scenario"],
                "cm": r["cm"],
                "mean_csr": f"{r['mean_csr']:.6f}",
                "std_csr": f"{r['std_csr']:.6f}",
            })

    print(f"\nSaved -> {out_file}")

    return all_results