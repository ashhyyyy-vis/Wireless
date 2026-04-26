import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import os
import sys

# Load data
df = pd.read_csv("results/final_all_scenarios_results.csv")
df.set_index("scenario", inplace=True)

# Parse command-line argument (0 for DU, 1 for RU)
partition_idx = int(sys.argv[1]) if len(sys.argv) > 1 else 0

# Split based on index (first 22 are DU, remaining 22 are RU)
du_count = 22
if partition_idx == 0:
    df = df.iloc[:du_count].copy()
    env_label = "Urban (DU)"
else:
    df = df.iloc[du_count:].copy()
    env_label = "Rural (RU)"

# Row-wise normalization (min-max per row)
norm_df = df.copy()

for idx, row in df.iterrows():
    min_val = row.min()
    max_val = row.max()
    
    # Avoid division by zero
    if max_val - min_val == 0:
        norm_df.loc[idx] = 0.5
    else:
        norm_df.loc[idx] = (row - min_val) / (max_val - min_val)

# Plot heatmap
plt.figure()

# Use red → yellow → green colormap
plt.imshow(norm_df.values, cmap="RdYlGn", aspect="auto")

# Axis labels
plt.xticks(ticks=np.arange(len(df.columns)), labels=df.columns, rotation=45)
plt.yticks(ticks=np.arange(len(df.index)), labels=df.index)

plt.title(f"Performance Heatmap: {env_label}")
plt.xlabel("Method")
plt.ylabel("Scenario")

plt.colorbar(label="Relative Performance (per scenario)")

# Optional: show values inside cells
for i in range(df.shape[0]):
    for j in range(df.shape[1]):
        plt.text(j, i, f"{df.iloc[i, j]:.3f}",
                 ha="center", va="center", fontsize=6)

plt.tight_layout()

# Save the plot
os.makedirs("results/plots", exist_ok=True)
out_path = f"results/plots/performance_heatmap_{'DU' if partition_idx == 0 else 'RU'}.png"
plt.savefig(out_path, dpi=200, bbox_inches='tight')
print(f"Heatmap saved to: {out_path}")

plt.show()