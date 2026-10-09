---
name: dlt
description: Work on the extract-and-load layer in pipeline/extract/ - the dlt resources that land every club's and every shared source's data in the private raw store. Use when adding a club, adding or changing a resource, writing or rechecking a NOT_AVAILABLE or SAME_AS note, touching .dlt/config.toml, writing an extract test, or when a dlt run check refuses a load. Covers the folder contract, one extraction per upstream dataset, the note format, the four measured hazards as rules, the three data checks, loading every club while gating publication downstream, the rule that terms are never routed around, how to add a club, testing under the socket guard, the purge for a field that should never have loaded, and why dltHub's AI harness is not installed.
user-invocable: true
---

# dlt in this repository

**Part of this is built, on the #1793 branch, and part is still the target.**
Stage 2a built `pipeline/extract/` (`_contract.py`, `_kinds.py`, `_run.py`,
`_warehouse.py`), `pipeline/.dlt/config.toml`, `requirements-extract.in`, and
the `atc/` and `nysdec/` folders, with `tests/test_extract_layout.py` and
`tests/test_extract_run.py`. Stage 2b's first half added the 21 providers whose
registered layers are all ArcGIS (`nysparks/`, `usfs/`, `pcta/` and the rest),
claiming 26 keys; `nycparks/` and `nycdot/` through the Socrata kind, 7
more; and `nynjtc/` through the WordPress, guide-page and Hike Finder kinds,
5 more, with the daily rule in `_run.py`; and `gatc/` through the club-PDF
kind. 1 key remains on `NOT_YET_EXTRACTED`, `usdm_drought`, with its blocker
beside it.
Every one of the 145 managing clubs answers every type: decision 88 put each
note and share in one file, `pipeline/extract/not_available.toml`, so 103
clubs have a folder of resource files and 42 have none, and
`_shared/not_clubs.py` holds the 25 umbrella and route-only lines (`NotClub`
in `_contract.py`). `_shared/` files declare a
`TYPE` and are found by `discover_shared()`; the four reviewed files load
there (podcast episodes, shelter capacity, highlights, work projects), and
opentrail's A.T. waypoints through `opentrail_feed()`, a non-registry input
whose file says why it claims nothing (`UNREGISTERED`), the `usgs_3dhp`
watch through `hydrography_watch(key)`, and every active NWS alert through
`nws_alerts()`, hourly, and 3DEP's and NHD's bucket listings through
`bucket_listing(key)`, and OurHike's own closures, reports, notes and
disputes through `conditions_query(key)`, the bake's queries over psycopg.
A change check may raise `Unavailable` (`_contract.py`) for an input its
own rule omits rather than stops on: the run leaves it out, and the
warehouse withdraws it. OSM's extracts land through `_shared/osm/geofabrik.py`,
fixture mode is `extract/_fixtures.py`, and the monthly lane and both conditions
jobs run against R2. Not built yet: `_shared/`'s other fetched resources
(NBM, NDMC; EPQS and Wikimedia, which query by POI), the as-sent copy beside
dlt's load (OSM's extracts aside, which `_geofabrik.py` mirrors as sent), and
the raw lake. Those come only from the old fetchers (`fetch_*.py`), and the
release build (`publish-vector-data.yml`) still reads every source through the
old fetchers and `fetch_all.py`; a change to one of those follows its own
docstring and tests. On `main` none of this exists until the pull request
merges.

This layer is planned because the maintainer reversed a written decision, on
2026-10-01: *"So that was you claude who pushed so hard on not using dlt. Trust
me, it will make things easier."* The decision it reverses is **#1294 —
Evaluated and declined: dlt for the fetch layer, and a weekly cadence for
non-alert data**. Do not re-argue it. Its measured hazards come back below as
rules, most of them from **PR #1363 — Port the ArcGIS fetch to dlt and count
it, instead of estimating what it replaces**, a spike closed unmerged on
2026-09-09 and called "the 2026-09-09 spike" below.

`pipeline/ELT.md`, "Extract and load (dlt)" and "The data checks", owns the
design. This file is the order of work and the traps. [CLAUDE.md](../../../CLAUDE.md)
wins over both, and where this file and CLAUDE.md could be read as
disagreeing, this file has a bug. "Decision N" below is a row of the
maintainer's decisions table in `pipeline/ELT.md`, "Overview".

Three terms are used throughout. **The raw store** is where the extract lands
raw: the private R2 bucket `our-hike-raw` (`R2_RAW_BUCKET`), under `raw/`,
every source alike, by ELT.md's decision 43, which voids decision 42's
hold-out list. The step cache shares it under `steps/`. The app never reads it. **The raw lake** is the DuckLake form
the monthly lane's raw tables move to at phase 3 (decision 26). **A lane** is
the scheduled job that reads a resource, set by its `meta.cadence`: closures,
warnings, NWS alerts, the NBM forecast manifest, the drought feed and OurHike's
own Postgres rows are hourly; NYNJTC's alert taxonomy terms are daily; nothing
is weekly; everything else is monthly (decisions 1 and 28a).

## Why there is no dlt plugin

The maintainer asked whether dlt has a skill set to add, and chose by poll
(decision 16) **this repository skill only**.

