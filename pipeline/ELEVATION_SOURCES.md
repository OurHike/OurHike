# Elevation data sources — a qualified survey (August 2026)

Companion to [README.md](README.md), [SOURCE_SURVEY.md](SOURCE_SURVEY.md) (the same
exercise for trail and POI sources) and [../features/ELEVATION_PROFILE.md](../features/ELEVATION_PROFILE.md)
(what the profile is used for). Written 2026-08-12 from live probes against every source
named below; every number here was measured that day, not quoted from a vendor page.

Why this exists: the elevation leg of the publish has been failing, and the question asked
was whether a better data source exists. The answer turns out to be **no for the data and
yes for the way we reach it** — so this survey qualifies the alternatives properly, and
then says which part of the current setup is actually broken.

The frame, borrowed from SOURCE_SURVEY.md and reordered for a raster:

1. **Vertical accuracy beats resolution.** Cumulative ascent sums every rise along the
   line, so a noisier DEM does not merely blur the profile, it *inflates the total* — and
   that total feeds the Naismith estimate. A source is better only if it makes the sum
   more truthful.
2. **Deterministic beats discoverable.** A URL that can be computed cannot 504.
3. **Public domain beats permissive.** Same rule CONTRIBUTING.md applies to every source.
4. **Fewer moving parts beats richer metadata.** Every catalog between us and the bytes is
   another thing that can be down at 12:16 on a Wednesday.

---

## 0. The short answer

**Keep the data. Drop the catalog.**

USGS 3DEP 1/3 arc-second is already the best available elevation source for this corridor,
and nothing tested beats it. What is failing is not 3DEP — it is the **TNM Access API**
(`tnmaccess.nationalmap.gov`), the discovery layer `fetch_elevation.py` uses to find out
which 3DEP tiles to read.

That discovery layer is unnecessary. The 1/3 arc-second product is a **uniform 1-degree
grid with a deterministic public URL per cell**, and USGS already publishes the newest
edition of each cell under a `current/` path. Every tile the corridor needs can be named
by arithmetic:

```
https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/13/TIFF/current/n35w085/USGS_13_n35w085.tif
                                                                        ^^^^^^^
                                          n{ceil(lat)}w{ceil(-lon)} — the cell's NW corner
```

Measured against the real centerline buffered 30 miles: **56 of 56 corridor cells resolve,
with zero discovery requests.** The 51 TNM queries, their retry ladder, their per-cell
disk cache, the edition-deduplication and the shrink write-gate all exist to survive a
dependency that does not need to be there.

---

## 1. What is actually failing, with the evidence

Two publish runs died on 2026-08-12, both inside `fetch_elevation.py`, both before
anything was exported:

