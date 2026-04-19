from run_simulation import run_one
from simulation.algorithm import CMType
from kholo import parse_scenario

def test_cm_movement(cm_type,seed=42):
    print(f"\n=== Testing {cm_type.name} ===")
    
    env, cx, cy, rho = parse_scenario("RU-500-60-25")
    
    # Run static drone case
    static_result = run_one(
        env=env,
        hotspot_cx=cx,
        hotspot_cy=cy,
        rho=rho,
        mode="static",
        cm_type=None,
        sim_duration_s=900,  # 15 min for quick test
        phase2_start_s=300,
        seed=seed,
        lambda_override=1.5,
        verbose=False
    )
    
    # Run dynamic algorithm case
    result = run_one(
        env=env,
        hotspot_cx=cx,
        hotspot_cy=cy,
        rho=rho,
        mode="algorithm",
        cm_type=cm_type,
        sim_duration_s=900,  # 15 min for quick test
        phase2_start_s=300,
        seed=seed,
        lambda_override=1.5,
        verbose=True  # This will show drone movements
    )
    
    print(f"\nFinal Results:")
    print(f"  Static CSR: {static_result['final_csr']:.4f}")
    print(f"  Dynamic CSR: {result['final_csr']:.4f}")
    print(f"  Trajectory points: {len(result['trajectory'])}")
    
    if result['trajectory']:
        first = result['trajectory'][0]
        last = result['trajectory'][-1]
        print(f"  Start: ({first[1]:.1f}, {first[2]:.1f}), CM={first[3]:.4f}")
        print(f"  End:   ({last[1]:.1f}, {last[2]:.1f}), CM={last[3]:.4f}")
        print(f"  Total movement: {abs(last[1]-first[1]) + abs(last[2]-first[2]):.1f}m")

if __name__ == "__main__":
    # Test different CM types to see movement patterns
    for cm in [CMType.CM7]:
        test_cm_movement(cm,101)
