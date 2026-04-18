import numpy as np
from run_simulation import run_one

import csv
import os

def save_timeseries_csv(label, times, csr, out_dir="results/convergence"):
    os.makedirs(out_dir, exist_ok=True)

    path = os.path.join(out_dir, f"{label}.csv")

    file_exists = os.path.exists(path)

    with open(path, "a", newline="") as f:
        writer = csv.writer(f)
        # write header ONLY if file is new
        if not file_exists:
            writer.writerow(["time", "csr"])
        else:
            writer.writerow([])  # blank line
            writer.writerow(["--- new run ---"])
        for t, c in zip(times, csr):
            writer.writerow([t, c])
        
        

    print(f"Appended -> {path}")