"""
Main simulation entry point.

Three-phase workflow (paper Section VIII):
  Phase I  – Steady state with all 12 sites healthy (warm-up).
  Phase II – Disaster: Site 0 fails, traffic hotspot emerges.
  Phase III– Recovery: Drone activates, positioning algorithm runs.

Generates comparison against three benchmarks:
  B0: No drone
  B1: Static drone above failing site
  (B2: Algorithm from [22] – omitted; our CM7 algorithm is the focus)

Outputs (in /results/):
  csr_timeseries.csv    – CSR over time for all modes
  drone_trajectory.csv  – (x, y, cm, time) log
  benchmark_comparison.csv – final CSR per scenario/mode
"""

import os
import math
import heapq
import csv
import time as wall_time
from typing import List, Dict, Optional, Tuple
import numpy as np

from simulation.config import (
    ENVIRONMENT, NUM_SITES, NUM_CELLS,
    PHASE1_DURATION_S, PHASE3_START_S,
    RESULTS_WINDOW_S, SIM_RUNS,
    CONTROL_INTERVAL_S, LAMBDA_ARRIVAL,
    HOTSPOT_RADIUS_M, FAILING_SITE_ID,
    DRONE_ALTITUDE_M,
)
from simulation.network import Network
from simulation.propagation import ShadowFadingService
from simulation.traffic import TrafficGenerator, Hotspot, UE
from simulation.resource import RadioEngine, AdmissionController, CSRTracker
from simulation.drone import Drone
from simulation.algorithm import DronePositioningAlgorithm, CMType
from simulation import handover

# ---------------------------------------------------------------------------
# Event types
# ---------------------------------------------------------------------------
EV_ARRIVAL    = 0
EV_DEPARTURE  = 1
EV_ALGORITHM  = 2   # drone position update tick


# ---------------------------------------------------------------------------
# Single simulation run
# ---------------------------------------------------------------------------

