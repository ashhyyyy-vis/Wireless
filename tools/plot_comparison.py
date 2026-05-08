#!/usr/bin/env python3
"""
Create a grouped bar chart comparing no_drone, static_drone, and CM7 algorithms
across all scenarios in the results CSV.
"""

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np

def plot_algorithm_comparison(csv_file="results/all_scenarios_results.csv", 
                            output_file="results/algorithm_comparison.png"):
    """
    Create a grouped bar chart comparing three algorithms across all scenarios.
    
    Args:
        csv_file: Path to the results CSV file
        output_file: Output path for the plot
    """
    # Read the CSV data
    df = pd.read_csv(csv_file)
    
    # Extract only the three algorithms we want to compare
    algorithms = ['no_drone', 'static_drone', 'CM7']
    df_filtered = df[['scenario'] + algorithms].copy()
    
    # Set up the plot
    plt.style.use('seaborn-v0_8')
    fig, ax = plt.subplots(figsize=(15, 8))
    
    # Set up positions for grouped bars
    x_pos = np.arange(len(df_filtered))
    bar_width = 0.25
    
    # Colors for each algorithm
    colors = ['#FF6B6B', '#4ECDC4', '#45B7D1']  # Red, Teal, Blue
    labels = ['No Drone', 'Static Drone', 'CM7 (Energy-aware)']
    
    # Create grouped bars
    for i, (algo, color, label) in enumerate(zip(algorithms, colors, labels)):
        bars = ax.bar(x_pos + i * bar_width, 
                     df_filtered[algo], 
                     bar_width, 
                     label=label, 
                     color=color, 
                     alpha=0.8,
                     edgecolor='black',
                     linewidth=0.5)
        
        # Add value labels on top of bars (optional, for readability)
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height + 0.002,
                   f'{height:.3f}', ha='center', va='bottom', fontsize=8)
    
    # Customize the plot
    ax.set_xlabel('Scenario', fontsize=12, fontweight='bold')
    ax.set_ylabel('Cell Success Rate (CSR)', fontsize=12, fontweight='bold')
    ax.set_title('Algorithm Performance Comparison: No Drone vs Static Drone vs CM7', 
                fontsize=14, fontweight='bold', pad=20)
    
    # Set x-axis labels
    ax.set_xticks(x_pos + bar_width)
    ax.set_xticklabels(df_filtered['scenario'], rotation=45, ha='right')
    
    # Set y-axis limits
    ax.set_ylim(0.75, 0.95)
    ax.grid(True, alpha=0.3, axis='y')
    
    # Add legend
    ax.legend(loc='upper left', bbox_to_anchor=(1.02, 1))
    
    # Adjust layout
    plt.tight_layout()
    
    # Save the plot
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"📊 Comparison plot saved to: {output_file}")
    
    # Show statistics
    print("\n📈 Algorithm Performance Summary:")
    print(f"{'Algorithm':<15} {'Mean CSR':<10} {'Std Dev':<10} {'Min CSR':<10} {'Max CSR':<10}")
    print("-" * 60)
    for algo, label in zip(algorithms, labels):
        mean_val = df_filtered[algo].mean()
        std_val = df_filtered[algo].std()
        min_val = df_filtered[algo].min()
        max_val = df_filtered[algo].max()
        print(f"{label:<15} {mean_val:.4f}    {std_val:.4f}    {min_val:.4f}    {max_val:.4f}")
    
    plt.show()

def plot_algorithm_comparison_split(csv_file="results/all_scenarios_results.csv", 
                                 output_file="results/algorithm_comparison_split.png"):
    """
    Create separate plots for Urban and Rural scenarios.
    
    Args:
        csv_file: Path to the results CSV file
        output_file: Output path for the plot
    """
    # Read the CSV data
    df = pd.read_csv(csv_file)
    
    # Extract only the three algorithms we want to compare
    algorithms = ['no_drone', 'static_drone', 'CM7']
    df_filtered = df[['scenario'] + algorithms].copy()
    
    # Split into Urban and Rural
    df_urban = df_filtered[df_filtered['scenario'].str.startswith('DU')].copy()
    df_rural = df_filtered[df_filtered['scenario'].str.startswith('RU')].copy()
    
    # Set up the plot
    plt.style.use('seaborn-v0_8')
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 8))
    
    colors = ['#FF6B6B', '#4ECDC4', '#45B7D1']  # Red, Teal, Blue
    labels = ['No Drone', 'Static Drone', 'CM7 (Energy-aware)']
    
    def plot_subplot(ax, df_subset, title):
        """Helper function to plot a single subplot."""
        x_pos = np.arange(len(df_subset))
        bar_width = 0.25
        
        for i, (algo, color, label) in enumerate(zip(algorithms, colors, labels)):
            bars = ax.bar(x_pos + i * bar_width, 
                         df_subset[algo], 
                         bar_width, 
                         label=label, 
                         color=color, 
                         alpha=0.8,
                         edgecolor='black',
                         linewidth=0.5)
        
        ax.set_xlabel('Scenario', fontsize=12, fontweight='bold')
        ax.set_ylabel('Cell Success Rate (CSR)', fontsize=12, fontweight='bold')
        ax.set_title(title, fontsize=13, fontweight='bold')
        ax.set_xticks(x_pos + bar_width)
        ax.set_xticklabels(df_subset['scenario'], rotation=45, ha='right')
        ax.set_ylim(0.75, 0.95)
        ax.grid(True, alpha=0.3, axis='y')
        ax.legend()
    
    # Plot both subplots
    plot_subplot(ax1, df_urban, 'Urban Scenarios (DU)')
    plot_subplot(ax2, df_rural, 'Rural Scenarios (RU)')
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"📊 Split comparison plot saved to: {output_file}")
    plt.show()

def main():
    """Main function to run plotting scripts."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Plot algorithm comparison from results CSV")
    parser.add_argument("--mode", choices=["single", "split"], default="single",
                       help="Plotting mode: 'single' for all scenarios, 'split' for urban/rural separation")
    parser.add_argument("--csv", default="results/all_scenarios_results.csv",
                       help="Path to results CSV file")
    parser.add_argument("--output", default=None,
                       help="Output file path (auto-generated if not specified)")
    
    args = parser.parse_args()
    
    if args.mode == "single":
        output_file = args.output or "results/algorithm_comparison.png"
        plot_algorithm_comparison(args.csv, output_file)
    elif args.mode == "split":
        output_file = args.output or "results/algorithm_comparison_split.png"
        plot_algorithm_comparison_split(args.csv, output_file)

if __name__ == "__main__":
    main()
