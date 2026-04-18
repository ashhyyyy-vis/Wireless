import sys
from kholo import run_all_scenarios
from simulation.cases import cases

if __name__ == "__main__":
    if len(sys.argv) > 1:
        case_arg = sys.argv[1]
        match case_arg:
            case "1":
                target = cases["case1"]  # Direct assignment (no extra list wrapping)
            case "2":
                target = cases["case2"]
            case "3":
                target = cases["case3"]
            case "4":
                target = cases["case4"]
            case "5":
                target = cases["case5"]
            case "6":
                target = cases["case6"]
            case _:
                print(f"Unknown case: {case_arg}, running all cases...")
                # Flatten all case lists into one flat list
                target = [scenario for case_list in cases.values() for scenario in case_list]
    else:
        # Flatten all case lists into one flat list
        target = [scenario for case_list in cases.values() for scenario in case_list]

    run_all_scenarios(target)