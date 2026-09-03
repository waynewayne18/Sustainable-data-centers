"""Water stress layer, from the EA's 2021 determination.

Source: Environment Agency, "Water stressed areas - final classification
2021", 1 July 2021. The report is a PDF/ODT with two lists of company
names. There is no table to join, so the lists are transcribed here and
matched to the water company boundary file by (COMPANY, AreaServed).

Scope: England only. The EA says so explicitly - "The assessment of water
stress only covers England." Scotland and Wales have no equivalent
determination, so cells there stay unknown rather than being filled in.

What the layer is honestly measuring
------------------------------------
The EA states this determination exists solely to decide whether a company
may charge by metered volume, and "must not be used for other purposes
such as development planning". So do not present this as a hydrological
constraint. Present it as: these are the areas government has formally
determined to be under serious water stress, and 84% of proposed data
centres are going into them anyway. That is a governance point, and it is
the one that survives scrutiny.

Boundaries you still need
-------------------------
The CSV export of the water company dataset is the attribute table only -
FID, COMPANY, AreaServed, Shape__Area, no geometry. Shape__Area is a
number, not a shape; you cannot burn it. Re-export the same layer as
GeoJSON or shapefile and point BOUNDARY at that.

    python3 -c "import sp.waterstress as w; print(w.check(w.BOUNDARY))"
"""

import os

import numpy as np

from sp.layers import burn_cached

BOUNDARY = "data/raw/water_company_areas.geojson"

# Seriously water stressed. Number is the figure-1 map reference.
STRESSED = {
    "Affinity Water": 1,
    "Anglian Water - East Anglia": 2,
    "Cambridge Water": 4,
    "Essex and Suffolk Water": 5,
    "Portsmouth Water": 7,
    "SES Water": 8,
    "South East Water": 9,
    "South Staffordshire Water": 10,
    "Southern Water": 11,
    "Severn Trent Water - excluding Chester": 12,
    "Thames Water": 14,
    "Veolia Water": 15,
    "Wessex Water": 17,
    "South West Water - Bournemouth": 19,
    "South West Water - Isles of Scilly": 20,
}

# Determined not seriously water stressed. Kept so the code can tell
# "assessed, and fine" apart from "never assessed" - they are different
# facts and only one of them is a gap.
NOT_STRESSED = {
    "Bristol Water": 3,
    "Northumbrian Water": 6,
    "South West Water - Devon and Cornwall": 13,
    "United Utilities": 16,
    "Yorkshire Water": 18,
    "Dwr Cymru - Herefordshire": 21,
    "Anglian Water - Hartlepool": 22,
    "Severn Trent - Chester zone": 23,
}

# (COMPANY, AreaServed) in the boundary file -> report entry.
#
# The report and the boundary file disagree on names, because trading
# names moved after 2021 and the report splits some companies by zone:
#   Essex and Suffolk Water now trades as Northumbrian Water. Its Essex
#     and Suffolk zones are stressed; Northumbria is not. Matching on
#     company name alone would mark the whole north east stressed.
#   Cambridge Water is inside the South Staffordshire group. Both are
#     stressed, so this one is harmless, but it is still a rename.
#   Bristol Water is inside South West Water. Not stressed, while South
#     West Water's Bournemouth zone is. Company-name matching gets this
#     backwards in both directions.
# This is why the join is on the pair, not on the company.
JOIN = {
    ("Affinity Water", "Three Valleys"):                  "Affinity Water",
    ("Affinity Water", "Folkestone (Dour)"):              "Affinity Water",
    ("Affinity Water", "Tendring Hundred (Brett)"):       "Affinity Water",
    ("Anglian Water", "Anglian"):                         "Anglian Water - East Anglia",
    ("Anglian Water", "Hartlepool"):                      "Anglian Water - Hartlepool",
    ("Northumbrian Water", "Essex"):                      "Essex and Suffolk Water",
    ("Northumbrian Water", "Suffolk"):                    "Essex and Suffolk Water",
    ("Northumbrian Water", "Northumbria"):                "Northumbrian Water",
    ("Portsmouth Water", "Portsmouth"):                   "Portsmouth Water",
    ("SES Water", "Sutton & East Surrey"):                "SES Water",
    ("South East Water", "Kent & Sussex"):                "South East Water",
    ("South East Water", "Southern"):                     "South East Water",
    ("South Staffordshire Water", "Cambridge"):           "Cambridge Water",
    ("South Staffordshire Water", "South Staffordshire"): "South Staffordshire Water",
    ("Southern Water", "Hampshire"):                      "Southern Water",
    ("Southern Water", "Sussex"):                         "Southern Water",
    ("Southern Water", "Medway"):                         "Southern Water",
    ("Southern Water", "Hastings"):                       "Southern Water",
    ("Southern Water", "Thanet"):                         "Southern Water",
    ("Southern Water", "Isle of Wight"):                  "Southern Water",
    ("Severn Trent Water", "Severn Trent"):               "Severn Trent Water - excluding Chester",
    ("Severn Trent Water", "Chester"):                    "Severn Trent - Chester zone",
    ("Thames Water", "London"):                           "Thames Water",
    ("Thames Water", "Guildford"):                        "Thames Water",
    ("Thames Water", "SWOX plus"):                        "Thames Water",
    ("Wessex Water", "Wessex"):                           "Wessex Water",
    ("South West Water", "Bournemouth"):                  "South West Water - Bournemouth",
    ("South West Water", "Isles of Scilly"):              "South West Water - Isles of Scilly",
    ("South West Water", "South West"):                   "South West Water - Devon and Cornwall",
    ("South West Water", "Bristol"):                      "Bristol Water",
    ("United Utilities", "United Utilities"):             "United Utilities",
    ("Yorkshire Water", "Yorkshire"):                     "Yorkshire Water",
}

