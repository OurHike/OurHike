---
name: dbt
description: Work on the dbt project in pipeline/dbt/ - models, sources, seeds, tests, contracts, exposures, macros and the SQLFluff config. Use when adding or changing any of those, when adding a club's staging models, when the dbt job or SQLFluff fails in CI, or when dbt deps fails in a sandbox. Covers what exists today against the target pipeline/ELT.md plans, the layer names and the evaluator's rules, contracts and the traps in them, SQL before an extension before Python, publication rules, state for pull requests, the commands CI runs, and the dbt deps workaround.
user-invocable: true
---

# dbt in this repository

**SQL first, then an extension, then Python** (decision 23): core DuckDB SQL, then SQL with `spatial`, then a community extension, and Python only on a written reason ([below](#sql-first-then-an-extension-then-python)).

The maintainer chose, by poll on 2026-10-01 (decision 11 under
**#1793 — Rebuild the data platform as dlt → dbt: seven contracted marts, a
monthly refresh, published docs, and lighter phone downloads**), to get dbt help
two ways: this file for what is specific to this repository, and dbt Labs'
general plugin for everything else.

**The plugin is enabled in [`.claude/settings.json`](../../settings.json)** as
`dbt@dbt-agent-marketplace`, from `dbt-labs/dbt-agent-skills`. Its
`.claude-plugin/marketplace.json` (read 2026-10-01) names the marketplace
`dbt-agent-marketplace` and three plugins: `dbt` (version 1.5.1, Apache-2.0),
`dbt-migration` and `dbt-extras`. Only `dbt` is enabled, because decision 11
named only that one. Ask the plugin how selectors, unit tests, contracts and
docs work in general. Several of its skills assume the dbt platform (dbt
Cloud), the dbt MCP server or the semantic layer; this project uses none of
them. **Where the plugin's general advice and this file disagree, this file
wins**, because each difference is a decision made here: no Python models,
unprefixed mart names, the jinja templater.

[CLAUDE.md](../../../CLAUDE.md) wins over both, and where this file and
CLAUDE.md could be read as disagreeing, this file has a bug. CLAUDE.md's
evidence grades bind every comment and description written in a model, and
models on the paths of its four harms (lost, out of water, in front of
something dangerous, unable to get off the trail quickly) carry the strictest
tests.

"Decision N" below is a row of the maintainer's decisions table in
`pipeline/ELT.md`, "Overview".

## Read this first: which project you are in

`pipeline/ELT.md` is the design that issue's pull request adds, on branch
`claude/intelligent-feynman-sw3ewm`. **Most of `pipeline/ELT.md` is built on
that branch**, and its "Phases" and "Work in flight" sections say what is not.
This file describes that branch. Check which project you are in before you
follow anything below.

| | `main` (read 2026-10-01 at 22e8a2be) | This branch (read 2026-10-06 at fd38fe24) | Target (`pipeline/ELT.md`) |
|---|---|---|---|
| dbt | `dbt-core==1.12.2` and `dbt-duckdb==1.11.0`, pinned in `pipeline/requirements-dbt.txt` | **`dbt==2.0.6`**, the full distribution, one version everywhere (decision 32); `dbt-oss` 2.0.5 is the documented fallback, which ran the same project green. `dbt-duckdb` and `sqlfluff-templater-dbt` are gone | the same |
| DuckDB | `duckdb==1.5.5`, the same pin as `requirements.in` | Python's 1.5.5 writes the fixture warehouse, and dbt reads it with its bundled 1.5.4, through an ADBC driver it downloads (measured on a runner, 2026-10-01) | the same |
| Packages | `dbt_utils` 1.4.1, `dbt_project_evaluator` 1.3.2, `codegen` 0.14.1 (`packages.yml`) | evaluator 1.4.0 | the same |
| Models | `staging/<org>/` for `atc`, `dec`, `mohonk`, `nynjtc`, `opentrail`, `oprhp`; `intermediate/int_pois_unioned.sql`; one mart, `marts/core/dim_pois.sql` | the target's layers: 132 folders under `staging/`, the eleven marts under `marts/<mart>/` with `elevation_v2`, `points_of_interest_v2` and `trail_lines_v2` beside them, and 50 `pub_` writers; `int_pois_unioned` and `dim_pois` are deleted (the maintainer's review: *"No dim_ !"*) | `base_` → `stg_` → `int_` → eleven unprefixed marts (below) |
| Loader | `load_raw.py` reads `data/raw/` into `data/warehouse.duckdb`'s `raw` schema | dlt, under `pipeline/extract/`; CI's warehouse is the extract in fixture mode (`extract/_fixtures.py`) over `make_dbt_fixtures.py`'s files | dlt, under `pipeline/extract/` (see [the dlt skill](../dlt/SKILL.md)) |
| Evaluator | its own CI step, warn-only (`pipeline/DBT.md:184`) | enforced at `error`, with a 57-row exceptions seed ([below](#the-evaluator)) | `error`, two exception rows |
| Lint | SQLFluff, `templater = dbt`, after the load and `dbt seed` | SQLFluff, `templater = jinja`, enforced, last in the job on every core; `dbt lint` after `dbt parse` (decision 33) | the same |
| `scripts/test.sh` | runs neither dbt nor SQLFluff | runs the `dbt` job's steps as its dbt suite ([below](#the-commands-ci-runs-today)) | plus the target's extra steps |

On `main`, or a branch cut from it, the project is `main`'s: a change must pass
that `dbt` job on dbt-core 1.12.2. Do not write v2-only YAML into it.

## The order of work

1. **Decide where the rule lives** — core SQL, then an extension, then
   Python ([below](#sql-first-then-an-extension-then-python)).
2. **Name the model by its layer**, and put it in that layer's folder.
3. **Write its YAML**: a description, a primary-key test, and on a mart a
   contract.
4. **Add the tests the rule needs**: generic, singular, and a unit test for
   any rule ported from Python.
5. **Run what CI runs** ([below](#the-commands-ci-runs-today)), then the state
   check if a mart or an exposure moved.
6. **Write the pull request's `## Data pipelines` section** from
   `scripts/pipelines.sh`, as CLAUDE.md asks.

## SQL first, then an extension, then Python

The maintainer, decision 23: *"All the dbt models should be sql-first. We
deeply prefer to have sql over python. Yes their might be some exceptions,
especially around the geospatial functions. Attempt to load a duckdb extension
and use sql before going the route of a python model though."*

Try each in order. Take a step down only on a written reason: a measured
failure, a missing function, or a parity unit test that SQL cannot pass. Write
that reason in the model's header comment, and in `pipeline/ELT.md`'s porting
ledger.

1. **Core DuckDB SQL.**
2. **SQL with the `spatial` extension.**
3. **SQL with a community extension**: `h3`, `geography`, `a5`, `raster`. All
   four install and load on DuckDB 1.5.5 (measured 2026-10-01). Whether
   dbt 2.0.6 loads a community extension from `profiles.yml`, and whether
   these four have builds for its bundled 1.5.4, are both `@unvalidated`; one
   CI run settles each. The fallback is a pre-hook
   `INSTALL … FROM community; LOAD …`.
4. **A Python step.**

**There are no dbt Python models here.** v2 refuses them on DuckDB, on dbt
2.0.6 as on dbt-oss 2.0.5: a three-line `def model(dbt, session)` parses, and
then fails at `dbt build` with `Internal Error: Python models are not supported
for duckdb adapter` (both measured 2026-10-01, `pipeline/ELT.md`, "Tests move
with their rule"). Re-run that probe at each dbt bump. A
Python rule runs as a step between dbt invocations:

- it reads named intermediates and writes a table in the `derived` schema;
- that table is declared as a source and staged as `stg_derived__<thing>`,
  because an intermediate reading a source trips the evaluator's
  `fct_marts_or_intermediate_dependent_on_source`;
- an exposure named `step_<name>` on its inputs puts both halves in the docs.

**What `spatial` has, on DuckDB 1.5.5** (measured 2026-10-01). Absent:
`ST_ClusterDBSCAN`, `ST_ClusterIntersecting`, `ST_ClusterWithin`, `ST_Split`,
`ST_Segmentize`, `ST_SnapToGrid`. `duckpgq` has no build for 1.5.5 (HTTP 404).
Present, among others: `ST_LineLocatePoint`, `ST_LineInterpolatePoints`,
`ST_LineSubstring`, `ST_LineMerge`, `ST_Node`, `ST_Simplify`, `ST_DWithin`,
`ST_AsMVT`. The full list is decision 23 in `pipeline/ELT.md`.

**Two traps in every geometry port**, both measured 2026-10-01:

- **`ST_Distance_Sphere`, `ST_Distance_Spheroid` and `ST_DWithin_Spheroid`
  read x as latitude.** With (lon, lat) points, a 30 m east–west pair at 41°N
  read 39.71 m, and a 30 m north–south pair read 8.26 m. Measure metres after
  `ST_Transform(geom, 'EPSG:4326', 'EPSG:5070', always_xy := true)`, which
  read 29.80 m, or call `ST_FlipCoordinates` before any `_Sphere`/`_Spheroid`
  function. Every port that measures a distance carries a unit test with a
  known 30 m pair in both directions.
- **Never call `ST_ReducePrecision` to get 6 decimals.** It removed 3 of
  249,046 vertices from the published trail lines, which would misalign
  `trail_miles.json`'s per-vertex mile arrays. Round `x` and `y` per vertex
  instead.

## Layers and names

| Layer | Name | Folder | Reads | Does |
|---|---|---|---|---|
| base | `base_<steward>__<layer>` | `staging/<steward>/base/` | one `source()` | once per upstream dataset, in the folder that extracts it (decision 34): `base_usfs__trails`, never one per club. Rename, cast, `st_setcrs(st_geomfromgeojson(geometry), 'OGC:CRS84')`, lowercase aliases, the key and the dedupe ([below](#one-key-per-table)). No filter, no join |
| staging | `stg_<club>__<mart>` | `staging/<club>/` | that club's base models | conform to the mart's shape: rename to its columns, carry the key. No filter: the club's review gate goes in its intermediate (decision 40) |
| union | `int_<mart>__unioned` | `intermediate/<mart>/` | every `stg_<club>__<mart>` | `union all by name`, no filter |
| heavy | `int_<mart>__<verb>` | `intermediate/<mart>/` | unions, intermediates, `stg_derived__*` | dedup, corridor, water distance, mile axis, graph |
| stewardship | `int_<mart>__stewardship` | `intermediate/<mart>/` | the deduplicated intermediate, `stg_registry__orgs`, ATC's club sections | one row per (feature, club, basis, evidence): which clubs steward each feature. It assigns, never copies |
| final | `int_<mart>__final` | `intermediate/<mart>/` | intermediates | the mart's rows, every contracted column but the two row dates ([Row dates](#row-dates-one-snapshot-per-mart)) |
| row history | `int_<mart>__history` | `snapshots/<mart>/` | its `int_<mart>__final` | a dbt snapshot: every version of every row, whole, schema `intermediate` |
| mart | one of the eleven names | `marts/<mart>/` | its history; its final model instead when `OURHIKE_ROW_HISTORY=off` | `row_history_mart()`: the current rows and their two dates. Contract, `access: public`, exposures |
| reporting | `rpt_<thing>` | `reporting/` | marts | counts for the docs page |
| publish | `pub_<file>` | `publish/` | the marts its exposure names | writes one phone file |

`<club>` is the club's extract folder name: `trail_orgs.json`'s `slug` with `-`
written `_`. That renames two of today's folders: `dec` becomes `nysdec` and
`oprhp` becomes `nysparks`. Non-club staging lives in `staging/registry/`
(`sources.json`, `trail_orgs.json`, every club's catalogue row), `staging/derived/`,
and one folder per shared source (`nws/`, `osm/`, `usgs/`, `opentrail/`,
`podcasts/`, `ourhike/`).

**A club's portion of another org's layer is an assignment, not a model of its
own** (decision 34; the maintainer: *"each club can take that data and assign
their portion"*). A club whose trail lives in USFS's layer has no base or
staging model for it. Its portion is rows in `int_<mart>__stewardship`, whose
basis is one of three: the ATC club-section polygons
(`raw_atc__trail_club_sections`), the club's `trails` list in
`trail_orgs.json`, or a name or ID match. Each feature reaches its mart once,
with its stewards attached. Dedup in intermediates is only for independent
datasets of the same ground, such as a club's own GPS line against USFS's;
a republished copy is a `SAME_AS` note in extract and never reaches dbt.

**The eleven marts, exactly:** `trail_lines`, `points_of_interest`,
`elevation`, `closures`, `warnings`, `podcasts`, `challenges`,
`trail_network`, `places`, `suggested_hikes`, `sources`. Never `dim_` or
`fct_`. The maintainer: *"do not keep the dim_ and fct_ prefixes in the marts
folders. Just use the names I provided"*.

**The evaluator learns those names through a var**, not an exceptions row,
because a `marts` row would switch naming off for every mart:

```yaml
# pipeline/dbt/dbt_project.yml (the file writes it as a block list)
vars:
  dbt_project_evaluator:
    marts_prefixes: ['trail_', 'points_', 'elevation_', 'closures_', 'warnings_',
                     'podcasts_', 'challenges_', 'places_', 'suggested_', 'sources_']
                     # never dim_ or fct_: the maintainer, in review, "No dim_ !"
```

The evaluator reads a prefix as `split_part(name, '_', 1) || '_'`, so `trail_`
covers both `trail_lines` and `trail_network`. Measured 2026-10-01 on dbt
2.0.6 and on dbt-oss 2.0.5, against a scratch copy with one model for each of
the eleven names under `models/marts/<name>/`: no naming or directory finding
for any of them. `pub_` is in `other_prefixes` beside `rpt_`
([below](#phone-files-are-written-last-and-only-locally)).

**Union by name, never by position.** `main`'s `int_pois_unioned.sql` unions
positionally with `select *`. Under that union a swapped `st_x`/`st_y` in one
staging model put every DEC lean-to in Antarctica on a green build, `PASS=145`
(the header of `assert_pois_land_in_the_region_this_build_covers.sql`).
`int_points_of_interest__unioned` replaced it, by name. Keep that region test
anyway: a swap inside one base model still unions cleanly.

**Materializations.** `base_` and `stg_` models are views. Unions and heavy
intermediates are tables, and `int_<mart>__final` models are views. Marts are
contracted tables. Snapshots exist for one purpose, the row dates: one
`int_<mart>__history` per mart and no other (decision 57, amending 52). Add
no incremental model and no other snapshot without a decision (decision 27).
`closures` and `warnings` stay `table`.

**Every source and every exposure carries `meta.cadence`**, one of `hourly`,
`daily`, `weekly`, `monthly` (decision 28). Models are not tagged: a model's
cadence is the fastest among its upstream sources, and each lane runs
`dbt build --select config.meta.cadence:<lane>+` (measured selecting correctly
on 2.0.5, 2026-10-01).

## One key per table

Decision 40, the maintainer's: *"every table needs a unique id. Use the
dbt_utils package in dbt, and call the generate_surrogate_key() macro to create
the key based on current values... staging tables should only do 2 main things.
data type conversion / field renaming & dedupe source tables."* `pipeline/ELT.md`,
"One key per table", has every table's measured key. On every model that reads
a `source()` (today's `stg_`, the target's `base_`):

- **The first column is the key**: `<what one row is>_key`, built with
  `{{ dbt_utils.generate_surrogate_key([...]) }}`. Its first input is the
  registry key as a literal (`"'dec_primitive_campsites'"`), so keys stay
  unique across the union. Then the upstream's own unique id, or the smallest
  set of current values measured unique, with `geometry_key('geom')` where no
  attribute tells two rows apart. Never `OBJECTID` or `FID` alone: a reload
  mints them again.
- **Measure the key before writing it**, on the live layer:
  `pipeline/spike_table_keys.py` finds the smallest unique set and counts the
  exact copies. Do not trust a key because a field is called an id. DEC's
  `ASSET_UID` names two different campsites four times over.
- **The model ends with `{{ dbt_utils.deduplicate(relation='renamed',
  partition_by='<key>', order_by='<order>') }}`**, the package's own macro.
  dbt_utils has no DuckDB version of it, and its default natural join drops
  every row holding a NULL (measured 2026-10-01), so `dbt_project.yml`'s
  `dispatch` block finds the project's `macros/duckdb__deduplicate.sql` (a
  QUALIFY) first. Never write a dedupe of your own, and never remove that
  dispatch block.
- **The raw table gets `duplicates_are_exact`** in `_<club>__sources.yml`,
  with the same key expressions (`geometry_key('geom')` written out as
  `md5(st_astext(geom))`). It fails the build when rows sharing a key differ,
  so a dedupe only ever removes exact copies.
- **The model's YAML** tests the key `unique` and `not_null`, and carries a
  `dbt_utils.equal_rowcount` against its source at `severity: warn`, which says
  how many copies the dedupe removed.
- `pipeline/tests/test_dbt_keys.py` checks all of that without a warehouse,
  and holds the model's key list equal to its source test's.
- **Nothing else happens in that model**: renames and casts, the key, the
  dedupe. Classification literals, seed lookups and review gates are
  intermediate work. `main`'s POI staging models carry `poi_type` and
  `confidence` literals; on this branch they are the `poi_sources` seed's
  columns, read by `int_points_of_interest__sources`.

## Row dates: one snapshot per mart

Every mart row carries **`_first_seen_at`** and **`_changed_at`**
(`timestamptz`, UTC); nothing else is asked to (decision 57, amending 52).
`pipeline/ELT.md`, "Row dates (decision 52)", has the design and its
measurements; `macros/row_history.sql` has the macros. This is what to do.

- **A new mart** is three files and a YAML entry each.
  - `intermediate/<mart>/int_<mart>__final.sql` holds the mart's SQL.
  - `snapshots/<mart>/int_<mart>__history.sql` is
    `{{ config(unique_key='<key>') }}` and
    `{{ row_history_snapshot('int_<mart>__final') }}` inside a snapshot
    block.
  - `marts/<mart>/<mart>.sql` is
    `{{ row_history_mart('int_<mart>__history', 'int_<mart>__final', '<key>') }}`.
  - The contract declares both dates `timestamptz`, with
    `description: "{{ doc('row_first_seen_at') }}"` (and `row_changed_at`)
    and a not_null test whose severity is exactly
    `"{{ 'warn' if env_var('OURHIKE_ROW_HISTORY', 'on') == 'off' else 'error' }}"`.
  - Copy `closures`. `pipeline/tests/test_dbt_row_dates.py` fails until
    every piece is there.
- **A later version** (`<mart>_v2`) selects v1's two dates. It gets no
  snapshot of its own.
- **Unit tests of a mart's logic** go on `int_<mart>__final`, where the SQL
  is.
- **The hash** covers every column but `_loaded_at` and the other load
  columns (`row_hash_load_columns()`). A column that changes on every run
  while the row does not goes in `row_history_snapshot()`'s `skip=[...]`.
  Otherwise every row reads as changed every run.
- **`_first_seen_at` equal to the history start means "at or before"**
  (`row_history_started_at()`, and history.json's `history_started_at`).
  Never read it as "new".
- **A removed row** stays in the snapshot with dbt_valid_to set and leaves
  the mart. Nothing reads it back yet; `row_history_removed()` is the hook
  for that later decision.
- **History lives outside the warehouse.** `build_marts.py` restores it
  before dbt and saves it after the writers (`pipeline/row_history.py`).
  - Never force a cold start in a lane's workflow.
  - List a store in `pipeline/row_history_stores.toml` once its first
    run has saved.
  - Only the conditions legs pass `--history-on-failure degrade`.

## Publication is decided once, in SQL, before dedup

- **`may_publish` has one home: `int_sources__publication`.** Every mart except
  `sources` keeps only rows whose source has `may_publish`; `sources` keeps
  every registered row, because it is where the flag is read. The flag is true
  only when the `licence_basis` is in the `publishable_licence_bases` seed
  **and** the row's own verdict says it ships (`reaches_hikers` in
  `sources.json`, or a `trail_orgs.json` `load` of `ship` or `via`). Null,
  `unstated` and `unresolved` are false. An absent licence is not permission.
  The whole rule is `pipeline/ELT.md`, "Who may publish": the public-GIS
  presumption, which decision 37 extends to internal-use and
  not-for-distribution layers on anonymous public endpoints; the
  clearinghouse ruling; the licence batch's other answers (decision 36,
  non-commercial use publishes; decision 38, each condition travels with its
  layer and a condition that cannot be met holds it); and the `refuse` orgs.
  A restriction no decision names stays `may_publish` false.
- **The `public_use` rule has one home: `int_points_of_interest__publishable`.**
  `export_nearby_poi.py`'s `public_verdict()` and `confidence_for()` are
  deleted at cutover, not kept beside the SQL.
- **Publication filters run before dedup.** A row that may not ship must never
  win a merge and then vanish, taking the place with it.
- No exporter and no writer model re-decides any of this.

## Contracts, and the traps in them

Every mart is a contracted table (`contract: {enforced: true}`), `access:
public`, with every column described. Intermediates are `protected`. Every mart
carries `club varchar` (the folder that extracted the row), `source_key
varchar` (with a relationships test to `sources`) and `_loaded_at timestamptz`,
and each feature appears once, its stewards attached from
`int_<mart>__stewardship`.

| Trap | Evidence | What to do |
|---|---|---|
| `geometry('OGC:CRS84')` refuses only a *different, known* CRS. It accepts a geometry with no CRS, and a `.duckdb` file never keeps one | measured 2026-10-01 on 2.0.5: a mart holding EPSG:5070 metres built green | every geometry mart carries a bounds test (lon in [-180, 180], lat in [-90, 90], plus the club's own box from `trail_orgs.json`'s `states`) beside the lon/lat swap test |
| column names are compared case-sensitively | measured on 1.12.2: ATC's `Name` failed until aliased | alias every column in lowercase in the base model |
| **Freshness on `_loaded_at` reads a quiet, healthy source as stale**: the extract stamps it only when a resource runs, so a FRESH change check leaves it at the last load | measured 2026-10-07: at c202d399, which measured notice sources on `_loaded_at`, tests/test_dbt_notice_source_freshness_runs.py's source confirmed unchanged an hour ago, with a `_loaded_at` a week old, warned. dbt 2.0.6 supports `loaded_at_query` on a source or a table, with Jinja, `{{ this }}` and a project macro; refuses it beside `loaded_at_field` on the same level (dbt9002); reads a null max as 1970-01-01, so stale, and a naive TIMESTAMP as UTC; a warning exits 0, an error 1 (all measured 2026-10-07 in a scratch project) | on any source whose check can answer FRESH, `loaded_at_query: "{{ last_read_or_confirmed_at(this) }}"` (macros/last_read_or_confirmed_at.sql: the newest `loaded` or `skipped` row in `_extract_runs`). Every notice source has it, erroring after 24 h unread, 48 h for a daily one (decision 100, generate_notice_models.py's FRESHNESS_HOURS), tagged `notices_job` or `conditions_job` for publish-conditions.yml's freshness step |
| `_loaded_at` is `TIMESTAMPTZ` on every dlt raw table, though `extract/_run.py` stamps naive UTC | measured 2026-10-01, dlt 1.30.0 filesystem destination: 63 of 64 fixture-mode tables, and `_warehouse.py`'s proven-empty table was the 64th until it was made the same. `TIMESTAMP` was `load_raw.py`'s, measured on 1.12.2 | declare `timestamptz` |
| no `foreign_key` constraint | Reasoned: DuckDB refuses to drop a table a foreign key references, and every rebuild drops it | a relationships test instead |
| `primary_key` and `check` fail any build into DuckLake | measured 2026-10-01 on 2.0.5 | why the warehouse moves to DuckLake only at phase 4 |
| v2 refuses `contract` on a snapshot; a contracted incremental model must set `on_schema_change` | measured 2026-10-01 on 2.0.5 | why `int_<mart>__history` has no contract: the mart's contract holds its columns |
| **On 2.0.6, a contracted model with a `GEOMETRY` column fails at build**: "Failed to convert type BinaryView ... not supported for DuckDB", from the contract's column check. The row above was measured on 2.0.5 and does not hold on 2.0.6 | measured 2026-10-02 on 2.0.6, the fixture warehouse, a closures mart (the cw worker), repro: any contracted `select st_point(1, 2) as geom` with `data_type: geometry`. An uncontracted model carries `GEOMETRY` fine | every contracted mart and `pub_` writer carries **`geom_geojson varchar`**, an RFC 7946 geometry in OGC:CRS84 at the phone file's precision, with tests that `st_geomfromgeojson` parses it. Keep `GEOMETRY` in uncontracted intermediates and convert at the mart, never earlier |
| **A 2.0.6 unit test compares a `DOUBLE` only after rounding it to one decimal place**: VARCHAR, integer and boolean compare exactly | measured 2026-10-02 on 2.0.6 by planting values in `expect` (the tl-at worker): 3365.9 and 0.44 passed against 3365.936… and 0.4004, and 4.0 against 3.985; 3365.96, 0.45 and 3.94 failed | carry a mile, a distance, an elevation or any must-match double as text (`varchar`, or JSON, which round-tripped 5,005 of 5,005 doubles exactly) in a unit-tested intermediate, and cast in the consumer. A unit test on a double safety field otherwise passes anything within about 0.05 |
| a 2.0.6 unit test cannot hold a `GEOMETRY` or a list column in a model's output: geometry panics ("BinaryView is not supported for DuckDB"), lists are refused ("Only primitive types ... supported for unit_testing") | measured 2026-10-02 on 2.0.6 (the tl-at worker) | WKT text for geometry (exact: DuckDB prints the shortest digits that read back to the same double), JSON text for a list |
| **dbt 2.0.6's DuckDB is 1.5.4 with spatial 28db190, and on it `ST_Intersects` against `GEOMETRYCOLLECTION EMPTY` segfaults the whole dbt process**; Python's DuckDB 1.5.5 answers false | measured 2026-10-02 by the tl-net worker: `ST_Union_Agg` over zero rows gives that empty collection, and intersecting many rows against it killed `dbt build` with no error line | guard every intersect against an aggregated union whose inputs can be empty with `having count(*) > 0` on the union, so an empty input gives no row rather than an empty geometry (int_trail_lines__network_area_closures does) |
| **`dbt lint` reads `left join x on true` as the table `x` aliased `on`** (AL01, AL05 errors), where SQLFluff 4.3.0 parses it as a join condition | measured 2026-10-02: CI's dbt job failed at its `dbt lint` step on 7074abb0, fc7f67ac and 0e1e0200, eight errors across four `pub_conditions_*` writers, while `sqlfluff lint` exited 0 on the same files | write the condition the joined CTE is already filtered on (`on gate.source_key = 'atc_trail_updates'`), which keeps a left join's one row when the CTE is empty; and run `dbt lint --profiles-dir .` beside SQLFluff before every push |
| **dbt 2.0.6 refuses a config key it does not know**: `config(when_empty=...)` failed the build, "Ignored unexpected key `when_empty`" (dbt1060), where dbt Core passes any key through to `config.get` | measured 2026-10-02 on 2.0.6, `phone_file` | a custom materialisation's own options go under `meta` (`config(meta={'when_empty': 'keep_last_file'})`, read back with `(config.get('meta') or {}).get(...)`); `format` and `location` pass because dbt-duckdb defines them |
| a given or expected double is written as `CAST(<literal> AS double)`, and DuckDB reads the literal as a `DECIMAL` first | measured 2026-10-02 on 2.0.6 (the tl-at worker): a 17-significant-digit literal came back one ulp off | another reason to compare must-match numbers as text |
| DuckDB's `round(x, n)` is not Python's `round()`: it scales by 10ⁿ and rounds half away from zero, where Python rounds the double's exact decimal value, half to even | measured 2026-10-02 on DuckDB 1.5.5 (the tl-net worker): of 266,800 doubles built to sit on, or an ulp either side of, a half at 6, 3 and 2 decimals, `round()` answered differently from Python on 14,125 and `cast(printf('%.6f', x) as double)` on none, at all three; DuckDB's JSON text of the printf result equalled `json.dumps` on all of them | a writer whose digits must match a Python exporter's cuts with `cast(printf('%.<n>f', x) as double)`, never `round()` |

**Absent means unknown, never zero.** The safety fields in `pipeline/ELT.md`,
"The eleven marts", are each a constraint or a test. Three examples: `capacity
is null or capacity >= 1`; `(water_distance_ft is null) = (water_distance_source
is null)`, so a distance never ships without the source the phone prints its
tilde from; `elevation_ft` is null where no DEM covers the point. Read that
table before adding a column to a mart a hiker's safety turns on.

## The evaluator

- **Severity** comes from
  `+severity: "{{ env_var('DBT_PROJECT_EVALUATOR_SEVERITY', 'error') }}"`:
  `error` everywhere by default, `warn` only for a local survey.
- **No global `--warn-error`.** On 1.12.2 it escalated 8 deprecations
  (measured). Name each error in `--warn-error-options` instead.
- **Coverage stays at 100.** `test_coverage_target` and
  `documentation_coverage_target` cannot be excepted per model, so every model
  carries its primary-key test and a description.
- **The exceptions seed** is `seeds/dbt_project_evaluator_exceptions.csv`
  (`fct_name, column_name, id_to_exclude, comment`), with the package's own copy
  disabled and `id_to_exclude` as a SQL `LIKE` pattern. **Every `comment`
  carries its reason and an issue number with its full title**, and a pytest
  refuses a row without them. **The seed holds 57 rows at fd38fe24**: 28
  `fct_sources_without_freshness`, 11 `fct_model_fanout`, 5
  `fct_missing_primary_key_tests`, 5 `fct_too_many_joins`, 4
  `fct_rejoining_of_upstream_concepts`, and one each of
  `fct_exposure_parents_materializations`,
  `fct_exposures_dependent_on_private_models`, `fct_hard_coded_references`
  and `fct_root_models`, each with its own reason. Stage 1's was 8. The
  intended state is two rows, both citing
  **#1793 — Rebuild the data platform as dlt → dbt: seven contracted marts, a
  monthly refresh, published docs, and lighter phone downloads**:
  `fct_too_many_joins` on `int_%__unioned` ("union branches, not joins": one
  parent per club), and `fct_exposures_dependent_on_private_models` on `step_%`
  (a Python step inside the build, not an outside consumer). A third row needs
  a reason a reviewer can disagree with. Fixing the model is usually the
  better answer (Reasoned: a row switches a rule off for every model its
  pattern matches).

## SQLFluff

`pipeline/.sqlfluff` keeps the `duckdb` dialect, ST06 off and RF04 ignoring
`name` and `source`, each with its reason in the file's header. **The templater
becomes `jinja`, in CI and locally** (decision 19), with `apply_dbt_builtins =
True`, `library_path = dbt/sqlfluff_libs` and `load_macros_from_path =
dbt/macros`. `dbt/sqlfluff_libs/dbt_utils.py` renders the REAL dbt_utils from
`dbt_packages/`, never a hand-written copy (the maintainer: *"Get the actual
dbt_utils package. Dont reinvent the wheel"*): it supplies only the dbt
built-ins the package's macros call, and on 2026-10-01 its output equalled dbt
2.0.6's compile on all 27 staging models. It needs no warehouse but does need
the packages, and the generated models, which exist only once
`python generate_dbt.py` has run (decision 91), so CI runs it last and only
after that step succeeded. Never add a macro body to that
file; if a new dbt_utils macro fails to render, the missing piece is a dbt
built-in it calls.

The jinja templater cannot see compiled `ref()` and `source()` relations,
`var()` values or macro bodies; `dbt build` on the fixtures covers those.
Whether a project macro a model calls renders correctly under it is
`@unvalidated` until the first such macro is linted. ST06 comes back once the
last positional union is gone, since that union is its only stated reason.

**`dbt lint` is a fast, dbt-aware first pass, never the gate** (decision 33).
It reads `pipeline/.sqlfluff` and warns that it supports only SQLFluff's `dbt`
templater ("Continuing anyway"). Measured 2026-10-01 on 2.0.6: 32 files in
0.05–0.08 s here and 0.04 s on a runner; it failed a planted CP01 (keyword
case) and passed a planted LT01 (a space before a comma) that SQLFluff fails.
So **SQLFluff stays the enforced check**: a clean `dbt lint` is not a clean
lint. Run it after `dbt deps`, because without `dbt_packages/` it installs
the packages itself, which in a sandbox empties them (below).

## State, for a pull request

State buys a pull request two answers and no time: a 13-node deferred build
took 6.9 s against 7.1 s for the full build (measured on 1.12.2 fixtures). So
pull-request jobs build everything and use state only for these. The shape,
from `pipeline/dbt/` (the base manifest is the merge-base parsed in a
`git worktree` in the same job, which needs no storage and no credential —
Reasoned; the job's exact paths are `pipeline/ELT.md`'s, "Running it"):

```sh
BASE=$(mktemp -d)        # outside the repository, never under pipeline/
git worktree add "$BASE" "$(git merge-base origin/main HEAD)"
# deps there too (or the clones below), and the base's own generated models
# (decision 91: a base from after it has none committed), then:
[ -f "$BASE/pipeline/generate_dbt.py" ] && (cd "$BASE/pipeline" && python generate_dbt.py)
(cd "$BASE/pipeline/dbt" && dbt parse --profiles-dir .)

# 1. a breaking change to a contracted mart fails
dbt build --profiles-dir . --select state:modified --state "$BASE/pipeline/dbt/target" \
  --warn-error-options '{"error":["UnversionedBreakingChange"]}'

# 2. which phone files the change stales: the exposures in this list
dbt ls --profiles-dir . --select state:modified+ --state "$BASE/pipeline/dbt/target"
```

The breaking-change check exited 2 on 1.12.2 (measured). On 2.0.5 and 2.0.6
`dbt build --help` does not list `--warn-error-options`, though 2.0.5's `dbt
parse` accepts it, so its exit on v2 is `@unvalidated` until a probe drops a
column. That `state:modified+` reaches the exposures was measured on 2.0.5
and again on 2.0.6 (2026-10-01): one edited staging model selected itself,
its two downstream models and the exposure on them.
`scripts/pipelines.sh` still answers every path dbt does not own. Remove the
worktree afterwards with `git worktree remove "$BASE"`.

**`--defer` needs `database:` on every source**, because sources are not
deferred: the first attempt failed with `"ci"."raw"… does not exist`. Adding it
marks 127 nodes modified once, so it lands with the v2 migration.

## Phone files are written last, and only locally

Each phone file is a `pub_<file>` model in `models/publish/`, materialized by
the project's `phone_file` materialisation (`macros/materializations/
phone_file.sql`), with an exposure (`type: application`) whose `meta` gives its
R2 keys, format, coordinate decimals, offline tier and size budget.

- **Writers run after every test has passed**, as a final
  `--select path:models/publish`, because `dbt build` tests a model after
  building it and a writer would otherwise write before its own tests run.
- **They write only under `var('processed_dir')`**, which is
  `pipeline/data/processed/dbt/` while a family's Python writer still runs,
  because `export_sources.py` writes the same file names into
  `data/processed/` and its manifests hash what it wrote. Stage 4 points it
  at `data/processed/`. **dbt never writes the public bucket**: a
  DuckDB `COPY … TO 's3://…'` stored every object with no `Content-Encoding`
  and no `Cache-Control` (measured 2026-10-01 against a local S3 stand-in, not
  R2), and phones rely on both. `publish.py` uploads.
- **Not dbt's `external`**: on 2.0.5 it writes snappy only, refuses `options`
  and `format='gdal'`, and writes an all-NULL row for an empty model (measured).
- **Coalesce `features` to `[]`**: `list()` over zero rows writes
  `"features":null`, and an empty closures file is a normal state.
- **`location` is a bare file name**, which `phone_file` refuses otherwise:
  `COPY` creates no directory (measured 2026-10-01). The phone's key, slash
  and all, is the exposure's `meta.r2_keys`.
- **A writer is `access: public` with an enforced contract**, as the
  evaluator wants of a model an exposure reads, and `phone_file` asserts it:
  a custom materialisation enforces none on its own (measured 2026-10-01 on
  dbt 2.0.6, a wrong contract type built and wrote its file until
  `phone_file` called `get_assert_columns_equivalent`).
- **`pub_` is in the evaluator's `other_prefixes`** beside `rpt_`, which
  `fct_model_naming_conventions` needed (measured 2026-10-01).
- **A writer's family gets a `parity.py` row** and a CI step comparing it
  with today's exporter, until the exporter is deleted (ELT.md, "How a rule
  moves").

## Docs and charts are built, never committed

- **dbt docs publish at `https://ourhike.org/data/`, never under `/app/`**
  (decision 10: counts only, no maps). On v2 the output is `index.html`, an
  assets directory and Parquet: on stage 1's fixtures, 315 assets and 38
  Parquet files, 12,301,390 bytes on 2.0.6 (2026-10-01). `--static` and
  `--empty-catalog` exist on neither 2.0.5 nor 2.0.6 (`dbt docs generate
  --help`, read 2026-10-01). `pages.yml` and `pr-preview.yml` build the
  published copy through `.github/actions/dbt-docs-site`, against an empty
  warehouse, and `pipeline/check_docs_site.py` checks what they copy into
  `_site/data/`. Its one exemption is the unit tests' own coordinates, which
  the page carries; whether it should is open (ELT.md, "Docs and charts").
- **dbt Charts boards are YAML in `pipeline/dbt/charts/`, rendered only once
  dbt Charts supports dbt v2** (decision 19): `dbt-charts` 0.8.0 pins
  `dbt-core>=1.8,<2`. That is a named external blocker. Do not work around it
  with a second dbt version. A board reads only `rpt_` models, and never uses
  `point_map`, `bubble_map` or `geoshape`; a pytest refuses both.
- **Commit neither.** `target/`, `dbt_packages/` and `logs/` are gitignored
  (`pipeline/dbt/.gitignore`), and so is the warehouse (`pipeline/data/`).
  Nothing ignores a rendered file under `pipeline/dbt/charts/` (checked
  2026-10-01), so render into `target/`.

## The commands CI runs today

The `dbt` job in `.github/workflows/pipeline-tests.yml` on this branch, on
Python 3.12, from `pipeline/`, with the job-level
`DBT_ENGINE_SEND_ANONYMOUS_USAGE_STATS=false` on every step. Stage 1's job ran
green on a runner in 46 s on 2026-10-01; at fd38fe24 the build step alone took
205 s and SQLFluff 458 s (Pipeline tests run 37408628160):

```sh
# restore ~/.cache/com.getdbt/adbc and ~/.duckdb/extensions/v1.5.4 (actions/cache, keyed on requirements-dbt.txt)
pip install -r requirements-dbt.txt                    # dbt==2.0.6, sqlfluff==4.3.0, duckdb==1.5.5
python -m venv "$RUNNER_TEMP/extract" && "$RUNNER_TEMP/extract/bin/pip" install -r requirements-extract.txt
"$RUNNER_TEMP/extract/bin/python" generate_dbt.py      # both generators' models, never committed (decision 91); they import dlt
# restore dbt/dbt_packages (actions/cache, keyed on packages.yml and package-lock.yml)
cd dbt
dbt deps --profiles-dir .                              # only on a cache miss, and saved after one that succeeded
dbt parse --profiles-dir .                             # the v2 gate
dbt lint --profiles-dir .                              # the fast first pass, not the gate
cd ..
python check_contract_versions.py --head dbt/target/manifest.json --base <the base commit's manifest, parsed in a git worktree after its own generate_dbt.py>
python -m venv "$RUNNER_TEMP/pipeline" && "$RUNNER_TEMP/pipeline/bin/pip" install -r requirements.txt   # the pipeline's own pins, for the steps and parity's old side
"$RUNNER_TEMP/pipeline/bin/pip" install "duckdb-extension-spatial==<that venv's duckdb version>"
"$RUNNER_TEMP/pipeline/bin/python" seed_spatial_extension.py   # Python's 1.5.5 only; dbt's 1.5.4 is cached, or dbt fetches it
python make_dbt_fixtures.py
"$RUNNER_TEMP/extract/bin/python" -m extract._fixtures --raw-dir data/raw --warehouse data/warehouse.duckdb
python build_marts.py --fixtures --python "$RUNNER_TEMP/pipeline/bin/python"   # seed, stage A, each step and what it unblocks, the pub_ writers last
"$RUNNER_TEMP/pipeline/bin/python" -m pytest tests/test_dbt_<...>_builds.py   # four steps, one file each: row dates, notices absent, a club held for its rows, club layers absent
"$RUNNER_TEMP/pipeline/bin/python" -m pytest tests/test_dbt_notice_source_freshness_runs.py   # decision 100's freshness, on a warehouse holding only a run log
"$RUNNER_TEMP/pipeline/bin/python" parity.py --json-dir data/processed/parity <family> --new data/processed/dbt/<file>   # one line per family
cd dbt
dbt source freshness --profiles-dir . --exclude tag:pdf_notice   # fixture mode lands no PDF; production measures them (generate_notice_models.py's PDF_NOTICE_TAG)
dbt docs generate --profiles-dir . --output-dir target/docs
python ../check_docs_site.py target/docs                     # the parts, no --vars, telemetry off, no coordinates outside the unit tests
DBT_PROJECT_EVALUATOR_SEVERITY=error dbt build -s package:dbt_project_evaluator --profiles-dir .
cd ..
sqlfluff lint dbt/models dbt/tests --processes 0       # the enforced lint, last, so a failed build reports first; generated models included
# save the cache on a miss, even when a step failed
```

**A model that runs DuckDB out of memory beside others gets `tags=['builds_alone']`**
in its own `config()`, with a comment naming the run that failed. `build_marts.py`
then builds it on one thread between the rest of its stage and what it feeds
(its docstring, "A MODEL TAGGED `builds_alone`"), and refuses after `dbt seed` a
tag that would build out of order or sit in the hourly lane. Monthly run 20 put
it on `int_places__resolved` and `int_trail_network__cuts`. Not `--threads 1`
for a whole lane, and not `concurrent_batches`, which is a microbatch model's.

**Telemetry off is the only switch.** `DBT_ENGINE_SEND_ANONYMOUS_USAGE_STATS=false`
is the documented opt-out. Measured 2026-10-01 through a logging proxy:
without it each 2.0.6 command tried (parse, show) opened `p.vx.dbt.com`; with
it parse, show and build opened none; and `DO_NOT_TRACK=1` did not stop it. The dbt Product Licensing Agreement's §3.2
forbids disabling licence validation or anything else that talks to dbt's
services, so never set `DBT_SKIP_REMOTE_LICENSE` or any other undocumented
switch, and leave alone the call 2.0.6 makes to `public.cdn.getdbt.com` once
per command.

The job runs only when its own changed-paths list matches: `pipeline/dbt/`,
`generate_dbt.py` and the two generators it runs, `load_raw.py`,
`lib/source_registry.py`, `make_dbt_fixtures.py`,
`seed_spatial_extension.py`, `sources.json`, the two `requirements-dbt`
files, `pipeline/.sqlfluff`, the workflow and the changed-paths action.

**`scripts/test.sh` runs the same steps as its dbt suite**, read from that
job's own changed-paths step, in CI's order, with telemetry off the same way.
The fixtures and the warehouse go to a temporary directory, never to
`pipeline/data/`. It installs nothing: it needs the `dbt` that
`requirements-dbt.txt` pins first on `PATH` (`dbt --version` reading `dbt
2.0.6`), with that environment's `python` and `sqlfluff` beside it, and
otherwise reports the suite SKIPPED in its last line. A `dbt-oss 2.0.5` first
on `PATH` is reported by name and skipped. `.claude/hooks/session-start.sh`
does not install `requirements-dbt.txt`, so make a Python 3.12 virtualenv
**outside the repository** (the session's scratchpad) and put it first:

```sh
python3.12 -m venv "$SCRATCH/dbtvenv"
"$SCRATCH/dbtvenv/bin/pip" install -r pipeline/requirements-dbt.txt
PATH="$SCRATCH/dbtvenv/bin:$PATH" scripts/test.sh --no-dbt-deps   # after the clones below
```

In the target, the suite gains the breaking-change check, the extract layout
pytest, dlt fixture mode and `build_marts.py` (`pipeline/ELT.md`, "Running
it").

## Elementary's checks, by hand

**Every Elementary check is tagged `elementary_check`, at warn, and runs in
`build_marts.py`'s checks pass, after the pub_ writers**: `dbt test -s
tag:elementary_check` at one thread, lane-scoped as the writers are, the
monthly lane's with `--vars '{"days_back": 400}'` (`ELEMENTARY_CHECKS` and its
docstring, "ELEMENTARY'S CHECKS RUN AFTER THE WRITERS"); the hourly lane runs
none yet (`HOURLY_LANE_CHECKS`), and CI's fixture build runs both lanes'.
Every dbt build before that pass leaves the tag out. The checks come from
`make_dbt_staging.py`'s `raw_table_checks()` on every raw table and from the
marts' YAML (decision 102; `pipeline/ELT.md`, "The checks, and where each
goes").

**Two switches, and a check needs both.** `OURHIKE_ELEMENTARY=true` enables
Elementary's own models and its two hooks; `OURHIKE_ELEMENTARY_CHECKS=true`
enables the checks themselves (`dbt_project.yml` and
`make_dbt_staging.py`'s `ELEMENTARY_ENABLED`). With the checks' switch alone,
`exposure_schema_validity` compiles to the text `None` and errors, and every
other check passes without querying anything (measured 2026-10-08 by the
session that built them). With Elementary's switch alone the checks are not
in the graph at all.

**Elementary's tables first, or nothing is recorded**: with them missing, a
command passes and stores no result (measured 2026-10-08). `build_marts.py`
runs `dbt run --select package:elementary` before `dbt seed` for that reason,
with both switches on, so that Elementary's `dbt_tests` table describes every
check. By hand, from `pipeline/dbt/`, over a warehouse a fixture build made,
the same two commands `build_marts.py` runs. Two fixture builds ran them green
on 2026-10-08, in a 4-core sandbox other builds shared: Elementary's tables in
1 m 34 s and 1 m 17 s, and the 1,949 checks in 10 m 5 s and 10 m 2 s.

```sh
export OURHIKE_ELEMENTARY=true OURHIKE_ELEMENTARY_CHECKS=true
export DBT_ENGINE_SEND_ANONYMOUS_USAGE_STATS=false TZ=UTC   # Elementary's times are UTC with no zone
dbt run --select package:elementary --profiles-dir .                     # its tables first, and again after a check changes
dbt test --select tag:elementary_check --threads 1 --profiles-dir .      # every check, as the pass runs them
```

To run fewer, intersect the tag with another selector, as `build_marts.py`
does for the hourly lane (`tag:elementary_check,config.meta.cadence:hourly+`).
Add `--vars '{"days_back": 400}'` to read a check as the monthly lane does.
Read the results in the warehouse's `elementary.elementary_test_results`, or
build the page's file over them, which is what `build_marts.py` does last:
`OURHIKE_BUILD_STARTED_AT='YYYY-MM-DD HH:MM:SS' dbt build -s pub_data_quality
--profiles-dir .` (UTC; unset, every result in the warehouse counts as this
build's).

What a run by hand will and will not show:

- **On a warehouse with no history, every anomaly check passes** and logs
  "Not enough data to calculate anomaly scores". One build is one point, and
  no check can warn before its window holds 11, this build's among them
  (`dbt_project.yml`, "ELEMENTARY'S TRAINING AND DETECTION", which has the
  measurement). `row_history.py` restores a lane's history before a build;
  a warehouse built by hand has none unless it ran `restore`.
- **A check on a raw table the warehouse does not hold errors.**
  `build_marts.py` leaves those out (`absent_sources()`); by hand, select
  around them.
- **No failing row is kept**: `test_sample_row_count` is 0, and on dbt 2.0.6
  Elementary stores none at any setting (measured 2026-10-08, `dbt_project.yml`
  says how). Never raise it, here or in a test's meta.
- **Never `edr`**, the Elementary CLI: decision 102 measured and refused it.

## `dbt deps` in a sandbox

`dbt deps` cannot download packages here. Measured 2026-10-01 in this sandbox:

- `curl https://codeload.github.com/dbt-labs/dbt-utils/tar.gz/1.4.1` answers
  `403`, while `https://hub.getdbt.com/api/v1/dbt-labs/dbt_utils.json` answers
  `200`. The hub resolves the version; codeload serves the tarball.
- dbt-core 1.12.2 fails with "not a gzip file" (measured in the same planning
  research, 2026-10-01).
- dbt 2.0.6 fails the same way as dbt-oss 2.0.5: `Failed to get tarball from
  https://codeload.github.com/…; status: 500`, exit 1, **and it prints
  `Installed 3 packages` while leaving all three folders empty** (2.0.6,
  measured 2026-10-01; 2.0.5 printed `Installed` for two). Check that each
  folder has files before trusting a run.

The workaround is to clone each package at the tag `packages.yml` pins. The
evaluator's tags carry a `v`; the others do not (`git ls-remote --tags`,
2026-10-01, and 2026-10-08 for Elementary, whose package lives in
elementary-data/dbt-data-reliability):

```sh
cd pipeline/dbt
rm -rf dbt_packages && mkdir dbt_packages
git clone -q --depth 1 --branch 1.4.1  https://github.com/dbt-labs/dbt-utils             dbt_packages/dbt_utils
git clone -q --depth 1 --branch 0.14.1 https://github.com/dbt-labs/dbt-codegen           dbt_packages/codegen
git clone -q --depth 1 --branch v1.4.0 https://github.com/dbt-labs/dbt-project-evaluator dbt_packages/dbt_project_evaluator
git clone -q --depth 1 --branch 0.26.0 https://github.com/elementary-data/dbt-data-reliability dbt_packages/elementary
```

Then run `scripts/test.sh --no-dbt-deps`, which skips `dbt deps` (and so does
not empty the clones) and says so in its last line. Without the flag its
`dbt deps` empties them, and every later `dbt parse` then tries the download
again and empties them too (measured 2026-10-08), so clone again after one. `dbt parse` over the
clones finished in 645 ms on dbt-oss 2.0.5 and in under a second on 2.0.6
(measured 2026-10-01). **On dbt-oss 2.0.5 a build failed with hub.getdbt.com
unreachable although `dbt_packages/` was present**; on 2.0.6, with the
packages, the driver and spatial in place, parse and build passed with every
outbound connection refused (both measured 2026-10-01). `pipeline/ELT.md`
plans for the session-start hook to do this clone; until it does, do it by
hand. Read the tags from `packages.yml`, not from this file, when they move.

## Adding a club's staging models

The club's extract folder comes first: [the dlt skill](../dlt/SKILL.md), "Adding
a club". The extract layout pytest then requires a `stg_<club>__<type>` for
exactly the club's available types, `photos` included and `org` excluded.

**A club ArcGIS layer of a places, elevation, points-of-interest or
trail-lines type is generated, never hand-written, and never committed**:
`python generate_dbt.py` from `pipeline/` runs `make_dbt_staging.py` (decision
54) and `generate_notice_models.py`, and every place that parses the project
runs it first (decision 91, the maintainer's poll of 2026-10-06). Commit the
registry or extract edit alone; git ignores what the generators write
(`pipeline/dbt/.gitignore`, and the exact list `make_dbt_staging.py` writes to
`models/.gitignore`). The pull request diff no longer shows the SQL a registry
edit produces, so run the script and read the files it names. It reads the layer's key from its `sources.json` row
(`key_fields`, else `id_fields`, else `id_field`; `geometry` in a list is
the shape) and stops, naming the row, when there is none or the key holds a
server row id. It writes the source block with its `duplicates_are_exact`
test, the base model (dates in `date_fields` cast from epoch milliseconds),
one `stg_<club>__<type>` per folder and type, the type's
`int_<type>__unioned`, and the region each source is held to
(`macros/generated_regions.sql`). `pipeline/tests/test_dbt_generated_staging.py`
holds that both generators write the same bytes in either order and over their
own output, that git ignores all of it, and that no committed file is theirs;
the pipeline suite will not start without the generated tree
(`tests/conftest.py`). A rule a
layer needs beyond its key, such as a historic alignment that may not route
or a road a trail layer carries, is a row of the `layer_rules` seed, read by
the type's intermediate, never an edit to a generated file; a point's POI
type is a row of the `club_poi_types` seed, an allowlist by the code the
layer lands, which `int_points_of_interest__club_points` applies, and a
`layer_rules` hold wins over any mapping. The steps
below are for everything else.

1. **`staging/<club>/_<club>__sources.yml`** declares every raw table dlt
   writes for the club (`raw_<club>__<key>`), each with a description, v2's
   `config:` block holding `loaded_at_field: _loaded_at` and `freshness`,
   `meta.cadence`, and an explicit `database:`. A closures or warnings
   source measures from the run log instead, `loaded_at_query: "{{
   last_read_or_confirmed_at(this) }}"`, with its job's tag (decision 100,
   [the trap above](#contracts-and-the-traps-in-them)). An unstaged
   declaration fails `fct_unused_sources`.
2. **One `base/base_<club>__<layer>.sql` per raw table the club extracts**,
   documented in `base/_<club>__base.yml`. A layer another folder extracts
   gets no base model here: the club's portion of it is rows in
   `int_<mart>__stewardship` (decision 34). dlt lands the geometry as `JSON` in DuckDB and
   `VARCHAR` in Parquet (measured 2026-10-01), so cast it before
   `st_geomfromgeojson`. Set CRS84, alias every column in lowercase, and give
   it its key and dedupe ([One key per table](#one-key-per-table)): measure the
   key first, on the live layer.
3. **One `stg_<club>__<mart>.sql` per available type**, conformed to the mart's
   columns so `union all by name` lines up. Renaming and the key only: the
   club's own review gate is a filter, and filters go in the club's
   intermediate (decision 40), never in staging and never in the union.
4. **`staging/<club>/_<club>__models.yml`** holds the club's model tests, in the
   club's own folder. Testing club models from one shared `staging.yml` is what
   gives today's 55 `fct_test_directories` findings.
5. **Add the club to `int_<mart>__unioned`**, and for POIs to
   `assert_int_points_of_interest__unioned_matches_staging_sum`, whose branch
   list is typed by hand on purpose.
6. **Give it a region box.** The lon/lat swap tests read each `source_key`'s
   box from the `regions` map in `macros/lands_outside_its_region.sql`; a key
   it does not list gets `eastern`, so a western or national source fails
   until it is given a row. A closures or warnings source is held in
   `int_closures__gate` instead, keeping its last good rows while the run goes
   red after publishing (decision 81). The three boxes were checked against the live
   layers' extents on 2026-10-03, and their margins are still `@unvalidated`
   (the macro's header says what would settle them).
7. **Run the job** ([above](#the-commands-ci-runs-today)), evaluator included:
   `scripts/test.sh`, with `--no-dbt-deps` in a sandbox.
