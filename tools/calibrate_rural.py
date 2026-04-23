"""
Calibrating lambda for rural environment.
"""
import sys
import os
import argparse
import numpy as np
import csv
from multiprocessing import Pool, cpu_count

from runners import run_one, parse_scenario

def run_calib_job(args):
    env, lambda_val, seed, duration, phase2_start = args
    res = run_one(
        env=env,
        mode="no_drone",
        sim_duration_s=duration,
        phase2_start_s=phase2_start,
        seed=seed,
        lambda_override=lambda_val,
        verbose=False
    )
    return res['final_csr']

def main():
    parser = argparse.ArgumentParser(description="Calibrate lambda for rural environment")
    parser.add_argument("--start", type=float, default=1.0)
    parser.add_argument("--end", type=float, default=6.0)
    parser.add_argument("--step", type=float, default=0.25)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--duration", type=float, default=1800.0)
    parser.add_argument("--phase2-start", type=float, default=300.0)
    
    args = parser.parse_args()
    
    env = "rural"
    # Generate lambda values
    num_steps = int((args.end - args.start) / args.step) + 1
    lambdas = [round(args.start + i * args.step, 2) for i in range(num_steps)]
    
    print(f"Calibrating lambda for {env} environment...")
    print(f"{'Lambda':<10} {'Mean CSR':<12} {'Std Dev':<10}")
    print("-" * 40)
    
    all_jobs = []
    for l in lambdas:
        for i in range(args.runs):
            all_jobs.append((env, l, 100 + i, args.duration, args.phase2_start))
    
    workers = min(cpu_count(), len(all_jobs))
    all_results = []
    results = []
    with Pool(workers) as p:
        for i, res in enumerate(p.imap(run_calib_job, all_jobs)):
            all_results.append(res)
            
            if (i + 1) % args.runs == 0:
                idx = i // args.runs
                l = lambdas[idx]
                csrs = all_results[idx * args.runs : (idx + 1) * args.runs]
                mean_csr = np.mean(csrs)
                std_csr = np.std(csrs)
                print(f"{l:<10.2f} {mean_csr:<12.4f} {std_csr:<10.4f}")
                results.append({"lambda": l, "mean_csr": mean_csr, "std_csr": std_csr})

    # Save to results
    os.makedirs("results", exist_ok=True)
    out_file = f"results/lambda_calibration_rural.csv"
    with open(out_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["lambda", "mean_csr", "std_csr"])
        writer.writeheader()
        writer.writerows(results)
    print(f"\nCalibration data saved to {out_file}")

if __name__ == "__main__":
    main()