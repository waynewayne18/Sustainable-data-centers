"""Report what is in every file in data/raw/.

Run this before loading anything into the pipeline. It tells you the layer
names, coordinate system, feature count and column names for each file —
which is exactly what you need to know before writing the loading code,
and exactly what people guess wrong.

    python3 inspect_data.py
"""

import glob
import os

import geopandas as gpd

VECTOR_EXT = (".gpkg", ".geojson", ".json", ".shp", ".gml", ".gdb")


def layers_in(path):
    """Layer names in a file, or [None] for formats with a single layer."""
    try:
        import pyogrio
        return [l[0] for l in pyogrio.list_layers(path)]
    except Exception:
        try:
            import fiona
            return list(fiona.listlayers(path))
        except Exception:
            return [None]


def describe(path):
    print(f"\n{'=' * 68}\n{os.path.basename(path)}  "
          f"({os.path.getsize(path) / 1e6:.1f} MB)")

    names = layers_in(path)
    if names != [None]:
        print(f"layers: {names}")

    for name in names:
        try:
            gdf = gpd.read_file(path, layer=name, rows=200)
        except Exception as e:
            print(f"  [{name}] FAILED: {type(e).__name__} {str(e)[:90]}")
            continue

        crs = gdf.crs.to_string() if gdf.crs else "NONE — will need setting"
        label = f"  [{name}] " if name else "  "
        print(f"{label}crs={crs}")
        print(f"{' ' * len(label)}geometry={gdf.geom_type.unique().tolist()}")
        print(f"{' ' * len(label)}columns={[c for c in gdf.columns if c != 'geometry'][:10]}")

        # Full count separately — reading 200 rows above keeps this fast on
        # large files like flood zones.
        try:
            import pyogrio
            info = pyogrio.read_info(path, layer=name)
            print(f"{' ' * len(label)}features={info['features']:,}")
        except Exception:
            pass


def main():
    files = sorted(
        f for f in glob.glob("data/raw/**/*", recursive=True)
        if f.lower().endswith(VECTOR_EXT)
    )

    if not files:
        print("Nothing found in data/raw/. Unzip your downloads there first.")
        return

    print(f"found {len(files)} vector file(s) in data/raw/")
    for f in files:
        describe(f)

    print(f"\n{'=' * 68}")
    print("Next: note the layer name and CRS for each. You need both when")
    print("loading. A CRS of NONE means you must set it manually — check")
    print("the dataset's documentation rather than guessing.")


if __name__ == "__main__":
    main()
