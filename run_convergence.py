import os
import csv
import argparse
import numpy as np
from multiprocessing import Pool, cpu_count
from main_convergence import _run_single
from simulation.cases import convergence_cases
from simulation.config import LAMBDA_ARRIVAL
from kholo import parse_scenario

def save_summary(summary_results, mode):
    """Helper to write/update the summary CSV."""
    os.makedirs("results", exist_ok=True)
    summary_file = f"results/convergence_summary_{mode}.csv"
    with open(summary_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["scenario", "convergence_time_s", "final_csr", "csv_path"])
        writer.writeheader()
        writer.writerows(summary_results)
    return summary_file

def run_all_convergence(mode="algorithm", n_runs=5, lambda_val=None, base_seed=100):
    """
    Run convergence analysis parallelized across all cores, 
    saving results scenario-by-scenario as they finish.
    """
    scenarios = list(convergence_cases)
    all_jobs = []
    
    for scenario in scenarios:
        env, _, _, _ = parse_scenario(scenario)
        lam = lambda_val if lambda_val is not None else LAMBDA_ARRIVAL[env]
        for i in range(n_runs):
            all_jobs.append((scenario, mode, lam, base_seed + i, 0.0))

    print("=" * 60)
    print(f"Parallel Convergence Run | Mode: {mode} | Total Jobs: {len(all_jobs)}")
    print(f"Utilizing {cpu_count()-1} workers (Incremental Saving Enabled)")
    print("=" * 60)

    summary_results = []
    workers = max(1, cpu_count() - 1)
    
    with Pool(workers) as p:
        # Using imap to process results in the order they were submitted
        # This allows us to 'chunk' the results by scenario
        result_iterator = p.imap(_run_single, all_jobs)
        
        for scenario_idx, scenario in enumerate(scenarios):
            print(f"\nProcessing Scenario {scenario_idx+1}/{len(scenarios)}: {scenario}")
            
            # Collect n_runs for this specific scenario
            scenario_series = []
            try:
                for _ in range(n_runs):
                    scenario_series.append(next(result_iterator))
            except StopIteration:
                break
            
            # Average the series
            times = [t for t, _ in scenario_series[0]]
            avg_csr = []
            for i in range(len(times)):
                vals = [run[i][1] for run in scenario_series if i < len(run)]
                avg_csr.append(float(np.mean(vals)))
            
            # Save individual scenario CSV immediately
            os.makedirs("results", exist_ok=True)
            out_file = f"results/convergence_{mode}_{scenario}.csv"
            with open(out_file, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["time", "csr"])
                for t, c in zip(times, avg_csr):
                    writer.writerow([t, c])
            
            # Calculate convergence (0.1% threshold)
            final_val = avg_csr[-1]
            conv_time = times[0]
            for i in range(len(times)-1, -1, -1):
                if abs(avg_csr[i] - final_val) > 0.001 * final_val:
                    if i + 1 < len(times):
                        conv_time = times[i+1]
                    break
            
            summary_results.append({
                "scenario": scenario,
                "convergence_time_s": conv_time,
                "final_csr": final_val,
                "csv_path": out_file
            })
            
            # Update summary file on disk after every scenario
            summary_file = save_summary(summary_results, mode)
            print(f"  > Done. Conv: {conv_time:6.1f}s | Final CSR: {final_val:.4f}")
            print(f"  > Progress saved to {summary_file}")

    print("\n" + "=" * 60)
    print(f"Batch convergence complete.")
    print("=" * 60)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Parallel Batch Convergence Analysis")
    parser.add_argument("--mode", default="algorithm", choices=["algorithm", "energy_algorithm"], help="Algorithm mode")
    parser.add_argument("--runs", type=int, default=5, help="Number of runs per scenario")
    parser.add_argument("--lambda_", type=float, default=None, help="Override lambda")
    parser.add_argument("--seed", type=int, default=100, help="Base seed")
    
    args = parser.parse_args()
    run_all_convergence(mode=args.mode, n_runs=args.runs, lambda_val=args.lambda_, base_seed=args.seed)
