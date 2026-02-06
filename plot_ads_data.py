import os
import csv
import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit
from pathlib import Path

# Get available CSV files
data_dir = Path("data")
csv_files = sorted([f.name for f in data_dir.glob("*.csv")])
if not csv_files:
    print("No CSV files found in data/ directory")
    exit(1)

# Display available files
print("Available CSV files:")
for i, file in enumerate(csv_files, 1):
    print(f"  {i}. {file}")

# Get user choice
choice = int(input(f"\nChoose a file (1-{len(csv_files)}): ")) - 1
selected_file = data_dir / csv_files[choice]
plot_name = input("Enter plot name: ")

# Read CSV data
n_vals = []
delta_vals = []

with open(selected_file, 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        n_vals.append(int(row['n']))
        delta_vals.append(float(row['delta']))

# Calculate y-values: 0.5 - delta
y_vals = [0.5 - d for d in delta_vals]

# Omit first 5 values (outliers)
# (keep slicing as-is; adjust index if needed)
n_vals = n_vals[5:]
y_vals = y_vals[5:]

# Ensure numpy arrays for fitting
n_arr = np.array(n_vals, dtype=float)
y_arr = np.array(y_vals, dtype=float)

# Define the model: y = 0.5 - C * n^(-a)
def model(n, C, a):
    n = np.array(n, dtype=float)
    return 0.5 - C * n ** (-a)

# Fit the curve using curve_fit
try:
    popt, _ = curve_fit(model, n_arr, y_arr, p0=[1.0, 0.5], maxfev=10000)
    C_fit, a_fit = popt
    fit_y = model(n_arr, C_fit, a_fit)

    # Calculate R²
    ss_res = np.sum((y_arr - fit_y) ** 2)
    ss_tot = np.sum((y_arr - np.mean(y_arr)) ** 2)
    r2 = 1 - (ss_res / ss_tot) if ss_tot != 0 else float('nan')

    fit_label = f'Best-fit: y = 0.5 - {C_fit:.6f}·n^(-{a_fit:.6f}), R² = {r2:.6f}'
except Exception as e:
    print(f"Fitting error: {e}")
    fit_y = None
    fit_label = None

# Create plot
plt.figure(figsize=(12, 7))
plt.scatter(n_vals, y_vals, label='Data', alpha=0.6, s=50)
if fit_y is not None:
    plt.plot(n_vals, fit_y, 'r-', linewidth=2, label=fit_label)

plt.xlabel('n')
plt.ylabel('0.5 - delta')
plt.title(plot_name)
plt.axhline(y=0.5, color='g', linestyle='--', linewidth=2, label='y = 1/2')
plt.legend(loc='best', fontsize=10)
plt.grid(True, alpha=0.3)
plt.tight_layout()

# Save and show
output_file = selected_file.stem + "_plot.png"
plt.savefig(output_file, dpi=150)
print(f"\nPlot saved to {output_file}")

plt.show()
