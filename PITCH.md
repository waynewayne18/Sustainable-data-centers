# Common Ground — pitch

Three minutes. Say it, don't read it. The demo does the work; your job is
to set it up and get out of the way.

---

## 0:00 — Open (25s)

> We're about to build a generation of data centres in this country. The
> question isn't whether — it's what they cost.
>
> And right now that decision is being made on land price, grid connection
> and planning risk. Not on whether the site is our best farmland. Not on
> whether the water is already over-committed. Not on whether the power is
> clean.
>
> So I built the map that prices those things.

**Pause.** Don't touch the laptop yet.

---

## 0:25 — What it is (20s)

> Common Ground scores every square kilometre of Great Britain — two
> hundred and thirty thousand of them — against the environmental
> constraints that should govern where these things go. Farmland quality.
> Flood risk. Protected landscapes. Water stress. And whether the
> electricity nearby is clean power currently being thrown away.
>
> All of it live, running in the page.

---

## 0:45 — Demo (85s)

Talk while you click. Slower than feels natural.

**Full map.**
> Every candidate site after hard exclusions. Flood zones, National Parks,
> Sites of Special Scientific Interest — those are gone before anything is
> scored. Not weighted. Gone.

**Tick "avoids the best farmland."**
> Agricultural Land Classification grades one and two — our most productive
> arable land. There's a published national study that identifies the
> optimum region for UK data centres and never scored farmland at all. A
> fifth of my shortlist just disappeared.

**Tick "at least 2km from protected landscape."**
> Impacts don't stop at the boundary fence. Two kilometres is the screening
> distance in air quality guidance for nationally important sites.

**Tick "outside a water-stressed area."**
> This is the Environment Agency's formal 2021 determination — not my
> judgement, the government's. Nearly sixty per cent of England is
> classified as seriously water stressed. Watch what survives.

**Let the count sit. Say nothing for two seconds.**

**Coordinates tab.**
> And it isn't just a picture. Every surviving site has a grid reference.
> That downloads as a spreadsheet.

**Open `out/available.png`.**
> One thing I want to show you. These white channels are river flood zones
> — actual river networks. These grey patches are the Lake District,
> Dartmoor, the South Downs. You cannot get that picture from misaligned
> data. That's how I know the constraints are real and not decorative.

---

## 2:10 — The carbon argument (30s)

> Now the energy side, and this is the part that surprised me.
>
> Britain pays wind farms to switch off, because the network can't carry
> their output south. That power doesn't disappear — gas stations are paid
> to make up the difference. Carbon Tracker put one recent year of this at
> around one point three million tonnes of CO2.
>
> I read the actual curtailment volumes the system operator publishes.
> Two hundred and seventy-seven thousand records. Ninety-six point six per
> cent of it is north of the main transmission constraint.
>
> Measured. Not assumed.

---

## 2:40 — The limitation, said first (20s)

> One honest thing. The environmental layers — farmland grades, flood
> zones, water stress — only exist for England. Scotland has equivalents
> from different bodies that aren't interchangeable. So the map covers
> England.
>
> Which is the finding. The places with the clean power going to waste are
> the places we can't yet screen on the same terms. That's a data gap
> sitting underneath a national infrastructure decision.

Say this before anyone asks. It turns your biggest gap into your sharpest
point.

---

## 3:00 — Close (15s)

> This doesn't tell you where to build. At a kilometre it can't. It tells
> you which districts are worth looking at, and exactly what you'd be
> giving up if you chose one.
>
> And the same siting that protects the farmland and the water uses power
> we're currently paying to waste. The environmental answer and the cheaper
> answer are the same answer. That's the whole point.
>
> Every source is open. It's all on GitHub. Thank you.

---

# Questions

**"Doesn't latency mean data centres have to be near London?"**
> Inference does. Training doesn't — those are batch jobs running for
> weeks. The build-out driving demand right now is training capacity, and
> it's the least latency-sensitive load on the grid.

**"Aren't the water claims about data centres overstated?"**
> Some of the reporting is contested, which is why I don't argue from
> consumption figures. I argue from the Environment Agency's formal
> determination of which areas are under serious water stress. That's a
> government classification, not an estimate.

**"How do you know that power is being wasted?"**
> Bid-offer acceptance volumes from NESO — the volume each wind farm was
> paid to stop generating. I matched those to physical locations through
> the planning database and placed 97.9% of the national volume.

**"Being near a curtailed wind farm doesn't mean you can use that power."**
> Completely right. That needs co-location, a private wire, or local
> network headroom. The model finds where clean power is stranded — the
> connection arrangement is a separate question, and a harder one.

**"Isn't a kilometre too coarse?"**
> Yes, for siting. It's regional screening. It says a district merits
> investigation and what the trade-offs are. It cannot say build here, and
> I don't claim it does.

**"So is this the most environmentally friendly location?"**
> It's the most defensible one on the constraints we can measure. It
> doesn't price embodied carbon, biodiversity net gain, or construction
> impact — and I'd rather say that than pretend the model is complete.
> Peat is the next layer; I checked the obvious dataset and it's
> non-commercially licensed, so I left it out rather than encumber the
> project.

**"Won't the grid upgrades fix the curtailment?"**
> They should. And the model quantifies how much of the case they remove —
> useful to be able to say about a multi-billion pound programme.

**"Where's the AI?"**
> The scoring is deterministic arithmetic and I'm not going to dress that
> up. What this is about is where AI capacity physically gets built, which
> is the decision in front of government right now. The two AI stages are
> specified and next: reading planning applications to extract capacity and
> cooling method, and training on existing facility locations to measure
> the gap between where the industry builds and where a public-interest
> model says it should.

**"What was hardest?"**
> Matching wind farms across two registries with no shared identifier. My
> first join looked ninety per cent successful and was wrong on the two
> largest offshore farms in the country — Moray West bound to Moray East,
> and Moray East vanished entirely. A third of the national volume,
> misplaced. I only caught it because I measured coverage by volume rather
> than by count.

---

# 60-second cut

> We're building a generation of data centres, and we're siting them on
> land price and grid connection — not on whether it's our best farmland,
> or whether the water is already over-committed.
>
> Common Ground scores every square kilometre of Britain against those
> constraints and lets you filter it.
>
> [Tick farmland. Tick water stress. Let the count drop.]
>
> And the clean power is in the wrong place: 96.6% of the wind we pay to
> switch off is north of the transmission constraint — measured, from the
> system operator's data. When we curtail that, gas fills the gap.
>
> The environmental answer and the cheaper answer turn out to be the same
> answer. Thank you.

---

# Delivery

- **Slower than feels right.** Nerves speed you up by about a third.
- **Three pauses:** after the opening, after the count drops, after 96.6%.
- **Don't apologise for anything.** Every limitation here is stated as a
  finding, because that's what it is.
- **The closing line is the pitch.** "The environmental answer and the
  cheaper answer are the same answer." Land that one cleanly.
- **If the wifi dies:** the basemap is a CDN tile layer, so it goes. Say
  so, then tick a box and let them watch the count change. The model runs
  in the page — that's a better moment than a working map.
- **If everything dies:** play the video.
