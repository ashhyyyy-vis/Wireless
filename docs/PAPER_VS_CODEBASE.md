# Comparison: Research Paper vs. Implementation

This document compares the theoretical models presented in the research paper (**"Online Positioning of a Drone-Mounted Base Station in Emergency Scenarios"**) with the logic implemented in this codebase.

---

## 1. Positioning Algorithm & Control Parameters

### Paper Specification
The paper identifies four control parameters for the drone base station:
1.  **Horizontal Position ($x, y$)**
2.  **Altitude ($z$)**
3.  **Cell Individual Offset ($CIO$)** — used to steer traffic.

### Code Implementation
**Simplification**: The codebase focuses exclusively on the **2D Horizontal Position ($x, y$)**.
- **Reasoning**: Section VI-D of the paper concludes that Altitude and $CIO$ have a negligible impact on the Call Success Rate (CSR) once a minimum threshold is met.
- **Result**: `DRONE_ALTITUDE_M` is fixed at **120m** and `DRONE_CIO_DB` is fixed at **0dB** in `simulation/config.py`.

---

## 2. Radio Propagation & Fading

### Paper Specification
- **Site Correlation**: Shadow fading should be correlated between different base station sites ($\omega = 0.5$).
- **State Sampling**: Users should be probabilistically assigned a Line-of-Sight (LoS) or Non-Line-of-Sight (NLoS) state.

### Code Implementation
- **Simplification (Site Correlation)**: Shadow fading maps are spatially correlated for a single site but **independent** between different sites. This means the benefit/penalty of fading is not shared across neighboring cells.
- **Simplification (Deterministic PL)**: Instead of sampling LoS/NLoS states for each user, the code calculates an **Expected Path Loss** using the probability of LoS as a weight. This results in smoother, more predictable signal values compared to a real-world "flickering" radio environment.

---

## 3. Resource Management & Admission Control

### Paper Specification
- **Dynamic Dropping**: If drone movement increases resource requirements beyond 100% capacity, the system should drop the "hungriest" UEs to maintain the CSR.
- **Proportional Fair Scheduling**: Detailed resource reallocation logic.

### Code Implementation
- **Simplification**: The `AdmissionController` uses a **Greedy Admission** policy. It blocks new users if capacity is full but does not proactively "kick out" or drop existing users if their signal quality degrades during drone movement.
- **Impact**: This may result in slightly higher CSR values in the simulation than what would be observed in a physically constrained real-world system.

---

## 4. Backhaul Constraints

### Paper Specification
The paper assumes the drone is wirelessly backhauled on a separate frequency band, implying that backhaul is a distinct physical link.

### Code Implementation
- **Simplification**: The codebase assumes an **Ideal Backhaul**. There is no modeling of backhaul capacity, latency, or the possibility of backhaul failure. The drone behaves as if it has a direct fiber connection to the core network.

---

## 5. Summary Table

| Category | Paper Model | Code Implementation |
| :--- | :--- | :--- |
| **Optimization** | 4D ($x, y, z, CIO$) | 2D ($x, y$) |
| **Shadow Fading** | Spatially + Inter-Site Correlated | Spatially Correlated only |
| **Link Quality** | Probabilistic LoS/NLoS sampling | Weighted Average (Expected Value) |
| **UE Capacity** | Dynamic Dropping (Load Gating) | Greedy Admission / Static Load |
| **Backhaul** | Wireless Relay Link | Ideal / Infinite Capacity |
| **UE Mobility** | Static (Fixed during call) | Static (Fixed during call) |

---

## Conclusion
The codebase is a **functional implementation** of the paper’s primary research goal: validating the effectiveness of **Control Metric 7 (CM7)** in an online positioning algorithm. While radio and resource management are simplified for execution speed, the **navigation logic** and **metric computation** are identical to the paper’s specifications.