def run_one(
    env: str = ENVIRONMENT,
    hotspot_cx: float = 0.0,
    hotspot_cy: float = 0.0,
    rho: float = 4.0,
    mode: str = "algorithm",   # "no_drone" | "static_drone" | "algorithm"
    cm_type: CMType = CMType.CM7,
    sim_duration_s: float = PHASE1_DURATION_S + 4 * 3600,
    phase2_start_s: float = PHASE1_DURATION_S,
    seed: int = 42,
    lambda_override: Optional[float] = None,
    verbose: bool = False,
) -> Dict:
    """
    Why use this function: Executes a single instance of the multi-phase 
    simulation (Warm-up -> Disaster -> Recovery) for a specific benchmark mode.

    Args:
        env (str): Environment type ("urban" or "rural").
        hotspot_cx (float): Hotspot X center coordinate in meters.
        hotspot_cy (float): Hotspot Y center coordinate in meters.
        rho (float): Traffic density multiplier in the hotspot.
        mode (str): Benchmark mode ("no_drone", "static_drone", or "algorithm").
        cm_type (CMType): Control Metric type used for the positioning algorithm.
        sim_duration_s (float): Total simulation duration in seconds.
        phase2_start_s (float): Time in seconds when the disaster/hotspot triggers.
        seed (int): Random seed for reproducibility.
        lambda_override (Optional[float]): Custom arrival rate to override defaults.
        verbose (bool): Whether to print progress logs during execution.

    Returns:
        Dict: A dictionary containing the CSR time series, drone trajectory, and final averaged CSR.
    """
    rng = np.random.default_rng(seed)

    # Build objects
    network = Network(env=env)
    _lam = lambda_override or LAMBDA_ARRIVAL[env]

    hotspot = Hotspot(cx=hotspot_cx, cy=hotspot_cy, rho=rho, active=False)
    traffic = TrafficGenerator(env=env, hotspot=hotspot, rng=rng,
                               lambda_override=_lam)
    shadow  = ShadowFadingService(num_sites=NUM_SITES, env=env, rng=rng)

    # Drone cell_id = NUM_CELLS (one beyond regular cells)
    drone = Drone(cell_id=NUM_CELLS, active=False)
    drone.assigned_ues = []   # attach list for tracking

    radio    = RadioEngine(network, drone, shadow, env=env)
    admission = AdmissionController(network, drone)
    csr_tracker = CSRTracker()

    # CSR scope: cells to count attempts/successes
    csr_scope = set(network.csr_scope_cell_ids())

    algo: Optional[DronePositioningAlgorithm] = None
    if mode == "algorithm":
        isd = network.isd
        algo = DronePositioningAlgorithm(
            drone, network, admission, cm_type=cm_type,
            step_m=1.0,
            x_bounds=(-2 * isd, 2 * isd),
            y_bounds=(-2 * isd, 2 * isd),
        )

    # Output collectors
    csr_series: List[Tuple[float, float]] = []
    trajectory: List[Tuple[float, float, float, float]] = []

    # Track active UEs
    active_ues: Dict[int, UE] = {}

    # Handover pending: ue_id -> (candidate_cell_id, trigger_time)
    ho_pending: Dict[int, Tuple[int, float]] = {}
    
    # Algorithm event counter for handover frequency control
    algo_event_counter = 0

    # ---------------------------------------------------------------------------
    # Event queue (min-heap): (time, event_type, payload)
    # ---------------------------------------------------------------------------
    events: List[Tuple[float, int, object]] = []

    def push(t, ev_type, payload=None):
        heapq.heappush(events, (t, ev_type, payload))

    # Seed first arrival
    push(traffic.next_arrival_time(0.0), EV_ARRIVAL, None)

    sim_time = 0.0
    last_snapshot = 0.0
    snapshot_interval = 60.0   # CSR snapshot every 60 s

    # Disaster phase flag
    disaster_triggered = False

    # Rolling window for windowed CSR: list of (time, success_bool)
    _call_log: List[Tuple[float, bool]] = []
    WINDOW = 300.0   # 5-minute rolling window (paper Section VIII-B)

    # ---------------------------------------------------------------------------
    # Main event loop
    # ---------------------------------------------------------------------------
    while events:
        sim_time, ev_type, payload = heapq.heappop(events)

        if sim_time > sim_duration_s:
            break

        # ---- Phase II trigger ----
        if sim_time >= phase2_start_s and not disaster_triggered:
            disaster_triggered = True
            if verbose:
                print(f"  [{sim_time:.0f}s] Phase II: site failure + hotspot")

            # Reset CSR tracker so only post-disaster calls are measured
            csr_tracker.reset()
            _call_log.clear()

            # Fail Site 0
            network.fail_site(FAILING_SITE_ID)
            for cell in network.sites[FAILING_SITE_ID].cells:
                # Release all UEs in failed cells
                for uid in list(cell.assigned_ues):
                    ue = active_ues.get(uid)
                    if ue:
                        admission.release(ue)
                cell.assigned_ues.clear()

            # Activate hotspot
            hotspot.active = True

            # Activate drone (if using)
            if mode in ("static_drone", "algorithm"):
                fs = network.failing_site()
                drone.activate(x=fs.x, y=fs.y)
                admission._allocations[drone.cell_id] = {}
                push(sim_time + CONTROL_INTERVAL_S, EV_ALGORITHM, None)

        # ---- Periodic CSR snapshot (5-min rolling window) ----
        if sim_time - last_snapshot >= snapshot_interval and disaster_triggered:
            # Windowed CSR: fraction of calls in last WINDOW seconds that succeeded
            cutoff_w = sim_time - WINDOW
            recent_calls = [(t, s) for t, s in _call_log if t >= cutoff_w]
            if recent_calls:
                w_csr = sum(s for _, s in recent_calls) / len(recent_calls)
            else:
                w_csr = csr_tracker.csr
            csr_series.append((sim_time, w_csr))
            last_snapshot = sim_time
            if verbose:
                print(f"  t={sim_time:.0f}s  CSR(5min)={w_csr:.4f}  "
                      f"drone=({drone.x:.1f},{drone.y:.1f})")

        # ==================================================================
        if ev_type == EV_ARRIVAL:
            ue = traffic.generate_ue(sim_time)

            # -----------------------------------------------------------
            # CSR scope check:
            # A UE is "in scope" if its pre-incident best-server cell
            # belongs to the failing site OR one of its immediate
            # neighbours (the blue + yellow shaded area in Fig 1).
            # We evaluate this using the healthy-network RSRP, i.e. we
            # temporarily include failing-site cells regardless of the
            # disaster state, and find the best unbiased cell.
            # -----------------------------------------------------------
            # Build a full RSRP table ignoring failure state
            full_rsrp: Dict[int, float] = {}
            for cell in network.cells:   # all 36, including failed ones
                full_rsrp[cell.cell_id] = radio.cell_rsrp(cell, ue)
            best_preincident = max(full_rsrp, key=lambda k: full_rsrp[k])
            in_scope = best_preincident in csr_scope

            # Current (possibly post-disaster) RSRP table for actual serving
            rsrp_tbl = radio.rsrp_table(ue)

            if in_scope:
                csr_tracker.attempts += 1
                selected_cid = radio.select_cell(rsrp_tbl)
                if selected_cid is None:
                    # No coverage -> failed call
                    if disaster_triggered:
                        _call_log.append((sim_time, False))
                else:
                    sinr = radio.sinr_db(selected_cid, ue, rsrp_tbl)
                    req_frac = radio.required_resource_fraction(sinr)
                    admitted = admission.try_admit(ue, selected_cid, req_frac)
                    if admitted:
                        csr_tracker.successes += 1
                        if disaster_triggered:
                            _call_log.append((sim_time, True))
                        ue.serving_cell_id = selected_cid
                        active_ues[ue.ue_id] = ue
                        push(ue.departure_time, EV_DEPARTURE, ue.ue_id)
                    else:
                        # Blocked by capacity
                        if disaster_triggered:
                            _call_log.append((sim_time, False))

            elif rsrp_tbl:  # out-of-scope UE: still admit (consume capacity)
                selected_cid = radio.select_cell(rsrp_tbl)
                if selected_cid is not None:
                    sinr = radio.sinr_db(selected_cid, ue, rsrp_tbl)
                    req_frac = radio.required_resource_fraction(sinr)
                    if admission.try_admit(ue, selected_cid, req_frac):
                        ue.serving_cell_id = selected_cid
                        active_ues[ue.ue_id] = ue
                        push(ue.departure_time, EV_DEPARTURE, ue.ue_id)

            # Process handovers for all active UEs
            #handover.process_handovers(sim_time, active_ues, radio, admission)

            # Schedule next arrival
            push(traffic.next_arrival_time(sim_time), EV_ARRIVAL, None)

        # ==================================================================
        elif ev_type == EV_DEPARTURE:
            uid = payload
            ue = active_ues.pop(uid, None)
            if ue:
                admission.release(ue)

        # ==================================================================
        elif ev_type == EV_ALGORITHM:
            if drone.active:
                # Process handovers periodically
                
                if mode == "algorithm" and algo is not None:
                    state = algo.step_algorithm()
                    trajectory.append((
                        sim_time,
                        state["x"], state["y"],
                        state.get("cm", 0.0),
                    ))
                # Update loads for CM computation
                admission.update_loads()
                
                # Process handovers every N algorithm events (reliable timing)
                algo_event_counter += 1
                if algo_event_counter % 25 == 0:  # Every 25 events = every 10 seconds
                    handover.process_handovers(sim_time, active_ues, radio, admission)
                push(sim_time + CONTROL_INTERVAL_S, EV_ALGORITHM, None)

    # ---------------------------------------------------------------------------
    # Compute final CSR: fraction of in-scope calls in the last
    # RESULTS_WINDOW_S that were successful (using the per-call log).
    # ---------------------------------------------------------------------------
    from simulation.config import RESULTS_WINDOW_S as _RW
    cutoff_final = sim_duration_s - _RW
    final_window_calls = [(t, s) for t, s in _call_log if t >= cutoff_final]
    if final_window_calls:
        final_csr = sum(s for _, s in final_window_calls) / len(final_window_calls)
    elif _call_log:
        # Use all post-disaster calls if window not reached yet
        final_csr = sum(s for _, s in _call_log) / len(_call_log)
    elif csr_series:
        final_csr = csr_series[-1][1]
    else:
        final_csr = csr_tracker.csr

    return {
        "csr_series": csr_series,
        "trajectory": trajectory,
        "final_csr":  final_csr,
        "mode":       mode,
        "env":        env,
        "rho":        rho,
        "hotspot_cx": hotspot_cx,
        "hotspot_cy": hotspot_cy,
    }