| run | started | died at |
|---|---|---|
| [31592776758](https://github.com/OurHike/OurHike/actions/runs/31592776758) | 11:38 UTC | `fetch_elevation.py` |
| [31595636184](https://github.com/OurHike/OurHike/actions/runs/31595636184) | 12:16 UTC | cell 9 of 51 |

The second run's log is the useful one. **Every single cell 504'd at least twice** before
succeeding:

```
TNM cell -83.73,34.20 answered 504 on attempt 1/5, retrying in 5s
TNM cell -83.73,34.20 answered 504 on attempt 2/5, retrying in 15s
cell 3/51: 16 candidate(s) from TNM, 7 new corridor-intersecting tile(s)
...
TNM cell -81.73,36.20 answered 504 on attempt 4/5, retrying in 60s
requests.exceptions.HTTPError: 504 Server Error: Gateway Timeout
```

This is not the single unlucky 504 that [#536](https://github.com/OurHike/OurHike/issues/536)
was written for. It is a sustained degradation in which the retry ladder is being spent in
full on nearly every request, and the ninth cell exhausts it.

### The #536 mitigation does not survive the failure it was built for

`fetch_elevation.py` writes each cell's TNM answer to `data/raw/elevation/tnm_cells/`
immediately, precisely so a run that dies on cell 37 keeps cells 1–36. That is correct,
and on a developer's machine it works.

In CI it does not, and the log proves it. The 12:16 run started 38 minutes after the 11:38
failure, and read **every** cell `from TNM` — not one `from cache`. The reason is the
workflow step:

```yaml
- name: Restore the TNM catalogue cache
  uses: actions/cache@v4        # <- saves in a post step that is skipped on job failure
  with:
    path: pipeline/data/raw/elevation/tnm_cells
```

The POI photo step two hundred lines above already knows this, and splits
`actions/cache/restore@v4` from an explicit save. The elevation step uses the combined
action, so partial progress is discarded on exactly the runs that had partial progress
worth keeping.

**That is a real bug and worth fixing on its own merits.** But it is a better retry around
a dependency that can be deleted outright, which is what the rest of this survey is about.

---

## 2. The complete candidate list

Everything examined, one line each. "Discovery" is what has to be asked before a byte of
elevation can be read.

| source | resolution | coverage | discovery | licence | measured verdict |
|---|---|---|---|---|---|
| **3DEP 1/3 arc-second, static `current/` grid** | ~10 m | CONUS + AK/HI/PR | **none — computed** | public domain | **recommended — §3** |
| 3DEP 1/3 arc-second via TNM Access API | ~10 m | same bytes | 51 API calls | public domain | in use; the failing part — §1 |
| 3DEP 1 metre | 1 m | patchy, project-based | irregular, needs a catalog | public domain | ~1 TB, and finer is not better here — §4 |
| Copernicus DEM GLO-30 | 30 m | global | computed | free, attribution | **+36% gain error in GA** — §5 |
| `elevation-tiles-prod` terrarium z13 | ~10–20 m | global | computed | mixed | **2017 snapshot**; already our hillshade — §6 |
| 3DEP ImageServer `identify` | ~10 m | seamless | none | public domain | **1.88 s/point → ~74 h** — §7 |
| USGS EPQS point query | ~10 m | seamless | none | public domain | same shape as above — §7 |
| OpenTopography API | various | global | API key | varies | adds a dependency, hosts the same 3DEP — §8 |
| State LiDAR portals (14 states) | 1 m–1 ft | per-state | 14 separate schemes | per-state | fragmentation for no accuracy gain — §8 |

---

## 3. The recommendation: the static 3DEP grid

### It is a real uniform grid, and the docstring says otherwise

`fetch_elevation.py`'s module docstring argues at length that 3DEP has no simple
grid-and-listing scheme, "unlike the topo quads":

> 1m DEM tiles are grouped into irregular per-LiDAR-acquisition "project" folders […] so
> there's no simple state-prefix listing scheme […] Tile filenames aren't consistent
> either

Every word of that is true — **of the 1-metre product**, which is what those sentences
describe. But `DATASET` is `National Elevation Dataset (NED) 1/3 arc-second`, and the
1/3 arc-second product is laid out completely differently: a fixed 1° × 1° grid, one
folder per cell, named from the cell's north-west corner. The reasoning that justified
reaching for TNM Access was written about a dataset the script does not use.

### Verified, not assumed

Probed 2026-08-12 against the real ANST centerline (3,025 features, fetched from the NPS
layer and buffered 30 miles the way `lib/corridor.py` does):

```
56 1-degree cell(s) within 30 miles of the centerline.
  present in the S3 listing: 56
  absent from the S3 listing: 0
HEADing every corridor cell's deterministic current/ URL...
  200 OK: 56 / 56
```

Tile properties, read through `/vsicurl/` exactly as `ElevationSampler` would:

| | |
|---|---|
| CRS | EPSG:4269 (NAD83) — `WarpedVRT` already reprojects, no code change |
| size | 10812 × 10812, float32 |
| internal tiling | 512 × 512, **overviews [2, 4, 8, 16, 32]** |
| nodata | -999999.0 |
| range requests | `Accept-Ranges: bytes` — a genuine COG |
| per tile | ~460–480 MB (25.5 GB across the corridor, **none of it downloaded**) |

These are the same Cloud-Optimized GeoTIFFs on the same bucket the pipeline already
streams from. The sampling stage does not change at all, and does not get faster — the
saving is that the 51 catalog calls in front of it disappear.

### USGS already solved the multiple-editions problem

`fetch_elevation.py` carries a CORRECTION block about editions:

> n35w084 alone has four editions (20220504, 20220512, 20220725, 20230215), separated only
> by a date in the filename […] `build_tile_index` keeps the newest edition per footprint.

That is a real hazard, and the fix is real. It is also already solved upstream — the
bucket separates `current/` from `historical/`:

```
current/n35w084/     1 tif   USGS_13_n35w084.tif
historical/n35w084/  6 tifs  ..._20100929  ..._20130911  ..._20220504
                             ..._20220512  ..._20220725  ..._20230215
```

`current/`'s `Last-Modified` matches the newest dated edition in `historical/` on every
cell checked (n35w084 → 2023-02-15; n46w069 → 2026-05-21 vs `_20260515`; n41w074 →
2024-09-26 vs `_20240925`). The TNM catalog returns historical editions mixed in with
current ones, which is *why* the dedup was needed. Asking the `current/` path asks a
question that cannot have a wrong answer.

So `_edition_of()`, the footprint-keyed `best` dict, and the "undated filename sorts
lowest" rule all become unnecessary — not because the hazard was imaginary, but because
the new path does not expose it.

### Coverage can still be checked, cheaply

The bucket is publicly listable. Two paginated requests enumerate **1,420 cell folders
nationwide**, which is a complete coverage answer for the entire country in less traffic
than one current per-cell query. That is optional — a computed URL that 404s is already an
honest "no coverage here", and `ElevationSampler` already returns `None` for an uncovered
point — but it means a coverage regression can still be detected up front if the write
gate is worth keeping.

---

## 4. 3DEP 1 metre — and a correction to the note that rejected it

`export_elevation.py` says going finer than 25 m sampling would need a finer DEM, and
points at `fetch_elevation.py`'s note for why 1 m is wrong — "not least that it has no
coverage at all at the northern terminus."

**That last claim is now out of date.** Katahdin/Baxter Peak (45.9044, -68.9214) falls in
UTM 19 cell x50y508, and that tile exists:

```
StagedProducts/Elevation/1m/Projects/ME_Eastern_B1_2017/TIFF/USGS_one_meter_x50y508_ME_Eastern_B1_2017.tif
```

Nineteen Maine LiDAR projects are staged on the bucket. The northern terminus is covered.

**It does not change the recommendation.** The other reasons stand and are the stronger
ones: roughly 1 TB for this corridor, an irregular project layout that genuinely does need
a catalog to navigate (so it would *reintroduce* the TNM dependency this survey is
removing), and — most importantly — §5 below demonstrates that resolution and accuracy are
not the same thing when the output is a *sum*. 1 m DEM exists to measure boulders and
building footprints. Worth correcting the note; not worth acting on.

---

## 5. Copernicus GLO-30 — the global option, measured and rejected

The obvious "better source altogether" candidate: 30 m, global, free, on AWS Open Data
with computed URLs and no catalog at all. If it were good enough it would solve the
discovery problem *and* unlock any trail outside the US.

It is not good enough. Sampled on real AT tread at the pipeline's own 25 m interval, and
summed with the pipeline's own `cumulative_gain_over_gaps` at its 3 m dead band:

| stretch | 3DEP 1/3 (~10 m) | Copernicus GLO-30 | terrarium z13 |
|---|---|---|---|
| GA — Springer/Blood Mtn (33.8 mi) | **13,718 ft** | 18,717 ft (**+36.4%**) | 14,305 ft (+4.3%) |
| PA — rocks near Lehigh Gap (13.3 mi) | **7,045 ft** | 7,537 ft (+7.0%) | 7,124 ft (+1.1%) |
| NH — Presidentials (16.2 mi) | **26,588 ft** | 26,746 ft (+0.6%) | 26,574 ft (−0.1%) |
| ME — Bigelow/Katahdin approach (17.6 mi) | **21,616 ft** | 22,113 ft (+2.3%) | 21,415 ft (−0.9%) |

Two things to read off this.

**The error is worst exactly where it hurts most.** Georgia is the densely-forested,
tightly-switchbacked terrain at the start of a thru-hike, and GLO-30 overstates the climb
there by more than a third. GLO-30 is a *surface* model built from radar — it sees the
forest canopy, and under southern Appalachian tree cover the canopy is not the ground.
Above treeline in the Presidentials the two sources agree to 0.6%, which is the tell.

**It also produced a floor of 0 ft** across the Georgia stretch (3DEP's minimum there is
2,518 ft) — GLO-30's void-filled cells reading as zero. A profile that dips to sea level
in north Georgia is not a subtle inaccuracy.

Worth revisiting only if OurHike ever covers ground 3DEP does not, and then as a
per-region fallback rather than a replacement.

---

## 6. The terrarium tiles — closest match, and an incidental finding

`elevation-tiles-prod` terrarium tiles came closest to 3DEP (−0.9% to +4.3%), which is
unsurprising: in CONUS that mosaic is largely derived from NED, so it is mostly 3DEP with
a resampling step in front of it.

It is still not the right source for the profile. `Last-Modified` on a z13 tile over the
AT reads **12 November 2017**. It is a nine-year-old snapshot of mixed global provenance,
and taking a derived, undated re-tiling of 3DEP in preference to 3DEP itself would be
choosing the copy over the original.

**The incidental finding is worth more than the comparison.** `export_dem.py`'s
`DEM_TILE_URL` *is* that bucket — so the app currently ships two different elevation
truths: the profile and its gain figures from current 3DEP, and the 3D terrain and
hillshade the hiker actually looks at from a 2017 mosaic. They agree closely enough that
nothing looks wrong, and no hiker will ever notice. But once the profile is reading a
deterministic 3DEP grid, building the client's DEM tiles from that same grid becomes
straightforward, and the app would have one elevation truth instead of two. That is a
separate piece of work and probably post-v1; recorded here because this is where the
evidence for it turned up.

---

## 7. Point-query services — right answer, wrong shape

Both USGS point services work, need no key, and need no discovery:

```
$ 3DEPElevation/ImageServer/identify  @ Springer
{"value":"1139.2", ...}    HTTP 200  time=1.88s
```

At 1.88 s per point, the full profile's ~141,000 samples would take **about 74 hours**
served one at a time, before any rate limiting. These are the correct tool for looking up
a handful of elevations — a single waypoint, a spot check, a test fixture — and the wrong
one for building a profile. Noted so nobody re-derives that.

---

## 8. OpenTopography, state LiDAR

**OpenTopography** hosts 3DEP among other datasets and will clip server-side, which is
genuinely useful for one-off extracts. For this pipeline it means an API key, a quota, and
a third party between us and bytes that USGS serves us directly — it *adds* a discovery
dependency to solve a problem caused by a discovery dependency.

**State LiDAR portals** (PA, VT, ME and others publish their own high-resolution
products) mean fourteen separate schemes, fourteen licence questions, and fourteen things
to re-check each season, in exchange for resolution §5 shows we should not want. Not
worth it for a trail that crosses all fourteen.

---

## 9. What this changes in the code

Not written here — this survey is the reconnaissance, and the work belongs in an issue
against it. In outline, `fetch_elevation.py` loses most of its reason to exist:

- `compute_grid_cells()` / `list_products_for_cell()` / `cell_products()` / the per-cell
  cache / `TNM_BACKOFF_SECONDS` — **all removable.** The corridor bbox already gives the
  cell list; the URL is a format string.
- `build_tile_index()` keeps its corridor-polygon filter (still worth not reading tiles
  the trail never crosses) and loses `_edition_of()` and the footprint dedup — §3.
- `bounds` for each tile come from the cell name arithmetically, rather than from TNM's
  `boundingBox`.
- `write_gate_problems()` becomes near-vacuous, since a computed cell list cannot shrink
  because a server was slow. Whether to keep it as a guard against a corridor-geometry
  regression is a judgement call for whoever does the work.
- `export_elevation.py` **does not change at all.** Same COGs, same `/vsicurl/`, same
  `WarpedVRT`, same sampling.

The workflow's `actions/cache@v4` step goes away with the cache it guards. If the static
grid is not adopted, that step still needs the `restore`/`save` split the photo cache
already uses — §1.

---

## 10. Marked for maintainer review

| item | why it needs eyes | where |
|---|---|---|
| Adopt the static grid, or just fix the cache? | The cache split is a two-line fix; the static grid deletes ~200 lines and a dependency. Both are defensible; only one is worth the review. | §1, §9 |
| Keep `write_gate_problems()`? | It guards against a failure mode that computed URLs cannot have, but still catches a corridor-geometry regression. | §9 |
| One elevation truth for terrain and profile | Real, small, and probably post-v1 — but it is a genuine inconsistency someone will eventually find. | §6 |
| The 1 m Katahdin note | Factually out of date in `fetch_elevation.py`; the conclusion it supports is still right. | §4 |
| Copernicus as a non-US fallback | Only matters if OurHike ever leaves 3DEP's footprint. | §5 |

---

*Method note for whoever refreshes this: every claim above is one `curl -I` against
`prd-tnm.s3.amazonaws.com` away from re-verification, and the source comparison is one run
of the sampling in §5 — real centerline, 25 m interval, `lib/elevation_gain.py`'s own dead
band, so the numbers are directly comparable to what `export_elevation.py` reports. Re-run
it before trusting these figures a year from now; 3DEP re-flies on a multi-year cycle and
the Georgia cells in particular were last revised in 2023 and 2026.*
