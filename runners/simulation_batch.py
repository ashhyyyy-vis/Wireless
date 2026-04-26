import math
import csv
import numpy as np
from multiprocessing import Pool, cpu_count

from .simulation_core import run_one
from simulation.config import LAMBDA_ARRIVAL
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
    """
    Worker function. Now returns metadata to identify the result in the flattened pool.
    """
    scenario, mode_label, mode, cm, seed, env, cx, cy, rho, total, phase1, lam = args

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

    return {
        "scenario": scenario,
        "mode_label": mode_label,
        "csr": result["final_csr"],
        "steps": result["steps_taken"]
    }


def _write_scenario_result(scenario, scenario_results, out_file, include_energy=False):
    """
    Write a single scenario's results to CSV file.
    """
    import os
    import csv
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(out_file), exist_ok=True)
    
    # Check if file exists to decide whether to write header
    file_exists = os.path.exists(out_file)
    
    # Prepare CSV headers
    headers = ["scenario", "no_drone", "static_drone"] + [f"CM{i}" for i in range(1, 8)]
    if include_energy:
        headers += ["Energy_CM7", "Energy_Steps"]
    
    with open(out_file, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        
        # Write header only if file is new
        if not file_exists:
            writer.writeheader()

        # Prepare row for this scenario
        row = {"scenario": scenario}
        
        # Add all metrics to row
        for metric_name in headers[1:]:  # Skip scenario column
            val = scenario_results.get(metric_name)
            if val is not None:
                row[metric_name] = f"{val:.6f}"
            else:
                row[metric_name] = "0.000000"
        
        writer.writerow(row)
        print(f"Scenario {scenario} results appended to {out_file}")


def run_all_scenarios(
    scenarios,
    out_file="results/all_scenarios_results.csv",
    n_runs=5,
    lambda_val=None,
    phase1=30*60,
    phase3=3600,
    workers=None,
    include_energy=False,
):
    """
    Run all scenarios in a single flattened pool for 100% CPU utilization.
    Saves results to CSV after each scenario completion.
    """
    import time
    total_sim_time = phase1 + phase3
    workers = workers or max(1, cpu_count() - 3)
    
    # 1. Build all jobs
    all_jobs = []
    expected_jobs_per_scenario = {}
    
    for scenario in scenarios:
        env, cx, cy, rho = parse_scenario(scenario)
        current_lambda = lambda_val if lambda_val is not None else LAMBDA_ARRIVAL[env]
        
        # Define modes for this scenario
        modes = [
            ("no_drone", "no_drone", None),
            ("static_drone", "static_drone", None),
        ]
        for cm in CMType:
            modes.append((cm.name, "algorithm", cm))
        
        if include_energy:
            modes.append(("Energy_CM7", "energy_algorithm", CMType.CM7))
            
        expected_jobs_per_scenario[scenario] = len(modes) * n_runs
        
        for mode_label, mode, cm in modes:
            for i in range(n_runs):
                all_jobs.append((
                    scenario, mode_label, mode, cm, 100 + i,
                    env, cx, cy, rho, total_sim_time, phase1, current_lambda
                ))

    # 2. Process all jobs in parallel
    print("=" * 60)
    print(f"Flattened Batch Runner: {len(scenarios)} scenarios | {len(all_jobs)} total jobs")
    print(f"Using {workers} parallel workers")
    print("=" * 60)

    # Tracking dictionaries
    # scenario_data[scenario][mode_label] = {"csrs": [], "steps": []}
    scenario_data = {s: {} for s in scenarios}
    jobs_finished_per_scenario = {s: 0 for s in scenarios}
    all_final_results = [] # To preserve return format

    completed_total = 0
    start_time = time.time()

    with Pool(workers) as p:
        # Use imap_unordered for maximum throughput
        for res in p.imap_unordered(_run_job, all_jobs):
            scenario = res["scenario"]
            label = res["mode_label"]
            csr = res["csr"]
            steps = res["steps"]
            
            # Update data
            if label not in scenario_data[scenario]:
                scenario_data[scenario][label] = {"csrs": [], "steps": []}
            
            scenario_data[scenario][label]["csrs"].append(csr)
            scenario_data[scenario][label]["steps"].append(steps)
            
            jobs_finished_per_scenario[scenario] += 1
            completed_total += 1
            
            # Print progress bar or log
            if completed_total % 5 == 0 or completed_total == len(all_jobs):
                elapsed = time.time() - start_time
                print(f" Progress: {completed_total}/{len(all_jobs)} jobs done | {elapsed:.1f}s elapsed")

            # 3. Check if a scenario is fully completed
            if jobs_finished_per_scenario[scenario] == expected_jobs_per_scenario[scenario]:
                print(f"\n[Scenario Complete] {scenario}")
                
                # Compute means for CSV
                scenario_results_summary = {}
                for lbl, data in scenario_data[scenario].items():
                    mean_csr = float(np.mean(data["csrs"]))
                    std_csr = float(np.std(data["csrs"]))
                    mean_steps = float(np.mean(data["steps"]))
                    
                    if lbl == "Energy_CM7":
                        scenario_results_summary["Energy_CM7"] = mean_csr
                        scenario_results_summary["Energy_Steps"] = mean_steps
                    else:
                        scenario_results_summary[lbl] = mean_csr
                    
                    # Store in the flat return format as well
                    all_final_results.append({
                        "scenario": scenario,
                        "cm": lbl,
                        "mean_csr": mean_csr,
                        "std_csr": std_csr,
                        "mean_steps": mean_steps
                    })
                
                # Write to CSV
                _write_scenario_result(scenario, scenario_results_summary, out_file, include_energy=include_energy)

    print(f"\nAll {len(scenarios)} scenarios completed. Final CSV: {out_file}")
    return all_final_results