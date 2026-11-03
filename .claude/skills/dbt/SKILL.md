---
name: dbt
description: Work on the dbt project in pipeline/dbt/ - models, sources, seeds, tests, contracts, exposures, macros and the SQLFluff config. Use when adding or changing any of those, when adding a club's staging models, when the dbt job or SQLFluff fails in CI, or when dbt deps fails in a sandbox. Covers the layer names and the evaluator's rules, one key per table, row dates, contracts and the traps in them, SQL before an extension before Python, publication rules, state for pull requests, phone-file writers, test thresholds, Elementary's checks, the commands CI runs, and the dbt deps workaround.
user-invocable: true
---

# dbt in this repository

`pipeline/ELT.md` is the design: what runs, how data flows, the eleven marts and the rules they keep. This file is how to work on the dbt half of it.

**SQL first, then an extension, then Python**: core DuckDB SQL, then SQL with `spatial`, then a community extension, and a Python step only on a written reason ([below](#sql-first-then-an-extension-then-python)).

**dbt Labs' general plugin is enabled** in [`.claude/settings.json`](../../settings.json) as `dbt@dbt-agent-marketplace` (from `dbt-labs/dbt-agent-skills`). Ask it how selectors, unit tests, contracts and docs work in general. Several of its skills assume dbt Cloud, the dbt MCP server or the semantic layer; this project uses none of them. **Where the plugin and this file disagree, this file wins**: no Python models, unprefixed mart names, the jinja templater. [CLAUDE.md](../../../CLAUDE.md) wins over both. Its evidence grades bind every comment and description in a model, and models on the paths of its four harms (lost, out of water, in front of something dangerous, unable to get off the trail quickly) carry the strictest tests.

## What the project is

| | |
|---|---|
| dbt | **`dbt==2.0.6`**, the full distribution, one version everywhere (CI, `scripts/test.sh`, the lanes, the docs build). `dbt-oss` 2.0.5 is the documented fallback; the same project ran green on it. |
| DuckDB | Python's 1.5.5 writes the fixture warehouse; dbt reads it with its bundled 1.5.4, through an ADBC driver it downloads. |
| Packages | `dbt_utils` 1.4.1, `codegen` 0.14.1, `dbt_project_evaluator` 1.4.0, Elementary 0.26.0 (`packages.yml`). |
| Models | `base_` → `stg_` → `int_` → eleven unprefixed marts (some with a `_v2` beside them) → `pub_` writers. |
| Generated models | `python generate_dbt.py` writes them at build time; git ignores them. |
| Loader | dlt, under `pipeline/extract/` ([the dlt skill](../dlt/SKILL.md)). CI's warehouse is the extract in fixture mode over `make_dbt_fixtures.py`'s files. |
| Evaluator | enforced at `error`, exceptions only through its commented seed. |
| Lint | SQLFluff with the `jinja` templater is the enforced check; `dbt lint` is a fast first pass. |

## The order of work

1. **Decide where the rule lives**: core SQL, then an extension, then Python.
2. **Name the model by its layer**, and put it in that layer's folder.
3. **Write its YAML**: a description of the model and of every column (say what the data means, its units, and what null means), a key test, and on a mart a contract.
4. **Add the tests the rule needs**: generic, singular, and a unit test for any rule ported from Python.
5. **Run what CI runs** ([below](#the-commands-ci-runs-today)).
6. **Write the pull request's `## Data pipelines` section** from `scripts/pipelines.sh`, as CLAUDE.md asks.

## SQL first, then an extension, then Python

Take a step down only on a written reason (a measured failure, a missing function, or a parity unit test SQL cannot pass), and write that reason in the model's header comment.

1. **Core DuckDB SQL.**
2. **SQL with the `spatial` extension.**
3. **SQL with a community extension**: `h3`, `geography`, `a5`, `raster` all install and load on DuckDB 1.5.5 (measured 2026-10-01). Whether dbt 2.0.6 loads one from `profiles.yml` on its bundled 1.5.4 is `@unvalidated`; one CI run settles it. The fallback is a pre-hook `INSTALL … FROM community; LOAD …`.
4. **A Python step.**

**There are no dbt Python models.** dbt 2.0.6 refuses them on DuckDB ("Python models are not supported for duckdb adapter"); re-run that probe at each dbt bump. A Python rule runs as a step between dbt invocations, in `build_marts.py`'s `STEPS`:

- it reads named intermediates and writes a table in the `derived` schema;
- that table is a source, staged as `stg_derived__<thing>`, because an intermediate reading a source trips the evaluator's `fct_marts_or_intermediate_dependent_on_source`;
- an exposure named `step_<name>` on its inputs puts both halves in the docs, and tells a state build what the step reads.

**What `spatial` lacks on DuckDB 1.5.5**: `ST_ClusterDBSCAN`, `ST_ClusterIntersecting`, `ST_ClusterWithin`, `ST_Split`, `ST_Segmentize`, `ST_SnapToGrid`. `duckpgq` has no build for 1.5.5. Present, among others: `ST_LineLocatePoint`, `ST_LineInterpolatePoints`, `ST_LineSubstring`, `ST_LineMerge`, `ST_Node`, `ST_Simplify`, `ST_DWithin`, `ST_AsMVT`.

**Two traps in every geometry port**:

- **`ST_Distance_Sphere`, `ST_Distance_Spheroid` and `ST_DWithin_Spheroid` read x as latitude.** With (lon, lat) points a 30 m east–west pair at 41°N read 39.71 m (measured 2026-10-01). Measure metres after `ST_Transform(geom, 'EPSG:4326', 'EPSG:5070', always_xy := true)`, or call `ST_FlipCoordinates` first. A published length is geodesic: `macros/geodesic_length_m.sql`. Every port that measures a distance carries a unit test with a known 30 m pair in both directions.
- **Never call `ST_ReducePrecision` to get 6 decimals.** It removed 3 of 249,046 vertices from the published trail lines, which would misalign `trail_miles.json`'s per-vertex mile arrays. Round `x` and `y` per vertex.

## Layers and names

| Layer | Name | Folder | Does |
|---|---|---|---|
| base | `base_<steward>__<layer>` | `staging/<steward>/base/` | One `source()`, once per upstream dataset, in the folder that extracts it. Rename, cast, `st_setcrs(st_geomfromgeojson(geometry), 'OGC:CRS84')`, lowercase aliases, the key and the dedupe. No filter, no join. A line type that shares an hourly notices resource gets a second base model at its own cadence (`make_dbt_staging.py`, "A LANE COPY"). |
| staging | `stg_<club>__<mart>` | `staging/<club>/` | Conform to the mart's columns and carry the key. No filter: an org's review gate goes in its intermediate. |
| union | `int_<mart>__unioned` | `intermediate/<mart>/` | `union all by name`, no filter. |
| heavy | `int_<mart>__<verb>` | `intermediate/<mart>/` | Publication filter, dedupe, corridor, water distance, mile axis, graph, notice rules. |
| stewardship | `int_<mart>__stewardship` | `intermediate/<mart>/` | One row per (feature, org, basis, evidence). Assigns, never copies. |
| final | `int_<mart>__final` | `intermediate/<mart>/` | The mart's rows, every contracted column but the two row dates. |
| row history | `int_<mart>__history` | `snapshots/<mart>/` | A dbt snapshot of the final model. |
| mart | one of the eleven names | `marts/<mart>/` | `row_history_mart()`: the current rows and their two dates. Contract, `access: public`, exposures. |
| publish | `pub_<file>` | `publish/` | Writes one phone file. |

`<club>` is the extract folder name: `trail_orgs.json`'s `slug` with `-` written `_`. Non-org staging lives in `staging/registry/` (`sources.json`, `trail_orgs.json`, every org's catalogue row), `staging/derived/`, and one folder per shared source (`nws/`, `osm/`, `usgs/`, `opentrail/`, `podcasts/`, `ourhike/`).

**An org's share of another org's layer is an assignment, not a model of its own.** An org whose trail lives in USFS's layer has no base or staging model for it; its share is rows in `int_<mart>__stewardship`, by ATC's club-section polygons, the org's `trails` list in `trail_orgs.json`, or a name or id match. Dedupe in intermediates is only for independent datasets of the same ground; a republished copy is a `SAME_AS` note in extract and never reaches dbt.

**The eleven marts, exactly:** `trail_lines`, `points_of_interest`, `elevation`, `closures`, `warnings`, `podcasts`, `challenges`, `trail_network`, `places`, `suggested_hikes`, `sources`. Never `dim_` or `fct_`. The evaluator learns the names through a var, not an exceptions row (a `marts` row would switch naming off for every mart):

```yaml
# pipeline/dbt/dbt_project.yml
vars:
  dbt_project_evaluator:
    marts_prefixes: ['trail_', 'points_', 'elevation_', 'closures_', 'warnings_',
                     'podcasts_', 'challenges_', 'places_', 'suggested_', 'sources_']
```

The evaluator reads a prefix as the name's first word plus `_`, so `trail_` covers `trail_lines` and `trail_network`. `pub_` is in `other_prefixes` beside `rpt_`.

**Union by name, never by position.** A positional `select *` union once let a swapped `st_x`/`st_y` put every DEC lean-to in Antarctica on a green build. Keep the region tests anyway: a swap inside one base model still unions cleanly.

**Materializations.** `base_`, `stg_` and `int_<mart>__final` models are views. Unions and heavy intermediates are tables. Marts are contracted tables. Snapshots exist only for the row dates, one per mart. Add no incremental model and no other snapshot without the maintainer's say.

**Every source and exposure carries `meta.cadence`** (`hourly`, `daily`, `weekly`, `monthly`). Models are not tagged: a model's cadence is its fastest upstream source's. `build_marts.py`'s monthly lane builds what an untagged source feeds, so such a source is monthly in effect; give a new one its cadence anyway.

## One key per table

Every model has one key column, unique and not null. On every model that reads a `source()`:

- **The first column is the key**: `<what one row is>_key`, built with `{{ dbt_utils.generate_surrogate_key([...]) }}`. Its first input is the registry key as a literal (`"'dec_primitive_campsites'"`), so keys stay unique across the union. Then the upstream's own unique id (GlobalID, else the layer's object id), or the smallest set of current values measured unique, with `geometry_key('geom')` where no attribute tells two rows apart. Never a row's position in the file.
- **Measure the key before writing it**, on the live layer: `pipeline/spike_table_keys.py` finds the smallest unique set and counts exact copies. A field called an id is not proof: DEC's `ASSET_UID` names two different campsites four times over.
- **The model ends with `{{ dbt_utils.deduplicate(relation='renamed', partition_by='<key>', order_by='<order>') }}`.** dbt_utils has no DuckDB version and its default natural join drops every row holding a NULL, so `dbt_project.yml`'s `dispatch` block finds the project's `macros/duckdb__deduplicate.sql` (a `QUALIFY`) first. Never write a dedupe of your own, and never remove that dispatch block.
- **The raw table gets `duplicates_are_exact`** in `_<club>__sources.yml`, with the same key expressions. It fails the build when rows sharing a key differ, so a dedupe only ever removes exact copies.
- **The model's YAML** tests the key `unique` and `not_null`, and carries `equal_rowcount_to_raw` against its raw table: a warning when the dedupe removed any copy, an error once the copies are half the raw table.
- **Nothing else happens in that model**: renames, casts, the key, the dedupe. Classification literals, seed lookups and review gates are intermediate work.
- **A key of several columns** anywhere else is built with `generate_surrogate_key` too. Two closures models that cut areas keep their key test at warn, a recorded exception.
- `pipeline/tests/test_dbt_keys.py` checks all of this without a warehouse.

## Row dates: one snapshot per mart

Every mart row carries **`_first_seen_at`** and **`_changed_at`** (`timestamptz`, UTC). `macros/row_history.sql` has the macros.

- **A new mart** is three files and a YAML entry each:
  - `intermediate/<mart>/int_<mart>__final.sql` holds the mart's SQL;
  - `snapshots/<mart>/int_<mart>__history.sql` is `{{ config(unique_key='<key>') }}` and `{{ row_history_snapshot('int_<mart>__final') }}` inside a snapshot block;
  - `marts/<mart>/<mart>.sql` is `{{ row_history_mart('int_<mart>__history', 'int_<mart>__final', '<key>') }}`;
  - the contract declares both dates `timestamptz`, with `description: "{{ doc('row_first_seen_at') }}"` (and `row_changed_at`) and a not_null test whose severity is exactly `"{{ 'warn' if env_var('OURHIKE_ROW_HISTORY', 'on') == 'off' or env_var('OURHIKE_DATA_ENV', 'dev') in ['production', 'ua'] else 'error' }}"`.
  - Copy `closures`. `pipeline/tests/test_dbt_row_dates.py` fails until every piece is there.
- **A later version** (`<mart>_v2`) selects v1's two dates and gets no snapshot of its own.
- **Unit tests of a mart's logic** go on `int_<mart>__final`, where the SQL is.
- **The hash** covers every column but `_loaded_at` and the other load columns. A column that changes every run while the row does not goes in `row_history_snapshot()`'s `skip=[...]`, or every row reads as changed every run.
- **`_first_seen_at` equal to the history start means "at or before"**, never "new".
- **A removed row** stays in the snapshot with `dbt_valid_to` set and leaves the mart. `row_history_removed()` is the hook for merging removed features back; nothing reads it yet.
- **History lives outside the warehouse.** `build_marts.py` restores it before dbt and saves it after the writers (`pipeline/row_history.py`). Never force a cold start in a lane's workflow. List a store in `pipeline/row_history_stores.toml` once its first run has saved. Only the conditions legs pass `--history-on-failure degrade`, which builds the closures and warnings marts with null dates rather than stopping the hour.

## Publication is decided once, in SQL, before dedupe

- **`may_publish` has one home: `int_sources__publication`.** Every mart except `sources` keeps only rows whose source may publish. The rules are `pipeline/ELT.md`, "Who may publish". Null, `unstated` and `unresolved` are false; an absent licence is not permission. A restriction no class of `licence_restriction_phrases.csv` reads stays false.
- **The `public_use` rule has one home: `int_points_of_interest__publishable`.**
- **Publication filters run before dedupe.** A row that may not ship must never win a merge and then vanish, taking the place with it.
- No exporter and no writer re-decides any of this.
- **No rule names an org.** A rule a layer needs goes in a seed keyed by what the data says (`layer_rules.csv`, `club_poi_types.csv`, `notice_words.csv`, `notice_source_fields.csv`), and applies the same way to every source.

## Contracts, and the traps in them

Every mart is a contracted table (`contract: {enforced: true}`), `access: public`, with every column described. Intermediates are `protected`. Every mart carries `club`, `source_key` and `_loaded_at timestamptz`. `source_key` is tested with `dbt_utils.relationships_where` against `int_sources__publication`, `to_condition: may_publish`: a plain `relationships` test passes a row whose source is registered but held back.

| Trap | What to do |
|---|---|
| `geometry('OGC:CRS84')` refuses only a different, known CRS. It accepts a geometry with no CRS, and a `.duckdb` file never keeps one: a mart holding EPSG:5070 metres built green (measured 2026-10-01). | Every geometry mart carries a bounds test and a region test (`macros/lands_outside_its_region.sql`). |
| Column names are compared case-sensitively. | Alias every column in lowercase in the base model. |
| **Freshness on `_loaded_at` reads a quiet, healthy source as stale**: the extract stamps it only when a resource runs, so a source confirmed unchanged keeps a week-old stamp. | Every source's `loaded_at_query` is `"{{ last_read_or_confirmed_at(this) }}"`: the run log's newest `loaded` or `skipped` row. Monthly sources warn at 35 days and error at 62; hourly and notice sources use their job's hours. The Python steps' own tables, which no run log names, keep `_loaded_at`. `tests/test_source_freshness.py` holds every source to this. |
| `_loaded_at` is `TIMESTAMPTZ` on every dlt raw table. | Declare `timestamptz`. |
| A `foreign_key` constraint stops DuckDB dropping the referenced table on rebuild. | A relationships test instead. |
| dbt refuses `contract` on a snapshot. | `int_<mart>__history` has none; the mart's contract holds its columns. |
| **On 2.0.6 a contracted model with a `GEOMETRY` column fails at build** ("Failed to convert type BinaryView … not supported for DuckDB"). | Every contracted mart and writer carries **`geom_geojson varchar`**, RFC 7946 in OGC:CRS84 at the phone file's precision, tested to parse with `st_geomfromgeojson`. Keep `GEOMETRY` in uncontracted intermediates. |
| **A 2.0.6 unit test compares a `DOUBLE` only after rounding it to one decimal**: 3365.9 passed against 3365.936. | Carry a mile, distance, elevation or any must-match double as text (`varchar`, or JSON) in a unit-tested intermediate, and cast in the consumer. |
| A 2.0.6 unit test cannot hold a `GEOMETRY` or list column in a model's output. | WKT text for geometry, JSON text for a list. |
| A given or expected double is written as `CAST(<literal> AS double)`, read as a `DECIMAL` first: a 17-digit literal came back one ulp off. | Another reason to compare must-match numbers as text. |
| **On dbt's DuckDB 1.5.4, `ST_Intersects` against `GEOMETRYCOLLECTION EMPTY` segfaults the whole dbt process**; `ST_Union_Agg` over zero rows gives that collection. | Guard every intersect against an aggregated union with `having count(*) > 0` on the union. |
| **`dbt lint` reads `left join x on true` as the table `x` aliased `on`**, where SQLFluff parses it as a join condition. | Write the condition the joined CTE is already filtered on; run `dbt lint` beside SQLFluff before every push. |
| **dbt 2.0.6 refuses a config key it does not know** ("Ignored unexpected key", dbt1060). | A custom materialisation's own options go under `meta` (`config(meta={'when_empty': 'keep_last_file'})`). |
| DuckDB's `round(x, n)` rounds half away from zero on the scaled value; Python rounds the double's exact decimal value half to even. They disagreed on 14,125 of 266,800 test values. | A writer whose digits must match a Python exporter's uses `cast(printf('%.<n>f', x) as double)`, never `round()`. |

**Absent means unknown, never zero.** The safety fields in `pipeline/ELT.md`, "The eleven marts", are each a constraint or a test: `capacity is null or capacity >= 1`; `(water_distance_ft is null) = (water_distance_source is null)`; `elevation_ft` null where no DEM covers the point. Read that list before adding a column to a mart a hiker's safety turns on.

## The evaluator

- **Severity** comes from `+severity: "{{ env_var('DBT_PROJECT_EVALUATOR_SEVERITY', 'error') }}"`: `error` everywhere by default, `warn` only for a local survey.
- **No global `--warn-error`.** Name each error in `--warn-error-options`.
- **Coverage stays at 100.** Every model carries its key test and a description.
- **The exceptions seed** is `seeds/dbt_project_evaluator_exceptions.csv` (`fct_name, column_name, id_to_exclude, comment`), with `id_to_exclude` a SQL `LIKE` pattern. **Every `comment` carries its reason and an issue number with its full title**, and a pytest refuses a row without them. A row switches a rule off for every model its pattern matches, so fixing the model is usually the better answer. The two rows the design expects: `fct_too_many_joins` on `int_%__unioned` (one parent per org: union branches, not joins) and `fct_exposures_dependent_on_private_models` on `step_%` (a Python step inside the build).

## SQLFluff

`pipeline/.sqlfluff` keeps the `duckdb` dialect, ST06 off and RF04 ignoring `name` and `source`, each with its reason in the file's header. **The templater is `jinja`, in CI and locally**, with `apply_dbt_builtins = True`, `library_path = dbt/sqlfluff_libs` and `load_macros_from_path = dbt/macros`. `dbt/sqlfluff_libs/dbt_utils.py` renders the real dbt_utils from `dbt_packages/`, never a hand-written copy: it supplies only the dbt built-ins the package's macros call. Never add a macro body to it; if a new dbt_utils macro fails to render, the missing piece is a built-in it calls. It needs the packages and the generated models, so CI runs it last, after `generate_dbt.py`.

The jinja templater cannot see compiled `ref()` and `source()` relations, `var()` values or macro bodies; `dbt build` on the fixtures covers those.

**`dbt lint` is a fast, dbt-aware first pass, never the gate.** It catches some rules SQLFluff does and misses others (it passed a planted space before a comma that SQLFluff fails), so a clean `dbt lint` is not a clean lint. Run it after `dbt deps`: without `dbt_packages/` it installs the packages itself, which in a sandbox empties them.

## State, for a pull request

**A pull request builds only what changed since `main`'s last build**, in `pipeline-tests.yml`'s `dbt` job:

1. **A push to `main` keeps its build**: after a build that passed, the fixture warehouse and its manifest go to the Actions cache as `dbt-ci-base-<commit>`.
2. **A pull request decides before its fixture load** (`pipeline/state_base.py`): a state build only when the cache matched, every path `git diff` lists from that commit is one `state_base.RULES` lets through, and no macro's text differs from the cached manifest's. Anything else is the full build, said in one `::notice` naming what decided it.
3. **`build_marts.py --fixtures --state-base <main's target/>`** builds `state:modified`, every node that reads the clock, and what a Python step rewrote from a changed input, each with what it feeds. Every step and every writer still runs. No `--defer`: every other node is already in the warehouse. Its docstring has the rest.

What keeps a state build right:

- **A model that reads the clock says so in its SQL** (`now()`, `current_date` and their kin, found by `build_marts.CLOCK` in its code or any macro it calls). A date that reaches a model any other way would let main's copy answer with main's day.
- **A Python step names what it reads in its `step_<name>` exposure.**
- **A rule in `state_base.RULES` needs a measurement** that dbt's `state:modified` sees the change, or a reason no build reads the path. Macros, generic tests, `dbt_project.yml`, the packages, the extract, the fixtures, the generators and the steps build everything, because dbt 2.0.6's state comparison does not see what a dispatched override reaches; macros are compared by text instead.

**`check_contract_versions.py`** compares the pull request's manifest with the base's, parsed in a `git worktree` after its own `generate_dbt.py`. It fails on a removed column, a changed type, or a version dropped before its `deprecation_date`, unless the change arrives as a new model version.

**`--defer` needs `database:` on every source**, because sources are not deferred.

## Phone files are written last, and only locally

Each phone file is a `pub_<file>` model in `models/publish/`, materialized by `macros/materializations/phone_file.sql`, with an exposure (`type: application`) beside it in `_publish__*.yml` whose `meta` gives its R2 keys, format, coordinate decimals and cadence.

- **Writers run after every test has passed**, as a final selection, because `dbt build` tests a model after building it.
- **They write only under `var('processed_dir')`.** **dbt never writes the public bucket**: a DuckDB `COPY … TO 's3://…'` stored every object with no `Content-Encoding` and no `Cache-Control` (measured 2026-10-01). `publish.py` uploads.
- **Not dbt's `external`**: it writes snappy only, refuses `options` and `format='gdal'`, and writes an all-NULL row for an empty model.
- **Coalesce `features` to `[]`**: an empty closures file is a normal state.
- **`location` is a bare file name**; `COPY` creates no directory. The phone's key is the exposure's `meta.r2_keys`.
- **A writer is `access: public` with an enforced contract**, which `phone_file` asserts: a custom materialisation enforces none on its own.
- **A writer's family gets a `parity.py` row** and a CI step comparing it with today's exporter, until the exporter is deleted.

## Docs and charts are built, never committed

- **dbt docs publish at `https://docs.ourhike.org/data/`, never under `/app/`**: counts only, no maps, on a host of their own away from the app's sign-in. `pages.yml` and `pr-preview.yml` build them through `.github/actions/dbt-docs-site` against an empty warehouse, and `pipeline/check_docs_site.py` checks what they copy. Anything that links from the root must still work under `/data/` on any host (`.github/scripts/docs_host.py`).
- **No dbt Charts board exists.** `dbt-charts` 0.9.1, the newest release, requires `dbt-core<2` (read from PyPI 2026-10-15), and installing a second dbt is not allowed. **#1811 — Fast follows after PR #1805's dlt → dbt re-platform: the hiker's own download choice, the cutover, and what the port found in today's code** writes the boards once Charts runs on dbt 2. A board will read only `rpt_` models and never draw a map. Until then `/data/quality/` shows each mart's rows and checks.
- **Commit neither.** `target/`, `dbt_packages/` and `logs/` are gitignored, and so is the warehouse. Render anything into `target/`.

## The commands CI runs today

The `dbt` job in `.github/workflows/pipeline-tests.yml`, on Python 3.12, from `pipeline/`, with `DBT_ENGINE_SEND_ANONYMOUS_USAGE_STATS=false` on every step:

```sh
# restore ~/.cache/com.getdbt/adbc and ~/.duckdb/extensions/v1.5.4 (actions/cache, keyed on requirements-dbt.txt)
pip install --require-hashes -r requirements-dbt-build.txt
pip install --require-hashes --no-build-isolation -r requirements-dbt.txt      # dbt==2.0.6, sqlfluff, duckdb==1.5.5
python -m venv "$RUNNER_TEMP/extract" && "$RUNNER_TEMP/extract/bin/pip" install --require-hashes -r requirements-extract.txt
"$RUNNER_TEMP/extract/bin/python" generate_dbt.py      # the generated models; they import dlt
# restore dbt/dbt_packages (actions/cache, keyed on packages.yml and package-lock.yml)
cd dbt
dbt deps --profiles-dir .                              # only on a cache miss
dbt parse --profiles-dir .
dbt lint --profiles-dir .                              # the fast first pass, not the gate
cd ..
python check_contract_versions.py --head dbt/target/manifest.json --base <the base commit's manifest>
python -m venv "$RUNNER_TEMP/pipeline" && "$RUNNER_TEMP/pipeline/bin/pip" install -r requirements.txt
"$RUNNER_TEMP/pipeline/bin/pip" install "duckdb-extension-spatial==<that venv's duckdb version>"
"$RUNNER_TEMP/pipeline/bin/python" seed_spatial_extension.py
python make_dbt_fixtures.py
# a pull request: restore the dbt-ci-base-<commit> cache, then a state build or the full one
python state_base.py --matched-key <key> --base-dir "$RUNNER_TEMP/dbt-ci-base" --head-manifest dbt/target/manifest.json --warehouse data/warehouse.duckdb
"$RUNNER_TEMP/extract/bin/python" -m extract._fixtures --raw-dir data/raw --warehouse data/warehouse.duckdb
python build_marts.py --fixtures --python "$RUNNER_TEMP/pipeline/bin/python"   # + --state-base on a state build
"$RUNNER_TEMP/pipeline/bin/python" -m pytest tests/test_dbt_<...>_builds.py tests/test_dbt_notice_source_freshness_runs.py
"$RUNNER_TEMP/pipeline/bin/python" parity.py --json-dir data/processed/parity <family> --new data/processed/dbt/<file>
cd dbt
dbt source freshness --profiles-dir . --exclude tag:pdf_notice   # fixture mode lands no PDF
dbt docs generate --profiles-dir . --output-dir target/docs
python ../check_docs_site.py target/docs
DBT_PROJECT_EVALUATOR_SEVERITY=error dbt build -s package:dbt_project_evaluator --profiles-dir .
cd ..
sqlfluff lint dbt/models dbt/tests --processes 0       # the enforced lint, last
```

**A model that runs DuckDB out of memory beside others gets `tags=['builds_alone']`** in its own `config()`, with a comment naming the run that failed. `build_marts.py` then builds it alone between the rest of its stage and what it feeds. Not `--threads 1` for a whole lane.

**Telemetry off is the only switch.** `DBT_ENGINE_SEND_ANONYMOUS_USAGE_STATS=false` is the documented opt-out; `DO_NOT_TRACK=1` did not stop it (measured 2026-10-01). The dbt Product Licensing Agreement's §3.2 forbids disabling licence validation, so never set `DBT_SKIP_REMOTE_LICENSE` or any other undocumented switch, and leave alone the call to `public.cdn.getdbt.com` each command makes.

**`scripts/test.sh` runs the same steps as its dbt suite**, read from the job's own changed-paths step, with the fixtures and warehouse in a temporary directory. It installs nothing: it needs the `dbt` that `requirements-dbt.txt` pins first on `PATH`, and otherwise reports the suite SKIPPED. The session-start hook does not install it, so make a Python 3.12 virtualenv **outside the repository** (the session's scratchpad) and put it first. The files are hash-pinned; recompile either only with the `pip-compile --generate-hashes` command its header records:

```sh
python3.12 -m venv "$SCRATCH/dbtvenv"
"$SCRATCH/dbtvenv/bin/pip" install --require-hashes -r pipeline/requirements-dbt-build.txt
"$SCRATCH/dbtvenv/bin/pip" install --require-hashes --no-build-isolation -r pipeline/requirements-dbt.txt
PATH="$SCRATCH/dbtvenv/bin:$PATH" scripts/test.sh --no-dbt-deps   # after the clones below
```

## Every test's two thresholds

Every dbt test declares `warn_if` and `error_if`, and every source `warn_after` and `error_after`. `dbt_project.yml`'s comment above `data_tests:` is the design.

- **Write no `severity`.** `OURHIKE_DATA_ENV` is the switch: production and UA warn and build on, and `build_marts.py` reports a warning past its own `error_if` as an error, red after the publish; dev and CI (unset) stop. `severity: error` is for a gate that must hold what it reaches in every environment (a writer's test gets it from the `publish` folder). `severity: warn` only with `meta: {stays_at_warn: <who decided, and why>}`.
- **The six marts a hiker's safety reads are gates** (`marts:` in `dbt_project.yml`: closures, warnings, points_of_interest, elevation, trail_lines, trail_network), and so are the closures gate's own tests: errors everywhere, so in production a failure holds their files at their last copy. A singular test reading one of them writes `{{ config(severity='error') }}` itself.
- **Zero tolerance needs nothing**: the project's `warn_if: ">0"` and `error_if: ">0"` apply. A tolerance is a pair in the `>N` form, never dbt's `!= 0`.
- **A review aid that names rows is `rows_named`** (`tests/generic/`): a warning when any row is named, an error when every row is. A singular one returns `total_rows` beside its rows and calls `named_rows_level()` in its `config()`, with `meta: {scores_a_level: true}`.
- `pipeline/tests/test_dbt_test_thresholds.py` fails any test without both thresholds and parses the project as dev and as production; `tests/test_dbt_thresholds_builds.py` builds one failing test both ways.

## Elementary's checks, by hand

**Every Elementary check is tagged `elementary_check`**, carries `make_dbt_staging.py`'s `elementary_check_config()` for its kind, and runs in `build_marts.py`'s checks pass after the writers (`dbt test -s tag:elementary_check` at one thread, lane-scoped). Every dbt build before that pass leaves the tag out. The checks come from `make_dbt_staging.py`'s `raw_table_checks()` on every raw table (volume and schema) and from the marts' YAML.

**Two switches, and a check needs both**: `OURHIKE_ELEMENTARY=true` enables Elementary's models and hooks; `OURHIKE_ELEMENTARY_CHECKS=true` enables the checks. With the checks' switch alone they pass without querying anything.

**Elementary's tables first, or nothing is recorded.** `build_marts.py` runs `dbt run --select package:elementary` before `dbt seed`. By hand, from `pipeline/dbt/`, over a warehouse a fixture build made:

```sh
export OURHIKE_ELEMENTARY=true OURHIKE_ELEMENTARY_CHECKS=true
export DBT_ENGINE_SEND_ANONYMOUS_USAGE_STATS=false TZ=UTC
dbt run --select package:elementary --profiles-dir .
dbt test --select tag:elementary_check --threads 1 --profiles-dir .
```

Intersect the tag with another selector to run fewer (`tag:elementary_check,config.meta.cadence:hourly+`). Add `--vars '{"days_back": 400}'` to read a check as the monthly lane does. Results are in `elementary.elementary_test_results`; `OURHIKE_BUILD_STARTED_AT='YYYY-MM-DD HH:MM:SS' dbt build -s pub_data_quality --profiles-dir .` builds the page's file over them.

- **On a warehouse with no history every anomaly check passes** ("Not enough data to calculate anomaly scores"): no check can warn before its window holds 11 points. `row_history.py restore` brings a lane's history back.
- **A check on a raw table the warehouse does not hold errors.** `build_marts.py` leaves those out (`absent_sources()`).
- **No failing row is kept**: `test_sample_row_count` is 0. Never raise it; the hourly lane carries hikers' reports.
- **Never `edr`**, Elementary's CLI: it brings a second dbt and sends usage events.

## `dbt deps` in a sandbox

`dbt deps` cannot download packages here: codeload.github.com answers 403 or 500 through the sandbox proxy, and **dbt 2.0.6 prints `Installed 3 packages` while leaving every folder empty**. Check each folder has files before trusting a run. Clone each package at the tag `packages.yml` pins instead (the evaluator's tags carry a `v`; read the tags from `packages.yml` when they move):

```sh
cd pipeline/dbt
rm -rf dbt_packages && mkdir dbt_packages
git clone -q --depth 1 --branch 1.4.1  https://github.com/dbt-labs/dbt-utils             dbt_packages/dbt_utils
git clone -q --depth 1 --branch 0.14.1 https://github.com/dbt-labs/dbt-codegen           dbt_packages/codegen
git clone -q --depth 1 --branch v1.4.0 https://github.com/dbt-labs/dbt-project-evaluator dbt_packages/dbt_project_evaluator
git clone -q --depth 1 --branch 0.26.0 https://github.com/elementary-data/dbt-data-reliability dbt_packages/elementary
```

Then run `scripts/test.sh --no-dbt-deps`, which skips `dbt deps` and says so. Without the flag `dbt deps` empties the clones, and every later `dbt parse` tries the download again and empties them too, so clone again after one. With the packages, the ADBC driver and spatial in place, dbt 2.0.6 parses and builds with every outbound connection refused.

## Adding a club's staging models

The org's extract comes first: [the dlt skill](../dlt/SKILL.md), "Adding a club". The extract layout pytest then requires a `stg_<club>__<type>` for exactly the org's available types, `photos` included and `org` excluded.

**A layer of a places, elevation, points-of-interest, trail-lines or notices type is generated, never hand-written, and never committed**: `python generate_dbt.py` from `pipeline/` runs `make_dbt_staging.py` and `generate_notice_models.py`. Commit the registry or extract edit alone, then run the script and read the files it names, since the diff will not show them. It reads the layer's key from its `sources.json` row (`key_fields`, else `id_fields`, else `id_field`) and stops, naming the row, when there is none or the key is a server row id. It writes the source block with its `duplicates_are_exact` test, the base model, one `stg_<club>__<type>`, the type's union, and each source's region (`macros/generated_regions.sql`). `pipeline/tests/test_dbt_generated_staging.py` holds that both generators write the same bytes in either order, that git ignores all of it, and that no committed file is theirs.

**A rule a layer needs beyond its key is a seed row, never an edit to a generated file**: a historic alignment that may not route, or a road a trail layer carries, is a row of `layer_rules.csv`; a point's POI type is a row of `club_poi_types.csv`, an allowlist by the code the layer lands; a notice source's columns are a row of `notice_source_fields.csv`. A `layer_rules` hold wins over any mapping.

For anything hand-written:

1. **`staging/<club>/_<club>__sources.yml`** declares every raw table dlt writes for the org (`raw_<club>__<key>`), each with a description of what the data is, a `config:` block holding `loaded_at_query: "{{ last_read_or_confirmed_at(this) }}"` and a `freshness` with both `warn_after` and `error_after`, `meta.cadence`, and an explicit `database:`. An unstaged declaration fails `fct_unused_sources`.
2. **One `base/base_<club>__<layer>.sql` per raw table the org extracts**, documented in `base/_<club>__base.yml`. dlt lands geometry as `JSON` in DuckDB and `VARCHAR` in Parquet, so cast it before `st_geomfromgeojson`. Measure the key first, on the live layer.
3. **One `stg_<club>__<mart>.sql` per available type**, conformed to the mart's columns. Renaming and the key only.
4. **`staging/<club>/_<club>__models.yml`** holds the org's model tests, in its own folder.
5. **Add the org to `int_<mart>__unioned`**, and for POIs to `assert_int_points_of_interest__unioned_matches_staging_sum`, whose branch list is typed by hand on purpose.
6. **Give it a region box.** The region tests read each `source_key`'s box from `macros/lands_outside_its_region.sql`; a key it does not list gets `eastern`, so a western or national source fails until it has a row. A closures or warnings source failing it is held in `int_closures__gate` instead, keeping its last good rows while the run goes red.
7. **Run the job** ([above](#the-commands-ci-runs-today)): `scripts/test.sh`, with `--no-dbt-deps` in a sandbox.
