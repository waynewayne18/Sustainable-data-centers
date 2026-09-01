# Tools, packages and data sources

Everything needed for the site finder. All data is openly licensed and
permits commercial reuse.

## Install

```bash
python3 -m pip install -r requirements.txt
```

### Core packages

| Package | Purpose |
|---|---|
| `geopandas` | Reading vector data, coordinate systems |
| `rasterio` | Rasterisation, reprojection |
| `shapely` | Geometry operations |
| `pyproj` | Projections, BNG to lat/lon |
| `numpy` | Every layer is one of these |
| `pandas` | Tabular joins, local authority summaries |
| `requests` | Every API below |
| `openpyxl` | Government data ships as .xlsx surprisingly often |
| `matplotlib` | Colour mapping |
| `pillow` | PNG output |

### Optional

| Package | Needed for |
|---|---|
| `osmnx` | OpenStreetMap brownfield and industrial land |
| `anthropic` | LLM extraction from planning applications |
| `jupyterlab` | Inspecting layers interactively |
| `playwright` | Automated checks that the page actually works |

No system GDAL install required — modern `rasterio` and `geopandas`
wheels bundle it.

### Front end

| Tool | Notes |
|---|---|
| Leaflet | Map rendering. **Vendor locally, do not use a CDN.** |
| CARTO basemap tiles | Optional. Needs network, so the page must work without it. |

## APIs — live, keyed

| API | Auth | Use |
|---|---|---|
| [Carbon Intensity](https://www.carbonintensity.org.uk/) | None | Regional grid carbon, half-hourly |
| [Elexon Insights](https://developer.data.elexon.co.uk/) | None | Curtailment and constraint events |

Neither needs a key. Elexon state plainly that all their APIs are public.
The older BMRS API required a scripting key; that is no longer the case.

Endpoints you need:

```
# curtailment — bid-offer acceptances
https://data.elexon.co.uk/bmrs/api/v1/datasets/BOALF
  ?from=2025-06-01T00:00Z&to=2025-06-02T00:00Z&format=json

# what each generating unit is
https://data.elexon.co.uk/bmrs/api/v1/reference/bmunits/all
```

**The known trap.** BOALF tells you which units were curtailed, not where
they are. Unit reference data gives fuel type and lead party, not reliable
coordinates. Mapping unit IDs to physical locations is the single most
likely thing to consume an entire evening.

Score curtailment by **GSP group** instead — the grid supply point regions
the system is already divided into. Published boundaries, every unit
belongs to one, and the Carbon Intensity API uses the same geography, so
two energy variables share one set of boundaries. Coarser, defensible, and
twenty minutes rather than four hours.

Attempt precise generator locations only if everything else is done.

## Which format to download

Most of these portals offer the same layer several ways. Pick in this
order:

| Format | Use it? | Why |
|---|---|---|
| **GeoPackage (.gpkg)** | **First choice** | Binary, compact, geopandas reads it natively, keeps CRS correctly, can hold several layers in one file |
| Shapefile (.shp) | Fine | Works everywhere, but splits across 4+ files and truncates field names to 10 characters |
| GeoJSON | Only if small | Plain text and very verbose. A national layer can unzip to many times the GeoPackage size and load slowly |
| File Geodatabase (.gdb) | Avoid | Readable but needs the right driver and is fussier |
| Layer file (.lyr) | Never | Esri styling only. Contains no data |

A GeoPackage can hold several layers. List them before loading:

```python
import pyogrio
pyogrio.list_layers("data/raw/Flood_Map_for_Planning_Flood_Zones.gpkg")
```

Then load the one you want:

```python
gpd.read_file(path, layer="<name from the list>")
```

### Flood zones specifically

Download `Flood_Map_for_Planning_Flood_Zones.gpkg.zip` from the dataset
page. It holds zones 2 and 3 as separate layers.

This is the most detailed dataset in the project — the polygons follow
every watercourse in England. Loading it takes a minute or two and burning
it to the grid a little longer. That is normal, it happens once per run,
and afterwards it is a 1300×700 boolean array and instant.

## Data downloads

Download once into `data/raw/`. Do not fetch over the network on every run.

### Boundaries and base mapping

| Dataset | Source | Licence |
|---|---|---|
| Local authority boundaries | [UK-GeoJSON](https://github.com/martinjc/UK-GeoJSON) | Open |
| OS Open Zoomstack | [OS Data Hub](https://osdatahub.os.uk/downloads/open) | OGL |
| OS Boundary-Line | OS Data Hub | OGL |
| OS Open Roads | OS Data Hub | OGL |

### Land

| Dataset | Source | Licence |
|---|---|---|
| Agricultural Land Classification | [Natural England](https://naturalengland-defra.opendata.arcgis.com/) | OGL |
| Green Belt | MHCLG via data.gov.uk | OGL |
| Brownfield registers | data.gov.uk | OGL |

### Water

| Dataset | Source | Licence |
|---|---|---|
| Flood Map for Planning (zones 2, 3) | [environment.data.gov.uk](https://environment.data.gov.uk/) | OGL |
| Water-stressed areas | Environment Agency | OGL |
| Drinking Water Safeguard Zones | [data.gov.uk](https://www.data.gov.uk/dataset/7fe90245-d6e8-4d7c-a13a-65a87455f429/drinking-water-safeguard-zones-groundwater) | OGL |

### Nature

| Dataset | Source | Licence |
|---|---|---|
| SSSI | Natural England | OGL |
| SAC, SPA, Ramsar | Natural England | OGL |
| National Parks, AONB | Natural England | OGL |
| Ancient Woodland Inventory | Natural England | OGL |
| Priority Habitat Inventory | Natural England | OGL |

### Energy

| Dataset | Source | Licence |
|---|---|---|
| TEC register | [NESO](https://www.neso.energy/data-portal/transmission-entry-capacity-tec-register) | Open |
| Substation locations | NESO / OS | Open |

### Climate

| Dataset | Source | Licence |
|---|---|---|
| Temperature, humidity, frost days, sunshine | Met Office climate averages | OGL |

### Community

| Dataset | Source | Licence |
|---|---|---|
| Population grid | ONS | OGL |
| Heat network zones | DESNZ | OGL |
| Indices of Deprivation | gov.uk | OGL |

## Deliberately not used

**Digimap.** Licensed for education and non-commercial use only, which
would encumber the project if it goes anywhere after the hackathon.
Everything above is OGL, CC BY or equivalent and permits commercial reuse.

Worth one line in the methods note: every data source is openly licensed
and permits commercial reuse. It quietly answers a due-diligence question
nobody then has to ask.

## Download order

Front-load anything large. No registrations block you — both APIs are
open, so nothing here has a waiting time.

1. Local authority boundaries — needed by the grid on first run.
2. Natural England exclusions — parks, SSSI, designations.
3. Flood zones — large files, start these early.
4. Agricultural Land Classification.
5. GSP group boundaries — shared by the curtailment and carbon variables.
6. Everything else, as each variable is added.
