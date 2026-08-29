"""Walking skeleton: national GB pipeline, end to end, on synthetic layers.

Run this before touching a real dataset. It exercises grid construction,
CRS handling, exclusion masking, normalisation, pillar scoring, LAD
aggregation and rendering — so when you swap synthetic layers for real
ones, any failure is in the data rather than in the pipeline.

    python skeleton.py

Writes out/map.html. Open it and look at it. Looking at the map is the
actual test: a pipeline that runs clean and produces a misaligned map is
exactly the failure this guards against.
"""

import time

import numpy as np

from sp.grid import build_grid
from sp.score import Model
from sp.render import web_map


def synthetic(grid, seed, scale=300_000):
    """Stand-in for a real criterion: a smooth spatial gradient.

    Smooth on purpose — a real orientation bug shows up immediately as a
    pattern running the wrong way, which random noise would hide.
    """
    h, w = grid.shape
    ys, xs = np.mgrid[0:h, 0:w].astype("float32")
    rng = np.random.default_rng(seed)
    ax, ay = rng.uniform(-1, 1, 2)
    arr = (ax * xs * grid.cell_size + ay * ys * grid.cell_size) / scale
    arr[~grid.land] = np.nan
    return arr


def synthetic_exclusion(grid, seed, n=40, radius_cells=12):
    """Stand-in for flood zones: scattered blobs. Replace with burn()."""
    rng = np.random.default_rng(seed)
    h, w = grid.shape
    mask = np.zeros(grid.shape, dtype=bool)
    land_idx = np.argwhere(grid.land)
    picks = land_idx[rng.choice(len(land_idx), n, replace=False)]
    ys, xs = np.mgrid[0:h, 0:w]
    for cy, cx in picks:
        r = radius_cells * rng.uniform(0.5, 1.5)
        mask |= ((ys - cy) ** 2 + (xs - cx) ** 2) < r * r
    return mask & grid.land


def main():
    t0 = time.time()
    grid = build_grid(cell_size=1000)
    print(f"grid {grid.shape} | {grid.n_land:,} land cells | "
          f"{len(grid.lad_names)} LADs | {time.time()-t0:.1f}s")

    m = Model(grid)
    m.exclude("flood", synthetic_exclusion(grid, seed=1))
    m.exclude("protected", synthetic_exclusion(grid, seed=2, n=25))

    # Four criteria across all four pillars, with mixed directions so the
    # direction handling is genuinely exercised rather than assumed.
    m.add("carbon", synthetic(grid, 11), "energy", higher_is_better=False)
    m.add("curtailment", synthetic(grid, 12), "energy", higher_is_better=True)
    m.add("alc", synthetic(grid, 13), "land", higher_is_better=False)
    m.add("water_stress", synthetic(grid, 14), "water", higher_is_better=False)
    m.add("heat_reuse", synthetic(grid, 15), "community", higher_is_better=True)

    print(m.report())

    score = m.score()
    print(f"score range {np.nanmin(score):.3f}-{np.nanmax(score):.3f}")

    top = grid.summarise(score).head(5)
    print("\ntop 5 local authorities (synthetic data, means nothing yet):")
    for _, r in top.iterrows():
        print(f"  {r['lad'][:34]:34s} {r['value']:.3f}  ({int(r['cells'])} cells)")

    t0 = time.time()
    out = web_map({
        "Overall score": score,
        "Energy pillar": m.pillar("energy"),
        "Land pillar": m.pillar("land"),
    }, grid)
    print(f"\nwrote {out} in {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
