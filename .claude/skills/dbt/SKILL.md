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

## Read this first: `pipeline/ELT.md` is a plan

`pipeline/ELT.md` is the design that issue's pull request adds, on branch
`claude/intelligent-feynman-sw3ewm`. **It describes the intended state, not
what is on `main`.** Most of this file is that target, because that is what
the branch is building. Check which project you are in before you follow
anything below.

| | Today, on `main` (read 2026-10-01 at 23fca25) | Target (`pipeline/ELT.md`) |
|---|---|---|
| dbt | `dbt-core==1.12.2` and `dbt-duckdb==1.11.0`, pinned in `pipeline/requirements-dbt.txt` (compiled on Python 3.12, which the job pins) | `dbt-oss==2.0.5`, one version everywhere (decisions 17 and 19). `dbt-duckdb` and `sqlfluff-templater-dbt` leave, because v2 bundles its own DuckDB driver and the templater needs dbt-core |
| DuckDB | `duckdb==1.5.5`, the same pin as `requirements.in` | v2 bundles 1.5.4. Whether that opens a file 1.5.5 wrote is `@unvalidated`; one CI run settles it |
| Packages | `dbt_utils` 1.4.1, `dbt_project_evaluator` 1.3.2, `codegen` 0.14.1 (`packages.yml`) | evaluator 1.4.0 |
| Models | `staging/<org>/` for `atc`, `dec`, `mohonk`, `nynjtc`, `opentrail`, `oprhp`; `intermediate/int_pois_unioned.sql` (a view); one mart, `marts/core/dim_pois.sql` | `base_` → `stg_` → `int_` → eleven unprefixed marts (below) |
| Loader | `load_raw.py` reads `data/raw/` into `data/warehouse.duckdb`'s `raw` schema | dlt, under `pipeline/extract/` (see [the dlt skill](../dlt/SKILL.md)) |
| Evaluator | runs as its own CI step, warn-only (`pipeline/DBT.md:184`): its findings never fail the job | `error` severity |
| SQLFluff | `templater = dbt`, run after the load and `dbt seed` | `templater = jinja`, first in the job |
| `scripts/test.sh` | runs neither dbt nor SQLFluff | runs the `dbt` job's steps in CI's order |

On any other branch the project is today's: a change must pass today's `dbt`
job on dbt-core 1.12.2. Do not write v2-only YAML into it.

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
   dbt-oss 2.0.5 loads a community extension from `profiles.yml`, and whether
   these four have builds for its bundled 1.5.4, are both `@unvalidated`; one
   CI run settles each. The fallback is a pre-hook
   `INSTALL … FROM community; LOAD …`.
4. **A Python step.**

**There are no dbt Python models here.** dbt-oss 2.0.5 refuses them: a
three-line `def model(dbt, session)` failed with `Internal Error: Python models
are not supported for duckdb adapter` (measured 2026-10-01, `pipeline/ELT.md`,
"SQL first, then an extension, then Python"). Re-run that probe at each dbt bump. A
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
| base | `base_<club>__<layer>` | `staging/<club>/base/` | one `source()` | rename, cast, `st_setcrs(st_geomfromgeojson(geometry), 'OGC:CRS84')`, lowercase aliases. No filter, no join |
| staging | `stg_<club>__<mart>` | `staging/<club>/` | that club's base models | conform to the mart's shape; apply the club's own review gate |
| union | `int_<mart>__unioned` | `intermediate/<mart>/` | every `stg_<club>__<mart>` | `union all by name`, no filter |
| heavy | `int_<mart>__<verb>` | `intermediate/<mart>/` | unions, intermediates, `stg_derived__*` | dedup, corridor, water distance, mile axis, graph |
| mart | one of the eleven names | `marts/<mart>/` | intermediates | contract, `access: public`, exposures |
| reporting | `rpt_<thing>` | `reporting/` | marts | counts for the docs page |
| publish | `pub_<file>` | `publish/` | the marts its exposure names | writes one phone file |

