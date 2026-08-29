# Stranded Power — national starter skeleton

A working end-to-end pipeline over the whole of Great Britain, running on
synthetic layers. Verified:

```
grid (1300, 700) | 230,044 land cells | 380 LADs | 4.7s
land 230,044 cells | excluded 31,349 | available 198,695 | criteria 5 across 4 pillars
score range 0.311-0.673
wrote out/map.html in 0.9s

real 0m7.416s
```

Whole country, seven seconds, 600KB of output.

## Run it

```
open out/map.html
pip3 install geopandas rasterio folium matplotlib pillow
python3 skeleton.py
```

Open `out/map.html` **and look at it**. Looking at the map is the test.
A pipeline that runs clean and produces a misaligned map is exactly the
failure this guards against.

## Why raster, not vector

This is the architectural decision the whole project rests on, and it was
measured rather than assumed:

| Approach | 1km grid over GB | Land-mask join |
|---|---|---|
| Vector polygons in GeoDataFrame | 793,484 cells | **did not finish in 10 min** |
| Rasterised numpy arrays | 230,044 land cells | **0.63 s** |

Rendering shows the same gap. National 1km cells as GeoJSON polygons is
well over 100MB and no browser will draw it. As a colour-mapped PNG warped
to WGS84 and overlaid on a basemap, it is 84KB per layer.

So: the grid is a numpy array, every layer is a numpy array aligned to it,
and vector data is burned into arrays on ingest via `burn()`. Everything
downstream is array arithmetic.

If someone proposes going back to a GeoDataFrame of cells "because it's
easier to reason about" — it is, right up until the first national join.

## Layout

```
sp/grid.py     raster grid, land mask, LAD attribution, vector burning
sp/score.py    Model: exclusions, normalisation, pillar scoring
sp/render.py   reprojection to WGS84, PNG overlays, folium map
skeleton.py    end-to-end run on synthetic layers
data/raw/      downloads land here, never edited in place
out/           rendered maps and overlay images
```

## Scope

**Great Britain, not the UK.** Northern Ireland sits on the Irish Grid and
its planning, flood and land data come from entirely separate agencies. It
is excluded deliberately, not accidentally — say so if asked.

Watch the other coverage boundary too: agricultural land classification,
flood zones and the deprivation indices are **England-only**. Scotland and
Wales have equivalents from different bodies that are not directly
interchangeable. The grid covers GB, so cells outside England will simply
have no data for those layers. Decide early whether you populate them,
scope to England, or mark them as incomplete on the map. Marking them is
the honest option and it looks more rigorous, not less.

## Replacing the synthetic parts

Two functions in `skeleton.py` are stand-ins. Swap them one at a time,
re-running and looking at the map after each.

**`synthetic_exclusion()`** →

```python
import geopandas as gpd
from sp.grid import burn
flood = gpd.read_file("data/raw/flood_zone_3.gpkg")
m.exclude("flood", burn(grid, flood) > 0)
```

`burn()` already reprojects to BNG, repairs invalid geometries, and
rasterises onto the exact grid. Nothing else changes.

**`synthetic()`** → a real criterion array, however you derive it.

Keep the `higher_is_better=` argument exactly as it is at every call site.
It is mandatory with no default on purpose: an inverted layer produces a
confident, completely wrong map and raises nothing anywhere.

## Build order

1. Real flood zones replacing the synthetic exclusion. Look at the map.
2. Remaining exclusions — protected sites, Green Belt.
3. First real criterion: carbon intensity. Simple API, regional values,
   no spatial complexity — exercises the scoring path cleanly.
4. Remaining criteria one at a time, looking at the map after each.
5. Pillar aggregation once every input is individually verified.
6. Planning-application overlay from Intelligence.

Never add two layers before rendering. Finding a misalignment with two
layers loaded takes minutes; with twelve it takes an evening.

## Reporting to politicians

`grid.summarise(array)` aggregates any layer to local authority level and
returns a ranked DataFrame. Use it. "Your local authority is in the top
decile" lands in a way "grid cell 4471" never will, and the LAD attribution
raster costs 0.35s to build.

## Interfaces

The `Model` class fixes what other roles build against:

| Thing | Meaning |
|---|---|
| `grid.land` | bool array, True on land |
| `grid.lad_id` | uint16, 0 = sea, else index into `grid.lad_names` + 1 |
| `m.exclusions[name]` | bool array per exclusion |
| `m.raw[(pillar, name)]` | criterion before normalisation, kept for auditing |
| `m.criteria[(pillar, name)]` | normalised 0–1, 1 always better |
| `m.pillar(name)` | weighted mean of that pillar |
| `m.score()` | combined surface, NaN outside available cells |

Application builds against these. Change them and tell them first.
