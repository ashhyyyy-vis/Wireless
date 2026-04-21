import os
import glob
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

def plot_all_convergence(results_dir="results", output_file="results/convergence_plot.png"):
    """
    Plots all convergence CSV files found in the results directory.
    """
    # 1. Setup Aesthetics
    sns.set_theme(style="whitegrid")
    plt.figure(figsize=(12, 7))
    colors = sns.color_palette("husl", 10)
    
    # 2. Find files (exclude the summary files)
    all_files = glob.glob(os.path.join(results_dir, "convergence_*.csv"))
    files = [f for f in all_files if "summary" not in f]
    
    if not files:
        print("No convergence CSV files found in results/ directory.")
        return

    # 3. Load and Plot
    for i, file_path in enumerate(sorted(files)):
        filename = os.path.basename(file_path)
        # Extract scenario name from convergence_algorithm_SCENARIO.csv
        scenario = filename.replace("convergence_algorithm_", "").replace(".csv", "")
        
        df = pd.read_csv(file_path)
        
        # Smooth the data slightly for better visualization
        df['csr_smooth'] = df['csr'].rolling(window=3, min_periods=1).mean()
        
        line, = plt.plot(df['time'], df['csr_smooth'], label=scenario, 
                         color=colors[i % len(colors)], linewidth=2)
        
        # Final value marker
        plt.scatter(df['time'].iloc[-1], df['csr_smooth'].iloc[-1], 
                    color=line.get_color(), s=40, zorder=5)

    # 4. Formatting
    plt.title("Algorithm Convergence: CSR over Time", fontsize=16, fontweight='bold', pad=20)
    plt.xlabel("Simulated Time (seconds)", fontsize=12)
    plt.ylabel("Call Success Rate (CSR)", fontsize=12)
    plt.ylim(0, 1.05)
    plt.legend(title="Scenarios", bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.tight_layout()

    # 5. Save
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    plt.savefig(output_file, dpi=150)
    print(f"Convergence plot saved to -> {output_file}")
    plt.show()

if __name__ == "__main__":
    plot_all_convergence()
