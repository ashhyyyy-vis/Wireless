import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns


def plot_heatmap(
    csv_path,
    title="CSR Heatmap",
    save_path=None,
    figsize=(12, 8),
):
    """
    Plot heatmap while preserving CSV order.
    """

    # -----------------------------
    # Load CSV (preserves order)
    # -----------------------------
    df = pd.read_csv(csv_path)

    # Preserve column order explicitly
    columns = list(df.columns)

    # Set index WITHOUT sorting
    df = df.set_index("scenario")

    # Reapply column order (just to be safe)
    df = df[columns[1:]]  # skip 'scenario'

    # -----------------------------
    # Plot
    # -----------------------------
    plt.figure(figsize=figsize)

    sns.heatmap(
        df,
        annot=True,
        fmt=".3f",
        cmap="viridis",
        linewidths=0.5,
        cbar_kws={"label": "CSR"},
    )

    plt.title(title)
    plt.xlabel("Method")
    plt.ylabel("Scenario")

    plt.xticks(rotation=45)
    plt.yticks(rotation=0)

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=120)
        print(f"Saved heatmap -> {save_path}")

    plt.show()


# -----------------------------
# Example
# -----------------------------
if __name__ == "__main__":
    plot_heatmap(
        "results/plot_maps.csv",
        title="CSR Heatmap (Original Order)",
        save_path="results/heatmap.png",
    )