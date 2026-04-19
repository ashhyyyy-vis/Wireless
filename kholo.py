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
def _write_scenario_result(scenario, scenario_results, out_file):
    """
    Write a single scenario's results to CSV file.
    
    Args:
        scenario (str): Scenario identifier
        scenario_results (dict): Results for all modes of this scenario
        out_file (str): Output CSV path
    """
    import os
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(out_file), exist_ok=True)
    
    # Check if file exists to decide whether to write header
    file_exists = os.path.exists(out_file)
    
    # Prepare CSV headers
    headers = ["scenario", "no_drone", "static_drone"] + [f"CM{i}" for i in range(1, 8)]
    
    with open(out_file, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        
        # Write header only if file is new
        if not file_exists:
            writer.writeheader()

        # Prepare row for this scenario
        row = {"scenario": scenario}
        
        # Add all metrics to row
        for metric_name in headers[1:]:  # Skip scenario column
            row[metric_name] = f"{scenario_results.get(metric_name, 0.0):.6f}"
        
        writer.writerow(row)
        print(f"Scenario {scenario} results appended to {out_file}")


def run_all_scenarios(
    scenarios,
    out_file="results/all_scenarios_results.csv",
    n_runs=5,
    lambda_val=5,
    phase1=30,
    phase3=2 * 60,
    workers=None,
):
    """
    Run all scenarios and save results to CSV after each scenario completion.

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

        # Collect results for this scenario
        scenario_results = {}

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
            scenario_results[res["cm"]] = res["mean_csr"]

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
            scenario_results[res["cm"]] = res["mean_csr"]

        # Write this scenario's results immediately
        _write_scenario_result(scenario, scenario_results, out_file)

    print(f"\nAll scenarios completed. Results in {out_file}")
    return all_results