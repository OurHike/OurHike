---
name: dlt
description: Work on the extract-and-load layer in pipeline/extract/ - the dlt resources that land every org's and every shared source's data in the private raw store. Use when adding an org, adding or changing a resource, writing or rechecking a NOT_AVAILABLE or SAME_AS note, touching .dlt/config.toml, writing an extract test, or when a dlt run check refuses a load. Covers the folder contract, one extraction per upstream dataset, the note format, the four measured hazards as rules, the three data checks, loading every org while gating publication downstream, the rule that terms are never routed around, how to add an org, testing under the socket guard, the purge for a field that should never have loaded, and why dltHub's AI harness is not installed.
user-invocable: true
---

# dlt in this repository

`pipeline/ELT.md`, "How data flows" and "The data checks", is the design. This file is the order of work and the traps. [CLAUDE.md](../../../CLAUDE.md) wins over both.

`pipeline/extract/` holds the readers (`_kinds.py` and the `_*.py` reader modules), the contract (`_contract.py`), the runner (`_run.py`), the warehouse loader (`_warehouse.py`), fixture mode (`_fixtures.py`), `_shared/` for national services and OurHike's own data, and `not_available.toml`, every org × type that publishes nothing loadable. `pipeline/.dlt/config.toml` holds the committed configuration, never credentials. The monthly lane, the hourly conditions legs and the notices job all run it against R2. The release build (`publish-vector-data.yml`) still reads its sources through the old `fetch_*.py` fetchers; a change to one of those follows its own docstring and tests.

dlt replaced a written decision not to use it, **#1294 — Evaluated and declined: dlt for the fetch layer, and a weekly cadence for non-alert data**. The hazards that evaluation measured come back below as rules, most of them from **PR #1363 — Port the ArcGIS fetch to dlt and count it, instead of estimating what it replaces** (a spike closed unmerged on 2026-09-09, "the 2026-09-09 spike" below).

Three terms. **The raw store** is the private R2 bucket `our-hike-raw` (`R2_RAW_BUCKET`), under `raw/`, every source alike; the step cache shares it under `steps/`; no phone reads it. **A lane** is the scheduled job that reads a resource, set by its `meta.cadence`: closures, warnings, NWS alerts, the drought feed and OurHike's own Postgres rows are hourly; NYNJTC's alert taxonomy terms are daily; nothing is weekly; everything else is monthly. **A leg** is one environment's half of an hourly job (`conditions_production`, `conditions_ua`, `notices_production`, `notices_ua`).

## Why there is no dlt plugin

- **dltHub's AI Harness (`dlt-hub/dlthub-ai-harness`) is not installed**, for a session either. Its licence permits use "solely in connection with dltHub Services under a governing Agreement", and excludes generating pipelines "for deployment on a third-party runtime platform". OurHike holds no such agreement and runs on GitHub Actions.
- **`dlt-mcp` is not installed** either.
- **dlt itself is Apache-2.0** and pinned in `requirements-extract.txt`. For general questions, dlt's documentation at dlthub.com/docs is the reference.

## The order of work

