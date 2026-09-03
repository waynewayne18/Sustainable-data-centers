"""Turn measured curtailment into a grid layer.

    python3 build_curtailment.py

What it does, in order:

  1. Reads the NESO wind BOA file. A negative BOA_Volume on a wind unit
     is that farm being paid to turn down. Sums those, per farm, over the
     year.
  2. Matches farm names to the REPD sites you already have, which is
     where the coordinates come from.
  3. Writes a review CSV so you can check the matches by eye before you
     believe any of it.
  4. Burns the matched MWh onto the grid and caches it.

It reports coverage **by volume**, not by count. Matching 200 tiny farms
and missing Seagreen would look like a 90% success rate and be useless.

Nothing here touches your existing code. It writes two new files.
"""

import glob
import os
import re
import sys
from difflib import SequenceMatcher

import numpy as np
import pandas as pd
from scipy.ndimage import gaussian_filter

from sp.grid import build_grid

BOA_FILES = [
    "data/raw/boa_2023_24.csv",
    "data/raw/boa_2024_25.csv",
    "data/raw/boa_2025_26.csv",
]
OUT_NPY = "data/processed/curtailment_1300x700_1000_s20.npy"
REVIEW = "out/curtailment_match_review.csv"
SIGMA = 20                       # cells; 20km, matching your wind layer
FUZZY = 0.86                     # name similarity floor

# Words that appear in one name and not the other and carry no identity.
NOISE = re.compile(
    r"\b(wind|farm|windfarm|offshore|onshore|extension|ext|phase|power|"
    r"station|energy|renewables|limited|ltd|plc|the|of|and)\b")


DIRS = {"east", "west", "north", "south",
        "eastern", "western", "northern", "southern"}


def dir_clash(a, b):
    """True if a and b carry different directional tokens — e.g. east vs west."""
    da, db = DIRS & set(a.split()), DIRS & set(b.split())
    return (da or db) and da != db


# Applied before any matching. Keys are the raw Generator_Full_Name as it
# appears in the BOA data; values are exact REPD Site Name spellings.
# A loud OVERRIDE MISS line is printed if the REPD target isn't in the lookup.
OVERRIDE = {
    "Moray Firth Eastern 1": "Moray East",
    "Moray West 1":          "Moray West Offshore Wind Farm Project",
}


def norm(name):
    """Reduce a farm name to its identifying core.

    'Seagreen 2' and 'Seagreen 1' both become 'seagreen', which is what we
    want: they are two BM units at one REPD site, and their curtailment
    should land on the same square.
    """
    s = re.sub(r"\([^)]*\)", " ", str(name).lower())  # strip parentheticals first
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    s = NOISE.sub(" ", s)
    s = re.sub(r"\b[0-9ivx]+\b", " ", s)      # trailing unit numbers
    return " ".join(s.split())


def find_repd():
    """REPD lands under different names depending on how you downloaded it."""
    for pat in ("data/raw/*repd*.csv", "data/raw/*REPD*.csv",
                "data/raw/*renewable*.csv", "data/raw/*.csv"):
        for p in sorted(glob.glob(pat)):
            if "boa_" in os.path.basename(p):
                continue
            try:
                head = pd.read_csv(p, nrows=1, encoding="latin-1",
                                   low_memory=False)
            except Exception:
                continue
            cols = {c.lower().strip() for c in head.columns}
            if any("site name" in c for c in cols) and \
               any("x-coord" in c or "x coord" in c for c in cols):
                return p
    return None


def pick(df, *fragments):
    """Find a column whose name contains any fragment. Fail loudly."""
    for frag in fragments:
        for c in df.columns:
            if frag in c.lower():
                return c
    raise KeyError(f"no column matching {fragments}. Columns present:\n"
                   f"{list(df.columns)}")