# ---------------------------------------------------------------------------
# Multi-run averaging
# ---------------------------------------------------------------------------

def run_scenario(
    env: str = ENVIRONMENT,
    hotspot_cx: float = 0.0,
    hotspot_cy: float = 0.0,
    rho: float = 4.0,
    mode: str = "algorithm",
    cm_type: CMType = CMType.CM7,
    n_runs: int = 5,
    verbose: bool = True,
    lambda_override: Optional[float] = None,
) -> Dict:
    """
    Why use this function: Orchestrates multiple simulation runs (Monte Carlo trials) 
    for a specific scenario and computes the mean and standard deviation of the CSR.

    Args:
        env (str): Environment type.
        hotspot_cx (float): Hotspot X coordinate.
        hotspot_cy (float): Hotspot Y coordinate.
        rho (float): Hotspot traffic intensity ρ.
        mode (str): Benchmark mode.
        cm_type (CMType): Control Metric used.
        n_runs (int): Number of runs to average.
        verbose (bool): Whether to log progress.
        lambda_override (Optional[float]): Custom arrival rate parameter.

    Returns:
        Dict: Aggregated results data with mean/std CSR and trajectory logs.
    """
    all_final_csr = []
    all_series = []
    all_traj = []

    for run in range(n_runs):
        if verbose:
            print(f"  Run {run+1}/{n_runs} ...")
        result = run_one(
            env=env,
            hotspot_cx=hotspot_cx,
            hotspot_cy=hotspot_cy,
            rho=rho,
            mode=mode,
            cm_type=cm_type,
            seed=42 + run,
            verbose=False,
            lambda_override=lambda_override,
        )
        all_final_csr.append(result["final_csr"])
        all_series.append(result["csr_series"])
        all_traj.extend(result["trajectory"])

    return {
        "mean_csr": float(np.mean(all_final_csr)),
        "std_csr":  float(np.std(all_final_csr)),
        "all_final_csr": all_final_csr,
        "trajectory": all_traj,
        "env": env, "rho": rho, "mode": mode,
        "hotspot_cx": hotspot_cx, "hotspot_cy": hotspot_cy,
    }


