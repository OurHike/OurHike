# A smaller hiking sheet — where the 789.6 MB actually goes, and which levers survive

Design for offering hikers a download meaningfully smaller than the whole
corridor at Standard. Written 2026-08-27. Every number below carries its grade
(measured / reasoned / `@unvalidated`) per [CLAUDE.md](../CLAUDE.md).

**The short version.** The download is 77% terrain and 23% map. Every lever that
makes the *terrain* cheaper per unit area fails the project's own acceptance
test — measured here, on real tiles, including the one this document set out to
recommend. So a smaller download has to come from **covering less ground**, not
from carrying the same ground more cheaply. That is the axis the maintainer
already re-decided on 2026-08-25, and this document sits beside that decision
rather than arguing with it.

> **One exception, found later (#1486) and shipped by #1506:** *encoder effort*
> — 1.1% of the archive for roughly double the build's encode step —
> passes, because it changes how the pixels are packed rather than what they
> are — 3.1 MB off `dem.pmtiles`, with all 162 sampled tiles decoding
> bit-identical. Every lever that touches the pixels themselves still fails.
> The sentence above holds as an argument about resolution and quantization,
> which is what it was written about, and not as a claim about the encoder.

> **The 789.6 MB in this document's title is historical, and the shares moved
> with it.** Everything below was written against the pre-taper archives; both
> halves have shrunk since, by different amounts and for unrelated reasons —
> the DEM by #1088's taper, the basemap by #1116's layer exclusion, which
> reached the bucket in the **2026-09-14** release and landed within 0.1% of
> what BASEMAP.md projected for it. **Measured** against
> `data.ourhike.org/latest.json` on 2026-09-15:
>
> | level | basemap | DEM | sheet | DEM share |
> |---|---|---|---|---|
> | Fine | 349,150,877 | 275,601,483 | **624.8 MB** | 44.1% |
> | Standard | 160,039,318 | 275,601,483 | **435.6 MB** | **63.3%** |
> | Light | 67,961,447 | 182,205,873 | **250.2 MB** | 72.8% |
>
> So "77% terrain and 23% map" now reads **63.3% / 36.7%** at Standard, and the
> sentence it supports — that a strategy going after the basemap first is
> optimising the small half — is still true at Standard and Light and **no
> longer true at Fine**, where z14 vector detail outweighs the terrain. The
> per-unit-area findings below are unaffected: they are ratios measured on
> tiles, not shares of a total.

## What the 789.6 MB is

**Measured**, from the published artifacts ([BASEMAP.md](BASEMAP.md) §Published
archives, `client/src/lib/hikingDetail.ts:33`, `client/src/lib/packages.ts:134`):

| artifact | bytes | share |
|---|---|---|
| `dem.pmtiles` (z0–13, 0.5 m quantize) | 607,265,661 | **76.9%** |
| `at_basemap_package_z13.pmtiles` (z0–13) | 182,286,799 | 23.1% |
| **Standard hiking sheet** | **789,552,460** | |

Plus ~6 MB of bundled glyphs (`client/public/glyphs/README.md`), which is not a
lever and is not discussed further.

**Any strategy that goes after the basemap first is optimising the small half.**

### What the DEM is for, and what it is not for

`dem.pmtiles` feeds exactly two things, both cartographic:

- the **hillshade** — one `type: 'hillshade'` layer (`liveTopo.ts:1216-1226`)
  over the `raster-dem` source at `liveTopo.ts:1074-1081`;
- the **contour lines**, generated in-browser by maplibre-contour from the same
  tiles (`client/src/map/contours.ts`, running in `demWorker.ts`).

There is no `map.setTerrain(...)` anywhere in `client/src` — no 3D relief, no
terrain mesh. **Measured** by enumeration of every importer of `DEM_PACKAGE` /
`DEM_SOURCE_ID` / `demGetTile`.

**It does not feed elevation gain, loss, pace, or the climb-ahead callout.**
Those come from `elevation_profile.json` — built by `export_elevation.py` from
USGS 3DEP 1/3 arc-second COGs read remotely, sampled every 25 m along the
#652-calibrated centerline, summed with `lib/elevation_gain.py`'s dead band —
and read on the phone from `ourhike:elevation` via `lib/elevationGain.ts` and
`lib/upcomingClimb.ts`. That artifact is per-trail vector data downloaded by
default, and is **not part of the 789.6 MB** (WIREFRAMES.md §4).

This matters for the risk calculus and is easy to overstate in either
direction. Deleting the DEM outright would not move a single number the app
computes. It would remove the hiker's ability to read terrain *shape* off the
map, which is real safety work — identifying which drainage you are in when you
are lost is what contours are for. It is not decoration, and it is not
arithmetic.

## The measured result that decides this document

Run 2026-08-27 against `s3.amazonaws.com/elevation-tiles-prod/terrarium/` — the
same bucket `export_dem.py` uses — on 360 corridor tiles (160 at z13, 80 at z12,
70 at z11, 50 at z10), with `spike_dem_banding.py`'s own
`hillshade`/`bilinear_upsample`/`flattest_window`/`compare` and
`export_dem.py`'s own `floor_blue`/`quantize_unit` copied verbatim so the rig
measures the transform that ships.

**The rig is faithful**, and this is the check to lead with: the 1 m arm
extrapolates to 397.2 MB against `export_dem.py`'s full-scale measurement of
397.6 MB (build-dem.yml run 1, 2026-08-05) — 0.1% apart, and genuinely
independent. It also reproduces the spike's headline: Cumberland Valley, 4×
overzoom, exaggeration 0.35, 1.0 m floor → 7.64% of pixels shifted >8/255,
against the spike docstring's 7.6%.

**Accuracy bound on every extrapolated figure below: ±0.7%** — the sample's
per-zoom mean bytes/tile times the published tile counts give 611.6 MB against
the published 607,265,661 B. An earlier draft of this measurement claimed 0.05%
agreement; that figure was circular (the baseline arm's ratio to itself is 1, so
it re-summed README's table) and is retracted.

### Every per-unit-area lever, and how it failed

| arm | DEM MB | fidelity verdict |
|---|---|---|
| **0.5 m floor (shipped)** | **607.0** | baseline |
| 1.0 m floor | 397.2 | already rejected 2026-08-06; 7.64% at exag 0.35 |
| 2.0 m floor (combined-value) | 326.1 | dead — 19.5–32.7% under overzoom |
| lossy WebP over terrarium | *larger* at q90/q95 | dead — RMSE 2,771 m, 95% of pixels >50 m wrong |
| re-encode to a lossy-tolerant form | 138 (4.4×) | dead — 22.4–46.1% hillshade shift |
| **cap the DEM at z12** | **209.4** | **dead — worse than the rejected 1 m step** |
| 128 px tiles at z13 | 140.5 | strictly dominated by the z12 cap; same resolution, 4× the tiles |

**Capping the DEM at z12 is the headline casualty, and it is the lever this
document expected to recommend.** Like-for-like at identical m/px, % of
hillshade pixels shifted >8/255:

| area | z12 cap | 1.0 m floor (already rejected) |
|---|---|---|
| Cumberland Valley PA | 6.29% | 7.64% |
| Harlem Valley NY | 28.61% | 7.72% |
| Franconia Ridge NH | 13.80% | 6.94% |
| **Smokies / Clingmans TN** | **66.36%** | 2.58% |
| McAfee Knob VA | 28.44% | 5.36% |
| Shenandoah Valley VA | 14.09% | 6.06% |

Worse in five of six areas and catastrophic in the Smokies. It also degrades the
**contour lines**, which the vertical-floor arms leave alone: halving the
horizontal grid moves every line's shape.

@unvalidated — what a *vertical* floor does to contour lines has not been
measured at all. `terrain.ts:98-115` sets the finest interval at 20 ft = 6.10 m
(imperial, z14 inherited to z15) and 10 m (metric, z13), so a floor at 2 m or
coarser is a meaningful fraction of a contour interval. What would settle it:
running maplibre-contour's own isoline extraction over quantized versus
unquantized tiles at the z14 threshold.

### Why elevation RMSE is the wrong acceptance metric here

The most portable finding of the run. The lossy-tolerant re-encoding and the
1 m floor have almost the same elevation error — 0.99 m RMSE versus 0.575 m —
and the re-encoding renders about **six times worse**. Hillshade is a spatial
derivative: quantization error is spatially correlated (a wide flat tread and
one step), codec error is uncorrelated, and the gradient of noise is noise
everywhere.

**A future proposal justified on elevation RMSE alone should be sent back to
render a hillshade.**

### One correction to the exaggeration the spike used

`spike_dem_banding.py:54` sets `EXAGGERATION = 0.35` citing `liveTopo.ts`'s
`HILLSHADE_EXAGGERATION`, which reads **0.3** (`liveTopo.ts:906`). The sheet
variants ship 0.30 (field, night_hike), 0.35 (quiet_pine, parchment) and 0.55
(ridgeline) (`liveTopo.ts:555-656`, pinned at `liveTopo.test.ts:1086-1090`).
Measured across that range, the 1 m floor is 4.19% at 0.30, 7.64% at 0.35 and
**23.79% at 0.55** — so 1 m at the ridgeline weight is worse than 2 m at the
field weight, and 1 m fails at native z13 with no overzoom at 0.35 and 0.55.
The 2026-08-06 decision stands; its stated evidence understates the case at one
sheet and overstates it at another. Worth an issue on its own.

## What does survive

### 1. The DEM's corridor is inherited, and it is 30 miles wide

`export_dem.py` takes its shape from `export_basemap.py`'s
`load_corridor_4326()`, which is `lib/corridor.py`'s `build_corridor()` at
`BUFFER_MILES = 30` — a **60-mile-wide band** along all 2,163 miles of trail.

That 30 is deliberate and its stated reason is POI context: *"towns, resupply,
parking, the things a thru-hiker leaves the trail for"* (`corridor.py:52-56`).
That is a strong reason to keep the **basemap** wide — the road you bail out on
is CLAUDE.md's "unable to get off the trail quickly." It is not a reason to
carry **hillshade and contours** 25 miles off-trail. Nobody bails out by reading
relief shading.

**Measured** 2026-08-27, against the real ANST centerline (3,025 features,
fetched from ATC's ArcGIS service), buffered in EPSG:5070 and counted with
`extract_package.tiles_intersecting`:

| buffer | z11 | z12 | z13 | DEM MB (reasoned) | vs 30 mi |
|---|---|---|---|---|---|
| **30 mi (shipped)** | 1,139 | 4,180 | 15,951 | 607.6 | — |
| 20 mi | 824 | 2,941 | 10,996 | 429.1 | 29.4% |
| 15 mi | 670 | 2,317 | 8,540 | 340.4 | 44.0% |
| 10 mi | 510 | 1,704 | 6,040 | 250.7 | 58.7% |
| 6 mi | 391 | 1,199 | 4,062 | 179.4 | 70.5% |
| 3 mi | 291 | 807 | 2,508 | 123.2 | 79.7% |

**The method validates:** 15,951 tiles at 30 miles against the published 15,932
— 0.12%. MB is **reasoned**: measured mean bytes/tile (from the published
per-zoom table) times measured tile count, with z0–10 held at its published
21.2 MB.

**These are lower bounds on the narrow rows.** A narrower corridor is not a
random sample of the wide one — it keeps the ridgeline tiles, which carry more
relief and compress worse. The real saving is smaller than the table shows, by
an amount nobody has measured. What would settle it: re-running `export_dem.py`
at a narrowed `--region` and weighing the archive.

**This is the only lever measured here that degrades no rendered pixel.** Inside
the band it keeps, the hillshade and the contours are byte-identical to today's.
What is lost is terrain shading far from the trail.

How wide should it be? `trailPosition.ts:50`'s `MAX_OFF_TRAIL_MILES = 3` is the
distance beyond which the app already declines to say where a hiker is on the
trail — though note its derivation is bucket-search geometry (it must fit inside
`BUCKET_DEGREES`, ~3.45 miles), not a finding about how far hikers wander. So it
anchors the *shape* of the answer, not the number.

### 1a. Decided: the width is a function of zoom, not one number

Maintainer's call, 2026-08-27. A uniform buffer was the wrong shape, and the
per-zoom price says why — **measured**, from the same run:

| | z11 | z12 | z13 |
|---|---|---|---|
| tile width | 9.31 mi | 4.66 mi | 2.33 mi |
| **MB per mile of buffer** | **1.36** | **4.12** | **12.37** |

Width is ~9× more expensive at z13 than at z11, because tile count quadruples
per level while tile width halves. A uniform corridor therefore spends nearly
all its bytes buying width at the zoom a hiker uses to look at the ground under
their feet, and nearly none at the zoom they pan out to for orientation.

So the corridor **tapers**: `export_dem.py`'s `CORRIDOR_TAPER_MILES` is
`{0: 30, 12: 15, 13: 6}` — z0–11 at 30 miles, z12 at 15, z13 at 6.

**BUILT AND MEASURED 2026-08-27** ([run 33065213666](https://github.com/OurHike/OurHike/actions/runs/33065213666),
`build-dem.yml` at the shipped defaults, 8,658 tiles, 0 absent):

| | tiles | MB |
|---|---|---|
| z0–9 (full bbox, context) | 821 | 29.4 |
| z10 | 329 | 11.8 |
| z11 | 1,139 | 49.3 |
| z12 (15 mi) | 2,315 | 78.8 |
| z13 (6 mi) | 4,054 | 106.2 |
| **dem.pmtiles** | **8,658** | **275.6** |

**PUBLISHED TO UA 2026-08-27** ([run 33065561782](https://github.com/OurHike/OurHike/actions/runs/33065561782)):
`dem.pmtiles` is **275,601,483 bytes** in the bucket, and now carries
`transfer_bytes` beside `size_bytes` as well.

| sheet | before | after |
|---|---|---|
| **Standard** (z13 basemap + DEM) | 789,876,586 — 789.9 MB | **458,212,397 — 458.2 MB** |
| **Fine** (z14 basemap + DEM) | 1,140,720,867 — 1.14 GB | **809,056,678 — 809.1 MB** |

**42.0% off Standard, 29.1% off Fine**, with the basemap untouched. Fine
dropping under a gigabyte has a consequence beyond the number: `DetailPicker`'s
iOS note was written when the hiking sheet's worst case was 1.14 GB and over
WebKit's per-origin allowance. It is not any more, and that comment now says so.

The projection this replaces said 275.4 MB, which is 0.1 MB out — and that
agreement is luckier than it looks. Per band it was wrong in both directions
and the errors happened to cancel: z0–9 and z10 came in 6.4 MB *under* the
projection, z12 and z13 5.0 MB *over*. The stated bias — that a narrow corridor
keeps the ridgeline tiles, which carry more relief and compress worse — held
exactly where it was claimed (the two tapered bands) and reversed where the
corridor did not narrow. **A per-zoom mean bytes/tile is not transferable
across a change of footprint**, and the total agreeing is not evidence that it
is.

Other schedules. **The table this replaces was optimistic, and one of its own
rows later proved it** — it projected 20/6/3 at ~159 MB, and when that schedule
was actually built as Light it weighed **182.2 MB**, 14.6% more. The cause is
the caveat two paragraphs up, applied to itself: those rows priced a narrowed
footprint at the *pre-taper* per-zoom mean bytes/tile, and a narrower corridor
keeps the ridgeline tiles, which carry more relief and compress worse.

Re-derived 2026-09-15 (#1486) from the **built** canonical bands instead —
`tiles_intersecting` over the real ANST centerline at each width, priced at
that band's own measured KB/tile (z11 42.3, z12 33.2, z13 25.6):

| schedule z11/z12/z13 | DEM MB | off DEM | sheet MB | off sheet |
|---|---|---|---|---|
| shipped, uniform 30 | 607.3 | — | 789.9 | — |
| **30/15/6 (built, shipped)** | **275.6** | **54.6%** | **435.6** | — |
| 30/10/6 | 254.6 | 7.6% | 414.6 | 4.8% |
| 30/5/6 | 233.0 | 15.4% | 393.0 | 9.8% |
| 20/6/3 (built as Light) | **182.2** | 33.9% | 250.2 | 42.6% |

The off-DEM and off-sheet columns are now against the **shipped 30/15/6**, not
against the withdrawn uniform-30 archive, because 30/15/6 is what a change
would actually be traded against.

**The method is checked rather than asserted.** Projecting the Light taper this
way gives 142.0 MB across z11–z13 against the 144.9 MB that build actually
weighed — **2.0% low**, per band (z11 −1.7%, z12 −2.4%, z13 −1.8%), and low is
the expected direction for exactly the ridgeline-compression reason above. So
every row here understates the archive by roughly 2%, which means it slightly
**overstates** the saving; treat the savings as upper bounds with a ~2% margin
rather than as exact.

**Only z12 moves between the first three rows**, and it is worth being explicit
about what that width feeds, because it is not what it looks like. The
hillshade reads the DEM at the camera's own zoom, but contours read **one zoom
out** — `contours.ts` passes `overzoom: 1`, and maplibre-contour resolves
`min(z - overzoom, maxzoom)`. So z12's width feeds the hillshade at camera z12
and the **contours at camera z13**; contours at camera z12 read z11, which the
taper leaves at 30 miles. Narrowing z12 therefore changes nothing a hiker sees
panned out, and nothing goes blank in the band it gives up either:
`demTiles.ts` walks up to `MAX_ANCESTOR_STEPS = 3` to the nearest ancestor the
archive holds, so past the edge the 40 ft lines and the relief are generated
from upscaled z11 rather than absent. What is lost there is resolution, not the
layer.

**And the shallow zooms stop being clipped at all.** `extract_package.py` has
kept the vector sheet's *entire* footprint through z9 since #189 — "panning out
offline shows the ground around the trail instead of blank paper" — while the
DEM under it clipped at every zoom. Panned out with no signal the two
disagreed on screen, and the disagreement was a packaging artefact rather than
a fact about the ground. `CONTEXT_ZOOM = 9` closes it.

**Measured** 2026-08-27, corridor tiles against the corridor's bounding box:

| zoom | corridor | bbox | ratio | cumulative cost of unclipping |
|---|---|---|---|---|
| z9 | 107 | 576 | 5.4× | **+26.5 MB** |
| z10 | 329 | 2,256 | 6.9× | +106.5 MB |
| z11 | 1,139 | 8,740 | 7.7× | +435.5 MB |

z9 is where it stops being cheap — so the boundary the project already drew
twice (`DEFAULT_CONTEXT_ZOOM`, `STRETCH_CONTEXT_ZOOM`) is also where the
measurement puts it, rather than being a coincidence. Unclipping z11 as well
would spend more than the whole taper saves.

@unvalidated **as numbers.** The shape is measured; 30/15/6 are picked. 6 is
2× `trailPosition.ts`'s `MAX_OFF_TRAIL_MILES`, the distance past which the app
already declines to say where a hiker is — though that constant is itself
derived from bucket-search geometry rather than from how far hikers wander, so
it anchors the shape of the answer and not the number. What would settle it:
what a hiker pans to when they are lost and off-trail, which nothing in this
project measures yet.

### 2. The basemap carries seven layers the style never draws

**Measured** 2026-08-27 on 358 OpenMapTiles-schema tiles fetched through the
app's own network fallthrough (OpenFreeMap, `basemap.ts`'s `OPENFREEMAP_TILEJSON`),
decoded with a hand-rolled MVT parser verified three ways (per-tile byte
accounting exact; the 16 recovered layer names match the TileJSON's `vector_layers`
exactly; a keep-everything re-encode lands within +0.0% of the original gzipped
size).

The style references **9 of 16** layers. It never references
`transportation_name`, `landuse`, `building`, `housenumber`, `poi`,
`aerodrome_label`, `aeroway`. Share of gzipped bytes those seven hold:

| | z12 | z13 | z14 |
|---|---|---|---|
| drop unreferenced layers | 10.0% | 14.2% | **37.4%** |
| + drop features the style filters out | 20.4% | 21.7% | 41.7% |
| + drop unread attribute keys | 28.3% | 28.6% | 47.2% |

Two design questions this surfaces rather than settles: the sheet pays for
`mountain_peak` ridge linestrings at z13–14 (47% and 76% of that layer) and
draws none of them, and pays for hamlet labels `PLACE_FILTER` deliberately
suppresses (65–68% of `place`).

**Caveat, and it is large.** OpenFreeMap's build is not ours: calibrated against
our implied per-tile means, the sample runs +24% at z12, +2.6% at z13 and −19%
at z14, cause unexplained, and the z14 headline has a bootstrap CI of
26.8–45.5%. **Per-layer shares transfer; absolute bytes do not.** Applied to the
182.3 MB z13 basemap the pruning is worth roughly 50 MB — reasoned, ±the above.

**It is new machinery, not a flag.** `export_basemap.py:162-175`'s
`planetiler_cmd()` passes no profile and no layer filter; Planetiler's
OpenMapTiles profile has no include/exclude argument. Filtering means a custom
profile or a post-pass over the PMTiles.

### 3. The basemap's z12 cut is viable where the DEM's is not

The asymmetry is already in [BASEMAP.md](BASEMAP.md): *"MapLibre overzooms z13
vector cleanly."* Vector geometry and labels stay sharp under overzoom; a
raster-dem's hillshade does not, which is exactly what §"Every per-unit-area
lever" measured. So `at_basemap_package_z12.pmtiles` at ~75.1 MB (**reasoned**
from BASEMAP.md's per-zoom table: 31.0 + 44.1) is a real rung, saving 107 MB,
while `dem_z12.pmtiles` is not.

The trail line itself is unaffected either way: the centerline, spurs and POIs
come from `trails.geojson` / `poi_*.geojson` via `lib/trailData.ts`, not from
OSM's `transportation` layer.

## The blocker any zoom-capped artifact hits first

**A light package that stops at a zoom the app still requests is a download that
silently needs signal.** Both resolvers treat "above the archive's ceiling" as an
ordinary miss and go to the network:

- `demTiles.ts:96-104` — *"undefined is a tile the archive never held — beyond
  the corridor, or above z13. A normal miss"* → `fetch(url)` to AWS.
- `basemap.ts:122-135` — *"beyond the package's footprint, or above/below its
  zoom range. A normal miss, so it falls through"* → OpenFreeMap.

Neither overzooms locally. `DEM_MAX_ZOOM = 13` (`terrain.ts:63`) and
`BASEMAP_MAX_ZOOM = 14` (`liveTopo.ts:93`) are compile-time constants; there is
no path by which either follows a hiker's stored preference.

**This is already latent at Standard**, not new to a Light tier: the shipped
default package is z0–13 under a source declaring `maxzoom: 14`, so an offline
hiker at camera z14 is past their package. WIREFRAMES.md §4's #352 amendment
describes the symptom. `client/src/map/poiSites.ts:8` states the opposite as
fact — *"`BASEMAP_MAX_ZOOM` is 14, so that is the zoom an offline hiker lives
at"* — which is true only at Fine. **Worth an issue whether or not anything
here ships.**

**A taper cannot be expressed through the source declaration at all**, which is
what forced the fix rather than merely motivating it: MapLibre's `raster-dem`
carries one `maxzoom`, so it cannot be told "z13 near the trail, z12 out on the
flank". It asks for z13 wherever the camera is deep enough.

So the fix lives in the `getTile` shim instead (#1088, `demTiles.ts`): on a
miss, walk up the pyramid to the nearest ancestor the archive does hold and
return an upscaled crop — **after** the network attempt, so a hiker with signal
still gets the sharp tile and this only ever replaces a throw.

The upscale is **nearest-neighbour, and that is a correctness constraint rather
than a quality setting.** Terrarium's red channel is a 256 m band index, so
interpolating between two pixels either side of a band boundary averages the
indices and invents an elevation hundreds of metres wrong — the same arithmetic
that made lossy compression measure 2,771 m RMSE above. Replicating whole
pixels cannot do that. MapLibre's own overzoom is safe for the opposite reason:
it decodes to elevation first and interpolates there.

## Where this leaves the answer

The user-facing question was a *tier*. The measured answer is that a tier cannot
deliver it on the terrain half, and the coverage decision already made delivers
it on both halves.

**Do not re-open the unit question.** Maintainer, 2026-08-25 on **#552 — Decide
the unit of offline coverage, and write it down**: 1°×1° cells that nobody sees,
with a named "piece" layer, org- and state-scoped, that the hiker chooses. The
grid exists (`pipeline/lib/corridor_grid.py`, `CELL_DEGREES = 1.0`, 51 cells for
the A.T.).

What this document contributes to that decision rather than beside it:

1. **Narrowing the DEM's corridor multiplies with cells** — it shrinks every
   cell's terrain, and it is the one lever that costs no rendered fidelity.
   It also eases the sharpest open problem the maintainer named: z0–9 context at
   6.3 MB duplicated across 51 cells is 321 MB.
2. **Basemap pruning is worth ~50 MB** and is independent of both.
3. **The zoom ladder is available on the basemap and closed on the DEM.**
4. **The archive-header `maxzoom` fix is a prerequisite** for any zoom-capped
   artifact, and is a live defect at Standard today.

### Two provenance defects found on the way

- `cut_cells.py:1-10` and `pipeline/README.md`'s "The 1-degree coverage cells
  (#556)" both assert *"the maintainer's #552 decision (2026-08-18)"* as
  current. It was reversed 2026-08-25. **#556 — Cut and publish coverage units
  from the build that already exists** is closed as completed against a unit
  decision that no longer holds.
- **No hiker has ever been offered anything smaller than 789.6 MB.** Verified
  2026-08-27 against `data.ourhike.org/latest.json`: release 2026-08-26, 42
  artifacts, six `.pmtiles`, zero stretch or context keys. The stretch cut has
  never run at full size.

## The sizes a hiker is shown come from the bucket now (#505)

`downloadDetail.ts` has carried this defect in its own header for a while: its
figures were copied from a build log, drifted from what was served, and the
advertised Standard tier was 14.8 MB smaller than the object behind it — "in
the direction that strands somebody who freed up exactly enough space". The fix
it names is the one now implemented: `publish.py` measures every artifact it
uploads, so the figure comes from `latest.json` and the constants become the
fallback for a phone that has not been able to ask.

**Measured 2026-08-27 against UA** (`environments/ua`, 131 artifacts), which is
where the drift is visible without running anything:

| artifact | client constant | UA measured | delta |
|---|---|---|---|
| `at_basemap_package_z13.pmtiles` | 182,286,799 | 182,610,914 | +324,115 |
| `at_basemap_package.pmtiles` | 532,459,439 | 533,455,195 | +995,756 |
| `dem.pmtiles` | 607,265,661 | 607,265,672 | +11 |
| **Standard sheet, as displayed** | **789.6 MB** | **789.9 MB** | |

One wrinkle that decided the implementation. `PublishedSnapshot.sizes` read
`transfer_bytes` and only that, which is right for the gzipped text artifacts —
`size_bytes` is the decoded figure and overstates a download about 4×. But
`transfer_bytes` exists only on artifacts uploaded since #919: of UA's 131
entries, **131 carry `size_bytes` and 6 carry `transfer_bytes`, none of them an
archive.** So the map archives — the only sizes the entrance page actually
prints — would have gone on reading their constants forever.

`size_bytes` is therefore used where the bucket stores the artifact
uncompressed, and that is not a guess: `lib/content_types.py` keeps `.pmtiles`
and `.fgb` out of `COMPRESSIBLE_TYPES` deliberately, because both are read by
byte range and a stored `Content-Encoding` would make ranges refer to
compressed offsets. Stored and served are the same bytes by construction. A
gzipped text artifact with no `transfer_bytes` still yields nothing, because
there is no honest download figure for one.

**Offline it asks nothing at all.** The read is gated on `online`, the same gate
`useTrailData.ts` puts on its own manifest fetch — a phone at a trailhead with
no signal must reach the network zero times, not once-and-fail, and
`App.trailData.test.tsx` pins that. It then shows the constant, which is the
right answer for a phone that cannot ask.

## Building the Light rung

`build-dem.yml` takes a `variant` input since #1088: **canonical** builds
`dem.pmtiles` at 30/15/6, **light** builds `dem_light.pmtiles` at **20/6/3**.
The taper tables live in `export_dem.py` (`CORRIDOR_TAPER_MILES`,
`LIGHT_TAPER_MILES`) rather than in YAML, so the numbers sit where they are
documented and tested.

What Light trades, stated plainly because it is not the trade Standard makes:
Standard already narrows to 6 miles of z13 either side of the trail; Light
halves that to **3 — exactly `trailPosition.MAX_OFF_TRAIL_MILES`, the distance
past which the app already refuses to say where a hiker is.** So terrain runs
out closer to the trail at every zoom, and a hiker who wanders further than the
app can locate them has no hillshade where they are.

Two things the workflow does that are not conveniences:

- **A light build does not cut cells.** `cut_cells.py` names its output
  from the family, so a light run would overwrite `dem_stretch_NN.pmtiles` with
  light bytes under the canonical keys — a quieter version of the
  wrong-bytes-behind-the-right-name failure the publish gate exists to prevent.
  A light stretch set needs its own family before it can be cut at all.
- **The artifact is named per variant**, so the publish job cannot download one
  variant's archive and upload it under the other's key.

`publish.py` already knew `dem_light.pmtiles`; what was missing was any way to
produce it. Until one had run, `hikingDetail.ts` kept the Light level at
`published: false` with a null size — the rung lights up when a build has run
and its bytes have been measured, not before, for the reason `packages.ts`
records as "a 404 on a mountain".

**BUILT 2026-08-27** ([run 33067212006](https://github.com/OurHike/OurHike/actions/runs/33067212006)):
`dem_light.pmtiles` is 5,553 tiles and **182,205,873 bytes** — z9 18.4, z10 9.2,
z11 36.3, z12 41.8, z13 66.8 MB. Note the context band shrank too (z9 552 tiles
against the canonical build's 576): the bbox follows the widest corridor, which
is 20 miles here rather than 30.

**And Light takes the z12 basemap cut** (#1107). The taper only ever touched
terrain, so both rungs were still carrying the same 182.6 MB of vector
basemap and Light came out only ~93 MB below Standard — thin for a choice a
hiker has to understand. `at_basemap_package_z12.pmtiles` is the other ~107 MB.

Capping the *basemap* at z12 is safe where capping the *DEM* there was not, and
the asymmetry is measured rather than assumed: BASEMAP.md's own finding is that
MapLibre overzooms z13 vector cleanly, while the same cap on the raster-dem
measured worse than a quantize step already rejected (see the table above).
Geometry and labels survive magnification; a hillshade computed from magnified
elevation does not.

**BUILT AND PUBLISHED 2026-08-27**
([run 33069162537](https://github.com/OurHike/OurHike/actions/runs/33069162537)),
so every figure below is measured in UA's bucket — and **promoted to production
the same day**, where all five artifacts re-measure identically. The two DEMs
came out byte-for-byte and hash-for-hash equal to UA's from independent builds
hours apart, which is the static AWS Open Data source and a deterministic
encode path; the basemap has no such guarantee and happened to match because
both builds drew the same OSM state:

| level | basemap | DEM | sheet | vs its own original |
|---|---|---|---|---|
| Fine | z14, 533,926,586 | 275,601,483 | **809.5 MB** | −29.0% |
| Standard | z13, 182,774,166 | 275,601,483 | **458.4 MB** | −42.0% |
| **Light** | **z12, 75,451,755** | **182,205,873** | **257.7 MB** | **−67.4%** |

Light's basemap came in at 75,451,755 bytes against the 75.1 MB reasoned from
BASEMAP.md's per-zoom table (31.0 + 44.1) — **0.5% high**. That is a wider miss
than the tapered DEM's whole-archive projection (275.4 against 275.6, 0.07%) and
a more trustworthy one: the DEM's per-band errors cancelled, 6.4 MB under at
z0–10 against 5.0 MB over at z12/z13, because the taper changed the footprint
those per-zoom means were measured on. Capping the basemap at z12 changes no
footprint at all, so summing published per-zoom bytes is arithmetic rather than
extrapolation. What the remaining 0.5% covers is the rounding in those published
per-zoom megabytes plus whatever OSM changed between the two builds — which of
those dominates has not been separated and would need the older build's exact
per-zoom bytes to settle.

**Standard and Fine both moved too, and not because of anything here.** This
run rebuilt the basemap from current OSM, so all three cuts were re-measured:
z13 went 182,610,914 → 182,774,166 and z14 533,455,195 → 533,926,586, drifts of
+0.09% each. `hikingDetail.ts` carries them exactly anyway — the constants are
what a phone that has not reached `latest.json` shows a hiker, and understating
is the direction that strands somebody who freed exactly enough.

*(This paragraph said check 18 "tolerates 2% and would not have flagged either",
which read as though the check was watching these artifacts. It was not:
`verify_release.py` read only `downloadDetail.ts`'s withdrawn raster tiers, so
nothing held the hiking sheet's advertised figures to the bucket at all. Corrected
and made true by [#1144 — verify_release gates the withdrawn raster tiers, not the
hiking sheet hikers download](https://github.com/OurHike/OurHike/issues/1144),
which points checks 2 and 18 at this table. The 2% tolerance is real and these
drifts are inside it.)*

**Against the 40–80% the request asked for**: Light is 67.4% off the 789.6 MB
Standard used to cost, inside the band; Standard's own 42.0% is at its floor.

@unvalidated — 20/6/3 is picked, not derived, and what Light gives up is stated
in `export_dem.py`: terrain runs out at 3 miles from the trail, exactly
`trailPosition.MAX_OFF_TRAIL_MILES`, so a hiker further off-trail than the app
can locate them has no hillshade where they are.

**What would settle it**, since #1107 closed without settling it and an
`@unvalidated` tag pointing at a closed issue says nothing: how far off the
centerline hikers actually go, which nobody here has measured. Two sources
would answer it without a field trial — the off-trail distribution of the
waypoints already in the corridor export, and how often `trailPosition.ts`
reports a fix beyond each candidate width. Either would turn 3 miles from a
number that matches a constant into a number that matches behaviour. Until one
is run, Light is the rung to be most careful recommending.

## Measured: baking loses, and the accounting is what loses it (#1486)

The "what was rejected" row above sat open because nobody had run it. Run
2026-09-15 with `spike_baked_terrain.py` (bytes and hillshade fidelity) and
`spike_baked_contours.mjs` (contour bytes, generated by maplibre-contour's own
isoline and vector-tile encoder rather than estimated), over
LIGHT_DOWNLOAD.md's own six areas at z11/z12/z13 — so these numbers sit beside
the z12-cap and 1 m-floor tables above rather than beside a new sample nobody
can compare against.

**The idea was attractive for a real reason, and the fidelity numbers vindicate
it.** A baked hillshade at WebP q85 shifts **0.22–0.34%** of pixels past 8/255
at native resolution, against the 1 m vertical floor's 4.19–7.64% that this
project already rejected. The codec is not the problem. The accounting is.

### What a baked hillshade weighs

Bytes per centre tile, mean over the six areas, against `export_dem.encode_tile`
itself on the same tiles (so arm A is the shipping transform, not a copy):

| zoom | DEM (shipped) | lossless | q75 | q85 | q95 |
|---|---|---|---|---|---|
| z11 | 48.9K | 44.2K | 13.2K | 18.2K | 27.7K |
| z12 | 36.9K | 39.8K | 10.2K | 14.3K | 23.0K |
| z13 | 27.1K | 36.6K | 7.9K | 11.5K | 19.9K |

**Both left-hand columns are pre-#1506 and are left as measured.** The shipped
encoder now asks for effort 100, so "DEM (shipped)" is high by 0.65/1.16/1.76%
and the 275.6 MB baseline with it; the spike's own lossless arm was encoding at
Pillow's default and has been aligned, so a re-run moves both columns a little
and neither conclusion. Restating them here from a ratio would replace numbers
from a real run with a corrected estimate of one, which is the wrong direction
to edit in — the next build re-measures them.

**Lossless baking is already a loss** — a shaded image carries more entropy than
the elevation it came from, once that elevation has had its sub-metre fraction
floored away. Every saving here is the lossy codec's, which is the point.

Projected onto the published per-zoom bands: **130.9 MB at q85**, 102.8 MB at
q75, against `dem.pmtiles`'s 275.6 MB. *Reasoned*, and calibrated — see below.

### Why that saving is not a saving

`dem.pmtiles` feeds the hillshade **and** maplibre-contour's isolines. Baking
only the hillshade frees nothing: the DEM still ships for the contours, and the
130.9 MB is pure addition. To drop the DEM you must bake the contours too, and
those are billed per interval *and* per unit, because `terrain.ts`'s
`CONTOUR_THRESHOLDS` carries an imperial and a metric ladder that both change
with zoom. A live map picks one per request for free; a baked archive carries
every combination it wants to offer.

Measured, gzipped, at the real thresholds:

| zoom | interval | imperial | metric | DEM tile |
|---|---|---|---|---|
| z11 | 200 ft / 100 m | 22.1K | 13.2K | 48.9K |
| z12 | 100 ft / 50 m | 23.0K | 14.4K | 36.9K |
| z13 | 40 ft / 10 m | 29.2K | 35.1K | 27.1K |

At z13 a single unit's contour tile already outweighs the DEM tile that draws
**both** units at **every** interval. Projected and calibrated: imperial
**160.2 MB**, metric **157.6 MB**, together **317.8 MB** — more than the whole
DEM, before any hillshade is added.

| | MB | vs `dem.pmtiles` |
|---|---|---|
| **ship today** — `dem.pmtiles` | **275.6** | — |
| bake: hillshade q85 | 130.9 | |
| bake: contours, imperial | 160.2 | |
| bake: contours, metric | 157.6 | |
| **bake: hillshade + both units** | **448.7** | **1.63×** |
| bake: hillshade + imperial only | 291.1 | 1.06× — still a loss, having dropped metric contours entirely |

### And that is the cheap version of the question

Those rows stop at z13. The app does not: `terrain.ts` caps the DEM at
`DEM_MAX_ZOOM = 13` but draws contours to `CONTOUR_MAX_ZOOM = 15`, overzooming
the same tiles, and the imperial ladder has a *finer* entry at z14 (20 ft)
than at z13. Live that costs nothing, because the lines come from tiles already
on the phone. Baked, every one of those tiles has to exist.

**Measured** by generating the 4 z14 and 16 z15 children of each z13 tile —
the same ground, so the sum is directly comparable:

| | z13 | z14 (4 tiles) | z15 (16 tiles) |
|---|---|---|---|
| multiplier vs z13 | 1× | **2.69×** | **5.34×** |

So a baked set matching what a hiker sees today is roughly **0.98 GB for the
imperial ladder alone** (*reasoned* from the measured multiplier), against
275.6 MB that serves both ladders to z15 by overzooming. This is the finding
that closes the question rather than merely settling it: the DEM is not
competing with a baked archive of the same size, it is competing with one
several times larger, because a raster of elevation is *reusable* in a way a
rendered line is not.

### What baking would also freeze

Not bytes, and worth stating because a future proposal will be tempted to trade
them away without noticing:

- **exaggeration** — `HILLSHADE_EXAGGERATION` is 0.30, and the sheet variants
  ship 0.30, 0.35 and 0.55 (`liveTopo.ts`). One bake serves one of them.
- **colour** — every palette sets its own `hillshade-shadow-color`,
  `-highlight-color` and `-accent-color` through `SHEET_COLOURS`. MapLibre's
  hillshade shader composes those three from the elevation gradient; a baked
  grayscale raster cannot be decomposed back into them.
- **contour interval and unit**, per the table above — which is the same
  objection `terrain.ts` already raised against baked contours for the live
  map, arriving here from the other direction.

### Overzoom, and an honest reading of it

Under the 4× magnification the client displays (z13 shown to z15), a baked
tile is magnified *as an image* — shade then magnify, where the shipped path
magnifies elevation then shades. % of pixels shifted >8/255 against
unquantized truth, z13:

| shipped (0.5 m floor) | baked lossless | baked q85 |
|---|---|---|
| 0.01% | **6.56%** | 7.93% |

**The codec contributes about 1.4 points of that; the rest is the order of
operations**, which is why the lossless column is measured and shown. That
distinction matters for anyone re-reading this: the difference is mostly
*blur* — shade-then-magnify declines to invent the detail that
magnify-then-shade interpolates into existence, and neither has real z15
information. It is not the terracing that sank the 1 m floor. It is recorded
here because it is a difference the metric sees, not because baking was
rejected on it. **Baking was rejected on bytes.**

### The one shape where baking wins

Falling out of the same table rather than proposed on top of it: a baked
hillshade is **0.28–0.42× the bytes of the DEM tile covering the same ground**
at q75–q85. That makes it a cheap way to **extend relief past the taper's
edge**, not a way to replace the DEM inside it — the taper drops z13 terrain
beyond 6 miles (3 at Light), and a hiker out there gets no shading at all
today. Relief context with no contours is a poor substitute for terrain near
the trail and a strictly better answer than blank paper far from it.

Nobody has asked for that, it is *not* a recommendation, and it would need
its own issue and its own acceptance test. It is recorded because the
measurement is already paid for and the next person to open this file should
not have to re-derive it.

### Two more levers, found while pricing the bake (#1486)

Both fell out of the same rig and neither is proposed here. They are recorded
because the measurements are already paid for, and because **one of them
qualifies this document's opening sentence.**

**Encoder effort is the one per-unit-area lever that does not fail**, and it
costs build minutes rather than fidelity. `export_dem.encode_tile` saved at
Pillow's WebP defaults (`method=4`, `quality=80`) — never chosen, simply what
the library does when asked for nothing. In *lossless* mode `quality` is
libwebp's search effort and not image quality, so the pixels return
bit-identical at any setting.

**The first version of this section quoted 6.4 MB and called it free. Both
halves were wrong, and the second is the instructive one.** That figure was
`method=6, quality=100`, and the time it costs had not been measured. It was,
on 2026-09-16, on 4 cores — the free runner's shape — and timed at 8 workers
over the canonical build's 8,658 tiles:

| setting | z11 | z12 | z13 | off `dem.pmtiles` | encode |
|---|---|---|---|---|---|
| `method=4, quality=80` (was) | — | — | — | — | 1.8 min |
| **`quality=100` (shipped, #1506)** | −0.65% | −1.16% | −1.76% | **3.1 MB** | **6.4 min** |
| `method=6, quality=100` | −0.74% | −1.98% | −4.26% | 6.5 MB | **72.5 min** |
| `method=6, quality=90` | −0.08% | −0.16% | −0.43% | 0.6 MB | 3.2 min |
| `method=2, quality=100` | +1.78% | +0.57% | +0.58% | *larger* | 1.1 min |

**`quality` is the lever and `method` is a trap.** The deep end of `method`
buys another 3.4 MB for **+66 minutes** of encode, and it would land on the
light build and every cell cut as well. `quality=100` alone is +4.6 minutes for
1.1% of the archive, which is the trade
**#1506 — The DEM encodes at PIL's WebP defaults, and one of them costs 3.1 MB
for nothing** made.

> **This paragraph said "+66 minutes … on a six-hour job" and the denominator
> was invented.** The DEM build is not six hours: run 52 (canonical, 8,658
> tiles) took **5 min 21 s** end to end, and `build-dem.yml` caps the job at
> `timeout-minutes: 120`. So +66 minutes is about **thirteen times the whole
> run**, not a fifth of it. The conclusion is unchanged and in fact stronger;
> the arithmetic supporting it was fiction, and it sat under a *measured*
> heading, which is how it went unchallenged. Corrected 2026-09-16 against the
> Actions API.
>
> **And the accepted cost is now measured too, which the projection did not
> survive.** The first canonical build after #1506 (run 54) against the last
> before it (run 52), same 8,658 tiles: the "Build the DEM archive" step went
> **3 min 08 s → 8 min 59 s**, so **+5 min 51 s (2.9×)** rather than the
> projected +4.6 minutes — 27% more, and nearly tripling the step where this
> file said "roughly doubles". Still comfortable against a 120-minute cap, and
> still the right trade; but a projection that a real run contradicts is worth
> replacing with the run rather than defending.

So "every lever that makes the terrain cheaper per unit area fails the project's
own acceptance test" is true of every lever that changes the *pixels* and false
of the one that only changes how they are packed — but "free" was the wrong
word for it, and a lever whose cost nobody had measured had no business being
called that.

**The half-metre bit is 31% of the archive and mostly buys nothing.** At
`QUANTIZE_STEP_M = 0.5` the blue channel holds one bit per pixel — it takes only
0 or 128 — and that bit is close to incompressible: the same 162 tiles weigh
6,017 KB at 0.5 m against 4,152 KB at 1 m, so **31.0%** of the archive is that
one bit. It exists to stop the 1 m staircase banding under overzoom, and
`spike_dem_banding.py` already found that banding is a *flat-ground*
phenomenon — mountainsides hide it. Per tile, 4× overzoomed, % of hillshade
pixels a 1 m floor shifts >8/255:

| tile relief (σ, m) | n | at exag 0.30 | at exag 0.55 | 0.5 m | 1 m |
|---|---|---|---|---|---|
| under 15 | 11 | 3.33% | 20.3% | 19.2K | 12.1K |
| 15–100 | 59 | 0.89% | 5.9% | 33.9K | 22.7K |
| over 100 | 92 | 0.85% | 4.4% | 41.4K | 29.1K |

So the bit earns its keep on the ground it was bought for and is close to waste
everywhere else — and "everywhere else" is most of a trail corridor. Keeping
0.5 m only where a 1 m floor shifts more than 2% of pixels at the worst shipped
exaggeration drops 94 of 162 tiles to 1 m for an archive **19.4% smaller**
(~53 MB), with no tile rendering worse than the threshold allows.

@unvalidated, and the gap is specific: **the seam between the two regimes has
not been looked at once.** Adjacent tiles either side of the threshold carry
different noise floors, and whether that shows as an edge under a hillshade is
exactly the question this table does not answer. The threshold itself is picked,
not derived. The flat end of the sample is also thin — 11 tiles under 15 m of
relief, from six areas chosen for a different question — so the row that matters
most for the decision is the row with the least behind it. What would settle it:
the same render-and-compare this file already runs, over a tile pair straddling
a real threshold boundary, at all three shipped exaggerations.

### Calibration, and the bias in this sample

Four of the six areas are mountainous, so the sample is denser than the
corridor: arm A runs **+15.6% (z11), +11.0% (z12), +5.9% (z13)** against the
published mean bytes/tile. Contour bytes scale with relief far harder than DEM
bytes do, so that bias cannot simply be carried across.

Every projection above is therefore **calibrated** rather than scaled: per zoom,
contour and hillshade bytes are regressed against DEM bytes across the six
areas and evaluated at the published mean bytes/tile — the one corridor-wide
anchor that exists without a full rebuild. The fits are tight (r = 0.95–0.97
for contours, 0.84–0.99 for the hillshade). Uncalibrated, the contour total
would read 367.5 MB rather than 317.8; the conclusion does not turn on which is
used, which is the only reason a regression over six points is good enough here.

**What would settle it properly:** running `export_dem.py`'s own tile
enumeration over the real corridor and baking the whole thing, which is a
build-scale job and not worth it for a lever this far from breaking even.

## What was rejected, so nobody re-proposes it

| proposal | why not |
|---|---|
| COG + LZW/DEFLATE | The phone decodes tiles through `createImageBitmap`; MapLibre's `raster-dem` speaks PNG and WebP. A COG is unreadable on the client. The idea behind it — smaller, no elevation loss — is already spent at 6.2× (`export_dem.py`). |
| TIN / mesh decimation | No mesh exists to decimate; there is no `setTerrain` in the client. |
| Lossy compression of terrarium | A 1-LSB error in the red channel is 256 m. Measured RMSE 2,771 m at q95, and *larger* files than lossless above q75. |
| Client-side truncation of a bigger archive | *"A download must be exactly the bytes its advertised size and published hash describe"* (PR #283). Breaks the hash contract, resume and the size promise at once. |
| Baking hillshade and contours instead of shipping the DEM | **Measured 2026-09-15 and rejected** — see the section below. Baking both units costs 448.7 MB against the DEM's 275.6, and matching the zoom the app actually draws contours at costs about a gigabyte for one unit. This row said "not measured" until #1486; the reasoning that made it attractive was right, and the arithmetic still lost. |
