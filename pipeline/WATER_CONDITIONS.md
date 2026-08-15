# Is the water flowing? — the open sources that carry a current low-water signal (August 2026)

Companion to [WATER_SOURCES.md](WATER_SOURCES.md), which answers *where water is* and
closes by saying that **"nothing open carries reliability"** and that flowing-today
"belongs to [DATA_NUDGES.md](../features/DATA_NUDGES.md)'s one-tap loop". That sentence was
true about the column it was measured against — point inventories, spring layers, NHD's
perennial/intermittent FCode, OSM's absent `seasonal=*` tags. It was never measured against
the **hydrology and drought-monitoring** column, which is a different set of publishers
answering a different question, and this document is that measurement.

The narrow correction it produces: **three federal programmes publish a current,
free, trail-locatable indication that water is low, updated hourly to weekly.** None of
them observes a spring, none of them can say a particular water source is dry, and the
one that reaches the actual headwater streams the trail walks past is a model whose
published skill in exactly those catchments is poor. So the reliability gap
WATER_SOURCES.md describes is real and DATA_NUDGES.md remains the answer to "is *this
spring* flowing". What changes is that "is the whole region running dry" is answerable
today, from sources a hiker's own state agency already trusts.

Everything below was measured **2026-08-15** against live endpoints unless another date is
given. [spike_water_conditions.py](spike_water_conditions.py) is committed beside this file
and re-runs every number in it; it caches each upstream response under `data/spike`, so a
re-run re-reports without re-fetching. What it measures is **coverage, currency and
cross-source coherence** — the things checkable without a hiker on the ground. **None of it
is accuracy.** No open observation set of dry A.T. springs exists to validate against;
WATER_SOURCES.md §4 measured that dead end and it has not moved.

## 1. USGS streamgauges — the trustworthy answer to a question near the trail

**Measured.** 2,252 active real-time discharge gauges across the fourteen trail states.
Against ATC's centerline (2,172.0 mi of geometry, measured from the same layer the pipeline
already fetches):

| within | gauges |
|---|---|
| 1 km | 11 |
| 2 km | 16 |
| 5 km | 41 |
| 10 km | 98 |
| 20 km | 218 |
| 50 km | 558 |

**The nearest gauges are not near the trail in any useful sense.** French Broad River at
Hot Springs, NC sits 9 m from the centerline; Housatonic River at Falls Village, CT 20 m.
Those are the places the A.T. drops off the ridge and crosses a road bridge over a large
river, which is the opposite of the hydrology a ridgeline spring has. A gauge is near the
trail geometrically and remote from it hydrologically, and any wording that ships must
survive that fact.

**What a gauge does publish that nothing else does: a percentile.** Discharge in cubic feet
per second means nothing to a hiker; discharge against the same gauge's own record for the
same calendar day means "low". Of the 218 gauges within 20 km, **199 had both a current
reading and day-of-year percentiles of record today**; their median record length is
**76 years** and 156 of them have 30 years or more. Classified on USGS's own streamflow-
condition cut points (much below normal is below the 10th percentile, below normal is
10th–25th):

| | all 199 | the 59 with a drainage area under 50 sq mi |
|---|---|---|
| much below normal (<p10) | 12% | 10% |
| below normal (p10–p25) | 16% | 17% |
| normal (p25–p75) | 49% | 51% |
| above normal (>p75) | 23% | 22% |

So the signal **discriminates today** rather than saying "normal" everywhere, and the
small-catchment subset — the gauges closest in character to a headwater stream — behaves
like the whole set rather than better or worse.

Three cautions, each of which would produce a wrong sentence on a card if ignored:

