import os
import csv
import time
import random as rand
import multiprocessing as mp
import subprocess
from fractions import Fraction
from typing import Any, List, Tuple, Union

HEADER = [
    "n", "|A|", "|A+A|", "delta", "dup_density"
]

def A_ads_size(p: int, n: int) -> tuple[int, int]:
    """
    Calls the C program ./ads_p to compute A_n and A_n + A_n.
    Returns (|A_n|, |A_n + A_n|) by parsing the output.
    """
    try:
        result = subprocess.run(
            ["./ads_p", str(p), str(n)],
            capture_output=True,
            text=True,
            check=True
        )
        # Parse the final line: "n, |A|, |A+A|"
        output_lines = result.stdout.strip().split('\n')
        for line in output_lines:
            if line.startswith(str(n) + ","):
                parts = line.split(",")
                A_size = int(parts[1].strip())
                AA_size = int(parts[2].strip())
                return A_size, AA_size
        raise RuntimeError(f"Could not parse output for n={n}")
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"C program failed for n={n}: {e.stderr}")
    except FileNotFoundError:
        raise RuntimeError("./ads_size not found. Please compile the C program first: gcc -o ads_size ads_size.c -lgmp")

def _worker(ns: list[int]) -> list[list[int]]:
    out = []
    for (p, i) in ns:
        A_size, AA_size = A_ads_size(p, i)
        P = (A_size * (A_size + 1) // 2)
        dup_density = Fraction(P - AA_size, P)
        delta = float(Fraction(1, 2) - Fraction(AA_size, A_size * A_size))
        out.append([i, A_size, AA_size, delta, float(dup_density)])
    return out


def compute_ads(s:int, p: int, n: int, i: int, out_dir: str = "data", k: int = 40, jobs: int | None = None, mp_context: str | None = "fork"):
    os.makedirs(out_dir, exist_ok=True)
    jobs = jobs or os.cpu_count() or 1

    t0 = time.time()

    ctx = mp.get_context(mp_context) if mp_context else mp.get_context()

    # Generate values: only every ith value from s+i to n
    values = list(range(s+i, n + 1, i))
    # Create (p, val) pairs for each value
    pairs = [(p, v) for v in values]
    # Distribute pairs evenly across k chunks
    chunks = [pairs[i * len(pairs) // k : (i + 1) * len(pairs) // k] for i in range(k)]
    # Remove empty chunks
    chunks = [c for c in chunks if c]

    all_rows: list[list[int]] = []

    with ctx.Pool(processes=jobs) as pool:
        done = 0
        for chunk_rows in pool.imap_unordered(_worker, chunks, chunksize=1):
            all_rows.extend(chunk_rows)
            done += 1
            print(f"{(100*done)//len(chunks)}% done, {time.time()-t0:.1f}s since start")

    all_rows.sort(key=lambda r: r[0])  # sort by n

    out_path = os.path.join(out_dir, f"ads_{p}_{n}_every_{i}.csv")
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(HEADER)
        w.writerows(all_rows)

    return out_path
