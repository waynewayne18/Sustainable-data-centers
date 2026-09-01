"""Pick specific candidate sites from a score surface.

A heat map shows a pattern. A list of named sites is a proposal. This
turns the score layer into a shortlist of actual places, each tagged with
which constraints it falls foul of, so the map can filter them live.

The spacing rule matters: without it the top 40 cells are all touching,
because good places are surrounded by other good places. Greedy thinning
keeps the best cell in each area and drops its neighbours.
"""

import numpy as np


def pick_sites(grid, score, n=40, min_km=25, flags=None, shortlist=60000):
    """Return the best n sites, spaced at least min_km apart.

    flags: dict of {label: boolean array} — constraints each site is
    tested against. A site records which flags are True at its location,
    which is what the checkboxes filter on.

    shortlist caps how many high-scoring cells the spacing pass considers.
    Sorting 200k cells then thinning them all is wasted work; the answer
    never comes from outside the top few thousand.
    """
    flags = flags or {}

    valid = np.isfinite(score)
    idx = np.argwhere(valid)
    vals = score[valid]

    order = np.argsort(vals)[::-1][:shortlist]
    idx = idx[order]
    vals = vals[order]

    min_cells = (min_km * 1000) / grid.cell_size
    min_sq = min_cells ** 2

    # Pre-allocated so the distance check doesn't rebuild an array each pass.
    picked = np.empty((n, 2), dtype="int32")
    k = 0
    sites = []

    for (r, c), v in zip(idx, vals):
        if k:
            d2 = (picked[:k, 0] - r) ** 2 + (picked[:k, 1] - c) ** 2
            if d2.min() < min_sq:
                continue

        picked[k] = (r, c)
        k += 1

        east = grid.transform.c + (c + 0.5) * grid.cell_size
        north = grid.transform.f - (r + 0.5) * grid.cell_size
        lad = grid.lad_names[grid.lad_id[r, c] - 1] if grid.lad_id[r, c] else "—"

        sites.append({
            "rank": len(sites) + 1,
            "row": int(r), "col": int(c),
            "easting": float(east), "northing": float(north),
            "score": round(float(v), 3),
            "council": lad,
            "flags": [k for k, a in flags.items() if bool(a[r, c])],
        })

        if len(sites) >= n:
            break

    if len(sites) < n:
        print(f"  note: found {len(sites)} of {n} requested. Either raise "
              f"shortlist= or lower min_km= ({min_km}km is spacing them out).")

    return _add_latlon(sites)


def _add_latlon(sites):
    """Convert BNG eastings/northings to lat/lon for web display."""
    from pyproj import Transformer

    if not sites:
        return sites

    tf = Transformer.from_crs("EPSG:27700", "EPSG:4326", always_xy=True)
    lons, lats = tf.transform(
        [s["easting"] for s in sites],
        [s["northing"] for s in sites],
    )
    for s, lat, lon in zip(sites, lats, lons):
        s["lat"] = round(float(lat), 5)
        s["lon"] = round(float(lon), 5)
    return sites
