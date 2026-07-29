# dbt transform layer — design & rollout plan

Companion to [../TECHNICAL_ARCHITECTURE.md](../TECHNICAL_ARCHITECTURE.md) and [README.md](README.md). **Status: designed 2026-07-29, not yet built** — this document is the plan (the technical component's design plus a phased rollout), written before the code per this project's usual pattern (see [FEATURES.md](../FEATURES.md)/[ROADMAP.md](../ROADMAP.md)'s design-doc-before-code convention). Phase A below is the first implementation step, not yet started.

## Why dbt, and why now

The pipeline currently fetches raw ATC/opentrail data to GeoJSON files and processes it ad hoc in Python + DuckDB spatial scripts (`spike_corridor.py`, `spike_raster_mosaic.py`, `export_pmtiles.py`). That's worked for proving the pipeline out, but it doesn't scale as OurHike adds trails beyond the AT (value #7 — built to be inherited by another club, not just NYNJTC/the AT): every new trail would mean more one-off scripts, no shared tested transform layer, and no principled place for `ROADMAP.md`'s currently-open "Unified POI schema" item (joining ATC + opentrail POI data into one schema) to live.

dbt adds a real **T** to this pipeline's data flow, turning it into a proper **extract-load-transform (ELT)** architecture:

- **Extract** — unchanged: `fetch_all.py`, `fetch_opentrail.py`, `fetch_topo_quads.py` keep pulling raw upstream data to `data/raw/*`, exactly as today.
- **Load** — new: a small script loads that already-fetched raw data into DuckDB tables (a `raw` schema) *before* any transformation happens — raw data lands in the warehouse first, untouched, so every transform downstream is reproducible from a known starting point and nothing gets silently reshaped on the way in.
- **Transform** — new, owned entirely by dbt: staging → intermediate → marts SQL models, tested and documented, turning raw tables into the clean, trusted outputs the rest of the pipeline (and eventually the client) consumes.

**Deliberately excluded: raster pixel data.** USGS topo quad GeoTIFFs (~14GB across ~1,654 files) stay exactly where they are — files on disk, handled by `fetch_topo_quads.py`/`fix_corrupted_quads.py`/`spike_raster_mosaic.py`/`export_pmtiles.py` unchanged. Loading raster bytes into DuckDB would buy nothing dbt needs (dbt's job here is tabular/attribute cleaning, not raster processing) and would work directly against value #8 (boring, low-maintenance — a multi-gigabyte DuckDB file is a much heavier thing to move around and back up than one that holds only attribute/vector data). Only a lightweight *metadata* table (quad URL, local path, last-modified — no pixels) is planned to load, so dbt can document/test *coverage* ("every registered quad has a manifest entry") without the warehouse ever holding raster bytes.

## Project structure

Planned layout, following dbt's standard staging/intermediate/marts convention:

```
pipeline/
  load_raw.py              # Extract-Load: raw/*.geojson etc. -> DuckDB `raw` schema
  data/warehouse.duckdb     # gitignored, same as everything else under data/
  dbt/
    dbt_project.yml
    packages.yml           # dbt_utils, dbt_project_evaluator, codegen
    package-lock.yml        # committed - real resolved versions
    profiles.yml            # DuckDB file path only, no credentials - safe to commit
    models/
      staging/
        atc/                # one _<source>__sources.yml per source system,
        opentrail/          # descriptions sourced from sources.json/upstream metadata
      intermediate/
      marts/
        core/
    seeds/
      poi_type_mapping.csv  # ATC/opentrail source codes -> one unified poi_type
    macros/
    tests/singular/
  .sqlfluff
  requirements-dbt.txt
```

**Naming/materialization conventions:** `stg_<source>__<entity>` (staging, one dbt `source()` in, light rename/cast/typing only, materialized as a view), `int_<entity>_<verb>` (intermediate, joins/unions business logic, view), `dim_`/`fct_` prefixes in marts (final, tested, documented, materialized as a table). Each layer gets its own DuckDB schema (`staging`, `intermediate`, `marts`) via a standard `generate_schema_name` macro override, since everything lives in one DuckDB file rather than separate databases.

**Where dbt docs' text comes from — nothing invented.** Every source/model description is meant to be transcribed from metadata this project already has, not authored from scratch:
- `sources.json`'s `title`/`notes`/`discovered_via`/`discovered_date` fields → source-level yml descriptions.
- `fetch_opentrail.py`'s `ICON_LEGEND` dict (the documented meaning of opentrail's `c`/`s`/`o`/`j`/`w`/`t`/`r`/`a` waypoint codes) → the `poi_type_mapping` seed's labels, and an `accepted_values` test on the raw `icon` column so an undocumented code appearing upstream fails loudly instead of silently passing through unmapped.
- Real ArcGIS field names/aliases, once reachable — via `dbt-codegen`'s `generate_source`/`generate_base_model` macros run against the real loaded raw tables (see Phase B; this environment's network policy blocks live ArcGIS/USGS access, so it couldn't be done as part of this design pass).

## The first vertical slice (Phase A)

Rather than migrating all ~12 registered ATC sources at once, Phase A targets one small, real, end-to-end slice that directly delivers `ROADMAP.md`'s open "Unified POI schema" item for a subset of sources:

```
stg_atc__shelters  ─┐
stg_atc__campsites ─┼─→ int_pois_unioned ─→ dim_pois
stg_opentrail__waypoints ─┘
```

`stg_opentrail__waypoints` resolves its raw `icon` code to a `poi_type` via the `poi_type_mapping` seed; the two ATC staging models tag their `poi_type` directly (`'shelter'`/`'campsite'`). `int_pois_unioned` is a plain `union all` into common columns; `dim_pois` adds a stable surrogate key (`dbt_utils.generate_surrogate_key(['source', 'source_id'])`).

**Explicitly not attempted in Phase A:** cross-source deduplication (a shelter appearing in both ATC and opentrail data isn't merged — `dim_pois` stays 1:1 with its inputs, which also keeps the row-count reconciliation tests below meaningful), and wiring `dim_pois` into the actual export step (`export_pmtiles.py`) — the mart lives inside the warehouse for now, export wiring is later work.

**Honesty note on column names:** this design couldn't reach ArcGIS's live metadata from this environment, so any staging-model column names referenced in Phase A implementation (e.g. illustrative names like `Shelter_Name`, `Trail_Club`) should be treated as placeholders until reconciled against the real fetched data's actual field names via `dbt-codegen` — see Phase B.

## Testing strategy

Two kinds of tests, both required:

- **Per-column generic tests** (mostly from `dbt_utils` — see below): `unique`/`not_null` on id and type columns, `dbt_utils.accepted_range` on latitude/longitude, `dbt_utils.expression_is_true` asserting `st_isvalid(geom)`, `accepted_values` on opentrail's raw `icon` column against the full documented legend, and a `relationships` test tying `dim_pois.poi_type` back to the `poi_type_mapping` seed (catches an unmapped type leaking through without hardcoding the domain twice).
- **Transformation-accuracy tests** — the specific ask that data stays accurate *through* the transformation, not just correct at the edges: a singular test per layer boundary (`assert_int_pois_unioned_matches_staging_sum.sql`, `assert_dim_pois_matches_int_pois_unioned.sql`) that fails if a layer's row count doesn't exactly match what its inputs should produce — catching a silently broken `union all` branch or an accidental filter, the kind of gotcha this project's `TESTING.md` already treats as a first-class regression risk.

A known duplication risk gets a real test, not just a comment: `poi_type_mapping.csv`'s opentrail rows mirror `fetch_opentrail.py`'s `ICON_LEGEND` dict by hand, so a Python-side test (`pipeline/tests/test_dbt_seed_sync.py`, added alongside the seed in Phase A) asserts the two stay in sync, failing CI the moment they drift instead of silently going stale.

## Documentation strategy

`dbt docs generate` produces the browsable model/column/lineage documentation from the yml files described above. Two things make this trustworthy rather than decorative:
1. Every source and model gets a description and every column that matters gets tested — undocumented/untested models are exactly what `dbt_project_evaluator` (below) flags.
2. Descriptions are transcribed from real upstream metadata already in this repo (`sources.json`, `ICON_LEGEND`), not invented, so the generated docs say something true.

## The three required packages

| Package | Version (verified real, via GitHub tags — dbt Hub registry itself wasn't reachable from this environment) | Purpose here |
|---|---|---|
| `dbt-labs/dbt_utils` | 1.4.1 | Generic tests (`accepted_range`, `expression_is_true`) and `generate_surrogate_key` for `dim_pois`'s primary key. |
| `dbt-labs/dbt_project_evaluator` | 1.3.2 | Project-structure/convention linting — undocumented models, untested models, naming, fanned-out sources. Run as its own `dbt build -s package:dbt_project_evaluator` step, kept separate from the data-test build so "did my data pass" and "does my project follow conventions" stay independently readable in CI. |
| `dbt-labs/codegen` | 0.14.1 | Bootstraps `sources.yml`/staging model stubs from real loaded tables — the sanctioned way both Phase A's initial slice and every future source (Phase B/D) get scaffolded, rather than hand-typing column lists. |

## SQL over Python, with a real precedent for the exception

Transform logic is SQL by default. The one documented exception this project already has is worth following as the rule, rather than inventing an abstract one: `export_pmtiles.py` originally tried corridor/tile intersection as one DuckDB query per candidate tile, killed it after 2 minutes with zero output, and fell back to a plain Python/shapely loop that finishes in seconds — a measured, documented failure, not a preference. The same bar applies here: SQL first, Python only when DuckDB genuinely can't do it or a measured attempt shows it's the wrong tool — and any such exception gets documented the same way, not silently reached for.

## Linting

SQLFluff, `dbt` templater, `duckdb` dialect (confirmed available). Config lives at `pipeline/.sqlfluff`. Unlike `ruff`'s deliberately narrowed rule set for the Python side (see `pipeline/pyproject.toml`), SQLFluff's default rule set isn't the same kind of maximalist surprise — Phase A implementation should run it for real against the actual models first and prune noisy rules only if they turn out to be, rather than pre-narrowing blind.

## CI (planned)

A new `dbt` job in `.github/workflows/pipeline-tests.yml`, alongside the existing `pytest` job — sharing the workflow's trigger block, but its own isolated runner/Python version. dbt tends to lag the newest CPython release (the existing `pytest` job already runs bleeding-edge Python 3.14), so the `dbt` job pins **Python 3.12** deliberately, not as an oversight. Planned steps: install `requirements-dbt.txt` → generate tiny synthetic raw fixtures on disk (small, code-generated GeoJSON, matching this project's existing "no committed binary fixtures, no real network/large data in CI" testing philosophy) → `load_raw.py` → `dbt deps` → `sqlfluff lint` → `dbt seed` → `dbt build` (run+test) → `dbt source freshness` → `dbt docs generate` → `dbt build -s package:dbt_project_evaluator`. Like `pytest` today, this job is not (yet) a required status check — see Phase C.

One freshness caveat worth being upfront about: `dbt source freshness` here measures "how recently did `load_raw.py` last run," not real upstream ATC/opentrail staleness — `load_raw.py` re-stamps its `_loaded_at` column every run regardless of whether the underlying fetch actually found new data. Real upstream change-detection already exists and lives in the fetch scripts (`dataLastEditDate` checks, ETag/If-None-Match) — this is a complementary, narrower signal, not a replacement, and the docs/CI messaging should say so plainly (value #4 — honest about what a signal actually means, not just that one exists).

## Rollout plan

- **Phase A — scaffold + first vertical slice (next implementation step, not started).** `load_raw.py`, the dbt project scaffold, the `stg_atc__{shelters,campsites}` + `stg_opentrail__waypoints` → `int_pois_unioned` → `dim_pois` slice above, its tests, the seed + sync test, `.sqlfluff`, `requirements-dbt.txt`, the new CI job, and `pytest` coverage for `load_raw.py` — all following this project's existing testing conventions (`tmp_path`, synthetic fixtures built in test code, no real network beyond the already-sanctioned one-time DuckDB spatial-extension install).
- **Phase B — reconcile against real data, expand coverage.** Once `fetch_all.py`/`fetch_opentrail.py`/`load_raw.py` have run for real, use `dbt-codegen` against the actual loaded raw tables to correct Phase A's illustrative column names, then add staging models for the remaining ATC sources as each is actually fetched (`parking`, `viewpoints`, `communities`, `trail_club_sections`, `side_trails`, `half_mile_points_from_springer`, `centerline`, `bridges`, `privies`, `at_treadway`). Decide whether/how to deduplicate POIs that appear in both ATC and opentrail data (explicitly deferred, not attempted in Phase A).
- **Phase C — CI gating.** Once the `dbt` job has run clean for a while, promote both it and `pytest` to required branch-protection checks together — mirroring `pytest`'s own current non-required status rather than jumping ahead of it. Consider publishing `dbt docs generate`'s static output somewhere browsable (not decided).
- **Phase D — the pattern for a second trail.** This is the growth case the whole design is aimed at. `sources.json` already carries a `provider` field, and the planned `load_raw.py` table naming (`raw_<provider>__<key>`) and staging naming (`stg_<provider>__<key>`) already generalize past AT-only assumptions — a new trail's sources become new rows in a registry and new staging models following the same pattern, not a parallel pipeline. The one thing worth a deliberate check at that point (value #7): revisit any place Phase A hardcoded an AT-only assumption (e.g. `poi_type` literals, the `poi_type_mapping` seed's vocabulary) to confirm nothing quietly baked in "the AT" where "a trail" was meant.

## Open scope boundaries worth restating

- Not touched by this design: `spike_corridor.py`, `spike_raster_mosaic.py`, `export_pmtiles.py`, or any raster/export logic. `dim_pois` is a warehouse-internal mart in Phase A; wiring it into the actual GeoJSON/PMTiles export step is future work.
- Not attempted: cross-source POI deduplication.
- Not yet updated: `pipeline/README.md`'s and `TESTING.md`'s how-to/testing sections stay describing today's pipeline until Phase A's code actually lands — updating them to describe unbuilt commands would be misleading in the meantime.
