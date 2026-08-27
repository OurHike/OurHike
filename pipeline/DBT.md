# dbt transform layer — design & rollout plan

Companion to [../TECHNICAL_ARCHITECTURE.md](../TECHNICAL_ARCHITECTURE.md) and [README.md](README.md). **Status: designed 2026-07-29; all four phases built.** Phase A 2026-08-18 and Phases C+D 2026-08-27 under **#100 — Build the dbt ELT transform layer before NYNJTC's own trail network arrives**; Phase B 2026-08-18 under **#99 — Expand the unified POI schema beyond its first slice**. The rollout plan at the bottom now records what each phase actually did rather than what it intended to do.

One Phase B item collapsed into Phase A: the staging models were built against the **real fetched layers' field names** (the implementing session had the live data on disk), so the "illustrative column names" honesty note below is history rather than a live caveat — `GlobalID`/`Name` and `dbid`/`title`/`icon` are the real names, verified against a full real-data load (2,352 rows in `dim_pois`, all 37 build tests green).

**What Phase C+D moved.** Both columns were measured on 2026-08-27, on the tree before and after the change — **against the synthetic CI fixtures, not a real fetch.** That is a real limit and it is why the "before" figures do not match Phase B's own (which counted 4,433 real rows): this environment has no fetched data at all, so the row counts below are the fixtures' and only the structural counts mean anything about the build. Phase D's staging column names come from `sources.json`'s recorded live measurements instead — see Phase D below for the dates.

| | before (Phase B tree) | after (Phase C+D) |
|---|---|---|
| raw tables loaded | 13 | 28 |
| staging models | 13 | 27 |
| source systems in `dim_pois` | 2 (ATC, opentrail) | 3 (+ NYS DEC) |
| `int_pois_unioned` branches | 7 | 13 |
| `dbt build` nodes | 93 (77 data tests) | 145 (115 data tests) |
| `dbt_project_evaluator` warnings | 2 | 5 |
| required status checks | 5 | 6 (`dbt` added) |

`dbt docs generate` reports **100% documentation coverage across all 29 models** and **79.31% test coverage (23 of 29)**; the six untested models, and each of the three new evaluator warnings, are named and argued for under Phase D.

## Why dbt, and why now

