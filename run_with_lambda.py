#!/usr/bin/env python3
"""
Script to run main.py with appropriate lambda values for each case:
- Cases 1,2,3: Use urban_lambda (8.5)
- Cases 4,5,6: Use rural_lambda (2.5)
"""

import sys
import os
from kholo import run_all_scenarios
from simulation.cases import cases

# Hardcoded lambda values from observations/calibrated_stuff.txt
URBAN_LAMBDA = 8.5
RURAL_LAMBDA = 2.5

def get_lambda_for_case(case_arg):
    """Return appropriate lambda value based on case number."""
    if case_arg in ["1", "2", "3"]:
        return URBAN_LAMBDA
    elif case_arg in ["4", "5", "6"]:
        return RURAL_LAMBDA
    else:
        # Default for mixed cases or all cases
        return URBAN_LAMBDA  # Default to urban

def run_scenarios_with_lambda(case_arg=None):
    """Run scenarios with appropriate lambda values."""
    
    if case_arg:
        # Handle specific case
        match case_arg:
            case "1":
                target = cases["case1"]
                lambda_val = get_lambda_for_case("1")
            case "2":
                target = cases["case2"]
                lambda_val = get_lambda_for_case("2")
            case "3":
                target = cases["case3"]
                lambda_val = get_lambda_for_case("3")
            case "4":
                target = cases["case4"]
                lambda_val = get_lambda_for_case("4")
            case "5":
                target = cases["case5"]
                lambda_val = get_lambda_for_case("5")
            case "6":
                target = cases["case6"]
                lambda_val = get_lambda_for_case("6")
            case _:
                print(f"Unknown case: {case_arg}, running all cases...")
                target = [scenario for case_list in cases.values() for scenario in case_list]
                lambda_val = URBAN_LAMBDA  # Default for mixed cases
    else:
        # Run all cases - need to handle mixed environments
        print("Running all cases with appropriate lambda values...")
        
        # Run urban cases (1,2,3) with urban lambda
        urban_scenarios = []
        for case_key in ["case1", "case2", "case3"]:
            urban_scenarios.extend(cases[case_key])
        
        print(f"Running urban scenarios with lambda={URBAN_LAMBDA}")
        run_all_scenarios(urban_scenarios, lambda_val=URBAN_LAMBDA, out_file="results/urban_scenarios_results.csv")
        
        # Run rural cases (4,5,6) with rural lambda
        rural_scenarios = []
        for case_key in ["case4", "case5", "case6"]:
            rural_scenarios.extend(cases[case_key])
        
        print(f"Running rural scenarios with lambda={RURAL_LAMBDA}")
        run_all_scenarios(rural_scenarios, lambda_val=RURAL_LAMBDA, out_file="results/rural_scenarios_results.csv")
        
        return

    # Run single case with appropriate lambda
    print(f"Running case {case_arg} with lambda={lambda_val}")
    run_all_scenarios(target, lambda_val=lambda_val, out_file=f"results/case_{case_arg}_results.csv")

if __name__ == "__main__":
    # Ensure results directory exists
    os.makedirs("results", exist_ok=True)
    
    if len(sys.argv) > 1:
        case_arg = sys.argv[1]
        run_scenarios_with_lambda(case_arg)
    else:
        run_scenarios_with_lambda()
