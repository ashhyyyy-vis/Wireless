# Drone-BS Online Positioning Simulation: Usage Instructions

This document explains how to use the various scripts provided in the `choice_scarf` project.
Note: Since the project is now structured as a package, all scripts should be run from the **project root** using the `-m` (module) flag.

---

## 1. Universal Dispatcher (`runners/entry.py`)
  This is the primary entry point for running all major simulation experiments. It uses an `--experiment` flag to decide which research module to run.

  ### Experiment 1: Metric Comparison (Full Research Battery)
  Runs the complete set of scenarios (48 total) or a specific case (1-6) defined in the research paper.
  * **Run a specific Case** (1-6):
    ```bash
    python3 -m runners.entry --experiment 1 <case_number>
    # Example: python3 -m runners.entry --experiment 1 2
    ```
  * **Run all scenarios**:
    ```bash
    python3 -m runners.entry --experiment 1
    ```
  * **Output**: Aggregated CSR results are saved to `results/all_scenarios_results.csv`.

  ### Experiment 2: Convergence Analysis (Legacy)
  Analyzes how CSR stabilizes over time for a specific scenario using the legacy algorithm.
  * **Usage**:
    ```bash
    python3 -m runners.entry --experiment 2 --scenario <ID> --runs <n>
    # Example: python3 -m runners.entry --experiment 2 --scenario DU-100-60-4 --runs 5
    ```
  * **Output**: Time-series CSV in `results/convergence_algorithm_<scenario>.csv`.

  ### Experiment 3: Energy Gains Comparison
  Evaluates efficiency gains (steps saved) and CSR impact of the energy-aware algorithm vs legacy across multiple representative scenarios.
  * **Usage**:
    ```bash
    python3 -m runners.entry --experiment 3 --runs <n> [--scenarios <ID1> <ID2>...]
    # Example: python3 -m runners.entry --experiment 3 --runs 3
    ```
  * **Output**: Comparative report in `results/energy_comparison_report.csv`.

  ### Experiment 4: Convergence on Energy-Aware Algorithm
  Analyzes stabilization for a specific scenario using the energy-aware algorithm.
  * **Usage**:
    ```bash
    python3 -m runners.entry --experiment 4 --scenario <ID> --runs <n>
    # Example: python3 -m runners.entry --experiment 4 --scenario DU-100-60-4 --runs 5
    ```
  * **Output**: Time-series CSV in `results/convergence_energy_algorithm_<scenario>.csv`.

  ---

## 2. Universal Tools Dispatcher (`tools/main.py`)
Provides a centralized way to access various utility and diagnostic tools.

  ### Tool 1: Verify Scenario
  Performs a deep verification of a single scenario across all modes (including all 7 CMs).
  * **Usage**:
    ```bash
    python3 -m tools.main --tool 1 <scenario_ID>
    # Example: python3 -m tools.main --tool 1 DU-100-60-4
    ```

  ### Tool 2: Single Scenario Metric Comparison
  Compares all 7 Control Metrics (CM1-CM7) against baselines for any arbitrary scenario ID.
  * **Usage**:
    ```bash
    python3 -m tools.main --tool 2 --scenario <ID> --runs <n>
    # Example: python3 -m tools.main --tool 2 --scenario DU-100-60-4 --runs 5
    ```

  ### Tool 3: Parameter Tuning
  Finds optimal values for Alpha, Epsilon, or Lambda via parameter sweeps.
  * **Usage**:
    ```bash
    python3 -m tools.main --tool 3 --scenario <ID> --mode [alpha|epsilon|lambda] --start <val> --end <val> --steps <n>
    ```

  ### Tool 4-6: Lambda Calibration
  Finds the arrival rate (Lambda) for different environments.
  * **Urban (Tool 4)**: `python3 -m tools.main --tool 4`
  * **Rural (Tool 5)**: `python3 -m tools.main --tool 5`
  * **No-Drone Baseline (Tool 6)**: `python3 -m tools.main --tool 6 --scenario <ID>`

  ### Tool 7-8: Diagnostics
  * **Admission/SINR (Tool 7)**: `python3 -m tools.main --tool 7`
  * **Scope/Signal Map (Tool 8)**: `python3 -m tools.main --tool 8`

  ---

## 3. Diagnostics and Validation
* **Quick Validation**: `python3 -m tests.validate`
* **Core Algorithm Test**: `python3 -m tests.validate_cm`

---

## Common Arguments & Defaults
- **Seed**: All scripts are standardized to use a base seed of `100`.
- **Lambda**: Scripts default to the values in `simulation/config.py` unless overridden by `--lambda_`.
- **Results**: All output data is stored in the `./results/` directory.
