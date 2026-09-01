"""Download layers from ArcGIS FeatureServer endpoints, with caching.

Most Defra, Environment Agency and Natural England layers are published as
ArcGIS FeatureServers rather than as files. That is not a problem — the
REST query endpoint returns GeoJSON. It just needs paging, because servers
cap how many features they return per request (usually 1000 or 2000).

This fetches the whole layer, pages through it, and caches the result to
disk so you only pay the download once.

Finding the URL: open the dataset page, look for the ArcGIS REST service
link, and take the part ending in /FeatureServer/0. If the page offers a
direct download instead, just use that — this is for when it doesn't.
"""

import json
import os
import time

import geopandas as gpd
import requests

from .grid import BNG


def fetch_arcgis(url, cache_path, page=1000, out_srs=27700, where="1=1",
                 timeout=60, refresh=False):
    """Pull an entire FeatureServer layer to a local GeoJSON file.

    url         .../FeatureServer/0  (no /query on the end)
    cache_path  where to save; returns immediately if it already exists
    out_srs     27700 asks the server for British National Grid directly,
                which saves a reprojection and avoids a class of error
    """
    if os.path.exists(cache_path) and not refresh:
        print(f"cached: {cache_path}")
        return gpd.read_file(cache_path)

    os.makedirs(os.path.dirname(cache_path) or ".", exist_ok=True)
    query = url.rstrip("/") + "/query"

    count = requests.get(query, params={
        "where": where, "returnCountOnly": "true", "f": "json",
    }, timeout=timeout).json().get("count")
    print(f"features to fetch: {count if count is not None else 'unknown'}")

    features, offset = [], 0
    while True:
        r = requests.get(query, params={
            "where": where,
            "outFields": "*",
            "f": "geojson",
            "outSR": out_srs,
            "resultOffset": offset,
            "resultRecordCount": page,
        }, timeout=timeout)
        r.raise_for_status()

        batch = r.json().get("features", [])
        if not batch:
            break

        features.extend(batch)
        offset += len(batch)
        print(f"  {offset}{'/' + str(count) if count else ''}", end="\r")

        if len(batch) < page:
            break
        time.sleep(0.2)   # be polite to a free public service

    print(f"\nfetched {len(features)} features")

    if not features:
        raise RuntimeError(f"no features returned from {url}")

    with open(cache_path, "w") as f:
        json.dump({
            "type": "FeatureCollection",
            "crs": {"type": "name",
                    "properties": {"name": f"EPSG:{out_srs}"}},
            "features": features,
        }, f)

    gdf = gpd.read_file(cache_path)
    if gdf.crs is None:
        gdf = gdf.set_crs(f"EPSG:{out_srs}")
    if gdf.crs.to_string() != BNG:
        gdf = gdf.to_crs(BNG)

    print(f"saved: {cache_path}  ({len(gdf)} features, {gdf.crs.to_string()})")
    return gdf
