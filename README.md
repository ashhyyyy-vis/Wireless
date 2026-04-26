## Energy-Aware Online Positioning of UAV-Based Base Stations in Dynamic Wireless Networks

---

## Base Paper
Online Positioning of a Drone-Mounted Base Station in Emergency Scenarios

This paper proposes a real-time, data-driven algorithm for positioning UAV base stations without requiring prior knowledge or training.

---

## Supporting References Studied

Energy-aware Relay Positioning in Flying Networks:  
Introduces energy-efficient UAV positioning by optimizing trajectory and propulsion energy. However, it assumes full knowledge of the environment and does not support real-time adaptive positioning.

Efficient 3D Aerial Base Station Placement Considering Users Mobility by Reinforcement Learning:  
Uses reinforcement learning to dynamically position UAVs under user mobility, but requires training and has higher computational complexity.

UAV-Assisted Wireless Communications: A Survey:  
Provides an overview of UAV-based communication systems, highlighting key challenges such as energy constraints, dynamic deployment, and positioning strategies.

---

## What the Paper Solves (Brief)

The base paper proposes a **data-driven, online algorithm** to dynamically position a drone-mounted base station in real-time.  
It adapts to **network disruptions and traffic hotspots** without requiring prior training or full knowledge of user distribution.

---

## Problem Statement

Existing online drone positioning approaches:
 - Assume **infinite energy / no battery constraints**
 - Focus primarily on **coverage and capacity optimization**
 - Ones that do focus on Energy assume a perfectly knows system

This is unrealistic because:
 - UAVs are inherently **battery-limited systems**
 - Continuous movement incurs significant energy cost

Therefore, there is a need to **incorporate energy awareness into real-time drone positioning decisions**

---

## Proposed Solution

We extend the online positioning approach by introducing **energy-aware decision making**.

Instead of always moving toward the position that maximizes network performance, the UAV makes decisions based on a trade-off between:

- performance improvement (using control metric)
- energy cost of movement

The UAV keeps moving **only when the improvement justifies the energy expenditure**, leading to more stable and efficient behavior.

---

## Methodology

The base paper evaluates multiple control metrics and identifies **CM7** as the metric that best correlates with Call Success Rate (CSR).  

CM7 represents the average load per user (UE) across the drone cell and the most heavily loaded neighboring cell.

We use CM7 as the control metric and modify the decision rule as follows:

gain = CM7_old − CM7_new

Move only if:

gain > λ × Energy + ε

Where:
- λ = trade-off parameter between performance and energy
- ε = small threshold to avoid unnecessary movement due to noise

---

### Energy Model (Simplified)

We use a discrete step-based energy model:

- If the UAV moves:  
  Energy = α

- If the UAV hovers:  
  Energy = β

Where:
- α = energy cost per movement step
- β = energy cost per hover step

Each iteration represents a fixed time step, so energy is computed per step rather than continuously.

This simplified model approximates propulsion energy without requiring complex physical modeling.

---

## Algorithm Behavior

- The UAV moves in a direction and observes the resulting change in CM7
- If improvement is sufficient (above energy threshold), it continues moving
- Otherwise, it stops or explores a new direction
- The UAV stabilizes when no movement yields sufficient benefit

---

## Simulation Setup (Planned)

- Users distributed randomly in a 2D area
- One UAV acting as a base station
- Performance metric:
  - Coverage or proxy metric for CSR

We simulate:
- Static positioning
- Online positioning (base paper)
- Energy-aware positioning (proposed)

---

## Expected Results / Comparisons

We compare:

1. **Static Placement**
   - Fixed drone position
   - Baseline performance

2. **Online Positioning (Base Paper)**
   - Optimizes performance
   - Ignores energy constraints

3. **Energy-Aware Online Positioning (Proposed)**
   - Introduces performance-energy trade-off
   - Reduces unnecessary movement

4. **Effect of λ**
   - Higher λ → less movement, lower energy usage
   - Lower λ → better performance, higher energy usage

---

### Expected Outcome

- Online positioning performs better than static placement
- Energy-aware positioning:
  - Slightly lower performance than pure online method
  - **Significantly improved energy efficiency**

This demonstrates the importance of incorporating realistic constraints into online UAV positioning systems.
