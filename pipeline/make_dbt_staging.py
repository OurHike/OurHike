"""Write the dbt staging layer for the clubs' registered layers from the registry, and check it.

pipeline/ELT.md, "Loading everything the clubs publish": "dbt models are generated, not
hand-written, wherever a layer has a measured key: a `base_<folder>__<key>` per raw table from one template,
keyed and deduped on the key the live read found, and each mart's union reading the registry for its
branches." This is that template. Its output is not committed (the maintainer's poll of 2026-10-06):
every place that parses the dbt project runs it first, through generate_dbt.py, so a registry edit's models are
whatever this writes from that edit. tests/test_dbt_generated_staging.py holds that two runs write the same bytes.

    python make_dbt_staging.py           write every generated file, and delete a generated file it no longer writes
    python make_dbt_staging.py --check   write nothing; exit 1 naming each file on disk that would change

WHICH LAYERS (registry-driven, by kind, type and measured key). Every resource that a club folder's file for
one of TYPES extracts as an ArcGIS layer (extract/_kinds.py's ArcgisLayer), a GIS file (extract/_gis_files.py's
GisFile), a geographic API (extract/_ogc.py's OgcFeatures and JsonFeatures) or a club page's or PDF's points
(extract/_pages_points.py's PagePoints and extract/_pdf_points.py's PdfPoints), a sources.json row of a kind in KINDS, unless a hand-written model already reads its raw table: those keep their own (the registry tables
staged by hand). So a layer registered later is staged by running this again, and by nothing else.
A file that SHARES a sibling's resource (one upstream feeding two types, such as a My Map of trail lines and
trailheads) gets a staging model of its own over the sibling's base model, and no second base or source: one
raw table, staged once. An elevation file shares only a row that names its `elevation_source`.

A LANE COPY is the one exception, for a geometric type that SHARES a closures or warnings resource (NOTICE_TYPES):
NGPC's Cowboy Trail, whose 29-section status layer is both its closures and its line (the maintainer's choice,
2026-10-11). The resource is still one extraction, on the hourly lane its type puts it on, and
generate_notice_models.py stages that hourly copy. But a dbt node's lane is the fastest cadence among the sources
it reads (build_marts.py's docstring, "A LANE BUILDS ONLY ITS OWN NODES"), so a trail-line model reading the
notices' hourly source would take every trail-line node it feeds off the monthly lane, and the monthly warehouse
holds no hourly table. So the monthly lane lands its own copy of the table (extract/_run.py's ALSO_READS, which
tests/test_dbt_generated_staging.py holds every lane copy to), and this writes that copy a source table and a
base model of their own, at the sharing type's cadence: the source table named `<raw table>_<cadence>`, with
the raw table as its `identifier`, and its base model `base_<f>__<key>_<cadence>` (Table.lane_copy). Each lane's
nodes then read the copy that lane landed, and the notices' hourly path is untouched. The two source tables name
one relation, which dbt_project_evaluator's fct_duplicate_sources refuses unless
seeds/dbt_project_evaluator_exceptions.csv excepts it; its row says why.

Every base model reads its raw table through raw_or_empty() (dbt/macros/raw_or_empty.sql), so a layer that has
never landed (one the monthly extract refused on its first run, or a keyed API, `api_key_env`, whose key the job
lacks) reads as no rows with the columns its models name, and stops nothing else (Table.raw_columns()).

WHAT EACH sources.json ROW GIVES IT:
- THE KEY: `key_fields`, else `id_fields`, else `id_field`, where `geometry` in a list stands for
  the shape (macros/geometry_key.sql) and an empty `key_fields` is a one-row layer, keyed by the registry key
  and its shape (base_pcta__centerline's precedent: a key needs a column beside the registry key). A row with
  none of these, or whose key holds a server's row id (OBJECTID, FID: a reload mints them again), STOPS the
  run and is named, so no table is staged without a measured key.
- `date_fields`: the layer's esriFieldTypeDate fields, which land as epoch milliseconds (extract/_kinds.py's
  ESRI_TYPES, "the base model converts them") and are cast to timestamptz here, in UTC as ArcGIS stores them.
  A row without it has its dates, if it has any, left as the integers dlt landed.
- per type, the fields a staging model renames to the union's columns (SHAPES): `name_field` or
  `name_constant` and `category_field` for places, `elevation_source` for elevation, `name_field` or
  `name_constant` for trail lines, and `name_field`, `type_field` and the id a point publishes under
  (`id_field`, unless it is a server row id) for points of interest. A rule a layer needs beyond these (a
  historic alignment, a road a trail layer carries, a planned trailhead, a water type that is not water) is a
  row of the dbt/seeds/layer_rules.csv seed, which the type's intermediate reads, and a point's POI type is a
  row of dbt/seeds/club_poi_types.csv.

Column names are the registry's field names as dlt names them on landing (the `sql_ci_v1` convention
.dlt/config.toml sets, path by path), quoted where DuckDB reserves the word, so `DESC_` is `"desc"`.

WHAT IT WRITES, for each club folder <f> with such layers, under dbt/models/staging/<f>/:
- `_<f>__generated__sources.yml`: each raw table, with its duplicates_are_exact test on the model's own key and
  Elementary's checks (raw_table_checks()), which generate_notice_models.py writes on its raw tables too,
  and its freshness, read from the run log and held to MONTHLY_FRESHNESS_DAYS (LOADED_AT_QUERY).
- `base/base_<f>__<key>.sql` and `base/_<f>__generated__base.yml`: one base model per raw table.
- `stg_<f>__<type>.sql` and `_<f>__generated__models.yml`: one staging model per type, every layer of that
  type in the folder conformed to its union's columns, the layer's own columns kept whole as `properties`.
And per type, under dbt/models/intermediate/<type>/: the type's union (SHAPES' `union`: `int_<type>__unioned`,
or `int_points_of_interest__club_unioned` beside the hand-written int_points_of_interest__unioned that reads it)
and its YAML, a `union all by name` of every staging model this writes for the type. And `dbt/macros/generated_regions.sql`, the region box
each generated source's rows are held to (macros/lands_outside_its_region.sql).

Every file it writes opens with GENERATED, which is how it knows which files are its own. And `models/.gitignore`,
the list of every file it writes under models/, by exact path (IGNORE_LIST says why a list and not a pattern).

CONTENT TYPES: podcasts, suggested_hikes, challenges and photos, whose
rows are episodes, write-ups, list items and photo manifest rows from feeds, APIs, WordPress and a wiki, not ArcGIS
layers. Their shapes carry `geometry=False`: no geom, no CRS cast, no region box. The tables staged are those a club
file's content reader extracts (CONTENT_COLUMNS' readers, and NPS's lists by endpoint in NPS_COLUMNS), each keyed on
its row's measured `key_fields`; a hike type's taxonomy terms (SiteTerms) are a lookup, staged in base only and keyed
on (taxonomy, id). Each type's union is `int_<type>__club_unioned`, beside the path its mart reads today, and each
staging model leaves the source's prose (CONTENT_PROSE) out of `properties`, so a body stops at the base model.

PAGES AND PDFS: the content types a club publishes as web
pages (extract/_pages_content.py's ContentPages) and as PDFs (extract/_pdf_content.py's ContentPdf) are staged the
same way, keyed on each row's measured `key_fields`; their rows are facts by construction, so nothing is set aside
as prose. A PDF's table lands only where pypdf is installed, which is the extract job's venv and not fixture mode's
Python, so in the fixture build its base model reads no rows through raw_or_empty().
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import textwrap
from dataclasses import dataclass
from functools import cache
from pathlib import Path

PIPELINE = Path(__file__).resolve().parent
DBT = PIPELINE / "dbt"
MODELS = DBT / "models"
STAGING = MODELS / "staging"
INTERMEDIATE = MODELS / "intermediate"
REGIONS_MACRO = DBT / "macros" / "generated_regions.sql"
#: Git's ignore list of every file this writes under models/, one exact path a line, so none is committed (decision
#: 91). A list, not a pattern: its base and staging models share their folders and their `base_<f>__` and
#: `stg_<f>__` names with the hand-written ones (102 .sql there at 24da1f07), so no pattern could tell the two apart,
#: and a pattern that hid a hand-written model would leave it out of every commit. pipeline/dbt/.gitignore ignores
#: this file itself and the regions macro, which sits outside models/.
IGNORE_LIST = MODELS / ".gitignore"

GENERATED = "GENERATED by pipeline/make_dbt_staging.py"
SQL_MARK = f"-- {GENERATED} from sources.json\n-- and the extract's club folders; edit them or it, never this file.\n"
YAML_MARK = f"# {GENERATED} from sources.json\n# and the extract's club folders; edit them or it, never this file.\n"
JINJA_MARK = f"{{#- {GENERATED} from sources.json\n    and the extract's club folders; edit them or it, never this file. -#}}\n"

#: The registry kinds an ArcgisLayer reads, then the waves 2 and 3: a GisFile, an OgcFeatures and a
#: JsonFeatures (lib/source_registry.py's GIS_FILE, OGC_FEATURES and JSON_FEATURES), then waves 4 and 5's
#: PdfPoints and PagePoints (PDF_POINTS and PAGE_POINTS). Fixture mode cannot read a PDF, because the dbt job installs
#: no pypdf (requirements.in's note), so CI's warehouse never holds a pdf_points table: its base model reads the
#: absent table as no rows (macros/raw_or_empty.sql), and the build reads its rows only where the extract landed them
#: (Table.read_from_pdf).
PDF_POINTS_KIND = "pdf_points"
KINDS = (
    "club_arcgis_layer",
    "external_arcgis_layer",
    "gis_file",
    "ogc_features",
    "json_features",
    "page_points",
    PDF_POINTS_KIND,
)

#: The server row ids a key may never hold (a truncate-and-reload mints them again), as dlt names them.
#: `feature_index` is a feature's position in its file (extract/_gis_files.py), which a re-saved file renumbers.
ROW_IDS = frozenset({"objectid", "objectid_1", "objectid_12", "fid", "oid", "esri_oid", "ogc_fid", "feature_index"})

#: What duplicates_are_exact sets aside on a file's or an OGC collection's rows, beside macros/row_hash.sql's
#: row_hash_row_ids(): two copies of one feature differ in their position in the file (`feature_index`) and in
#: the id an exporter mints per feature (`feature_id`: Catamount's GeoJSON repeats a line under ids 52 and 53,
#: measured 2026-10-04), and in nothing else.
FILE_ROW_IDS = [
    "objectid",
    "objectid_1",
    "objectid_12",
    "oid",
    "esri_oid",
    "fid",
    "ogc_fid",
    "_dlt_id",
    "_socrata_id",
    "feature_index",
    "feature_id",
]
FILE_KINDS = frozenset({"gis_file", "ogc_features"})

#: The region every generated source's rows are held to. The widest of the three boxes
#: macros/lands_outside_its_region.sql draws, and still one that catches a swapped United States point (its
#: latitude would read -64 or less). @unvalidated as a fit: no generated layer's vertices had been read when
#: this was set, and a server's own extent is never the evidence (USFWS's answered lat -24.99 to 90 for vertices at 13.64 to 63.20). What settles each is its row of
#: int_<type>__source_extents on a live build, which names the narrowest box its vertices fit.
DEFAULT_REGION = "us_and_territories"

#: Types whose every layer already has its box decided in macros/lands_outside_its_region.sql, so the generator
#: gives them none. The trail-line rows (2026-10-03, cdaba599): that macro's map lists each one outside the eastern
#: box and its header says a row it leaves out sits inside it, so leaving one out is a decision, eastern, which a
#: generated box would widen. Those boxes were read off each layer's returnExtentOnly but one (usfws_trail_segments,
#: from its vertices), so int_trail_lines__source_extents is what checks them on a live build.
#: The point-of-interest rows the same way (2026-10-03, 643eecdf and a1c39d8c): that macro lists the 41 whose
#: points reach outside the eastern box, each boxed by every point of the layer read with outSR 4326, and its
#: header says a point row it leaves out has all its points inside the eastern box.
REGIONS_DECIDED_BY_HAND = frozenset({"trail_lines", "points_of_interest"})

#: The types whose resources generate_notice_models.py stages (its NOTICE_TYPES, which
#: tests/test_dbt_generated_staging.py holds this to: that module imports this one, so this one cannot import it). A
#: geometric type sharing one of their resources is a lane copy (the module docstring, "A LANE COPY").
NOTICE_TYPES = frozenset({"closures", "warnings"})

LINE = 76  # SQL comment width: SQLFluff's LT05 holds every line to 80

# --- Freshness, from the run log --------------------------------------------------------

#: Every extracted source's `loaded_at_query`, as dbt renders it: when OurHike's extract last read the table or
#: confirmed it unchanged, from the run log (macros/last_read_or_confirmed_at.sql), never a date of the source's own
#: and never `_loaded_at`, which a change check that finds the source unchanged leaves at the last load. Every source
#: in every lane uses it, so a quiet but healthy source does not read as stale. generate_notice_models.py writes it from here, and tests/test_source_freshness.py holds the hand-written
#: sources blocks to it.
LOADED_AT_QUERY = "{{ last_read_or_confirmed_at(this) }}"
#: HOW MANY DAYS A MONTHLY SOURCE MAY GO UNREAD before dbt's source freshness warns, and then errors (every
#: freshness check carries both). Both @unvalidated: the lead's pick of two missed monthly refreshes against
#: refresh-reference.yml's cron, `15 5 3 * *`, settled by how often a healthy monthly source passes 35 days over the
#: first season. What they do, Reasoned from that cron and from where the monthly lane measures them, once, in
#: build_marts.py's freshness run right after the build of the extract it pins: a source the month's extract read is
#: hours old there; one it missed once is 28 to 31 days old, and passes; missed twice, 59 to 62 days, and warns (it
#: errors only across two 31-day months); missed three times, 89 to 92 days, and errors. A rebuild from an older pin
#: (pipeline/ELT.md, "Rebuilding from a pin") reads older by the pin's age. generate_notice_models.py's
#: MONTHLY_WARN_DAYS, 7 and warn only, gave its one monthly notice source a number nobody derived, which measured more
#: than a week after a read would warn about three weeks of every month.
MONTHLY_FRESHNESS_DAYS = (35, 62)

# --- Elementary's checks on raw tables -----------------------------------------------------------

#: The tag every Elementary check carries, and no other test does: build_marts.py leaves the tagged tests out of
#: every dbt build and runs them in a pass of their own after the writers (its docstring, "ELEMENTARY'S CHECKS RUN
#: AFTER THE WRITERS"). tests/test_elementary_checks.py holds the tag and the severity on every check.
ELEMENTARY_CHECK = "elementary_check"
#: Every check exists only with a switch of its own on, OURHIKE_ELEMENTARY_CHECKS, which only build_marts.py sets: in a
#: build that runs the checks, for the two dbt commands that need them in the graph, Elementary's own tables (whose
#: dbt_tests table is where the data-quality file reads each check's lineage) and the checks pass (its CHECKS_SWITCH).
#: Every other command, the docs site, the evaluator and the pytest suites' builds carry none: enabled, the 1,979
#: checks cost each `dbt parse` about 5 s of CPU, and the hourly lane, which runs none, 59 s of CPU over the commit
#: before them, against 25 s with them disabled (measured 2026-10-08, build_marts.py's docstring, "ELEMENTARY'S
#: CHECKS RUN AFTER THE WRITERS"). Never on without Elementary's own switch (dbt_project.yml's OURHIKE_ELEMENTARY):
#: with it off, 0.26.0's exposure_schema_validity compiles to the text `None` and errors, and every other kind passes
#: having queried nothing (both measured 2026-10-08 on dbt 2.0.6). A test whose `enabled` renders false is no node of
#: the manifest (measured the same day in a scratch project).
ELEMENTARY_ENABLED = "{{ env_var('OURHIKE_ELEMENTARY_CHECKS', 'false') == 'true' }}"


#: ELEMENTARY'S CHECKS' TWO THRESHOLDS (the maintainer, 2026-10-15: "Every test should have both the
#: warning and error thresholds"; his "Build as proposed" took these). An anomaly check has one sensitivity, so its
#: `fail_calc` scores the rows Elementary returns, each carrying `is_anomalous`, `anomaly_score`, `metric_value` and
#: `training_avg` (0.26.0's get_read_anomaly_scores_query()), as a level: 1, a warning, where Elementary flagged a
#: point (past dbt_project.yml's anomaly_sensitivity of 3 deviations, and past an `ignore_small_changes` where a check
#: sets one); 2, an error, where that point is also past 6 deviations and more than 50% from its training average.
#: A schema change is a warning for an added column and an error for a removed or retyped one, the two a base
#: model's select or cast breaks on. Both expressions are dbt_project.yml vars, their one home, because a YAML config
#: is rendered with `var()` but no project macro. Measured on dbt 2.0.6 with Elementary 0.26.0 in a scratch project
#: (2026-10-15): after ten equal builds a row count doubled, and the level scored 1 at these bars and 2 with the
#: deviation bar at 2.9, a dbt warning and a dbt error, while ignore_small_changes at 25% passed a null rate moving
#: from 10% to 11% that warned without it; and one model built three times scored 0, then 1 with a column added,
#: then 2 with one removed, read off `test_sub_type`, the name 0.26.0's schema_changes gives the change in the rows it
#: returns. Each check is an error by severity in every environment: the checks pass is a `dbt test` after the
#: writers, where a failure skips nothing (measured the same day) and, in production and UA, never changes the run's
#: exit, so a level 2 there is a red row on the data-quality page and an error on the run
#: summary, and nothing more; in dev and CI, build_marts.py fails the job at its end. @unvalidated: 6 deviations and 50%
#: are the lead's picks, settled by the first season's errors. A lane whose window holds n builds cannot score past
#: (n - 1) / sqrt(n) deviations (dbt_project.yml's ELEMENTARY'S TRAINING AND DETECTION), so the monthly lane's 13
#: builds in 400 days can never reach 6 and its checks only ever warn (Reasoned).
ELEMENTARY_ANOMALY_LEVEL = "{{ var('elementary_anomaly_level') }}"
ELEMENTARY_SCHEMA_CHANGE_LEVEL = "{{ var('elementary_schema_change_level') }}"
#: The checks scored as an anomaly level; exposure_schema_validity keeps the project's zero tolerance, any column a
#: phone file reads missing or retyped being an error.
ANOMALY_CHECKS = ("volume_anomalies", "dimension_anomalies", "column_anomalies", "all_columns_anomalies")


def elementary_check_config(kind: str) -> dict:
    """An Elementary check's `config`, a new dict each call (so yaml.safe_dump writes no alias between checks), for
    `kind` (its name without `elementary.`): an error by severity, its two thresholds (above), tagged
    ELEMENTARY_CHECK, and enabled with the checks' own switch alone (ELEMENTARY_ENABLED). The keys are in the order a
    hand-written check writes them, which tests/test_elementary_checks.py compares."""
    config: dict = {"severity": "error"}
    if kind in ANOMALY_CHECKS:
        config.update(fail_calc=ELEMENTARY_ANOMALY_LEVEL, warn_if=">0", error_if=">1")
    elif kind == "schema_changes":
        config.update(fail_calc=ELEMENTARY_SCHEMA_CHANGE_LEVEL, warn_if=">0", error_if=">1")
    config.update(tags=[ELEMENTARY_CHECK], enabled=ELEMENTARY_ENABLED)
    return config


def raw_table_checks() -> list[dict]:
    """The Elementary checks one raw table carries, whatever its cadence, as items of its source table's `data_tests`
    (pipeline/ELT.md, "The checks, and where each goes"). The one home of them: both generators write these, and
    tests/test_elementary_checks.py holds every hand-written raw table to the same list.

    - volume_anomalies with no timestamp column: the table's rows at each build. Not rows per day by `_loaded_at`,
      which ELT.md names for the hourly sources: every raw table is loaded with write_disposition "replace"
      (extract/_run.py), so all of a table's rows carry its last load's stamp, and Elementary recounts the last two
      days' buckets from the table as it stands (0.26.0's get_metric_buckets_min_and_max treats a source as
      incremental), which would record 0 for each day before a reload. Reasoned from those two, not run.
    - schema_changes: a column added, dropped or retyped upstream, against the columns the last build recorded.

    NO FRESHNESS CHECK OF ELEMENTARY'S (the maintainer, 2026-10-15). freshness_anomalies on
    `_loaded_at` learned how long a source usually goes unchanged, since a change check that finds a source unchanged
    leaves its last load's stamp (ELT.md, "dlt configuration requirements"), and event_freshness_anomalies how long
    since a club last edited a notice: neither is how long since OurHike last read the source. On UA's hourly page of
    2026-10-15 04:38 UTC all 97 freshness warnings were event_freshness_anomalies, each first flagged by the first
    build after a 70.8-hour pause in OurHike's own hourly runs. Freshness is dbt's `source freshness` on each source's
    `loaded_at_query` (LOADED_AT_QUERY) alone, which build_marts.py runs before the data-quality file.
    """
    return [
        {"elementary.volume_anomalies": {"config": elementary_check_config("volume_anomalies")}},
        {"elementary.schema_changes": {"config": elementary_check_config("schema_changes")}},
    ]


def raw_table_checks_yaml(indent: int) -> list[str]:
    """raw_table_checks() as `data_tests` list items at `indent`, the way sources_yaml() writes its YAML."""
    pad, lines = " " * indent, []
    for check in raw_table_checks():
        ((name, body),) = check.items()
        lines.append(f"{pad}- {name}:")
        for key in ("arguments", "config"):
            if key not in body:
                continue
            lines.append(f"{pad}    {key}:")
            for field, value in body[key].items():
                # Quoted where YAML would read the text otherwise: Jinja, and a threshold such as ">0", whose `>`
                # would open a folded block.
                quoted = "{{" in str(value) or str(value).startswith(">")
                shown = _yaml_list(value) if isinstance(value, list) else json.dumps(value) if quoted else value
                lines.append(f"{pad}      {field}: {shown}")
    return lines


@dataclass(frozen=True)
class Shape:
    """What one type's staging models conform to, and the union that reads them."""

    key_column: str  # <what one row is>_key
    row: str  # what one row is, in words
    union: str
    columns: tuple[tuple[str, str], ...]  # (column, description) beside the key, source_key, club, geom, properties, _loaded_at
    # False for a content type: its rows are episodes, write-ups, list items and
    # photo manifest rows, with no geometry column, so no geom, no region box and no CRS cast.
    geometry: bool = True
    # True where the union clears a row landed as one point outside its source's box and marks it in
    # `point_outside_region` (union_sql()): places only, since monthly run 19 (refresh-reference.yml 37253303123)
    # failed the places union's swap test on three stray NPS points. The other types' unions are unchanged.
    clears_stray_points: bool = False


