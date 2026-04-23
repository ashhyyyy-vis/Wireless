"""
Calibration script to find LAMBDA_ARRIVAL that yields target CSR in a FAILED SITE scenario.
Tests no_drone mode with disaster to calibrate for realistic post-failure conditions.
"""
import os
import sys
import argparse
import numpy as np
import csv
from multiprocessing import Pool, cpu_count
from runners import run_one, parse_scenario

def run_calib_job(args):
    scenario, lambda_val, seed, duration, phase2_start = args
    env, cx, cy, rho = parse_scenario(scenario)
    
    # Run with disaster (failed site)
    res = run_one(
        env=env,
        hotspot_cx=cx,
        hotspot_cy=cy,
        rho=rho,
        mode="no_drone",
        seed=seed,
        lambda_override=lambda_val,
        sim_duration_s=duration,
        phase2_start_s=phase2_start,    # Disaster triggers during simulation
        verbose=False,
    )
    return res["final_csr"]

def calibrate_lambda(scenario="DU-0-0-0", start=1.0, end=10.0, steps=10, runs=5, 
                    duration=1800.0, phase2_start=300.0, target_csr=0.85):
    env, _, _, _ = parse_scenario(scenario)
    print("=" * 60)
    print(f"Lambda Calibration (Failed Site Scenario)")
    print(f"Scenario: {scenario} (Env: {env})")
    print(f"Range: [{start}, {end}] | Steps: {steps} | Runs per Step: {runs}")
    print(f"Target CSR: {target_csr:.2f} | Phase 2 starts at: {phase2_start}s")
    print("=" * 60)
    
    lambdas = np.linspace(start, end, steps)
    results = []
    closest_lambda = None
    closest_diff = float('inf')

    print(f"{'Lambda':<10} | {'Mean CSR':<12} | {'Std Dev':<10} | {'Status':<15}")
    print("-" * 60)

    # Prepare all jobs upfront for maximum efficiency
    all_jobs = []
    for lam in lambdas:
        for i in range(runs):
            all_jobs.append((scenario, lam, 100 + i, duration, phase2_start))
    
    workers = min(cpu_count(), len(all_jobs))
    all_results = []
    with Pool(workers) as p:
        for i, res in enumerate(p.imap(run_calib_job, all_jobs)):
            all_results.append(res)
            
            if (i + 1) % runs == 0:
                idx = i // runs
                lam = lambdas[idx]
                csrs = all_results[idx * runs : (idx + 1) * runs]
                mean_csr = np.mean(csrs)
                std_csr = np.std(csrs)
                diff = abs(mean_csr - target_csr)
                
                if diff < closest_diff:
                    closest_diff = diff
                    closest_lambda = lam
                
                status = "CLOSEST" if lam == closest_lambda else ""
                print(f"{lam:<10.4f} | {mean_csr:<12.4f} | {std_csr:<10.4f} | {status:<15}")
                
                results.append({
                    "lambda": float(lam),
                    "mean_csr": float(mean_csr),
                    "std_csr": float(std_csr),
                    "diff_from_target": float(diff)
                })

    # Save to results
    os.makedirs("results", exist_ok=True)
    out_file = f"results/lambda_calibration_failed_site_{scenario}.csv"
    with open(out_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["lambda", "mean_csr", "std_csr", "diff_from_target"])
        writer.writeheader()
        writer.writerows(results)
        
    print("-" * 60)
    print(f"Calibration data saved to {out_file}")
    print(f"\n=== Calibration Results ===")
    print(f"Recommended lambda: {closest_lambda:.4f}")
    print(f"CSR at recommended lambda: {np.mean([r['mean_csr'] for r in results if abs(r['lambda'] - closest_lambda) < 0.001]):.4f}")
    print(f"Difference from target: {closest_diff:.4f}")

def run_calibrate(parser: argparse.ArgumentParser):
    parser.add_argument("--scenario", default="DU-0-0-0", help="Scenario string (e.g. DU-100-60-4)")
    parser.add_argument("--start", type=float, default=1.0, help="Start lambda value")
    parser.add_argument("--end", type=float, default=10.0, help="End lambda value")
    parser.add_argument("--steps", type=int, default=10, help="Number of lambda steps")
    parser.add_argument("--runs", type=int, default=5, help="Runs per lambda step")
    parser.add_argument("--duration", type=float, default=1800.0, help="Simulation duration (seconds)")
    parser.add_argument("--phase2-start", type=float, default=300.0, help="Phase 2 start time (seconds)")
    parser.add_argument("--target-csr", type=float, default=0.85, help="Target CSR for failed site scenario")
    
    args = parser.parse_args()
    
    calibrate_lambda(
        scenario=args.scenario, 
        start=args.start, 
        end=args.end, 
        steps=args.steps, 
        runs=args.runs, 
        duration=args.duration,
        phase2_start=args.phase2_start,
        target_csr=args.target_csr
    )

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Lambda Calibration (Failed Site Scenario)")
    run_calibrate(parser)
