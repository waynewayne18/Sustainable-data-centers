"""Interactive site map — England only, wind-scored.

Score is proximity to operational wind capacity. Checkboxes are land-use
constraints applied on top. Tick one and watch the count drop — that's
the demo.

    python3 sites_demo.py

Writes out/sites.html.
"""

from sp.grid import build_grid
from sp.layers import burn_cached, grade_mask, repd_wind, england_mask, distance_from_protected
from sp.score import Model
from sp.sites import pick_sites
from sp.sitemap import site_map

ALC = "data/raw/alc.geojson"


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

    # Score: proximity to stranded wind capacity only.
    # ALC is a planning constraint (breach or don't), not a sliding score;
    # it lives as the checkbox below rather than baked into the ranking.
    m.add("wind", repd_wind(grid, "data/raw/repd.csv"), "energy",
          higher_is_better=True)

    print(m.report())
    score = m.score()

    # Load the already-cached exclusion masks so we can reuse them for the
    # buffer distance — no re-burning, just reading from data/processed/.
    parks = burn_cached(grid, "data/raw/natural_parks.geojson")
    sssi  = burn_cached(grid, "data/raw/sssi.geojson")

    best_farmland = grade_mask(grid, ALC, "ALC_GRADE", ["Grade 1", "Grade 2"])
    flags = {
        "Avoids best farmland":           ~best_farmland & eng,
        "At least 2km from protected land": distance_from_protected(
            grid, parks, sssi, min_dist_m=2000),
    }

    sites = pick_sites(grid, score, n=500, min_km=5, flags=flags)
    print(f"\npicked {len(sites)} sites, min 5km apart")
    for s in sites[:6]:
        tag = f"  [{', '.join(s['flags'])}]" if s["flags"] else "  [fails farmland]"
        print(f"  #{s['rank']:2d} {s['council'][:26]:26s} {s['score']:.3f}{tag}")

    out = site_map(
        sites, flags, grid,
        title="Stranded Power",
        subtitle="Best sites for a data centre near stranded wind. "
                 "Tick a requirement — only sites meeting all conditions are shown.",
    )
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