`<club>` is the club's extract folder name: `trail_orgs.json`'s `slug` with `-`
written `_`. That renames two of today's folders: `dec` becomes `nysdec` and
`oprhp` becomes `nysparks`. Non-club staging lives in `staging/registry/`
(`sources.json`, `trail_orgs.json`, every `org.py` row), `staging/derived/`,
and one folder per shared source (`nws/`, `osm/`, `usgs/`, `opentrail/`,
`podcasts/`, `ourhike/`).

**The eleven marts, exactly:** `trail_lines`, `points_of_interest`,
`elevation`, `closures`, `warnings`, `podcasts`, `challenges`,
`trail_network`, `places`, `suggested_hikes`, `sources`. Never `dim_` or
`fct_`. The maintainer: *"do not keep the dim_ and fct_ prefixes in the marts
folders. Just use the names I provided"*.

**The evaluator learns those names through a var**, not an exceptions row,
because a `marts` row would switch naming off for every mart:

```yaml
# pipeline/dbt/dbt_project.yml
vars:
  marts_prefixes: ['trail_', 'points_', 'elevation_', 'closures_', 'warnings_',
                   'podcasts_', 'challenges_', 'places_', 'suggested_', 'sources_']
```

The evaluator reads a prefix as `split_part(name, '_', 1) || '_'`, so `trail_`
covers both `trail_lines` and `trail_network`. Measured on 1.12.2 with the
first seven prefixes: passing, and failing `dim_pois`. On 2.0.5 it is
`@unvalidated` until the first evaluator run there. Whether `pub_` needs adding
to `other_prefixes` beside `rpt_` is `@unvalidated` the same way.

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

## Publication is decided once, in SQL, before dedup

- **`may_publish` has one home: `int_sources__publication`.** Every mart except
  `sources` keeps only rows whose source has `may_publish`; `sources` keeps
  every registered row, because it is where the flag is read. The flag is true
  only when the `licence_basis` is in the `publishable_licence_bases` seed
  **and** the row's own verdict says it ships (`reaches_hikers` in
  `sources.json`, or a `trail_orgs.json` `load` of `ship` or `via`). Null,
  `unstated` and `unresolved` are false. An absent licence is not permission.
  The whole rule, with the public-GIS presumption, the clearinghouse ruling,
  the batched licence question and the `refuse` orgs, is `pipeline/ELT.md`,
  "Who may publish".
- **The `public_use` rule has one home: `int_points_of_interest__publishable`.**
  `export_nearby_poi.py`'s `public_verdict()` and `confidence_for()` are
  deleted at cutover, not kept beside the SQL.
- **Publication filters run before dedup.** A row that may not ship must never
  win a merge and then vanish, taking the place with it.
- No exporter and no writer model re-decides any of this.

## Contracts, and the traps in them

Every mart is a contracted table (`contract: {enforced: true}`), `access:
public`, with every column described. Intermediates are `protected`. Every mart
carries `club varchar`, `source_key varchar` (with a relationships test to
`sources`) and `_loaded_at timestamp`.

