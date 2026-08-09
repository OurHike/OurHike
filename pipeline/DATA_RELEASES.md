# Versioned data releases — design & rollout plan

Companion to [README.md](README.md), [../TECHNICAL_ARCHITECTURE.md](../TECHNICAL_ARCHITECTURE.md) and [../TESTING.md](../TESTING.md). **Status: designed 2026-07-31, not yet built** — this document is the plan, written before the code per this project's usual convention (see [DBT.md](DBT.md), [../FEATURES.md](../FEATURES.md)).

Scope is **trail data only** — the artifacts `publish.py` ships to R2. User accounts, condition reports, closures and comments live in Postgres/Supabase behind the FastAPI backend and are untouched by any of this.

**One half of that sentence has a design against it now.** [../features/CONDITIONS_DELIVERY.md](../features/CONDITIONS_DELIVERY.md) (designed 2026-08-08, not yet built) publishes *verified* closures and reports as artifacts under `conditions/`, so the public read path stops going through the backend. Accounts, comments and everything unmoderated stay exactly where this sentence puts them. The release machinery below — versioning, retention, the `latest.json` manifest — is what that design reuses rather than rebuilds; what it adds is a second producer writing into the same layout, which is the part worth reading this document for before building it.

## Why: what breaks today

`publish.py` writes every artifact to a **flat key at the bucket root** — `background.pmtiles`, `trails.geojson`, `poi_shelter.geojson` — and the client builds exactly those URLs from a build-time `VITE_DATA_BASE_URL` (`client/src/lib/config.ts:23-25`). A publish is a `PutObject` overwrite of a live key. Four consequences, in rough order of how badly they hurt a hiker:

