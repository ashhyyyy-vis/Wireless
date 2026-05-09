# Choice Scarf Codebase Documentation

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Core Simulation Modules](#core-simulation-modules)
3. [Configuration System](#configuration-system)
4. [Network Topology](#network-topology)
5. [Drone System](#drone-system)
6. [Resource Management](#resource-management)
7. [Positioning Algorithms](#positioning-algorithms)
8. [Propagation Models](#propagation-models)
9. [Traffic Generation](#traffic-generation)
10. [Experiment Framework](#experiment-framework)
11. [Data Flow and Execution](#data-flow-and-execution)
12. [Usage Examples](#usage-examples)

---

## Architecture Overview

The Choice Scarf codebase simulates drone-mounted base station positioning in emergency communication scenarios. The system models a cellular network with 12 three-sectorized sites, where one site fails during a disaster phase and a drone provides coverage assistance.

### Core Components

1. **Network Layer**: Hexagonal cellular topology with wraparound boundaries
2. **Drone System**: Mobile base station with positioning algorithms
3. **Resource Management**: Radio resource allocation and admission control
4. **Propagation Models**: Path loss and shadow fading calculations
5. **Traffic Generation**: User equipment and hotspot modeling
6. **Experiment Framework**: Batch execution and result collection

### Simulation Phases

1. **Phase I (Warm-up)**: 1 hour normal operation to establish baseline
2. **Phase II (Disaster)**: Site failure, drone activation
3. **Phase III (Recovery)**: Drone positioning optimization continues

---

## Core Simulation Modules

### simulation/__init__.py

The central import hub that provides access to all simulation components. This module imports and re-exports the main classes and functions from submodules, creating a unified interface for the simulation system.

**Key Exports**:
- Network topology classes (Network, Site, Cell)
- Drone and positioning algorithms
- Resource management and traffic generation
- Propagation and configuration utilities

---

## Configuration System

### simulation/config.py

Central configuration repository containing all simulation parameters, constants, and environment-specific settings. This module separates configuration from implementation, allowing easy parameter tuning without code changes.

**Configuration Categories**:

1. **Network Topology**: Number of sites, sectors, cell layout
2. **Environment Settings**: Urban vs rural parameters
3. **Physical Layer**: Frequencies, powers, antenna models
4. **Propagation Models**: Path loss constants, shadow fading
5. **Traffic Parameters**: Arrival rates, call durations
6. **Algorithm Settings**: Movement parameters, energy costs
7. **Timing Configuration**: Phase durations, measurement periods

**Key Design Principles**:
- Environment-specific dictionaries (urban vs rural)
- Physical constants derived from standards (3GPP, ITU)
- Calibrated parameters for realistic CSR (~98% in healthy state)
- Energy-aware algorithm parameters for trade-off studies

**Usage Pattern**:
```python
from simulation.config import NUM_SITES, ISD, ENVIRONMENT
# Access environment-specific values
isd = ISD[ENVIRONMENT]  # Gets 500m for urban, 3500m for rural
```

---

## Network Topology

### simulation/network.py

Implements the cellular network infrastructure using a hexagonal grid layout with periodic boundary conditions. The network represents 12 three-sectorized base station sites arranged to simulate an infinite network through wraparound.

**Core Concepts**:

1. **Hexagonal Grid**: Sites positioned using axial coordinates converted to Cartesian
2. **Three-Sector Sites**: Each site has 3 sectors with 120° azimuth separation
3. **Wraparound Boundaries**: Eliminates edge effects by treating the network as toroidal
4. **Site Failure Model**: Site 0 fails during Phase II to simulate disaster

**Data Structures**:

- **Cell**: Individual sector with load tracking and UE assignment
- **Site**: Base station location with three cells and antenna height
- **Network**: Complete topology with distance calculations and wraparound logic

**Key Functions**:

1. **Site Generation**: `_hex_sites()` creates 12-site hexagonal cluster
2. **Distance Calculations**: 2D/3D distances with wraparound handling
3. **Cell Lookup**: Find serving cell for any coordinate
4. **Neighbor Management**: Identify adjacent cells for handover

**Design Rationale**:
The hexagonal layout matches standard cellular network models while the wraparound boundaries ensure that edge effects don't bias the simulation results. The three-sector configuration reflects real-world base station deployments.

---

## Drone System

### simulation/drone.py

Models the drone-mounted base station as a mobile communication platform with antenna characteristics and signal transmission capabilities. The drone serves as the adaptive element in the network, repositioning itself to optimize coverage after the disaster.

**Core Capabilities**:

1. **Position Management**: 3D coordinates with boundary constraints
2. **Antenna Modeling**: Directional gain patterns based on azimuth angles
3. **Signal Transmission**: RSRP calculation including path loss and antenna effects
4. **State Tracking**: Active/inactive status and movement history

**Key Functions**:

1. **Antenna Gain**: `drone_antenna_gain()` calculates directional gain
2. **RSRP Calculation**: `rsrp()` computes received signal strength
3. **Position Updates**: Movement within defined boundaries
4. **Signal Mapping**: Coverage area visualization

**Antenna Model**:
The drone uses a simplified 3GPP antenna model with:
- 65° horizontal beamwidth
- 30° maximum gain
- Omnidirectional vertical pattern

**Design Philosophy**:
The drone acts as a mobile base station with realistic antenna characteristics. The positioning algorithms control the drone's movement to optimize network performance while respecting physical constraints.

---

## Resource Management

### simulation/resource.py

Manages radio resources, user equipment admission, and performance tracking. This module implements the core radio access network functions including admission control, load balancing, and quality of service monitoring.

**Core Components**:

1. **RadioEngine**: Handles resource allocation and capacity management
2. **AdmissionController**: Manages UE admission and call setup
3. **CSRTracker**: Tracks Cell Success Rate performance metrics
4. **UE**: User equipment model with mobility and traffic requirements

**Resource Allocation Logic**:

1. **Capacity Calculation**: Each cell has finite resources based on bandwidth
2. **Admission Decision**: New calls admitted if resources available
3. **Load Balancing**: UEs assigned to best-serving cells based on signal strength
4. **Handover Management**: UE can switch cells for better service

**Performance Tracking**:

- **CSR (Cell Success Rate)**: Percentage of successfully served calls
- **Load Monitoring**: Real-time resource utilization per cell
- **Service Quality**: Call success/failure tracking
- **Rolling Metrics**: 5-minute sliding window for CSR calculation

**Key Design Decisions**:

1. **Greedy Admission**: Admit if resources available, no complex scheduling
2. **Signal-Based Assignment**: UEs connect to strongest signal cell
3. **Rolling Average**: CSR calculated over time window for stability
4. **Resource Units**: Abstract resource representation independent of technology

---

## Positioning Algorithms

### simulation/algorithm.py

Implements drone positioning strategies that determine how the drone moves to optimize network coverage. The algorithms range from simple grid search to sophisticated energy-aware optimization.

**Algorithm Classes**:

1. **DronePositioningAlgorithm**: Base class with common movement logic
2. **EnergyAwarePositioningAlgorithm**: Energy-conscious movement strategy
3. **CM Types**: Different algorithm variants (CM1-CM7)

**Movement Strategy**:

1. **Coordinate System**: X-Y plane movement with fixed altitude
2. **Step Size**: 1-meter movements per decision cycle
3. **Boundary Handling**: Constrained movement within defined area
4. **Axis-Based Search**: Systematic exploration along coordinate axes

**Energy-Aware Algorithm**:

**Decision Rule**: Move only if performance gain exceeds energy cost
```
Move if: gain > α × Energy + ε
where: gain = CM7_old - CM7_new
```

**Key Parameters**:
- α = 1.3: Energy weighting factor
- ε = 0.001: Minimum improvement threshold
- Energy cost = 0.01: Cost per movement step

**Algorithm Behavior**:

1. **Performance Evaluation**: Calculate CSR at current position
2. **Gain Assessment**: Compare with previous position performance
3. **Energy Decision**: Move only if justified by performance gain
4. **Direction Management**: Reverse or switch axes on insufficient gain
5. **Stopping Criteria**: Halt after consecutive failures

**Design Philosophy**:
The algorithms balance exploration (finding optimal positions) with exploitation (maintaining good performance). The energy-aware variant adds sustainability considerations to the optimization process.

---

## Propagation Models

### simulation/propagation.py

Implements radio wave propagation models for both terrestrial and air-to-ground links. The module combines path loss calculations with shadow fading to create realistic signal strength predictions.

**Propagation Models**:

1. **Terrestrial Links**: 3GPP TR 38.901 models for UE ↔ Base Station
2. **Air-to-Ground Links**: Al-Hourani model for UE ↔ Drone connections
3. **Shadow Fading**: Fraile et al. spatially correlated shadow fading

**LoS/NLoS Modeling**:

**Dual Implementation**:
- **Stochastic**: Binary LoS/NLoS decision based on probability
- **Deterministic**: Weighted average of LoS and NLoS path loss

**LoS Probability Model** (Al-Hourani):
```
P(LoS) = 1 / (1 + ξ × exp(-ψ × (θ - ξ)))
where θ is elevation angle, ξ and ψ are environment parameters
```

**Path Loss Calculation**:

1. **Free Space Path Loss**: Basic propagation loss based on distance
2. **Excessive Loss**: Additional loss for LoS/NLoS conditions
3. **Shadow Fading**: Log-normal fading with spatial correlation
4. **Minimum Coupling Loss**: Prevents unrealistically high signal levels

**Shadow Fading Implementation**:

1. **Spatial Correlation**: Fading correlated between nearby locations
2. **Site Correlation**: Base stations share correlated shadow fading
3. **Random Generation**: Per-run variation for realistic simulation

**Design Considerations**:
The propagation models balance accuracy with computational efficiency. The dual LoS/NLoS implementation allows both stochastic simulation and deterministic analysis.

---

## Traffic Generation

### simulation/traffic.py

Models user equipment behavior and traffic generation patterns. The module creates realistic call patterns and user distributions to simulate network load.

**Traffic Components**:

1. **UE (User Equipment)**: Individual mobile users with position and requirements
2. **TrafficGenerator**: Creates calls according to Poisson process
3. **Hotspot**: Concentrated user areas with elevated traffic intensity

**Call Generation**:

1. **Poisson Arrivals**: Calls arrive with exponential inter-arrival times
2. **Exponential Duration**: Call lengths follow exponential distribution
3. **Spatial Distribution**: UEs distributed across network area
4. **Hotspot Effects**: Concentrated areas with higher traffic intensity

**User Equipment Model**:

1. **Position**: 2D coordinates with fixed height (1.5m)
2. **Mobility**: Static during call lifetime
3. **Requirements**: Minimum bitrate for service quality
4. **Service Duration**: Exponential call holding time

**Hotspot Modeling**:

1. **Location**: Circular area with defined center and radius
2. **Intensity Multiplier**: Increased traffic generation in hotspot
3. **Environment-Specific**: Different intensity values for urban/rural

**Traffic Parameters**:

1. **Arrival Rate (λ)**: Calls per second over network area
2. **Call Duration (τ)**: Mean call length in seconds
3. **Minimum Bitrate**: Required service quality (0.384 Mbps)
4. **Hotspot Radius**: 100m fixed radius for concentrated areas

**Design Rationale**:
The traffic model creates realistic network load patterns that stress the system sufficiently to demonstrate algorithm performance differences. The hotspot model represents emergency scenarios where user density increases in specific areas.

---

## Experiment Framework

### runners/ Directory

The experiment framework provides tools for running simulations, collecting results, and analyzing performance across different scenarios and algorithms.

**Core Components**:

1. **simulation_core.py**: Single simulation execution engine
2. **simulation_batch.py**: Batch processing and scenario management
3. **experiment_*.py**: Specialized experiment modules
4. **experiments_launcher.py**: Unified experiment dispatcher

### simulation_core.py

**Purpose**: Execute single simulation runs with defined parameters

**Execution Flow**:

1. **Initialization**: Set up network, drone, and traffic
2. **Phase I (Warm-up)**: Run 1 hour to establish baseline
3. **Phase II (Disaster)**: Fail site 0, activate drone
4. **Phase III (Recovery)**: Continue optimization
5. **Results Collection**: Extract performance metrics

**Key Functions**:

1. **run_one()**: Execute single simulation with specified parameters
2. **run_scenario()**: Parse scenario string and run simulation
3. **Phase Management**: Handle transitions between simulation phases

### simulation_batch.py

**Purpose**: Manage multiple simulation runs and result aggregation

**Batch Processing**:

1. **Scenario Parsing**: Convert scenario strings to simulation parameters
2. **Parallel Execution**: Use multiprocessing for multiple runs
3. **Result Aggregation**: Average results across multiple runs
4. **CSV Output**: Save results in structured format

**Scenario Format**: "DU-100-60-4"
- DU/RU: Urban/Rural environment
- 100: Distance from disaster (meters)
- 60: Hotspot distance from UE cluster center (meters)
- 4: Traffic intensity multiplier (rho)

### Experiment Modules

**experiment_metrics.py**: Compare algorithms across scenarios
**experiment_convergence.py**: Analyze algorithm convergence behavior
**experiment_energy.py**: Energy performance analysis

**Common Pattern**:
1. **Parameter Setup**: Define experiment-specific arguments
2. **Simulation Execution**: Run multiple scenarios/algorithms
3. **Result Collection**: Aggregate and format results
4. **Output Generation**: Save CSV files and generate plots

### experiments_launcher.py

**Purpose**: Unified interface for running all experiments

**Dispatch Logic**:
```python
match args.experiment:
    case 1: run_metric_comparison()
    case 2: run_convergence_analysis()
    case 3: run_energy_analysis()
    case 4: run_convergence_energy_aware()
```

**Centralized Arguments**:
- --runs: Number of simulation runs per scenario
- --seed: Random seed for reproducibility
- --verbose: Detailed output option

---

## Data Flow and Execution

### Simulation Lifecycle

1. **Configuration Loading**: Load parameters from config.py
2. **Network Initialization**: Create hexagonal topology
3. **Drone Deployment**: Position drone at initial location
4. **Traffic Generation**: Create UEs and call patterns
5. **Phase Execution**: Run three simulation phases
6. **Results Collection**: Extract performance metrics
7. **Output Generation**: Save results and create visualizations

### Data Flow Diagram

```
config.py → Network → Drone → Resources → Traffic
    ↓           ↓       ↓        ↓         ↓
Parameters → Topology → Position → Load → Users
    ↓           ↓       ↓        ↓         ↓
Simulation Core ← Algorithm ← Propagation ← Admission
    ↓                                           ↓
Results ← CSR Tracking ← RSRP Calculation ← Call Management
```

### Key Data Structures

1. **Network State**: Cell loads, UE assignments, signal strengths
2. **Drone State**: Position, trajectory, algorithm parameters
3. **Traffic State**: Active calls, UE positions, service requirements
4. **Performance Metrics**: CSR values, convergence data, energy usage

---

## Usage Examples

### Basic Simulation Run

```python
from runners import run_one
from simulation.algorithm import CMType

# Run single simulation
result = run_one(
    env="urban",
    hotspot_cx=100, hotspot_cy=0,
    rho=8,  # Traffic intensity
    mode="algorithm",  # CM type
    cm_type=CMType.CM7,
    sim_duration_s=7200,  # 2 hours
    phase2_start_s=3600,  # Disaster at 1 hour
    seed=100
)

print(f"Final CSR: {result['final_csr']}")
print(f"Drone steps: {result['steps_taken']}")
```

### Batch Experiment

```python
from runners.simulation_batch import run_all_scenarios
from simulation.cases import cases

# Run all urban cases
urban_scenarios = cases['case1'] + cases['case2'] + cases['case3']
run_all_scenarios(
    urban_scenarios,
    out_file="results/urban_results.csv",
    n_runs=5,
    include_energy=True
)
```

### Convergence Analysis

```python
from runners.experiment_convergence import generate_convergence_data

# Analyze algorithm convergence
convergence_file, conv_time, final_val = generate_convergence_data(
    scenario="DU-100-60-4",
    mode="energy_algorithm",
    n_runs=10,
    drone_delay_s=0.0,
    base_seed=100
)
```

### Energy Comparison

```python
from runners.experiment_energy import compare_energy_aware

# Compare energy-aware vs legacy algorithms
results = compare_energy_aware(
    scenarios=["DU-100-60-4", "RU-500-60-50"],
    n_runs=5,
    base_seed=100,
    output_file="results/energy_comparison.csv"
)
```

---

## Rebuilding Guide

### System Dependencies

1. **Python 3.12+**: Core language runtime
2. **NumPy**: Numerical computations and array operations
3. **Matplotlib/Seaborn**: Visualization and plotting
4. **Pandas**: Data manipulation and analysis
5. **Multiprocessing**: Parallel execution support

### Development Steps

1. **Configuration System**: Start with config.py to define all parameters
2. **Network Topology**: Implement hexagonal grid with wraparound
3. **Propagation Models**: Add path loss and shadow fading calculations
4. **Resource Management**: Build admission control and CSR tracking
5. **Drone System**: Create mobile base station with antenna model
6. **Positioning Algorithms**: Implement movement strategies
7. **Traffic Generation**: Add UE and call modeling
8. **Simulation Core**: Integrate all components into execution engine
9. **Experiment Framework**: Build batch processing and analysis tools
10. **Validation**: Verify results match expected performance patterns

### Key Design Patterns

1. **Configuration-Driven**: Separate parameters from implementation
2. **Modular Architecture**: Independent components with clear interfaces
3. **State Management**: Centralized state tracking for consistency
4. **Parallel Execution**: Multiprocessing for batch experiments
5. **Result Aggregation**: Statistical analysis across multiple runs

### Testing Strategy

1. **Unit Tests**: Verify individual component functionality
2. **Integration Tests**: Test component interactions
3. **Scenario Tests**: Validate against known results
4. **Performance Tests**: Ensure reasonable execution times
5. **Reproducibility Tests**: Verify consistent results with same seeds

This documentation provides the logical foundation for rebuilding the entire Choice Scarf simulation system, focusing on the architectural decisions and data flow patterns rather than implementation syntax.
