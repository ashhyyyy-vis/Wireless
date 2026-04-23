import time
import os
import sys
import argparse
import numpy as np
import csv
from multiprocessing import Pool, cpu_count
from runners import run_one, parse_scenario

def run_calib_job(args):
    scenario, lambda_val, seed, duration = args
    env, cx, cy, rho = parse_scenario(scenario)
    
    # We run in 'no_drone' mode. 
    res = run_one(
        env=env,
        hotspot_cx=cx,
        hotspot_cy=cy,
        rho=rho,
        mode="no_drone",
        seed=seed,
        lambda_override=lambda_val,
        sim_duration_s=duration,
        phase2_start_s=duration - 900, # Keep network healthy for the whole duration
        verbose=False,
    )
    return res["final_csr"]

def calibrate_lambda(scenario="DU-0-0-0", start=1.0, end=10.0, steps=10, runs=5, duration=1800.0):
    env, _, _, _ = parse_scenario(scenario)
    print("=" * 60)
    print(f"Lambda Calibration (No-Drone, Healthy Network)")
    print(f"Scenario: {scenario} (Env: {env})")
    print(f"Range: [{start}, {end}] | Steps: {steps} | Runs per Step: {runs}")
    print("=" * 60)
    
    lambdas = np.linspace(start, end, steps)
    results = []

    print(f"{'Lambda':<10} | {'Mean CSR':<12} | {'Std Dev':<10}")
    print("-" * 60)

    # Prepare all jobs upfront
    all_jobs = []
    for lam in lambdas:
        for i in range(runs):
            all_jobs.append((scenario, lam, 100 + i, duration))
    
    workers = min(cpu_count(), len(all_jobs))
    all_results = []
    with Pool(workers) as p:
        for i, res in enumerate(p.imap(run_calib_job, all_jobs)):
            all_results.append(res)
            
            # Print as each lambda's batch completes
            if (i + 1) % runs == 0:
                idx = i // runs
                lam = lambdas[idx]
                csrs = all_results[idx * runs : (idx + 1) * runs]
                mean_csr = np.mean(csrs)
                std_csr = np.std(csrs)
                
                print(f"{lam:<10.4f} | {mean_csr:<12.4f} | {std_csr:<10.4f}")
                results.append({
                    "lambda": float(lam),
                    "mean_csr": float(mean_csr),
                    "std_csr": float(std_csr)
                })

    # Save to results
    os.makedirs("results", exist_ok=True)
    out_file = f"results/lambda_calibration_{scenario}.csv"
    with open(out_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["lambda", "mean_csr", "std_csr"])
        writer.writeheader()
        writer.writerows(results)
        
    print("-" * 60)
    print(f"Calibration data saved to {out_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Lambda Calibration (No-Drone)")
    parser.add_argument("--scenario", default="DU-0-0-0", help="Scenario string (e.g. DU-100-60-4)")
    parser.add_argument("--start", type=float, default=1.0)
    parser.add_argument("--end", type=float, default=10.0)
    parser.add_argument("--steps", type=int, default=10)
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--duration", type=float, default=1800.0)
    
    args = parser.parse_args()
    start=time.time()
    calibrate_lambda(
        scenario=args.scenario, 
        start=args.start, 
        end=args.end, 
        steps=args.steps, 
        runs=args.runs, 
        duration=args.duration
    )
    end=time.time()
    print(f"Total time taken: {end-start}")
