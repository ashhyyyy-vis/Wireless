import sys
import math
import time
import argparse
from multiprocessing import Pool, cpu_count
from .simulation_batch import parse_scenario
from .simulation_core import run_one
from simulation.algorithm import CMType

def _verify_worker(args):
    """Worker function for parallel verification."""
    env, cx, cy, rho, mode, cm, label, total, phase1 = args
    res = run_one(
        env=env,
        hotspot_cx=cx,
        hotspot_cy=cy,
        rho=rho,
        mode=mode,
        cm_type=cm,
        sim_duration_s=total,
        phase2_start_s=phase1,
        seed=100, # Deterministic for verification
        verbose=False
    )
    csr = res["final_csr"]
    steps = res.get("steps_taken", 0)
    return label, csr, steps

def verify_singular(scenario_str: str):
    print("="*60)
    print(f"  VERIFYING SCENARIO: {scenario_str}")
    print("="*60)

    try:
        env, cx, cy, rho = parse_scenario(scenario_str)
    except Exception as e:
        print(f"Error parsing scenario '{scenario_str}': {e}")
        return

    # Simulation settings
    PHASE1 = 15 * 60       # 15 min warm-up
    PHASE3 = 1 * 3600      # 1 h Phase III
    TOTAL  = PHASE1 + PHASE3
    
    # Run Modes
    jobs = [
        ("no_drone", None, "No Drone"),
        ("static_drone", None, "Static Drone"),
    ]
    
    # Add Algorithm modes for all CMs
    for cm in CMType:
        jobs.append(("algorithm", cm, f"Algo ({cm.name})"))

    # Add Energy Aware Algorithm (usually CM7)
    jobs.append(("energy_algorithm", CMType.CM7, "Energy Algo (CM7)"))

    # Prepare task list for multiprocessing
    task_args = []
    for mode, cm, label in jobs:
        task_args.append((env, cx, cy, rho, mode, cm, label, TOTAL, PHASE1))

    results = []
    print(f"Running {len(task_args)} modes in parallel...")
    print("-" * 60)
    
    workers = min(cpu_count(), len(task_args))
    with Pool(workers) as p:
        for label, csr, steps in p.imap(_verify_worker, task_args):
            results.append((label, csr, steps))
            print(f" DONE: {label:<25} | CSR: {csr:.4f} | Steps: {steps}")

    print("\n" + "="*60)
    print(f"{'Label':<25} | {'CSR':<10} | {'Steps':<10}")
    print("-" * 60)
    for label, csr, steps in results:
        print(f"{label:<25} | {csr:<10.4f} | {steps:<10}")
    print("="*60)

def run_verify_scenario(parser: argparse.ArgumentParser):
    parser.add_argument("scenario", help="Scenario string (e.g. DU-100-60-4)")
    args = parser.parse_args()
    
    start = time.time()
    verify_singular(args.scenario)
    end = time.time()
    print(f"Time taken: {end-start:.2f} seconds")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    run_verify_scenario(parser)