- **dltHub's AI Harness (`dlt-hub/dlthub-ai-harness`) is not installed.** Its
  licence (the repository's `LICENSE`, read 2026-10-01) permits use "solely in
  connection with dltHub Services under a governing Agreement", and lists as
  not permitted "Using toolkits and skills provided by dltHub to generate code
  or pipelines for deployment on a third-party runtime platform or
  orchestration service that is not part of dltHub Services." OurHike holds no
  dltHub Agreement, and every pipeline here runs on GitHub Actions (Reasoned).
  Do not install it for a session either.
- **`dlt-mcp` 0.3.0 (Apache-2.0) is not installed**, by the same poll.
- **dlt itself, 1.30.0, is Apache-2.0** and is what the extract layer pins.
  For generic questions, dlt's own documentation at dlthub.com/docs is the
  reference.

## The order of work

1. **Registry rows first**: a reviewed `pipeline/reference/trail_orgs.json` row
   for the club, and a `pipeline/sources.json` row for every upstream that no
   other folder already extracts ([below](#one-extraction-per-upstream-dataset)).
2. **The club's answers**: a resource file for each type it publishes, and a
   row of `not_available.toml` (a share or a dated note) for every other type.
3. **The traps**: the four hazards below, checked line by line.
4. **The tests**, under the socket guard.
5. **The dbt staging** for every available type ([the dbt skill](../dbt/SKILL.md)).
6. **The pull request**: the new-data review report and `scripts/pipelines.sh`.

## The folder contract

```
pipeline/
  .dlt/config.toml   # committed: telemetry off, naming, file format. Never credentials
  extract/
    _contract.py     # TYPES, FILE_TYPES, NotAvailable, discover(), the lane and claim maps
    _kinds.py        # one builder per source kind
    _run.py          # change checks -> extract -> normalize -> run check -> load
    _warehouse.py    # raw store -> warehouse.duckdb `raw` (load_raw.py's successor)
    _shared/         # free-form: national services, aggregators, OurHike's own data, not_clubs.py
    not_available.toml  # every club's notes and shares, one row per club x type (decision 88)
    atc/  nysdec/  … # a managing club's resource files, one per type it publishes
```

**Never `pipeline/dlt/`.** Scripts run from `pipeline/`, which is first on
`sys.path`, so a `dlt/` folder there would shadow `import dlt` (decision 12).

**Every managing club answers every type** (decisions 18 and 88): 145 clubs
from `trail_orgs.json` at 23fca25, which is its 173 rows minus 12
`national_umbrella`, 13 `route_only` and 3 `aggregator`. A club with no
resource file has no folder: 103 have one (counted 2026-10-06). Umbrellas and route-only trails get one dated line each in
`_shared/not_clubs.py`. Aggregators (`osm`, `outerspatial`, `avenza`) live in
`_shared/`. Anything real an umbrella publishes, such as a podcast, goes in
`_shared/` too.

**The folder name is `trail_orgs.json`'s `slug` with `-` written `_`**, because
Python cannot import a hyphen. No slug has an underscore, so the mapping
reverses exactly (measured 2026-10-01). There is no `__init__.py`: a folder
holds its resource files and nothing else.

**Each of the ten types is answered exactly once** (decision 13, as decision 88
amends it), by `<folder>/<type>.py` or by the row `[<folder>.<type>]` of
`not_available.toml`, and the layout test fails a type answered by neither or
by both. The eleventh type, `org`, is the club's catalogue row:
`discover()` makes one for every managing club from `trail_orgs.json`
(`catalogue_row()` in `_kinds.py`), so nobody writes it.

| type | feeds | lane |
|---|---|---|
| `org` (the catalogue row, made by `discover()`) | `sources` | monthly |
| `trail_lines.py` | `trail_lines`, `trail_network`, elevation calibration | monthly |
| `points_of_interest.py` | `points_of_interest` | monthly |
| `elevation.py` | `elevation` (3DEP itself is `_shared/usgs/`) | monthly |
| `closures.py` · `warnings.py` | `closures` · `warnings` | **hourly** |
| `places.py` | `places` | monthly |
| `suggested_hikes.py` | `suggested_hikes` | monthly |
| `podcasts.py` · `challenges.py` | `podcasts` · `challenges` | monthly |
| `photos.py` | photo manifest rows, never pixels | monthly |

`trail_network` and `sources` have no file: dbt derives them. The lane
belongs to the type. Each answer is exactly one of:

- **A resource file, `CLAIMS` + `RESOURCES`**: the `sources.json` keys it owns,
  and a `Resource` for each. It may carry `SAME_AS` notes for the copies it
  does not extract, or be `SAME_AS` alone, when a republished copy of another
  resource's dataset is all the org publishes for this type.
- **A share row, `shares = "<type>"`**: a sibling type's resource file also
  feeds this type. One upstream is one resource and one raw table even when it
  feeds two types, so `[atc.warnings]` holds `shares = "closures"` and claims
  nothing.
- **A note row**: a dated note (below).

**`not_available.toml` is one file for every club**, so two sessions adding
notes for different clubs both edit it. Its rows are sorted by club, then type,
and a blank line separates each. Measured 2026-10-06 on a two-row copy: git
merged an edit to one row with an edit to the next, and refused two new rows
inserted between the same two rows. So sessions that add rows in parallel
(a wave's workers) hand them to one session to write, as `sources.json` rows
are handed to the lead. Its header comment says how `discover()` and the layout test read it, and how
to retire a row.

**A builder takes a `sources.json` key, never a URL.** A club file therefore
cannot fetch anything the registry does not hold, and every new upstream is a
`sources.json` row first, with its licence established and recorded
([CONTRIBUTING.md](../../../CONTRIBUTING.md), "A note on data and licences").

**A builder imports nothing the extract job does not install.** The job
installs `requirements-extract.txt` alone, while the pipeline suite's
environment holds every build dependency, so an import that only the build
jobs pin passes every test and fails the job. Borrowing one constant from a
fetcher brings that fetcher's imports with it: `export_weather_alerts.py`
imports shapely, so the NWS endpoint and its response check moved to
`lib/nws_alerts.py`. `tests/test_extract_layout.py` walks the extract's own
imports and fails on one with no pin.

**Raw tables are named `raw_<folder>__<key>`**, passed to dlt as `table_name=`
exactly as written. A real run keeps that name under both `snake_case` and
`sql_ci_v1`, but dlt's `normalize_table_identifier()` called on its own
collapses the `__` to `raw_nysdec_dec_lean_tos` (measured 2026-10-01, dlt
1.30.0), so no code here builds a table name by calling it. **A key may not
start with a digit**: a run normalizes the name as a path split on `__` and
escapes such a segment, so `raw_usgs__3dep_13_current` landed as
`raw_usgs___3dep_13_current` and the run check, counting the name as written,
refused the monthly lane for an empty table it had loaded (run 37058045092,
2026-10-02). `raw_table()` refuses such a key, and the layout test holds every
resource's table to dlt's own `normalize_path`.

## One extraction per upstream dataset

The maintainer, decision 34: *"Are we landing the same data, multiple times?
We shouldn't. Like for USFS, that should get landed as a 'base' layer (subset
of staging) Then each club can take that data and assign their portion."*

- **Each upstream dataset is extracted exactly once, in its steward's
  folder**: USFS's national trail layer in `usfs/trail_lines.py`, and nowhere
  else. A club whose portion lives in that layer writes no resource for it;
  its file is a dated note naming the resource it draws from (the `via` rule).
  The club's portion is assigned in dbt, in `int_<mart>__stewardship`, by
  ATC's club-section polygons, the club's `trails` list in `trail_orgs.json`,
  or a name or ID match ([the dbt skill](../dbt/SKILL.md)).
- **A republished copy is a `SAME_AS` note, never a resource.** Before
  writing a resource, check that the layer is not a copy of one another folder
  extracts: the same row count and edit dates, an ArcGIS Online view or twin of
  an on-prem layer, or an item whose description names the original. The
  coverage audit's examples, each measured 2026-10-01: DEC's ArcGIS Online
  twins of its on-prem layers (`DEC_Trails/1` holds the same 5,292 segments
  as `dil_trails/2`), DEC's 2025 `DEC_pointsinterest` copy, CDTC's views of
  NPS POIs, and CPW's three COTREX copies, of which the newest is extracted.
- **A `SAME_AS` note ages like a `NOT_AVAILABLE` note**: `confirmed`,
  `checked` and `recheck_after_days`, failed by the monthly ageing check and
  rechecked by a person, because a copy can stop being one. Once its publisher
  edits it apart from the original, it is an independent dataset and gets a
  resource of its own.
- **The layout test fails two resources that point at the same upstream URL
  or ArcGIS item id**, and a `SAME_AS` copy that some file also claims.
- **Post-load dedup is only for independent datasets of the same ground**,
  such as a club's own GPS line against USFS's line. Never load a copy
  so that dedup can remove it.

```python
@dataclass(frozen=True)
class SameAs:  # pipeline/extract/_contract.py (shape)
    original: str  # the sources.json key whose resource extracts the dataset
    copy: tuple[str, ...]  # the copy's URLs or ArcGIS item ids
    confirmed: date  # the day a person compared them
    checked: tuple[str, ...]  # what shows it is the same data
    recheck_after_days: int = RECHECK_AFTER_DAYS
```

## The `NOT_AVAILABLE` note

A note is a row of `pipeline/extract/not_available.toml`, named
`[<folder>.<type>]`. `discover()` reads each into the `NotAvailable` in
`_contract.py`, and the layout test holds its shape:

```toml
[nynjtc.elevation]
confirmed = 2026-10-01
summary = """
Nothing published (coverage audit 2026-10-01, batch b2_nynjtc).

USGS 3DEP (`_shared/`) covers this. …"""
checked = [
    "`hasZ:false` and `hasM:false` on `Long_Path_2023/0`, … The 76 AGOL items include no Image Service, …",
]
where = ["https://services7.arcgis.com/G1WTEJ6UVRUTvh9C/arcgis/rest/services", "https://nynjtc.org/"]
```

| field | rule |
|---|---|
| `confirmed` | the day a person looked, a TOML date (`2026-10-01`, unquoted). Never in the future, and never moved without looking again |
| `summary` | the prose a reader needs beside the fields: what the club publishes instead, why it is refused, which folder a type is drawn from |
| `checked` | what was looked at, written so somebody else can repeat it |
| `where` | the https URLs |
| `recheck_after_days` | default 180, `@unvalidated`: settled by how often a re-survey overturns a note that old. Written only where it differs |
| `terms` | the terms, **verbatim**, when the data exists and its terms refuse it |
| `reason` | what landing waits on (a `sources.json` row, a key, a permission), or why it is refused |

A field outside this list is refused where the file is read, so a misspelt
`terms` stops the run rather than dropping a refusal's quoted words.

**Claim only what you checked.** The note above restates the coverage
audit's NYNJTC × elevation row (batch b2). It records the ArcGIS root, the
ArcGIS Online search and the site's own pages from the list below, so the
clearinghouse, land-manager and data.gov items are still to work and write in.
Check the survey before writing any note: its ATC × elevation row found a
Z-enabled centerline (`ATX_Ratings/FeatureServer/9`), so ATC's elevation is
a resource once that layer has a `sources.json` row, not a note.

**Most notes were first drafted from the coverage audit's
`bcc70dd0:pipeline/reference/org_coverage.json`** (retired by decision 88, and
read now with `git show`), never from the batch files behind it: `checked` is
the row's evidence, the summary its note, and `where` the URLs the text
names, with each host-less ArcGIS service name resolved to a full URL by a
live `?f=json` read (2026-10-01). Text that ends in '…' was trimmed in that
file. The batch files (`b1`-`b7`, `c1`-`c21`, `p01`-`p10`, `q01`, `r01`) were
never committed and were never scrubbed: the JSON replaced every email
address, phone number, personal ArcGIS account and named private individual
with a description, and the files still hold them. Their text goes into a
note only after a person has read it. The twelve persistence-pass rows in the
23 registry providers' folders were read and carry their full seven-item
checklist; every other note keeps the trimmed, scrubbed copy. The 118 clubs
with no registry row keep it throughout: screened, their 109 persisted rows'
batch text held personal ArcGIS account names (an email-based account,
several individuals' handles), 146,504 characters too many to read with care.

**A GIS-shaped type is not given up early** (decision 21b; the maintainer:
*"Make sure for all of these orgs that you dont give up to easily. The GIS
info almost always is reusable."*). Before a note on `trail_lines`,
`points_of_interest`, `places`, `closures`, `warnings` or `elevation`, work
this list and write what you tried into `checked`:

- every ArcGIS REST root on the org's hosts, not only `/arcgis` (WDNR's DEM sat
  under `/arcgis_image`);
- ArcGIS Online search by org name, owner and orgid; Hub sites;
- the state GIS clearinghouse;
- the parent or partner agency's GIS: USFS, NPS, state parks, county, MPO;
- data.gov, CKAN, Socrata;
- GPX, KML or KMZ on the website; Google My Maps KML export; GeoPDF maps;
- for closures and warnings: conditions pages, RSS, WordPress categories and
  status APIs.

`pipeline/ORG_COVERAGE_SURVEY.md` §2 has the same checklist as the audit worked
it. The layout test checks a note's shape, never whether its searches were
done, so the list is a reviewer's check.

**Rechecking a note**: a monthly job is to fail a note past `confirmed +
recheck_after_days` (decision 14's check 3, not built yet:
`refresh-reference.yml` lists it under "NOT HERE YET"). That job is not
upstream of publish, so a stale podcast note never holds back this month's
water data. To clear a note, redo the search, then either rewrite `confirmed`
and `checked` in its row with what you found this time, or retire the row: write
the resource file `<folder>/<type>.py` and delete the row in the same commit.
The layout test fails while both exist. Whatever the note said that the
resource's reader still needs goes in the new file's docstring, in your own
words; git keeps the row.

## Four measured hazards, now rules

| Rule | Why (measured) |
|---|---|
| **1. Geometry carries a JSON hint:** `columns={"geometry": {"data_type": "json"}}` on every geometry resource | On defaults the A.T. centerline became 2,072,165 rows in 4 tables and reported `LOADED` (the 2026-09-09 spike). With the hint: 3,025 rows, round-tripped through `ST_GeomFromGeoJSON`. The column lands `JSON` in DuckDB and `VARCHAR` in the filesystem destination's Parquet (2026-10-01), so base models cast it first |
| **2. An unchanged upstream is left out of the run, never run empty.** Skip it with `with_resources()`; never yield nothing | Under `replace`, an empty yield took `closures` from 1 row to 0. A resource left out kept its rows and `_dlt_load_id` (2026-10-01) |
| **3. Telemetry off:** `RUNTIME__DLTHUB_TELEMETRY=false` in every job, `dlthub_telemetry = false` in `.dlt/config.toml` | On by default (`dlthub_telemetry` reads `True` in dlt 1.30.0, 2026-10-01), sending to `telemetry.scalevector.ai` from jobs holding R2 write keys. What it sends is `@unvalidated`; off makes that moot |
| **4. Change checks are ours, before dlt, and three-valued.** `lib/freshness_state.py`'s `FRESH` / `STALE` / `UNKNOWN`. Only `FRESH` skips; `UNKNOWN` fetches | A dlt cursor cannot tell "checked, nothing changed" from "nobody checked". `lib/freshness_state.py`: "THE FAILURE THAT MATTERS is a false 'fresh'" |

**Rule 2 has a second half: a failed load must not empty a table either.**
Under dlt's default `truncate-and-insert`, a load that fails empties every
`replace` table of the run or cuts it short, and the run check before the load
cannot see it (measured 2026-10-01). So:

- **Monthly lane, from phase 3:** the raw lake sets
  `replace_strategy = "insert-from-staging"`, and builds read the last
  snapshot the after-run check marked good.
- **Hourly lanes, and monthly before phase 3:** a build reads only files whose
  load_id is committed in `_dlt_loads` and equals the one `_extract_runs`
  recorded. The load_id comes from the **file name**, because a zero-row
  Parquet file has no `_dlt_load_id` value. The files are an explicit list,
  never a glob.
- **`append` only for `_extract_runs`.** An empty `append` makes no load
  package, so "the newest load on disk" kept serving lifted closures
  (measured).
- **A pending package is dropped before the run syncs.** A run that died
  between extract and commit leaves its package and its resource state in
  the working directory. Kept, the next run read that uncommitted marker and
  answered FRESH, and the run log's own `pipeline.run()` committed the dead
  package with no `_extract_runs` row (measured 2026-10-01). `_run.py` drops
  it, warns, then syncs, and refuses a load that commits more than one
  package. Runners start empty, so this bites a reused directory.
- **An allowed zero counts only with the upstream's own count, read in the
  same run**: ArcGIS `returnCountOnly=true`, Socrata `count(*)` under the
  entry's `where`, WordPress `X-WP-Total`, the slug count of ATC's
  trail-updates sitemap, the moderated query's own `count(*)` for OurHike's
  Postgres, an NWS `200` with no features. Without it the zero is `UNKNOWN`.
  **A count you make of what you parsed is not one**: a page whose layout
  moved parses to none exactly as an empty page does. So every reader kind
  declares `zero_proof` on its own class (`extract/_contract.py`'s
  `Resource.zero_proof`): the upstream's count it reads, in words, or `None`.
  The run check refuses a zero from a `None` kind whatever it recorded, and
  keeps the shrink floor on such a table where it may be empty.
  `tests/test_extract_zero_proofs.py` pins every kind's answer, so a new kind
  is refused until somebody writes it down.

**Rule 4 on a safety path: no check may answer `FRESH` while the data moved.**

- On-prem ArcGIS ETags hash the response body, so a service-metadata ETag
  never moves when the data does: USFS read `"1a7709d0"` on both 2026-09-02 and
  2026-10-01 (measured). Use the statistics fingerprint instead: `count`,
  `max(OID)`, `sum(Shape_Length)` and the maintained date. On an hourly or
  daily layer an unchanged fingerprint is FRESH only when that date is the one
  the layer's `editFieldsInfo.editDateField` names, since only editor
  tracking's date is promised to move on every edit; otherwise it is UNKNOWN
  and the layer is read every run (five layers, read 2026-10-09).
- `max(edit date)` alone cannot see a deleted row, and neither can a cursor
  (Reasoned: a deleted row has no edit date left to read).
- WordPress feed validators are site-wide (measured 2026-10-01), so they never
  decide `FRESH` for closures.
- An RSS window is not a list of current items: absence from it is never read
  as "lifted".
- A 304 never reaches dlt, where it raises `PipelineStepFailed` (measured by
  the 2026-09-09 spike). The conditional request is ours, and 304 means
  `FRESH`.

Each platform's check is in `pipeline/ELT.md`, "The skip-unchanged check, by
platform". **A refused run's marker does not survive it**: after
`abort_packages()` (measured as `drop_pending_packages()`, its alias, deprecated
in dlt 1.30.0) the old marker came back, and `sync_destination()`
restored it on a fresh pipeline directory (measured 2026-10-01 on DuckDB and a
local `file://` destination; R2 is `@unvalidated`). **But a load can advance
the stored marker without committing**: dlt 1.30.0's filesystem
`complete_load()` stores the state before it writes the `_dlt_loads` row, and
`get_stored_state()` restores the newest state file whether its load
committed or not (read in `filesystem.py`, reproduced in
`tests/test_extract_run.py`). **So a marker counts only beside the rows a
build reads**: `_run()` reads the marker of a table with no logged, committed
load as no marker, and turns a FRESH verdict into UNKNOWN when that load's
files are gone, replaced by a later load (`served_files_intact()`). The
monthly lane's second run committed and then refused before its log, and its
third run answered 53 resources FRESH whose rows no build could read
(refresh-reference.yml, 37070628933 and 37081046157, 2026-10-03).

**The rest of `.dlt` configuration**, each with its measurement in
`pipeline/ELT.md`, "dlt configuration requirements":

- `naming = "sql_ci_v1"`, plus a map step flattening `properties`, so
  `GlobalID` lands as `globalid` (16 staging models read that name).
- Column hints from each ArcGIS layer's `fields`, so an all-null column is
  still created; `esriFieldTypeDate` lands `bigint` and base models convert it.
- Schema contract `{"columns": "evolve", "data_type": "freeze"}` on ArcGIS.
- **ArcGIS pages come from `lib/arcgis.py`'s `iter_layer_pages()`, never a
  second pager.** It steps by rows returned, stops on an empty page, halves a
  refused page and refuses a server that repeats a page. dlt's
  `OffsetPaginator` steps by `limit`: against a server capping pages at 4,
  `limit=10` loaded 4 of 10 rows (measured 2026-10-01). A later kind that does
  use `rest_api` sets `value_step = len(page)` and `maximum_offset`.
- **One retrying session per caller**, never a global `RUNTIME__REQUEST_*`:
  `extract/_kinds.py`'s `session()` (named by `lib/user_agent.py`) passed to
  `lib/http_retry.py`, or `RESTClient(session=RetryingSession(posture))` for a
  `rest_api` kind. Retry postures differ on purpose
  (`lib/http_retry.py`; **#536 — One transient 504 from USGS throws away an
  entire publish**).
- `_loaded_at` (naive UTC) is stamped in the map step **only when a resource
  runs**, so a `FRESH` table keeps its old stamp. So dbt's freshness on a
  source whose check can answer `FRESH` reads the run log, never
  `_loaded_at` (the dbt skill's trap table, decision 100).
- **One dlt schema per store**: every `pipeline.extract()` and `pipeline.run()`
  passes `schema=store_schema(pipeline)`. dlt puts its own state in the
  default schema's package, so a second schema means a second package and
  the "one load expected" refusal. A bare resource such as the run log
  otherwise takes a schema named after the pipeline. The monthly lane's
  refused first run and then "2 committed" on its second
  (refresh-reference.yml, 37070628933, 2026-10-02) reproduce that way in
  `tests/test_extract_run.py`. The R2 store's own schema list was not read.
- dbt runs as its own CLI step, never through `dlt.dbt`, whose default is
  `dbt>=1.7,<2` while this project runs `dbt` 2.0.6 (decision 32).

**A field its publisher retyped is refused on every run until one table is
reset.** `data_type: freeze` compares against the store's dlt schema, which
`replace` never resets, so the layer logs `refused` every run, its last
committed table stands, and dbt's source freshness turns it red. First read
the refusal (`schema contract: …` in the run summary) beside the layer's own
metadata, and reset only when the new type is the publisher's choice, never
to make a broken answer load. Then, while that lane's own job is not running,
`python -m extract._run --lane <lane or leg> --raw-bucket our-hike-raw --only
<raw table> --reset`: it reads that table whatever its check says and lands it
with `refresh="drop_resources"`, which drops the table and its state and
erases its schema history inside the same load package, so a reset the run
check refuses drops nothing (`tests/test_extract_conditions_legs.py`). It
refuses anything but exactly one `--only`. A base model casting the field may
need changing in the same pull request.

## Load every club, gate publication downstream

The maintainer, round 5: *"We should just load ALL the clubs now and handle any
deduplication after the extract-load."*

- **`trail_orgs.json`'s `load` column stops gating extraction and keeps gating
  publication.** A resource never filters on a licence. `may_publish` is
  decided per layer in dbt (`int_sources__publication`): a registered key
  publishes on its `sources.json` `reaches_hikers` and `licence_basis`, and
  `load` decides for what has no `sources.json` row yet.
- **The only filters before dbt are the ones a request already carries**:
  Socrata `where` clauses, the conditions database's moderation predicates,
  ATC's Campsite Sustainability Index read for official sites only, and an
  agency's own status field on a closure or status layer (never a date or a
  name; `pipeline/ELT.md`, "Status layers are often stale").
- **Deduplication is dbt's**, in intermediates, after every club has loaded.
- **Public GIS is presumed reusable** (decision 21a): a layer an org publishes
  itself, anonymously, over a public endpoint gets `licence_basis: public_gis`.
  Decision 37 extends that to layers whose own words say "internal use", "not
  for distribution" or "all rights reserved", against those words. DEC's and
  OPRHP's clearinghouse datasets are the maintainer's own rulings (decisions 20
  and 22), and so are the licence batch's other answers: profit- and
  sale-limited layers publish as non-commercial use (36), and conditions
  travel with their layer, a condition that cannot be met holding it (38).
  **Whatever a layer's words say, extract it and quote them verbatim** on its
  `sources.json` row; dbt decides publication. Restrictive text that no
  decision names keeps `may_publish` false and goes to the maintainer.

**People never ship, and are never loaded.** A resource excludes person fields
in its requested field list, so they never reach the raw store, whatever the
licence. The first denylist entries are Forest Ranger Contact's `RANGER`,
`PHONE_CELL`, `PHONE_ALT`, `EMAIL`, `SUPERVISOR` and `SUPERVIS_1`; a pytest
refuses any resource whose hints or field list name one. Some tables are never
extracted at all, among them OPRHP's Palisades Bear Program results (patron
emails, phones and addresses), Mohonk's volunteer Survey123 table and the
finisher and member rosters the coverage audit found. The full list is in
`pipeline/ELT.md`, "Club by club".

## Terms are never routed around

- **A refusal is a note, not a puzzle.** The four `refuse` rows and every
  permission-gated source get dated notes quoting the terms in `terms`, and
  load only on written permission (the poll: *"Note now, load on
  permission"*). Nothing is fetched past what the coverage audit already read.
- **The maintainer sends every permission request.** No session contacts an
  org. Each reply is quoted, with its date, in the club's licence fields.
- **robots.txt, a 403 or a login means `UNKNOWN`, and stops there.**
- **Every request sends `lib/user_agent.py`'s `USER_AGENT`**
  (`CONTACTABLE_USER_AGENT` for Wikimedia), on every host. It names the
  project and links to it rather than impersonating a browser, so an operator
  can see who is asking from one line of their log. ATC's host refuses the
  default `python-requests` agent (403) and accepts this one (200, measured
  2026-08-24, in that module's docstring): its block was on an anonymous
  agent, and saying who we are is not getting around it.
- **Never imitate a browser** (decision 39, the maintainer's poll of
  2026-10-01). Never send a browser's or another client's User-Agent, not even
  for a host that serves one: `tnstateparks.com` and LSHT's ClubExpress files
  refuse our agent, so they hold until the org answers. A host that refuses
  our own named agent has refused us: record it as `UNKNOWN` and report it in
  the pull request; do not try another agent.
- **A club's own public ArcGIS layer counts as published, whatever its
  website's waiver says** (decision 39, "Allow ArcGIS copies, else ask"). So
  ONDA's public `ODT Tracks` layer is extracted, while the GPX, CalTopo maps
  and Databook behind its waiver are not fetched. Whether it may publish
  while `onda` is a `refuse` row is the maintainer's open question, so its
  `may_publish` stays false. Other no-automation terms and waivers mean ask:
  a dated note quoting them, and a request the maintainer sends. ATC's
  trail-updates scrape stays as it is, on **#458 — Confirm with the ATC what
  may be republished from their Trail Updates**.
- **Honour `Crawl-delay`.** Two of today's fetchers do not: `lib/atc_scrape.py`
  sends ATC's listing pages with no throttle against its `Crawl-delay: 10`, and
  `fetch_hikefinder.py` sends 2 requests a second against Hike Finder's
  `Crawl-delay: 10` (read 2026-10-01). A dlt resource replacing either waits
  the delay, which puts Hike Finder's 386 requests at 64 minutes or more
  (Reasoned), on the monthly lane where that fits. ATC's closures move to its
  trail-updates sitemap: 1 request of 3,411 bytes instead of about 350 a day.
- **An agency's copy of a steward's gated route is the maintainer's call**:
  Ohio DNR's Buckeye line, OPRD's Oregon Desert Trail and Blue Mountains Trail.
  So are Facebook-only channels and members-only pages. Do not write the
  extractor that would take the decision for them.

## The three data checks

| check | when | what it holds |
|---|---|---|
| **1. Layout**, `pipeline/tests/test_extract_layout.py` | every pull request | every managing club answers each of the ten types exactly once, by a resource file or a `not_available.toml` row, never both; club folders only for managing slugs, holding only resource files; every row a share naming a sibling with a resource file, or a well-formed note (`confirmed` not in the future, non-empty `checked` and `where`, `recheck_after_days > 0`); `SAME_AS` notes whose `original` is claimed; no two resources pointing at the same upstream URL or ArcGIS item id; one catalogue row per managing club; a `stg_<club>__<type>` for exactly the available types; every `sources.json` key claimed once and every claim resolving; no table on two lanes. **A note's shape, never its age**, so the calendar cannot turn an unrelated pull request red |
| **2. Run check**, in `_run.py` | after every dlt run | *before the load*: each available resource loaded or recorded `FRESH`; `rows > 0` unless the type may be empty and the upstream's own count proves the zero; rows ≥ 0.5 × the last loaded count, except closures and warnings, which have no floor (the floors are `@unvalidated`; six monthly runs settle them); each club's catalogue row produces exactly one row. A failure drops the package, so nothing loads and no marker advances. *After the load*: `committed()` checks the load is in `_dlt_loads`, the rows on disk equal the rows normalized, and every count proof holds; a failure records `unverified` and the build refuses |
| **3. Note ageing** | the monthly run, not upstream of publish | a `NOT_AVAILABLE` or `SAME_AS` note past `confirmed + recheck_after_days` fails, and a person rechecks it |

Check 2 also reaches dbt as source tests on `raw._extract_runs`, so a build
cannot quietly consume a run that was refused: one copy at `error` for closures
and warnings, one at `warn` for the rest.

**A resource a leg refuses on its own warns, and turns red in dbt's source
freshness** (decision 100, the maintainer's poll of 2026-10-07: "Red after
24h. But this should be Red in the data source freshness feature of dbt. Not
blocking a datasource pipeline"). The leg leaves it out, its last committed
table stands, its run log row says `refused`, and the run exits 3, which
extract-notices.yml and publish-conditions.yml's dbt path record and warn on,
the summary naming the source and why. publish-conditions.yml then runs `dbt
source freshness` after it has published, and a notice source turns red once
it has gone 24 hours (48 for a daily one, 2 for NWS's alerts, decision 101)
without a `loaded` or `skipped` row: `macros/last_read_or_confirmed_at.sql`, the same two outcomes `due()`
counts as a check. OurHike's own Postgres rows still stop the whole leg, red
at once (`stops_the_leg()`). The monthly lane's `refused` job in
refresh-reference.yml still fails its run: decision 100 named the notices.

## Adding a club

1. **A reviewed `trail_orgs.json` row**, because the folder name is its slug.
   A candidate from `pipeline/reference/trail_candidates.json` needs its row
   first. The catalogue came from **#1543 — 165 trail organizations exist and
   the registry knows 14, with no way to load the rest that does not cost one
   pull request each**; `features/ORG_BULK_LOAD.md` explains its `load`
   verdicts.
2. **A `sources.json` row per upstream**, with the licence quoted and its
   basis recorded, before any resource names it.
3. **Its answers for the ten types.** A type it publishes is a resource file,
   `pipeline/extract/<folder>/<type>.py`, built from `_kinds.py` (or `SAME_AS`
   notes); every other type is a row of `not_available.toml`, a share or a
   note. Its catalogue row needs nothing: `discover()` makes it from the
   `trail_orgs.json` row. Never a second resource for a dataset another folder
   already extracts. Start from the club's rows in
   `pipeline/ORG_COVERAGE_SURVEY.md`, and work the discovery list above before
   any note on a GIS-shaped type.
4. **Exclude person fields** in every field list, and check them against the
   denylist.
5. **Fixtures**: `make_dbt_fixtures.py` emits the upstream's answers (layer
   metadata with real `fields` and `maxRecordCount`, query pages, Socrata
   pages, WordPress posts). Its "Nothing here is invented" rule extends to the
   `fields` lists: copy them from the live layer.
6. **Tests** under the socket guard (below).
7. **dbt staging** for every available type: [the dbt skill](../dbt/SKILL.md),
   "Adding a club's staging models".
8. **Run** the layout test, `python -m extract._run --pipeline all --fixtures`,
   and the dbt job.
9. **In the pull request**: the new-data review report decision 31 asks for —
   counts per org × type × mart, each layer's licence basis and `may_publish`,
   and every new closure, warning, water and shelter source listed for review —
   plus the `## Data pipelines` section from `scripts/pipelines.sh`.

## Tests under the socket guard

Every extract test runs under `pipeline/tests/conftest.py`'s autouse
`no_outside_network` guard, which raises on any socket connection to a
non-loopback address. `requests_mock` answers instead: it intercepts at the
adapter layer, above sockets. The 2026-09-09 spike measured dlt's `rest_api`
source clean under a verbatim copy of that guard, with zero non-loopback
connection attempts, because `rest_api` is built on `requests`.

- **Every pipeline a test builds writes under `tmp_path`.** Pass
  `pipelines_dir=str(tmp_path)` and a `tmp_path` filesystem or DuckDB
  destination. dlt's default working directory is outside the test
  (`/var/dlt/pipelines` as root in this sandbox, measured 2026-10-01 on dlt
  1.30.0), so state from one test would reach the next (Reasoned). And
  `dlt.pipeline(destination="duckdb")` with no path writes into the working
  directory: the 2026-09-09 spike's first run dropped 117 MB of `.duckdb`
  files into `pipeline/`.
- **The cases worth a test, because each was measured going wrong**: a server whose
  pages are smaller than `limit` (all rows must load); an unchanged upstream
  (the resource is left out and its rows survive); an injected load failure
  (the previous rows survive, or the build refuses); a 304 (`FRESH`, and dlt is
  never called); a geometry round-trip through `ST_GeomFromGeoJSON`; telemetry
  off in `.dlt/config.toml`.
- Name each test for the failure it guards, by the plain-language skill's
  2 a.m. test: `test_a_page_smaller_than_limit_still_loads_every_row`, not
  `test_paginator`.

## A field that should never have loaded

Extraction is what makes a purge unnecessary. If a person field is loaded
anyway, fix the resource first so it never loads again, then remove the value
everywhere it went. `pipeline/ELT.md`, "Purging a field that should never have
loaded", has the measurement behind each step: a sentinel value was searched for
in every byte after each one.

**On a DuckLake lake**, in this order:

1. Fix the dlt resource.
2. Rewrite every table that held it without the field, with
   `CREATE OR REPLACE … SELECT * EXCLUDE (<field>)` or
   `ducklake_rewrite_data_files`. **Do not flush inlined data first**: the
   flush wrote a deleted inlined row into a new live Parquet file.
3. `ducklake_expire_snapshots(older_than => now())`. **This destroys all time
   travel, including every pinned `raw_run`.**
4. `ducklake_cleanup_old_files(cleanup_all => true)` and
   `ducklake_delete_orphaned_files(cleanup_all => true)`.
5. `COPY FROM DATABASE` into a new catalog file, and replace the catalog
   object: the old file's free pages still held the value.

**On the plain-file tiers** (Reasoned from those measurements): the next
`replace` deletes the table's old file; delete by hand every as-sent object in
`current/` and `snapshots/` that holds the field, since `snapshots/` is
write-once; and **delete, never edit**, every `steps/raw_inputs/` copy, stored
warehouse and `browse/ourhike.duckdb` built from that table, because a DuckDB
file's free pages keep a dropped value.

Either way the purge removes every pinned `raw_run`, so the next promotion
needs a fresh UA build. Say in the pull request which field loaded, for how
long, and where it reached; the maintainer decides who else needs telling.
