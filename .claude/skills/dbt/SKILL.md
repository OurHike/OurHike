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
`claude/intelligent-feynman-sw3ewm`. **Stage 1, the dbt tooling, is built on
that branch; the rest of `pipeline/ELT.md` is the intended state.** Most of
this file is that target, because that is what the branch is building. Check
which project you are in before you follow anything below.

| | `main` (read 2026-10-01 at 22e8a2be) | This branch, stage 1 built (2026-10-01) | Target (`pipeline/ELT.md`) |
|---|---|---|---|
| dbt | `dbt-core==1.12.2` and `dbt-duckdb==1.11.0`, pinned in `pipeline/requirements-dbt.txt` | **`dbt==2.0.6`**, the full distribution, one version everywhere (decision 32); `dbt-oss` 2.0.5 is the documented fallback, which ran the same project green. `dbt-duckdb` and `sqlfluff-templater-dbt` are gone | the same |
| DuckDB | `duckdb==1.5.5`, the same pin as `requirements.in` | Python's 1.5.5 writes the fixture warehouse, and dbt reads it with its bundled 1.5.4, through an ADBC driver it downloads (measured on a runner, 2026-10-01) | the same |
| Packages | `dbt_utils` 1.4.1, `dbt_project_evaluator` 1.3.2, `codegen` 0.14.1 (`packages.yml`) | evaluator 1.4.0 | the same |
| Models | `staging/<org>/` for `atc`, `dec`, `mohonk`, `nynjtc`, `opentrail`, `oprhp`; `intermediate/int_pois_unioned.sql`; one mart, `marts/core/dim_pois.sql` | the same models, with v2-shaped YAML, one `_<org>__models.yml` per org folder, a measured key on every model, and the mart renamed `marts/points_of_interest/points_of_interest.sql` (the maintainer's review: *"No dim_ !"*) | `base_` → `stg_` → `int_` → eleven unprefixed marts (below) |
| Loader | `load_raw.py` reads `data/raw/` into `data/warehouse.duckdb`'s `raw` schema | the same | dlt, under `pipeline/extract/` (see [the dlt skill](../dlt/SKILL.md)) |
| Evaluator | its own CI step, warn-only (`pipeline/DBT.md:184`) | enforced at `error`, with an 8-row exceptions seed | `error`, two exception rows |
| Lint | SQLFluff, `templater = dbt`, after the load and `dbt seed` | SQLFluff, `templater = jinja`, first in the job and enforced; `dbt lint` after `dbt parse` (decision 33) | the same |
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
| mart | one of the eleven names | `marts/<mart>/` | intermediates | contract, `access: public`, exposures |
| reporting | `rpt_<thing>` | `reporting/` | marts | counts for the docs page |
| publish | `pub_<file>` | `publish/` | the marts its exposure names | writes one phone file |

`<club>` is the club's extract folder name: `trail_orgs.json`'s `slug` with `-`
written `_`. That renames two of today's folders: `dec` becomes `nysdec` and
`oprhp` becomes `nysparks`. Non-club staging lives in `staging/registry/`
(`sources.json`, `trail_orgs.json`, every `org.py` row), `staging/derived/`,
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
for any of them. Whether `pub_` needs adding to `other_prefixes` beside `rpt_`
is `@unvalidated` until the first `pub_` model meets the evaluator.

**Union by name, never by position.** Today's `int_pois_unioned.sql` unions
positionally with `select *`. Under that union a swapped `st_x`/`st_y` in one
staging model put every DEC lean-to in Antarctica on a green build, `PASS=145`
(the header of `assert_pois_land_in_the_region_this_build_covers.sql`). Keep
that region test anyway: a swap inside one base model still unions cleanly.

**Materializations.** `base_` and `stg_` models are views. Unions and heavy
intermediates are tables. Marts are contracted tables. Whether snapshots or
incremental models join them is **an open question for the maintainer**
(decision 27), answered at the phase that ports the POI marts. Do not add a
snapshot or an incremental model before that answer. `closures` and `warnings`
stay `table` in every option.

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
  intermediate work. Today's POI staging models still carry `poi_type` and
  `confidence` literals; they move when stage 3 rebuilds staging.

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
| `_loaded_at` is `TIMESTAMPTZ` on every dlt raw table, though `extract/_run.py` stamps naive UTC | measured 2026-10-01, dlt 1.30.0 filesystem destination: 63 of 64 fixture-mode tables, and `_warehouse.py`'s proven-empty table was the 64th until it was made the same. `TIMESTAMP` was `load_raw.py`'s, measured on 1.12.2 | declare `timestamptz` |
| no `foreign_key` constraint | Reasoned: DuckDB refuses to drop a table a foreign key references, and every rebuild drops it | a relationships test instead |
| `primary_key` and `check` fail any build into DuckLake | measured 2026-10-01 on 2.0.5 | why the warehouse moves to DuckLake only at phase 4 |
| v2 refuses `contract` on a snapshot; a contracted incremental model must set `on_schema_change` | measured 2026-10-01 on 2.0.5 | matters only once decision 27 is answered |
| **On 2.0.6, a contracted model with a `GEOMETRY` column fails at build**: "Failed to convert type BinaryView ... not supported for DuckDB", from the contract's column check. The row above was measured on 2.0.5 and does not hold on 2.0.6 | measured 2026-10-02 on 2.0.6, the fixture warehouse, a closures mart (the cw worker), repro: any contracted `select st_point(1, 2) as geom` with `data_type: geometry`. An uncontracted model carries `GEOMETRY` fine | every contracted mart and `pub_` writer carries **`geom_geojson varchar`**, an RFC 7946 geometry in OGC:CRS84 at the phone file's precision, with tests that `st_geomfromgeojson` parses it. Keep `GEOMETRY` in uncontracted intermediates and convert at the mart, never earlier |
| **A 2.0.6 unit test compares a `DOUBLE` only after rounding it to one decimal place**: VARCHAR, integer and boolean compare exactly | measured 2026-10-02 on 2.0.6 by planting values in `expect` (the tl-at worker): 3365.9 and 0.44 passed against 3365.936… and 0.4004, and 4.0 against 3.985; 3365.96, 0.45 and 3.94 failed | carry a mile, a distance, an elevation or any must-match double as text (`varchar`, or JSON, which round-tripped 5,005 of 5,005 doubles exactly) in a unit-tested intermediate, and cast in the consumer. A unit test on a double safety field otherwise passes anything within about 0.05 |
| a 2.0.6 unit test cannot hold a `GEOMETRY` or a list column in a model's output: geometry panics ("BinaryView is not supported for DuckDB"), lists are refused ("Only primitive types ... supported for unit_testing") | measured 2026-10-02 on 2.0.6 (the tl-at worker) | WKT text for geometry (exact: DuckDB prints the shortest digits that read back to the same double), JSON text for a list |
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
  refuses a row without them. **Stage 1's seed holds 8 rows today**:
  `fct_too_many_joins` on `int_%unioned` (today's `int_pois_unioned`),
  `fct_unused_sources` on `raw_oprhp__oprhp_park_polygons`, and six
  `fct_missing_primary_key_tests` rows for the staging models with no
  recorded id. Each leaves with the stage that fixes it. The intended state
  is two rows, both citing
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
the packages, so it runs right after `dbt deps`. Never add a macro body to that
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
# deps there too (or the clones below), then:
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
  --help`, read 2026-10-01). The site build makes them.
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
`DBT_ENGINE_SEND_ANONYMOUS_USAGE_STATS=false` on every step. It ran green on
a runner in 46 s on 2026-10-01:

```sh
# restore ~/.cache/com.getdbt/adbc and ~/.duckdb/extensions/v1.5.4 (actions/cache, keyed on requirements-dbt.txt)
pip install -r requirements-dbt.txt                    # dbt==2.0.6, sqlfluff==4.3.0, duckdb==1.5.5
sqlfluff lint dbt/models dbt/tests                     # the enforced lint; needs no warehouse
cd dbt
dbt deps --profiles-dir .
dbt parse --profiles-dir .                             # the v2 gate
dbt lint --profiles-dir .                              # the fast first pass, not the gate
cd ..
pip install "duckdb-extension-spatial==$(python -c 'import duckdb; print(duckdb.__version__)')"
python seed_spatial_extension.py                       # Python's 1.5.5 only; dbt's 1.5.4 is cached, or dbt fetches it
python make_dbt_fixtures.py
python load_raw.py
cd dbt
dbt seed --profiles-dir .
dbt build --profiles-dir . --exclude package:dbt_project_evaluator
dbt source freshness --profiles-dir .
dbt docs generate --profiles-dir . --output-dir target/docs   # then checks index.html, assets/ and Parquet exist
DBT_PROJECT_EVALUATOR_SEVERITY=error dbt build -s package:dbt_project_evaluator --profiles-dir .
# save the cache on a miss, even when a step failed
```

**Telemetry off is the only switch.** `DBT_ENGINE_SEND_ANONYMOUS_USAGE_STATS=false`
is the documented opt-out. Measured 2026-10-01 through a logging proxy:
without it each 2.0.6 command tried (parse, show) opened `p.vx.dbt.com`; with
it parse, show and build opened none; and `DO_NOT_TRACK=1` did not stop it. The dbt Product Licensing Agreement's §3.2
forbids disabling licence validation or anything else that talks to dbt's
services, so never set `DBT_SKIP_REMOTE_LICENSE` or any other undocumented
switch, and leave alone the call 2.0.6 makes to `public.cdn.getdbt.com` once
per command.

The job runs only when its own changed-paths list matches: `pipeline/dbt/`,
`load_raw.py`, `lib/source_registry.py`, `make_dbt_fixtures.py`,
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
evaluator's tags carry a `v`; the other two do not (`git ls-remote --tags`,
2026-10-01):

```sh
cd pipeline/dbt
rm -rf dbt_packages && mkdir dbt_packages
git clone -q --depth 1 --branch 1.4.1  https://github.com/dbt-labs/dbt-utils             dbt_packages/dbt_utils
git clone -q --depth 1 --branch 0.14.1 https://github.com/dbt-labs/dbt-codegen           dbt_packages/codegen
git clone -q --depth 1 --branch v1.4.0 https://github.com/dbt-labs/dbt-project-evaluator dbt_packages/dbt_project_evaluator
```

Then run `scripts/test.sh --no-dbt-deps`, which skips `dbt deps` (and so does
not empty the clones) and says so in its last line. `dbt parse` over the
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

1. **`staging/<club>/_<club>__sources.yml`** declares every raw table dlt
   writes for the club (`raw_<club>__<key>`), each with a description, v2's
   `config:` block holding `loaded_at_field: _loaded_at` and `freshness`,
   `meta.cadence`, and an explicit `database:`. An unstaged declaration fails
   `fct_unused_sources`.
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
6. **Give it a region box.** The bounds and region tests read the club's box
   from `trail_orgs.json`'s `states`; a `national` row keeps the national
   bound. Every margin is `@unvalidated` until a pass over a live fetch reports
   each layer's real extent.
7. **Run the job** ([above](#the-commands-ci-runs-today)), evaluator included:
   `scripts/test.sh`, with `--no-dbt-deps` in a sandbox.
