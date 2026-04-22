# Codebase Documentation: Drone-BS Positioning Simulation

This document provides a comprehensive technical overview of the `choice_scarf` project. It describes the architecture, mathematical models, and implementation details of the simulation environment used to research drone-mounted base station positioning in emergency scenarios.

---

## 1. System Architecture
The project is built as a **Discrete Event Simulation (DES)**. It models a cellular network where events (User arrivals, departures, and algorithm ticks) drive the state of the system over time.

### Core Workflow: The Three Phases
1.  **Phase I (Steady State)**: A healthy 7-site cluster operates normally. Users arrive and depart to "warm up" the network and establish baseline Call Success Rate (CSR).
2.  **Phase II (Disaster)**: The central site (Site 0) is disabled, and a traffic hotspot emerges near the failed area. CSR drops significantly.
3.  **Phase III (Recovery)**: A drone-mounted base station activates and uses an "online" positioning algorithm to navigate toward the hotspot and restore service.

---

## 2. Simulation Engine Modules (`simulation/`)

### 2.1. Network Topology (`network.py`)
- **Rhombus Boundary**: Implements a periodic cluster of 7 sites (each with 3 sectors).
- **Wraparound Logic**: Distances are calculated using a 3D hexagonal wraparound to simulate an infinite network without edge effects.
- **Site/Cell Objects**: Manages the state of base stations, including their coordinates, boresight angles, and active/failed status.

### 2.2. Radio Propagation (`propagation.py`)
- **Path Loss Model**: Implements the Al-Hourani model for air-to-ground links, calculating the probability of Line-of-Sight (LoS) based on environment constants ($\alpha, \beta, \gamma$).
- **Antenna Gain**: Implements 3D gain patterns for both ground base stations (3GPP model with electrical downtilt) and the drone (omnidirectional with attenuation).
- **Shadow Fading**: Uses the Fraile model to generate spatially correlated shadow fading using a decorrelation distance.

### 2.3. Traffic & UE Management (`traffic.py`)
- **Poisson Process**: Users are generated using an exponential inter-arrival time distribution.
- **Hotspot Logic**: Arrival rates are scaled by a multiplier ($\rho$) within a 100m radius of the hotspot center.
- **UE Object**: Tracks user position, serving cell, bitrate requirements, and simulation timing.

### 2.4. Resource Management (`resource.py`)
- **RadioEngine**: Calculates RSRP, SINR, and the required resource block (RB) fraction for each user.
- **AdmissionController**: Manages the capacity of each cell. A call is admitted only if sufficient RBs are available (Total capacity = 1.0).
- **CSRTracker**: Monitors the ratio of admitted calls to total attempts within the "impact area" (failing site + neighbors).

### 2.5. Handover Logic (`handover.py`)
- Implements **A3-event based handover** with Hysteresis and Time-to-Trigger (TTT).
- Users periodically check if a neighboring cell (including the drone) provides a better signal.

---

## 3. Positioning Algorithms (`algorithm.py`)

### 3.1. Standard Online Algorithm
A gradient-free optimization that navigates the drone by minimizing a **Control Metric (CM)**.
- **Movement**: 1-meter steps in X or Y.
- **Logic**: If the CM improves, the drone continues in the same direction. If it degrades, it reverses. If it degrades again after reversing, it switches axes.

### 3.2. Energy-Aware Variant
Modifies the standard algorithm to conserve drone energy.
- **Gating**: The drone only moves if the improvement in CM exceeds a threshold: `Gain > (Alpha * Energy_Cost + Epsilon)`.
- **Termination**: If the drone fails to find an improvement after checking both directions on both axes, it stops moving.

### 3.3. Control Metrics (CM1–CM7)
The objective functions used to guide the drone:
- **CM1**: Drone Load.
- **CM2**: Load of the most loaded neighboring cell.
- **CM7 (Primary)**: A weighted average load per UE between the drone and the most loaded neighbor, prioritizing service for areas with the highest user density.

---

## 4. Execution & Analysis Layer

### 4.1. Core Runner (`run_simulation.py`)
- Contains `run_one()`: The central function that executes a single multi-phase simulation run.
- Manages the event queue and state transitions.

### 4.2. Batch Processing (`kholo.py` & `main.py`)
- **`kholo.py`**: A parallel processing wrapper that runs multiple scenarios and trials simultaneously using `multiprocessing`.
- **`main.py`**: The entry point for the "Full Research Battery," mapping scenario IDs (e.g., `DU-100-60-4`) to execution jobs.

### 4.3. Analysis Scripts
- **`calibrate.py`**: Iteratively runs simulations to find the correct `LAMBDA_ARRIVAL` for an environment to hit target CSR benchmarks.
- **`run_convergence.py`**: Specifically measures the time taken for the positioning algorithm to stabilize.
- **`run_energy_comparison.py`**: Compares the standard algorithm vs the energy-aware one in terms of `steps_taken` and final `CSR`.

---

## 5. Configuration (`simulation/config.py`)
All physical and simulation constants are centralized here:
- **Environment Params**: ISD (500m/3500m), Carrier Freq (3.5GHz), Bandwidth (5MHz).
- **Algorithm Params**: Step size (1m), Control Interval (400ms), Energy constants.
- **Default Targets**: Calibrated lambda values for Urban and Rural scenarios.

---

## 6. Data Schema
- **Scenario ID Format**: `[ENV]-[DIST]-[PHI]-[RHO]`
    - `ENV`: DU (Urban) or RU (Rural)
    - `DIST`: Hotspot distance from center
    - `PHI`: Hotspot angle
    - `RHO`: Traffic intensity multiplier
