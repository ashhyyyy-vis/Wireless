# TODO: Alignment with Research Paper Implementation

This document outlines the gaps between the current codebase and the theoretical models/simulations described in the research paper **"Online Positioning of a Drone-Mounted Base Station in Emergency Scenarios"**. Implementing these items will bring the simulation results closer to the paper's original findings.

## 1. Dynamic Resource Management & UE Dropping [DONE]
*   **Paper Specification:** If drone movement increases resource requirements beyond 100% capacity, the system should drop the "hungriest" UEs to maintain stability.
*   **Implementation:** `AdmissionController.rebalance_all_cells` now re-evaluates all active UEs every 400ms. It uses optimized RSRP caching to maintain performance and evicts users based on resource demand (highest requirement dropped first) to keep cell load ≤ 100%.


## 2. Inter-Site Shadow Fading Correlation [DONE]
*   **Paper Specification:** Shadow fading should be correlated between different base station sites with a correlation factor $\omega = 0.5$.
*   **Implementation:** `ShadowFadingService` has been updated to implement the Fraile et al. model. It now combines a `_common_map` with site-specific `_site_maps` using $\sqrt{\omega}$ and $\sqrt{1-\omega}$ weights to ensure inter-site correlation.


## 3. Stochastic LoS/NLoS State Sampling [DONE]
*   **Paper Specification:** Link quality should be sampled probabilistically for LoS or NLoS states.
*   **Implementation:** `drone_path_loss` and `bs_path_loss` now perform discrete sampling based on the $p_{LoS}$ probability. This introduces realistic signal variance and "flickering," ensuring the simulation captures sudden signal drops that impact CSR.


## 4. Enhanced CSR Tracking (Mid-Call Drops) [DONE]
*   **Paper Specification:** Call Success Rate (CSR) is defined by calls that have coverage, are admitted, **are not dropped**, and receive the minimum bitrate for their **entire duration**.
*   **Implementation:** `CSRTracker` now separates initiation from completion. Calls are only recorded as successful at `EV_DEPARTURE`. A mid-call signal quality check has been added to `run_simulation.py` that drops UEs if RSRP falls below -120 dBm or if they are evicted by the dynamic scheduler.

## 5. Handover Retry Logic [DONE]
*   **Paper Specification:** The paper states: "Whenever a handover request is denied, it is repeated after 50 ms provided that the conditions triggering the handover are still satisfied."
*   **Implementation:** Handover failures are now returned to the event loop, which schedules an `EV_HO_RETRY` event for 50ms later. The retry logic re-verifies signal conditions before attempting re-admission.

---

## 6. Wireless Backhaul Modeling (Optional)
*   **Paper Specification:** The drone is wirelessly backhauled on a separate frequency band, implying finite backhaul capacity and link quality constraints.
*   **Current Implementation:** The codebase currently assumes an **Ideal Backhaul** with infinite capacity and no latency.
*   **Task:** Introduce a backhaul capacity limit in `config.py` and enforce it within the `AdmissionController` for all UEs served by the drone.

## 7. Systematic Scenario Validation (Optional)
*   **Paper Specification:** The paper evaluates performance across 44 specific scenarios (Urban/Rural, various hotspot distances, angles, and intensities).
*   **Current Implementation:** While the tools to create these scenarios exist, there is no automated suite to run and aggregate results for the full set of 44 scenarios.
*   **Task:** Create a standardized configuration generator in `simulation/cases.py` that maps exactly to the 44 scenarios in the paper and a runner script to execute the full evaluation suite.
