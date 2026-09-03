"""Interactive site map — England only, wind-scored.

Score is proximity to operational wind capacity. Checkboxes are land-use
constraints applied on top. Tick one and watch the count drop — that's
the demo.

    python3 sites_demo.py

Writes out/sites.html.
"""

import numpy as np
import pandas as pd

from sp.grid import build_grid
from sp.layers import burn_cached, england_mask
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

    # Near curtailed wind: cells within 50km of any farm that recorded curtailment.
    # Coordinates from the matched review CSV — no percentile, no smoothing.
    from scipy.ndimage import distance_transform_edt as _edt
    _farms = pd.read_csv("out/curtailment_match_review.csv")
    _farms = _farms[_farms["how"] != "UNMATCHED"]
    _inv = ~grid.transform
    _farm_mask = np.zeros(grid.shape, dtype=bool)
    for _, _r in _farms.iterrows():
        _c, _w = _inv * (_r["easting"], _r["northing"])
        _c, _w = int(_c), int(_w)
        if 0 <= _w < grid.shape[0] and 0 <= _c < grid.shape[1]:
            _farm_mask[_w, _c] = True
    _dist_m = _edt(~_farm_mask) * grid.cell_size
    near_curtailed_wind = (_dist_m <= 50_000) & grid.land
    print(f"\nnear_curtailed_wind: {near_curtailed_wind.sum():,} land cells within 50km "
          f"({near_curtailed_wind.sum() / grid.n_land:.1%} of land)")

    stressed, assessed = water_stress(grid)
    # Cells outside England are unassessed — they pass the filter rather than
    # being treated as stressed. Only assessed English cells can fail it.
    outside_water_stress = ~stressed | ~assessed | ~eng

    far_from_sssi   = (_edt(~sssi)  * grid.cell_size >= 2000) & grid.land
    far_from_parks  = (_edt(~parks) * grid.cell_size >= 2000) & grid.land
    print(f"far_from_wildlife_sites:    {far_from_sssi.sum():,} land cells "
          f"({far_from_sssi.sum() / grid.n_land:.1%})")
    print(f"far_from_protected_landscape: {far_from_parks.sum():,} land cells "
          f"({far_from_parks.sum() / grid.n_land:.1%})")

    flags = {
        "Within 50km of a curtailed wind farm":       near_curtailed_wind,
        "Avoids best farmland":                        ~best_farmland & eng,
        "At least 2km from a protected wildlife site": far_from_sssi,
        "At least 2km from a protected landscape":     far_from_parks,
        "Outside a water-stressed area (England)":     outside_water_stress,
    }

    sites = pick_sites(grid, score, n=10000, min_km=5, shortlist=250_000, flags=flags)
    print(f"\npicked {len(sites)} sites, min 5km apart")
    for s in sites[:6]:
        tag = f"  [{', '.join(s['flags'])}]" if s["flags"] else "  [fails farmland]"
        print(f"  #{s['rank']:2d} {s['council'][:26]:26s} {s['score']:.3f}{tag}")

    out = site_map(
        sites, flags, grid,
        title="Common Ground",
        subtitle="Model coverage: England. Curtailment analysis: Great Britain.",
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
