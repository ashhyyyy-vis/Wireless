#!/usr/bin/env python3
"""
Script to plot convergence data for a single scenario from run_convergence output.
"""

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import argparse
import os

def plot_single_scenario(csv_file, scenario_name=None, save_path=None):
    """
    Plot convergence data for a single scenario.
    
    Args:
        csv_file (str): Path to convergence CSV file
        scenario_name (str): Name of scenario to plot
        save_path (str): Path to save plot
    """
    # Load the convergence data
    df = pd.read_csv(csv_file)
    
    if scenario_name:
        # Filter for specific scenario
        scenario_data = df[df['scenario'] == scenario_name]
        if scenario_data.empty:
            print(f"Scenario '{scenario_name}' not found in {csv_file}")
            return
    else:
        # Use all data
        scenario_data = df
    
    if 'time_s' in scenario_data.columns:
        # Detailed time series data (from convergence_summary.csv)
        plt.figure(figsize=(12, 8))
        plt.plot(scenario_data['time_s'], scenario_data['csr'], 
                marker='o', linewidth=2, markersize=6)
        plt.xlabel('Time (seconds)')
        plt.ylabel('Call Success Rate (CSR)')
        plt.title(f'Convergence - {scenario_name if scenario_name else "All Scenarios"}')
        plt.grid(True, alpha=0.3)
        plt.ylim(0, 1.05)
        
    elif 'convergence_time_s' in scenario_data.columns:
        # Summary data (from convergence_summary_algorithm.csv)
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
        
        # Plot 1: Final CSR values
        scenarios = scenario_data['scenario']
        final_csrs = scenario_data['final_csr']
        colors = plt.cm.Set3(range(len(scenarios)))
        
        bars1 = ax1.bar(range(len(scenarios)), final_csrs, color=colors)
        ax1.set_xlabel('Scenario')
        ax1.set_ylabel('Final CSR')
        ax1.set_title('Final CSR by Scenario')
        ax1.set_xticks(range(len(scenarios)))
        ax1.set_xticklabels(scenarios, rotation=45)
        ax1.grid(True, alpha=0.3)
        
        # Plot 2: Convergence times
        conv_times = scenario_data['convergence_time_s']
        bars2 = ax2.bar(range(len(scenarios)), conv_times, color=colors)
        ax2.set_xlabel('Scenario')
        ax2.set_ylabel('Convergence Time (s)')
        ax2.set_title('Convergence Time by Scenario')
        ax2.set_xticks(range(len(scenarios)))
        ax2.set_xticklabels(scenarios, rotation=45)
        ax2.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
    else:
        print("Unknown data format. Expected 'time_s' or 'convergence_time_s' columns.")
        return
    
    # Save plot
    if save_path:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"Plot saved to: {save_path}")
    
    plt.show()

def main():
    parser = argparse.ArgumentParser(description='Plot single scenario convergence')
    parser.add_argument('--csv', default='results/convergence_summary.csv', 
                       help='Path to convergence CSV file')
    parser.add_argument('--scenario', help='Scenario name to plot (e.g., DU-100-60-8)')
    parser.add_argument('--save', help='Save path for plot (e.g., results/plot.png)')
    
    args = parser.parse_args()
    
    # Auto-detect plot type based on CSV structure
    if os.path.exists(args.csv):
        df = pd.read_csv(args.csv)
        if 'time_s' in df.columns:
            print("Detected time series data format")
            plot_type = "timeseries"
        elif 'convergence_time_s' in df.columns:
            print("Detected summary data format")
            plot_type = "summary"
        else:
            print("Unknown data format")
            return
    else:
        print(f"CSV file not found: {args.csv}")
        return
    
    plot_single_scenario(args.csv, args.scenario, args.save)

if __name__ == "__main__":
    main()