SHAPES = {
    "places": Shape(
        key_column="place_key",
        row="one feature of a places layer: a park, a public land unit, a town, a section of trail",
        union="int_places__unioned",
        columns=(
            (
                "name",
                "The layer's own name for the feature, from the registry's `name_field`, or its `name_constant` for a layer that names its one feature only in the registry; null where it has neither.",
            ),
            ("category", "The layer's own category, from the registry's `category_field`; null where the registry names none."),
        ),
        clears_stray_points=True,
    ),
    "elevation": Shape(
        key_column="elevation_feature_key",
        row="one feature of an elevation layer: a point with a height, a line whose vertices carry one, or a band",
        union="int_elevation__unioned",
        columns=(
            (
                "published_elevation",
                "The elevation field the registry's `elevation_source` names (`field <name>`), as text, exactly as the layer publishes it; null for a layer whose elevation is its geometry's Z. Its unit is the registry's `elevation_unit`, which int_elevation__club_samples reads row by row.",
            ),
        ),
    ),
    "points_of_interest": Shape(
        key_column="poi_key",
        row="one point of a points-of-interest layer: a shelter, a campsite, a water source, a trailhead, a parking area",
        union="int_points_of_interest__club_unioned",
        columns=(
            (
                "name",
                "The layer's own name for the point, from the registry's `name_field`, or its `name_constant`; null where it has neither.",
            ),
            (
                "category",
                "The layer's own type for the point, from the registry's `type_field`, as text exactly as the layer publishes it (a coded value is its code, not its label); null where the registry names none. No value here is a POI type by itself: the club_poi_types seed maps a layer's own field values to POI types, and int_points_of_interest__club_points applies it.",
            ),
            (
                "source_id",
                "The id the point publishes under: the registry `id_field`'s value, as text, where that field is the layer's own id, and the base model's key where it is a server row id (a reload mints OBJECTID and FID again).",
            ),
        ),
    ),
    "trail_lines": Shape(
        key_column="trail_segment_key",
        row="one line of a trail-line layer: a trail, a section, a route or an alignment, as the layer draws it",
        union="int_trail_lines__unioned",
        columns=(
            (
                "name",
                "The layer's own name for the line, from the registry's `name_field`, or its `name_constant` for a layer that names its lines only in the registry; null where it has neither.",
            ),
        ),
    ),
    # The content types. Each union is `__club_unioned`, as
    # points_of_interest's is, because the type's mart reads another path today (the podcasts mart reads
    # reference/podcast_episodes.json's editorial picks, suggested_hikes the Hike Finder and the highlights,
    # challenges the reviewed challenge files through int_challenges__unioned) and these rows are the clubs' own
    # datasets beside it. photos has no mart: its union is the photo manifest a later step reads.
    "podcasts": Shape(
        key_column="episode_key",
        row="one episode of a club's own podcast feed, or one item of NPS's audio list",
        union="int_podcasts__club_unioned",
        columns=(
            ("title", "The episode's title as its feed or list states it."),
            (
                "published",
                "The episode's publication date as its feed states it, unparsed (RSS pubDate); null for an NPS audio item, which states none.",
            ),
            ("link", "The episode's own page, as its feed or list links it; null where it links none."),
            ("audio_url", "The audio file's URL (an RSS enclosure, or NPS's first version), linked and never fetched."),
        ),
        geometry=False,
    ),
    "suggested_hikes": Shape(
        key_column="hike_key",
        row="one hike a club or NPS publishes: a WordPress write-up, a wiki trail or hike page, an NPS thing to do or tour",
        union="int_suggested_hikes__club_unioned",
        columns=(
            ("name", "The hike's name as its source titles it (WordPress's rendered title, a wiki page's title, NPS's title)."),
            ("link", "The page a hiker reads it on, as the source links it."),
        ),
        geometry=False,
    ),
    "challenges": Shape(
        key_column="challenge_item_key",
        row="one item of a challenge list a club or NPS publishes: an NPS passport stamp location, or a club wiki's challenge page",
        union="int_challenges__club_unioned",
        columns=(
            ("name", "The item's name as its source states it (NPS's label, a wiki page's title)."),
            ("link", "The page it is published on; null where the source links none (NPS's stamp locations)."),
        ),
        geometry=False,
    ),
    "photos": Shape(
        key_column="photo_key",
        row="one photo's manifest row: its URL, its own credit and licence and its page, never its pixels",
        union="int_photos__club_unioned",
        columns=(
            ("title", "The photo's title as its source states it."),
            ("image_url", "The image file's URL, linked and never fetched (bytes never enter DuckDB)."),
            ("credit", "The photo's own credit line, as its source states it for that photo."),
            (
                "licence",
                "The photo's own licence or constraint, as its source states it for that photo (NPS's constraintsInfo.constraint): never a park's, an account's or a site's licence.",
            ),
            ("link", "The photo's own page."),
        ),
        geometry=False,
    ),
}

