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

Against UA's untapered 607.3 MB that is **54.6% off the DEM**, and the Standard
hiking sheet goes 789.9 → **458.1 MB, 42.0% off**, with the basemap untouched.

The projection this replaces said 275.4 MB, which is 0.1 MB out — and that
agreement is luckier than it looks. Per band it was wrong in both directions
and the errors happened to cancel: z0–9 and z10 came in 6.4 MB *under* the
projection, z12 and z13 5.0 MB *over*. The stated bias — that a narrow corridor
keeps the ridgeline tiles, which carry more relief and compress worse — held
exactly where it was claimed (the two tapered bands) and reversed where the
corridor did not narrow. **A per-zoom mean bytes/tile is not transferable
across a change of footprint**, and the total agreeing is not evidence that it
is.

Other schedules, still **reasoned** on the same method and therefore carrying
the caveat above:

| schedule z11/z12/z13 | DEM MB | off DEM | sheet MB | off sheet |
|---|---|---|---|---|
| shipped, uniform 30 | 607.3 | — | 789.9 | — |
| **30/15/6 (built)** | **275.6** | **54.6%** | **458.1** | **42.0%** |
| 30/10/6 | ~229 | ~62% | ~411 | ~48% |
| 20/6/3 | ~159 | ~74% | ~342 | ~57% |

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

- `cut_stretches.py:1-10` and `pipeline/README.md`'s "The 50-mile stretch units
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

- **A light build does not cut stretches.** `cut_stretches.py` names its output
  from the family, so a light run would overwrite `dem_stretch_NN.pmtiles` with
  light bytes under the canonical keys — a quieter version of the
  wrong-bytes-behind-the-right-name failure the publish gate exists to prevent.
  A light stretch set needs its own family before it can be cut at all.
- **The artifact is named per variant**, so the publish job cannot download one
  variant's archive and upload it under the other's key.

`publish.py` already knew `dem_light.pmtiles`; what was missing was any way to
produce it. **It is still unbuilt**, so `hikingDetail.ts` keeps the Light level
at `published: false` with a null size. The rung lights up when a build has run
and its bytes have been measured — not before, for the reason `packages.ts`
records as "a 404 on a mountain".

@unvalidated — 20/6/3 is picked. Against a tapered Standard at 458.1 MB, a
Light sheet lands around 342 MB on the same reasoning that projected Standard,
which the build above showed to be trustworthy in total and not per band. That
is a ~116 MB gap for a choice a hiker has to understand, and whether it is
worth a rung at all is still the open question at the end of this document.

## What was rejected, so nobody re-proposes it

| proposal | why not |
|---|---|
| COG + LZW/DEFLATE | The phone decodes tiles through `createImageBitmap`; MapLibre's `raster-dem` speaks PNG and WebP. A COG is unreadable on the client. The idea behind it — smaller, no elevation loss — is already spent at 6.2× (`export_dem.py`). |
| TIN / mesh decimation | No mesh exists to decimate; there is no `setTerrain` in the client. |
| Lossy compression of terrarium | A 1-LSB error in the red channel is 256 m. Measured RMSE 2,771 m at q95, and *larger* files than lossless above q75. |
| Client-side truncation of a bigger archive | *"A download must be exactly the bytes its advertised size and published hash describe"* (PR #283). Breaks the hash contract, resume and the size promise at once. |
| Baking hillshade and contours instead of shipping the DEM | Not rejected — **not measured.** `terrain.ts` rejected baked contours for the live map (interval must follow zoom and unit preference), and one of its three reasons — *"it costs no storage and no extra download"* — inverts under a size budget. A baked hillshade would also tolerate lossy compression, which terrarium cannot. It is the largest unmeasured idea here and deserves its own spike. |
