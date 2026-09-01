"""Interactive site map on synthetic data.

Same pipeline as skeleton.py, but instead of a heat map it picks specific
candidate sites and lets you rule them out with checkboxes.

    python3 sites_demo.py

Writes out/sites.html. Tick a constraint and watch the count fall — that
falling number is the demo.
"""

import numpy as np

from sp.grid import build_grid
from sp.score import Model
from sp.sites import pick_sites
from sp.sitemap import site_map
from skeleton import synthetic, synthetic_exclusion


def main():
    grid = build_grid()
    print(f"grid {grid.shape} | {grid.n_land:,} land cells")

    m = Model(grid)
    m.exclude("flood", synthetic_exclusion(grid, seed=1))
    m.exclude("protected", synthetic_exclusion(grid, seed=2, n=25))

    m.add("carbon", synthetic(grid, 11), "energy", higher_is_better=False)
    m.add("curtailment", synthetic(grid, 12), "energy", higher_is_better=True)
    m.add("alc", synthetic(grid, 13), "land", higher_is_better=False)
    m.add("water_stress", synthetic(grid, 14), "water", higher_is_better=False)
    m.add("heat_reuse", synthetic(grid, 15), "community", higher_is_better=True)

    print(m.report())
    score = m.score()

    # Constraint flags. Each becomes a checkbox. Replace these thresholds
    # with real tests once real layers are loaded — e.g. ALC grade <= 3a
    # for "on the best farmland".
    flags = {
        "On the best farmland":
            m.raw[("land", "alc")] > np.nanpercentile(m.raw[("land", "alc")], 65),
        "In a water-stressed area":
            m.raw[("water", "water_stress")] > np.nanpercentile(
                m.raw[("water", "water_stress")], 60),
        "Far from any heat customer":
            m.raw[("community", "heat_reuse")] < np.nanpercentile(
                m.raw[("community", "heat_reuse")], 40),
        "On a high-carbon grid":
            m.raw[("energy", "carbon")] > np.nanpercentile(
                m.raw[("energy", "carbon")], 55),
    }

    sites = pick_sites(grid, score, n=40, min_km=25, flags=flags)
    print(f"\npicked {len(sites)} sites, min 25km apart")
    for s in sites[:6]:
        tag = f"  [{', '.join(s['flags'])}]" if s["flags"] else ""
        print(f"  #{s['rank']:2d} {s['council'][:26]:26s} {s['score']:.3f}{tag}")

    out = site_map(
        sites, flags,
        title="Stranded Power",
        subtitle="Best sites in Great Britain for a data centre. "
                 "Tick a constraint to rule out sites that breach it.",
    )
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
