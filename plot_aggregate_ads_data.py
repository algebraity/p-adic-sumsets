import os
import csv
import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit
from pathlib import Path

# Get CSV files from data/every_5 folder
data_dir = Path("data/every_5")
if not data_dir.exists():
    print(f"Directory {data_dir} not found")
    exit(1)

csv_files = sorted([f for f in data_dir.glob("*.csv")])
if not csv_files:
    print(f"No CSV files found in {data_dir} directory")
    exit(1)

print(f"Found {len(csv_files)} CSV files in {data_dir}/")

# Define the model: y = 0.5 - C * n^(-a)
def model(n, C, a):
    n = np.array(n, dtype=float)
    return 0.5 - C * n ** (-a)

# Create plot
plt.figure(figsize=(14, 8))

# Process each file
for csv_file in csv_files:
    print(f"Processing {csv_file.name}...")
    
    # Extract p value from filename (e.g., "ads_2_500_every_5" -> p=2)
    filename_parts = csv_file.stem.split('_')
    try:
        p_val = filename_parts[1]  # Format: ads_p_n_every_5
    except:
        p_val = csv_file.stem
    
    # Read CSV data
    n_vals = []
    delta_vals = []
    
    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            n_vals.append(int(row['n']))
            delta_vals.append(float(row['delta']))
    
    # Calculate y-values: 0.5 - delta
    y_vals = [0.5 - d for d in delta_vals]
    
    # Omit first 5 values (outliers)
    n_vals = n_vals[50:]
    y_vals = y_vals[50:]
    
    if not n_vals:
        print(f"  Skipping {csv_file.name} - insufficient data after filtering")
        continue
    
    # Ensure numpy arrays for fitting
    n_arr = np.array(n_vals, dtype=float)
    y_arr = np.array(y_vals, dtype=float)
    
    # Fit the curve using curve_fit
    try:
        popt, _ = curve_fit(model, n_arr, y_arr, p0=[1.0, 0.5], maxfev=10000)
        C_fit, a_fit = popt
        fit_y = model(n_arr, C_fit, a_fit)
        
        # Calculate R²
        ss_res = np.sum((y_arr - fit_y) ** 2)
        ss_tot = np.sum((y_arr - np.mean(y_arr)) ** 2)
        r2 = 1 - (ss_res / ss_tot) if ss_tot != 0 else float('nan')
        
        fit_label = f'p={p_val}: y = 0.5 - {C_fit:.6f}·n^(-{a_fit:.6f}), R² = {r2:.6f}'
        
        # Plot best-fit curve
        plt.plot(n_arr, fit_y, linewidth=2.5, label=fit_label, marker='o', markersize=5, alpha=0.7)
        
        print(f"  Fitted: C={C_fit:.6f}, a={a_fit:.6f}, R²={r2:.6f}")
    except Exception as e:
        print(f"  Fitting error for {csv_file.name}: {e}")

plt.xlabel('n', fontsize=12)
plt.ylabel('0.5 - delta', fontsize=12)
plt.title('Best-fit curves for different p values (every_5 dataset)', fontsize=14)
plt.axhline(y=0.5, color='green', linestyle='--', linewidth=2, label='y = 1/2', alpha=0.5)
plt.legend(loc='best', fontsize=10)
plt.grid(True, alpha=0.3)
plt.tight_layout()

# Save and show
output_file = "every_5_combined_plot.png"
plt.savefig(output_file, dpi=150)
print(f"\nPlot saved to {output_file}")

plt.show()
