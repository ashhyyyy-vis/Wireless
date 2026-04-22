import sys
import math
from .kholo import parse_scenario
from . import run_one
from simulation.algorithm import CMType

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

    results = []
    
    for mode, cm, label in jobs:
        print(f"Running {label}...", end="", flush=True)
        res = run_one(
            env=env,
            hotspot_cx=cx,
            hotspot_cy=cy,
            rho=rho,
            mode=mode,
            cm_type=cm,
            sim_duration_s=TOTAL,
            phase2_start_s=PHASE1,
            seed=42, # Deterministic for verification
            verbose=False
        )
        csr = res["final_csr"]
        steps = res.get("steps_taken", 0)
        results.append((label, csr, steps))
        print(f" DONE (CSR: {csr:.4f}, Steps: {steps})")

    print("\n" + "="*60)
    print(f"{'Label':<25} | {'CSR':<10} | {'Steps':<10}")
    print("-" * 60)
    for label, csr, steps in results:
        print(f"{label:<25} | {csr:<10.4f} | {steps:<10}")
    print("="*60)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 -m runners.verify_scenario <scenario_string>")
        print("Example: python3 -m runners.verify_scenario DU-100-60-4")
    else:
        verify_singular(sys.argv[1])
