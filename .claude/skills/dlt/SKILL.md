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
5 more, with the daily rule in `_run.py`. 4 keys remain on
`NOT_YET_EXTRACTED`. Not built yet: `_shared/`, `gatc/` and the club-PDF
kind, the other clubs, the as-sent copy, the raw lake, fixture mode, and any
run against R2. Every other
source still comes from the old fetchers (`fetch_*.py`, `lib/arcgis.py`,
`lib/socrata.py`) and `load_raw.py`; a change to one of those follows its own
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

Three terms are used throughout. **The raw store** is the private R2 bucket
`R2_RAW_BUCKET`, which no phone reads. **The raw lake** is the DuckLake form
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
2. **The folder**: eleven files, each a resource, a share or a dated note.
3. **The traps**: the four hazards below, checked line by line.
4. **The tests**, under the socket guard.
5. **The dbt staging** for every available type ([the dbt skill](../dbt/SKILL.md)).
6. **The pull request**: the new-data review report and `scripts/pipelines.sh`.

## The folder contract

```
pipeline/
  .dlt/config.toml   # committed: telemetry off, naming, file format. Never credentials
  extract/
    _contract.py     # TYPES, NotAvailable, discover(), the lane and claim maps
    _kinds.py        # one builder per source kind
    _run.py          # change checks -> extract -> normalize -> run check -> load
    _warehouse.py    # raw store -> warehouse.duckdb `raw` (load_raw.py's successor)
    _shared/         # free-form: national services, aggregators, OurHike's own data, not_clubs.py
    atc/  nysdec/  … # one folder per managing club, exactly 11 files each
```

**Never `pipeline/dlt/`.** Scripts run from `pipeline/`, which is first on
`sys.path`, so a `dlt/` folder there would shadow `import dlt` (decision 12).

**One folder per managing club** (decision 18): 145 from `trail_orgs.json` at
23fca25, which is its 173 rows minus 12 `national_umbrella`, 13 `route_only`
and 3 `aggregator`. Umbrellas and route-only trails get one dated line each in
`_shared/not_clubs.py`. Aggregators (`osm`, `outerspatial`, `avenza`) live in
`_shared/`. Anything real an umbrella publishes, such as a podcast, goes in
`_shared/` too.

**The folder name is `trail_orgs.json`'s `slug` with `-` written `_`**, because
Python cannot import a hyphen. No slug has an underscore, so the mapping
reverses exactly (measured 2026-10-01). There is no `__init__.py`, so the file
count is exact.

**Exactly these eleven files**, the same in every club folder (decision 13):

| file | feeds | lane |
|---|---|---|
| `org.py` | `sources` (never a note: `RESOURCES = [catalogue_row()]`) | monthly |
| `trail_lines.py` | `trail_lines`, `trail_network`, elevation calibration | monthly |
| `points_of_interest.py` | `points_of_interest` | monthly |
| `elevation.py` | `elevation` (3DEP itself is `_shared/usgs/`) | monthly |
| `closures.py` · `warnings.py` | `closures` · `warnings` | **hourly** |
| `places.py` | `places` | monthly |
| `suggested_hikes.py` | `suggested_hikes` | monthly |
| `podcasts.py` · `challenges.py` | `podcasts` · `challenges` | monthly |
| `photos.py` | photo manifest rows, never pixels | monthly |

`trail_network` and `sources` have no file: dbt derives them. The lane
belongs to the type. Each type file defines exactly one of:

- **`CLAIMS` + `RESOURCES`**: the `sources.json` keys it owns, and a `Resource`
  for each.
- **`SHARES = "<type>"`**: a sibling file's resource also feeds this type. One
  upstream is one resource and one raw table even when it feeds two types, so
  `atc/warnings.py` holds `SHARES = "closures"` and no `CLAIMS`.