# ---------------------------------------------------------------------------
# Results I/O
# ---------------------------------------------------------------------------

def save_results(results: List[Dict], out_dir: str = "results") -> None:
    """
    Why use this function: Exports the simulation benchmark results to a CSV file for post-analysis.

    Args:
        results (List[Dict]): List of scenario results.
        out_dir (str): Relative directory path to save files. Defaults to "results".

    Returns:
        None
    """
    os.makedirs(out_dir, exist_ok=True)

    csv_path = os.path.join(out_dir, "benchmark_comparison.csv")
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "env", "rho", "hotspot_cx", "hotspot_cy",
            "mode", "mean_csr", "std_csr",
        ])
        writer.writeheader()
        for r in results:
            writer.writerow({
                "env":        r["env"],
                "rho":        r["rho"],
                "hotspot_cx": r["hotspot_cx"],
                "hotspot_cy": r["hotspot_cy"],
                "mode":       r["mode"],
                "mean_csr":   f"{r['mean_csr']:.4f}",
                "std_csr":    f"{r['std_csr']:.4f}",
            })
    print(f"Saved benchmark comparison -> {csv_path}")


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------

def plot_results(results: List[Dict], out_dir: str = "results") -> None:
    """
    Why use this function: Generates comparison bar charts showing the CSR performance 
    across different benchmark modes for each scenario.

    Args:
        results (List[Dict]): List of scenario results.
        out_dir (str): Directory where plots should be saved.

    Returns:
        None
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not available, skipping plots.")
        return

    os.makedirs(out_dir, exist_ok=True)

    # Group by (env, rho, hotspot)
    groups: Dict[str, List] = {}
    for r in results:
        key = f"{r['env']}-rho{r['rho']}-hs({r['hotspot_cx']:.0f},{r['hotspot_cy']:.0f})"
        groups.setdefault(key, []).append(r)

    for label, grp in groups.items():
        fig, ax = plt.subplots(figsize=(8, 4))
        colours = {"no_drone": "#e74c3c", "static_drone": "#f39c12", "algorithm": "#27ae60"}
        for r in grp:
            ax.bar(r["mode"], r["mean_csr"],
                   yerr=r["std_csr"], color=colours.get(r["mode"], "grey"),
                   capsize=4, alpha=0.85, label=r["mode"])
        ax.set_ylim(0, 1.05)
        ax.set_ylabel("Mean CSR")
        ax.set_title(f"CSR Benchmark - {label}")
        ax.legend()
        fig.tight_layout()
        path = os.path.join(out_dir, f"csr_{label}.png")
        fig.savefig(path, dpi=120)
        plt.close(fig)
        print(f"Plot saved -> {path}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Drone-BS Positioning Simulation (Pijnappel et al. 2024)"
    )
    parser.add_argument("--env",    default="urban", choices=["urban", "rural"])
    parser.add_argument("--rho",    type=float, default=4.0,
                        help="Hotspot traffic multiplier (2/4/8 urban, 10/25/50 rural)")
    parser.add_argument("--hs_x",  type=float, default=100.0,
                        help="Hotspot centre x offset from failing site (m)")
    parser.add_argument("--hs_y",  type=float, default=100.0,
                        help="Hotspot centre y offset from failing site (m)")
    parser.add_argument("--runs",   type=int,   default=3,
                        help="Number of simulation runs to average (25 for paper accuracy)")
    parser.add_argument("--lambda_", type=float, default=None,
                        help="Override arrival rate λ (calls/s)")
    parser.add_argument("--modes",  nargs="+",
                        default=["no_drone", "static_drone", "algorithm"],
                        help="Which benchmark modes to run")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    print("=" * 60)
    print(f"  Simulation: env={args.env}, rho={args.rho}, "
          f"hotspot=({args.hs_x:.0f},{args.hs_y:.0f}), runs={args.runs}")
    print("=" * 60)

    all_results = []
    t0 = wall_time.time()

    for mode in args.modes:
        print(f"\n>> Mode: {mode}")
        result = run_scenario(
            env=args.env,
            hotspot_cx=args.hs_x,
            hotspot_cy=args.hs_y,
            rho=args.rho,
            mode=mode,
            cm_type=CMType.CM7,
            n_runs=args.runs,
            verbose=args.verbose,
            lambda_override=args.lambda_,
        )
        all_results.append(result)
        print(f"  CSR = {result['mean_csr']:.4f} +/- {result['std_csr']:.4f}")

    elapsed = wall_time.time() - t0
    print(f"\nTotal wall time: {elapsed:.1f}s")

    save_results(all_results)
    plot_results(all_results)

    print("\nDone. Results in ./results/")
