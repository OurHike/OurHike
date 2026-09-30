# Elevation data sources — a qualified survey (August 2026, restored and updated September 2026)

Companion to [README.md](README.md), [SOURCE_SURVEY.md](SOURCE_SURVEY.md) (the same
exercise for trail and POI sources) and [../features/ELEVATION_PROFILE.md](../features/ELEVATION_PROFILE.md)
(what the profile is used for). Written 2026-08-12 from live probes against every source
named below; every number in §§1–8 was measured that day, not quoted from a vendor page.
§9 and §10 are rewritten 2026-09-17 to describe what actually shipped, five weeks later.

**Why this file did not exist until now, despite being cited.** The original survey was
[PR #549](https://github.com/OurHike/OurHike/pull/549) against this issue
(**#548 — Survey elevation data sources: is there a better one than 3DEP-via-TNM for
v1?**); the PR was closed on 2026-09-09 without merging, for no reason recorded on it, and
the document never landed. Everything that read it in the meantime had to take it on
faith: `fetch_elevation.py`'s own docstring says *"pipeline/ELEVATION_SOURCES.md section 3
is the survey that established that (#548, #549)"* pointing at a file that was not in the
tree, and `pipeline/README.md` never gained the link the closed PR added. This restores
the content (§§0–8 are the original survey, unchanged) and brings §9–10 up to date with
what actually happened since.

Why this exists: the elevation leg of the publish was failing, and the question asked
was whether a better data source exists. The answer turns out to be **no for the data and
yes for the way it was reached** — so this survey qualifies the alternatives properly, and
then says which part of the original setup was actually broken.

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

USGS 3DEP 1/3 arc-second was already the best available elevation source for this
corridor, and nothing tested beat it. What was failing was not 3DEP — it was the **TNM
Access API** (`tnmaccess.nationalmap.gov`), the discovery layer `fetch_elevation.py` used
to find out which 3DEP tiles to read.

That discovery layer turned out to be unnecessary. The 1/3 arc-second product is a
**uniform 1-degree grid with a deterministic public URL per cell**, and USGS already
publishes the newest edition of each cell under a `current/` path. Every tile the corridor
needs can be named by arithmetic:

```
https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/13/TIFF/current/n35w085/USGS_13_n35w085.tif
                                                                        ^^^^^^^
                                          n{ceil(lat)}w{ceil(-lon)} — the cell's NW corner
```

Measured against the real centerline buffered 30 miles: **56 of 56 corridor cells
resolved, with zero discovery requests.** Spot-checked live again tonight (2026-09-17):
`current/n35w084/USGS_13_n35w084.tif` and `current/n46w069/USGS_13_n46w069.tif` both still
answer `200` with `Accept-Ranges: bytes`, five weeks on — the scheme has not moved. The 51
TNM queries, their retry ladder, their per-cell disk cache, the edition-deduplication and
the shrink write-gate all existed to survive a dependency that did not need to be there.
**This is now the code, not a proposal — see §9.**

---

## 1. What was actually failing, with the evidence

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

This was not the single unlucky 504 that [#536](https://github.com/OurHike/OurHike/issues/536)
was written for. It was a sustained degradation in which the retry ladder was being spent
in full on nearly every request, and the ninth cell exhausted it.

### The #536 mitigation did not survive the failure it was built for

`fetch_elevation.py` wrote each cell's TNM answer to `data/raw/elevation/tnm_cells/`
immediately, precisely so a run that died on cell 37 kept cells 1–36. That was correct,
and on a developer's machine it worked.

In CI it did not, and the log proved it. The 12:16 run started 38 minutes after the 11:38
failure, and read **every** cell `from TNM` — not one `from cache`. The reason was the
workflow step:

```yaml
- name: Restore the TNM catalogue cache
  uses: actions/cache@v4        # <- saves in a post step that is skipped on job failure
  with:
    path: pipeline/data/raw/elevation/tnm_cells
```

The POI photo step two hundred lines above already knew this, and split
`actions/cache/restore@v4` from an explicit save. The elevation step used the combined
action, so partial progress was discarded on exactly the runs that had partial progress
worth keeping. **Moot now — §9: the whole cache and the dependency it guarded are gone.**

---

## 2. The complete candidate list

Everything examined, one line each. "Discovery" is what has to be asked before a byte of
elevation can be read.

| source | resolution | coverage | discovery | licence | measured verdict |
|---|---|---|---|---|---|
| **3DEP 1/3 arc-second, static `current/` grid** | ~10 m | CONUS + AK/HI/PR | **none — computed** | public domain | **recommended, now shipped — §3, §9** |
| 3DEP 1/3 arc-second via TNM Access API | ~10 m | same bytes | 51 API calls | public domain | replaced — was the failing part, §1 |
| 3DEP 1 metre | 1 m | patchy, project-based | irregular, needs a catalog | public domain | ~1 TB, and finer is not better here — §4 |
| Copernicus DEM GLO-30 | 30 m | global | computed | free, attribution | **+36% gain error in GA** — §5 |
| `elevation-tiles-prod` terrarium z13 | ~10–20 m | global | computed | mixed | **2017 snapshot**; still the client's hillshade — §6 |
| 3DEP ImageServer `identify` | ~10 m | seamless | none | public domain | **1.88 s/point → ~74 h** — §7 |
| USGS EPQS point query | ~10 m | seamless | none | public domain | same shape as above — §7 |
| OpenTopography API | various | global | API key | varies | adds a dependency, hosts the same 3DEP — §8 |
| State LiDAR portals (14 states) | 1 m–1 ft | per-state | 14 separate schemes | per-state | fragmentation for no accuracy gain — §8 |

---

## 3. The recommendation: the static 3DEP grid

### It is a real uniform grid, and the docstring said otherwise

`fetch_elevation.py`'s module docstring used to argue at length that 3DEP had no simple
grid-and-listing scheme, "unlike the topo quads":

> 1m DEM tiles are grouped into irregular per-LiDAR-acquisition "project" folders […] so
> there's no simple state-prefix listing scheme […] Tile filenames aren't consistent
> either

Every word of that was true — **of the 1-metre product**, which is what those sentences
described. But `DATASET` was `National Elevation Dataset (NED) 1/3 arc-second`, and the
1/3 arc-second product is laid out completely differently: a fixed 1° × 1° grid, one
folder per cell, named from the cell's north-west corner. The reasoning that justified
reaching for TNM Access was written about a dataset the script did not use.

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
streamed from. The sampling stage did not change at all — the saving was that the 51
catalog calls in front of it disappeared.

### USGS already solved the multiple-editions problem

`fetch_elevation.py` used to carry a CORRECTION block about editions:

> n35w084 alone has four editions (20220504, 20220512, 20220725, 20230215), separated only
> by a date in the filename […] `build_tile_index` keeps the newest edition per footprint.

That was a real hazard, and the fix was real. It was also already solved upstream — the
bucket separates `current/` from `historical/`:

```
current/n35w084/     1 tif   USGS_13_n35w084.tif
historical/n35w084/  6 tifs  ..._20100929  ..._20130911  ..._20220504
                             ..._20220512  ..._20220725  ..._20230215
```

`current/`'s `Last-Modified` matched the newest dated edition in `historical/` on every
cell checked (n35w084 → 2023-02-15; n46w069 → 2026-05-21 vs `_20260515`; n41w074 →
2024-09-26 vs `_20240925`). The TNM catalog returned historical editions mixed in with
current ones, which is *why* the dedup was needed. Asking the `current/` path asks a
question that cannot have a wrong answer.

So `_edition_of()`, the footprint-keyed `best` dict, and the "undated filename sorts
lowest" rule all became unnecessary — not because the hazard was imaginary, but because
the new path does not expose it. `build_tile_index()` no longer carries either — §9.

### Coverage can still be checked, cheaply

The bucket is publicly listable. Two paginated requests enumerate **1,420 cell folders
nationwide**, which is a complete coverage answer for the entire country in less traffic
than one current per-cell query. That was optional — a computed URL that 404s is already
an honest "no coverage here", and `ElevationSampler` already returns `None` for an
uncovered point — but it means a coverage regression can still be detected up front if the
write gate is worth keeping. It was: `write_gate_problems()` shipped — §9.

---

## 4. 3DEP 1 metre — and a correction to the note that rejected it

`export_elevation.py` said going finer than 25 m sampling would need a finer DEM, and
pointed at `fetch_elevation.py`'s note for why 1 m was wrong — "not least that it has no
coverage at all at the northern terminus."

**That last claim was out of date.** Katahdin/Baxter Peak (45.9044, -68.9214) falls in
UTM 19 cell x50y508, and that tile exists:

```
StagedProducts/Elevation/1m/Projects/ME_Eastern_B1_2017/TIFF/USGS_one_meter_x50y508_ME_Eastern_B1_2017.tif
```

Nineteen Maine LiDAR projects are staged on the bucket. The northern terminus is covered.

**It does not change the recommendation.** The other reasons stand and are the stronger
ones: roughly 1 TB for this corridor, an irregular project layout that genuinely does need
a catalog to navigate (so it would *reintroduce* the TNM dependency this survey removed),
and — most importantly — §5 below demonstrates that resolution and accuracy are not the
same thing when the output is a *sum*. 1 m DEM exists to measure boulders and building
footprints.

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

## 6. The terrarium tiles — closest match, and a finding still open

`elevation-tiles-prod` terrarium tiles came closest to 3DEP (−0.9% to +4.3%), which is
unsurprising: in CONUS that mosaic is largely derived from NED, so it is mostly 3DEP with
a resampling step in front of it.

It is still not the right source for the profile. `Last-Modified` on a z13 tile over the
AT read **12 November 2017**. It is a nine-year-old snapshot of mixed global provenance,
and taking a derived, undated re-tiling of 3DEP in preference to 3DEP itself would be
choosing the copy over the original.

**The incidental finding is worth more than the comparison, and it is still true today.**
`export_dem.py`'s `DEM_TILE_URL` is still that same bucket (checked in the source tonight,
2026-09-17) — so the app currently ships two different elevation truths: the profile and
its gain figures from current 3DEP (since §9), and the 3D terrain and hillshade the hiker
actually looks at from the same 2017 terrarium mosaic this section measured. They agree
closely enough that nothing looks wrong, and no hiker will ever notice. But now that the
profile reads a deterministic 3DEP grid, building the client's DEM tiles from that same
grid is straightforward, and the app would have one elevation truth instead of two. Still
unclaimed, still probably post-v1 work rather than a v1 blocker — recorded here because
this is where the evidence for it lives, not fixed tonight because it touches
`export_dem.py`'s raster/WebP pipeline and the client's terrain source, a larger and
differently-risked change than this survey's scope.

---

## 7. Point-query services — right answer, wrong shape

Both USGS point services worked, needed no key, and needed no discovery:

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

## 9. What this changed in the code — shipped, five weeks later

Left as reconnaissance in the original survey, with the work assigned to its own issue.
**[#550 — Read 3DEP from its static 1-degree grid, and stop asking TNM Access which tiles
exist](https://github.com/OurHike/OurHike/issues/550) did the work and closed
2026-08-13**, merged as [PR #613 — Compute the 3DEP tile list instead of asking which
tiles exist](https://github.com/OurHike/OurHike/pull/613). Checked against the tree
tonight (2026-09-17), every item in that issue's outline landed:

- `compute_grid_cells()`'s TNM half, `list_products_for_cell()`, `cell_products()`,
  `cached_cell_items()`, `cell_cache_path()`, the `tnm_cells` cache directory and
  `TNM_BACKOFF_SECONDS` are gone. The corridor bbox gives the cell list; the URL is a
  format string, exactly as §3 measured.
- `build_tile_index()` still applies the corridor-polygon filter — still worth not reading
  tiles the trail never crosses — and no longer carries `_edition_of()` or the footprint
  dedup.
- Tile `bounds` are derived from the cell name arithmetically, not from TNM's
  `boundingBox`.
- `write_gate_problems()` was kept, per the judgement call §10 flagged as open: a computed
  cell list cannot shrink because a server was slow, but it still catches a
  corridor-geometry regression, and the maintainer's call was that this was still worth
  guarding against.
- The `Restore the TNM catalogue cache` step is gone from the publish workflow, and with
  it the whole failure mode §1 documented — there is no longer a cache to lose on a failed
  run, because there is no longer a catalog call to cache.
- `export_elevation.py` did not change, as predicted — same COGs, same `/vsicurl/`, same
  `WarpedVRT`, same sampling.

One thing has grown past what this survey measured, and is **out of this document's
scope**: `fetch_elevation.py`'s own docstring now describes a `network_extent()` that
widened the tile set from the 9-cell New York City bounding box the code carried when this
survey was written to all of NYS Parks/DEC/NYNJTC/Mohonk Preserve's lines (#1019) — 31
cells touched instead of 7, by the script's own count. That is a real, larger elevation
footprint than the 56 corridor cells §3 verified, and the file says outright that how many
of the 31 the corridor already covers is unmeasured in its own environment. Whether the
static-grid recommendation still holds at that footprint is presumably yes (the grid is
uniform CONUS-wide, not corridor-shaped) but was not re-verified here — flagging rather
than re-measuring, because it is a different question from the one #548 asked.

---

## 10. Marked for maintainer review

| item | status | where |
|---|---|---|
| Adopt the static grid, or just fix the cache? | **Decided and shipped**: the static grid, via #550/PR #613. | §1, §9 |
| Keep `write_gate_problems()`? | **Decided and shipped**: kept. | §9 |
| One elevation truth for terrain and profile | **Still open.** `export_dem.py` still reads the 2017 terrarium mosaic for the client's terrain/hillshade while the profile reads current 3DEP (since #550). Real, small, and still probably post-v1 — nobody has opened the follow-up issue for it yet as of tonight. | §6 |
| The 1 m Katahdin note | **Still uncorrected.** `export_elevation.py` (checked tonight, line ~152) still reads "not least that it has no coverage at all at the northern terminus" — the claim §4 found out of date in August is still in the tree in September. The conclusion the comment supports is still right for the other reasons in §4, so nothing behaves wrong; the sentence itself is just false and nobody has touched it. A one-line fix, not made tonight because it is a comment edit riding on a survey PR rather than something this document's own scope covers. | §4 |
| Copernicus as a non-US fallback | Only matters if OurHike ever leaves 3DEP's footprint. Still not relevant. | §5 |
| The network extent's cell count (31 vs the 56 this survey measured) | **Not evaluated here** — a real change since this survey, worth its own look rather than a guess folded into this restoration. | §9 |

---

*Method note for whoever refreshes this next: every claim in §§0–8 is one `curl -I`
against `prd-tnm.s3.amazonaws.com` away from re-verification, and the source comparison is
one run of the sampling in §5 — real centerline, 25 m interval, `lib/elevation_gain.py`'s
own dead band, so the numbers are directly comparable to what `export_elevation.py`
reports. Re-run it before trusting these figures another year out; 3DEP re-flies on a
multi-year cycle, and the Georgia cells in particular were last revised in 2023, and
n46w069 (checked tonight) in May 2026 — so at least one corridor cell has already changed
under this survey once.*