1. **A publish can corrupt a download already in progress.** `archiveDownload.ts` resumes a partial 314 MB / 1.18 GB archive with `Range` + `If-Range`. If R2's CORS policy fails to expose `etag`, there is no `If-Range` to send, R2 honours the range against the *new* object, and old bytes get spliced onto new ones. The client's size check provably cannot catch it — `totalBytes` is *defined* as `heldBytes + declared` (`archiveDownload.ts:47-54`), so both sides of the comparison are the same expression. The result is a PMTiles file that reports itself complete, renders wrong past the seam, and never falls back to the network (`pmtilesSource.ts:9-11,40-44`). Commit `e503bcb` hardened the client against this; the real fix is for the bytes behind a URL to never change.

   *Detected, not prevented ([#197](https://github.com/OurHike/OurHike/issues/197)).* The client now hashes every chunk as it streams and holds the completed archive to the SHA-256 this manifest already publishes for that key (`client/src/lib/sha256.ts`, `client/src/lib/dataManifest.ts`) — and drops a held partial whose published hash has moved since those bytes were held, which is the half that does not depend on `etag` surviving CORS. So a splice is caught before it is stored rather than rendered as a map, and nothing spliced is ever kept. The vector artifacts this manifest also names — `trails.geojson`, the POI files, `spurs.json`, `elevation_profile.json` — are held to their published hashes the same way (`client/src/lib/trailData.ts`); they are never resumed, so a splice cannot happen to them, but a damaged JSON file parses perfectly well and a POI in the wrong place is not something a parse can catch. What it does not do is save the hiker the download: they lose the transfer and start again. The real fix is still below — bytes behind a URL that never change.
2. **A hiker cannot pin, and cannot be told.** A completed archive is stored under `ourhike:corridor-archive` with no hash, no ETag and no version (`pmtilesSource.ts:16`), so a republish is invisible to a device that already downloaded — no staleness signal, no "update available", no way for the app to even know. `latest.json`'s `version` is read by nothing but `publish.py` itself.

   *The record now exists, the signal does not ([#197](https://github.com/OurHike/OurHike/issues/197)).* A verified archive keeps the SHA-256 it was checked against beside it (`client/src/lib/archiveDownload.ts`, `readArchiveVersion`), so which published build a phone holds is answerable at all — it was not before. Nothing reads it yet: comparing it against the manifest and telling the hiker their map is from an older release is still this consequence's own work. An archive stored with no published hash to check against deliberately claims nothing rather than inheriting the previous claim.
3. **Publishing is the same act as releasing.** There is no state in which new data exists but is not yet being served. Every quality gate has to run *before* the upload, on local disk, and therefore tests something other than what hikers actually receive.
4. **Nothing is incremental above the artifact level.** Every raster build re-fetches all 51 cells' quads from scratch.

   *Partly resolved.* §1 below is built: `check-upstream-freshness.yml` runs the check daily against a published `build_state.json` and holds no R2 credentials. The build itself (§2) is still neither scheduled nor incremental.

The goal of this plan, stated as one property: **a hiker who has downloaded map data never loses access to it, and never has it changed underneath them.** Everything below follows from that.

## The shape

Four separate things, deliberately not collapsed into one:

| | runs | can write to R2 | can change what hikers get |
|---|---|---|---|
| **Daily freshness check** | cron, daily | **no — holds no credentials** | no |
| **Weekly candidate build** | cron, weekly | yes, only under `releases/<new>/` | no |
| **Verification battery** | after each build | no | no |
| **Release** | a merged PR, then a tag | no | **yes — this is the only one** (see §4's amendment) |

The separation is the design. A scheduled job cannot change a hiker's data even if it wanted to, because the only thing that selects a dataset is a constant in the client source.

### R2 layout

```
releases/2026-08-07/
  trails.geojson  trails.fgb
  poi_{shelter,water,campsite,resupply,crossing}.{geojson,fgb}
  elevation_profile.json
  background.pmtiles  background_z11.pmtiles  background_z13.pmtiles
  manifest.json          # per-artifact sha256 + size_bytes + which release the bytes came from
  build_state.json       # every upstream freshness marker, as of this build
releases/index.json      # every release, newest first, each with status: candidate | verified | released
latest.json              # unchanged shape; gains a `release` field naming the released folder
background.pmtiles ...   # today's flat keys, FROZEN — see Migration
_internal/cells/2026-08-07/tile_NNN.tif + cells_state.json
```

Release ids are `YYYY-MM-DD`, with a `-2`, `-3` suffix for a same-day rebuild. Human-readable, lexically sortable, and it answers "how old is the map on my phone" without a lookup table.

The naming rules those segments follow — what a prefix may be, what an object may be called, and why a published key can never be renamed — are [R2_LAYOUT.md](R2_LAYOUT.md), enforced by `lib/r2_keys.py`. This document owns the tree above and the clocks below; that one owns the spelling.

Everything under `releases/<v>/` is **written once and never overwritten**. That single rule is what makes consequence 1 above structurally impossible rather than defended against.

`_internal/` is build state, not hiker-facing. On the current r2.dev public bucket it is nonetheless publicly readable; it is named to make that obvious rather than to hide it.

## 1. Daily freshness check — flags, never publishes

**Built.** `.github/workflows/check-upstream-freshness.yml`: `schedule` (daily) + `workflow_dispatch`, `permissions: {contents: read, issues: write}`, **no R2 secrets at all**.

Two things landed differently from the sketch below, both because the release layout in §2 does not exist yet:

- The state is published as a **flat `build_state.json` at the bucket root**, not under `releases/<v>/`, matching the flat keys everything else uses today. It moves under the release folder when §2 lands.
- It is a **sidecar in `publish.py`, not an artifact**: it uploads only when a version is actually written, and its own hash never causes a version. Both halves matter. Counted as an artifact it would bump the version whenever an upstream was edited without changing a single exported byte, breaking the "never a no-op bump" rule. Uploaded on a run that published nothing, it would describe upstreams *newer* than the bytes live in the bucket — the check would compare current markers against current markers, report FRESH, and the map would go on serving the old data with nothing flagging it. That is the exact false-fresh this check exists to prevent, so the state is only ever written together with the bytes it describes.

One more distinction the sketch did not have: a state captured by a build that ran only part of the pipeline **omits** the sources it never touched, rather than publishing them as empty. The vector publish does not fetch topo quads or DEM tiles, and an empty entry would read as "we looked and found nothing" — a daily STALE for the raster half, forever. Omitted, it reads as UNKNOWN, which is what it is.

`check_freshness.py` already normalises all four upstreams' freshness markers (ArcGIS `dataLastEditDate`, opentrail ETag, S3 `Last-Modified` on a date-seeded 25-quad sample, the 3DEP edition set) and already keeps STALE and UNKNOWN apart because they call for different responses. What it cannot do today is run in CI: its "recorded" side reads `data/raw/manifest.json` and friends, which no fresh checkout has, so on a hosted runner it would report everything STALE.

**The fix is what makes the daily job need zero credentials.** Extract the recorded-marker side into `lib/freshness_state.py`:

- `capture_state()` → the full marker dict, built from `data/raw/*` after a fetch. Called at build time, written into each release's `build_state.json`.
- `load_state(path_or_url)` → the same dict, read from a local file **or fetched over plain HTTPS**.
- `compare_state(recorded, upstream)` → per-source `Freshness` verdicts, reusing the existing `compare_marker()` / `summarise()`.

`check_freshness.py` gains `--state <path|url>` (defaulting to today's local behaviour, so its 28 existing tests keep passing unchanged) and `--json <out>`. The daily job then reads `${DATA_BASE_URL}/releases/<currently-released>/build_state.json` over the public URL — the same path a hiker's phone uses — and diffs it against live upstreams. No bucket credentials exist in that job, so it is *structurally* incapable of replacing anyone's data.

**How it flags.** Three surfaces, none of which is a publish:

- The workflow job summary, always.
- The JSON verdict as a workflow artifact, for the weekly build to read if it wants a head start.
- **One** GitHub Issue, titled "Upstream data freshness", labelled `data-freshness`, **updated in place** — never a second issue, never a comment per day. Body lists each STALE source and the date it first went stale, and each UNKNOWN source separately. When everything returns to FRESH the issue is closed.

One deliberate inversion: `summarise()` exits 1 on stale-or-unknown, which is right for a pre-build gate and wrong here. A red X every single day for a legitimately-changed upstream trains people to ignore the signal. **The daily workflow treats a non-zero freshness verdict as data to record, and fails only if the check itself crashed.** Staleness is the normal state between weekly builds; it is news, not an error.

## 2. Weekly candidate build — new folder, only what's new

New `.github/workflows/build-data-release.yml`: `schedule` (weekly, Mondays) + `workflow_dispatch` with a `force_full_rebuild` boolean. `concurrency: data-release`, sharing a group with the existing publish workflows so two builds can never interleave.

| job | what it does |
|---|---|
| `plan` | Resolve the current release from `releases/index.json`. Fetch its `manifest.json`, `build_state.json`, and `_internal/cells/<cur>/cells_state.json`. Run `fetch_all.py` + `fetch_opentrail.py` (cheap, and needed for the corridor anyway), `fetch_topo_quads.py --metadata-only`, `build_cells_manifest.py`. Compare against the previous state and emit: the new release id, which vector artifacts need rebuilding, which cell indices need re-mosaicking, and whether **anything** does. |
| `mosaic` | Matrix over **only the changed cells**. Guarded by `if: needs.plan.outputs.changed_cells != '[]'`, since Actions errors on an empty matrix. Otherwise identical to today's job. |
| `assemble` | Download this run's changed tiles; copy the rest forward from `_internal/cells/<prev>/`. Keep the existing "Confirm every cell arrived" check — all 51 must be present regardless of how each one got there. Build the three PMTiles tiers. Skipped entirely when no cell changed. |
| `stage` | Upload changed artifacts to `releases/<new>/`; **server-side `copy_object`** for every artifact whose sha256 matches the previous release. Write `manifest.json` (recording, per artifact, which release the bytes originated in) and `build_state.json`. Append to `releases/index.json` with `status: "candidate"`. Does not touch `latest.json`. |
| `verify` | The battery in §3, against the staged folder over its public URL. On success flips the index entry to `"verified"`. |
| `propose` | Open the draft PR in §4. Only runs if `verify` passed. |

**If nothing changed, no release is written and no PR is opened** — the same rule `publish.py:170-176` already applies ("never a no-op bump"), lifted to the release level.

### Why every release folder is complete

Copy-forward is a *server-side copy*, not a pointer. `releases/2026-08-07/` contains every artifact even if only one changed that week. A hiker's client resolves exactly one folder and must find everything there; a folder that only holds the week's deltas would make correctness depend on chasing a chain backwards, and one gap in that chain is a 404 on a mountain. Storage is the price, and it is the right thing to pay.

### Incremental raster reuse

**Decided 2026-07-31: per-cell reuse, with full per-release intermediates stored in R2.**

`_internal/cells/<release>/cells_state.json` records, per cell: its quad set with each quad's `last_modified`, the sha256 of its output tile, and a hash of the corridor geometry it was clipped against.

A cell is re-mosaicked iff its quad set changed, **or** the corridor changed, **or** its tile is missing from the previous release. Otherwise the tile is copied forward. In a typical week — USGS republishes topo quads in infrequent batches and 3DEP is on multi-year cycles — that is zero cells, and the raster leg drops from hours to a few minutes of copies.

Two honest caveats:

- **A centerline edit invalidates everything.** `export_pmtiles.py` clips against a corridor built fresh from `centerline.geojson`, so any ATC centerline edit changes every tile's clip mask and forces a full 51-cell rebuild. ATC edits the centerline several times a year, so those weeks cost full price. Phase 5 narrows this by hashing each cell's *own* slice of the corridor (`ST_Intersection(corridor, cell_bbox)`) instead of the whole polygon — an edit in Georgia then rebuilds Georgia's cells, not Maine's. Phase 1 uses the whole-corridor hash: conservative, obviously correct, and never wrong in the dangerous direction.
- **This reuses output tiles, not input quads.** `fetch_and_mosaic_cell.py` still starts each cell from an empty scratch dir with no download resume, exactly as today. A cell that does rebuild costs what it costs now.

**Intermediates are stored per release, on a shorter clock than the releases themselves — 30 days.** They are build inputs, never hiker-facing: their only consumer is the *next* build, which diffs against the most recent release. Keeping a few generations means a recent release can be rebuilt or a bad cell re-cut without re-fetching 14 GB of quads; keeping a year of them would be ~190 GB of data nothing will ever read again. 30 days holds roughly four weekly generations, which is enough for that and no more.

## 3. The verification battery

New `pipeline/verify_release.py`, run against a staged release **over its public HTTPS URL**, with no credentials. That is the point: it tests the artifact a hiker's phone will actually fetch, through the same CDN, CORS policy and range machinery, rather than a file on the runner's disk.

This inverts today's `check_output_quality.py`-then-`publish.py` order, and that is safe now when it was not before: previously publishing *was* releasing, so verification had to precede the upload. Now a staged candidate is inert — nothing points at it until a merged PR does. `check_output_quality.py` still runs before staging as a cheap local gate, and gets added to the raster workflow, where it is currently missing entirely.

**A. Presence and contract**
1. `manifest.json` parses and has the expected shape.
2. Every key the *client* will request exists — `TRAILS_KEY`, `poiKey()` for each of `POI_TYPES`, and all three `BACKGROUND_ARCHIVES` — read out of `client/src/lib/config.ts` rather than duplicated. This extends `test_publish.py::test_background_archives_cover_every_tier_the_client_offers` from "the mapping covers every tier" to "the bucket does". A tier the app offered and the bucket lacked has already happened once (`publish.py:65-67`).
3. No artifact present in the previous release is missing from this one.

**B. Byte-level integrity**
4. `HEAD` each artifact: 200, `Content-Length` == manifest `size_bytes`, `Accept-Ranges: bytes`, `ETag` present.
5. Stream-download and SHA-256 each artifact; must match the manifest. ~1.6 GB per run, streamed and never buffered. It is the only check that proves the bytes a hiker downloads are the bytes that were built and verified.
6. Range requests — prefix, mid-file, suffix — each 206, correct length, bytes identical to the corresponding slice of the full download.
7. **`If-Range` is honoured**: correct ETag → 206, stale ETag → 200. This is precisely the mechanism `archiveDownload.ts:93-118` relies on to refuse a splice, and the client's own size check cannot substitute for it. It must be tested, not assumed.
8. **CORS**: `Access-Control-Expose-Headers` includes `etag`, `content-length`, `content-range`, `accept-ranges` — the exact list in `LAUNCH_CHECKLIST.md:52-60`. A CORS regression silently disarms check 7 on real devices while CI, which is not a browser, would never notice.

**C. PMTiles structure**
9. Each tier opens; header min/max zoom matches the tier's declared zooms (11 / 12 / 13).
10. Tile count matches what the build reported.
11. **Coverage**: every corridor cell has a tile at *every* zoom in the tier's range — the same gate `export_pmtiles.py:218-235` runs at build time, re-run against the published archive by range-reading it, which additionally proves the archive is readable the way MapLibre reads it.
12. Spot-decode tiles spread across zoom and geography; each must be a valid WebP of the expected dimensions.

**D. Vector content**
13. Each `poi_*.geojson` and `trails.geojson` parses as a FeatureCollection.
14. Feature counts clear their per-type minimums via `lib/completeness.count_problems`, with the same `minimums={"crossing": 0}` exception `export_poi.py` already makes.
15. No null or empty geometries; every geometry inside the corridor bbox.
16. Every trail feature carries a non-null `blaze_color` (the [TRAIL_BLAZE_COLORS.md](../features/TRAIL_BLAZE_COLORS.md) contract).

**E. Release-over-release regression**
17. Any artifact whose size or feature count drops more than `check_output_quality.DROP_THRESHOLD` (10%) fails, unless `build_state.json` shows the responsible upstream actually changed. This is `flag_drops()` retargeted from run-vs-baseline to release-vs-release — strictly better, because `data/quality_baseline.json` is gitignored and absent on a hosted runner (the vector workflow's own comment admits the check reports SKIPPED there), while the previous release's manifest is always available.
18. **Advertised-size drift**: each tier within 2% of `DOWNLOAD_DETAIL_LEVELS[].sizeBytes` in `client/src/lib/downloadDetail.ts`. That figure is weighed against remaining phone storage at a trailhead. `README.md:179` already says a tier drifting far from its advertised size "is a real problem, not a rounding detail" — this is the first thing that enforces it.

**F. The releases hikers are already on still work**
19. Re-run A and B against the **currently released** folder, not just the candidate. This is what actually enforces the headline property: it catches an accidental deletion, a lifecycle rule, or a permissions change on a folder people are pinned to today. Failing it blocks the PR even when the new candidate is flawless.

Unit tests for all of the above go in `pipeline/tests/test_verify_release.py`, synthetic fixtures + `requests-mock`/`moto`, per [TESTING.md](../TESTING.md). The battery itself runs as a workflow step rather than a pytest test, consistent with TESTING.md's standing position that real-data end-to-end verification is a documented procedure, not part of the suite.

## 3a. The standing monitor

**Built** — `pipeline/check_deployment.py` and `.github/workflows/check-deployment.yml`, daily. This is tier 1 of [#431](https://github.com/OurHike/OurHike/issues/431).

**It is not the battery above, and the difference is the whole reason it exists.** §3 is a *release-time* gate: it verifies a staged candidate before promotion. What happened in [#427](https://github.com/OurHike/OurHike/issues/427) was a **good release quietly stopping being reachable** — the R2 bucket's CORS allow-list lost `https://ourhike.github.io`, days after a release that was and stayed correct, so the deployed app drew a topo sheet with no Appalachian Trail on it for eight days. A release gate catches bad releases. Both are needed and they are different checks.

**Why every check we already had was green.** Check 8 above names this in advance: *"A CORS regression silently disarms check 7 on real devices while CI, which is not a browser, would never notice."* That is not a metaphor — it is what happened. `check_freshness.py`, `r2-credentials-check.yml`, and every `curl` anyone typed send **no `Origin` header**, and the bucket answered all of them perfectly throughout: a ranged `GET` returned `206` with `Content-Range`, `ETag` and `Accept-Ranges` intact. One header decides whether a browser may read those bytes, and nothing sent it.

So the monitor sends one, for every origin declared in [`.github/expected-origins.yml`](../.github/expected-origins.yml):

1. **Origin** — `Access-Control-Allow-Origin` comes back matching. A wildcard pattern is probed with a *concrete* hostname it should match, since `*` is not something a browser sends and a rule covering no real hostname covers nothing.
2. **Preflight** — an `OPTIONS` asking for the request headers the client actually sends is answered with all of them in `Access-Control-Allow-Headers`.
3. **Exposed headers** — `Access-Control-Expose-Headers` covers `etag`, `content-length`, `content-range`, `accept-ranges`. Present and *readable* are different things, and only a browser can tell.
4. **Artifacts** — every key `latest.json` names answers `HEAD` 200, with a non-zero `Content-Length` and `Accept-Ranges: bytes`.
5. **Range** — a one-byte range comes back `206` with a `Content-Range`.

**The preflight assertion found a live defect the day it was written**, which is the clearest possible argument for it. `range` is CORS-safelisted for simple byte ranges, so a *first* download needs no preflight and works against a wrong policy. **`if-range` is not safelisted**, and `client/src/lib/archiveDownload.ts` sends it on every *resume* — it is what makes the server itself arbitrate a stale partial rather than splicing old bytes onto new (§1). The policy documented in `LAUNCH_CHECKLIST.md` allowed `if-match`, which nothing in this repository has ever sent, and **not** `if-range`.

**Measured against the live bucket, 2026-08-09**, rather than argued from the spec:

| `Access-Control-Request-Headers` | answer |
|---|---|
| `if-match` | `204`, `Access-Control-Allow-Headers: if-match` |
| `range` | `204`, `Access-Control-Allow-Headers: range` |
| **`if-range`** | **`403 Forbidden`, no CORS headers at all** |

So resuming an interrupted 1.18 GB download is refused by the browser **today**, invisibly, and only ever on a phone in the place where resuming matters most. The same run confirmed the policy is genuinely enforced on the `r2.dev` subdomain rather than permissive — an undeclared origin gets no `Access-Control-Allow-Origin` at all — so the origin assertion discriminates rather than always passing.

**That run also corrected the check itself**, which is worth recording because the first version was confidently wrong in a way only real data exposed. R2 answers a preflight naming a disallowed header with a bare `403` and *no* `Access-Control-Allow-Headers`, not a `200` listing the subset it permits. Reading the empty allow-list off that `403` made every requested header look refused, so the check reported `range` as disallowed when `range` is allowed and only `if-range` is not. A refused preflight is now re-asked one header at a time, so the alarm names the header to add instead of the whole list.

**Three constraints, each of which changes what the check may do:**

- **It must not download the artifacts.** `HEAD` and one-byte ranges answer every question above; pulling the real files would be ~1.6 GB of egress a day against a rate-limited `r2.dev` subdomain to learn what one byte already said. Proving the *bytes* is check 5's job, at release time, once.
- **It must not fail the run.** GitHub emails on a scheduled workflow's failure every run, so a week-long outage would send seven identical emails and the eighth would be filtered. The tracking issue is the signal: opening it notifies, updating its body does not, the all-clear comment notifies once. Same discipline `check-upstream-freshness.yml` already keeps, for the same reason.
- **A request that never completed is not a refusal.** "Could not ask" says nothing about the CORS policy, and a flaky third party must not be able to declare an outage. Those are reported and never open the issue.

**What it cannot check, stated rather than implied.** `latest.json` publishes a sha256 per artifact and **no size**, so "exists at its published size" is not a question this can ask — it asserts each artifact is present, non-empty and rangeable, which is what makes it fetchable and resumable, not that it is the length anyone intended. A truncated-but-served artifact is caught by the client's own per-chunk hashing and by check 5, not here.

**One declaration, several readers.** The origins file is the single home for the list; the CORS policy pasted into Cloudflare is *generated* from it (`check_deployment.py --print-cors-policy`) rather than kept as a second copy, because the second copy is precisely what drifted. Supabase's redirect allow-list wants the same list in its own spelling and is the next reader — #431's tier 3. The browser-level check that the app *draws a trail* is tier 2, still unbuilt.

## 3b. The published-data smoke test

**Built** — `pipeline/smoke_published.py` and `.github/workflows/smoke-published.yml`, weekly. This closes [#94](https://github.com/OurHike/OurHike/issues/94).

**Three checks now overlap in name and not in question**, which is worth stating once rather than rediscovering:

| | when | cost | asks |
|---|---|---|---|
| `check_deployment.py` (§3a) | daily | no downloads | can a browser **reach** it |
| `smoke_published.py` (here) | weekly | ~18 MB | is what is there **correct** |
| `verify_release.py` (§3) | per release | ~1.6 GB | is a **candidate** fit to promote |

The first two watch a *published* release quietly going wrong; the third gates a *new* one. A hash cannot be checked without reading bytes, which is why this one downloads and §3a's never does.

**Over the manifest, never a hardcoded list.** #94's own follow-up is emphatic, and it is the easiest thing to get wrong: `publish.py` has grown `quad_sheet_z14.pmtiles`, a vector basemap package and a DEM package since the issue was filed. A test naming `background.pmtiles` would pass while the packages a hiker navigates by went unchecked.

Per artifact: headers (present, rangeable, **no `Content-Encoding`**), a **mid-file** range, the SHA-256 against `latest.json`, and for `.pmtiles` an actual read.

**The PMTiles read is the part #94 was really asking for.** `traverse` — the library's own directory walk, the same code `extract_package.py` runs against local files — is pointed at an HTTP byte source, so the archive is opened the way MapLibre opens it: header, root directory, then a real tile, each a `Range` against a file far too large to download. Measured against the live bucket 2026-08-09: **3–4 requests and under 103 KB per archive, including the 1.18 GB tier.** The tile's first bytes are then held to what the header promised — WebP is `RIFF`, a gzipped vector tile is `\x1f\x8b` — because "bytes arrived" and "a tile arrived" are different claims and only the second one is a map.

**Three deliberate choices worth not re-litigating:**

- **A mid-file range, not a prefix one.** A prefix range is the case a server that half-understands ranges is most likely to get right, so asking for one proves the least — and the client resumes from wherever it got to, which is by definition not the start.
- **`Content-Encoding` is a failure, not a note.** If the bucket transparently re-encodes, a `Range` applies to the *encoded* bytes while `archiveDownload.ts` counts decoded ones, so a resume reads from the wrong offset and surfaces as a hash mismatch naming nothing about encoding.
- **Skipped is reported as skipped.** An artifact over the hash budget is not one whose hash was verified. Rolling that into a pass is how a green run comes to mean less than a reader assumes.

**A missing `Content-Type` is noted and not failed.** R2 currently sends none at all for these keys; `fetch().json()` ignores it and MapLibre reads bytes, so failing on it would be inventing a rule the app does not have.

**First real run, 2026-08-09: 66 checks, 0 failed, 48 ok, 18 skipped** — every artifact present, every hash under budget matching, all six archives opening over ranges and yielding a tile.

## 4. Release only by a code change

New `client/src/lib/dataRelease.ts`:

```ts
/** Which published dataset this build reads. Bumping this IS the release. */
export const DATA_RELEASE = '2026-08-07'
```

and `config.ts:dataUrl()` becomes `` `${DATA_BASE_URL}/releases/${DATA_RELEASE}/${key}` ``.

**Assumption (unanswered question): a committed constant, not a repo variable.** A variable would let the dataset every hiker receives change with no commit, no review and no history. A constant puts the release in `git log`, makes it revertable with `git revert`, and puts it structurally out of reach of every pipeline workflow — they all run with `contents: read`.

The weekly build's last job opens a **draft PR** on `data-release/<version>` changing that one line, with the full verification report as the body. A human reviews and merges. `pages.yml` redeploys on push to main. That merge is the release, and it is the only thing that is.

**Amended 2026-08-07 by [../RELEASING.md](../RELEASING.md).** That last sentence was written when `main` deployed straight to production, which was true at the time. Under the code release process it no longer is: the merge deploys to **UA**, and a tagged release is what puts the new dataset in front of hikers. Everything else above stands unchanged — the constant is still what selects a dataset, it is still committed rather than configured, and a scheduled job still cannot move it. What changes is that promoting it now gets a real client fetching it through a real browser first, which is the one thing this document's own verification battery cannot do from a runner. RELEASING.md §10 is the seam.

`pages.yml` gains one guard next to its existing grep proving `DATA_BASE_URL` was inlined: assert `releases/<DATA_RELEASE>/manifest.json` returns 200, so a build can never deploy pinned to a folder that is not there.

## Retention

**Decided 2026-07-31: 90 days, with the clock starting when a release is superseded, and a floor of the 3 most recent released folders.**

The naive reading of "expire after 90 days" — 90 days from the build date, applied blindly by a bucket lifecycle rule — would break the property this whole plan exists to deliver, so it is worth being precise about why and what replaces it.

### The failure it would cause

`DATA_RELEASE` is compiled into the client. The web build redeploys on every merge to main, so it is never far behind; **installed app-store builds are**. A Capacitor build shipped in March still asks for March's release folder, and neither the App Store nor Play can force that build forward. If the folder expired at day 90, that hiker gets a 404 — not a stale map, no map — and the client has no fallback path (`trailData.ts:81-87` throws, `App.tsx:217-226` stops before the archive).

Already-downloaded data is unaffected either way: a completed archive lives in IndexedDB on the phone and no bucket policy touches it. The exposure is exactly the hiker who has the app but has not downloaded yet, or who deletes and re-downloads at a resupply stop — which is a normal thing to do when storage runs short, and the worst possible moment to discover the data is gone.

### The rule that keeps 90 days

Retention is enforced by a **scheduled prune workflow, not an R2 lifecycle rule.** Lifecycle rules can only express "older than N days under this prefix"; they cannot express "unless something still points at it", and that exemption is the entire safety property. Three tiers:

| what | kept | why |
|---|---|---|
| **Released folders** | 90 days **after being superseded**, floor of the 3 most recent | The clock starts when a newer release takes over, so a release that stays current for months never ages out from under the build pinned to it |
| **Candidates never released** | 14 days | Inert by construction — nothing ever pointed at them |
| **`_internal/` intermediates** | 30 days | Build inputs only; see above |

Plus two hard exemptions the prune job refuses to cross, regardless of age:

1. **The currently-released folder** — the one `latest.json` names — is never eligible. Ever.
2. **Any release listed in `releases/pinned.json`** — a small committed-and-published list of releases that shipped app-store builds still point at. The release PR adds an entry; an entry is removed by hand when that app build is genuinely out of support. This is the escape hatch that makes a 90-day policy safe for a 7-month thru-hike.

The prune job runs on a schedule, computes the eligible set, and **prints what it would delete and why on every run**. Deletion happens only for objects that clear all three tiers plus both exemptions. A dry-run mode is the default for `workflow_dispatch`; the scheduled invocation passes the flag explicitly.

### What this costs

With a weekly build and a roughly monthly release cadence, 90 days of superseded-release retention holds **3–4 released folders plus whichever candidates are inside their 14-day window** — comfortably meeting the "always at least 3 versions" bar, and more when ad-hoc releases land between the regular ones. Steady state is roughly 8–12 GB under `releases/` and ~15 GB under `_internal/`, so on the order of $0.40/month at R2's $0.015/GB-month, flat rather than growing.

Note the cadence split this assumes, since the two are not the same thing: the **build** is weekly, the **release** is whatever a human merges. Most weekly candidates will never become releases, which is why they get their own much shorter clock.

## Never losing map data

The property, and the four things that deliver it:

1. **Immutable folders.** An object is written once under a key containing its release id. The bytes behind a URL a partial download recorded cannot change, so the splice failure mode disappears at the source rather than being defended against in the client.
2. **Nothing is deleted while anything still points at it.** Pruning is age-based but exemption-gated: the current release and every release in `releases/pinned.json` are untouchable regardless of age, and the 90-day clock only starts once a release has been superseded.
3. **A pinned folder passed verification before the client pinning it existed**, and check F re-proves it every week.
4. **A client is never forced forward.** This one needs client work and is not free: today a completed archive carries no identity at all, so the app cannot tell which release it holds. Phase 6 makes `ourhike:corridor-archive` release-scoped, has `deleteArchive()` remove a superseded archive only *after* the replacement completes, and surfaces "update available" instead of silently going stale — the client half of `TECHNICAL_ARCHITECTURE.md:94-97`, which has never been built.

## Migration

Today's flat root keys are what every already-deployed client build requests, and they must stay — frozen, never overwritten, never deleted. The first weekly run seeds `releases/<date>/` from them by server-side copy (their hashes are already known from `latest.json`), so release 1 is byte-identical to what is live and the migration itself changes nothing for anyone.

`latest.json` keeps its exact current shape and meaning, so `publish.py`'s diff logic and anything else reading it keeps working. It gains one field naming the currently-released folder.

## Rollout

Ordered so the safety property lands first and nothing is scheduled until the thing it triggers is trustworthy.

- **Phase 1 — versioned layout and the release gate.** `publish.py` grows a release mode; seed release 1 from the live flat keys; add `dataRelease.ts` and the `pages.yml` guard. Dispatch-only, nothing scheduled. Delivers immutability and PR-gated release on its own.
- **Phase 2 — `verify_release.py` and the battery**, plus `check_output_quality.py` added to the raster workflow. Run manually against release 1 to establish a baseline.
- **Phase 3 — the weekly build**, with artifact-level copy-forward, ending in the draft PR. Gated on Phase 2 passing.
- **Phase 4 — the daily freshness check**: `lib/freshness_state.py`, `check_freshness.py --state/--json`, and the issue-updating workflow.
- **Phase 5 — per-cell raster reuse**, including the per-cell corridor-slice hash that stops a Georgia centerline edit from rebuilding Maine.
- **Phase 6 — client-side release awareness**: release-scoped storage keys, no eviction before a replacement completes, "update available".
- **Phase 7 — the prune workflow.** Deliberately last. Nothing needs deleting until several months of releases exist, and a pruning job written before `releases/pinned.json` has real entries in it is a pruning job with an untested exemption path. Until it ships, retention is simply "keep everything", which is never the unsafe direction.

## Open questions

One decision remains unanswered; the plan proceeds on the recommendation and it is reversible before the phase that depends on it.

- **Release pin** — a committed constant (assumed) vs. a repo variable. Affects Phase 1, and it is the one that is awkward to revisit afterwards, since it determines whether the released dataset lives in the code's own history.

Settled 2026-07-31, previously open:

- **Incremental depth** — per-cell reuse with full per-release intermediates in R2.
- **Retention** — 90 days from supersession, floor of 3 released folders, with the current release and `releases/pinned.json` exempt. See [Retention](#retention).

Also still open, and not blocking: whether `elevation_profile.json` belongs in a release at all while no client code reads it (`publish-vector-data.yml:31`), and whether the `.fgb` variants — published, never fetched — should keep being shipped.