def _load_year(path):
    """Return a per-farm curtailment DataFrame for one BOA file.

    Returns columns: key, name, mwh — one row per normalised farm name.
    """
    boa = pd.read_csv(path)
    curt = boa[boa["BOA_Volume"] < 0].copy()
    curt["mwh"] = curt["BOA_Volume"].abs()
    per_unit = (curt.groupby(["Generator_Name", "Generator_Full_Name"])["mwh"]
                    .sum().reset_index())
    per_unit["key"] = per_unit["Generator_Full_Name"].map(norm)
    farms = (per_unit.groupby("key")
                     .agg(mwh=("mwh", "sum"),
                          name=("Generator_Full_Name", "first"))
                     .reset_index())
    return boa, farms


def main():
    missing = [f for f in BOA_FILES if not os.path.exists(f)]
    if missing:
        print("missing BOA files:")
        for f in missing:
            print(f"  {f}")
        return 1

    # ---------------------------------------------------------------- BOA
    # Load each year separately, print per-year totals, then sum and divide
    # by n_years for a mean annual figure. Farms absent in a year contribute
    # 0 to that year's total — the mean is over years, not appearances.
    print("Per-year curtailment:")
    year_frames = []
    for path in BOA_FILES:
        label = (os.path.basename(path)
                 .removeprefix("boa_").removesuffix(".csv").replace("_", "/"))
        boa, yr = _load_year(path)
        yr_total = yr["mwh"].sum()
        print(f"  {label}: {len(boa):,} rows | "
              f"{yr_total:,.0f} MWh across {len(yr)} farms")
        year_frames.append(yr)

    n_years = len(BOA_FILES)
    combined = pd.concat(year_frames)
    farms = (combined.groupby("key")
                     .agg(mwh=("mwh", "sum"),
                          name=("name", "first"))
                     .reset_index())
    farms["mwh"] = farms["mwh"] / n_years          # mean annual
    farms = farms.sort_values("mwh", ascending=False)
    total = farms["mwh"].sum()
    print(f"\nmean annual ({n_years} years): {total:,.0f} MWh across {len(farms)} farms")
    print("\ntop 10 by mean annual volume:")
    for _, r in farms.head(10).iterrows():
        print(f"  {r['mwh']:>12,.0f} MWh  {r['name']}")

    # --------------------------------------------------------------- REPD
    repd_path = find_repd()
    if repd_path is None:
        print("\nCould not find the REPD csv in data/raw/. Set it by hand.")
        return 1
    print(f"\nREPD: {repd_path}")
    repd = pd.read_csv(repd_path, encoding="latin-1", low_memory=False)

    c_name = pick(repd, "site name")
    c_x = pick(repd, "x-coord", "x coord")
    c_y = pick(repd, "y-coord", "y coord")
    c_tech = pick(repd, "technology")

    wind = repd[repd[c_tech].astype(str).str.contains("wind", case=False,
                                                      na=False)].copy()
    wind[c_x] = pd.to_numeric(wind[c_x], errors="coerce")
    wind[c_y] = pd.to_numeric(wind[c_y], errors="coerce")
    wind = wind.dropna(subset=[c_x, c_y])
    wind["key"] = wind[c_name].map(norm)
    print(f"  {len(wind):,} wind sites with coordinates")

    lookup = {}
    for _, r in wind.iterrows():
        lookup.setdefault(r["key"], (r[c_x], r[c_y], r[c_name]))
    keys = list(lookup)

    # -------------------------------------------------------------- match
    rows = []
    for _, f in farms.iterrows():
        k = f["key"]

        # Manual override — applied before any matching.
        if f["name"] in OVERRIDE:
            target = OVERRIDE[f["name"]]
            nk = norm(target)
            if nk in lookup:
                x, y, site = lookup[nk]
                rows.append((f["name"], site, f["mwh"], x, y, 1.0, "override"))
            else:
                print(f"OVERRIDE MISS: '{f['name']}' -> '{target}' "
                      f"(norm: '{nk}') not found in REPD lookup")
                rows.append((f["name"], "", f["mwh"], np.nan, np.nan, 0.0,
                             "UNMATCHED"))
            continue

        if k in lookup:
            x, y, site = lookup[k]
            rows.append((f["name"], site, f["mwh"], x, y, 1.0, "exact"))
            continue
        best, score = None, 0.0
        for cand in keys:
            if dir_clash(k, cand):
                continue
            s = SequenceMatcher(None, k, cand).ratio()
            if s > score:
                best, score = cand, s
        if score >= FUZZY:
            x, y, site = lookup[best]
            rows.append((f["name"], site, f["mwh"], x, y, score, "fuzzy"))
        else:
            rows.append((f["name"], "", f["mwh"], np.nan, np.nan, score,
                         "UNMATCHED"))

    m = pd.DataFrame(rows, columns=["boa_name", "repd_site", "mwh",
                                    "easting", "northing", "score", "how"])
    m = m.sort_values("mwh", ascending=False)
    os.makedirs("out", exist_ok=True)
    m.to_csv(REVIEW, index=False)

    placed = m[m["how"] != "UNMATCHED"]
    print(f"\nmatched {len(placed)}/{len(m)} farms, "
          f"{placed['mwh'].sum() / total:.1%} of curtailed volume")
    print(f"review file: {REVIEW}")

    miss = m[m["how"] == "UNMATCHED"].head(10)
    if len(miss):
        print("\nbiggest unmatched - check these by hand:")
        for _, r in miss.iterrows():
            print(f"  {r['mwh']:>12,.0f} MWh  {r['boa_name']}")

    fuzzy = m[m["how"] == "fuzzy"].head(10)
    if len(fuzzy):
        print("\nfuzzy matches - confirm none are wrong:")
        for _, r in fuzzy.iterrows():
            print(f"  {r['score']:.2f}  {r['boa_name']:<32} -> {r['repd_site']}")

    # --------------------------------------------------------------- burn
    grid = build_grid(boundary_path="data/raw/lad.json") \
        if os.path.exists("data/raw/lad.json") else build_grid()

    acc = np.zeros(grid.shape, "float64")
    inv = ~grid.transform
    n_in = 0
    for _, r in placed.iterrows():
        col, row = inv * (r["easting"], r["northing"])
        col, row = int(col), int(row)
        if 0 <= row < grid.shape[0] and 0 <= col < grid.shape[1]:
            acc[row, col] += r["mwh"]        # += not =, farms share squares
            n_in += 1
    print(f"\nplaced {n_in} farms inside the grid")
    if n_in == 0:
        print("  nothing landed. The REPD coordinates are probably not BNG.")
        return 1

    # Smooth before masking to land, so offshore curtailment reaches the
    # coast. That is the whole point - the power comes ashore.
    surf = gaussian_filter(acc, sigma=SIGMA)
    if surf.max() > 0:
        surf = surf / surf.max()
    surf = surf.astype("float32")

    os.makedirs("data/processed", exist_ok=True)
    np.save(OUT_NPY, surf)
    print(f"saved {OUT_NPY}")

    # ------------------------------------------------------------- sanity
    on_land = surf[grid.land]
    north = np.zeros(grid.shape, bool)
    rows_i = np.arange(grid.shape[0])
    for i in rows_i:
        _, n = grid.transform * (0, i + 0.5)
        north[i, :] = n > 600_000
    share = acc[north].sum() / acc.sum() if acc.sum() else 0
    print(f"\nland mean {on_land.mean():.4f}, max {on_land.max():.4f}")
    print(f"{share:.1%} of curtailed volume is north of northing 600km")
    print("  (if that is not most of it, check the coordinates)")

    best = np.unravel_index(np.argmax(np.where(grid.land, surf, 0)),
                            grid.shape)
    lad = grid.lad_names[grid.lad_id[best] - 1] if grid.lad_id[best] else "?"
    print(f"highest land cell sits in: {lad}")
    return 0


if __name__ == "__main__":
    sys.exit(main())