#: The content readers whose tables this stages, by class name, and each type's conformed columns per
#: reader: a raw field (written as the registry and the live answers name it, normalized as dlt lands it), a
#: JSON path into one (`field $.path`), or None for a column the reader's rows never carry.
CONTENT_COLUMNS = {
    ("podcasts", "PodcastEpisodes"): {"title": "title", "published": "pubDate", "link": "link", "audio_url": "enclosure_url"},
    ("podcasts", "NpsContent"): {},
    ("suggested_hikes", "WordpressPosts"): {"name": "title $.rendered", "link": "link"},
    ("suggested_hikes", "WordpressChildPages"): {"name": "title $.rendered", "link": "link"},
    ("suggested_hikes", "NpsContent"): {},
    ("suggested_hikes", "MediawikiTemplatePages"): {"name": "title", "link": "fullurl"},
    ("challenges", "NpsContent"): {},
    ("challenges", "MediawikiTemplatePages"): {"name": "title", "link": "fullurl"},
    ("photos", "NpsContent"): {},
    # The page reader (extract/_pages_content.py): every type's rows carry the type's own
    # columns by these names (its TYPE_COLUMNS), whatever site they were read from.
    ("suggested_hikes", "ContentPages"): {"name": "name", "link": "link"},
    ("challenges", "ContentPages"): {"name": "name", "link": "link"},
    ("podcasts", "ContentPages"): {"title": "title", "published": "published", "link": "link", "audio_url": "audio_url"},
    ("photos", "ContentPages"): {
        "title": "title",
        "image_url": "image_url",
        "credit": "credit",
        "licence": "licence",
        "link": "link",
    },
    # The PDF reader (extract/_pdf_content.py): the same type columns as its page reader.
    ("suggested_hikes", "ContentPdf"): {"name": "name", "link": "link"},
    ("challenges", "ContentPdf"): {"name": "name", "link": "link"},
    # The workbook reader (extract/_sheet_content.py): the same type columns again.
    ("suggested_hikes", "ContentSheet"): {"name": "name", "link": "link"},
    ("challenges", "ContentSheet"): {"name": "name", "link": "link"},
    # A club page's points (extract/_pages_points.py's PagePoints) that a content file SHARES: one row per page, its
    # columns the ones the points row names for the type in `shared_page_rows` (page_rows_columns()), as NPS's are
    # its endpoint's. The Palmetto Trail's passages: the lead's ruling of 2026-10-04, one reader of its 33 pages.
    ("suggested_hikes", "PagePoints"): {},
    # An ArcGIS layer whose rows each link one photograph (ATA's Scenic Resources and StoryMap
    # layers, RCO's camping inventory). Each layer names its photo field its own way (`Link`, `pic_url`, `PhotoWeb`),
    # so its sources.json row's `photo_columns` names the fields, as a points row names its `name_field`
    # (photo_columns()). The row's position stays in `properties`, as the GeoJSON text dlt landed.
    ("photos", "ArcgisLayer"): {},
}
#: NPS's lists, one reader for five endpoints, conformed by (type, the endpoint's path under /api/v1/), each field
#: one extract/_content.py's NPS_CONTENT_COLUMNS hints so the column exists on every run.
NPS_COLUMNS = {
    ("podcasts", "multimedia/audio"): {
        "title": "title",
        "published": None,
        "link": "permalinkUrl",
        "audio_url": "versions $[0].url",
    },
    ("suggested_hikes", "thingstodo"): {"name": "title", "link": "url"},
    ("suggested_hikes", "tours"): {"name": "title", "link": None},
    ("challenges", "passportstamplocations"): {"name": "label", "link": None},
    ("photos", "multimedia/galleries/assets"): {
        "title": "title",
        "image_url": "fileInfo $.url",
        "credit": "credit",
        "licence": "constraintsInfo $.constraint",
        "link": "permalinkUrl",
    },
}
#: The prose each reader's rows carry, by the field names the live sources served on 2026-10-04. It lands in the
#: private raw store and stops at `base_` (the round brief's item 3: "a WordPress post's or an
#: episode's body lands in the private raw store and stops at base_"), so a staging model's `properties` sets
#: each to null, which json_merge_patch drops. A wiki page's wikitext is its prose and its template's fields
#: at once: it stops at base_ too, so a later rule that reads a trail's distance from its template parses the
#: base model, never a published column.
CONTENT_PROSE = {
    "PodcastEpisodes": ("description", "content_encoded", "itunes_summary", "itunes_subtitle", "ns_description"),
    "NpsContent": (
        "description",
        "transcript",
        "shortDescription",
        "longDescription",
        "accessibilityInformation",
        "feeDescription",
        "reservationDescription",
        "seasonDescription",
        "petsDescription",
        "locationDescription",
        "activityDescription",
        "ageDescription",
        "timeOfDayDescription",
        "durationDescription",
        "altText",
        "images",
        "stops",
    ),
    "WordpressPosts": ("content", "excerpt", "uagb_excerpt"),
    "WordpressChildPages": ("content", "excerpt"),
    "MediawikiTemplatePages": ("content",),
    # A content page's rows are facts by construction (extract/_pages_content.py's TYPE_COLUMNS allowlist): no prose
    # lands in the raw store, so none needs stopping here.
    "ContentPages": (),
    "ContentPdf": (),
    "ContentSheet": (),
}
#: The readers whose tables are lookups beside a type's rows, staged in base only: a hike type's taxonomy terms.
CONTENT_LOOKUPS = ("SiteTerms",)
#: The key of a lookup table: each term is one id within one taxonomy.
LOOKUP_KEY_FIELDS = ("taxonomy", "id")