- **Regulated gauges lie about drought.** West Branch Croton River *below dam* near Kent
  Cliffs, NY reads *above normal* today at 81 cfs against a median of 14, 7.8 km from the
  trail: that is New York City's reservoir system releasing, not rain. Any use of this
  data needs a regulation screen, and one is already published: USGS's
  [HCDN-2009](https://pubs.usgs.gov/fs/2012/3047/pdf/fs2012-3047.pdf) is a 743-site
  national list drawn from GAGES-II, screened to exclude gauges whose flow is affected by
  diversion, storage or other human activity in the basin. This spike does not apply it.
  **@unvalidated — how many of the 199 gauges above are regulated is unmeasured, and so is
  how many survive an HCDN-2009 join at all.** What would settle it is that join, plus the
  `below dam` phrasing already visible in the station names.
- **A short record is a weak percentile.** The set runs from 9 years to 135. A 10th
  percentile computed from nine Augusts is a different claim from one computed from
  ninety-nine, and only one of them deserves the word "much below normal".
- **The endpoint that serves percentiles is being switched off.** These figures come from
  `waterservices.usgs.gov/nwis/stat/`. USGS is decommissioning legacy WaterServices in
  **Q1 2027**, with degradation possible from the second half of 2026 — i.e. now — and
  WaterWatch, the percentile map everyone links to, is already gone: `waterwatch.usgs.gov`
  redirected to [the retirement notice](https://waterdata.usgs.gov/blog/wdfn-stats-delivery/)
  when this was checked on 2026-08-15, which is that notice's "by the end of 2025" having
  actually happened rather than being planned. The
  replacement at `api.waterdata.usgs.gov` is live and serves daily values, but **checked
  2026-08-15 it publishes no percentile collection at all** — its collection list has
  `daily`, `latest-daily` and `statistic-codes`, and nothing that computes a percentile.
  Anything built here computes its own from the daily record, which is what USGS's
  [`hyswap`](https://doi-usgs.github.io/hyswap/) package exists to do. **A design that
  points at the legacy endpoint is already stale.**

## 2. USGS groundwater wells — right physics, wrong density

A ridgeline spring is groundwater reaching the surface, so a shallow well's water level is
closer in physics to spring flow than a river gauge is. **Measured:** 943 active real-time
groundwater-level wells across the fourteen states, and near the trail they are thin —
13 within 5 km, 37 within 10 km, 66 within 20 km. The nearest are a Cumberland County
observation well 350 m off the trail in Pennsylvania, a Virginia well at 438 m, and one
inside Bear Mountain State Park, NY at 1.0 km.

**Reasoned, not measured:** 37 wells over 2,172 miles is one per 59 miles at best, and they
sit in valleys where wells get drilled rather than on the ridges where the trail and its
springs are. This is the source whose physics is right and whose sampling cannot carry a
trail-wide claim. Worth a second look only if a regional index is what ships, never a
per-shelter one.

## 3. NOAA's National Water Model — the only source that reaches the actual streams

This is the find, and it comes with the largest caveat in this document.

NOAA's National Water Model simulates streamflow for every NHDPlus reach in the country,
and the National Water Prediction Service serves it as a free, unauthenticated JSON API
(`api.water.noaa.gov/nwps/v1/reaches/{comid}/streamflow`). USGS's NLDI resolves a
coordinate to its reach in one call, so **any point on the trail can be turned into a
current modelled flow for the stream beside it**, without a key or an account.

**Measured:** **4,086 NWM reaches lie within 2 km of the A.T. centerline, and 2,732 of them
are stream order 1** — the headwater channels that WATER_SOURCES.md §5 says NHD classifies
worst and that a hiker actually drinks from. Of 60 points sampled evenly along the whole
corridor, 59 resolved to a reach with a live series and 57 of those carried real numbers;
**9 of the 57 report exactly 0.000 cfs right now**, with the rest spread across a plausible
range (quartiles 0.35 / 1.41 / 4.94 cfs, maximum 2,403). Zero is not the model's default
answer, which is what makes it interesting — and three of the nine zeros (Bluff Creek,
Cove Creek, Tye River) sit between latitude 37.67 and 37.83, inside §4's central-Virginia
severe-drought band. **Three out of nine is an anecdote, not a correlation**, and it is
recorded here as the thing worth measuring properly rather than as a result.

**The same sample is the reason to be careful.** One of those zeros is named *Tye River* —
a real Virginia river, not a seep. A model reporting a named river at exactly 0.000 cfs is
either telling us something severe or telling us its headwater routing bottoms out at
zero, and this spike cannot distinguish the two.

**Two traps found in the data itself:**

- **NWM's missing-value sentinel arrives as a number.** Two of the 59 reaches — Watauga
  River in Tennessee and Dead River in Maine — returned `-9999.0` for every hour of their
  series. A consumer that does not filter it publishes "−9999 cfs", or worse, treats it as
  the lowest flow on the trail.
- **Agreement at gauged reaches proves nothing about ungauged ones.** The
  analysis-and-assimilation series is nudged toward gauge observations where gauges exist.
  Validating the model at the reaches that have gauges and then quoting that skill for the
  headwaters that do not is the specific mistake available here.

**What the literature says about exactly these catchments, and it is not encouraging.**
[Morales-Velazquez et al. 2025 (JAWRA)](https://onlinelibrary.wiley.com/doi/10.1111/1752-1688.70040)
evaluated NWM retrospective streamflow against 19 unregulated montane catchments in the
northeastern US — drainage areas 0.41–191 km², stream orders 1 to 3. Its ranges include
four the A.T. walks (the Berkshires/Taconics, the Greens, the Whites and Maine's
Longfellows) and two it does not (the Adirondacks, and Allegheny sites in western
Pennsylvania), so it is the closest published read on the A.T.'s own headwaters north of
the mid-Atlantic rather than a study of them. The model fell **below the accepted-performance
threshold at 13 of the 19 sites for NSE, 10 of 19 for KGE and 8 of 19 for percent bias**,
with a consistently negative bias whose seasonal medians run −2.72% in autumn, −22.68% in
winter, −31.77% in spring and **−18.95% in summer** — the season a hiker cares about. In
the other direction,
[Hughes et al. 2024 (JGR Atmospheres)](https://agupubs.onlinelibrary.wiley.com/doi/10.1029/2023JD038522)
reports that NWM retrospective streamflow does represent low-flow conditions at ungauged
reaches well enough for drought monitoring, and better than its own soil moisture does.
**Caveat on that second citation: it was read from its abstract and from search summaries,
because the publisher returns 403 to this sandbox.** It is cited here as a pointer to
follow, not as a result this project has checked.

**A raw cfs number is not the signal anyway — the percentile is**, exactly as in §1, and
that is where the cost sits. The only published per-reach climatology is the NWM
retrospective, on AWS as Zarr: **385,704 hourly steps × 2,776,734 reaches**, chunked
672 × 30,000. The corridor's reaches fall in **27 of the 93 reach blocks**, so a full
44-year per-reach baseline would read **15,498 chunks, about 1.2 TB uncompressed**. That is
not a nightly job; it is a one-off derivation producing a small per-reach table of
day-of-year percentiles, and it should be costed as such before anyone promises it.

## 4. The U.S. Drought Monitor — coarse, weekly, and the one a hiker already understands

Free GeoJSON at `droughtmonitor.unl.edu/data/json/usdm_current.json`, released every
Thursday, produced by NDMC/USDA/NOAA authors who read the gauges, the soil moisture, the
precipitation records and local reports and publish a single reviewed judgement. There is a
per-county history API as well (`usdmdataservices.unl.edu`).

**Measured, this week's release (valid 2026-08-11 to 2026-08-17), against the centerline:**

| class | A.T. miles | share |
|---|---|---|
| D0 abnormally dry or worse | 877.1 | 40.4% |
| D1 moderate drought or worse | 295.4 | 13.6% |
| D2 severe drought or worse | 205.8 | 9.5% |
| D3 extreme drought | 10.2 | 0.5% |
| no class at all | 1,294.9 | 59.6% |

The D2 stretch is central Virginia, roughly latitude 37.4 to 38.0 — the Blue Ridge between
the James River and Shenandoah. The 10 miles of D3 sit around latitude 35.13–35.22 in the
Nantahalas of North Carolina. **Two hundred miles of the Appalachian Trail are in severe
drought today**, and this is the cheapest, most legible way to say so.

**A coherence check, because two sources agreeing is worth more than either alone.**
Cross-tabulating §1's gauges against the drought class at each gauge's own location: of
the 74 gauges in no drought class, 3 read much below normal and 22 read above normal; of
the 20 in D2, 4 read much below normal and only 1 above. The instrument and the weekly
human consensus point the same way. **They are not independent**, though — the Drought
Monitor's authors use streamflow among their inputs, so some of that agreement is the same
gauges arriving twice. It is a sanity check, not a validation.

## 5. What does not exist, so nobody goes looking twice

- **No open, per-source water-condition observation set for this trail.** Unchanged from
  WATER_SOURCES.md §4: FarOut's comment stream is the de-facto A.T. water report and is
  not ours to take. This is still the gap [DATA_NUDGES.md](../features/DATA_NUDGES.md) is
  designed to fill.
- **ATC's own feed is not a water channel.** `lib/atc_updates.py` records ATC's closed
  category set — Detour, Alert, Closure, Parking, Hiking Safety, Animal — and there is no
  water or drought category in it. Checked against their live page 2026-08-15: nine current
  updates, none about water, drought or dry springs, while 206 miles of the trail sit in
  D2. **The steward who knows the trail best is not publishing this, and that is a finding
  rather than an oversight to route around** — it is also the natural thing to raise
  whenever the combined ATC ask in WATER_SOURCES.md §7 option 3 gets sent.
- **NASA's GRACE-derived groundwater percentile is too coarse.** Live and current
  (`nasagrace.unl.edu`, latest 2026-08-03, weekly), and physically the right variable, but
  published on a 0.125° grid — roughly 12 km, which is wider than the distance between many
  A.T. shelters. It cannot distinguish one side of a ridge from the other. Worth naming
  only so the next survey does not re-derive it.

## 6. How any of it would land in this codebase

Verified against the code 2026-08-15, and the shape is deliberately unlike the water-points
work:

- **None of this is a POI and none of it is a pin.** A percentile is a statement about a
  watershed, not a place. `conditions/` is the artifact family that already exists for
  time-varying public safety data ([export_conditions.py](export_conditions.py),
  [features/CONDITIONS_DELIVERY.md](../features/CONDITIONS_DELIVERY.md)) — static bytes,
  free egress, no running server on the safety read path — and a water-conditions artifact
  keyed by mile range belongs beside `closures.json` and `reports.json`, not in
  `unify_poi`.
- **Refresh cadence is the argument against the obvious design.** Gauges update hourly, the
  Drought Monitor weekly, and a hiker in the hundred-mile wilderness is offline for a week.
  Anything published here must carry its own observation time and be readable as stale —
  [staleness.ts](../client/src/lib/staleness.ts)'s tiers exist, though its own 14/60-day
  constants are the unsourced numbers [CLAUDE.md](../CLAUDE.md) calls out, and they were
  chosen for POI confirmations rather than for hydrology. **A water-conditions tier needs
  its own thresholds, derived rather than borrowed.**
- **The wording is the whole risk, and it is a safety path.** "Streams in this area are
  running much below normal for mid-August (USGS, 3 gauges, updated 2 hours ago)" is a
  claim this data supports. "The spring at Thomas Knob is dry" is not, and no amount of
  modelling makes it one. HIKER_SAFETY.md's asymmetry applies exactly as `wrongWay.ts`
  states it: a false "there is water" is the failure that matters.

## 7. The options, ranked

1. **The Drought Monitor as a regional banner** — *smallest effort, largest honest
   coverage.* One weekly fetch of a public GeoJSON, intersected with the centerline the
   pipeline already has, published into `conditions/`. It reaches 877 miles today, it
   carries a name hikers already know from their own state's news, it needs no percentile
   machinery, and it cannot be mistaken for a claim about a particular spring. The
   licence needs a human read before anything ships (NDMC is a university partnership, not
   a pure federal work), which is the one blocker.
2. **USGS gauge percentiles as a corridor-scale index** — *medium effort, the strongest
   evidence in this document.* Screen for unregulated small catchments, compute
   day-of-year percentiles locally from the daily record via `hyswap` against the new API
   (never the retiring one), publish a per-segment "streams here are running X" with the
   gauge count and record length attached so a thin claim reads as thin. 198 gauges is
   sparse per mile and deep per gauge — the opposite shape to option 1, which is why they
   are worth having together.
3. **Ask ATC to publish a water advisory** — *no code, and the highest-value thing here.*
   The steward already runs a categorised update feed that hikers read; it has no water
   category and said nothing during a drought that covers a tenth of the trail. Adding
   this to WATER_SOURCES.md §7 option 3's combined ask costs a sentence.
4. **A National Water Model spike** — *research, not a build.* It is the only source that
   reaches the 2,732 order-1 reaches beside the trail, and its published skill in exactly
   those catchments is poor enough that shipping it now would be the confidently wrong
   prediction FEATURES.md warns about. The honest next step is to measure it rather than
   adopt it: pick the reaches nearest the gauges from option 2, compare NWM against
   observation at *those* reaches through a summer, and read the Hughes 2024 paper
   properly. **Do not ship an NWM number to a hiker before that exists.**
5. **What not to build:** anything per-spring from any of these sources; a groundwater-well
   index (§2, too sparse); a GRACE layer (§3 of the "does not exist" list, too coarse); and
   any design pointing at `waterservices.usgs.gov` or WaterWatch, both of which are on
   their way out.

**The sentence this document exists to protect.** Every source above answers "is the
region dry", and a hiker asks "will there be water at the next shelter". Those are
different questions, and the distance between them is the reason this ranks a weekly
county-scale polygon above an hourly per-reach model. A regional signal published as a
regional signal is honest and useful. The same data published as a promise about a spring
is the failure mode [OurHikeValues.md](../OurHikeValues.md) #4 exists to prevent.
