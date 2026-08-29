"""National raster grid on British National Grid.

Architecture note, and it matters:

At regional scale you can hold cells as shapely polygons in a GeoDataFrame.
At national scale you cannot. A 1km vector grid over GB is ~793,000 polygons,
and a single spatial join against the coastline did not finish in 10 minutes.
The same operation as a rasterisation takes 0.63 seconds.

So the grid is a numpy array, layers are numpy arrays, and vector data is
burned into arrays on ingest. Everything downstream is array arithmetic.

Everything is EPSG:27700. It is metric, so a 1000-unit cell is 1km with no
projection maths at the call site.
"""

from dataclasses import dataclass

import geopandas as gpd
import numpy as np
from rasterio import features
from rasterio.transform import from_origin

BNG = "EPSG:27700"

# GB extent in BNG metres. Covers Land's End to Shetland.
# Northern Ireland is deliberately out of scope: it sits on the Irish Grid,
# and its planning, flood and land data come from entirely different agencies.
EXTENT = (0, 0, 700_000, 1_300_000)

BOUNDARY_URL = (
    "https://raw.githubusercontent.com/martinjc/UK-GeoJSON/master/"
    "json/administrative/gb/lad.json"
)


@dataclass
class Grid:
    """A national raster grid plus the masks every layer is aligned to."""

    transform: object
    shape: tuple
    land: np.ndarray          # bool, True where land
    lad_id: np.ndarray        # uint16, 0 = sea, else index into lad_names+1
    lad_names: list
    cell_size: int

    @property
    def n_land(self):
        return int(self.land.sum())

    def empty(self, fill=np.nan, dtype="float32"):
        """A new layer array aligned to this grid."""
        return np.full(self.shape, fill, dtype=dtype)

    def summarise(self, arr, stat="mean"):
        """Aggregate an array to local authority level.

        This is how results get reported to anyone political. 'Your
        constituency scores in the top decile' lands; 'grid cell 4471'
        does not.
        """
        import pandas as pd

        rows = []
        for i, name in enumerate(self.lad_names, start=1):
            sel = (self.lad_id == i) & self.land & np.isfinite(arr)
            if not sel.any():
                continue
            v = arr[sel]
            rows.append({
                "lad": name,
                "cells": int(sel.sum()),
                "value": float(getattr(np, stat)(v)),
            })
        return pd.DataFrame(rows).sort_values("value", ascending=False)


def build_grid(cell_size: int = 1000, boundary_path: str = BOUNDARY_URL) -> Grid:
    """Rasterise the GB coastline into a land mask and LAD attribution."""
    lad = gpd.read_file(boundary_path).to_crs(BNG)

    name_col = next(
        (c for c in ("LAD13NM", "lad13nm", "name", "NAME") if c in lad.columns),
        None,
    )
    names = (
        lad[name_col].astype(str).tolist()
        if name_col
        else [f"lad_{i}" for i in range(len(lad))]
    )

    xmin, ymin, xmax, ymax = EXTENT
    shape = ((ymax - ymin) // cell_size, (xmax - xmin) // cell_size)
    transform = from_origin(xmin, ymax, cell_size, cell_size)

    land = features.rasterize(
        ((g, 1) for g in lad.geometry),
        out_shape=shape, transform=transform, dtype="uint8",
    ).astype(bool)

    lad_id = features.rasterize(
        ((g, i) for i, g in enumerate(lad.geometry, start=1)),
        out_shape=shape, transform=transform, dtype="uint16",
    )

    return Grid(transform, shape, land, lad_id, names, cell_size)


def burn(grid: Grid, gdf: gpd.GeoDataFrame, value_col: str = None) -> np.ndarray:
    """Rasterise a vector layer onto the grid.

    With value_col, burns that attribute. Without, burns 1 where any
    geometry falls — which is what an exclusion mask needs.
    """
    if gdf.crs is None:
        raise ValueError("layer has no CRS; refusing to guess")
    if gdf.crs.to_string() != BNG:
        gdf = gdf.to_crs(BNG)

    invalid = ~gdf.geometry.is_valid
    if invalid.any():
        gdf = gdf.copy()
        gdf.loc[invalid, "geometry"] = gdf.loc[invalid, "geometry"].buffer(0)

    pairs = (
        ((g, v) for g, v in zip(gdf.geometry, gdf[value_col]))
        if value_col
        else ((g, 1) for g in gdf.geometry)
    )

    return features.rasterize(
        pairs, out_shape=grid.shape, transform=grid.transform,
        dtype="float32", fill=0,
    )
