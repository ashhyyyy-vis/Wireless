import sys
import os
from unittest.mock import MagicMock

# Add current directory to path
sys.path.append(os.getcwd())

from simulation.algorithm import EnergyAwarePositioningAlgorithm, CMType
from simulation.drone import Drone

def test_energy_logic():
    # Setup mocks
    drone = Drone(cell_id=36, active=True)
    network = MagicMock()
    admission = MagicMock()
    
    # Mock compute_cm to return specific values
    # We'll use a local function and side_effect to simulate CM changes
    cm_values = [0.5, 0.49, 0.485, 0.48, 0.47] 
    # Steps:
    # 1. 0.5 (initial) -> prev=0.5
    # 2. 0.49 (gain=0.01) -> threshold=0.011 -> improved=False -> Reverse
    # 3. 0.485 (gain=0.005) -> threshold=0.011 -> improved=False -> Switch Axis
    
    cm_iter = iter(cm_values)
    
    # We need to mock compute_cm in simulation.algorithm
    import simulation.algorithm
    original_compute_cm = simulation.algorithm.compute_cm
    simulation.algorithm.compute_cm = lambda *args, **kwargs: next(cm_iter)

    print("Testing EnergyAwarePositioningAlgorithm logic...")
    
    # threshold = alpha * energy + epsilon = 1.0 * 0.01 + 0.001 = 0.011
    algo = EnergyAwarePositioningAlgorithm(
        drone, network, admission,
        energy_cost=0.01, alpha=1.0, epsilon=0.001
    )
    
    # Step 1: Initial record
    res1 = algo.step_algorithm()
    print(f"Step 1: CM={res1['cm']}")
    
    # Step 2: Gain = 0.5 - 0.49 = 0.01. 0.01 < 0.011 -> improved=False
    res2 = algo.step_algorithm()
    print(f"Step 2: CM={res2['cm']}, Gain={res2['gain']:.3f}, Threshold={res2['threshold']:.3f}, Improved={res2['improved']}")
    assert res2['improved'] == False
    assert algo._direction == -1.0 # Should have reversed
    
    # Step 3: Gain = 0.49 - 0.485 = 0.005. 0.005 < 0.011 -> improved=False
    # Since we already reversed, this should trigger axis switch
    res3 = algo.step_algorithm()
    print(f"Step 3: CM={res3['cm']}, Gain={res3['gain']:.3f}, Improved={res3['improved']}, Axis={res3['axis']}")
    assert res3['improved'] == False
    # _switch_axis resets _prev_cm, so it returns early next time or we check state
    
    print("\nTest passed! The algorithm correctly respects the energy-gated improvement threshold.")

    # Restore original function
    simulation.algorithm.compute_cm = original_compute_cm

if __name__ == "__main__":
    try:
        test_energy_logic()
    except Exception as e:
        print(f"Test failed: {e}")
        sys.exit(1)
