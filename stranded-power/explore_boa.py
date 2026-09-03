"""Step 1 of the curtailment join. Look before you write code against it.

    python3 explore_boa.py

Downloads the NESO wind BOA volumes for one year and the Elexon BMU
reference list, then prints what is actually in them. Nothing is burned,
nothing is cached, nothing is joined. The only job is to find out the
column names, because every line of the real module depends on them and
guessing wrong costs an hour.

Read the output, then tell me what it says.
"""

import io
import json
import os
import sys
import urllib.request

YEAR = "2025_26"                       # change if this year is thin
OUT = "data/raw"

NESO_PKG = ("https://api.neso.energy/api/3/action/"
            "datapackage_show?id=wind-bmu-boa-volumes")
ELEXON_BMU = "https://data.elexon.co.uk/bmrs/api/v1/reference/bmunits/all"

HEAD = {"User-Agent": "Mozilla/5.0 (research; single request)"}


def get(url, timeout=120):
    req = urllib.request.Request(url, headers=HEAD)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def preview(name, raw, n=6):
    """Print the header and first few rows of a CSV without pandas."""
    text = raw.decode("utf-8-sig", errors="replace")
    lines = text.splitlines()
    print(f"\n--- {name} : {len(lines):,} lines ---")
    for line in lines[:n]:
        print("   ", line[:220])


def main():
    os.makedirs(OUT, exist_ok=True)

    # 1. Find the CSV for the chosen year.
    print("Fetching the NESO data package...")
    try:
        pkg = json.loads(get(NESO_PKG))
    except Exception as e:
        print(f"  failed: {type(e).__name__}: {e}")
        print("  Open https://www.neso.energy/data-portal/wind-bmu-boa-volumes")
        print("  in a browser, download a year's CSV to data/raw/, and rerun")
        print("  with BOA_LOCAL set to that path.")
        return 1

    resources = pkg["result"]["resources"]
    print(f"  {len(resources)} resources:")
    for r in resources:
        print(f"    {r.get('name', '?'):<28} {r.get('path', '')}")

    match = [r for r in resources if YEAR in str(r.get("path", ""))
             or YEAR in str(r.get("name", ""))]
    if not match:
        print(f"\n  nothing matching {YEAR}. Pick a path from the list above "
              f"and set YEAR to that year.")
        return 1

    url = match[0]["path"]
    print(f"\nDownloading {url}")
    boa = get(url)
    path = os.path.join(OUT, f"boa_{YEAR}.csv")
    with open(path, "wb") as f:
        f.write(boa)
    print(f"  saved {len(boa) / 1e6:.1f} MB to {path}")
    preview("BOA volumes", boa)

    # 2. The BMU reference list, which is what turns an ID into a name.
    print("\nFetching the Elexon BMU reference list...")
    try:
        ref = get(ELEXON_BMU)
    except Exception as e:
        print(f"  failed: {type(e).__name__}: {e}")
        print("  Not fatal - the BOA file may carry names already. Check the")
        print("  preview above.")
        return 0

    path = os.path.join(OUT, "bmunits.json")
    with open(path, "wb") as f:
        f.write(ref)
    data = json.loads(ref)
    rows = data if isinstance(data, list) else data.get("data", [])
    print(f"  saved {len(ref) / 1e6:.1f} MB to {path}, {len(rows):,} units")
    if rows:
        print("  fields:", sorted(rows[0].keys()))
        wind = [r for r in rows
                if "WIND" in str(r.get("fuelType", "")).upper()]
        print(f"  {len(wind):,} wind units. First few:")
        for r in wind[:6]:
            print("   ", {k: r[k] for k in list(r)[:6]})

    print("\nNow paste the two previews back to me.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
