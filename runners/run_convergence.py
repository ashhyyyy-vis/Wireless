import os
import csv
import argparse
from main_convergence import generate_convergence_data
from simulation.cases import convergence_cases

def run_all_convergence(mode="algorithm", n_runs=5, lambda_val=None, base_seed=100):
    """
    Run convergence analysis for all scenarios in convergence_cases.
    """
    scenarios = list(convergence_cases.keys())
    summary_results = []

    print("=" * 60)
    print(f"Batch Convergence Run | Mode: {mode} | Runs: {n_runs}")
    print("=" * 60)

    for scenario in scenarios:
        out_file, conv_time, final_csr = generate_convergence_data(
            scenario, 
            mode=mode, 
            n_runs=n_runs, 
            lambda_val=lambda_val,
            base_seed=base_seed
        )
        
        summary_results.append({
            "scenario": scenario,
            "convergence_time_s": conv_time,
            "final_csr": final_csr,
            "csv_path": out_file
        })

    # Save summary
    os.makedirs("results", exist_ok=True)
    summary_file = f"results/convergence_summary_{mode}.csv"
    with open(summary_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["scenario", "convergence_time_s", "final_csr", "csv_path"])
        writer.writeheader()
        writer.writerows(summary_results)

    print("\n" + "=" * 60)
    print(f"Batch convergence run complete.")
    print(f"Summary saved to: {summary_file}")
    print("=" * 60)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Batch Convergence Analysis")
    parser.add_argument("--mode", default="algorithm", choices=["algorithm", "energy_algorithm"], help="Algorithm mode")
    parser.add_argument("--runs", type=int, default=5, help="Number of runs per scenario")
    parser.add_argument("--lambda_", type=float, default=None, help="Override lambda")
    parser.add_argument("--seed", type=int, default=100, help="Base seed")
    
    args = parser.parse_args()
    
    run_all_convergence(mode=args.mode, n_runs=args.runs, lambda_val=args.lambda_, base_seed=args.seed)
