# Per-source clocks, a private raw store, and deltas at each stage's own unit — design

Companion to [DATA_RELEASES.md](DATA_RELEASES.md), [DBT.md](DBT.md) and
[R2_LAYOUT.md](R2_LAYOUT.md). **Status: designed 2026-09-09, revised 2026-09-24 to add a
step cache between the raw store and the public bucket and to settle the storage format
(#1653). Nothing is built beyond what
[#1311 — The vector build went from 20 to 108 minutes in twelve days: a corridor union
over 466k lines paid twice, every external layer re-fetched every run, and a publish that
pays a round-trip per object](https://github.com/OurHike/OurHike/issues/1311) landed.**
Written before the code, per this project's usual convention — the same one DBT.md and
DATA_RELEASES.md follow, and for the same reason: the decisions below are cheaper to
disagree with here than in a workflow file.

The question this answers is the maintainer's, asked 2026-09-08:

> What if we did a true ELT approach, where the pipelines run at specific intervals for
> each source, then do a delta table, where only new records are processed? Could this
> be possible?

**Yes — and most of it already exists**, which is the whole reason to write it down
rather than build from the intuition. ("Most" is a judgement about the four bullets
below, not a count of anything; #1312 puts it at about two thirds.) What follows is what
is already here, the three clarifications that reshape the rest, and the parts that are
genuinely unbuilt.

**A second question followed on 2026-09-24**: should processed data live in R2 too, and
as one DuckDB file or as Iceberg? The answer is the section "Three tiers, and a step cache
between them", which adds a second private bucket for the output of expensive steps, and
compares the four storage formats with what was measured that day.

This is the home for **[#1312 — Run each source on its own clock, keep raw bytes in a
private store, and rebuild only the unit that moved — the ELT and delta design, written
down](https://github.com/OurHike/OurHike/issues/1312)**. It deliberately does **not**
design the weekly candidate build: that is DATA_RELEASES.md §2, still unbuilt, and it
belongs to that document under the one-home rule. It also does not re-argue the fetch
framework question — **[#1294 — Evaluated and declined: dlt for the fetch layer, and a
weekly cadence for non-alert data](https://github.com/OurHike/OurHike/issues/1294)** is
the evaluation this design rests on.

## What already exists

Stated first, because the interesting design work is all in the gap between this list
and the question.

- **Extract is already change-aware, per source, with whatever that upstream honours.**
  ArcGIS `editingInfo.dataLastEditDate` (`fetch_all.py`, `fetch_external_layers.py`), a
  real HTTP `If-None-Match` → 304 (`fetch_opentrail.py`), S3 `Last-Modified` per topo
  quad and per elevation tile (`fetch_topo_quads.py`, `fetch_elevation.py`), a
  filename-is-the-version check (`fetch_drought.py`), conditional headers plus a body
  sha256 fallback for WordPress installs that re-serve identical bytes without a 304
  (`fetch_club_pdfs.py`), a per-POI outcome cache for both photo fetchers
  (`poi_images.json`, `poi_images_atc.json`), and — since #1311 — a `max(UPDATED)`
  statistics query for NYS DEC's on-prem server and a service-metadata ETag for the
  Forest Service's, through `lib/arcgis.get_layer_max_field` /
  `lib/arcgis.get_service_etag`. #1294 tabulates the first six with file and line.
- **Load and Transform exist.** `load_raw.py` plus `pipeline/dbt/`: 28 raw tables, 27
  staging models, `dim_pois`, 115 data tests, a required CI check (DBT.md, all four
  phases built, the last two 2026-08-27).
- **Publish already diffs per artifact** and never bumps a version for nothing
  (`publish.py`, the "never a no-op bump" rule DATA_RELEASES.md §2 lifts to the release
  level).
- **A row-level diff already exists as a pure function.** `lib/data_change.classify()`
  reads two GeoJSON artifacts into `{severity, added, removed, moved, edited}` and
  grades `ROUTINE` against `CONSEQUENTIAL`, built for
  **[#919 — A published data fix reaches no phone that already has the app, because the
  download asks whether there is trail data and never which](https://github.com/OurHike/OurHike/issues/919)**.

What does not exist: **a job that runs the fetchers with the previous run's outputs
present**, a durable home for those outputs that is not an Actions cache, and any reuse
below the artifact level except the one #1311 built.

## Three clarifications

These are the spine of the design, and each one moves the proposal somewhere it pays.

### 1. "Per-source intervals" is a scheduling change, not a fetch change

Every mechanism the proposal needs is in the fetchers already. In steady state a full
fetch is a handful of metadata requests and no transfer — `fetch_all.py:25` says "most
runs do ~9 small metadata checks and no actual data transfer", and since #1311 the
external layers' skip can fire too. Neither figure is a measurement of a *warm* CI run,
because there has never been one: read it as the shape of the steady state rather than as
a number anybody has seen on a runner.

What defeats it is that **a GitHub runner is empty every time**. The skip compares
against a manifest in gitignored `pipeline/data/`, and the only thing carrying that
between runs is an Actions cache the workflow itself warns not to count on: GitHub
evicts an entry 7 days unread, against a release cadence of about a month
(`publish-vector-data.yml`'s "Restore derived water data" comment). **That is not a
theoretical risk and it has already cost published data**: **[#812 — 2,699 published
water points and crossings exist only in an Actions cache, and committing the ledger they
produced arms a trap](https://github.com/OurHike/OurHike/issues/812)** found the derived
water files living nowhere else, so a broken cache chain would have taken 2,699 water
points and crossings off the map with nothing announcing it — one of the four ways this
app can hurt somebody, arriving through a storage decision. Its fix gave *those three
files* a home as published sidecars; the raw layers still have none. #1311 measured
the consequence on run #88 of `publish-vector-data.yml`, 2026-09-08: all 18 external
layers re-fetched on every run — about 195,000 features over ~200 page requests, 9m43s
to 12m51s, byte-identical output run to run, and not one layer printing "up to date,
skipping."

So the missing piece is **a job that runs the cheap fetchers on a clock, with the
previous outputs present, and puts what it produced somewhere durable.** That is
`extract-sources.yml` below.

**One irony worth recording, because it inverts the intuition the question came from.**
`publish-vector-data.yml` carries `workflow_dispatch:` and nothing else — verified
against its trigger block, 2026-09-09 — so the POI, trail and vector data is fetched
when a human presses a button. #1294 measured the same thing across the directory on
2026-09-08 and drew the conclusion this document inherits: **"move the non-alert data to
weekly" would be an *increase* in cadence, not a reduction.** Only
`publish-conditions.yml` publishes on a cron, and its hourly bake is roughly 15 HTTP
requests an hour against upstreams whose politeness budgets were computed before the
question was asked.

That does not make the proposal wrong. It relocates it: the win is not fetching *less
often*, it is **fetching from a warm start**, so that the run a human dispatches begins
with yesterday's bytes on disk and asks a dozen metadata questions instead of pulling
195,000 features it already has.

### 2. "Delta table" is the right idea at the wrong grain

A delta table over the tabular data would save nothing worth the machinery. The warehouse
is thousands of rows — `dim_pois` was 4,433 on the 2026-08-18 real-data load (DBT.md
Phase B) — rebuilt whole as 145 `dbt build` nodes on every CI run. **Nobody has timed
`dbt build` here**, so the argument is the scale rather than a stopwatch: thousands of
rows of attributes, against the 41 of run #88's 108 minutes that one corridor union cost
(#1311, measured 2026-09-08). An incremental materialisation on that would buy whatever
that unmeasured number is, and cost a merge key, a late-arriving-row question and a
full-refresh escape hatch. What would settle it is one timed `dbt build` on a real load —
worth having before Phase 4, not before Phase 2.

**The cost is somewhere else, and it is not row-shaped.** It is in HTTP crawls, remote
raster range reads and multi-gigabyte downloads, whose natural units are *a photo URL*,
*a point on a DEM tile*, *a 1° cell*, *a quad*. So **"delta" in this pipeline means
content-addressed caching at each stage's own unit of work** — which is exactly the rule
`publish.py` already applies per artifact, pushed down one level.

**The first built instance is #1311's DEM sample cache**, and it is the model for the
rest. `export_elevation.py` writes `samples.json` beside the tile index, keyed per point
at six decimal places, and all three elevation exporters read it — the A.T. profile, the
per-edge climb, the per-edge profile — so the second one to run pays nothing for a point
the first already sampled, and a re-run pays nothing for either. Three properties are
what make it a cache a safety path may use:

- **It is discarded whole when the tile-edition marker moves**, never merged. A merge
  would go on serving one re-flown cell's old elevations from whichever entries happened
  to survive, which is the single failure this cache could cause that a hiker would
  feel: a profile confidently wrong about ground that has been re-surveyed.
- **A `None` marker is refused.** A cache nothing can invalidate must not serve a safety
  path.
- **It is an optimisation, not a source.** An unreadable or half-written file reads as no
  cache at all and costs a slow run, never the export.

Its size is the honest gap, and `export_elevation.py`'s own header carries the arithmetic:
run #88 sampled 138,695 points for the A.T. profile (measured 2026-09-08), which at a
~35-byte entry is about 5 MB — and **the junction-graph half is `@unvalidated`, because
nobody has computed it.** The first real run after #1311 settles it, and the file is there
to measure.

**The row-level view stays available and stays where it is.** `lib/data_change.classify()`
already answers "which features were added, removed, moved or edited between these two
GeoJSONs" without a warehouse, a snapshot table or a merge key, and this design uses it
at the raw layer (below) rather than reimplementing it in SQL.

**dbt snapshots (SCD2) become worth building when an exporter reads from the marts, and
not before.** DBT.md defers that wiring, and its own warning has to be repeated here
rather than pointed at, because it is the thing a snapshot design would walk straight
into: **a row in `dim_pois` is not a publishable POI.** The mart carries `public_use` —
each organization's own public/internal flag — deliberately *unapplied*, because
`export_nearby_poi.py` already drops DEC's `N` side with tests behind it (13,823
culverts, gates and sign posts on the backcountry layer alone), and a second safety
filter written in SQL beside the tested Python one is the parallel pipeline
**[#100 — Build the dbt ELT transform layer before NYNJTC's own trail network
arrives](https://github.com/OurHike/OurHike/issues/100)** exists to prevent. Anything that ever exports from that mart reads `public_use` first.

### 3. The raw zone must be private

`_internal/` on the public bucket is world-readable — DATA_RELEASES.md says so in as
many words ("On the current r2.dev public bucket it is nonetheless publicly readable; it
is named to make that obvious rather than to hide it"), and R2_LAYOUT.md's "what does not
belong in the bucket" list already forbids **"mirrors of raw upstream pulls"** there.
Neither rule is negotiable for a raw zone, because raw layers carry rows this project has
decided never to publish:

| what | why it never ships |
|---|---|
| ATC's Campsite Sustainability Index — **2,333 user-created campsites** | SOURCE_SURVEY.md §3b: publishing their locations "may be actively harmful"; these are the sites land managers are often trying to close. `build_water_distance.py` never even requests them. |
| USFS `CAMPING AREA` — **10,783 of `usfs_rec_sites`' 31,405 rows**, measured live 2026-09-02 | Dispersed camping (`development_scale` 0 on 8,135 of them). Held back under the same argument, at 4.6× the scale of the holdback that set the precedent — `sources.json`'s `usfs_dispersed_camping_holdback` carries the evidence. |
| NYS DEC rows the organization flags non-public | `export_nearby_poi.py` drops the `N` side; the warehouse carries the flag unapplied (DBT.md Phase D). |
| opentrail.org's waypoints | Licence unresolved — **[#98 — Confirm opentrail.org data-reuse terms with the maintainer](https://github.com/OurHike/OurHike/issues/98)**, open and `blocked-external`. It has **no registry row at all**: none of `sources.json`'s 37 entries is opentrail (counted 2026-09-09), so not one of the registry's own gates is even asked about it. |

**`reaches_hikers` is not a licence judgement and must not be read as one here.**
`sources.json`'s own `reaches_hikers_comment` says it: true means an exporter reads this
source and its rows reach a release, false means registered-but-not-shipped for any
reason. A raw store holds the bytes of both, before any gate has run.

**Maintainer's decision, 2026-09-08: a second, private R2 bucket.** A read-only token in
the build job, a write token in the extract job, and **it is never given a public domain
or `r2.dev` access.** The public bucket's rules then stay true of the public bucket,
which is the point — R2_LAYOUT.md does not gain an exemption, it gains a sibling.

## Three tiers, and a step cache between them (revised 2026-09-24)

The maintainer's second question, 2026-09-24, home
**[#1653 — Write down where processed pipeline data lives between runs: a private step
cache keyed by input hash, and which format holds it](https://github.com/OurHike/OurHike/issues/1653)**:

> Lets say we start storing some data on R2 so we dont need to reprocess it constantly.
> Like we load the largest files to R2 or the ones that are comput intesince and only
> process those monthly. Should we just make a duckdb that lives out there too and holds
> the process data? Is that the best format or should we use something like iceberg?

**Short answer: yes, keep processed data in R2, but as each expensive step's own output,
stored under a hash of what went into it, not as one database.** The raw store above
keeps what was *downloaded*. It does not keep what was *computed*, and most of a build's
time is computation. So this revision adds a second private tier, the **step cache**,
between the raw store and the public bucket. DuckDB stays the engine that reads both, not
the place either lives.

### Where a build spends its time

The eight longest steps of `publish-vector-data.yml`'s build job, measured from the step
timings of two consecutive runs on `main`, 2026-09-23:

| step | [#140](https://github.com/OurHike/OurHike/actions/runs/35915344855) | [#141](https://github.com/OurHike/OurHike/actions/runs/35921489619) | the work |
|---|---|---|---|
| `export_network_elevation.py` | 15:32 | 2:50 | DEM block reads when `samples.json` is cold; Python resampling of 656,621 edges when warm |
| `export_nearby_trails.py` | 8:13 | 8:17 | Python geometry over the other organizations' layers |
| `build_trail_graph.py` | 5:36 | 5:35 | Python geometry: noding the network into a graph |
| `fetch_hikefinder.py` | 3:49 | 3:50 | HTTP; the export serves no ETag or Last-Modified |
| `fetch_elevation.py` | 3:11 | 3:10 | 476 HTTP HEADs to pin DEM tile editions |
| `export_network_profile.py` | 2:45 | 2:47 | the same resampling, every point already cached |
| `export_trails.py` | 2:39 | 2:39 | Python geometry |
| `fetch_external_layers.py` | 2:36 | 2:33 | HTTP |
| **build job, whole** | **52:54** | **39:57** | |

#140 started with 283 of 10,382,251 DEM points cached and #141 with all of them. That
one difference is 12:42 of the 12:57 between the two runs. **No step in either list is a
query over attribute rows.** `dbt build` is not in this workflow at all. So which *table
format* the processed data sits in decides very little of this. What decides it is
whether a step runs at all.

### The three tiers

| tier | holds | written by | read by | where |
|---|---|---|---|---|
| **1 · raw store** | upstream bytes exactly as sent, each source on its own clock | the extract job | the build job, read-only | private bucket (the 2026-09-08 decision above) |
| **2 · step cache** | each expensive step's output, under a hash of its inputs, its code and its tool versions | the build job | the build job | a **second** private bucket (below) |
| **3 · public bucket** | published artifacts | the publish job | phones | unchanged: DATA_RELEASES.md, R2_LAYOUT.md |

### The rule for when a step runs

**Downloads run on a calendar, one per source. Computation runs when its inputs change.**
The calendar is the clocks table below: OSM monthly, the conditions bake hourly, and so
on. A step does not have a calendar of its own. When OSM refreshes on the first of the
month, the steps that read OSM run once in the next build and are cache hits after that.

- **The key is a hash of everything the output depends on:** each input's sha256 (from
  the raw store's `index.json` for a raw input, and from the producing step's own key for
  a step's output), the source of this repository's modules the step imports, its
  parameters (`SAMPLE_INTERVAL_METERS`, a dead band, a buffer radius), and the versions of
  duckdb, the spatial extension, shapely, pyproj, rasterio and GDAL.
- **A key is written once and never overwritten**, so a step cannot serve half of an old
  answer. That is the discard-whole rule `_load_sample_cache` already follows, made
  structural: a changed input is a different key, not an edit to the old one.
- **Only a deterministic output is stored.** An output that depended on something the key
  cannot see is computed and used but not written. Two examples: a DEM tile whose
  edition the index could not pin (`_sources_with_no_pinned_edition`'s existing rule),
  and a network call made inside the step.
- **It is an optimisation, never a source**, in the same words the DEM sample cache uses.
  An unreadable object, a hash that disagrees with its entry, or a store that is not
  configured yet all mean "run the step". None of them fails the export.
- **The unit is the step's own**, which is clarification 2 above. It is the whole output
  for a step whose inputs move together, like the OSM water scan. It is per unit inside a
  step whose output is a list of independent answers, like the climb for each graph edge.

The first candidates, and what each would save:

| unit | step | what it would save | issue |
|---|---|---|---|
| per-edge climb and profile | `export_network_elevation.py`, `export_network_profile.py` | 15:32 cold, 2:50 and 2:47 warm (measured above), for every edge whose geometry did not move | **[#1651 — The two graph-elevation steps resample all 656,621 edges every run, and re-read 9.5M DEM points whenever the Actions cache is cold](https://github.com/OurHike/OurHike/issues/1651)** |
| the 14 OSM state extracts (tier 1) and the water scan (tier 2) | `fetch_osm_water.py`, `fetch_trail_water.py`, `build-basemap.yml` | ~3.5 GB and ~15 min whenever the Actions cache lapses (the workflow input's own figure) | **[#1652 — Download OSM's Geofabrik extracts at most once a month, into a private raw bucket that outlives the 7-day Actions cache](https://github.com/OurHike/OurHike/issues/1652)** |
| whole-step outputs of the network chain | `export_nearby_trails.py` → `build_trail_graph.py` → `export_trails.py` | up to 16:28 (#140's three steps), on a build where none of the layers they read moved | none yet |

**How often that last row would hit is `@unvalidated`.** #1311 measured the 18 external
layers re-fetching byte-identical on consecutive runs (run #88, 2026-09-08). That says
unchanged inputs happen; it does not say how often. The raw store's `log.json`, one row
per fetch attempt, is what would measure it.

### DuckDB's role: the engine, plus a copy to browse

- **Each build assembles its working database from tiers 1 and 2**, rather than every
  step re-parsing GeoJSON. Measured in a sandbox, 2026-09-24, on a synthetic stand-in
  for `nearby_trails.geojson` (112,000 lines, 268 MB): re-parsing it with `json.loads`
  plus shapely takes **12.5 s**, and reading the same lines from a persisted DuckDB table
  into a shapely array takes **0.8 s**. Six steps read that file today:
  `export_nearby_poi.py`, `reconcile_poi_identity.py`, `export_poi.py`,
  `build_trail_graph.py`, `export_places.py` and `fetch_elevation.py`.
- **Geometry crosses from DuckDB to shapely as WKB, not WKT.** On the same benchmark, WKT
  took 7.9 s against WKB's 0.8 s, and `export_trails.py` and `export_nearby_trails.py`
  pass WKT today.
- **A read-only browse copy, for people** (the maintainer's choice by poll, 2026-09-24).
  This is a `.duckdb` file rebuilt after each publish and kept in the step-cache bucket.
  It is opened from a laptop with `ATTACH '<url>' (READ_ONLY)`. Measured in the same
  sandbox over HTTP with range requests: counting a 112,000-row table pulled **1.3 MB of
  a 167 MB file**, and an attempted `CREATE TABLE` was refused ("attached in read-only
  mode"). It holds every never-publish row in the table under clarification 3, so it
  gets the same privacy as the rest of the store, and no pipeline step reads it.

### Which format holds tier 2

The four options the question raised, each checked against the pinned `duckdb==1.5.5`
in a sandbox on 2026-09-24:

| option | updating one table | geometry | history | verdict |
|---|---|---|---|---|
| **One `.duckdb` file on R2** | Download the whole file, change it, upload the whole file. One writer. | native | none: each upload replaces the last | **The browse copy above, not the store.** Readers are cheap (measured above). Writes are whole-file, and the file format follows the DuckDB version, which `requirements.in` pins by hand. |
| **Iceberg, through R2 Data Catalog** | new Parquet files plus a committed snapshot | a WKB binary column, unless Iceberg v3's geometry type works end to end, which was not checked | snapshots, time travel | **Not now.** Built for many writers and many engines, and this pipeline has one CI writer and one engine. R2 Data Catalog is Cloudflare's managed Iceberg catalog inside R2: open beta since 2025-04-10, pricing published in May 2026 ($9.00 per million catalog operations after 1 million free a month), billing not yet switched on (Cloudflare changelog, read 2026-09-24). DuckDB's `iceberg` extension installs and loads on 1.5.5; **writing to an R2 catalog from it was not tried**. |
| **DuckLake** | new Parquet files, plus a small catalog database | native: a `GEOMETRY` column round-tripped | snapshots, and a change feed per table | **The upgrade path.** It is the "DuckDB that lives out there" done properly. The `ducklake` extension installs on 1.5.5. Two inserts produced two Parquet files and two snapshots, and the geometry read back exactly as written. It is newer than Iceberg and bound to the same DuckDB pin. |
| **Plain files plus `index.json`** | rewrite only the file that changed | GeoParquet for vector tables; each upstream's own format in tier 1 | the raw store's `log.json` | **Start here.** Any tool reads them, and it is the layout this document already designs for tier 1. |

**What would move the verdict.** Move to DuckLake when this design starts hand-building
snapshots or change tracking beyond `log.json`, which is exactly what DuckLake does
natively. Move to Iceberg when a second engine needs the same tables (R2 SQL, Spark, a
partner's warehouse), or a second writer appears. Neither is true on 2026-09-24.

**Rasters stay out of every tier.** The DEM is read in place from USGS's own
Cloud-Optimized GeoTIFFs. Only what is sampled from them, like the per-edge climb, is
cached, in tier 2. DBT.md's "Deliberately excluded: raster pixel data" paragraph holds the
reasoning and the 2026-09-24 measurements of the `raster` and `raquet` extensions.

### Why the step cache is a second private bucket

**R2 API tokens are scoped to buckets, not to key prefixes.** The permission groups are
"Bucket Item Read" and "Bucket Item Write" on named buckets, and only short-lived
temporary credentials can be narrowed to paths (Cloudflare's R2 token documentation,
read 2026-09-24). The build job writes the step cache. If the step cache were a prefix in
the raw bucket, the build job would need write access to that bucket, and "the build job
cannot write raw" (the clocks table below) would stop being true. A second bucket keeps
it true for the price of two more secrets.

The alternative is one private bucket with write access in the build job. It is simpler,
it gives up that guarantee, and it is recorded here so the choice is visible rather than
made by default.

## The shape: four clocks

The column that matters is the third one, the same way it is in DATA_RELEASES.md's own
table: a job that cannot write to a bucket cannot damage what a hiker downloads, whatever
else it gets wrong.

| clock | job | can write R2 | what it does |
|---|---|---|---|
| hourly (`40 * * * *`) | `publish-conditions.yml` — **exists** | **public bucket, `conditions/` only** | The closures/reports/notes/drought/ATC-updates bake. Untouched by this design. |
| daily | **`extract-sources.yml` — NEW, UNBUILT** | **private raw bucket only** — holds no public-bucket credential | Pulls the previous outputs from the private store, runs the cheap change-aware fetchers, pushes back only what moved, appends a row per source to the raw delta log. A source can carry a **maximum age** instead of a change check: the OSM state extracts carry 30 days, so this daily job downloads them at most monthly (#1652, below). |
| daily (`20 7 * * *`) | `check-upstream-freshness.yml` — **exists** | **no — holds no credentials at all** | Compares published `build_state.json` against live upstream markers and flags into its one tracking issue. DATA_RELEASES.md §1. |
| dispatch, weekly under DATA_RELEASES.md §2 | `publish-vector-data.yml` — **exists** | public bucket, and the **step-cache bucket** (revised 2026-09-24) | Restores raw from the private store instead of from a 7-day Actions cache; each step looks up its key in the step cache before running, and writes its output there after. |

**The OSM extracts go monthly, and nothing that warns a hiker does** (the maintainer,
2026-09-24: *"We should only download a lot of the data like once per month. The OSM data
doesn't need to be updated so frequently"*). Offered the same day and not chosen: the
other organizations' layers, the NYNJTC Hike Finder export and the USGS edition checks.
Closures, alerts, ATC trail updates and the hourly conditions bake keep their cadence
whatever else moves, because a month-old closure list puts a hiker in front of something
dangerous. **The 30 days is `@unvalidated`**: it is the maintainer's round number, and
nobody has measured how fast OSM's water and stream data changes along this corridor. The
extract job's `log.json` rows for OSM are what would measure it.

Three properties of that table are deliberate and worth not collapsing later:

- **The extract job cannot publish.** It carries no public-bucket credential, so a bug in
  a fetcher cannot reach a phone. It is the same structural argument DATA_RELEASES.md
  makes for the freshness check, one bucket over.
- **The build job cannot write raw.** Its private-bucket token is read-only, so a build
  cannot quietly redefine what "yesterday's bytes" were. (Whether it should hold that
  token at all is an open question below.)
- **The build job can write the step cache and nothing else private.** That is why the
  step cache is its own bucket: "Why the step cache is a second private bucket" above.

## The store's layout

Two trees, and the second one is the delta table.

```
current/<path relative to pipeline/data/raw>     # mirrors the fetchers' own outputs
current/index.json                                # {sha256, size_bytes, pushed_at} per file
snapshots/<source_key>/<timestamp>_<sha12>.geojson
snapshots/<source_key>/log.json                   # append-only, one row per fetch attempt
```

The step-cache bucket (revised 2026-09-24) has a simpler shape, because a key never
changes meaning:

```
steps/<step name>/<key>/<output files>            # written once, never overwritten
steps/<step name>/<key>/inputs.json               # what the key hashed, readable
browse/ourhike.duckdb                             # the read-only copy for people
```

`inputs.json` is there so a hit can be explained: a person can see which input hashes,
module sources and versions a stored output was computed from. **How long old keys are
kept is an open question below.**

**`current/` mirrors `data/raw/` exactly**, path for path, because the fetchers' own
output layout is already a designed thing (`FETCH_OUTPUTS` in `publish-vector-data.yml`
is that list, checked against the fetchers' constants by
`tests/test_fetch_cache_paths.py`). A second naming scheme here would be a second place
for that list to drift.

**`index.json` is what makes a push and a pull cheap.** A push uploads only files whose
sha256 differs from the index; a pull skips any file whose local copy already hashes to
the recorded value. It is the same rule `publish.py` applies to artifacts, and it is why
neither direction needs a per-file HEAD — one small JSON read answers for the whole tree.
(#1311 measured what per-object round trips cost on the public side: 1,267.68 MB across
1,715 artifacts plus ~3,016 photo objects in 2,147 seconds on run #88, 0.45 s per object,
on a runner that pushed 422 MB into the Actions cache at 172 MB/s.)

**A snapshot object is written only when content moved.** DEC's back-country layer has
not changed since 2026-08-18 by the field its marker reads (`lib/arcgis.py`'s
`get_layer_max_field` docstring), so under this design the ~21,470 features it holds cost
a marker read and nothing else, every day, indefinitely. The timestamp-plus-short-hash
name means a snapshot can never overwrite another and reads in fetch order in a listing.

**`log.json` is the delta table, at the raw layer.** Append-only, **one row per fetch
attempt** — including the ones that found nothing, because "we looked and it had not
moved" is the observation that settles the open questions below, and a log of only the
changes cannot make it:

```json
{"fetched_at": "...", "marker": "...", "sha256": "...", "size_bytes": 0, "key": "...",
 "change": {"severity": "routine", "added": 0, "removed": 0, "moved": 0, "edited": 0}}
```

`change` is `lib/data_change.classify()` over the previous snapshot and the new bytes,
and is **absent rather than zeroed** on a run that fetched nothing — absent means nobody
diffed, and a row of zeroes would say the opposite. It is the same function `publish.py`
already runs on the published side, so "eleven new privies" and "the spring you were
walking to is gone" are distinguishable at the raw layer, months before anybody asks the
warehouse. `marker` is whatever that source's change detection actually compared,
recorded verbatim, so **both sides of every comparison are in the log** — which is how
the Forest Service's `@unvalidated` service-metadata ETag gets settled rather than
assumed (below).

Three properties this shape is chosen for, stated so a later change can be weighed
against them:

- **The log is evidence, not a cache.** Deleting `current/` costs a re-fetch; deleting
  the log costs the history of what upstream did, which nothing can reconstruct.
- **`classify()` grades an unreadable diff as CONSEQUENTIAL, never routine.** That is its
  own documented choice and it is the right direction here too: a raw file this cannot
  parse is one somebody should look at.
- **Nothing in the store is a URL.** Every object is reached with a credential, which is
  what makes it legitimate to hold the rows in the table above.

### The private bucket needs its own key validator, not `lib/r2_keys.py`

This is the part most likely to be got wrong by reuse, so it is written down. Every rule
in `lib/r2_keys.py` exists because **a key in the public bucket is a permanent URL**:

- **at most 4 segments** — `snapshots/<source_key>/<timestamp>_<sha12>.geojson` is 3 and
  fits, but a per-quad or per-tile raw tree would not, and the reason for the limit ("a
  prefix doing a manifest's job") is an argument about a served layout;
- **the banned word `latest`** — banned because a permanent URL must not describe itself
  as current, which is exactly what `current/` here is *for*;
- **a closed extension set** — `geojson`, `fgb`, `pmtiles`, `json`, `tif`, `jpg`, "the
  set the bucket serves". A raw store holds `.duckdb`, `.parquet`, `.pbf`, `.zip`, `.pdf`
  and whatever an upstream sends next, and none of it is served to anybody.

So the private store gets a **small validator of its own** — no reserved words, no
segment ceiling, and a rule set aimed at the one thing that does still matter there: a
key that cannot collide and cannot escape its prefix. Reusing `r2_keys.py` would either
fail legal raw keys or force its rules to be loosened for the public bucket, and the
public bucket is the one where a wrong name cannot be taken back. **The same validator
serves the step-cache bucket** (revised 2026-09-24), whose `steps/<step name>/<key>/` keys
fail `r2_keys.py` for the same reasons raw keys do.

### Secrets, and degrading until the account work lands

Eight new repository secrets, plus one reused. The three `R2_STEPS_*` rows were added
2026-09-24:

| secret | held by | why |
|---|---|---|
| `R2_RAW_BUCKET` | both jobs | The private bucket's name. Separate from `R2_BUCKET` so no code path can reach one holding the other's name. |
| `R2_RAW_READ_ACCESS_KEY_ID` / `R2_RAW_READ_SECRET_ACCESS_KEY` | the build job | Read-only token. |
| `R2_RAW_WRITE_ACCESS_KEY_ID` / `R2_RAW_WRITE_SECRET_ACCESS_KEY` | the extract job | Write token, and the only credential in that job. |
| `R2_STEPS_BUCKET` | the build job | The step-cache bucket's name (revised 2026-09-24). |
| `R2_STEPS_WRITE_ACCESS_KEY_ID` / `R2_STEPS_WRITE_SECRET_ACCESS_KEY` | the build job | "Bucket Item Write" on the step-cache bucket only, which includes reading it. |
| `R2_ENDPOINT_URL` | both, **reused** | R2's endpoint is account-scoped rather than bucket-scoped, so a second bucket in the same account is the same URL. A second copy of it would be a second thing to rotate. |

The browse copy is opened with a **personal read-only token** on the step-cache bucket,
created by whoever wants to query it. It is not a repository secret, because no workflow
reads the copy.

**Every step that needs one of these degrades with a `::warning` and continues**, until
the account work exists — the posture `publish-conditions.yml`'s "Is there a database to
read" step already takes for an unconfigured conditions database: it names what did not
happen, sets its own `go=false`, and lets the legs that need no credential run. A
merged-but-unconfigured extract job that fails red every morning is a job whose failures
stop being read, which is the same argument DATA_RELEASES.md §1 makes for the freshness
check treating staleness as news rather than an error.

## Phases, honestly ordered

- **Phase 0 — #1311's measured regression. Landing now, on the branch that carries this
  document.** It comes first because a jump in data volume makes every incremental unit
  bigger in proportion — `nearby_trails.geojson` went from 21,805 features on a live
  fetch 2026-08-25 (DBT.md Phase D) to 112,439 once the USFS nationwide layers registered
  on 2026-09-02 (#1311, measured on run #88), roughly five times — so nothing below would
  have prevented the last twelve days. What
  landed, in the order it was committed: unbuffered logs on both publishing workflows,
  with the build timeout 120 → 180 minutes, so a slow step stops reading as a hang;
  `fetch_external_layers.py` reading `sources.json`'s substitute change markers, with
  `data/raw/external/` joining the carried cache paths; the corridor's network widening
  turned from a union of 112,439 buffered lines into an R-tree join; the DEM sampler
  reading only the 512-px blocks a point lands in, with the shared per-point cache that
  is this design's first delta unit; the publish's per-object round trips replaced by one
  listing and bounded pools; and the hourly conditions bake given a pip cache and
  content-addressed cache keys, in place of three new entries per run.
- **Phase 1 — this document.** #1312, revised 2026-09-24 under #1653 to add the step
  cache and settle the storage format.
- **Phase 2 — the extract job and the private store.** `extract-sources.yml`, the
  push/pull client, the key validator, `index.json`, `snapshots/` and the log. The build
  job learns to restore raw from the store before falling back to a cold fetch, exactly
  where it restores from the Actions cache today. **The OSM state extracts go first**
  (#1652), because they are the one source with a maintainer's cadence decision and the
  largest single download.
- **Phase 3 — the step cache, then per-unit reuse in the expensive stages.** The DEM
  sample cache is built. Next is the step-cache client (a key function, a lookup and a
  write-once put) and its first unit, the per-edge climb and profile (#1651). Then the
  network chain's whole-step outputs, with the working database assembled from
  GeoParquet and WKB instead of re-parsed GeoJSON, then the browse copy. After those come
  per-cell raster reuse — **DATA_RELEASES.md's own unbuilt Phase 5**, including the
  per-cell corridor-slice hash that stops a Georgia centerline edit rebuilding Maine —
  and per-quad reuse under it.
- **Phase 4 — exporters reading from dbt marts, with snapshots as the row-level delta.**
  Longest, last, and gated on the `public_use` warning above being answered in the export
  path rather than in SQL. Nothing in Phases 0–3 depends on it.

## Rejected, with the reason

Written down so the next session does not re-propose them from the same intuition — the
pattern #1294 set, and **[#393 — What OurHike costs to run, who pays for it, and the
guardrails that keep a bad week off a personal credit
card](https://github.com/OurHike/OurHike/issues/393)** before it with its "Non-options,
considered and rejected" section.

- **Delta Lake or Iceberg as the raw/table format.** It means `pyarrow` plus `deltalake`
  in an environment whose `duckdb` is pinned by hand to `1.5.5` because DuckDB extensions
  are ABI-locked and `duckdb-extension-spatial` must publish a matching build
  (`requirements.in`'s only hand-written constraint) — and those pins install in jobs
  holding R2 write credentials (CONTRIBUTING.md). For that, a table format that touches
  **none of the expensive stages**: the cost measured in #1311 is a corridor union, a
  raster window read, a per-object round trip and a 195,000-feature re-fetch, and a
  transactional table format changes none of them. Against value #8 — "boring,
  well-supported technology over cutting-edge complexity". #1294 declined a neighbouring
  proposal on overlapping grounds, and reasons 1, 2 and 4 there apply here unchanged.
  **Re-checked 2026-09-24, and still declined, for a narrower reason.** Two of the costs
  above have shrunk. R2 now runs the Iceberg catalog itself (R2 Data Catalog), and
  DuckDB's own `iceberg` extension loads on 1.5.5, so neither `deltalake` nor a catalog
  server would be needed. The reason that stands is the one about expensive stages, now
  with a table behind it: "Where a build spends its time" in the three-tier section shows
  no step in the eight longest querying attribute rows. The verdict and what would move
  it are in that section's format table.
- **Round-tripping the warehouse through the public bucket** so the next run can restore
  it. Three independent refusals: `.duckdb` and `.parquet` are not in
  `r2_keys.ALLOWED_EXTENSIONS` and adding them would mean the public bucket serving a
  format no client reads; the file holds every never-publish row in the table above,
  `public_use` carried and unapplied; and nothing downstream reads the warehouse at all
  yet (DBT.md, "Open scope boundaries"). It is a private-store question if it is anyone's,
  and today it is nobody's. **Answered 2026-09-24:** it is the step-cache bucket's
  question now, as the read-only browse copy. That copy is never a store any step reads.
- **One `.duckdb` file on R2 as the store for processed data** (asked 2026-09-24). An
  update means downloading the whole file, changing it and uploading the whole file,
  there is only one writer, and each upload erases the history. The file format also
  follows the DuckDB version that `requirements.in` pins by hand. Reading it remotely is
  cheap (measured in the three-tier section), which is why it is the browse copy and not
  the store.
- **Stripping `generated_at` from the conditions artifacts** so an unchanged hour uploads
  nothing. It would work — the bake is the one thing on an hourly clock, and its bytes
  are otherwise identical most hours. #1311's cache-key change reached this question on
  2026-09-09 and left the stamp baked in deliberately, so this is a decision taken rather
  than an idea nobody had. It is refused because the client renders that field
  as "as of &lt;date&gt;" (R2_LAYOUT.md's `conditions/` note), so an hour-old verified
  closure list would read to a hiker as three days old. Saving an upload by making a
  safety artifact look staler than it is inverts value #4 — "honesty about uncertainty
  ('reported 3 days ago' vs. 'confirmed today')" is the example the value itself uses.

## Open questions

Seven, none of them blocking Phase 2, and each with what would settle it. The two added on
2026-09-24 come first.

- **How long should the step cache keep an old key?** A key is never overwritten, so the
  bucket only grows. Keeping the last few keys per step makes a revert cheap, and keeping
  one makes storage flat. **Nothing has measured the sizes.** #1651's two per-edge files
  come to ~24 MB and ~68 MB by arithmetic: 656,621 keys at ~25 bytes each, plus the values.
  The profile's values alone are `trail_graph_profile.json`'s 51,854,022 bytes, measured on
  run #140. The network chain's outputs have not been sized. The first month of the bucket's own
  listing settles it. R2 charges for storage and not for egress, so the question is
  money, not speed.
- **How often does a step-cache key actually hit?** This is the "how often" behind the
  whole-step row of the three-tier section's candidates table, `@unvalidated` there. The
  raw store's `log.json` answers it for the inputs, one row per fetch, and the build's
  log answers it for the steps, if each lookup prints hit or miss the way
  `ElevationSampler.report` prints cache counts today.

- **How many 512-px DEM blocks does a 468,743-edge network touch, and how large does
  `samples.json` get?** `@unvalidated` — the A.T. half is ~5 MB by arithmetic from
  138,695 sampled points (run #88, 2026-09-08); the graph half has never been computed.
  **The first CI run after #1311 answers it twice over**: the sampler logs its point
  count and the file is there to measure. If it is hundreds of megabytes the answer is a
  shape that can be appended to, not a policy for discarding points.
- **Does the Forest Service's service-metadata ETag move when its features move?**
  `sources.json` tags it `@unvalidated` — an ETag on the *metadata* has not been shown to
  track the *features* — and `fetch_external_layers.py` now records both sides of every
  comparison per run, so a handful of runs settles it. Until then that layer's skip is
  believed rather than known.
- **Was publish's 0.45 s per object request latency or R2-side throttling?** Measured on
  run #88 (1,267.68 MB, 1,715 artifacts plus ~3,016 photo objects, 2,147 s) with the same
  runner pushing 422 MB into the Actions cache at 172 MB/s, which rules out bandwidth and
  not throttling. The pooled upload #1311 landed will say: if concurrency scales the
  throughput it was latency, and if it plateaus it was the other thing.
- **Why does the fetch cache miss?** Two candidates, calling for different fixes.
  `publish-vector-data.yml`'s own comment blames GitHub's 7-day eviction of an entry
  nobody read, against a release cadence of about a month. The other is size: the hourly
  conditions bake keyed all three of its saves on `github.run_id` until #1311, opening
  roughly 144 entries a day against a 10 GB per-repository limit that evicts
  least-recently-used, while the fetch cache is ~403 MB. **That second hypothesis is
  `@unvalidated`** — reasoned from the key shapes, never measured — and **one listing of
  the Actions cache API before and after that change settles it.** Worth asking before
  the private store is built: if the entry is merely idle-evicted, the store's value is
  durability rather than speed, and the two are argued for differently.
- **Should the build job hold a read-only private-bucket token at all?** The alternative
  is the extract job publishing raw as a workflow artifact the build downloads, which
  removes the credential entirely at the cost of a retention window measured in days and
  a coupling between two workflows' runs. The decision above is the token; this records
  that the other shape exists and is not obviously worse.
