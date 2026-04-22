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

from simulation import (
    ENVIRONMENT, NUM_SITES, NUM_CELLS,
    PHASE1_DURATION_S, PHASE3_START_S,
    RESULTS_WINDOW_S, SIM_RUNS,
    CONTROL_INTERVAL_S, LAMBDA_ARRIVAL,
    HOTSPOT_RADIUS_M, FAILING_SITE_ID,
    DRONE_ALTITUDE_M,
    ALGO_ENERGY_COST, ALGO_ALPHA, ALGO_EPSILON,
    Network, ShadowFadingService,
    TrafficGenerator, Hotspot, UE,
    RadioEngine, AdmissionController, CSRTracker,
    Drone, DronePositioningAlgorithm, CMType, EnergyAwarePositioningAlgorithm,
    handover
)

# ---------------------------------------------------------------------------
# Event types
# ---------------------------------------------------------------------------
EV_ARRIVAL    = 0
EV_DEPARTURE  = 1
EV_ALGORITHM  = 2   # drone position update tick
EV_DRONE_ACTIVATE = 3  # delayed drone activation
EV_HO_RETRY = 4     # handover retry after 50ms

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
    phase3_start_s: float = PHASE1_DURATION_S,
    drone_delay_s: float = 0.0,
    seed: int = 100,
    lambda_override: Optional[float] = None,
    energy_cost_override: Optional[float] = None,
    alpha_override: Optional[float] = None,
    epsilon_override: Optional[float] = None,
    verbose: bool = False,
) -> Dict:
    """
    Why use this function: Executes a single instance of the multi-phase 
    simulation (Warm-up -> Disaster -> Recovery) for a specific benchmark mode.
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
    elif mode == "energy_algorithm":
        isd = network.isd
        algo = EnergyAwarePositioningAlgorithm(
            drone, network, admission, cm_type=cm_type,
            step_m=1.0,
            x_bounds=(-2 * isd, 2 * isd),
            y_bounds=(-2 * isd, 2 * isd),
            energy_cost=energy_cost_override if energy_cost_override is not None else ALGO_ENERGY_COST,
            alpha=alpha_override if alpha_override is not None else ALGO_ALPHA,
            epsilon=epsilon_override if epsilon_override is not None else ALGO_EPSILON,
        )

    # Output collectors
    csr_series: List[Tuple[float, float]] = []
    trajectory: List[Tuple[float, float, float, float]] = []

    # Track active UEs
    active_ues: Dict[int, UE] = {}
    
    # Track which active UEs are in CSR scope
    csr_active_ues = set()

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
                        active_ues.pop(uid)
                        if uid in csr_active_ues:
                            csr_active_ues.remove(uid)
                            _call_log.append((sim_time, False)) # Mark as failed
                cell.assigned_ues.clear()

            # Activate hotspot
            hotspot.active = True

            # Activate drone (if using) - with delay
            if mode in ("static_drone", "algorithm", "energy_algorithm"):
                fs = network.failing_site()
                # Schedule drone activation after delay
                drone_activation_time = sim_time + drone_delay_s
                push(drone_activation_time, EV_DRONE_ACTIVATE, (fs.x, fs.y))

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
            # RSRP table and CSR scope check
            # -----------------------------------------------------------
            # Populate cache and get current table
            rsrp_tbl = radio.get_optimized_rsrp_table(ue)
            
            # For scope, we look at terrestrial only (pre-incident logic)
            best_preincident = max(ue.terrestrial_rsrp_cache, key=lambda k: ue.terrestrial_rsrp_cache[k])
            in_scope = best_preincident in csr_scope

            if in_scope:
                csr_tracker.record_attempt(sim_time)
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
                        ue.serving_cell_id = selected_cid
                        active_ues[ue.ue_id] = ue
                        csr_active_ues.add(ue.ue_id)
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

            # Schedule next arrival
            push(traffic.next_arrival_time(sim_time), EV_ARRIVAL, None)

        # ==================================================================
        elif ev_type == EV_DEPARTURE:
            uid = payload
            ue = active_ues.pop(uid, None)
            if ue:
                admission.release(ue)
                if uid in csr_active_ues:
                    csr_active_ues.remove(uid)
                    csr_tracker.record_success(sim_time)
                    if disaster_triggered:
                        _call_log.append((sim_time, True))

        # ==================================================================
        elif ev_type == EV_ALGORITHM:
            if drone.active:
                if mode in ("algorithm", "energy_algorithm") and algo is not None:
                    state = algo.step_algorithm()
                    trajectory.append((
                        sim_time,
                        state["x"], state["y"],
                        state.get("cm", 0.0),
                    ))
                    
                # Update loads for CM computation
                admission.update_loads()
                
                # --- Mid-call drop check (Paper §V-D) ---
                # 1. RSRP check (coverage drops)
                for uid in list(active_ues.keys()):
                    ue = active_ues[uid]
                    if ue.serving_cell_id is not None:
                        rsrp_tbl = radio.get_optimized_rsrp_table(ue)
                        rsrp = rsrp_tbl.get(ue.serving_cell_id, -1e9)
                        if rsrp < -120.0:
                            if verbose:
                                print(f"  t={sim_time:.1f}s: UE {uid} DROPPED (Coverage, RSRP={rsrp:.1f} dBm)")
                            admission.release(ue)
                            active_ues.pop(uid)
                            if uid in csr_active_ues:
                                csr_active_ues.remove(uid)
                                if disaster_triggered:
                                    _call_log.append((sim_time, False))

                # 2. Capacity check (Dynamic Dropping / Eviction)
                dropped_ids = admission.rebalance_all_cells(radio, active_ues)
                for uid in dropped_ids:
                    if verbose:
                        print(f"  t={sim_time:.1f}s: UE {uid} DROPPED (Capacity/Eviction)")
                    ue = active_ues.pop(uid, None)
                    if ue:
                        if uid in csr_active_ues:
                            csr_active_ues.remove(uid)
                            if disaster_triggered:
                                _call_log.append((sim_time, False))

                # Process handovers periodically
                algo_event_counter += 1
                if algo_event_counter % 2 == 0:  # Every 800ms
                    failed_hos = handover.process_handovers(sim_time, active_ues, radio, admission)
                    for ue_id, target_cid in failed_hos:
                        # Schedule retry after 50ms
                        push(sim_time + 0.050, EV_HO_RETRY, (ue_id, target_cid))

                push(sim_time + CONTROL_INTERVAL_S, EV_ALGORITHM, None)

        # ==================================================================
        elif ev_type == EV_HO_RETRY:
            ue_id, target_cid = payload
            ue = active_ues.get(ue_id)
            if ue and ue.serving_cell_id is not None:
                # Re-check conditions
                rsrp_tbl = radio.get_optimized_rsrp_table(ue)
                curr_rsrp = rsrp_tbl.get(ue.serving_cell_id, -1e9)
                new_rsrp  = rsrp_tbl.get(target_cid, -1e9)
                
                if new_rsrp >= curr_rsrp + 3.0:
                    sinr = radio.sinr_db(target_cid, ue, rsrp_tbl)
                    req_frac = radio.required_resource_fraction(sinr)
                    
                    old_cid = ue.serving_cell_id
                    admission.release(ue)
                    
                    if admission.try_admit(ue, target_cid, req_frac):
                        ue.serving_cell_id = target_cid
                        if verbose:
                            print(f"  t={sim_time:.1f}s: Handover RETRY SUCCESS for UE {ue_id}")
                    else:
                        # rollback and retry again? 
                        # Paper says "it is repeated after 50 ms provided that the conditions... are still satisfied"
                        # To avoid infinite loop, we could limit retries, but paper implies continued retry.
                        admission.try_admit(ue, old_cid, req_frac)
                        push(sim_time + 0.050, EV_HO_RETRY, (ue_id, target_cid))

        # ==================================================================
        elif ev_type == EV_DRONE_ACTIVATE:
            x, y = payload
            if mode in ("static_drone", "algorithm", "energy_algorithm"):
                drone.activate(x=x, y=y)
                admission._allocations[drone.cell_id] = {}
                push(sim_time + CONTROL_INTERVAL_S, EV_ALGORITHM, None)
                if verbose:
                    print(f"  t={sim_time:.1f}s: Drone ACTIVATED at ({x:.1f},{y:.1f})")

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
        "steps_taken": algo.steps_taken if algo else 0
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
    all_steps = []

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
            seed=100 + run,
            verbose=False,
            lambda_override=lambda_override,
        )
        all_final_csr.append(result["final_csr"])
        all_series.append(result["csr_series"])
        all_traj.extend(result["trajectory"])
        all_steps.append(result["steps_taken"])

    return {
        "mean_csr": float(np.mean(all_final_csr)),
        "std_csr":  float(np.std(all_final_csr)),
        "mean_steps": float(np.mean(all_steps)),
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
        colours = {"no_drone": "#e74c3c", "static_drone": "#f39c12", "algorithm": "#27ae60", "energy_algorithm": "#3498db"}
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
                        default=["no_drone", "static_drone", "algorithm", "energy_algorithm"],
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
