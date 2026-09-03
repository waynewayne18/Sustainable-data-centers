"""Check the pipeline produced something sane.

Run after any batch of changes. It rebuilds the grid independently, then
inspects whatever is in data/processed/ and out/, so it works regardless
of how the rest of the code has been edited.

    python3 verify.py

PASS  looks right
WARN  possible, but worth a look
FAIL  definitely wrong

It cannot tell you whether the holes are in the right *places*. Only you
can do that, by opening the map. See the note it prints at the end.
"""

import glob
import os

import numpy as np

GREEN, YELLOW, RED, DIM, OFF = "\033[32m", "\033[33m", "\033[31m", "\033[2m", "\033[0m"

# Rough share of GB land each layer should cover, as a sanity band.
# Wide on purpose — this catches "nothing loaded" and "everything loaded",
# not small errors.
EXPECTED = {
    "parks":     (0.02, 0.15, "National Parks ~10% of England"),
    "sssi":      (0.01, 0.15, "SSSI ~8% of England"),
    "flood":     (0.02, 0.25, "Flood zone follows rivers"),
    "alc":       (0.02, 0.40, "Grade 1+2 farmland"),
    "greenbelt": (0.02, 0.20, "Green Belt ~13% of England"),
}

results = []


def check(label, ok, detail=""):
    tag = {True: f"{GREEN}PASS{OFF}", False: f"{RED}FAIL{OFF}",
           None: f"{YELLOW}WARN{OFF}"}[ok]
    print(f"  {tag}  {label}")
    if detail:
        print(f"        {DIM}{detail}{OFF}")
    results.append(ok)


def check_grid():
    print("\nGRID")
    try:
        from sp.grid import build_grid
    except Exception as e:
        check("sp.grid imports", False, f"{type(e).__name__}: {e}")
        return None

    path = "data/raw/lad.json"
    grid = build_grid(boundary_path=path) if os.path.exists(path) else build_grid()

    check("shape is (1300, 700)", grid.shape == (1300, 700), f"got {grid.shape}")
    check("230,044 land cells", grid.n_land == 230_044,
          f"got {grid.n_land:,}" + ("" if grid.n_land == 230_044
                                    else "  <- boundary file differs"))
    check("380 local authorities", len(grid.lad_names) == 380,
          f"got {len(grid.lad_names)}")
    check("land mask is boolean", grid.land.dtype == bool, f"got {grid.land.dtype}")
    return grid


def check_layers(grid):
    print("\nCACHED LAYERS  (data/processed/)")
    files = sorted(glob.glob("data/processed/*.npy"))

    if not files:
        check("any layers cached", False,
              "nothing in data/processed/ — no real data has been burned yet")
        return

    for f in files:
        name = os.path.basename(f)[:-4]
        arr = np.load(f)

        if arr.shape != grid.shape:
            check(name, False, f"shape {arr.shape} != grid {grid.shape}")
            continue

        if arr.dtype == bool:
            hits = int((arr & grid.land).sum())
        else:
            hits = int((np.isfinite(arr) & (arr != 0) & grid.land).sum())

        share = hits / grid.n_land

        if hits == 0:
            check(name, False, "0 cells on land — the layer loaded but "
                               "nothing landed on the grid. Check the CRS.")
            continue
        if share > 0.85:
            check(name, False, f"{share:.0%} of all land — almost certainly "
                               "burned the wrong thing")
            continue

        band = next((v for k, v in EXPECTED.items() if k in name.lower()), None)
        detail = f"{hits:,} cells, {share:.1%} of GB land"

        if band:
            lo, hi, why = band
            detail += f"  |  expected {lo:.0%}-{hi:.0%} ({why})"
            check(name, lo <= share <= hi or None, detail)
        else:
            check(name, None, detail + "  |  no expected range — check by eye")


def check_outputs():
    print("\nOUTPUT FILES  (out/)")
    for path, floor in (("out/map.html", 100_000), ("out/sites.html", 5_000)):
        if not os.path.exists(path):
            check(path, None, "not generated yet")
            continue
        size = os.path.getsize(path)
        check(path, size >= floor,
              f"{size / 1000:.0f} KB" + ("" if size >= floor
                                         else f"  <- under {floor // 1000}KB, likely empty"))


def main():
    print("=" * 62)
    print("STRANDED POWER — pipeline check")
    print("=" * 62)

    grid = check_grid()
    if grid is not None:
        check_layers(grid)
    check_outputs()

    fails = results.count(False)
    warns = results.count(None)
    print("\n" + "=" * 62)
    print(f"{results.count(True)} passed, {warns} warnings, {fails} failed")

    print(f"""
{DIM}This cannot check the thing that matters most.

Open out/sites.html and out/map.html and look at them. Are the
excluded areas on the Lake District, Snowdonia, Dartmoor? Does
flood risk follow rivers? A pipeline can produce perfectly
plausible numbers from a completely misaligned map.{OFF}""")


if __name__ == "__main__":
    main()
