"""Helpers for loading real vector layers onto the grid.

Each function here is a stand-in replacement for a synthetic_exclusion()
or synthetic() call in skeleton.py. Build order follows SPEC.md § Rule 2.
"""

from pathlib import Path

import geopandas as gpd
import numpy as np

from sp.grid import Grid, burn

# Where rasterised arrays are stored between runs.
# data/processed/ survives deletion of out/ — burns are expensive to redo.
_CACHE_DIR = Path("data/processed")


def burn_cached(
    grid: Grid,
    path: str | Path,
    layer: str = None,
    chunk: int = None,
    where: dict = None,
) -> np.ndarray:
    """Rasterise a vector file and cache the result as a .npy array.

    On a warm cache the file read and rasterise step is skipped entirely,
    so repeated runs of skeleton.py stay fast even as real layers accumulate.

    Cache is invalidated whenever the source file is newer than the cached
    array, so editing data/raw/ always picks up the change.

    layer : OGR layer name — required for multi-layer files (e.g. GeoPackage).
    chunk : read this many features at a time; use for large files (>1 GB)
            to avoid loading everything into memory at once. Progress is
            printed to stdout after each chunk.
    where : {column: [values]} — filter rows to those whose column value is
            in the list. Applied per-chunk when chunk is set. Included in the
            cache key so different filters produce different cached arrays.

    Returns a bool array aligned to grid — True where the geometry falls.
    """
    path = Path(path)
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)

    layer_tag = f"_{layer}" if layer else ""
    where_tag = ("_" + "_".join(
        f"{c}-{'|'.join(str(v) for v in sorted(vs))}"
        for c, vs in sorted(where.items())
    )) if where else ""
    key = f"{path.stem}{layer_tag}{where_tag}_{grid.shape[0]}x{grid.shape[1]}_{grid.cell_size}"
    cache_path = _CACHE_DIR / f"{key}.npy"

    if cache_path.exists():
        src_mtime = path.stat().st_mtime
        cache_mtime = cache_path.stat().st_mtime
        if cache_mtime >= src_mtime:
            return np.load(cache_path).astype(bool)

    read_kwargs = dict(layer=layer) if layer else {}

    def _apply_where(gdf):
        if not where:
            return gdf
        mask = np.ones(len(gdf), dtype=bool)
        for col, vals in where.items():
            mask &= gdf[col].isin(vals).values
        return gdf[mask]

    if chunk:
        import pyogrio
        info = pyogrio.read_info(str(path), **read_kwargs)
        n_total = info["features"]
        arr = np.zeros(grid.shape, dtype=bool)
        n_done = 0
        while n_done < n_total:
            gdf_chunk = gpd.read_file(
                path,
                skip_features=n_done,
                max_features=min(chunk, n_total - n_done),
                **read_kwargs,
            )
            arr |= burn(grid, _apply_where(gdf_chunk)).astype(bool)
            n_done += len(gdf_chunk)
            print(f"  {n_done:,} / {n_total:,} features | {arr.sum():,} cells",
                  flush=True)
    else:
        gdf = _apply_where(gpd.read_file(path, **read_kwargs))
        arr = burn(grid, gdf).astype(bool)

    np.save(cache_path, arr)
    return arr


def distance_from_protected(grid: Grid, *bool_arrays: np.ndarray,
                            min_dist_m: float) -> np.ndarray:
    """True where cells are at least min_dist_m from any protected cell.

    Combines all supplied boolean arrays into a single protected-land mask,
    then runs distance_transform_edt on its inverse to get Euclidean distance
    (in cells) to the nearest protected cell. Multiplied by grid.cell_size to
    convert to metres. Returns a land-masked boolean array.

    The input arrays should already be land-masked (e.g. from burn_cached).
    Pass already-cached masks — no file reads happen here.
    """
    from scipy.ndimage import distance_transform_edt

    combined = np.zeros(grid.shape, dtype=bool)
    for arr in bool_arrays:
        combined |= arr.astype(bool)

    dist_m = distance_transform_edt(~combined) * grid.cell_size
    return (dist_m >= min_dist_m) & grid.land


def england_mask(grid: Grid) -> np.ndarray:
    """Boolean mask — True on English land cells, False on sea, Scotland, Wales.

    Identified by matching known Scottish and Welsh council name substrings
    against the LAD names in the boundary file. England has complete coverage
    for ALC, flood zones and the other England-only layers; Scotland and Wales
    do not. Restricting to England means every checkbox bites everywhere.
    """
    _scottish = [
        'Aberdeen', 'Angus', 'Argyll', 'Clackmannan', 'Dumfries', 'Dundee',
        'East Ayr', 'East Dunb', 'East Loth', 'East Renf', 'Edinburgh',
        'Eilean', 'Falkirk', 'Fife', 'Glasgow', 'Highland', 'Inverclyde',
        'Midlothian', 'Moray', 'North Ayr', 'North Lanark', 'Orkney',
        'Perth', 'Renfrewshire', 'Scottish', 'Shetland', 'South Ayr',
        'South Lanark', 'Stirling', 'West Dunb', 'West Loth',
        'Western Isles', 'Comhairle',
    ]
    _welsh = [
        'Blaenau', 'Bridgend', 'Caerphilly', 'Cardiff', 'Carmarthen',
        'Ceredigion', 'Conwy', 'Denbigh', 'Flintshire', 'Gwynedd',
        'Isle of Anglesey', 'Merthyr', 'Monmouth', 'Neath', 'Newport',
        'Pembroke', 'Powys', 'Rhondda', 'Swansea', 'Torfaen',
        'Vale of Glamorgan', 'Wrexham',
    ]
    non_english = set(
        n for n in grid.lad_names
        if any(k in n for k in _scottish + _welsh)
    )
    english_ids = [
        i + 1 for i, n in enumerate(grid.lad_names) if n not in non_english
    ]
    return np.isin(grid.lad_id, english_ids) & grid.land


