import argparse
from .kholo import run_all_scenarios
from simulation.cases import cases
import time

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run simulation scenarios.")
    parser.add_argument("case", nargs="?", default="all", help="Case number (1-6) or 'all'")
    parser.add_argument("--energy", action="store_true", help="Include energy-aware CM7 in results")
    parser.add_argument("--runs", type=int, default=5, help="Number of runs per scenario")
    parser.add_argument("--out", default="results/all_scenarios_results.csv", help="Output CSV path")
    
    args = parser.parse_args()

    if args.case != "all":
        case_key = f"case{args.case}"
        if case_key in cases:
            target = cases[case_key]
        else:
            print(f"Unknown case: {args.case}, running all cases...")
            target = [scenario for case_list in cases.values() for scenario in case_list]
    else:
        target = [scenario for case_list in cases.values() for scenario in case_list]
    start=time.time()
    run_all_scenarios(
        target, 
        out_file=args.out, 
        n_runs=args.runs, 
        include_energy=args.energy
    )
    end=time.time()
    print(f"Total time taken: {end-start} seconds")