# In the boundary file, absent from the report. Wales is outside the
# determination's scope; Fawley transferred to South West Water without a
# separate determination. Left unknown on purpose - a guess here would be
# invisible in the output.
OUT_OF_SCOPE = {
    ("Hafren Dyfrdwy", "Hafren Dyfrdwy"),
    ("Dwr Cymru", "Dwr Cymru"),
    ("South West Water", "Fawley"),
}


def _norm(s):
    """Names arrive with stray whitespace and mangled accents."""
    return " ".join(str(s).replace("µ", "w").split()).strip()


def _read(path):
    import pyogrio
    gdf = pyogrio.read_dataframe(path)
    for col in ("COMPANY", "AreaServed", "AreaType"):
        if col not in gdf.columns:
            raise KeyError(f"{path} has no column {col!r}. Columns: "
                           f"{list(gdf.columns)}")
    # 397 of 432 rows are 'inset' - tiny new-appointment sites, mostly
    # Independent Water Networks estates. Far below 1km. Dropped.
    return gdf[gdf["AreaType"] != "inset"].copy()


def check(path=BOUNDARY):
    """Report how the join lands, without touching the grid.

    Run this before burning anything. It is the cheap version of the
    mistake: an unmatched area silently becomes not-stressed, and a whole
    water company quietly drops out of the map.
    """
    if not os.path.exists(path):
        return f"missing: {path}\nSee the module docstring - you need the geometry, not the CSV."

    gdf = _read(path)
    if gdf.geometry.isna().all():
        return (f"{path} has no geometry. This is the attribute-table "
                "export. Re-export as GeoJSON or shapefile.")

    unmatched, counts = [], {"stressed": 0, "not": 0, "out of scope": 0}
    for _, r in gdf.iterrows():
        key = (_norm(r["COMPANY"]), _norm(r["AreaServed"]))
        if key in OUT_OF_SCOPE:
            counts["out of scope"] += 1
        elif key not in JOIN:
            unmatched.append(key)
        elif JOIN[key] in STRESSED:
            counts["stressed"] += 1
        else:
            counts["not"] += 1

    seen = {JOIN[(_norm(r["COMPANY"]), _norm(r["AreaServed"]))]
            for _, r in gdf.iterrows()
            if (_norm(r["COMPANY"]), _norm(r["AreaServed"])) in JOIN}
    no_boundary = sorted((set(STRESSED) | set(NOT_STRESSED)) - seen)

    lines = [f"{len(gdf)} company areas: " +
             ", ".join(f"{v} {k}" for k, v in counts.items())]
    if unmatched:
        lines.append("UNMATCHED - these would silently read as not stressed:")
        lines += [f"    {c} / {a}" for c, a in unmatched]
    if no_boundary:
        lines.append("in the report, no boundary found: " + ", ".join(no_boundary))
    return "\n".join(lines)


def water_stress(grid, path=BOUNDARY):
    """Return (stressed, assessed) as two boolean arrays on the grid.

    stressed  cell is in an area determined seriously water stressed
    assessed  cell is in any area the 2021 determination covered

    Two arrays, not one, because `not stressed` and `never assessed` are
    different claims. A single array collapses Scotland into 'fine',
    which is exactly the England-only gap CLAUDE.md says not to hide.
    """
    gdf = _read(path)
    gdf["COMPANY"] = gdf["COMPANY"].map(_norm)
    gdf["AreaServed"] = gdf["AreaServed"].map(_norm)

    pairs = list(zip(gdf["COMPANY"], gdf["AreaServed"]))
    entry = [JOIN.get(p) for p in pairs]

    gdf["_stressed"] = [1 if e in STRESSED else 0 for e in entry]
    gdf["_assessed"] = [0 if e is None else 1 for e in entry]

    stressed = burn_cached(grid, gdf[gdf["_stressed"] == 1], "water_stressed")
    assessed = burn_cached(grid, gdf[gdf["_assessed"] == 1], "water_assessed")
    return stressed.astype(bool), assessed.astype(bool)


if __name__ == "__main__":
    print(check())