class KeyRefused(ValueError):
    """A registry row with no usable measured key: the run stops and names it."""


@cache
def _naming():
    from dlt.common.normalizers.naming.sql_ci_v1 import NamingConvention

    return NamingConvention()


@cache
def _reserved() -> frozenset[str]:
    import duckdb

    rows = duckdb.sql("select keyword_name from duckdb_keywords() where keyword_category in ('reserved', 'type_function')")
    return frozenset(name for (name,) in rows.fetchall())


def column(field: str) -> str:
    """A registry field name as the landed column: dlt's name for it, quoted where DuckDB reserves the word."""
    name = _naming().normalize_path(field)
    return f'"{name}"' if name in _reserved() else name


def _sql_text(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


@dataclass(frozen=True)
class Table:
    folder: str
    type: str
    key: str
    table: str
    cadence: str
    entry: dict
    # The extract reader's class name: ArcgisLayer for every geographic layer (an ArcGIS layer, a GIS file or a
    # geographic API), a content reader (CONTENT_COLUMNS), which decides how the staging model
    # conforms the table's columns.
    reader: str = "ArcgisLayer"
    # The sibling type whose base model this staging reads, for a file that SHARES that sibling's resource.
    shared_from: str | None = None
    # True for the monthly lane's own copy of a closures or warnings table this geometric type SHARES (the module
    # docstring, "A LANE COPY"): a source table and a base model of its own, at this type's cadence.
    lane_copy: bool = False

    @property
    def shape(self) -> Shape:
        return SHAPES[self.type]

    @property
    def source_table(self) -> str:
        """The table's name in its dbt source block: the raw table's own, or for a lane copy the raw table's with its
        cadence after it, since generate_notice_models.py's notices block already declares the raw table's own name.
        A lane copy's source table carries the raw table as its `identifier`, so both read one relation."""
        return f"{self.table}_{self.cadence}" if self.lane_copy else self.table

    @property
    def lookup(self) -> bool:
        """A lookup beside a type's rows (a hike type's terms): staged in base only, never a union branch."""
        return self.reader in CONTENT_LOOKUPS

    @property
    def page_rows(self) -> bool:
        """A content type's rows from a page's points table it SHARES: one row per page, not one per point."""
        return self.reader == "PagePoints" and not self.shape.geometry

    @property
    def key_column(self) -> str:
        return "term_key" if self.lookup else self.shape.key_column

    @property
    def base_key_column(self) -> str:
        """The key column the base model carries: its own type's, or the sibling's for a shared resource."""
        return "term_key" if self.lookup else SHAPES[self.shared_from or self.type].key_column

    @property
    def base(self) -> str:
        return f"base_{self.folder}__{self.source_table.removeprefix(f'raw_{self.folder}__')}"

    @property
    def title(self) -> str:
        title = self.entry.get("title") or self.key
        return f"{title}: its taxonomy terms" if self.lookup else title

    @property
    def read_from_pdf(self) -> bool:
        """A table its reader takes off a PDF through pypdf: extract/_pdf_points.py's PdfPoints (a `pdf_points` row)
        or extract/_pdf_content.py's ContentPdf; or a workbook, extract/_sheet_content.py's ContentSheet. Fixture mode's
        Python need not have pypdf, and fixture mode serves no binary file, so the fixture warehouse never holds the
        table. Its freshness is every monthly table's all the same: LOADED_AT_QUERY reads the run log and never the
        table, so a table the warehouse does not hold is measured as any other. Until then it carried
        `freshness: null`, because `dbt source freshness` on `_loaded_at` failed on the missing table (CI's dbt job,
        2026-10-04, on ata_water_cache_boxes, bmta_access_points and rmc_recommended_hikes)."""
        return self.entry.get("kind") == PDF_POINTS_KIND or self.reader in ("ContentPdf", "ContentSheet")

    def key_inputs(self) -> list[str]:
        """The key's inputs as generate_surrogate_key takes them: the registry key, then each measured field."""
        entry = self.entry
        if self.lookup:
            return [f"'{self.key}'", *(column(field) for field in LOOKUP_KEY_FIELDS)]
        if self.page_rows:
            return [f"'{self.key}'", "source_url"]  # one row per page: every PagePoints row carries its page's URL
        if "key_fields" in entry:
            fields, home = list(entry["key_fields"]), "key_fields"
        elif entry.get("id_fields"):
            fields, home = list(entry["id_fields"]), "id_fields"
        elif entry.get("id_field"):
            fields, home = [entry["id_field"]], "id_field"
        else:
            raise KeyRefused(f"{self.key}: no key_fields, id_fields or id_field on its sources.json row")
        if not fields:
            fields = ["geometry"]  # a one-row layer: the registry key and its shape
        inputs = [f"'{self.key}'"]
        for field in fields:
            if field == "geometry":
                inputs.append("geometry_key('geom')")
                continue
            if not isinstance(field, str) or " " in field:
                raise KeyRefused(f"{self.key}: {home} holds {field!r}, which is not one of the layer's fields")
            name = column(field)
            if name.strip('"') in ROW_IDS:
                raise KeyRefused(f"{self.key}: {home} holds {field}, a server row id, which a reload mints again")
            inputs.append(name)
        return inputs

    def key_comment(self) -> str:
        entry = self.entry
        if self.lookup:
            return (
                "a term's `taxonomy` and its `id`: WordPress numbers terms within one site, and the reader lands each "
                "taxonomy's terms with its name (extract/_content.py's SiteTerms), so the pair is one term."
            )
        text = entry.get("key_comment") or entry.get("id_comment")
        if text:
            return registry_words(text)
        home = "key_fields" if "key_fields" in entry else "id_fields" if entry.get("id_fields") else "id_field"
        return f"the registry's `{home}`; its row records no measurement of it."

    def date_columns(self) -> list[str]:
        return [column(field) for field in self.entry.get("date_fields") or []]

    def raw_columns(self) -> list[str]:
        """Every raw column the base model and the staging models over it name, as raw_or_empty() takes them.

        A table that has never landed reads as no rows with these columns (macros/raw_or_empty.sql), so every
        column a generated model names is here: the key's fields, the dates (epoch milliseconds, so bigint), the
        geometry, and each field the registry row conforms. The row's fields are all taken whichever type reads
        them, because a file that SHARES this table conforms the same row's fields over the same base model."""
        entry = self.entry
        names: dict[str, str] = {}
        for item in self.key_inputs()[1:]:  # the registry key's literal first, then the measured fields
            if item != "geometry_key('geom')":
                names.setdefault(item.strip('"'), "varchar")
        if self.shape.geometry:
            names.setdefault("geometry", "varchar")
        conformed = [entry[name] for name in ("name_field", "type_field", "category_field", "id_field") if entry.get(name)]
        elevation = entry.get("elevation_source") or ""
        if elevation.startswith("field "):
            conformed.append(elevation.removeprefix("field ").strip())
        if not self.shape.geometry and not self.lookup:
            conformed += [field.split(" ", 1)[0] for field in content_columns(self).values() if field is not None]
        for fields in (entry.get("shared_page_rows") or {}).values():
            conformed += [field for field in fields.values() if field is not None]
        for field in conformed:
            names.setdefault(column(field).strip('"'), "varchar")
        for name in self.date_columns():
            names[name.strip('"')] = "bigint"
        return [name if type_ == "varchar" else f"{name}:{type_}" for name, type_ in names.items()]


def _raw_key_columns(inputs: list[str]) -> list[str]:
    """The same key over the raw table, as duplicates_are_exact takes it: geometry_key('geom') written out."""
    raw_geometry = "md5(st_astext(st_geomfromgeojson(cast(geometry as varchar))))"
    return [raw_geometry if item == "geometry_key('geom')" else item for item in inputs]


def _hand_written_raw_tables() -> set[str]:
    """Every raw table a model this generator did not write already reads."""
    import re

    pattern = re.compile(r"source\('[a-z0-9_]+',\s*'(raw_[a-z0-9_]+)'\)")
    found = set()
    for path in MODELS.rglob("*.sql"):
        text = path.read_text()
        if GENERATED in text.split("\n", 1)[0]:
            continue
        found.update(pattern.findall(text))
    return found


def tables() -> list[Table]:
    """Every layer this stages, sorted by folder and key; stops on the first row with no usable key."""
    sys.path.insert(0, str(PIPELINE))
    from extract._contract import CADENCE_BY_TYPE, DEFAULT_CADENCE, discover
    from extract._gis_files import GisFile
    from extract._kinds import ArcgisLayer, registry_entry
    from extract._ogc import JsonFeatures, OgcFeatures
    from extract._pages_points import PagePoints
    from extract._pdf_points import PdfPoints

    hand_written = _hand_written_raw_tables()
    readers = {reader for _, reader in CONTENT_COLUMNS} | set(CONTENT_LOOKUPS)
    geographic = ArcgisLayer | GisFile | OgcFeatures | JsonFeatures | PagePoints | PdfPoints
    files = discover()
    by_place = {(club_file.club, club_file.type): club_file for club_file in files}
    found = []
    for club_file in files:
        if club_file.type not in SHAPES:
            continue
        owner = by_place.get((club_file.club, club_file.shares)) if club_file.shares else club_file
        if owner is None:
            continue
        # The module docstring, "A LANE COPY": a geometric type sharing a notice type's resource.
        lane_copy = owner.type in NOTICE_TYPES and SHAPES[club_file.type].geometry
        if owner.type not in SHAPES and not lane_copy:
            continue
        for resource in owner.resources:
            # A lane copy's raw table is always read by the notices' own base model, which generate_notice_models.py
            # writes and this does not; its copy is declared under its own name, so that model is not in its way.
            if resource.table in hand_written and not lane_copy:
                continue
            reader = type(resource).__name__
            if SHAPES[club_file.type].geometry:
                if not isinstance(resource, geographic) or resource.entry.get("kind") not in KINDS:
                    continue
                reader = "ArcgisLayer"
            elif reader not in readers or (reader not in CONTENT_LOOKUPS and (club_file.type, reader) not in CONTENT_COLUMNS):
                continue
            elif reader == "PagePoints" and club_file.type not in (resource.entry.get("shared_page_rows") or {}):
                continue  # a page's points feed a content type only through the fields their row names for it
            elif reader == "ArcgisLayer" and not resource.entry.get("photo_columns"):
                # An ArcGIS layer feeds photos only through the fields its row's `photo_columns` names, so a photos
                # row that SHARES a points layer carrying a photo field (BLM's `PHOTO_LINK`) stays unstaged, as it
                # was, until its row names them.
                continue
            # A keyed API's table is withdrawn whenever its key is unset (extract/_ogc.py's JsonFeatures). It is staged
            # all the same: its base model reads an absent table as no rows (macros/raw_or_empty.sql).
            entry = registry_entry(resource.key)
            if club_file.shares and club_file.type == "elevation" and not entry.get("elevation_source"):
                continue  # a line layer an elevation file shares carries its heights only where its row says so
            if lane_copy:
                # At the sharing type's own cadence, the lane its nodes are built in, never the resource's hourly one.
                cadence = CADENCE_BY_TYPE.get(club_file.type, DEFAULT_CADENCE)
                found.append(
                    Table(club_file.club, club_file.type, resource.key, resource.table, cadence, entry, reader, lane_copy=True)
                )
                continue
            shared_from = owner.type if club_file.shares else None
            found.append(
                Table(club_file.club, club_file.type, resource.key, resource.table, resource.cadence, entry, reader, shared_from)
            )
    found.sort(key=lambda table: (table.folder, table.key, table.table, table.shared_from or ""))
    refused = []
    for table in found:
        try:
            table.key_inputs()
        except KeyRefused as error:
            refused.append(str(error))
    if refused:
        raise KeyRefused("no staging without a measured key:\n  " + "\n  ".join(refused))
    return found


#: A numbered decision, poll question or work wave as a registry note cites it ("decision 40", "decision 54's wave 1",
#: "Q3"). A note copied into a model's description drops these: the docs say what the data is, and the decision log is
#: git history. The publication rule reads a row's `licence` for its rulings and never these descriptions.
_NUMBERED_REFERENCE = re.compile(
    r"\s*\((?:decisions? \d+[a-z]?(?:\([a-z]\))?(?:(?:, | and | or )\d+[a-z]?)*|Q\d+)\)"
    r"|\b[Dd]ecisions? \d+[a-z]?(?:''|')s (?:waves? \d+(?: and \d+)? )?"
    r"|,? (?:per|under|by) decisions? \d+[a-z]?(?:\([a-z]\))?"
)
#: Any other mention, mid-sentence ("what decision 40 asks of a key"), reads as the rule it names.
_OTHER_REFERENCE = re.compile(r"\b[Dd]ecisions? \d+[a-z]?(?:\([a-z]\))?\b")


def registry_words(text: str) -> str:
    """A registry note as a model's description quotes it, without the numbered references it cites."""
    text = _NUMBERED_REFERENCE.sub(lambda match: "the " if "'s " in match.group(0) else "", text)
    return _OTHER_REFERENCE.sub("the maintainer's rule", text)


def _comment(text: str, indent: str = "") -> str:
    return "\n".join(textwrap.wrap(text, LINE - len(indent), initial_indent=f"{indent}-- ", subsequent_indent=f"{indent}-- "))


def _folded(text: str, indent: int) -> str:
    """A YAML folded scalar's body, wrapped."""
    pad = " " * indent
    return "\n".join(textwrap.wrap(text, 100 - indent, initial_indent=pad, subsequent_indent=pad))


def _held_back(entry: dict) -> str:
    if entry.get("reaches_hikers") is False:
        return "Its sources.json row reads `reaches_hikers: false`, so int_sources__publication holds it back from every mart."
    return "Whether it may publish is int_sources__publication's to decide, from its sources.json row."


# --- base models ----------------------------------------------------------------------------------------------


def _key_item(item: str) -> str:
    """One generate_surrogate_key input as the base models write it: the registry key as `"'<key>'"`, the
    geometry as the geometry_key('geom') call, and a column as a quoted string (tests/test_dbt_keys.py reads
    the list back with ast.literal_eval)."""
    if item.startswith("'"):
        return json.dumps(item)
    if item == "geometry_key('geom')":
        return item
    return repr(item)


def _lane_copy_note(table: Table) -> str:
    """What a lane copy's base model and source table say they are (the module docstring, "A LANE COPY")."""
    stem = table.table.removeprefix(f"raw_{table.folder}__")
    return (
        f"The {table.cadence} lane's own copy of {table.table}, a table the hourly lane lands for this folder's "
        f"closures or warnings, which extract/not_available.toml's [{table.folder}.{table.type}] row SHARES: "
        f"extract/_run.py's ALSO_READS lands it in the {table.cadence} lane's store too, still one extraction "
        f". generate_notice_models.py stages the hourly copy as base_{table.folder}__{stem}; this one "
        f"is read only by stg_{table.folder}__{table.type}, so each lane's nodes read the copy that lane landed."
    )


def base_sql(table: Table) -> str:
    inputs = table.key_inputs()
    dates = table.date_columns()
    head = [
        _comment(
            f"{table.title} ({table.entry.get('provider') or table.folder}, sources.json `{table.key}`): every row, "
            "keyed and deduped, with nothing filtered and nothing joined. A base model, the one place "
            "this dataset is staged."
            if not table.lane_copy
            else f"{table.title} ({table.entry.get('provider') or table.folder}, sources.json `{table.key}`): every "
            "row, keyed and deduped, with nothing filtered and nothing joined. " + _lane_copy_note(table)
        ),
        "--",
        _comment(f"Key: {table.key_comment()}"),
    ]
    if dates:
        head += ["--", _comment(f"Dates: {', '.join(dates)}, the layer's esriFieldTypeDate fields (sources.json `date_fields`).")]
    # SQLFluff's LT05 holds every line to 80: a long exclude list or source() call breaks over lines, the
    # source() call after its first argument, where tests/test_dbt_keys.py's pattern still reads it.
    excluded = ["geometry", *dates]
    exclude = f"* exclude ({', '.join(excluded)}),"
    if len(exclude) + 8 > 80:
        exclude = "* exclude (\n" + ",\n".join(f"            {name}" for name in excluded) + "\n        ),"
    # Read through raw_or_empty() (macros/raw_or_empty.sql): a table that has never landed reads as no rows with the
    # columns these models name, rather than stopping every other club's layers.
    relation = f"source('{table.folder}', '{table.source_table}')"
    # 8 for the indent and 1 for the comma after it: raw_montour_trail__montour_trail_access_areas, the first relation
    # exactly 72 long (2026-10-11), came to 81 under a check that counted the indent alone.
    if len(relation) + 9 > 80:
        relation = f"source('{table.folder}',\n            '{table.source_table}')"
    names = ", ".join(f"'{name}'" for name in table.raw_columns())
    listed = (
        f"[{names}]"
        if len(names) + 10 <= 80
        else "[\n" + "".join(f"            '{name}',\n" for name in table.raw_columns()) + "        ]"
    )
    source = f"{{{{ raw_or_empty(\n        {relation},\n        {listed}\n    ) }}}}"
    casts = "".join(f",\n        to_timestamp({name} / 1000) as {name}" for name in dates)
    key_lines = "".join(f"\n            {_key_item(item)}," for item in inputs)
    if table.shape.geometry:
        select_source = f"""    -- dlt lands geometry as GeoJSON text and an ArcGIS date as epoch
    -- milliseconds (extract/_kinds.py's ESRI_TYPES); both are cast here, as
    -- staging models do.
    select
        {exclude}
        st_geomfromgeojson(cast(geometry as varchar)) as geom{casts}
    from {source}"""
    else:
        select_source = f"""    -- A content table carries no geometry and is cast nowhere: each column is
    -- as dlt landed it (a WordPress date a timestamp, a feed's pubDate the
    -- string it states, which a rewrite here would restate), nested as JSON.
    select *
    from {source}"""
    return (
        SQL_MARK
        + "\n".join(head)
        + f"""
with source as (
{select_source}
),

renamed as (
    select
        {{{{ dbt_utils.generate_surrogate_key([{key_lines}
        ]) }}}} as {table.key_column},
        source.*
    from source
)

{{{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='{table.key_column}', order_by='_dlt_id'
) }}}}
"""
    )


def _yaml_list(items: list[str]) -> str:
    return "[" + ", ".join(json.dumps(item) for item in items) + "]"


def sources_yaml(folder: str, folder_tables: list[Table]) -> str:
    cadence = _cadence(folder_tables)
    lines = [
        YAML_MARK + "version: 2",
        "",
        "sources:",
        f"  - name: {folder}",
        "    description: >",
        _folded(
            f"The layers sources.json registers for the extract's {folder}/ folder (pipeline/extract/{folder}/) "
            f"that pipeline/make_dbt_staging.py stages, landed as raw_{folder}__<key> and staged once each by a "
            "generated base model here. Descriptions transcribed from sources.json's titles and key notes.",
            6,
        ),
        "    schema: raw",
        "    config:",
        "      # When the extract last read each table or confirmed it unchanged:",
        "      # make_dbt_staging.py's LOADED_AT_QUERY and MONTHLY_FRESHNESS_DAYS say why.",
        f'      loaded_at_query: "{LOADED_AT_QUERY}"',
        "      meta:",
        f"        cadence: {cadence}",
        *_freshness_lines(folder, cadence),
        "    tables:",
    ]
    for table in folder_tables:
        lines += [
            f"      - name: {table.source_table}",
            *(
                [
                    "        # make_dbt_staging.py's docstring, \"A LANE COPY\": the raw table the notices' own source table",
                    "        # names, which dbt_project_evaluator_exceptions.csv's fct_duplicate_sources row lets two name.",
                    f"        identifier: {table.table}",
                ]
                if table.lane_copy
                else []
            ),
            "        data_tests:",
            f"          # Rows sharing {table.base}'s key must be exact copies.",
            "          - duplicates_are_exact:",
            "              arguments:",
            f"                key_columns: {_yaml_list(_raw_key_columns(table.key_inputs()))}",
            *([f"                row_id_columns: {_yaml_list(FILE_ROW_IDS)}"] if table.entry.get("kind") in FILE_KINDS else []),
            "          # Elementary's checks (raw_table_checks()), each at warn and run after the writers.",
            *raw_table_checks_yaml(10),
            "        description: >",
            _folded(
                f"{table.title} (sources.json `{table.key}`). "
                + (_lane_copy_note(table) + " " if table.lane_copy else "")
                + f"Key: {table.key_comment()}",
                10,
            ),
        ]
    return "\n".join(lines) + "\n"


def _freshness_lines(folder: str, cadence: str) -> list[str]:
    """A generated sources block's `freshness`, by its cadence: MONTHLY_FRESHNESS_DAYS, every table this writes being
    on the monthly lane (the types it stages are monthly). Any other cadence stops the run, naming the
    folder, rather than guessing a threshold: an hourly or daily source's numbers are the and 101's
    (generate_notice_models.py's FRESHNESS_HOURS), for the notice sources that generator stages."""
    if cadence != "monthly":
        raise ValueError(f"{folder}: a generated sources block is monthly, and this one is {cadence}; give it its thresholds")
    warn, error = MONTHLY_FRESHNESS_DAYS
    return [
        "      freshness:",
        f"        warn_after: {{count: {warn}, period: day}}",
        f"        error_after: {{count: {error}, period: day}}",
    ]


def _cadence(folder_tables: list[Table]) -> str:
    cadences = {table.cadence for table in folder_tables}
    if len(cadences) != 1:
        raise ValueError(f"{folder_tables[0].folder}: one source block per folder needs one cadence, found {sorted(cadences)}")
    return cadences.pop()


def base_yaml(folder: str, folder_tables: list[Table]) -> str:
    lines = [YAML_MARK + "version: 2", "", "models:"]
    for table in folder_tables:
        inputs = ", ".join(item.strip("'") if item.startswith("'") else item for item in table.key_inputs())
        lines += [
            f"  - name: {table.base}",
            "    data_tests:",
            "      # Warns when the dedupe dropped any row, each an exact copy",
            "      # (duplicates_are_exact on the raw table), and is an error once",
            "      # the copies are half the raw table (its two",
            "      # thresholds are the generic test's). A raw table that never",
            "      # landed passes (tests/generic/equal_rowcount_to_raw.sql).",
            "      - equal_rowcount_to_raw:",
            "          arguments:",
            f"            compare_model: source('{folder}', '{table.source_table}')",
            "    description: >",
            _folded(
                f"{table.title}, every row, keyed and deduped, the layer's own columns under dlt's "
                f"names. {_held_back(table.entry)} "
                + (
                    f"A lookup beside stg_{folder}__{table.type}'s rows, which carry its ids; no union reads it."
                    if table.lookup
                    else f"{table.shape.union} reads it through stg_{folder}__{table.type}."
                )
                + (" " + _lane_copy_note(table) if table.lane_copy else ""),
                6,
            ),
            "    columns:",
            f"      - name: {table.key_column}",
            "        description: >",
            _folded(
                f"The row's key: dbt_utils.generate_surrogate_key over {inputs}, the registry key "
                "first and then the fields measured unique for this layer.",
                10,
            ),
            "        data_tests: [not_null, unique]",
        ]
    return "\n".join(lines) + "\n"


# --- staging models -------------------------------------------------------------------------------------------


def _name(entry: dict) -> str:
    """The `name` column: the registry's `name_field`, else its `name_constant`, else null."""
    if entry.get("name_field"):
        return f"cast({column(entry['name_field'])} as varchar) as name"
    if entry.get("name_constant"):
        line = f"cast({_sql_text(entry['name_constant'])} as varchar) as name"
        if len(line) + 5 <= 80:  # indent, and the comma after it
            return line
        # LT05: a long constant is cut at spaces into pieces joined with ||, each piece keeping its space.
        pieces, piece = [], ""
        for word in entry["name_constant"].split(" "):
            candidate = f"{piece} {word}" if piece else word
            if piece and len(_sql_text(candidate + " ")) > 60:
                pieces.append(piece + " ")
                piece = word
            else:
                piece = candidate
        pieces.append(piece)
        joined = "\n        || ".join(_sql_text(text) for text in pieces)
        return f"cast(\n        {joined} as varchar\n    ) as name"
    return "cast(null as varchar) as name"


def _conformed(table: Table) -> list[str]:
    entry = table.entry
    if table.type == "trail_lines":
        return [_name(entry)]
    if table.type == "points_of_interest":
        category = f"cast({column(entry['type_field'])} as varchar)" if entry.get("type_field") else "cast(null as varchar)"
        id_field = entry.get("id_field")
        if id_field and column(id_field).strip('"') not in ROW_IDS:
            source_id = f"cast({column(id_field)} as varchar)"
        else:
            source_id = f"cast({table.base_key_column} as varchar)"
        return [_name(entry), f"{category} as category", f"{source_id} as source_id"]
    if table.type == "places":
        category = (
            f"cast({column(entry['category_field'])} as varchar)" if entry.get("category_field") else "cast(null as varchar)"
        )
        return [_name(entry), f"{category} as category"]
    if table.type == "elevation":
        source = entry.get("elevation_source") or ""
        if source.startswith("field "):
            return [f"cast({column(source.removeprefix('field ').strip())} as varchar) as published_elevation"]
        if source == "geometry Z":
            return ["cast(null as varchar) as published_elevation"]
        raise ValueError(f"{table.key}: elevation_source {source!r} is neither 'field <name>' nor 'geometry Z'")
    if not table.shape.geometry:
        return _content_conformed(table)
    raise ValueError(f"{table.key}: no staging shape for type {table.type}")


def content_columns(table: Table) -> dict[str, str | None]:
    """A content table's conformed columns: CONTENT_COLUMNS for its reader, an NPS list's by its endpoint."""
    if table.reader == "NpsContent":
        path = table.entry["url"].rstrip("/").split("/api/v1/", 1)[-1]
        found = NPS_COLUMNS.get((table.type, path))
        if found is None:
            raise ValueError(f"{table.key}: no NPS_COLUMNS row for {table.type} from {path!r}")
        return found
    if table.page_rows:
        fields = page_rows_fields(table)
        return {name: fields.get(name) for name, _ in table.shape.columns}
    if table.reader == "ArcgisLayer":
        return photo_columns(table)
    return CONTENT_COLUMNS[(table.type, table.reader)]


def photo_columns(table: Table) -> dict[str, str | None]:
    """An ArcGIS photo layer's conformed columns, as its sources.json row's `photo_columns` names the layer's fields.

    The row must name the field holding the image's URL, and may name a field for each other column; a column it
    names no field for is null, never guessed (CLAUDE.md: absent means unknown). None of the layers registered so far
    states a credit or a licence for its photographs, so their rows name neither."""
    fields = table.entry.get("photo_columns") or {}
    names = [name for name, _ in table.shape.columns]
    unknown = sorted(set(fields) - set(names))
    if not fields.get("image_url") or unknown:
        raise ValueError(f"{table.key}: `photo_columns` must name the image_url field, and only columns of {names}")
    return {name: fields.get(name) for name in names}


def page_rows_fields(table: Table) -> dict[str, str]:
    """{the type's column: the raw column}, as the points row's `shared_page_rows` names them for the type."""
    fields = (table.entry.get("shared_page_rows") or {}).get(table.type)
    if not fields or "link" not in fields:
        raise ValueError(f"{table.key}: `shared_page_rows` names no fields (and no link) for {table.type}")
    return fields


def _content_conformed(table: Table) -> list[str]:
    lines = []
    for name, field in content_columns(table).items():
        if field is None:
            lines.append(f"cast(null as varchar) as {name}")
        elif " " in field:
            raw, path = field.split(" ", 1)
            lines.append(f"json_extract_string({column(raw)}, '{path}') as {name}")
        else:
            lines.append(f"cast({column(field)} as varchar) as {name}")
    return lines


def stg_sql(folder: str, type_: str, type_tables: list[Table]) -> str:
    shape = SHAPES[type_]
    if not shape.geometry:
        return _content_stg_sql(folder, type_, type_tables)
    head = _comment(
        f"The {folder}/ folder's {type_.replace('_', ' ')} layers, conformed to {shape.union}'s columns: each "
        "layer's rename to the union's names and its key, nothing filtered (a club's review gate is "
        "an intermediate's). The layer's own columns ride whole in `properties`, under dlt's names, so a rule "
        "downstream reads a field by the name its registry row gives it: json_merge_patch drops a member a "
        "patch sets to null, so `properties` is the base row without the geometry that travels beside it."
    )
    branches = []
    for table in type_tables:
        conformed = "".join(f"\n    {line}," for line in _conformed(table))
        key = shape.key_column if table.base_key_column == shape.key_column else f"{table.base_key_column} as {shape.key_column}"
        branches.append(
            f"""select
    '{table.key}' as source_key,
    '{folder}' as club,
    {key},{conformed}
    geom,
    json_merge_patch(
        to_json({table.base}),
        '{{"geom": null}}'
    ) as properties,
    _loaded_at
from {{{{ ref('{table.base}') }}}}"""
        )
    return SQL_MARK + head + "\n" + "\nunion all by name\n".join(branches) + "\n"


def _patch_lines(members: str) -> list[str]:
    """A JSON object literal, `'{...}'`, cut at its commas into lines SQLFluff's 80 columns hold (`||` joined)."""
    if not members:
        return ["'{}'"]
    parts = members.split(", ")
    lines, line = [], ""
    for part in parts:
        candidate = f"{line}, {part}" if line else part
        if line and len(candidate) > 56:
            lines.append(line + ",")
            line = part
        else:
            line = candidate
    lines.append(line)
    if len(lines) == 1:
        return ["'{" + lines[0] + "}'"]
    quoted = ["'{" + lines[0] + " '"] + [f"|| '{text} '" for text in lines[1:-1]] + [f"|| '{lines[-1]}}}'"]
    return quoted


def _content_stg_sql(folder: str, type_: str, type_tables: list[Table]) -> str:
    """A content type's staging model: each table's rename to the union's columns and its key, as text."""
    shape = SHAPES[type_]
    head = _comment(
        f"The {folder}/ folder's {type_.replace('_', ' ')} sources, conformed to {shape.union}'s columns: each "
        "source's rename to the union's names and its key, nothing filtered (a club's review gate is "
        "an intermediate's). The source's own columns ride in `properties`, under dlt's names, all but its prose: "
        "json_merge_patch drops each member the patch sets to null, so a body, an episode's notes or a page's "
        "wikitext stops at the base model."
    )
    for table in type_tables:
        if table.page_rows:
            head += "\n" + _comment(
                f"`{table.key}` is a page's points table this folder's {type_.replace('_', ' ')} file SHARES (one read "
                "of each page): it gives one row per page, grouped on `source_url` and the fields its "
                "row's `shared_page_rows` names, and only those fields ride in `properties`."
            )
    branches = []
    for table in type_tables:
        if table.page_rows:
            branches.append(_page_rows_branch(folder, table))
            continue
        conformed = "".join(f"\n    {line}," for line in _conformed(table))
        prose = ", ".join(f'"{column(name).strip(chr(34))}": null' for name in CONTENT_PROSE.get(table.reader, ()))
        patch = "\n".join(f"        {line}" for line in _patch_lines(prose))
        branches.append(
            f"""select
    '{table.key}' as source_key,
    '{folder}' as club,
    {shape.key_column},{conformed}
    json_merge_patch(
        to_json({table.base}),
{patch}
    ) as properties,
    _loaded_at
from {{{{ ref('{table.base}') }}}}"""
        )
    return SQL_MARK + head + "\n" + "\nunion all by name\n".join(branches) + "\n"


def _page_rows_branch(folder: str, table: Table) -> str:
    """A content type's branch over a page's points table it SHARES: one row per page (`source_url`), grouped.

    Every row of one page carries that page's facts alike (the points row's `shared_page_rows_comment` says how that
    was measured), so grouping on the page and the fields named keeps one row a page; a page whose rows ever
    disagreed would group into two rows under one key, which the staging model's unique test refuses. `properties`
    is those fields alone, under the type's names: a marker's type and place stay in the points' staging model.
    """
    fields = page_rows_fields(table)
    raw = list(dict.fromkeys(["source_url", *(field for field in fields.values() if field is not None)]))
    conformed = "".join(f"\n    {line}," for line in _content_conformed(table))
    members = ",\n".join(f"        '{name}', {column(field)}" for name, field in fields.items() if field is not None)
    key_lines = "".join(f"\n        {_key_item(item)}," for item in table.key_inputs())
    group = ",\n".join(f"    {column(field)}" for field in raw)
    return f"""select
    '{table.key}' as source_key,
    '{folder}' as club,
    {{{{ dbt_utils.generate_surrogate_key([{key_lines}
    ]) }}}} as {table.shape.key_column},{conformed}
    json_object(
{members}
    ) as properties,
    max(_loaded_at) as _loaded_at
from {{{{ ref('{table.base}') }}}}
group by
{group}"""


def models_yaml(folder: str, by_type: dict[str, list[Table]]) -> str:
    lines = [YAML_MARK + "version: 2", "", "models:"]
    for type_, type_tables in sorted(by_type.items()):
        shape = SHAPES[type_]
        keys = ", ".join(f"`{table.key}`" for table in type_tables)
        paged = [table for table in type_tables if table.page_rows]
        grain = "one row per base row"
        if paged:
            grain += " (one per page for " + ", ".join(f"`{table.key}`" for table in paged) + ", whose points it shares)"
        lines += [
            f"  - name: stg_{folder}__{type_}",
            "    description: >",
            _folded(
                f"The {folder}/ folder's {type_.replace('_', ' ')} layers ({keys}), {grain}, renamed to "
                f"{shape.union}'s columns, with each layer's own columns in `properties`.",
                6,
            ),
            "    columns:",
            f"      - name: {shape.key_column}",
            "        description: The base model's key, carried." if not paged else "        description: >-",
        ]
        if paged:
            lines.append(
                _folded("The base model's key, carried; for a shared page's points, the page's: (its key, `source_url`).", 10)
            )
        lines.append("        data_tests: [not_null, unique]")
    return "\n".join(lines) + "\n"


# --- unions ---------------------------------------------------------------------------------------------------


def union_sql(type_: str, staging_models: list[str]) -> str:
    shape = SHAPES[type_]
    geometry = ["geom"] if shape.geometry else []
    columns = [
        "source_key",
        "club",
        shape.key_column,
        *(name for name, _ in shape.columns),
        *geometry,
        "properties",
        "_loaded_at",
    ]
    what = "registered layers" if shape.geometry else "registered feeds, APIs and WordPress and wiki sources"
    head = _comment(
        f"Every {type_.replace('_', ' ')} row of the clubs' {what} that pipeline/make_dbt_staging.py "
        "stages, one row each, unfiltered: a `union all by name` of every stg_<folder>__"
        f"{type_} it writes. The branch list is the registry's, written by the generator from sources.json and the "
        "extract's club folders, so a layer registered later joins by running it again. Nothing here is filtered "
        "for publication: whatever reads it keeps int_sources__publication's verdict, the one home of may_publish."
    )
    select = ",\n    ".join(columns)
    branches = [f"select\n    {select}\nfrom {{{{ ref('{model}') }}}}" for model in staging_models]
    union = "\nunion all by name\n".join(branches)
    if not shape.clears_stray_points:
        return SQL_MARK + "{{ config(materialized='table') }}\n" + head + "\n" + union + "\n"
    head += "\n--\n" + _comment(
        "A STRAY POINT IS CLEARED, NOT PUBLISHED. A row that landed as one point outside the box its source is held "
        "to keeps no geometry here, and `point_outside_region` marks it (macros/lands_outside_its_region.sql's "
        "point_outside_its_region says why a point and nothing else): absent means unknown, as for a row that "
        "landed with no coordinate. So the lon/lat swap test reads what is left, and a swapped point layer, "
        f"which loses every point, fails int_{type_}__source_extents' loses_too_many_points_outside_region test "
        "instead."
    )
    indented = "\n".join(f"    {line}" for line in union.split("\n"))
    cleared = "case\n        when point_outside_region then null\n        else geom\n    end as geom"
    final = [cleared if name == "geom" else name for name in columns]
    final.insert(columns.index("geom") + 1, "point_outside_region")
    checked = (
        "checked as (\n"
        "    select\n"
        "        unioned.*,\n"
        "        {{ point_outside_its_region('unioned.geom', 'unioned.source_key') }}\n"
        "            as point_outside_region\n"
        "    from unioned\n"
        ")"
    )
    body = f"with unioned as (\n{indented}\n),\n\n{checked}\n\nselect\n    " + ",\n    ".join(final) + "\nfrom checked\n"
    return SQL_MARK + "{{ config(materialized='table') }}\n" + head + "\n" + body


def union_yaml(type_: str, type_tables: list[Table]) -> str:
    shape = SHAPES[type_]
    if shape.geometry:
        description = (
            f"Every {type_.replace('_', ' ')} row of the {len(type_tables)} registered layers "
            f"pipeline/make_dbt_staging.py stages, unioned by name: {shape.row}. Each row carries its layer's "
            "registry key, the club folder that extracted it, the base model's key, the conformed columns below, "
            "its geometry as landed and its layer's own columns as `properties`. Unfiltered: whatever reads it keeps "
            "int_sources__publication's verdict."
        )
        if shape.clears_stray_points:
            description += (
                " A row landed as one point outside the box its source is held to keeps no geometry here and is "
                "marked `point_outside_region`, so it cannot be published at a wrong spot."
            )
        region_test = [
            "    data_tests:",
            "      # The lon/lat swap test, against the box each source's rows are held",
            "      # to (macros/generated_regions.sql, read by",
            "      # macros/lands_outside_its_region.sql).",
            "      - lands_in_the_region_its_source_publishes_in:",
            "          arguments:",
            "            geometry: geom",
        ]
        if shape.clears_stray_points:
            region_test[4:4] = [
                "      # It reads `geom` after a stray point is cleared, so a line or",
                "      # polygon reaching outside its box fails here, and a point layer",
                "      # that loses too many points to the clearing, as a swapped one loses",
                f"      # all of them, fails int_{type_}__source_extents' test.",
            ]
    else:
        description = (
            f"Every {type_.replace('_', ' ')} row of the {len(type_tables)} registered sources "
            f"pipeline/make_dbt_staging.py stages for this type, unioned by name: {shape.row}. "
            "Each row carries its source's registry key, the club folder that extracted it, the base model's key, "
            "the conformed columns below and its source's own columns, prose left out, as `properties`. No "
            "geometry: a row is placed, where it is placed at all, by its own fields in `properties`. Unfiltered: "
            "whatever reads it keeps int_sources__publication's verdict."
        )
        region_test = []
    lines = [
        YAML_MARK + "version: 2",
        "",
        "models:",
        f"  - name: {shape.union}",
        "    description: >",
        _folded(description, 6),
        *region_test,
        "    columns:",
        f"      - name: {shape.key_column}",
        "        description: The base model's key, carried; unique across the union because the registry key is its first input.",
        "        data_tests: [not_null, unique]",
        "      - name: source_key",
        "        description: The layer's sources.json key.",
        "        data_tests:",
        "          - not_null",
        "          - relationships:",
        "              arguments:",
        "                to: ref('stg_registry__sources')",
        "                field: source_key",
        "      - name: club",
        "        description: The extract folder that landed the row (trail_orgs.json's slug, `-` written `_`).",
        "        data_tests: [not_null]",
    ]
    for name, description in shape.columns:
        lines += [f"      - name: {name}", "        description: >", _folded(description, 10)]
    if shape.clears_stray_points:
        lines += [
            "      - name: geom",
            "        description: >",
            _folded(
                "The feature's geometry as the layer published it, in OGC:CRS84, with a Z where the layer's vertices "
                "carry one; null where it landed with none, or as one point outside the box its source is held to "
                "(`point_outside_region`).",
                10,
            ),
            "      - name: point_outside_region",
            "        description: >",
            _folded(
                "True where the row landed as one point outside the box its source is held to, so `geom` is null "
                "here (macros/lands_outside_its_region.sql's point_outside_its_region); false on every other row. "
                f"int_{type_}__source_extents counts them per source.",
                10,
            ),
            "        data_tests: [not_null]",
            "      - name: properties",
            "        description: The base row's own columns, under dlt's names, as JSON, the geometry left out.",
        ]
    elif shape.geometry:
        lines += [
            "      - name: geom",
            "        description: The feature's geometry as the layer published it, in OGC:CRS84, with a Z where the layer's vertices carry one.",
            "      - name: properties",
            "        description: The base row's own columns, under dlt's names, as JSON, the geometry left out.",
        ]
    else:
        lines += [
            "      - name: properties",
            "        description: The base row's own columns, under dlt's names, as JSON, its prose left out.",
        ]
    lines += [
        "      - name: _loaded_at",
        "        description: When the extract landed the row (dlt's load stamp).",
    ]
    return "\n".join(lines) + "\n"


def hand_set_regions() -> set[str]:
    """The source keys macros/lands_outside_its_region.sql's own `regions` map lists: a box somebody set by hand."""
    import re

    text = (DBT / "macros" / "lands_outside_its_region.sql").read_text()
    block = re.search(r"\{%-?\s*set regions = \{(.*?)\}\s*-?%\}", text, re.S)
    return set(re.findall(r"'([a-z0-9_]+)':", block.group(1))) if block else set()


def regions_macro(all_tables: list[Table]) -> str:
    by_hand = hand_set_regions()
    keys = sorted(
        {
            table.key
            for table in all_tables
            if table.key not in by_hand and table.type not in REGIONS_DECIDED_BY_HAND and table.shape.geometry
        }
    )
    cases = "\n".join(f"    when {{{{ column }}}} = '{key}' then '{DEFAULT_REGION}'" for key in keys)
    return (
        JINJA_MARK
        + """{#-
    The region box each source pipeline/make_dbt_staging.py stages is held
    to, as CASE branches on its key for macros/lands_outside_its_region.sql:
    us_and_territories for every one the macro's own `regions` map does not
    already list, the widest box that still catches a swapped United States
    point. @unvalidated as a fit, and never set from a server's extent (the
    generator's DEFAULT_REGION says why); each source's row of
    int_<type>__source_extents names the narrowest box its vertices fit.
    SQL rather than a returned dict, so SQLFluff's jinja templater renders
    it as dbt does.
-#}
{% macro generated_region_cases(column) -%}
"""
        + cases
        + """
{%- endmacro %}
"""
    )


# --- the run --------------------------------------------------------------------------------------------------


def render() -> dict[Path, str]:
    """Every file this writes, by path, from the registry and the extract's folders as they stand."""
    all_tables = tables()
    files: dict[Path, str] = {}
    by_folder: dict[str, list[Table]] = {}
    for table in all_tables:
        by_folder.setdefault(table.folder, []).append(table)
    staging_by_type: dict[str, list[str]] = {}
    tables_by_type: dict[str, list[Table]] = {}
    for folder, folder_tables in sorted(by_folder.items()):
        root = STAGING / folder
        # A shared resource is one raw table: its source and base come from the type that extracts it.
        owned = [table for table in folder_tables if table.shared_from is None]
        files[root / f"_{folder}__generated__sources.yml"] = sources_yaml(folder, owned)
        files[root / "base" / f"_{folder}__generated__base.yml"] = base_yaml(folder, owned)
        by_type: dict[str, list[Table]] = {}
        for table in folder_tables:
            if table.shared_from is None:
                files[root / "base" / f"{table.base}.sql"] = base_sql(table)
            if not table.lookup:
                by_type.setdefault(table.type, []).append(table)
        for type_, type_tables in sorted(by_type.items()):
            files[root / f"stg_{folder}__{type_}.sql"] = stg_sql(folder, type_, type_tables)
            staging_by_type.setdefault(type_, []).append(f"stg_{folder}__{type_}")
            tables_by_type.setdefault(type_, []).extend(type_tables)
        files[root / f"_{folder}__generated__models.yml"] = models_yaml(folder, by_type)
    for type_, staging_models in sorted(staging_by_type.items()):
        shape = SHAPES[type_]
        files[INTERMEDIATE / type_ / f"{shape.union}.sql"] = union_sql(type_, staging_models)
        files[INTERMEDIATE / type_ / f"_{type_}__generated__intermediate.yml"] = union_yaml(type_, tables_by_type[type_])
    files[REGIONS_MACRO] = regions_macro(all_tables)
    files[IGNORE_LIST] = ignore_list(files)
    # SQLFluff's LT05 holds a model's every line to 80 and runs ten minutes into the dbt job: fail here instead.
    long = [
        f"{path.relative_to(PIPELINE)}:{number}"
        for path, text in files.items()
        if path.suffix == ".sql" and path.parent.name != "macros"
        for number, line in enumerate(text.split("\n"), 1)
        if len(line) > 80
    ]
    if long:
        raise ValueError("generated lines over SQLFluff's 80 columns: " + ", ".join(long))
    return files


#: A path git's ignore syntax reads as itself: no glob character, no leading `!` or `#`, no space to trim.
PLAIN_PATH = re.compile(r"[a-z0-9_][a-z0-9_./-]*")


def ignore_list(files: dict[Path, str]) -> str:
    """models/.gitignore: every file in `files` under models/, anchored to that folder with a leading slash, sorted."""
    paths = sorted(path.relative_to(MODELS).as_posix() for path in files if path.is_relative_to(MODELS))
    odd = [path for path in paths if not PLAIN_PATH.fullmatch(path)]
    if odd:
        raise ValueError(f"a generated path git would not read as itself in {IGNORE_LIST.name}: " + ", ".join(odd))
    return YAML_MARK + "".join(f"/{path}\n" for path in paths)


def generated_on_disk() -> set[Path]:
    """Every file under dbt/ that this generator wrote, by its first line."""
    found = set()
    for path in [*MODELS.rglob("*.sql"), *MODELS.rglob("*.yml"), REGIONS_MACRO, IGNORE_LIST]:
        if path.is_file() and GENERATED in path.read_text().split("\n", 1)[0]:
            found.add(path)
    return found


def differences(files: dict[Path, str]) -> list[str]:
    problems = []
    for path, text in sorted(files.items()):
        if not path.exists():
            problems.append(f"missing: {path.relative_to(PIPELINE)}")
        elif path.read_text() != text:
            problems.append(f"differs: {path.relative_to(PIPELINE)}")
        elif GENERATED not in path.read_text().split("\n", 1)[0]:
            problems.append(f"hand-written file in the way: {path.relative_to(PIPELINE)}")
    for path in sorted(generated_on_disk() - set(files)):
        problems.append(f"stale: {path.relative_to(PIPELINE)}")
    return problems


def write(files: dict[Path, str]) -> None:
    for path, text in files.items():
        if path.exists() and GENERATED not in path.read_text().split("\n", 1)[0]:
            raise FileExistsError(f"{path}: a hand-written file is where a generated one goes; nothing written")
    for path in generated_on_disk() - set(files):
        path.unlink()
    for path, text in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--check", action="store_true", help="write nothing; exit 1 naming each file that would change")
    args = parser.parse_args(argv)
    files = render()
    if args.check:
        problems = differences(files)
        for problem in problems:
            print(problem)
        return 1 if problems else 0
    write(files)
    print(f"{len(files)} generated files written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
