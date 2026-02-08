import os
import csv
import matplotlib.pyplot as plt
from pathlib import Path
import re
import math

DATA_DIR = Path("data")
EVERY_1_DIR = DATA_DIR / "every_1"
PLOTS_DIR = DATA_DIR / "plots"
PLOTS_DIR.mkdir(parents=True, exist_ok=True)

csv_paths = sorted(EVERY_1_DIR.glob("ads_*_every_1.csv"))
if not csv_paths:
    raise SystemExit("No CSV files found in data/every_1 (expected ads_<p>_<N>_every_1.csv)")

plot_name = input("Enter plot name (blank for default): ").strip()

def infer_p_from_filename(name: str) -> int | None:
    m = re.search(r"^ads_(\d+)_", name)
    if m:
        return int(m.group(1))
    return None

def read_n_delta(path: Path) -> tuple[list[int], list[float]]:
    n_vals: list[int] = []
    delta_vals: list[float] = []
    with open(path, "r", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or "n" not in reader.fieldnames or "delta" not in reader.fieldnames:
            raise ValueError(f"CSV missing required columns 'n' and 'delta': {path}")
        for row in reader:
            n_vals.append(int(row["n"]))
            delta_vals.append(float(row["delta"]))
    return n_vals, delta_vals


def gp_values(p: int, n_vals: list[int], delta_vals: list[float]) -> list[float]:
    lp = math.log(float(p))
    out: list[float] = []
    for n, d in zip(n_vals, delta_vals, strict=True):
        if n <= 0:
            out.append(float("nan"))
        else:
            out.append((math.log(float(n)) / lp) - (float(n) * float(d)))
    return out


series: list[tuple[int, list[int], list[float]]] = []
for path in csv_paths:
    p = infer_p_from_filename(path.name)
    if p is None or p < 2:
        continue
    n_vals, delta_vals = read_n_delta(path)
    gp = gp_values(p, n_vals, delta_vals)
    series.append((p, n_vals, gp))

series.sort(key=lambda t: t[0])
if not series:
    raise SystemExit("No valid ads_<p>_500_every_1.csv files found")

plt.figure(figsize=(13, 7.5))
for p, n_vals, gp in series:
    plt.plot(n_vals, gp, linewidth=1.5, label=f"p={p}")

plt.xlabel("n")
plt.ylabel(r"$g_p(n) = \log_p(n) - n\,\delta(n)$")
default_title = r"$g_p(n)$ for data/every_1"
plt.title(plot_name if plot_name else default_title)
plt.legend(loc="best", fontsize=9, ncols=2)
plt.grid(True, alpha=0.3)
plt.tight_layout()

output_file = PLOTS_DIR / "gp_every_1.png"
plt.savefig(output_file, dpi=150)
print(f"Plot saved to {output_file}")
plt.show()
