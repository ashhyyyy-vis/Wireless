import argparse
import sys

def main():
    parser = argparse.ArgumentParser(description="Choice Scarf Tools Dispatcher")
    parser.add_argument("--tool", type=int, required=True,
                        help="Tool number:\n"
                             "1: Verify Scenario\n"
                             "2: Metric Comparison (Single Scenario)\n"
                             "3: Parameter Tuning\n"
                             "4: Lambda Calibration (Urban/General)\n"
                             "5: Lambda Calibration (Rural)\n"
                             "6: Lambda Calibration (No-Drone Baseline)\n"
                             "7: Diagnostics (SINR/Admission)\n"
                             "8: Diagnostics (Signal Strength Map)")
    
    # We use parse_known_args so that sub-commands can define their own arguments
    args, unknown = parser.parse_known_args()
    
    match args.tool:
        case 1:
            from runners.scenario_tester import run_verify_scenario
            run_verify_scenario(parser)
        case 2:
            from .metric_comp import run_metric_comp
            run_metric_comp(parser)
        case 3:
            from .tune_parameters import run_tune_parameters
            run_tune_parameters(parser)
        case 4:
            from .calibrate import run_calibrate
            run_calibrate(parser)
        case 5:
            from .calibrate_rural import run_calibrate_rural
            run_calibrate_rural(parser)
        case 6:
            from .calibrate_no_drone import run_calibrate_no_drone
            run_calibrate_no_drone(parser)
        case 7:
            from .diag import run_diag
            run_diag(parser)
        case 8:
            from .diag2 import run_diag2
            run_diag2(parser)
        case _:
            print("Invalid tool number")
            sys.exit(1)

if __name__ == "__main__":
    main()
