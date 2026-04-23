import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Choice Scarf Simulation Runner")
    parser.add_argument("--experiment", type=int, required=True, 
                        help="Experiment number:\n"
                             "1: Metric comparison\n"
                             "2: Convergence analysis (legacy)\n"
                             "3: Energy gains on proposed algo\n"
                             "4: Convergence on energy aware algo")
    
    # We use parse_known_args so that sub-commands can define their own arguments
    args, unknown = parser.parse_known_args()
    
    match args.experiment:
        case 1:
            from .experiment_metrics import run_metric_comparison
            run_metric_comparison(parser)
        case 2:
            from .experiment_convergence import run_convergence_analysis
            run_convergence_analysis(parser)
        case 3:
            from .experiment_energy import compare_energy_aware
            # Case 3 has its own arg parsing logic if needed, but we can just use defaults or add more
            parser.add_argument("--runs", type=int, default=3)
            parser.add_argument("--scenarios", nargs="+")
            args = parser.parse_args()
            compare_energy_aware(scenarios=args.scenarios, n_runs=args.runs)
        case 4:
            from .experiment_convergence import run_convergence_analysis
            # For case 4, we want to force mode="energy_algorithm"
            # We can either modify the parser or just pass it through
            # Let's just use the same analysis but default to energy_algorithm
            # Actually, let's just use run_convergence_analysis and let the user specify --mode
            # or we can hardcode it here.
            import sys
            if "--mode" not in sys.argv:
                sys.argv.extend(["--mode", "energy_algorithm"])
            run_convergence_analysis(parser)
        case _:
            print("Invalid experiment number")
            exit(1)
