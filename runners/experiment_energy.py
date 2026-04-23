import os
import csv
import argparse
import numpy as np
from multiprocessing import Pool, cpu_count
from .simulation_core import run_one
from simulation.config import LAMBDA_ARRIVAL, ALGO_ALPHA, ALGO_EPSILON, ALGO_ENERGY_COST
from .simulation_batch import parse_scenario

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
    scenario, mode, lambda_val, seed, alpha, epsilon, energy_cost = args
    env, cx, cy, rho = parse_scenario(scenario)
    
    # Use standard duration for comparison
    phase1 = 30.0
    phase3 = 300.0  # 5 minutes of drone movement
    total = phase1 + phase3
    
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
    
    return res["final_csr"], res["steps_taken"]

def compare_energy_aware(scenarios=None, n_runs=3, lambda_val=None, base_seed=100):
    scenarios = scenarios or DEFAULT_SUBSET
    results = []

    print("=" * 100)
    print(f"Energy-Aware Comparison | Runs: {n_runs}")
    print(f"{'Scenario':<15} | {'CSR Legacy':<10} | {'CSR Energy':<10} | {'Steps L':<8} | {'Steps E':<8} | {'Saved':<6} | {'Delta CSR':<10}")
    print("-" * 100)

    for scenario in scenarios:
        env, _, _, _ = parse_scenario(scenario)
        lam = lambda_val if lambda_val is not None else LAMBDA_ARRIVAL[env]
        
        legacy_csrs = []
        legacy_steps = []
        energy_csrs = []
        energy_steps = []
        
        # Run legacy
        for i in range(n_runs):
            csr, steps = run_energy_job((scenario, "algorithm", lam, base_seed + i, None, None, None))
            legacy_csrs.append(csr)
            legacy_steps.append(steps)
            
        # Run energy-aware
        for i in range(n_runs):
            csr, steps = run_energy_job((scenario, "energy_algorithm", lam, base_seed + i, ALGO_ALPHA, ALGO_EPSILON, ALGO_ENERGY_COST))
            energy_csrs.append(csr)
            energy_steps.append(steps)
            
        mean_csr_l = np.mean(legacy_csrs)
        mean_steps_l = np.mean(legacy_steps)
        mean_csr_e = np.mean(energy_csrs)
        mean_steps_e = np.mean(energy_steps)
        
        saved = mean_steps_l - mean_steps_e
        delta_csr = mean_csr_e - mean_csr_l
        
        print(f"{scenario:<15} | {mean_csr_l:<10.4f} | {mean_csr_e:<10.4f} | {mean_steps_l:<8.1f} | {mean_steps_e:<8.1f} | {saved:<6.1f} | {delta_csr:<10.4f}")
        
        results.append({
            "scenario": scenario,
            "csr_legacy": mean_csr_l,
            "csr_energy": mean_csr_e,
            "steps_legacy": mean_steps_l,
            "steps_energy": mean_steps_e,
            "steps_saved": saved,
            "csr_delta": delta_csr
        })

    # Save results
    os.makedirs("results", exist_ok=True)
    out_file = "results/energy_comparison_report.csv"
    with open(out_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)
        
    print("-" * 100)
    print(f"Energy comparison report saved to: {out_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Energy-Aware vs Legacy Comparison")
    parser.add_argument("--scenarios", nargs="+", help="Scenarios to evaluate")
    parser.add_argument("--runs", type=int, default=3, help="Number of runs per scenario")
    parser.add_argument("--lambda_", type=float, default=None, help="Override lambda")
    parser.add_argument("--seed", type=int, default=100, help="Base seed")
    
    args = parser.parse_args()
    
    compare_energy_aware(scenarios=args.scenarios, n_runs=args.runs, lambda_val=args.lambda_, base_seed=args.seed)
