import os
import csv
import argparse
import numpy as np
from multiprocessing import Pool, cpu_count
from .simulation_core import run_one
from simulation.config import LAMBDA_ARRIVAL, ALGO_ALPHA, ALGO_EPSILON, ALGO_ENERGY_COST
from .simulation_batch import parse_scenario
from simulation.cases import cases

# Define a representative subset for energy comparison
DEFAULT_SUBSET = [
    "DU-100-60-4",
    "DU-100-90-8",
    "DU-200-120-8",
    "RU-500-60-25",
    "RU-1000-90-50",
    "RU-0-0-25"
]

def run_energy_job(args):
    scenario, mode, lambda_val, seed, alpha, epsilon, energy_cost, phase1, total = args
    env, cx, cy, rho = parse_scenario(scenario)
    
    res = run_one(
        env=env,
        hotspot_cx=cx,
        hotspot_cy=cy,
        rho=rho,
        mode=mode,
        seed=seed,
        lambda_override=lambda_val,
        alpha_override=alpha,
        epsilon_override=epsilon,
        energy_cost_override=energy_cost,
        sim_duration_s=total,
        phase2_start_s=phase1,
        phase3_start_s=phase1,
        verbose=False,
    )
    
    return {
        "scenario": scenario,
        "mode": mode,
        "csr": res["final_csr"],
        "steps": res["steps_taken"]
    }

def compare_energy_aware(scenarios=None, n_runs=3, lambda_val=None, base_seed=100, phase1=None, total=5400.0):
    if phase1 is None:
        phase1 = total / 3.0
    if scenarios == ["all"] or scenarios == "all":
        scenarios = [s for case_list in cases.values() for s in case_list]
    else:
        scenarios = scenarios or DEFAULT_SUBSET
    
    # 1. Build all jobs
    all_jobs = []
    expected_jobs_per_scenario = {}
    for scenario in scenarios:
        env, _, _, _ = parse_scenario(scenario)
        lam = lambda_val if lambda_val is not None else LAMBDA_ARRIVAL[env]
        
        scenario_jobs = []
        for i in range(n_runs):
            # Legacy job
            scenario_jobs.append((scenario, "algorithm", lam, base_seed + i, None, None, None, phase1, total))
            # Energy-aware job
            scenario_jobs.append((scenario, "energy_algorithm", lam, base_seed + i, ALGO_ALPHA, ALGO_EPSILON, ALGO_ENERGY_COST, phase1, total))
        
        all_jobs.extend(scenario_jobs)
        expected_jobs_per_scenario[scenario] = len(scenario_jobs)

    # 2. Prepare CSV file
    os.makedirs("results", exist_ok=True)
    out_file = "results/energy_comparison_report.csv"
    file_exists = os.path.exists(out_file)
    
    csv_fields = ["scenario", "csr_legacy", "csr_energy", "steps_legacy", "steps_energy", "steps_saved", "csr_delta"]
    with open(out_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields)
        writer.writeheader()

    # 3. Run in parallel with incremental feedback
    print("=" * 100)
    print(f"Energy-Aware Comparison (Parallel) | Scenarios: {len(scenarios)} | Runs: {n_runs} | Duration: {total}s (Warmup: {phase1}s)")
    print(f"{'Scenario':<15} | {'CSR Legacy':<10} | {'CSR Energy':<10} | {'Steps L':<8} | {'Steps E':<8} | {'Saved':<6} | {'Delta CSR':<10}")
    print("-" * 100)

    data = {s: {"algorithm": {"csrs": [], "steps": []}, "energy_algorithm": {"csrs": [], "steps": []}} for s in scenarios}
    jobs_finished = {s: 0 for s in scenarios}
    
    workers = min(cpu_count(), len(all_jobs))
    with Pool(workers) as p:
        for res in p.imap_unordered(run_energy_job, all_jobs):
            s = res["scenario"]
            m = res["mode"]
            data[s][m]["csrs"].append(res["csr"])
            data[s][m]["steps"].append(res["steps"])
            jobs_finished[s] += 1

            # Check if this scenario is complete
            if jobs_finished[s] == expected_jobs_per_scenario[s]:
                mean_csr_l = np.mean(data[s]["algorithm"]["csrs"])
                mean_steps_l = np.mean(data[s]["algorithm"]["steps"])
                mean_csr_e = np.mean(data[s]["energy_algorithm"]["csrs"])
                mean_steps_e = np.mean(data[s]["energy_algorithm"]["steps"])
                
                saved = mean_steps_l - mean_steps_e
                delta_csr = mean_csr_e - mean_csr_l
                
                # Print to terminal
                print(f"{s:<15} | {mean_csr_l:<10.4f} | {mean_csr_e:<10.4f} | {mean_steps_l:<8.1f} | {mean_steps_e:<8.1f} | {saved:<6.1f} | {delta_csr:<10.4f}")
                
                # Append to CSV
                with open(out_file, "a", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=csv_fields)
                    writer.writerow({
                        "scenario": s,
                        "csr_legacy": mean_csr_l,
                        "csr_energy": mean_csr_e,
                        "steps_legacy": mean_steps_l,
                        "steps_energy": mean_steps_e,
                        "steps_saved": saved,
                        "csr_delta": delta_csr
                    })
        
    print("-" * 100)
    print(f"Energy comparison report finalized at: {out_file}")
        
    print("-" * 100)
    print(f"Energy comparison report saved to: {out_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Energy-Aware vs Legacy Comparison")
    parser.add_argument("--scenarios", nargs="+", help="Scenarios to evaluate")
    parser.add_argument("--runs", type=int, default=3, help="Number of runs per scenario")
    parser.add_argument("--lambda_", type=float, default=None, help="Override lambda")
    parser.add_argument("--duration", type=float, default=5400.0, help="Total simulation duration (s)")
    parser.add_argument("--warmup", type=float, default=None, help="Warmup/Static phase duration (s). Defaults to 1/3 of duration.")
    parser.add_argument("--seed", type=int, default=100, help="Base seed for reproducibility")
    
    args = parser.parse_args()
    
    compare_energy_aware(
        scenarios=args.scenarios, 
        n_runs=args.runs, 
        lambda_val=args.lambda_, 
        base_seed=args.seed,
        phase1=args.warmup,
        total=args.duration
    )
