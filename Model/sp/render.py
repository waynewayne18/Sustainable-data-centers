"""Render a score surface as a lightweight web map.

A national 1km grid is ~230,000 land cells. Shipped as GeoJSON polygons
that is well over 100MB and no browser will render it. As a colour-mapped
PNG warped to WGS84 and laid over a basemap, it is a few hundred KB.

This is the reason the whole pipeline is raster rather than vector.
"""

import numpy as np
from rasterio.warp import calculate_default_transform, reproject, Resampling

from .grid import BNG


def to_png(arr, path, cmap="viridis", vmin=None, vmax=None):
    """Colour-map an array to RGBA PNG, transparent where NaN."""
    import matplotlib
    matplotlib.use("Agg")
    from PIL import Image

    # matplotlib.colormaps is the API from 3.6 onward; cm.get_cmap was
    # removed in 3.9. Support both so this doesn't depend on whose laptop
    # it runs on.
    try:
        colormap = matplotlib.colormaps[cmap]
    except (AttributeError, KeyError):
        from matplotlib import cm
        colormap = cm.get_cmap(cmap)

    finite = np.isfinite(arr)
    vmin = np.nanmin(arr) if vmin is None else vmin
    vmax = np.nanmax(arr) if vmax is None else vmax

    norm = np.zeros(arr.shape, dtype="float32")
    if vmax > vmin:
        norm[finite] = (arr[finite] - vmin) / (vmax - vmin)

    rgba = (colormap(norm) * 255).astype("uint8")
    rgba[..., 3] = np.where(finite, 210, 0)

    Image.fromarray(rgba, mode="RGBA").save(path)
    return path


def warp_to_wgs84(arr, grid):
    """Reproject a BNG array to EPSG:4326 for web display.

    Returns (array, [[south, west], [north, east]]) ready for an
    image overlay.
    """
    src_h, src_w = grid.shape
    xmin, ymax = grid.transform.c, grid.transform.f
    xmax = xmin + src_w * grid.cell_size
    ymin = ymax - src_h * grid.cell_size

    dst_transform, dst_w, dst_h = calculate_default_transform(
        BNG, "EPSG:4326", src_w, src_h, xmin, ymin, xmax, ymax
    )

    dst = np.full((dst_h, dst_w), np.nan, dtype="float32")
    reproject(
        source=arr.astype("float32"), destination=dst,
        src_transform=grid.transform, src_crs=BNG,
        dst_transform=dst_transform, dst_crs="EPSG:4326",
        resampling=Resampling.nearest, src_nodata=np.nan, dst_nodata=np.nan,
    )

    west, north = dst_transform.c, dst_transform.f
    east = west + dst_w * dst_transform.a
    south = north + dst_h * dst_transform.e

    return dst, [[south, west], [north, east]]


def web_map(layers, grid, path="out/map.html", cmap="viridis"):
    """Build a folium map with one toggleable overlay per named layer.

    layers: dict of {display name: 2D array on `grid`}
    """
    import os
    import folium

    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    img_dir = os.path.join(os.path.dirname(path) or ".", "tiles")
    os.makedirs(img_dir, exist_ok=True)

    m = folium.Map(location=[54.5, -3.0], zoom_start=6, tiles="CartoDB positron")

    for i, (name, arr) in enumerate(layers.items()):
        warped, bounds = warp_to_wgs84(arr, grid)
        png = os.path.join(img_dir, f"layer_{i}.png")
        to_png(warped, png, cmap=cmap)
        folium.raster_layers.ImageOverlay(
            image=png, bounds=bounds, opacity=0.8, name=name,
        ).add_to(m)

    folium.LayerControl(collapsed=False).add_to(m)
    m.save(path)
    return path
