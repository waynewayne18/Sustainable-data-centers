# Stranded Power

A model that scores every 1km square of Great Britain for how suitable it
is to build a data centre, then picks specific candidate sites.

Built for the UK Parliament hackathon, 4 September 2026. Judged by
policymakers. Working demos count for more than slides.

## What the project argues

Two things are true at once, and nobody has put them on the same map.

1. Britain pays wind farms to switch off because the grid can't carry
   northern power south. Scottish curtailment cost £343m in 2025; total
   constraint costs have passed £1bn.
2. 84% of proposed UK data centres are going into water-stressed areas,
   mostly in the South East.

So clean power is wasted in one place while resources are strained in
another. The model shows where facilities should go instead, and the gap
between that and where they're actually going is the argument.

The economic framing matters more than the environmental one here.
Constraint payments land on consumer bills, so this is a bill-payer
argument, not just a carbon one.

## The finding we're chasing

A 2026 paper in *Land* built a national UK suitability surface and
concluded **Lincolnshire**. It scored climate and infrastructure. It never
scored agricultural land quality.

Lincolnshire contains some of the best arable land in England.

**The Lincolnshire test:** load the agricultural land classification, clip
to Lincolnshire, look at the grade distribution. If the published optimum
sits on Grade 1 and 2 farmland, the headline is that the published answer
puts data centres on England's best farmland because the model that
produced it never priced food security.

This is the highest-value thing to verify. Not yet done.

Position the project as extending published work, never as inventing it.

## Architecture — do not change without asking

**Raster, not vector.** The grid is a numpy array. Every layer is a numpy
array of the same shape. Vector data is burned onto the grid on ingest.

Measured, not assumed:

| Approach | 1km grid over GB | Land-mask join |
|---|---|---|
| Vector polygons in a GeoDataFrame | 793,484 cells | did not finish in 10 min |
| Rasterised numpy arrays | 230,044 land cells | 0.63 s |

A GeoDataFrame of cells is easier to read and is not viable nationally.
If you find yourself suggesting one, don't.

**EPSG:27700 everywhere.** British National Grid is metric, so 1000 units
is 1km with no projection maths at the call site. Convert on ingest.

**`higher_is_better` is mandatory on `Model.add()` and has no default.**
An inverted layer produces a confident, completely wrong map and raises
nothing. It looks like an oversight worth tidying. It isn't.

**Pillars combine last.** Four themes — energy, land, water, community —
scored separately, combined only at the end. This keeps trade-offs visible
instead of buried in one number, and it survives the question "what if I
weight it differently".

**The demo must work offline.** Venue wifi is assumed unusable. The site
map builds its panel before touching Leaflet and wraps the map in a
try/catch, so a network failure loses the map but not the counts, filters
or shortlist. Don't undo that ordering.

## Already considered and rejected

Don't suggest these back:

- **SAR change detection** to find sites under construction. Cut. Real
  preprocessing burden, noisy results, and planning applications are
  better evidence.
- **Three-region scope.** Was needed when SAR was in scope. National is
  now cheap, so the model runs nationally.
- **Digimap** for base data. Its licence is education-only, which would
  encumber the project commercially. Everything used is open licensed.
- **A chatbot over the map.** Adds nothing, and judges see through it.
- **ML to predict the score.** Circular — the score is already computed
  deterministically.

## Where AI is used

The scoring model is arithmetic, not AI, and shouldn't be described as AI.

1. **Planning application extraction.** An LLM reads planning application
   text and pulls out structured facts: is this a data centre, capacity,
   cooling method, water use. Not yet built.
2. **Revealed preference.** Train a model on ~570 known data centre
   locations to learn what actually drives siting, then contrast with what
   the normative model says should. The gap quantifies the externality
   argument. Not yet built.

## The objection everything rests on

"Data centres need low latency, that's why they cluster near London."

Answer: AI training is latency-insensitive — batch jobs running for weeks.
Inference needs to be near users; training doesn't. Don't make changes
that quietly assume otherwise.

## Layout

```
sp/grid.py     raster grid, land mask, LAD attribution, burn() for vectors
sp/score.py    Model: exclusions, normalisation, pillar scoring
sp/render.py   WGS84 reprojection, PNG overlays, folium heat map
sp/sites.py    pick candidate sites with spatial thinning
sp/sitemap.py  interactive site map with constraint checkboxes
skeleton.py    end-to-end run, heat map output
sites_demo.py  end-to-end run, site map output
data/raw/      downloads land here, never edited in place
out/           generated output, safe to delete
```

## Two kinds of layer

**Exclusions** are boolean. The cell is unavailable — flood zone, national
park. No score, removed. `Model.exclude(name, bool_array)`.

**Criteria** are continuous. Normalised to 0–1 where 1 is always the good
end. `Model.add(name, array, pillar, higher_is_better=...)`.

Raw values stay in `Model.raw` so any result can be traced back.

## Scope, stated deliberately

**Great Britain, not the UK.** Northern Ireland is on the Irish Grid with
separate data agencies. Excluded on purpose — say so rather than hiding it.

**Several layers are England-only** — agricultural land classification,
flood zones, indices of deprivation. Scotland and Wales have equivalents
from different bodies that are not interchangeable. Cells outside England
will have gaps. Do not silently fill them; marking gaps is more credible
than pretending uniform coverage.

**1km is regional screening, not site selection.** The model can say a
district merits investigation. It cannot say build here.

## Current state

The pipeline runs end to end on **synthetic data**. `synthetic()` and
`synthetic_exclusion()` in `skeleton.py` are the stand-ins.

The task now is replacing them with real layers, one at a time, checking
the map after each. Build order is in README.md.

## Conventions

- Never add two layers before rendering and looking at the output.
- Downloads go to `data/raw/` and are not edited in place.
- Don't fetch the boundary file over the network once a local copy exists.
- Every data source must be openly licensed and permit commercial reuse.
- Prefer clear code over clever code. People are reading this under time
  pressure.

## Testing a change

```bash
python3 skeleton.py      # heat map -> out/map.html
python3 sites_demo.py    # site map -> out/sites.html
```

Expect `230,044 land cells`. If that number moves, something is wrong with
the grid or the boundary file.
