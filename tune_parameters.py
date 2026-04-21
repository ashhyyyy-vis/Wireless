import os
import sys
import argparse
import numpy as np
import csv

# Add current directory to path
sys.path.append(os.getcwd())

from run_simulation import run_one
from simulation.config import LAMBDA_ARRIVAL, ALGO_EPSILON, ALGO_ALPHA, ALGO_ENERGY_COST
from simulation.algorithm import CMType
from kholo import parse_scenario

def run_tuning(scenario, mode, duration, start, end, steps):
    env, cx, cy, rho = parse_scenario(scenario)
    config_lambda = LAMBDA_ARRIVAL[env]
    
    print(f"\n>>> Tuning {mode.capitalize()} (Scenario={scenario}, Env={env})")
    print(f">>> Duration={duration}s, Seed=100")
    print("-" * 100)
    header = f"{mode.capitalize():<12} | {'Energy CSR':<12} | {'Legacy CSR':<12} | {'Steps E':<10} | {'Steps L':<10} | {'Saved':<10}"
    print(header)
    print("-" * 100)
    
    values = np.linspace(start, end, steps)
    results = []
    
    # Timing constants
    phase1 = 30.0
    total_duration = phase1 + duration

    for val in values:
        # Determine parameter overrides
        l_val = val if mode == "lambda" else config_lambda
        a_val = val if mode == "alpha" else ALGO_ALPHA
        e_val = val if mode == "epsilon" else ALGO_EPSILON
        
        # Run legacy algorithm
        res_legacy = run_one(
            env=env,
            hotspot_cx=cx,
            hotspot_cy=cy,
            rho=rho,
            mode="algorithm",
            sim_duration_s=total_duration,
            phase2_start_s=phase1,
            phase3_start_s=phase1,
            lambda_override=float(l_val),
            seed=100,
            verbose=False
        )
        
        # Run energy-aware algorithm
        res_energy = run_one(
            env=env,
            hotspot_cx=cx,
            hotspot_cy=cy,
            rho=rho,
            mode="energy_algorithm",
            sim_duration_s=total_duration,
            phase2_start_s=phase1,
            phase3_start_s=phase1,
            lambda_override=float(l_val),
            alpha_override=float(a_val),
            epsilon_override=float(e_val),
            seed=100,
            verbose=False
        )
        
        c_e = res_energy['final_csr']
        c_l = res_legacy['final_csr']
        s_e = res_energy['steps_taken']
        s_l = res_legacy['steps_taken']
        saved = s_l - s_e
        
        print(f"{val:<12.4f} | {c_e:<12.4f} | {c_l:<12.4f} | {s_e:<10} | {s_l:<10} | {saved:<10}")
        
        results.append({
            mode: val,
            "energy_csr": c_e,
            "legacy_csr": c_l,
            "steps_energy": s_e,
            "steps_legacy": s_l,
            "steps_saved": saved
        })

    print("-" * 100)
    
    # Save to CSV
    os.makedirs("results", exist_ok=True)
    out_file = f"results/tuning_{mode}_{scenario}.csv"
    with open(out_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)
    print(f"Results saved to {out_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Unified Tuning Script for Drone Positioning")
    parser.add_argument("--scenario", required=True, help="Scenario (e.g. DU-100-60-4)")
    parser.add_argument("--mode", choices=["lambda", "alpha", "epsilon"], required=True)
    parser.add_argument("--duration", type=float, default=300.0, help="Phase 3 duration (s)")
    
    # Ranges
    parser.add_argument("--start", type=float, help="Start value")
    parser.add_argument("--end", type=float, help="End value")
    parser.add_argument("--steps", type=int, default=5, help="Number of steps")
    
    args = parser.parse_args()
    
    # Default ranges if not provided
    defaults = {
        "lambda": (2.0, 10.0),
        "alpha": (1.0, 50.0),
        "epsilon": (0.0, 0.05)
    }
    
    start = args.start if args.start is not None else defaults[args.mode][0]
    end = args.end if args.end is not None else defaults[args.mode][1]
    
    run_tuning(args.scenario, args.mode, args.duration, start, end, args.steps)
