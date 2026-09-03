# SPEC — Interactive site finder

Build target for Claude Code. Read alongside CLAUDE.md, which holds the
architecture rules and project context.

## What we are building

One web page. A map of Great Britain showing candidate data centre sites,
with a panel of checkboxes down one side.

Each checkbox is a **requirement**. Tick it, and only sites meeting that
condition remain on the map. Tick several, and a site must satisfy **all**
of them to be shown. This is AND logic, not OR.

With nothing ticked, every candidate site is visible.

## Core behaviour

1. All filtering happens in the browser. Site data is embedded in the page
   as JSON. Ticking a box must feel instant — no server, no recompute.
2. A live count shows how many sites currently qualify, and how many were
   removed.
3. Each site has a popup: rank, local authority, score, and which
   conditions it meets and fails.
4. If no site satisfies every ticked condition, show that clearly as a
   result, not as an error. Wording: "No site in Great Britain satisfies
   all selected conditions." Offer to show the closest matches.

That empty state is a feature. It demonstrates that the constraints are in
genuine tension, which is the whole argument.

## Always excluded

Removed before scoring. Never appear as sites, never get a checkbox.
Offering a tickbox for these implies you could build in a national park.

| Exclusion | Source |
|---|---|
| Flood zone 3 | EA Flood Map for Planning |
| National Parks, AONB | Natural England |
| SSSI, SAC, SPA, Ramsar | Natural England |

## Checkbox requirements

`[P]` marks criteria used by the 2026 *Land* paper, included so results
are directly comparable to published work.

### Energy

| Checkbox | Condition | Source |
|---|---|---|
| Near curtailed wind | In a transmission-constrained zone | Elexon BMRS |
| Low-carbon grid | Regional intensity below median | Carbon Intensity API |
| Spare grid capacity | Connection headroom available | NESO TEC register |
| Near a substation `[P]` | Within threshold distance | NESO / OS |
| Cool climate `[P]` | Mean annual temp below median | Met Office |
| Low humidity `[P]` | Relative humidity below median | Met Office |
| Frost days `[P]` | Air frost days above median | Met Office |
| Solar resource `[P]` | Sunshine hours above median | Met Office |

### Land

| Checkbox | Condition | Source |
|---|---|---|
| Avoids best farmland | Not ALC grade 1 or 2 | Natural England |

> **Note:** The Provisional ALC dataset does not sub-grade Grade 3 into 3a
> and 3b. Claiming "not 3a" would be false precision. Grade 3 land is
> therefore excluded from this filter entirely, which understates the
> constraint — some Grade 3 cells are 3a (good-quality arable) and should
> arguably be protected. A fully sub-graded source would tighten this.
| Avoids Green Belt | Outside designated Green Belt | MHCLG |
| Previously developed | On brownfield land | Brownfield registers / OSM |

### Water

| Checkbox | Condition | Source |
|---|---|---|
| Not water-stressed | Outside stressed areas | EA |
| Protects groundwater | Outside drinking water safeguard zones | EA |
| Outside flood zone 2 `[P]` | Not in flood zone 2 | EA |

### Nature

| Checkbox | Condition | Source |
|---|---|---|
| Avoids ancient woodland | Outside ancient woodland inventory | Natural England |
| Avoids priority habitats | Outside priority habitat inventory | Natural England |

### Community

| Checkbox | Condition | Source |
|---|---|---|
| Buffered from housing | Beyond noise threshold from settlements | ONS population grid |
| Near a heat network | Within reach of a heat network zone | Heat network zones |
| Transport access `[P]` | Within threshold of major road | OS Open Roads |

## Build order for variables — and graceful degradation

All 19 are in scope. Solo, the risk is not inaccuracy, it is arriving with
twelve loaded and seven half-broken.

Two rules make that impossible.

### Rule 1 — a checkbox only exists if its data loaded

Never hard-code the checkbox list. Generate it from whichever layers
actually loaded successfully. If a dataset fails or is not done yet, its
checkbox simply does not render, and everything else works.

This means the page is always shippable. Stopping at any point leaves a
coherent tool rather than a broken one.

### Rule 2 — build in this order

Grouped by cost, not just importance. Some variables are cheap in batches
because they share one source and one download.

**Tier 1 — the argument. Stop here and you still have a full demo.**

| Variable | Source | Notes |
|---|---|---|
| Avoids best farmland | Natural England ALC | The checkbox that makes the point |
| Outside water-stressed areas | EA | Backs the 84% figure |
| Near curtailed wind | Elexon, by GSP group | Energy argument |
| Low-carbon grid | Carbon Intensity API | Free, no download |
| Avoids Green Belt | MHCLG | Cheap |