- **`NOT_AVAILABLE`**: a dated note (below).
- **`SAME_AS`**: a tuple of `SameAs` notes, when a republished copy of another
  resource's dataset is all the org publishes for this type. A `CLAIMS` file
  may carry `SAME_AS` notes too, for the copies it does not extract.

**A builder takes a `sources.json` key, never a URL.** A club file therefore
cannot fetch anything the registry does not hold, and every new upstream is a
`sources.json` row first, with its licence established and recorded
([CONTRIBUTING.md](../../../CONTRIBUTING.md), "A note on data and licences").

**Raw tables are named `raw_<folder>__<key>`**, passed to dlt as `table_name=`
exactly as written. A real run keeps that name under both `snake_case` and
`sql_ci_v1`, but dlt's `normalize_table_identifier()` called on its own
collapses the `__` to `raw_nysdec_dec_lean_tos` (measured 2026-10-01, dlt
1.30.0), so no code here builds a table name by calling it.

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

```python
# pipeline/extract/nynjtc/elevation.py
"""NYNJTC publishes no elevation product: its trails' profiles are 3DEP (_shared/usgs/)
along the lines nynjtc/trail_lines.py loads."""
NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("the 27 FeatureServers on NYNJTC's ArcGIS root: hasZ false on Long_Path_2023/0, "
             "NYNJTC_HighlandsTrail2021sections/0 and Long_Path_Shawangunk_Ridge_Trail/0; Z only on "
             "Points (0 rows), roundrock (a KMZ import) and 26 trailhead points",
             "ArcGIS Online, orgid:G1WTEJ6UVRUTvh9C: 76 public items, none an Image Service, "
             "elevation or DEM item",
             "nynjtc.org's WordPress search for 'elevation profile' and 'elevation gain': "
             "book sales and prose only"),
    where=("https://services7.arcgis.com/G1WTEJ6UVRUTvh9C/arcgis/rest/services",
           "https://www.arcgis.com/sharing/rest/search?q=orgid:G1WTEJ6UVRUTvh9C",
           "https://www.nynjtc.org/wp-json/wp/v2/search"),
)
```

| field | rule |
|---|---|
| `confirmed` | the day a person looked. Never in the future, and never moved without looking again |
| `checked` | what was looked at, written so somebody else can repeat it |
| `where` | the URLs |
| `recheck_after_days` | default 180, `@unvalidated`: settled by how often a re-survey overturns a note that old |
| `terms` | the terms, **verbatim**, when the data exists and its terms refuse it |

**Claim only what you checked.** The note above restates the coverage
audit's NYNJTC × elevation row (batch b2, upheld by its skeptic pass, measured
2026-10-01). It records the ArcGIS root, the ArcGIS Online search and the
site's own files from the list below, so it is committed only after the
clearinghouse, land-manager and data.gov items are worked and written in.
Check the survey before writing any note: its ATC × elevation row found a
Z-enabled centerline (`ATX_Ratings/FeatureServer/9`), so `atc/elevation.py` is
a resource once that layer has a `sources.json` row, not a note.

**A note drafted from the coverage audit restates `reference/org_coverage.json`,
never the batch files behind it.** Stage 2b's 183 notes were drafted that way:
`checked` is the row's evidence, the docstring its note, and `where` the URLs
the text names, with each host-less ArcGIS service name resolved to a full URL
by a live `?f=json` read (2026-10-01). The batch files (`b1`-`b7`, `c1`-`c21`,
`p01`-`p10`, `q01`, `r01`) were never committed and were never scrubbed: the
JSON replaced every email address, phone number, personal ArcGIS account and
named private individual with a description, and the files still hold them.
Their text goes into a note only after a person has read it. The ten
persistence-pass rows in stage 2b were read and carry their full seven-item
checklist; every other note keeps the trimmed, scrubbed copy, and says so in
its last line.

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

