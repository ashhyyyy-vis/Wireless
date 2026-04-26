import pandas as pd
import matplotlib.pyplot as plt
import os

# Load data from the generated report file
csv_path = "results/energy_comparison_report.csv"

if not os.path.exists(csv_path):
    print(f"Error: {csv_path} not found. Please run Experiment 3 first.")
    exit(1)

try:
    df = pd.read_csv(csv_path)
except Exception as e:
    print(f"Error reading CSV: {e}")
    exit(1)

# Calculate metrics
positive_gains = (df["csr_delta"] >= 0).sum()
total_scenarios = len(df)
avg_save = df["steps_saved"].mean()

# Extract group (DU / RU)
df["group"] = df["scenario"].apply(lambda x: x.split("-")[0])

# Plot
plt.figure(figsize=(10, 6), dpi=120)

for group in df["group"].unique():
    subset = df[df["group"] == group]
    plt.scatter(subset["steps_saved"], subset["csr_delta"], label=group, alpha=0.7, s=60)

# Axis labels
plt.xlabel("Steps Saved (vs Legacy)", fontsize=12)
plt.ylabel("CSR Delta (Energy - Legacy)", fontsize=12)

# Set X-axis to start from 375 as requested by user
plt.xlim(left=375)

# Reference lines
plt.axhline(0, color='black', linestyle='--', alpha=0.3)  # CSR no change
plt.axvline(0, color='black', linestyle='--', alpha=0.3)  # no steps saved

# Legend
plt.legend(frameon=True, shadow=True)

# Summary Text Box
stats_text = (
    f"Total Scenarios: {total_scenarios}\n"
    f"Positive CSR Gains: {positive_gains}\n"
    f"Avg. Steps Saved: {avg_save:.1f}"
)
props = dict(boxstyle='round', facecolor='white', alpha=0.8, edgecolor='#cccccc')
plt.text(0.05, 0.95, stats_text, transform=plt.gca().transAxes, fontsize=10,
        verticalalignment='top', bbox=props)

# Title
plt.title("Energy-Aware Efficiency: Steps Saved vs CSR Delta", fontweight='bold', pad=15)

# Save the plot
os.makedirs("results/plots", exist_ok=True)
out_path = "results/plots/energy_tradeoff_analysis.png"
plt.savefig(out_path, dpi=150, bbox_inches='tight')
print(f"Energy trade-off plot saved to: {out_path}")

plt.show()