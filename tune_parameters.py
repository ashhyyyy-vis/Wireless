import os
import sys
import argparse
import numpy as np

# Add current directory to path
sys.path.append(os.getcwd())

from run_simulation import run_one
from simulation.config import LAMBDA_ARRIVAL, ALGO_EPSILON
from simulation.algorithm import CMType
from kholo import parse_scenario

def tune_alpha(scenario, duration, a_start, a_end, a_steps):
    env, cx, cy, rho = parse_scenario(scenario)
    config_lambda = LAMBDA_ARRIVAL[env]
    print(f"\n>>> Tuning Alpha (Scenario={scenario}, Environment={env}, Lambda={config_lambda}, Epsilon=0.0, Duration={duration}s)")
    print("-" * 65)
    print(f"{'Alpha':<15} | {'Energy Algo CSR':<18} | {'Legacy Algo CSR':<18}")
    print("-" * 65)
    
    alphas = np.linspace(a_start, a_end, a_steps)
    best_csr = -1
    best_val = None
    
    best_legacy_csr = 0
    
    # We will use a short warm-up (30s) and then the defined duration for the disaster phase
    phase1 = 30.0
    total_duration = phase1 + duration

    for a in alphas:
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
            lambda_override=config_lambda,
            seed=100,
            verbose=False
        )
        legacy_csr = res_legacy['final_csr']
        
        # Run energy algorithm
        res = run_one(
            env=env,
            hotspot_cx=cx,
            hotspot_cy=cy,
            rho=rho,
            mode="energy_algorithm",
            sim_duration_s=total_duration,
            phase2_start_s=phase1,
            phase3_start_s=phase1,
            lambda_override=config_lambda,
            alpha_override=float(a),
            epsilon_override=0.0,
            seed=100,
            verbose=False
        )
        csr = res['final_csr']
        print(f"{a:<15.4f} | {csr:<18.4f} | {legacy_csr:<18.4f}")
        
        if csr > best_csr:
            best_csr = csr
            best_val = a
            best_legacy_csr = legacy_csr
            
    print("-" * 65)
    print(f"Best Alpha: {best_val:.4f} with Max CSR: {best_csr:.4f}")
    
    # Check drop against legacy algorithm
    if best_legacy_csr - best_csr > 0.05:
        print(f"\n[!] WARNING: The maximum CSR ({best_csr:.4f}) dropped significantly compared to the legacy algorithm ({best_legacy_csr:.4f})!")
    else:
        print(f"Check Passed! Energy-aware performance is close to or better than legacy ({best_legacy_csr:.4f}).")

def tune_epsilon(scenario, duration, e_start, e_end, e_steps):
    env, cx, cy, rho = parse_scenario(scenario)
    config_lambda = LAMBDA_ARRIVAL[env]
    print(f"\n>>> Tuning Epsilon (Scenario={scenario}, Environment={env}, Lambda={config_lambda}, Duration={duration}s)")
    print("-" * 65)
    print(f"{'Epsilon':<15} | {'Energy Algo CSR':<18} | {'Legacy Algo CSR':<18}")
    print("-" * 65)
    
    epsilons = np.linspace(e_start, e_end, e_steps)
    best_csr = -1
    best_val = None
    
    best_legacy_csr = 0
    
    # We will use a short warm-up (30s) and then the defined duration for the disaster phase
    phase1 = 30.0
    total_duration = phase1 + duration

    for e in epsilons:
        # Run legacy algorithm (Should remain constant across epsilons since we fixed lambda)
        res_legacy = run_one(
            env=env,
            hotspot_cx=cx,
            hotspot_cy=cy,
            rho=rho,
            mode="algorithm",
            sim_duration_s=total_duration,
            phase2_start_s=phase1,
            phase3_start_s=phase1,
            lambda_override=config_lambda,
            seed=100,
            verbose=False
        )
        legacy_csr = res_legacy['final_csr']

        # Run energy algorithm
        res = run_one(
            env=env,
            hotspot_cx=cx,
            hotspot_cy=cy,
            rho=rho,
            mode="energy_algorithm",
            sim_duration_s=total_duration,
            phase2_start_s=phase1,
            phase3_start_s=phase1,
            lambda_override=config_lambda,
            epsilon_override=float(e),
            seed=100,
            verbose=False
        )
        csr = res['final_csr']
        print(f"{e:<15.6f} | {csr:<18.4f} | {legacy_csr:<18.4f}")
        
        if csr > best_csr:
            best_csr = csr
            best_val = e
            best_legacy_csr = legacy_csr
            
    print("-" * 65)
    print(f"Best Epsilon: {best_val:.6f} with Max CSR: {best_csr:.4f}")
    
    # Check drop against legacy algorithm
    if best_legacy_csr - best_csr > 0.05:
        print(f"\n[!] WARNING: The maximum CSR ({best_csr:.4f}) dropped significantly compared to the legacy algorithm ({best_legacy_csr:.4f})!")
    else:
        print(f"Check Passed! Energy-aware performance is close to or better than legacy ({best_legacy_csr:.4f}).")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Tuning script for Drone Positioning Algorithm")
    parser.add_argument("--scenario", required=True, help="Scenario identifier (e.g., DU-100-60-4)")
    parser.add_argument("--mode", choices=["alpha", "epsilon"], required=True, help="Tuning mode")
    parser.add_argument("--duration", type=float, default=1800.0, help="Simulation duration (seconds)")
    
    # Alpha range
    parser.add_argument("--a_start", type=float, default=0.5, help="Start value for alpha")
    parser.add_argument("--a_end", type=float, default=5.0, help="End value for alpha")
    parser.add_argument("--a_steps", type=int, default=5, help="Number of steps for alpha")
    
    # Epsilon range
    parser.add_argument("--e_start", type=float, default=0.0, help="Start value for epsilon")
    parser.add_argument("--e_end", type=float, default=0.005, help="End value for epsilon")
    parser.add_argument("--e_steps", type=int, default=5, help="Number of steps for epsilon")
    
    args = parser.parse_args()
    
    if args.mode == "alpha":
        tune_alpha(args.scenario, args.duration, args.a_start, args.a_end, args.a_steps)
    else:
        tune_epsilon(args.scenario, args.duration, args.e_start, args.e_end, args.e_steps)
