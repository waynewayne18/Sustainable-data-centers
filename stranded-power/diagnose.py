"""Show where each cached layer points, geographically.

When the answer clusters somewhere unexpected, this tells you which layer
is responsible. It reads only the cached arrays and the grid, so it works
whatever shape the rest of the pipeline is in.

    python3 diagnose.py

For each layer it reports the councils that score highest on it. If one
layer's top councils are Cornwall and Devon, that layer is your answer —
and if it's your only scored criterion, it is deciding everything.
"""

import glob
import os

import numpy as np

from sp.grid import build_grid

CACHE_DIRS = ("data/processed", "out/cache", "cache")
DIM, BOLD, OFF = "\033[2m", "\033[1m", "\033[0m"


def find_caches():
    files = []
    for d in CACHE_DIRS:
        files += sorted(glob.glob(os.path.join(d, "*.npy")))
    return files


def top_councils(grid, arr, n=6):
    """Councils ranked by mean value of this layer, ignoring empty ones."""
    rows = []
    for i, name in enumerate(grid.lad_names, start=1):
        sel = (grid.lad_id == i) & grid.land
        if sel.sum() < 20:                     # skip tiny authorities
            continue
        vals = arr[sel]
        vals = vals[np.isfinite(vals)]
        if len(vals) == 0:
            continue
        rows.append((float(vals.mean()), name, int(sel.sum())))
    rows.sort(reverse=True)
    return rows[:n], rows[-n:]


def main():
    local = "data/raw/lad.json"
    grid = build_grid(boundary_path=local) if os.path.exists(local) else build_grid()
    print(f"grid {grid.shape} | {grid.n_land:,} land cells\n")

    files = find_caches()
    if not files:
        print("No cached layers found. Nothing to diagnose.")
        return

    for f in files:
        name = os.path.basename(f)[:-4]
        arr = np.load(f).astype("float32")

        if arr.shape != grid.shape:
            print(f"{BOLD}{name}{OFF}  SKIPPED — shape {arr.shape} != {grid.shape}\n")
            continue

        on_land = arr[grid.land]
        on_land = on_land[np.isfinite(on_land)]

        kind = "mask" if set(np.unique(on_land)) <= {0.0, 1.0} else "values"
        print(f"{BOLD}{name}{OFF}  ({kind}, "
              f"range {on_land.min():.3g}–{on_land.max():.3g}, "
              f"mean {on_land.mean():.3g})")

        high, low = top_councils(grid, arr)

        print(f"  {DIM}highest{OFF}")
        for v, lad, cells in high:
            print(f"    {v:7.3f}  {lad[:32]:32s} {DIM}{cells} cells{OFF}")
        print(f"  {DIM}lowest{OFF}")
        for v, lad, cells in reversed(low):
            print(f"    {v:7.3f}  {lad[:32]:32s} {DIM}{cells} cells{OFF}")
        print()

    print(f"""{DIM}How to read this.

A mask layer shows what share of each council it covers.
A values layer shows the average value there.

If your sites are landing somewhere unexpected, find the layer whose
"highest" list matches that place. That layer is driving the result.

If only one layer is a scored criterion, it decides everything — the
exclusion layers only remove squares, they never rank them.{OFF}""")


if __name__ == "__main__":
    main()
