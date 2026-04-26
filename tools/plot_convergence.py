import pandas as pd
import matplotlib.pyplot as plt
import os
import argparse

def plot_convergence_properly(csv_path, scenario_name):
    """
    Generates a polished convergence plot focusing on the transition from
    disaster low to drone-optimized high.
    """
    # Load data
    if not os.path.exists(csv_path):
        print(f"Error: {csv_path} not found.")
        return
    
    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return
    
    # 1. FIND DEPLOYMENT JUMP: Shift time so 0 is when the drone starts
    # We find the timestamp where the largest CSR increase occurs
    df['csr_diff'] = df['csr'].diff()
    jump_idx = df['csr_diff'].idxmax()
    deployment_time_csv = df.loc[jump_idx, 'time']
    
    df['time_rel'] = df['time'] - deployment_time_csv
    
    # Filter for the relevant comparison range (pre-drone disaster to converged state)
    # Start at -360s (approx 6 mins of disaster phase) to 1800s post-deployment
    df_plot = df[(df['time_rel'] >= -360) & (df['time_rel'] <= 2000)].copy()
    
    if df_plot.empty:
        print("Data is empty after re-centering. Check if CSV timestamps align with deployment jump.")
        return

    # 2. ANALYSIS: Metrics relative to deployment
    # Disaster state (just before deployment)
    low_point = df[df.index == jump_idx-1]['csr'].values[0] if jump_idx > 0 else df_plot['csr'].iloc[0]
    
    final_high = df_plot['csr'].iloc[-1]
    peak_val = df_plot['csr'].max()
    
    # 3. PLOT AESTHETICS
    plt.figure(figsize=(10, 6), dpi=120)
    # Attempt to use a nice theme
    try:
        plt.style.use('seaborn-v0_8-muted')
    except:
        plt.style.use('ggplot')
    
    plt.plot(df_plot['time_rel'], df_plot['csr'], 
             color='#27ae60', linewidth=2.5, label='CM7 Algorithm (CSR)')
    
    # Deployment point is now exactly at 0
    plt.axvline(x=0, color='#e74c3c', linestyle='--', alpha=0.6, label='Drone Deployed')
    
    # 4. TRUNCATE Y-AXIS: Zoom in on the improvement range
    # Ensure some breathing room
    y_min = low_point * 0.98
    y_max = max(peak_val, final_high) * 1.02
    plt.ylim(y_min, y_max)
    
    # 5. LABELLING
    plt.title(f"Convergence Analysis: {scenario_name}\n(0s = Drone Deployment)", 
              fontsize=14, fontweight='bold', pad=20)
    plt.xlabel("Time since Deployment (seconds)", fontsize=12)
    plt.ylabel("Call Success Rate (CSR)", fontsize=12)
    
    # 6. ANNOTATIONS
    # Disaster State Point (1 minute before deployment)
    plt.annotate(f'Disaster State: {low_point:.3f}', 
                 xy=(-120, low_point), xytext=(-300, low_point - (y_max-y_min)*0.1),
                 arrowprops=dict(facecolor='black', shrink=0.05, width=1, headwidth=5),
                 fontsize=10)
    
    # Converged High (at the end)
    plt.annotate(f'Converged High: {final_high:.3f}', 
                 xy=(df_plot['time_rel'].iloc[-1], final_high), 
                 xytext=(df_plot['time_rel'].iloc[-1]-800, final_high + (y_max-y_min)*0.05),
                 arrowprops=dict(facecolor='black', shrink=0.05, width=1, headwidth=5),
                 fontsize=10)

    plt.grid(True, linestyle=':', alpha=0.6)
    plt.legend(loc='lower right', frameon=True, shadow=True)
    
    # Save the polished result
    os.makedirs("results/plots", exist_ok=True)
    out_name = f"results/plots/convergence_focus_{scenario_name}.png"
    plt.savefig(out_name, bbox_inches='tight')
    plt.close()
    print(f"Properly scaled convergence plot saved to: {out_name}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Polished Convergence Plotter")
    parser.add_argument("--csv", required=True, help="Path to convergence CSV")
    parser.add_argument("--name", default="Scenario", help="Scenario name for title")
    
    args = parser.parse_args()
    plot_convergence_properly(args.csv, args.name)
