from run_simulation import run_one
from convergence import run_avg_csr, save_timeseries_csv
import matplotlib.pyplot as plt
import math

def parse_scenario(s: str):
    env_code, d, phi, rho = s.split("-")

    env_map = {
        "DU": "urban",
        "RU": "rural",
    }

    env = env_map[env_code]

    d = float(d)
    phi_deg = float(phi)
    rho = float(rho)

    phi = math.radians(phi_deg)

    cx = d * math.cos(phi)
    cy = d * math.sin(phi)

    return env, cx, cy, rho, d, phi_deg

def label_scenario(env, d, phi_deg):
    if d == 0:
        return "Failing Site"

    if env == "urban":
        if phi_deg == 0:
            return "A"
        elif phi_deg == 60:
            return "B"

    else:  # rural
        if phi_deg == 0:
            return "C"
        elif phi_deg == 60:
            return "D"

    return f"{d}-{phi_deg}"  # fallback

from multiprocessing import Pool, cpu_count


def _run_single(args):
    env, cx, cy, rho, mode, lambda_val, seed = args

    res = run_one(
        env=env,
        hotspot_cx=cx,
        hotspot_cy=cy,
        rho=rho,
        mode=mode,
        seed=seed,
        lambda_override=lambda_val,
        sim_duration_s=30*60 + 2*3600,
        phase2_start_s=30*60,
        verbose=False,
    )

    return res["csr_series"]

def run_avg_csr(
    env,
    cx,
    cy,
    rho,
    mode="algorithm",
    lambda_val=None,
    n_runs=5,
    workers=None,
):
    workers = workers or min(cpu_count(), n_runs)

    jobs = [
        (env, cx, cy, rho, mode, lambda_val, 42 + i)
        for i in range(n_runs)
    ]

    with Pool(workers) as p:
        all_series = p.map(_run_single, jobs)

    # --- averaging (same as before) ---
    times = [t for t, _ in all_series[0]]

    avg_csr = []
    for i in range(len(times)):
        vals = [run[i][1] for run in all_series if i < len(run)]
        avg_csr.append(np.mean(vals))

    return times, avg_csr


def generate_convergence_curves_from_list(
    scenarios,
    lambda_val,
):
    results = {}

    for s in scenarios:
        env, cx, cy, rho, d, phi_deg = parse_scenario(s)

        label = label_scenario(env, d, phi_deg)

        print(f"\n>> {label} ({s})")

        t, csr = run_avg_csr(
            env=env,
            cx=cx,
            cy=cy,
            rho=rho,
            lambda_val=lambda_val,
        )
        save_timeseries_csv(label, t, csr)
        results[label] = (t, csr)

    return results

def plot_convergence(results, title=""):

    for name, (t, csr) in results.items():
        plt.plot(t, csr, label=name)

    plt.xlabel("Time (s)")
    plt.ylabel("CSR")
    plt.title(title)
    plt.legend()
    plt.grid()
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":

    scenarios = [
        "DU-0-0-2",
        "DU-100-0-2",
        "DU-100-60-2",
    ]

    results = generate_convergence_curves_from_list(
        scenarios,
        lambda_val=11,
    )

    plot_convergence(results, "Urban Convergence (ρ=2)")