# Energy-Aware Positioning Algorithm Review

## Overview

The energy-aware algorithm implements a conservative movement strategy that balances network performance gains against energy consumption in drone positioning systems.

## Algorithm Design

### Decision Rule

The algorithm follows a simple but effective decision rule:

```
Move if: gain > α × Energy + ε
where: gain = CM7_old - CM7_new
```

This ensures that the drone only moves when the expected improvement in network performance (measured by Cell Success Rate) justifies the energy cost of movement.

### Implementation Details

The algorithm evaluates the gain from the previous movement step and compares it against a threshold that combines energy cost and a minimum improvement requirement:

1. **Calculate gain**: `gain = CM7_old - CM7_new` (positive values indicate improvement)
2. **Set threshold**: `threshold = α × Energy + ε`
3. **Decision**: Move only if `gain > threshold`

If the gain is insufficient, the algorithm reverses direction or switches axes, similar to the legacy algorithm, but without wasting energy on "undo" movements.

## Parameter Analysis

### α = 1.3 (Weighting Factor)

**Rationale**: Sets energy cost ~30% higher than raw energy value

**Effect**: Creates moderate conservativism - the algorithm moves only when gains significantly outweigh costs

**Trade-off**: Balances energy savings with network responsiveness

- **Lower α** would increase movement but reduce energy savings
- **Higher α** would save more energy but potentially miss optimization opportunities

### ε = 0.001 (Minimum Improvement)

**Rationale**: Prevents micro-movements for negligible gains

**Effect**: Acts as a stability filter - avoids oscillation around local optima

**Purpose**: Ensures movements are meaningful, not just noise

### Energy Cost = 0.01 per step

**Rationale**: Small but non-zero cost per meter movement

**Effect**: Accumulates over long trajectories to discourage unnecessary movement

## Performance Characteristics

### Energy Efficiency

- **Reduced movement**: Only moves when justified by significant CSR improvement
- **Early stopping**: Algorithm halts after 4 consecutive failures, conserving energy
- **No backtracking**: Unlike some algorithms, it doesn't waste energy undoing moves

### Network Performance

From the experimental results (`all_scenarios_results.csv`), CM7 shows:

- **Consistent performance** across diverse scenarios
- **Competitive CSR** values compared to more aggressive algorithms
- **Particularly strong** performance in challenging scenarios (high congestion)

### Trade-off Analysis

#### Advantages

1. **Energy savings** through selective movement
2. **Stable positioning** avoids oscillation
3. **Good baseline performance** maintained
4. **Predictable behavior** with clear stopping criteria

#### Limitations

1. **Slower convergence** due to conservative movement
2. **May miss local optima** that require small incremental gains
3. **Less responsive** to rapid network changes

## Parameter Sensitivity

The chosen parameters create a balanced approach:

- **Conservative enough** to achieve meaningful energy savings
- **Permissive enough** to maintain competitive network performance
- **Stable enough** to avoid unnecessary oscillations

### Recommended Parameter Ranges

| Parameter | Current Value | Recommended Range | Effect of Increase | Effect of Decrease |
|-----------|---------------|-------------------|-------------------|-------------------|
| α | 1.3 | 1.0 - 2.0 | More conservative, less movement | More aggressive, higher energy use |
| ε | 0.001 | 0.0005 - 0.005 | Higher stability, slower convergence | More responsive, potential oscillation |
| Energy Cost | 0.01 | 0.005 - 0.02 | Stronger energy savings | More movement, less energy efficiency |

## Use Cases

The energy-aware algorithm is particularly suitable for:

- **Battery-constrained deployments** where flight time is limited
- **Long-duration operations** requiring sustainable positioning
- **Scenarios where energy is a premium resource** (remote deployments)
- **Environmental considerations** where energy efficiency is prioritized

## Comparison with Other Algorithms

Based on the experimental results:

| Algorithm | Energy Efficiency | CSR Performance | Convergence Speed | Stability |
|-----------|-------------------|-----------------|-------------------|-----------|
| No Drone | N/A | Low | N/A | High |
| Static Drone | Low | Medium | Fast | High |
| CM1-CM6 | Medium | High | Medium | Medium |
| **CM7 (Energy-aware)** | **High** | **High** | **Slow** | **High** |

## Conclusion

The energy-aware algorithm successfully **decouples energy consumption from network optimization** while maintaining competitive performance. The parameter choices reflect a **pragmatic engineering approach** that prioritizes sustainable operation over aggressive optimization.

The trade-off analysis demonstrates that **modest energy savings** can be achieved with **minimal performance penalty**, making this approach viable for real-world drone positioning systems.

### Key Takeaways

1. **Effective balance** between energy efficiency and network performance
2. **Conservative parameters** (α=1.3, ε=0.001) provide good stability
3. **Suitable for long-duration** and **resource-constrained** deployments
4. **Maintains competitive CSR** while reducing unnecessary movement

The algorithm represents a practical solution for sustainable drone positioning in emergency communication scenarios.
