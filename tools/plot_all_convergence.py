import pandas as pd
import matplotlib.pyplot as plt
import os
import glob

def plot_all_convergence(results_dir):
    """
    Finds all convergence CSVs and plots them on a single graph for comparison.
    """
    csv_files = glob.glob(os.path.join(results_dir, "convergence_algorithm_*.csv"))
    
    if not csv_files:
        print(f"No convergence files found in {results_dir}")
        return

    plt.figure(figsize=(12, 7), dpi=120)
    
    # Selection of distinct colors for multiple lines
    colors = [
        '#2ecc71', '#3498db', '#e74c3c', '#f1c40f', 
        '#9b59b6', '#1abc9c', '#e67e22', '#34495e',
        '#d35400', '#27ae60', '#2980b9', '#8e44ad'
    ]
    
    global_low = 1.0
    global_high = 0.0
    
    # Sort files to keep the legend consistent
    csv_files.sort()

    for i, file_path in enumerate(csv_files):
        # Extract scenario name from filename
        scenario = os.path.basename(file_path).replace("convergence_algorithm_", "").replace(".csv", "")
        try:
            df = pd.read_csv(file_path)
            # 1. CENTER ON DEPLOYMENT
            # Find the timestamp where the largest CSR increase occurs
            df['csr_diff'] = df['csr'].diff()
            jump_idx = df['csr_diff'].idxmax()
            deployment_time_csv = df.loc[jump_idx, 'time']
            
            df['time_rel'] = df['time'] - deployment_time_csv
            
            # Focus on local transition (+/- 2000s around deployment)
            df_plot = df[(df['time_rel'] >= -360) & (df['time_rel'] <= 2000)].copy()
            
            if df_plot.empty:
                continue

            # Update global scale for axes truncation
            local_low = df[df.index == jump_idx-1]['csr'].values[0] if jump_idx > 0 else df_plot['csr'].iloc[0]
            local_high = df_plot['csr'].max()
            global_low = min(global_low, local_low)
            global_high = max(global_high, local_high)
            
            # Plot line
            color = colors[i % len(colors)]
            plt.plot(df_plot['time_rel'], df_plot['csr'], 
                     linewidth=2, label=scenario, color=color, alpha=0.85)

        except Exception as e:
            print(f"Error processing {file_path}: {e}")

    # Vertical line for deployment (Now centered at 0)
    plt.axvline(x=0, color='#95a5a6', linestyle='--', alpha=0.5, label='Drone Deployed')

    # Formatting
    plt.title("Convergence Comparison: All Scenarios\n(Aligned at Deployment)", fontsize=15, fontweight='bold', pad=20)
    plt.xlabel("Time since Deployment (seconds)", fontsize=12)
    plt.ylabel("Call Success Rate (CSR)", fontsize=12)
    
    # Truncate axes properly based on global range
    padding = (global_high - global_low) * 0.15
    plt.ylim(global_low - padding, global_high + padding)
    plt.xlim(-400, 2050) # Range covering the main convergence period
    
    plt.grid(True, linestyle=':', alpha=0.5)
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left', borderaxespad=0., 
               fontsize=9, ncol=1 if len(csv_files) < 10 else 2)
    
    plt.tight_layout()
    
    os.makedirs("results/plots", exist_ok=True)
    out_name = "results/plots/convergence_comparison_all.png"
    plt.savefig(out_name, bbox_inches='tight')
    plt.close()
    print(f"Comparison plot saved to: {out_name}")

if __name__ == "__main__":
    plot_all_convergence("results")