def distinct(path: str | Path, column: str, layer: str = None) -> list:
    """Return sorted unique values of a column without loading geometries."""
    read_kwargs = dict(layer=layer) if layer else {}
    gdf = gpd.read_file(path, columns=[column], **read_kwargs)
    return sorted(gdf[column].dropna().unique().tolist())


def grade_mask(
    grid: Grid,
    path: str | Path,
    column: str,
    grades: list,
    layer: str = None,
) -> np.ndarray:
    """Burn only features whose `column` value is in `grades`.

    Returns a bool array — True where those features fall on the grid.
    """
    read_kwargs = dict(layer=layer) if layer else {}
    gdf = gpd.read_file(path, **read_kwargs)
    subset = gdf[gdf[column].isin(grades)]
    if subset.empty:
        raise ValueError(f"No features matched grades {grades} in {column!r}")
    return burn(grid, subset).astype(bool)


# Numeric mapping for ALC grades. Non-agricultural, urban and unclassified
# polygons are deliberately absent — they burn as 0 which is then set to NaN.
_ALC_GRADE_TO_NUM = {
    "Grade 1": 1.0,
    "Grade 2": 2.0,
    "Grade 3": 3.0,
    "Grade 4": 4.0,
    "Grade 5": 5.0,
}


def repd_wind(grid: Grid, path: str | Path, sigma: float = 20) -> np.ndarray:
    """Burn operational wind capacity (MW) onto the grid, then Gaussian-smooth.

    Reads the Renewable Energy Planning Database CSV, filters to operational
    wind (onshore + offshore), and burns Installed Capacity (MWelec) at each
    project's BNG coordinates. Cells with multiple projects accumulate their
    capacities (additive merge). The raw point layer is then smoothed with a
    Gaussian kernel (sigma cells) to produce a proximity-to-generation surface.

    After smoothing, sea cells are set to NaN. Land cells with no nearby wind
    will have a small positive value from the kernel tails rather than 0.

    Result is cached in data/processed/; cache is invalidated if the CSV is
    newer than the cached array.
    """
    import pandas as pd
    from rasterio import features, enums
    from scipy.ndimage import gaussian_filter

    path = Path(path)
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    key = (f"repd_wind_{grid.shape[0]}x{grid.shape[1]}"
           f"_{grid.cell_size}_s{int(sigma)}")
    cache_path = _CACHE_DIR / f"{key}.npy"

    if cache_path.exists():
        src_mtime = path.stat().st_mtime
        if cache_path.stat().st_mtime >= src_mtime:
            return np.load(cache_path)

    df = pd.read_csv(path, encoding="latin1")
    wind = df[
        (df["Development Status (short)"] == "Operational") &
        (df["Technology Type"].isin(["Wind Onshore", "Wind Offshore"]))
    ].copy()

    for col in ("X-coordinate", "Y-coordinate", "Installed Capacity (MWelec)"):
        wind[col] = pd.to_numeric(wind[col], errors="coerce")
    wind = wind.dropna(subset=["X-coordinate", "Y-coordinate",
                                "Installed Capacity (MWelec)"])
    print(f"  repd_wind: {len(wind)} operational wind projects, "
          f"{wind['Installed Capacity (MWelec)'].sum():.0f} MW total")

    gdf = gpd.GeoDataFrame(
        wind,
        geometry=gpd.points_from_xy(wind["X-coordinate"], wind["Y-coordinate"]),
        crs="EPSG:27700",
    )

    # Additive rasterise: cells with multiple projects sum their capacities.
    arr = features.rasterize(
        ((g, float(v)) for g, v in
         zip(gdf.geometry, gdf["Installed Capacity (MWelec)"])),
        out_shape=grid.shape,
        transform=grid.transform,
        dtype="float32",
        fill=0.0,
        merge_alg=enums.MergeAlg.add,
    )

    # Smooth to a proximity surface.
    arr = gaussian_filter(arr.astype("float64"), sigma=sigma).astype("float32")
    arr[~grid.land] = np.nan

    np.save(cache_path, arr)
    return arr


def alc_numeric(grid: Grid, path: str | Path) -> np.ndarray:
    """Burn ALC grade as a float layer: 1 = best farmland, 5 = poorest.

    Cells with no ALC data (outside England, urban, non-agricultural) are
    set to NaN and will be skipped by the scoring model rather than scored
    as zero. This is intentional: NaN signals missing data, not low quality.

    Pass to Model.add() with higher_is_better=True so that Grade 4/5
    (poor farmland, lower food-security concern) score highest.
    """
    gdf = gpd.read_file(path)
    gdf = gdf[gdf["ALC_GRADE"].isin(_ALC_GRADE_TO_NUM)].copy()
    gdf["_num"] = gdf["ALC_GRADE"].map(_ALC_GRADE_TO_NUM)
    arr = burn(grid, gdf, value_col="_num")
    arr[arr == 0] = np.nan  # unburned cells have fill=0; set to NaN
    return arr
