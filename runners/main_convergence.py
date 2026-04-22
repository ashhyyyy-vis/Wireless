import os
import sys
import csv
import numpy as np
from multiprocessing import Pool, cpu_count
from . import run_one
from simulation.config import LAMBDA_ARRIVAL
from .kholo import parse_scenario

# Add current directory to path
sys.path.append(os.getcwd())

def _run_single(args):
    """Worker for parallel simulation runs."""
    scenario, mode, lambda_val, seed, drone_delay = args
    env, cx, cy, rho = parse_scenario(scenario)
    
    # We use a standard duration for convergence checks
    # 30s warm up + 1800s Phase 1 + 3600s Phase 3
    # Or just use relative timings from config
    phase1 = 30.0
    duration = 3600.0  # 1 hour to ensure convergence
    
    res = run_one(
        env=env,
        hotspot_cx=cx,
        hotspot_cy=cy,
        rho=rho,
        mode=mode,
        seed=seed,
        lambda_override=lambda_val,
        sim_duration_s=phase1 + duration,
        phase2_start_s=phase1,
        phase3_start_s=phase1,
        drone_delay_s=drone_delay,
        verbose=False,
    )

    return res["csr_series"]

def generate_convergence_data(scenario, mode="algorithm", n_runs=5, lambda_val=None, drone_delay_s=0.0, base_seed=100):
    """Runs multiple simulations and averages the CSR time series."""
    env, _, _, _ = parse_scenario(scenario)
    lam = lambda_val if lambda_val is not None else LAMBDA_ARRIVAL[env]
    
    print(f"\n>>> Generating Convergence Data (Scenario={scenario}, Mode={mode}, Lambda={lam})")
    
    jobs = [
        (scenario, mode, lam, base_seed + i, drone_delay_s)
        for i in range(n_runs)
    ]
    
    workers = min(cpu_count(), n_runs)
    with Pool(workers) as p:
        all_series = p.map(_run_single, jobs)
    
    # Align and average
    times = [t for t, _ in all_series[0]]
    avg_csr = []
    
    for i in range(len(times)):
        vals = [run[i][1] for run in all_series if i < len(run)]
        avg_csr.append(np.mean(vals))
    
    # Save to CSV
    os.makedirs("results", exist_ok=True)
    out_file = f"results/convergence_{mode}_{scenario}.csv"
    with open(out_file, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["time", "csr"])
        for t, c in zip(times, avg_csr):
            writer.writerow([t, c])
    
    print(f"Convergence data saved to {out_file}")
    
    # Numerical finding: 
    # Find when CSR stays within 0.1% of final value
    final_val = avg_csr[-1]
    conv_time = None
    for i in range(len(times)-1, -1, -1):
        if abs(avg_csr[i] - final_val) > 0.001 * final_val:
            if i + 1 < len(times):
                conv_time = times[i+1]
            break
    
    # If it never fluctuated more than 0.1% from the end, it converged from the start
    if conv_time is None and times:
        conv_time = times[0]

    if conv_time is not None:
        print(f"Stated Convergence reached at approx {conv_time:.1f}s")
    
    return out_file, conv_time, final_val

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Convergence Data Generator")
    parser.add_argument("--scenario", required=True, help="Scenario (e.g. DU-100-60-4)")
    parser.add_argument("--mode", default="algorithm", choices=["algorithm", "energy_algorithm"])
    parser.add_argument("--runs", type=int, default=5, help="Number of Monte Carlo trials")
    parser.add_argument("--delay", type=float, default=0.0, help="Drone delay (s)")
    parser.add_argument("--seed", type=int, default=100, help="Base random seed")
    
    args = parser.parse_args()
    
    generate_convergence_data(args.scenario, args.mode, args.runs, drone_delay_s=args.delay, base_seed=args.seed)