"""Interactive site map — England only, wind-scored.

Score is proximity to operational wind capacity. Checkboxes are land-use
constraints applied on top. Tick one and watch the count drop — that's
the demo.

    python3 sites_demo.py

Writes out/sites.html.
"""

import numpy as np

from sp.grid import build_grid
from sp.layers import burn_cached, england_mask, distance_from_protected
from sp.score import Model
from sp.sites import pick_sites
from sp.sitemap import site_map
from sp.waterstress import water_stress

ALC = "data/raw/alc.geojson"
CURTAILMENT_NPY = "data/processed/curtailment_1300x700_1000_s20.npy"


def main():
    grid = build_grid()
    print(f"grid {grid.shape} | {grid.n_land:,} land cells")

    eng = england_mask(grid)
    print(f"England land cells: {eng.sum():,}")

    m = Model(grid)
    m.exclude("national_parks", burn_cached(grid, "data/raw/natural_parks.geojson"))
    m.exclude("sssi",           burn_cached(grid, "data/raw/sssi.geojson"))
    m.exclude("flood", burn_cached(
        grid, "data/raw/floodmaps",
        layer="Flood_Zones_2_3_Rivers_and_Sea",
        chunk=50_000,
    ))
    # Restrict to England: ALC, flood zones and other layers are England-only;
    # Scottish/Welsh sites would be immune to every checkbox, which is dishonest.
    m.exclude("non_england", ~eng)

    # Score: measured curtailment volume (MWh, NESO BOA 2025/26), already
    # normalised 0–1 and Gaussian-smoothed to sigma=20km. Curtailment is
    # better information than capacity: it measures what the grid actually
    # cannot absorb, not what was installed.
    curtailment = np.where(grid.land, np.load(CURTAILMENT_NPY), np.nan)
    m.add("curtailment", curtailment, "energy", higher_is_better=True)

    print(m.report())
    score = m.score()

    # Load the already-cached exclusion masks so we can reuse them for the
    # buffer distance — no re-burning, just reading from data/processed/.
    parks = burn_cached(grid, "data/raw/natural_parks.geojson")
    sssi  = burn_cached(grid, "data/raw/sssi.geojson")

    best_farmland = burn_cached(grid, ALC, where={"ALC_GRADE": ["Grade 1", "Grade 2"]})

    # High curtailment: top quartile of the curtailment surface among land cells.
    curt_land = curtailment[np.isfinite(curtailment)]
    thresh = float(np.percentile(curt_land, 75))
    print(f"\nhigh_curtailment threshold: {thresh:.4f} "
          f"(75th percentile, {curt_land.size:,} land cells)")
    high_curtailment = np.isfinite(curtailment) & (curtailment >= thresh)
    print(f"  {high_curtailment.sum():,} cells qualify "
          f"({high_curtailment.sum() / grid.n_land:.1%} of land)")

    stressed, assessed = water_stress(grid)
    # Cells outside England are unassessed — they pass the filter rather than
    # being treated as stressed. Only assessed English cells can fail it.
    outside_water_stress = ~stressed | ~assessed | ~eng

    flags = {
        "High curtailment":                   high_curtailment,
        "Avoids best farmland":               ~best_farmland & eng,
        "At least 2km from protected land":   distance_from_protected(
            grid, parks, sssi, min_dist_m=2000),
        "Outside a water-stressed area (England)": outside_water_stress,
    }

    sites = pick_sites(grid, score, n=5000, min_km=5, flags=flags)
    print(f"\npicked {len(sites)} sites, min 5km apart")
    for s in sites[:6]:
        tag = f"  [{', '.join(s['flags'])}]" if s["flags"] else "  [fails farmland]"
        print(f"  #{s['rank']:2d} {s['council'][:26]:26s} {s['score']:.3f}{tag}")

    out = site_map(
        sites, flags, grid,
        title="Common Ground",
        subtitle="",
        captions={
            "Outside a water-stressed area (England)": (
                "Environment Agency determination 2021. "
                "England only — Scotland and Wales have no equivalent assessment."
            ),
        },
    )
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