The pipeline currently fetches raw ATC/opentrail data to GeoJSON files and processes it ad hoc in Python + DuckDB spatial scripts (`spike_corridor.py`, `render_cell_tiles.py`, `assemble_raster.py` — the raster chain that replaced `export_pmtiles.py` in 2026-08). That's worked for proving the pipeline out, but it doesn't scale as OurHike adds trails beyond the AT (value #7 — built to be inherited by another club, not just NYNJTC/the AT): every new trail would mean more one-off scripts, no shared tested transform layer, and no principled place for `ROADMAP.md`'s currently-open "Unified POI schema" item (joining ATC + opentrail POI data into one schema) to live.

dbt adds a real **T** to this pipeline's data flow, turning it into a proper **extract-load-transform (ELT)** architecture:

- **Extract** — unchanged: `fetch_all.py`, `fetch_opentrail.py`, `fetch_topo_quads.py` keep pulling raw upstream data to `data/raw/*`, exactly as today.
- **Load** — new: a small script loads that already-fetched raw data into DuckDB tables (a `raw` schema) *before* any transformation happens — raw data lands in the warehouse first, untouched, so every transform downstream is reproducible from a known starting point and nothing gets silently reshaped on the way in.
- **Transform** — new, owned entirely by dbt: staging → intermediate → marts SQL models, tested and documented, turning raw tables into the clean, trusted outputs the rest of the pipeline (and eventually the client) consumes.

**Deliberately excluded: raster pixel data.** USGS topo quad GeoTIFFs (~14GB across ~1,654 files) stay exactly where they are — files on disk, handled by `fetch_topo_quads.py`/`fix_corrupted_quads.py`/`render_cell_tiles.py`/`assemble_raster.py` unchanged. Loading raster bytes into DuckDB would buy nothing dbt needs (dbt's job here is tabular/attribute cleaning, not raster processing) and would work directly against value #8 (boring, low-maintenance — a multi-gigabyte DuckDB file is a much heavier thing to move around and back up than one that holds only attribute/vector data). Only a lightweight *metadata* table (quad URL, local path, last-modified — no pixels) was ever planned to load, and it still has not been built — nothing in Phases A–D needed it, so dbt can document/test *coverage* ("every registered quad has a manifest entry") without the warehouse ever holding raster bytes.

## Project structure

The layout as built, following dbt's standard staging/intermediate/marts convention. `models/staging/` now holds one directory per source system — `atc/`, `opentrail/`, and Phase D's `nynjtc/`, `oprhp/`, `mohonk/`, `dec/` — each with its own `_<source>__sources.yml`:

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
        nynjtc/             # Phase D: the non-A.T. organizations, whose raw
        oprhp/              # files land in data/raw/external/ rather than
        mohonk/             # data/raw/ - fetch_external_layers.py's own
        dec/                # on-disk boundary, carried rather than flattened
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

**Explicitly not attempted in Phase A:** cross-source deduplication (a shelter appearing in both ATC and opentrail data isn't merged — `dim_pois` stays 1:1 with its inputs, which also keeps the row-count reconciliation tests below meaningful), and wiring `dim_pois` into the actual export step (`export_poi.py`) — the mart lives inside the warehouse for now, export wiring is later work.

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

Transform logic is SQL by default. The one documented exception this project already has is worth following as the rule, rather than inventing an abstract one: the raster export of the time (`export_pmtiles.py`, since replaced by `lib/raster_tiles.py`'s one-warp chain — the measurement predates the rewrite and stands) originally tried corridor/tile intersection as one DuckDB query per candidate tile, killed it after 2 minutes with zero output, and fell back to a plain Python/shapely loop that finishes in seconds — a measured, documented failure, not a preference. The same bar applies here: SQL first, Python only when DuckDB genuinely can't do it or a measured attempt shows it's the wrong tool — and any such exception gets documented the same way, not silently reached for.

## Linting

SQLFluff, `dbt` templater, `duckdb` dialect (confirmed available). Config lives at `pipeline/.sqlfluff`. Unlike `ruff`'s deliberately narrowed rule set for the Python side (see `pipeline/pyproject.toml`), SQLFluff's default rule set isn't the same kind of maximalist surprise. Phase A ran it for real and pruned on that evidence — two prunes, reasons in `.sqlfluff` itself: ST06 (column order), because the staging models feed a positional `union all` and their column order is a semantic contract, and RF04 for `name`/`source` only, because those are `lib/poi_schema.py`'s own unified record keys. Everything else runs at defaults and passes.

## CI (built)

A `dbt` job in `.github/workflows/pipeline-tests.yml`, alongside the existing `pytest` job — sharing the workflow's trigger block, but its own isolated runner/Python version. dbt tends to lag the newest CPython release (the existing `pytest` job already runs bleeding-edge Python 3.14), so the `dbt` job pins **Python 3.12** deliberately, not as an oversight. The steps, in order: install `requirements-dbt.txt` → generate tiny synthetic raw fixtures on disk (small, code-generated GeoJSON, matching this project's existing "no committed binary fixtures, no real network/large data in CI" testing philosophy) → `load_raw.py` → `dbt deps` → `sqlfluff lint` → `dbt seed` → `dbt build` (run+test) → `dbt source freshness` → `dbt docs generate` → `dbt build -s package:dbt_project_evaluator`. Every one of those steps is real and runs; this job became a required status check on 2026-08-27 — see Phase C.

One freshness caveat worth being upfront about: `dbt source freshness` here measures "how recently did `load_raw.py` last run," not real upstream ATC/opentrail staleness — `load_raw.py` re-stamps its `_loaded_at` column every run regardless of whether the underlying fetch actually found new data. Real upstream change-detection already exists and lives in the fetch scripts (`dataLastEditDate` checks, ETag/If-None-Match) — this is a complementary, narrower signal, not a replacement, and the docs/CI messaging should say so plainly (value #4 — honest about what a signal actually means, not just that one exists).

## Rollout plan

- **Phase A — scaffold + first vertical slice (built 2026-08-18, #100).** `load_raw.py`, the dbt project scaffold, the `stg_atc__{shelters,campsites}` + `stg_opentrail__waypoints` → `int_pois_unioned` → `dim_pois` slice above, its tests, the seed + sync test, `.sqlfluff`, `requirements-dbt.txt`, the new CI job, and `pytest` coverage for `load_raw.py` — all following this project's existing testing conventions (`tmp_path`, synthetic fixtures built in test code, no real network beyond the already-sanctioned one-time DuckDB spatial-extension install).
- **Phase B — reconcile against real data, expand coverage (built 2026-08-18, #99).** Every registered ATC layer is now staged against its real fetched field names (verified by loading the live fetch and reading `information_schema.columns`, not guessed): four more POI layers (`viewpoints`, `parking`, `privies`, `communities`) widen `int_pois_unioned`/`dim_pois` from three sources to seven (2,352 → 4,433 rows on the 2026-08-18 fetch), and six infrastructure layers (`bridges`, `centerline`, `side_trails`, `trail_club_sections`, `half_mile_points_from_springer`, `at_treadway`) get attribute-only staging models — geometry processing stays in the Python spatial scripts, per this document's scope. `bridges` is staged but deliberately NOT unioned: whether a bridge is a hiker-facing POI type is a product call (#99 records it as open), written into the `poi_type_mapping` seed as an empty-`poi_type` row so the decision is greppable rather than implicit. Cross-source deduplication remains explicitly deferred (nothing observed in the 4,433 rows forced the question; it belongs with export wiring).
- **Phase C — CI gating (built 2026-08-27, #100 — Build the dbt ELT transform layer before NYNJTC's own trail network arrives).** The `dbt` job is now declared a required status check in [`.github/expected-protections.yml`](../.github/expected-protections.yml), with the reason in that file's own voice. Three things are worth recording rather than assuming:

  - **`pytest` was already required**, so the "promote both together" instruction above resolved to promoting one. The pairing argument was about not jumping ahead of `pytest`; `pytest` went first, and this is the other half arriving late.
  - **The `merge_group:` precondition was verified rather than trusted.** `pipeline-tests.yml`'s trigger block is shared by both jobs and carries `merge_group`, which is the property `expected-protections.yml` insists on before any check may be required — a workflow without it *hangs* a queue entry rather than failing it. `.github/tests/test_repository_protections.py` re-checks it from the checkout on every pull request; the suite runs green (333 passed, 12 skipped, 2026-08-27).
  - **The check name is the bare job id `dbt`**, because that job has no `name:` and no matrix. It also carries no job-level `if:` — the scoping lives in its steps — so a pull request touching nothing under `pipeline/dbt/` still reports success having done nothing, which is the property that makes requiring it safe rather than a trap.

  **Flipping the actual GitHub setting is a human action** and has not been done here: `expected-protections.yml`'s own header says no API this repository can reach will make it. What landed is the declaration and the test that holds it to the workflows. Publishing `dbt docs generate`'s static output somewhere browsable is still undecided and still not done.
- **Phase D — the pattern for a second trail (built 2026-08-27, #100 — Build the dbt ELT transform layer before NYNJTC's own trail network arrives).** The growth case the whole design is aimed at, and the phase that found out how much of the design actually generalized. Fifteen non-A.T. layers now load and fourteen are staged, across four organizations: NYNJTC, NYS OPRHP, Mohonk Preserve and NYS DEC.

  **What the trigger was.** On 2026-08-25 the maintainer removed the geographic ring that had been clipping the non-A.T. layers (**#1019 — A survey's proposed ring decides which of NYS Parks' and NYNJTC's trails ship, and DEC's ship not at all**, in the maintainer's own words: *"There shouldnt be a ring around NYC. Include all of DEC, NYNJTC & NYSP. Don't limit data from orgs based on geography."*), and the exported trail network went from **4,002 features to 21,805**, measured either side of that change against the same fetched layers (`export_nearby_trails.py`, `NYC_SOURCE_SURVEY.md` §1). `pipeline/dbt/` still staged ATC and opentrail only. All four of the other organizations' trail lines were by then being fetched and exported — `nearby_trails.geojson` holds 21,805 features out of 22,286 read, 7.3 MB gzipped, measured on a live fetch 2026-08-25 — while the warehouse could not see one row of any of them — the "second parallel ad hoc pipeline" #100 exists to prevent, arriving by omission rather than by anybody deciding on it.

  **The A.T.-assumption audit this bullet used to ask for, and what it found.** Three real bake-ins and one clean bill of health:

  1. **`load_raw.py`'s registry filter was the whole defect.** It selected `kind is None`, which is the twelve A.T. layers and only those; every other organization's layer carries `kind: external_arcgis_layer`. It now asks `lib/source_registry.py` for both ArcGIS kinds, the same split the fetchers use. That module's own comment had already predicted this exact moment — "load_raw.py's kind filter keeps them out of the warehouse the same way, until #100's staging models take them deliberately."
  2. **`_provider_slug` collapsed a provider to its first word**, which was right while every provider was `ATC` and wrong the moment two New York State agencies registered: `NYS OPRHP` and `NYS DEC` both slug to `nys`. Measured against the live registry 2026-08-27 — 33 entries, 9 distinct providers, exactly one first-word collision (`NYS OPRHP` and `NYS DEC`), spanning 12 of the 33 entries. Not a name clash (the key keeps the table unique) but a table named after the state on the layers that decide whether a hiker sees a lean-to. Replaced by an explicit `PROVIDER_SLUGS` table that **raises** on an unmapped multi-word provider, following `lib/source_registry.py`'s `POI_SOURCE_KEYS` precedent: a layer that turns out to differ should differ in a table, not somewhere clever.
  3. **The `poi_type_mapping` seed's `source_system` was a closed two-value domain**, `["atc", "opentrail"]` — the one place the Phase A slice genuinely encoded "the A.T." where "an organization" was meant. Widened to include `dec`. It stays a closed list on purpose (an unlisted value is a typo, not a new organization), but adding one is now a one-line change.
  4. **Nothing was baked into the `poi_type` vocabulary, and this is now a checked claim rather than a hoped-for one.** All six `poi_type` values NYS DEC's registry entries declare — `shelter`, `campsite`, `viewpoint` ×3, `parking` — land inside `lib/poi_schema.py`'s existing `POI_TYPES` with no new type needed and no A.T.-specific term in the way. The `source` literals (`atc_shelters`, `dec_lean_tos`) were already organization-prefixed and generalized untouched, as did the `raw_<provider>__<key>` / `stg_<provider>__<entity>` naming, `generate_schema_name`, the layer materializations, and both reconciliation tests. That is the part of the design that worked.

  **One naming wart, recorded rather than fixed.** `sources.json` has one flat key namespace, so its non-A.T. keys already carry an org prefix — which makes the mechanical table name stutter: `raw_oprhp__oprhp_trails`, `raw_dec__dec_lean_tos`. Renaming the registry keys would end it and is a `sources.json` change rather than a dbt one, so it is not made here. Staging model names do not stutter, because a model name is a chosen entity rather than a key: `stg_oprhp__trails`, `stg_dec__lean_tos`.

  **`public_use`: one new column in the unified POI shape, carried and not applied.** DEC and OPRHP publish a public/internal flag and ATC and opentrail do not, so `dim_pois` gained a column that is each organization's own flag verbatim, null where an organization declares no such split. It is deliberately **not** filtered on. `export_nearby_poi.py` already drops DEC's `N` side (on the big backcountry layer that side is 13,823 culverts, gates and sign posts) with tests behind it, and re-implementing a safety filter in SQL beside the tested Python one is the second parallel pipeline this issue exists to prevent. The cost is real and belongs here rather than in a code comment: **a row in `dim_pois` is not a publishable POI**, and anything that ever exports from this mart must read `public_use` first.

  **Which sources were staged, and which were not.** Of the 33 registered sources, 27 are ArcGIS feature layers with fetchable per-feature GeoJSON; all 27 now load, and 26 are staged. The six that are not ArcGIS layers, plus the one loaded-but-unstaged layer, are each excluded for a stated reason:

  | Source | Why it is not staged |
  |---|---|
  | `oprhp_park_polygons` | Loaded, deliberately not staged — the only layer in that position. `sources.json` records a count (858 boundary polygons, 2026-08-18) and a last-edit date for it and **not one field name**, so a staging model would be a column list nobody has measured. Its CI fixture carries no properties either, for the same reason. Ends with one field-metadata read of the service. |
  | `atc_trail_updates` | Not a feature layer — a WordPress page whose build input is a file a human reviews and a merged pull request releases. There is no per-feature GeoJSON to load. |
  | `nynjtc_trail_alerts` | Same shape: notices read from a WordPress REST API. Its placement, dedup and voice questions are all open in `features/ORG_NOTICES.md`, and a warehouse table would freeze a schema nobody has decided on. |
  | `gatc_water_sources` | A club PDF whose licence is **unstated** — fetched for review and cross-checks only until GATC answers a redistribution ask. Its parsed rows arrive as fused strings by design (the PDF's text layer stores each printed row as one string, and `lib/club_pdfs.py` declines to split them by guesswork), so there is no column list to stage even if the terms were settled. |
  | `osm_water` | A Geofabrik extract, not an ArcGIS layer, and `sources.json` records no field list for it — only the four OSM tag selectors used to pick its 7,574 nodes. Staging it means inventing a column list. It is also a **water** source, where `export_poi.py` already applies a measured 25 m dedup against opentrail and a low-confidence tier; a second untested path to the same points is worth having only after the field list is measured. |
  | `usdm_drought` | A national weekly polygon file. The transform that matters is a **spatial clip** to a 10 km corridor, which this document's scope explicitly leaves in the Python/DuckDB spatial scripts — and the artifact's meaning depends on the WEEK, which lives in the filename rather than in the rows, so a raw table would lose the one thing that makes the claim checkable. |
  | `usgs_3dhp` | Nothing fetches it. The registry entry holds a watch, not data; there is no file to load. |

  **What the staging models refuse to say, which is the part worth reading.** Every column staged is a name `sources.json` records as measured against the live layer with a date; where a layer's fields are not recorded, the model stages what is evidenced and stops. Concretely: `stg_oprhp__trail_closures` has **two columns**, because two field names are all that were ever measured for a closure layer; `stg_oprhp__trails` stages two blaze columns rather than the three the layer has, because only two were written down; `stg_nynjtc__highlands_trail` has **no blaze column at all**, because the layer publishes none and `'Unknown' as blaze` would turn a stated absence into a value a join could match on; `stg_dec__lean_tos` has no capacity column, because DEC publishes none; and **six models carry no `source_id` at all** — NYNJTC's two, Mohonk's, and OPRHP's three — because no id field is recorded for any of those layers and `ST_Read`'s `OGC_FID` is GDAL's row number for one fetch rather than the organization's identity for the feature. Using it would survive every test in this project and renumber every row the next time an organization republished in a different order.

  **Two layers are staged and deliberately not unioned**, following the `stg_atc__bridges` precedent: `stg_oprhp__facilities` and `stg_dec__backcountry_features`. Neither declares a layer-wide `poi_type`, because neither has one — both are typed **per row** by `export_nearby_poi.py`'s value maps, each with its own allowlist and its own `NAMED_EXCLUSIONS`. OPRHP's facilities layer carries water (136 `Water Spigot` and 15 `Drinking Fountain` among its 158 `Sub_Asset` values, measured live 2026-08-27) and both of those values are held back there as a water holdback, no seasonal shutoff being recorded anywhere. Copying either map into SQL would give one product decision two homes.

  **What `dbt_project_evaluator` now says**, recorded because the run is warn-only and an unexplained new warning is how a convention check stops being read. It went from 2 warnings to 5, and every new one is a state argued for above:

  - `fct_missing_primary_key_tests`: **6** — exactly the six models with no recorded id column (`stg_nynjtc__long_path`, `stg_nynjtc__highlands_trail`, `stg_mohonk__trails`, `stg_oprhp__trails`, `stg_oprhp__trail_closures`, `stg_oprhp__facilities`). Ends when a field-metadata read gives them one.
  - `fct_unused_sources`: **1** — `raw_oprhp__oprhp_park_polygons`, loaded and unstaged, per the table above.
  - `valid_test_coverage`: **1** — 79.31% (23 of 29 models), which is those same six. Documentation coverage is 100%.
  - `fct_too_many_joins` (**1**) and `fct_test_directories` (**55**, was 33) were both already warning before Phase D and scale with model count; neither is a new decision.

## Open scope boundaries worth restating

- Not touched by this design: `spike_corridor.py`, `render_cell_tiles.py`, `assemble_raster.py`, or any raster/export logic. `dim_pois` is still a warehouse-internal mart after Phase D; wiring it into the actual GeoJSON/PMTiles export step is future work, and Phase D raised the price of doing it carelessly — the mart now holds rows their own publishing organization flags as internal, carried in `public_use` and not filtered out. **A row in `dim_pois` is not a publishable POI.**
- Not attempted: cross-source POI deduplication. Phase D did not force the question either — DEC splits by asset type where this schema splits by what a hiker walks to, so three DEC services land on `viewpoint`, and they stay three models with three `source` values rather than being merged.
- Not staged: geometry. Every non-A.T. line layer is staged for its attributes only, the same scope line `stg_atc__centerline_segments` has always followed; the spatial work stays in the Python/DuckDB scripts.
- `pipeline/README.md` and `TESTING.md` gained their dbt sections when Phase A landed, as this line used to promise.