**Tier 2 — one portal, several layers. Cheap per variable.**

Natural England: ancient woodland, priority habitats.
EA: flood zone 2, drinking water safeguard zones.

**Tier 3 — one source, four variables. Best value in the whole list.**

Met Office climate averages give temperature, humidity, air frost days and
sunshine hours from a single download. Four of the paper's criteria for
roughly the cost of one.

**Tier 4 — real work each, do last.**

Grid connection headroom (NESO TEC), substation proximity, transport
access, housing buffer, heat network proximity, previously developed land.

### The stop line

After Tier 1 you have a working tool that makes the complete argument.
Everything after that is accuracy, not viability. Judge remaining time
against that line, not against the total.

## UI requirements

Nineteen checkboxes in a flat list is a tax form, not a tool. Structure:

- **Collapsible groups** — Energy, Land, Water, Nature, Community. Energy
  and Land open by default; the rest collapsed.
- Each group header shows how many of its boxes are ticked.
- Each checkbox shows, greyed, how many sites currently meet it. This
  tells the user which condition is about to cost them.
- **Site count is the hero element.** Large, prominent, animates on change.
  Below it: "N of M sites qualify".
- **Reset button** clears all conditions.
- **Site list** below the filters, ranked, clicking one pans the map to it.
- Markers sized by score. Clicking opens a popup with the full breakdown.

### Visual direction

Modern, restrained, and readable on a projector from the back of a room.

- Dark UI panel, light or dark map tiles — commit to one and be consistent.
- One accent colour for interactive elements and markers. No rainbow.
- System font stack or a single clean sans. No decorative type.
- Generous spacing. Checkbox rows need a large tap target.
- Numbers in a monospace face so counts don't jitter when they change.
- Transitions under 200ms. This is a tool, not an animation showcase.
- Must work at 1280×800 and on a phone.

## Non-negotiable: it works offline

Venue wifi is assumed unusable.

- Build the panel and bind the checkbox handlers **before** any mapping
  library call.
- Wrap map initialisation in try/catch. If it fails, show a message in the
  map area and keep counts, filters and the site list fully working.
- Vendor the mapping library and its CSS locally. No CDN at run time.
- Embed all site data in the page. No fetch calls.

Test by disabling networking and reloading. Everything except the base
map tiles must still work.

## Data pipeline

Python produces the site data; the page only filters it.

1. Build the national 1km grid (`sp/grid.py`).
2. Apply hard exclusions.
3. Load each variable as a layer, burned onto the grid.
4. Score each cell (`sp/score.py`).
5. Pick candidate sites with spatial thinning (`sp/sites.py`).
6. For each site, evaluate every checkbox condition to true/false.
7. Write sites plus their condition results into the page as JSON.

Site records need: rank, lat, lon, easting, northing, score, local
authority, per-pillar scores, and a map of condition name to boolean.

## Handling missing data

Agricultural land classification, flood zones and the deprivation indices
are England-only. Scotland and Wales have equivalents from different
agencies that are not interchangeable.

A site outside England has **unknown**, not false, for those conditions.
Do not silently treat unknown as passing or failing.

Show it: mark such sites distinctly and say so in the popup. Being visibly
honest about coverage gaps reads as more rigorous, not less.

## Acceptance criteria

- [ ] Nothing ticked shows all sites.
- [ ] Ticking one condition reduces the count and removes the right sites.
- [ ] Ticking several applies AND logic, not OR.
- [ ] Ticking everything either shows a small set or a clear empty state.
- [ ] Every count in the UI matches the visible markers.
- [ ] Reset restores the full set.
- [ ] Page works with networking disabled, minus base map tiles.
- [ ] Readable at 1280×800 and usable on a phone.
- [ ] Sites outside England show unknown, not false, for England-only data.
- [ ] A variable whose data failed to load produces no checkbox, and the
      rest of the page works normally.

## Build order

Work in this sequence. Each step should leave a page that runs.

1. Flip the existing site map from exclusion logic to requirement logic.
2. Group the checkboxes and add counts per group.
3. Add hard exclusions using real Natural England and EA data.
4. Add the Land group conditions — farmland grade first.
5. Add Water, then Energy, then Nature, then Community.
6. Vendor the mapping library locally.
7. Polish the UI against the visual direction above.

Add one variable at a time and check the map after each. Never add two
before looking at the output.