| Trap | Evidence | What to do |
|---|---|---|
| `geometry('OGC:CRS84')` refuses only a *different, known* CRS. It accepts a geometry with no CRS, and a `.duckdb` file never keeps one | measured 2026-10-01 on 2.0.5: a mart holding EPSG:5070 metres built green | every geometry mart carries a bounds test (lon in [-180, 180], lat in [-90, 90], plus the club's own box from `trail_orgs.json`'s `states`) beside the lon/lat swap test |
| column names are compared case-sensitively | measured on 1.12.2: ATC's `Name` failed until aliased | alias every column in lowercase in the base model |
| `_loaded_at` is `TIMESTAMP`, not `TIMESTAMPTZ` | measured on 1.12.2; the value is naive UTC (`load_raw.py:201-206`) | declare `timestamp` |
| no `foreign_key` constraint | Reasoned: DuckDB refuses to drop a table a foreign key references, and every rebuild drops it | a relationships test instead |
| `primary_key` and `check` fail any build into DuckLake | measured 2026-10-01 on 2.0.5 | why the warehouse moves to DuckLake only at phase 4 |
| v2 refuses `contract` on a snapshot; a contracted incremental model must set `on_schema_change` | measured 2026-10-01 on 2.0.5 | matters only once decision 27 is answered |

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
  refuses a row without them. The intended state is two rows, both citing
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
True`, `library_path = dbt/sqlfluff_libs` (a two-line stub of
`dbt_utils.generate_surrogate_key`) and `load_macros_from_path = dbt/macros`.
On today's 32 files it took 2.0 s with 4 processes and found 0 violations
(measured 2026-10-01). It needs no warehouse, so it runs first.

The jinja templater cannot see compiled `ref()` and `source()` relations,
`var()` values or macro bodies; `dbt build` on the fixtures covers those.
Whether a project macro a model calls renders correctly under it is
`@unvalidated` until the first such macro is linted. ST06 comes back once the
last positional union is gone, since that union is its only stated reason.

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

The breaking-change check exited 2 on 1.12.2 (measured). On 2.0.5 `dbt build
--help` does not list `--warn-error-options`, though `dbt parse` accepts it, so
its exit there is `@unvalidated` until a probe drops a column. That
`state:modified+` reaches the exposures was measured on 2.0.5 (2026-10-01).
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
  `pipeline/data/processed/`. **dbt never writes the public bucket**: a
  DuckDB `COPY … TO 's3://…'` stored every object with no `Content-Encoding`
  and no `Cache-Control` (measured 2026-10-01 against a local S3 stand-in, not
  R2), and phones rely on both. `publish.py` uploads.
- **Not dbt's `external`**: on 2.0.5 it writes snappy only, refuses `options`
  and `format='gdal'`, and writes an all-NULL row for an empty model (measured).
- **Coalesce `features` to `[]`**: `list()` over zero rows writes
  `"features":null`, and an empty closures file is a normal state.

## Docs and charts are built, never committed

- **dbt docs publish at `https://ourhike.org/data/`, never under `/app/`**
  (decision 10: counts only, no maps). On 2.0.5 the output is `index.html`, 330
  assets (13 MB) and Parquet, and `--static` and `--empty-catalog` no longer
  exist (`dbt docs generate --help`, read 2026-10-01). The site build makes
  them.
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

The `dbt` job in `.github/workflows/pipeline-tests.yml`, on Python 3.12, from
`pipeline/`:

```sh
pip install -r requirements-dbt.txt
pip install "duckdb-extension-spatial==$(python -c 'import duckdb; print(duckdb.__version__)')"
python seed_spatial_extension.py
python make_dbt_fixtures.py
python load_raw.py
(cd dbt && dbt deps --profiles-dir . && dbt seed --profiles-dir .)
OURHIKE_WAREHOUSE=data/warehouse.duckdb sqlfluff lint dbt/models dbt/tests
cd dbt
dbt build --profiles-dir . --exclude package:dbt_project_evaluator
dbt source freshness --profiles-dir .
dbt docs generate --profiles-dir .
dbt build -s package:dbt_project_evaluator --profiles-dir .
```

The job runs only when its own changed-paths list matches: `pipeline/dbt/`,
`load_raw.py`, `make_dbt_fixtures.py`, `sources.json`, the two
`requirements-dbt` files, `pipeline/.sqlfluff`, the workflow and the
changed-paths action.

