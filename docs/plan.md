# Developer Implementation Guide: Drone Positioning Algorithm
**Context:** This guide is a companion to "Online Positioning of a Drone-Mounted Base Station in Emergency Scenarios" (IEEE TVT, 2024). It translates the research logic into a software execution plan.

---

## 1. Simulation Infrastructure (Ref: Section V)

### 1.1. Grid & Coordinate System
* **The Rhombus Boundary:** Implement the 7-site cluster as the fundamental simulation area. 
* **Wraparound Mapping:** Create a function `get_distance(pos_a, pos_b)` that calculates the 3D distance by considering `pos_b` and its 6 periodic images (displaced by the cluster basis vectors). This ensures a seamless "infinite" network.
* **Sectorization:** Map each site $(x_s, y_s)$ to three `Cell` objects with boresight angles $\alpha \in \{30^\circ, 150^\circ, 270^\circ\}$.

### 1.2. Radio Link Budget
* **Antenna Pattern (Section V-B):** Implement Equation (1) for the 3D gain. 
    * *Developer Note:* Ensure $\theta$ (vertical) and $\phi$ (horizontal) are calculated relative to the sector's boresight. Use $\theta_{tilt} = 10^\circ$.
* **The Drone Channel:** Strictly follow Equation (2). 
    * Use a sigmoid function for $p_{LoS}$ based on the environment constants ($\xi, \psi$) from Table II.
    * Use $P_{tx} = 27$ dBm (0.5W) for the drone vs 43 dBm (20W) for the BS.

---

## 2. Traffic & Admission Engine

### 2.1. Poisson Session Management
* **User Object:** `UE { id, x, y, start_time, duration, current_cell_id }`.
* **Hotspot Geometry:** Define a circle $H$ with radius 100m. 
    * If `dist(UE, H_center) < 100`, arrival rate = $\lambda \rho$.
    * Else, arrival rate = $\lambda$.
* **Service Time:** Sample call duration from an exponential distribution with mean $1/\mu$.

### 2.2. Association & CSR Logic
* **Initial Association:** UE selects the cell with the highest $RSRP_{i} = P_{tx,i} + G_{i} - L_{i}$.
* **Admission Constraint:** A call is successful if and only if:
    1.  $\max(RSRP) \geq -120$ dBm.
    2.  The selected cell has available Resource Blocks (RB). 
* **CSR Metric:** Maintain a global counter of `Successes` and `Attempts`.

---

## 3. The "Online" Optimization Brain (Ref: Section VII)

This is the core algorithm. Implement it as a **Gradient Ascent** module where the Control Metric (CM) is the objective function.

### 3.1. Pluggable Metric Function $\mathcal{J}$
Create a template where any CM from Section VI can be inserted. 
* **Target Metric (CM 7):** Focus on load-balancing. 
    * $J = \sum_{u \in \mathcal{U}_d} \mathbb{1}(\text{satisfied}) - \alpha \cdot \text{InterferenceFactor}$
    * *Simplification:* If real-time interference calculation is too heavy, the paper suggests using a simplified load-ratio.

### 3.2. Step-wise Movement Logic
Every control interval $T$:

1.  **Probe (Gradient Estimation):**
    * Calculate the metric at current position $\mathcal{J}(x, y)$.
    * Calculate $\mathcal{J}$ at four surrounding "probe points" at distance $\delta$: $(x \pm \delta, y)$ and $(x, y \pm \delta)$.
2.  **Calculate Step Direction:**
    * $\nabla \mathcal{J} \approx \left[ \frac{\mathcal{J}_{east} - \mathcal{J}_{west}}{2\delta}, \frac{\mathcal{J}_{north} - \mathcal{J}_{south}}{2\delta} \right]$
3.  **Execute Move:**
    * Update: $Pos_{new} = Pos_{old} + \eta \cdot \frac{\nabla \mathcal{J}}{\|\nabla \mathcal{J}\|}$
    * **Constraint:** Ensure $\|\Delta Pos\| \leq V_{max} \cdot T$. 
    * **Altitude:** Keep $h = 120$m (constant) as per Section VIII-A findings.

---

## 4. Simulation Workflow

### Phase I: Steady State (Baseline)
* Run the network with 7 healthy sites.
* Populate users and allow the system to reach a "warm" state where CSR is stable.

### Phase II: The Disaster
* **Trigger:** Disable Site 0 (the central site).
* **Trigger:** Inject the 100m hotspot at a random offset from $(0,0)$.
* **Result:** Monitor the immediate drop in CSR.

### Phase III: Recovery (Drone Loop)
* Initialize Drone at $(0,0, 120)$.
* Start the Optimization Loop from Section 3.2.
* **Output:** Save the Drone trajectory $(x_t, y_t)$ and the time-series CSR data for comparison against the "No Drone" and "Static Drone" benchmarks mentioned in Section VIII.

---

## 5. Implementation Constants (Urban)
* **ISD:** 500m
* **Carrier:** 3.5 GHz
* **BW:** 5 MHz
* **$\lambda$ (Arrival Rate):** Adjust until healthy CSR $\approx 98\%$.
* **$\rho$ (Hotspot Multiplier):** 2, 4, or 8.s