1. **Registry rows first**: a `pipeline/reference/trail_orgs.json` row for the org, and a `pipeline/sources.json` row for every upstream that no other org already extracts ([below](#one-extraction-per-upstream-dataset)).
2. **The org's answers**: a resource for each type it publishes, and a row of `not_available.toml` (a share or a dated note) for every other type.
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
  resource's dataset is all the org publishes for this type. A claimed key it
  read once and may not read again is `KEPT` instead, never both: a `Kept` in
  `_contract.py` holding a dated note that quotes the refusal in `terms`. No
  lane reads it, and builds and pins go on reading its last committed table,
  so only the maintainer may rule a key kept (TIGER's states, open question 16).
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

- **Each upstream dataset is extracted exactly once, under its steward**: USFS's national trail layer is read once, as USFS's. An org whose share lives in that layer writes no resource for it; its answer is a dated note naming the resource it draws from (the `via` rule). Its share is assigned in dbt, in `int_<mart>__stewardship`, by ATC's club-section polygons, the org's `trails` list in `trail_orgs.json`, or a name or id match ([the dbt skill](../dbt/SKILL.md)).
- **A republished copy is a `SAME_AS` note, never a resource.** Before writing a resource, check the layer is not a copy of one another org extracts: the same row count and edit dates, an ArcGIS Online view or twin of an on-prem layer, or an item whose description names the original. DEC's ArcGIS Online `DEC_Trails/1` holds the same 5,292 segments as its on-prem `dil_trails/2` (measured 2026-10-01), so only one is read.
- **A `SAME_AS` note ages like a `NOT_AVAILABLE` note**, because a copy can stop being one: once its publisher edits it apart from the original, it is an independent dataset and gets a resource of its own.
- **The layout test fails two resources that point at the same upstream URL or ArcGIS item id**, and a `SAME_AS` copy that some resource also claims.
- **Post-load dedupe is only for independent datasets of the same ground**, such as an org's own GPS line against USFS's. Never load a copy so that dedupe can remove it.

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

A note is a row of `pipeline/extract/not_available.toml`, named `[<folder>.<type>]`. `discover()` reads each into `_contract.py`'s `NotAvailable`, and the layout test holds its shape:

```toml
[nynjtc.elevation]
confirmed = 2026-10-01
summary = """
Nothing published. USGS 3DEP (`_shared/`) covers this. …"""
checked = [
    "`hasZ:false` and `hasM:false` on `Long_Path_2023/0`, … The 76 AGOL items include no Image Service, …",
]
where = ["https://services7.arcgis.com/G1WTEJ6UVRUTvh9C/arcgis/rest/services", "https://nynjtc.org/"]
```

| field | rule |
|---|---|
| `confirmed` | the day a person looked, a TOML date. Never in the future, and never moved without looking again |
| `summary` | what a reader needs beside the fields: what the org publishes instead, why it is refused, which org a type is drawn from |
| `checked` | what was looked at, written so somebody else can repeat it |
| `where` | the https URLs |
| `recheck_after_days` | default 180, `@unvalidated`: settled by how often a re-survey overturns a note that old. Written only where it differs |
| `terms` | the terms, **verbatim**, when the data exists and its terms refuse it |
| `reason` | what landing waits on (a `sources.json` row, a key, a permission), or why it is refused |

A field outside this list is refused where the file is read, so a misspelt `terms` stops the run rather than dropping a refusal's quoted words.

**Claim only what you checked**, and check `pipeline/ORG_COVERAGE_SURVEY.md` before writing a note: its ATC × elevation row found a Z-enabled centerline, so ATC's elevation is a resource once that layer is registered, not a note. Some notes were first drafted from the survey's scrubbed JSON (`git show bcc70dd0:pipeline/reference/org_coverage.json`); the survey's batch files were never committed or scrubbed of personal details, so their text goes into a note only after a person has read it.

**A GIS-shaped type is not given up early.** GIS data is almost always published somewhere reusable. Before a note on `trail_lines`, `points_of_interest`, `places`, `closures`, `warnings` or `elevation`, work this list and write what you tried into `checked`:

- every ArcGIS REST root on the org's hosts, not only `/arcgis` (WDNR's DEM sat under `/arcgis_image`);
- ArcGIS Online search by org name, owner and orgid; Hub sites;
- the state GIS clearinghouse;
- the parent or partner agency's GIS: USFS, NPS, state parks, county, MPO;
- data.gov, CKAN, Socrata;
- GPX, KML or KMZ on the website; Google My Maps KML export; GeoPDF maps;
- for closures and warnings: conditions pages, RSS, WordPress categories and status APIs.

The layout test checks a note's shape, never whether its searches were done, so the list is a reviewer's check.

**Rechecking a note.** A monthly job fails a note past `confirmed + recheck_after_days`; it is not upstream of any publish, so a stale podcast note never holds back this month's water data. To clear a note, redo the search, then either rewrite `confirmed` and `checked` with what you found, or retire the row and register the resource in the same commit. The layout test fails while both exist.

## Four measured hazards, now rules

| Rule | Why (measured) |
|---|---|
| **Geometry carries a JSON hint:** `columns={"geometry": {"data_type": "json"}}` on every geometry resource | On defaults the A.T. centerline's 3,025 features became 2,072,165 rows in 4 tables and still reported `LOADED` (the 2026-09-09 spike). The column lands `JSON` in DuckDB and `VARCHAR` in Parquet, so base models cast it first. Unhinted, a geometry null on every row of a first load lands no column at all; the layout test holds every reader kind to the hint (`YIELDS_GEOMETRY`) |
| **An unchanged upstream is left out of the run, never run empty.** Skip it with `with_resources()`; never yield nothing | Under `replace`, an empty yield took `closures` from 1 row to 0. A resource left out keeps its rows (2026-10-01) |
| **Telemetry off:** `RUNTIME__DLTHUB_TELEMETRY=false` in every job, `dlthub_telemetry = false` in `.dlt/config.toml` | On by default, sending to `telemetry.scalevector.ai` from jobs holding R2 write keys |
| **Change checks are ours, before dlt, and three-valued:** `lib/freshness_state.py`'s `FRESH` / `STALE` / `UNKNOWN`. Only `FRESH` skips; `UNKNOWN` fetches | A dlt cursor cannot tell "checked, nothing changed" from "nobody checked", and never sees a delete. The failure that matters is a false "fresh" |

**A failed load must not empty a table either.** Under dlt's default `truncate-and-insert`, a load that fails empties every `replace` table of the run or cuts it short, and the run check before the load cannot see it (measured 2026-10-01). So:

- **A build reads only files whose load is committed** in `_dlt_loads` and equals the one `_extract_runs` recorded. The load id comes from the **file name**, because a zero-row Parquet file has no `_dlt_load_id` value. The files are an explicit list, never a glob.
- **`append` only for `_extract_runs`.** An empty `append` makes no load package, so "the newest load on disk" kept serving lifted closures.
- **A pending package is dropped before the run syncs.** A run that died between extract and commit leaves its package and resource state behind; kept, the next run read that marker and answered FRESH. `_run.py` drops it, warns, then syncs, and refuses a load that commits more than one package.
- **An allowed zero counts only with the upstream's own count, read in the same run**: ArcGIS `returnCountOnly=true`, Socrata `count(*)` under the entry's `where`, WordPress `X-WP-Total`, the moderated query's own `count(*)` for OurHike's Postgres, an NWS `200` with no features. Without it the zero is `UNKNOWN`. **A count you make of what you parsed is not one**: a page whose layout moved parses to nothing exactly as an empty page does. Every reader kind declares `zero_proof` on its class (`Resource.zero_proof`): the upstream count it reads, in words, or `None`. The run check refuses a zero from a `None` kind, and keeps the shrink floor on such a table. `tests/test_extract_zero_proofs.py` pins every kind's answer.

**On a safety path no check may answer `FRESH` while the data moved.**

- On-prem ArcGIS ETags hash the metadata response, so they never move when the data does (USFS read the same ETag a month apart). Use the statistics fingerprint instead: `count`, `max(OID)`, `sum(Shape_Length)` and the maintained date. An unchanged fingerprint is FRESH only when that date is the one editor tracking names (`editFieldsInfo.editDateField`); otherwise it is UNKNOWN and the layer is read every run.
- `max(edit date)` alone cannot see a deleted row.
- WordPress feed validators are site-wide, so they never decide `FRESH` for closures.
- An RSS window is not a list of current items: absence from it is never read as "lifted".
- A 304 never reaches dlt, where it raises `PipelineStepFailed`. The conditional request is ours, and 304 means `FRESH`.
- **A marker counts only beside the rows a build reads.** dlt's filesystem `complete_load()` stores state before it writes the `_dlt_loads` row, and the stored state is restored whether its load committed or not. So `_run()` reads the marker of a table with no logged, committed load as no marker, and turns FRESH into UNKNOWN when that load's files are gone (`served_files_intact()`).

**The rest of `.dlt` configuration:**

- `naming = "sql_ci_v1"`, plus a map step flattening `properties`, so `GlobalID` lands as `globalid`.
- Column hints from each ArcGIS layer's `fields`, so an all-null column is still created; `esriFieldTypeDate` lands `bigint` and base models convert it.
- Schema contract `{"columns": "evolve", "data_type": "freeze"}` on ArcGIS.
- **ArcGIS pages come from `lib/arcgis.py`'s `iter_layer_pages()`, never a second pager.** It steps by rows returned, stops on an empty page, halves a refused page, and raises `OffsetIgnored` on a server that repeats a page or serves more rows than the layer's own count; `_kinds.py` then reads the layer again by object id (`keyset=`). dlt's `OffsetPaginator` steps by `limit`: against a server capping pages at 4, `limit=10` loaded 4 of 10 rows.
- **One retrying session per caller**, never a global `RUNTIME__REQUEST_*`: `_kinds.py`'s `session()` passed to `lib/http_retry.py`. Retry postures differ on purpose (**#536 — One transient 504 from USGS throws away an entire publish**).
- `_loaded_at` (naive UTC) is stamped in the map step **only when a resource runs**, so a `FRESH` table keeps its old stamp. dbt's freshness therefore reads the run log, never `_loaded_at`.
- **One dlt schema per store**: every `pipeline.extract()` and `pipeline.run()` passes `schema=store_schema(pipeline)`. A second schema means a second package and the "one load expected" refusal.
- dbt runs as its own CLI step, never through `dlt.dbt`, whose default pins `dbt<2`.

**A field its publisher retyped is refused on every run until one table is reset.** `data_type: freeze` compares against the store's schema, which `replace` never resets, so the layer logs `refused`, its last committed table stands, and freshness turns it red. Read the refusal (`schema contract: …` in the run summary) beside the layer's metadata, and reset only when the new type is the publisher's choice. Then, while that lane is not running: `python -m extract._run --lane <lane or leg> --raw-bucket our-hike-raw --only <raw table> --reset`. It drops the table, its state and its schema history inside the same load package, so a reset the run check refuses drops nothing. A base model casting the field may need changing in the same pull request.

## Load every org, gate publication downstream

- **`trail_orgs.json`'s `load` column does not gate extraction.** A resource never filters on a licence. `may_publish` is decided per layer in dbt (`int_sources__publication`; `pipeline/ELT.md`, "Who may publish").
- **The only filters before dbt are the ones a request already carries**: Socrata `where` clauses, the conditions database's moderation predicates, ATC's Campsite Sustainability Index read for official sites only, and an agency's own status field on a closure or status layer (never a date or a name).
- **Deduplication is dbt's**, in intermediates, after every org has loaded.
- **Whatever a layer's words say, extract it and quote them verbatim** on its `sources.json` row; dbt decides publication by class of wording.

**People never ship, and are never loaded.** A resource leaves person fields out of its requested field list, so they never reach the raw store, whatever the licence: the `PERSON_FIELDS` denylist, each ArcGIS layer's own editor-tracking fields, and any column whose name reads as a person's (`PERSON_SHAPED`) unless its name ends in an organization's mark (…Org, …Agency, …Unit, …Dept) or its row clears it in `not_person_fields`. A free-text column that carries personal data is left out whole. Some tables are never extracted at all, such as survey results with patron contact fields and volunteer rosters. A pytest refuses any resource whose hints or field list name a person field.

## Terms are never routed around

- **A refusal is a note, not a puzzle.** The four `refuse` orgs and every permission-gated source get dated notes quoting the terms in `terms`, and load only on written permission.
- **The maintainer sends every permission request.** No session contacts an org. Each reply is quoted, with its date, in the org's licence fields.
- **A robots.txt disallow, a 403 on the data or a login means `UNKNOWN`, and stops there.** A 4xx other than 429 on robots.txt itself means no rules (RFC 9309; `extract/_robots.py`). A 5xx, a 429 or no answer skips that host for the run.
- **Every request sends `lib/user_agent.py`'s `USER_AGENT`** (`CONTACTABLE_USER_AGENT` for Wikimedia). It names the project and links to it, so an operator can see who is asking from one line of their log.
- **Never imitate a browser.** Never send a browser's or another client's User-Agent, even to a host that would serve one. A host that refuses our own named agent has refused us: record it as `UNKNOWN`, report it in the pull request, and do not try another agent.
- **An org's own public ArcGIS layer counts as published, whatever its website's waiver says.** Other no-automation terms and waivers mean ask: a dated note quoting them, and a request the maintainer sends. ATC's trail-updates scrape stays as it is, on **#458 — Confirm with the ATC what may be republished from their Trail Updates**.
- **Honour `Crawl-delay`**, and send one request per source per run, conditional wherever the host sends validators.
- **An agency's copy of a steward's gated route**, a Facebook-only channel or a members-only page is the maintainer's call. Do not write the extractor that would take the decision for them.

## The three data checks

| check | when | what it holds |
|---|---|---|
| **Layout**, `pipeline/tests/test_extract_layout.py` | every pull request | every managing org answers each type exactly once, by a resource or a `not_available.toml` row, never both; every row a share naming a sibling with a resource, or a well-formed note; `SAME_AS` notes whose `original` is claimed; no two resources on one upstream URL or item id; one catalogue row per managing org; a `stg_<club>__<type>` for exactly the available types; every `sources.json` key claimed once; no table on two lanes. **A note's shape, never its age**, so the calendar cannot turn an unrelated pull request red |
| **Run check**, in `_run.py` | after every dlt run | *before the load*: each available resource loaded or recorded `FRESH`; `rows > 0` unless the type may be empty and the upstream's own count proves the zero; rows at least half the last loaded count, except a may-be-empty table whose kind counts its upstream (the floors are `@unvalidated`); each org's catalogue row produces exactly one row. A failure drops the package, so nothing loads and no marker advances. *After the load*: `committed()` checks the load is in `_dlt_loads`, the rows on disk equal the rows normalized, and every count proof holds; a failure records `unverified` and the build refuses |
| **Note ageing** | the monthly run, not upstream of publish | a note past `confirmed + recheck_after_days` fails, and a person rechecks it |

The run check also reaches dbt as source tests on `raw._extract_runs`, so a build cannot quietly consume a refused run.

**A resource a leg refuses on its own warns, and turns red in dbt's source freshness**, never by blocking the pipeline. The leg leaves it out, its last committed table stands, its run log row says `refused`, and the run exits 3, which `extract-notices.yml` and `publish-conditions.yml` record and warn on. After publishing, `dbt source freshness` turns a source red once it has gone its limit without a `loaded` or `skipped` row (24 hours for a notice source, 2 for NWS's alerts; `macros/last_read_or_confirmed_at.sql`). OurHike's own Postgres rows still stop the whole leg at once (`stops_the_leg()`). The monthly lane's `refused` job fails its run.

## Adding a club

1. **A `trail_orgs.json` row**, because the folder and table names come from its slug. It is written without review when it meets the standards in `pipeline/ELT.md`, "Licences and publication"; `features/ORG_BULK_LOAD.md` explains the `load` values.
2. **A `sources.json` row per upstream**, with the licence quoted, its basis recorded and its provenance in the row's notes, before anything reads it.
3. **Its answers for every type.** A type it publishes is a registered resource; every other type is a row of `not_available.toml`, a share or a note. Its catalogue row is made from the `trail_orgs.json` row. Never a second resource for a dataset another org already extracts. Start from the org's rows in `pipeline/ORG_COVERAGE_SURVEY.md`, and work the discovery list above before any note on a GIS-shaped type.
4. **Leave out person fields** in every field list, and check them against the denylist.
5. **Fixtures**: `make_dbt_fixtures.py` emits the upstream's answers (layer metadata with real `fields` and `maxRecordCount`, query pages, Socrata pages, WordPress posts). "Nothing here is invented" covers the `fields` lists too: copy them from the live layer.
6. **Tests** under the socket guard (below).
7. **dbt staging** for every available type: [the dbt skill](../dbt/SKILL.md), "Adding a club's staging models".
8. **Run** the layout test, `python -m extract._run --pipeline all --fixtures`, and the dbt job (`scripts/test.sh` does all three).
9. **In the pull request**: counts per org × type × mart, each layer's licence basis and `may_publish`, every new closure, warning, water and shelter source listed for review, and the `## Data pipelines` section from `scripts/pipelines.sh`.

## Tests under the socket guard

Every extract test runs under `pipeline/tests/conftest.py`'s autouse `no_outside_network` guard, which raises on any socket connection to a non-loopback address. `requests_mock` answers instead, intercepting at the adapter layer above sockets; dlt's `rest_api` source ran clean under the guard because it is built on `requests`.

- **Every pipeline a test builds writes under `tmp_path`.** Pass `pipelines_dir=str(tmp_path)` and a `tmp_path` filesystem or DuckDB destination. dlt's default working directory is outside the test, so state from one test would reach the next, and `dlt.pipeline(destination="duckdb")` with no path writes into the working directory (the 2026-09-09 spike dropped 117 MB of `.duckdb` files into `pipeline/`).
- **The cases worth a test, because each was measured going wrong**: a server whose pages are smaller than `limit` (all rows must load); an unchanged upstream (the resource is left out and its rows survive); an injected load failure (the previous rows survive, or the build refuses); a 304 (`FRESH`, and dlt is never called); a geometry round-trip through `ST_GeomFromGeoJSON`; telemetry off in `.dlt/config.toml`.
- Name each test for the failure it guards (the plain-language skill's 2 a.m. test): `test_a_page_smaller_than_limit_still_loads_every_row`, not `test_paginator`.

## A field that should never have loaded

Extraction is what makes a purge unnecessary. If a person field is loaded anyway, fix the resource first so it never loads again, then remove the value everywhere it went. Each step below was checked by searching every byte for a planted value after it.

**On a DuckLake lake**, in this order:

1. Fix the dlt resource.
2. Rewrite every table that held it without the field, with `CREATE OR REPLACE … SELECT * EXCLUDE (<field>)` or `ducklake_rewrite_data_files`. **Do not flush inlined data first**: the flush wrote a deleted inlined row into a new live Parquet file.
3. `ducklake_expire_snapshots(older_than => now())`. **This destroys all time travel, including every pinned `raw_run`.**
4. `ducklake_cleanup_old_files(cleanup_all => true)` and `ducklake_delete_orphaned_files(cleanup_all => true)`.
5. `COPY FROM DATABASE` into a new catalog file, and replace the catalog object: the old file's free pages still held the value.

**On the plain-file tiers, which the raw store uses today**: the next `replace` deletes the table's old file; `purge-person-fields.yml` (`pipeline/purge_person_fields.py`) reads each stored object's own schema or keys and deletes exactly those holding a value, dry-run by default; and **delete, never edit**, every pin, stored warehouse and browse copy built from that table, because a DuckDB file's free pages keep a dropped value.

Either way the purge removes every pinned `raw_run`, so the next promotion needs a fresh UA build. Say in the pull request which field loaded, for how long, and where it reached; the maintainer decides who else needs telling.