**`scripts/test.sh` runs none of this today.** It has no dbt or SQLFluff step,
and `scripts/suite_scopes.py`'s `scope_for` returns only the first
changed-paths step in a workflow, which in `pipeline-tests.yml` is the pytest
job's. `.claude/hooks/session-start.sh` does not install
`requirements-dbt.txt` either. So for a dbt change, make a Python 3.12
virtualenv **outside the repository** (the session's scratchpad), install
`requirements-dbt.txt` into it, run the block above by hand, and say in the
pull request that you did. In the target, `test.sh` runs the `dbt` job's steps
in CI's order: lint, deps, parse, breaking-change check, the extract layout
pytest, dlt fixture mode, the build, freshness and docs, the evaluator
(`pipeline/ELT.md`, "Running it").

## `dbt deps` in a sandbox

`dbt deps` cannot download packages here. Measured 2026-10-01 in this sandbox:

- `curl https://codeload.github.com/dbt-labs/dbt-utils/tar.gz/1.4.1` answers
  `403`, while `https://hub.getdbt.com/api/v1/dbt-labs/dbt_utils.json` answers
  `200`. The hub resolves the version; codeload serves the tarball.
- dbt-core 1.12.2 fails with "not a gzip file" (measured in the same planning
  research, 2026-10-01).
- dbt-oss 2.0.5 fails with `Failed to get tarball from
  https://codeload.github.com/…; status: 500`, **and prints `Installed` for
  `codegen` and `dbt_utils` while leaving both folders empty.** Check that
  each folder has files before trusting a run.

The workaround is to clone each package at the tag `packages.yml` pins. The
evaluator's tags carry a `v`; the other two do not (`git ls-remote --tags`,
2026-10-01):

```sh
cd pipeline/dbt
rm -rf dbt_packages && mkdir dbt_packages
git clone -q --depth 1 --branch 1.4.1  https://github.com/dbt-labs/dbt-utils             dbt_packages/dbt_utils
git clone -q --depth 1 --branch 0.14.1 https://github.com/dbt-labs/dbt-codegen           dbt_packages/codegen
git clone -q --depth 1 --branch v1.3.2 https://github.com/dbt-labs/dbt-project-evaluator dbt_packages/dbt_project_evaluator
```

With the evaluator at `v1.4.0`, `dbt parse` on dbt-oss 2.0.5 then finished in
645 ms (measured 2026-10-01). **v2 still asks hub.getdbt.com on every
invocation**, and a build failed with the hub unreachable although
`dbt_packages/` was present (measured 2026-10-01, `pipeline/ELT.md`, "Where data
lives between runs"). So the clones get a v2 run past codeload, not past an
unreachable hub. `pipeline/ELT.md` plans for the session-start hook to do this
clone; until it does, do it by hand. Read the tags from `packages.yml`, not
from this file, when they move.

## Adding a club's staging models

The club's extract folder comes first: [the dlt skill](../dlt/SKILL.md), "Adding
a club". The extract layout pytest then requires a `stg_<club>__<type>` for
exactly the club's available types, `photos` included and `org` excluded.

1. **`staging/<club>/_<club>__sources.yml`** declares every raw table dlt
   writes for the club (`raw_<club>__<key>`), each with a description, v2's
   `config:` block holding `loaded_at_field: _loaded_at` and `freshness`,
   `meta.cadence`, and an explicit `database:`. An unstaged declaration fails
   `fct_unused_sources`.
2. **One `base/base_<club>__<layer>.sql` per raw table**, documented in
   `base/_<club>__base.yml`. dlt lands the geometry as `JSON` in DuckDB and
   `VARCHAR` in Parquet (measured 2026-10-01), so cast it before
   `st_geomfromgeojson`. Set CRS84, alias every column in lowercase, key it on
   the layer's stable upstream id (`pipeline/ELT.md`, "Stable upstream keys").
3. **One `stg_<club>__<mart>.sql` per available type**, conformed to the mart's
   columns so `union all by name` lines up. The club's own review gate goes
   here, never in the union.
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
7. **Run the job** ([above](#the-commands-ci-runs-today)), evaluator included.
