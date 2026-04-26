import argparse
from .simulation_batch import run_all_scenarios
from simulation.cases import cases
import time

def run_metric_comparison(parser: argparse.ArgumentParser):
    parser.add_argument("case", nargs="?", default="all", help="Case number (1-6) or 'all'")
    parser.add_argument("--energy", action="store_true", help="Include energy-aware CM7 in results")
    parser.add_argument("--runs", type=int, default=5, help="Number of runs per scenario")
    parser.add_argument("--out", default="results/all_scenarios_results.csv", help="Output CSV path")
    parser.add_argument("--duration", type=float, default=5400.0, help="Total simulation duration (s)")
    parser.add_argument("--warmup", type=float, default=None, help="Warmup duration (s). Defaults to 1/3 of duration.")
    
    args = parser.parse_args()
    
    warmup = args.warmup if args.warmup is not None else args.duration / 3.0
    active_phase = args.duration - warmup

    if args.case != "all":
        case_key = f"case{args.case}"
        if case_key in cases:
            target = cases[case_key]
        else:
            print(f"Unknown case: {args.case}, running all cases...")
            target = [scenario for case_list in cases.values() for scenario in case_list]
    else:
        target = [scenario for case_list in cases.values() for scenario in case_list]
    
    start = time.time()
    run_all_scenarios(
        target, 
        out_file=args.out, 
        n_runs=args.runs, 
        include_energy=args.energy,
        phase1=warmup,
        phase3=active_phase
    )
    end = time.time()
    print(f"Total time taken: {end-start:.2f} seconds")