**Rechecking a note**: a monthly job fails a note past `confirmed +
recheck_after_days`. That job is not upstream of publish, so a stale podcast
note never holds back this month's water data. To clear it, redo the search,
then either replace the note with a resource or rewrite `confirmed` and
`checked` with what you found this time.

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
- **An allowed zero counts only with the upstream's own count, read in the
  same run**: ArcGIS `returnCountOnly=true`, Socrata `count(*)` under the
  entry's `where`, WordPress `X-WP-Total`, the slug count of ATC's
  trail-updates sitemap, the moderated query's own `count(*)` for OurHike's
  Postgres, an NWS `200` with no features. Without it the zero is `UNKNOWN`.

**Rule 4 on a safety path: no check may answer `FRESH` while the data moved.**

- On-prem ArcGIS ETags hash the response body, so a service-metadata ETag
  never moves when the data does: USFS read `"1a7709d0"` on both 2026-09-02 and
  2026-10-01 (measured). Use the statistics fingerprint instead: `count`,
  `max(OID)`, `sum(Shape_Length)` and the maintained date.
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
platform". **A marker advances only when a load commits**: after
`drop_pending_packages()` the old marker came back, and `sync_destination()`
restored it on a fresh pipeline directory (measured 2026-10-01 on DuckDB and a
local `file://` destination; R2 is `@unvalidated`).

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
  runs**, so a `FRESH` table keeps its old stamp.
- dbt runs as its own CLI step, never through `dlt.dbt`, whose default is
  `dbt>=1.7,<2` while this project runs `dbt` 2.0.6 (decision 32).

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
| **1. Layout**, `pipeline/tests/test_extract_layout.py` | every pull request | club folders equal the managing slugs; exactly the 11 files; each a resource, a share naming a type that has one, a well-formed note (`confirmed` not in the future, non-empty `checked` and `where`, `recheck_after_days > 0`), or `SAME_AS` notes whose `original` is claimed; no two resources pointing at the same upstream URL or ArcGIS item id; `org.py` never a note; a `stg_<club>__<type>` for exactly the available types; every `sources.json` key claimed once and every claim resolving; no table on two lanes. **A note's shape, never its age**, so the calendar cannot turn an unrelated pull request red |
| **2. Run check**, in `_run.py` | after every dlt run | *before the load*: each available resource loaded or recorded `FRESH`; `rows > 0` unless the type may be empty and the upstream's own count proves the zero; rows ≥ 0.5 × the last loaded count, except closures and warnings, which have no floor (the floors are `@unvalidated`; six monthly runs settle them); `org.py` produces exactly one row. A failure drops the package, so nothing loads and no marker advances. *After the load*: `committed()` checks the load is in `_dlt_loads`, the rows on disk equal the rows normalized, and every count proof holds; a failure records `unverified` and the build refuses |
| **3. Note ageing** | the monthly run, not upstream of publish | a `NOT_AVAILABLE` or `SAME_AS` note past `confirmed + recheck_after_days` fails, and a person rechecks it |

Check 2 also reaches dbt as source tests on `raw._extract_runs`, so a build
cannot quietly consume a run that was refused: one copy at `error` for closures
and warnings, one at `warn` for the rest.

## Adding a club

1. **A reviewed `trail_orgs.json` row**, because the folder name is its slug.
   A candidate from `pipeline/reference/trail_candidates.json` needs its row
   first. The catalogue came from **#1543 — 165 trail organizations exist and
   the registry knows 14, with no way to load the rest that does not cost one
   pull request each**; `features/ORG_BULK_LOAD.md` explains its `load`
   verdicts.
2. **A `sources.json` row per upstream**, with the licence quoted and its
   basis recorded, before any resource names it.
3. **`pipeline/extract/<folder>/` with the eleven files.** `org.py` is
   `RESOURCES = [catalogue_row()]`. Each other file is a resource built from
   `_kinds.py`, a `SHARES`, a note, or `SAME_AS` notes. Never a second
   resource for a dataset another folder already extracts. Start from the club's rows in
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
