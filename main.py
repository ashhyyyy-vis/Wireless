import sys
from kholo import run_all_scenarios
from simulation.cases import cases

if __name__ == "__main__":
    # If an argument is provided, get that specific case; 
    # otherwise, take all values from the cases dictionary.
    if len(sys.argv) > 1:
        target = [cases[sys.argv[1]]]
    else:
        target = list(cases.values())
    
    run_all_scenarios(target)