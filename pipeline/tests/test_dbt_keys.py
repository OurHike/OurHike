"""Decision 40 of #1793, held without a warehouse: every staging model keys and dedupes its rows the same way.

The maintainer, 2026-10-01: "every table needs a unique id. Use the dbt_utils
package in dbt, and call the generate_surrogate_key() macro to create the key
based on current values... staging tables should only do 2 main things. data
type conversion / field renaming & dedupe source tables." pipeline/ELT.md, "One
key per table", has the measurement behind each key.

A key is written twice: in the staging model, which builds it with
dbt_utils.generate_surrogate_key, and on the model's raw table, whose
duplicates_are_exact test checks that rows sharing it are exact copies. If the
two lists drift, the test checks a key the model does not build, and the
dedupe can drop a real feature with every test green. So this file reads both
and holds them equal, along with the rest of the shape: a key on every staging
model, tested unique and not null, and a dedupe on that key.
"""

import ast
import re
from functools import cache
from pathlib import Path

import pytest
import yaml

DBT = Path(__file__).resolve().parent.parent / "dbt"
STAGING = DBT / "models" / "staging"
KEY_LINE = re.compile(r"\{\{\s*dbt_utils\.generate_surrogate_key\((\[.*?\])\)\s*\}\}\s+as\s+(\w+_key)\b", re.S)
DEDUPE = re.compile(
    r"\{\{\s*dbt_utils\.deduplicate\(\s*relation='renamed',\s*partition_by='(\w+)',\s*order_by='(\w+)'\s*\)\s*\}\}\s*$"
)
# Digits too: a raw table's key may hold one (raw_shta__shta_line_2025), and a model whose source() this
# pattern missed would leave every check below silently. Whitespace too, for a call split across lines to
# keep within SQLFluff's line length (pipeline/generate_notice_models.py's).
SOURCE = re.compile(r"source\(\s*'([a-z0-9_]+)',\s*'([a-z0-9_]+)'\s*\)")
# Every model that keys and dedupes a raw table, which is every staging model that reads a
# source() (decision 40): the stg_ models of the first 28, and the base_ models stage 3 adds
# for the rest (ELT.md, "The dbt project"). A stg_ model that reads a base model, as the
# registry's do, has its key from that base model.
MODELS = sorted(path for path in [*STAGING.rglob("stg_*.sql"), *STAGING.rglob("base_*.sql")] if SOURCE.search(path.read_text()))
# A staging model's `geom`, as its raw table holds it: dlt lands geometry as
# GeoJSON text, and every model casts it in its source CTE with exactly this.
RAW_GEOMETRY = "st_geomfromgeojson(cast(geometry as varchar))"


def geometry_key_body() -> str:
    """What `geometry_key('geom')` renders to, read from the macro itself."""
    text = (DBT / "macros" / "geometry_key.sql").read_text()
    body = re.search(r"\{%\s*macro geometry_key\(column\)\s*-?%\}\s*(.*?)\s*\{%-?\s*endmacro", text, re.S).group(1)
    return body.replace("{{ column }}", "geom")


def model_key(path: Path) -> tuple[str, list[str]]:
    match = KEY_LINE.search(path.read_text())
    assert match, f"{path.name}: no `{{{{ dbt_utils.generate_surrogate_key([...]) }}}} as <thing>_key` line"
    items = match.group(1).replace("geometry_key('geom')", repr(geometry_key_body()))
    return match.group(2), ast.literal_eval(items)


# Read once: every parametrized case below asks, and there are hundreds (decisions 53's and 54's generated
# models).
@cache
def models_yaml() -> dict:
    found = {}
    for path in [*STAGING.rglob("_*__models.yml"), *STAGING.rglob("_*__base.yml")]:
        for model in yaml.safe_load(path.read_text())["models"]:
            found[model["name"]] = model
    return found


@cache
def source_tests() -> dict:
    found = {}
    for path in STAGING.rglob("_*__sources.yml"):
        for source in yaml.safe_load(path.read_text())["sources"]:
            for table in source.get("tables", []):
                found[(source["name"], table["name"])] = table.get("data_tests") or []
    return found


def test_there_are_staging_models_to_check():
    assert len(MODELS) >= 27 + 28


@cache
def _reviewed_tables() -> frozenset[str]:
    """The raw tables the extract loads from reviewed files in git, which carry no geometry."""
    from extract._contract import all_resources, discover, discover_shared
    from extract._kinds import ReviewedDir, ReviewedFile

    resources = all_resources(discover() + discover_shared())
    return frozenset(resource.table for resource in resources if isinstance(resource, ReviewedFile | ReviewedDir))


@cache
def _row_tables() -> frozenset[str]:
    """The raw tables of the kinds whose rows have no geometry column: WordPress posts and their place
    terms, OurHike's own conditions queries, whose closures, reports and notes give a place as lat/lon, the
    Hike Finder's pages, whose one coordinate is a lat/lon pair in `start`, ATC's Trail Updates pages,
    which give one as an A.T. mile, and a guide's section pages (the guide_pages kind), whose entries carry
    NYNJTC's own coordinates and miles inside their JSON."""
    from extract._contract import all_resources, discover, discover_shared
    from extract._json_apis import (
        DcnrParkAdvisories,
        MediawikiAnnouncements,
        NpsAlerts,
        SheetCsvSegments,
        UsgsElevatedVolcanoes,
    )
    from extract._kinds import (
        AtcTrailUpdatePages,
        ConditionsQuery,
        FeedNotices,
        GuidePages,
        PageNotice,
        PublishedHikes,
        WordpressPosts,
        WordpressTerms,
    )

    resources = all_resources(discover() + discover_shared())
    kinds = WordpressPosts | WordpressTerms | ConditionsQuery | PublishedHikes | AtcTrailUpdatePages | GuidePages
    # Decision 53's notice readers whose rows carry no geometry (pipeline/generate_notice_models.py's READERS).
    kinds |= FeedNotices | PageNotice | NpsAlerts | DcnrParkAdvisories | UsgsElevatedVolcanoes | MediawikiAnnouncements
    kinds |= SheetCsvSegments
    return frozenset(resource.table for resource in resources if isinstance(resource, kinds)) - _content_tables()


@cache
def _content_tables() -> frozenset[str]:
    """Section C's content tables (decision 54 wave 3): the raw tables pipeline/make_dbt_staging.py stages for a type
    whose shape carries no geometry (podcast episodes, write-ups, list items, photo manifest rows). A club page's points
    table a content type SHARES (Table.page_rows, the Palmetto Trail's passages) is not one: it is the points' own raw
    table, geometry and all, and its base model is the points'."""
    import make_dbt_staging

    return frozenset(table.table for table in make_dbt_staging.tables() if not table.shape.geometry and not table.page_rows)


#: The derived tables a Python step writes with no geometry column (build_marts.py's STEPS): step_form_route's
#: routes carry their ends as JSON lists of [lon, lat] at full precision, the exact doubles the graph search used,
#: and step_weather_squares lands squares.json as one JSON document. The POI family's: site_water names each
#: A.T. site by its global id and its water as JSON, osm_water carries fetch_osm_water.py's lon/lat columns,
#: osm_water_grade is a verdict per osm_id, poi_photos is manifest rows, and long_path_guide holds each record
#: whole as JSON. dem_samples and graph_pieces have a geometry.
GEOMETRY_FREE_STEP_TABLES = {
    "formed_routes",
    "weather_squares",
    "site_water",
    "osm_water",
    "osm_water_grade",
    "poi_photos",
    "long_path_guide",
}


def test_the_geometry_free_step_tables_are_the_derived_tables_that_declare_no_geometry():
    declared = {}
    for path in (STAGING / "derived").rglob("_*__sources.yml"):
        for source in yaml.safe_load(path.read_text())["sources"]:
            for table in source.get("tables") or []:
                declared[table["name"]] = {column["name"] for column in table.get("columns") or []}
    assert {name for name, columns in declared.items() if "geometry" not in columns} == GEOMETRY_FREE_STEP_TABLES


#: The extract's own run log (extract/_run.py's RUNS_TABLE), one row per resource per run, which holds no geometry.
RUN_LOG_TABLES = {"_extract_runs"}


def test_the_run_log_table_is_the_one_extract_run_writes():
    from extract._run import RUNS_TABLE

    assert RUN_LOG_TABLES == {RUNS_TABLE}
    assert {path.stem for path in MODELS if SOURCE.search(path.read_text()).group(2) in RUN_LOG_TABLES} == {"base_extract__runs"}


#: The closures and warnings marts' own snapshots, read back as sources (staging/row_history/, decision 53's
#: phase C): rows of int_<mart>__final, whose geometry is GeoJSON text already, never a raw geometry column.
ROW_HISTORY_TABLES = {"int_closures__history", "int_warnings__history"}


def test_the_row_history_tables_are_the_two_conditions_marts_snapshots():
    snapshots = {path.stem for path in (DBT / "snapshots").rglob("int_*__history.sql")}
    assert ROW_HISTORY_TABLES <= snapshots
    assert {path.stem for path in MODELS if SOURCE.search(path.read_text()).group(2) in ROW_HISTORY_TABLES} == {
        "stg_row_history__closures",
        "stg_row_history__warnings",
    }


SPATIAL_MODELS = [
    path
    for path in MODELS
    if SOURCE.search(path.read_text()).group(2)
    not in _reviewed_tables()
    | _row_tables()
    | GEOMETRY_FREE_STEP_TABLES
    | RUN_LOG_TABLES
    | ROW_HISTORY_TABLES
    | _content_tables()
]


@cache
def _generated_row_models() -> set[str]:
    """The base models pipeline/generate_notice_models.py writes for a notice reader that lands no geometry."""
    import generate_notice_models

    return {
        source.base_model
        for source in generate_notice_models.notice_sources()
        if not source.hand_staged and not source.reader.spatial
    }


def test_the_content_models_are_generated_and_read_no_geometry():
    """Each of section C's content base models is the generator's, and none casts a geometry its source does not have."""
    content = [path for path in MODELS if SOURCE.search(path.read_text()).group(2) in _content_tables()]
    assert len(content) == len(_content_tables()), "one generated base model per content table"
    for path in content:
        text = path.read_text()
        assert text.startswith("-- GENERATED by pipeline/make_dbt_staging.py"), path.name
        assert path.stem.startswith("base_") and "st_geomfromgeojson" not in text, path.name


def test_the_row_kinds_models_read_no_geometry():
    assert {
        path.stem for path in MODELS if SOURCE.search(path.read_text()).group(2) in _row_tables()
    } == _generated_row_models() | {
        "base_nynjtc__nynjtc_trail_alerts",
        "base_nynjtc__nynjtc_trail_alerts_terms",
        "base_ourhike__closures",
        "base_ourhike__reports",
        "base_ourhike__notes",
        "base_ourhike__disputes",
        "base_atc__atc_trail_updates_pages",
        "base_nynjtc__nynjtc_hike_finder",
        "stg_nynjtc__long_path_guide",
    }


def test_only_the_reviewed_file_models_read_no_geometry():
    assert {path.stem for path in MODELS if SOURCE.search(path.read_text()).group(2) in _reviewed_tables()} == {
        "base_podcasts__podcast_episodes",
        "base_ourhike__poi_identity",
        "base_ourhike__blaze_mapping",
        "base_ourhike__trail_name_aliases",
        "base_registry__sources",
        "base_registry__nynjtc_paper_maps",
        "base_atc__atc_trail_updates",
        "base_atc__atc_updates",
        "base_atc__water_distance",
        "base_greenbelly__shelter_capacity",
        "base_ourhike__work_projects",
        "base_ourhike__highlights",
        "base_nynjtc__nynjtc_hike_photos",
        "base_atc__challenges_atc",
        "base_ourhike__challenges_publishers",
    }


@pytest.mark.parametrize("path", SPATIAL_MODELS, ids=lambda p: p.stem)
def test_each_staging_model_casts_geometry_from_its_raw_table_the_one_way(path):
    """The source CTE's cast is what RAW_GEOMETRY stands for, so a model that casts differently fails here, not in a key."""
    assert f"{RAW_GEOMETRY} as geom" in path.read_text(), f"{path.name} does not cast its raw geometry with {RAW_GEOMETRY}"


@pytest.mark.parametrize("path", MODELS, ids=lambda p: p.stem)
def test_each_staging_model_builds_its_key_and_dedupes_on_it(path):
    key_column, inputs = model_key(path)
    assert inputs and inputs[0].startswith("'") and inputs[0].endswith("'"), (
        "the first input is the registry key as a literal, so a key stays unique once sources are unioned"
    )
    assert len(inputs) >= 2, "a key needs at least one column beside the registry key"
    dedupe = DEDUPE.search(path.read_text().rstrip())
    assert dedupe, (
        f"{path.name} must end with {{{{ dbt_utils.deduplicate(relation='renamed', partition_by='{key_column}', ...) }}}}"
    )
    assert dedupe.group(1) == key_column


@pytest.mark.parametrize("path", MODELS, ids=lambda p: p.stem)
def test_each_staging_key_is_tested_unique_and_not_null(path):
    key_column, _ = model_key(path)
    model = models_yaml()[path.stem]
    columns = {column["name"]: column for column in model.get("columns", [])}
    assert key_column in columns, f"{path.stem}: no YAML entry for {key_column}"
    assert {"unique", "not_null"} <= set(columns[key_column].get("data_tests", []))


@pytest.mark.parametrize("path", MODELS, ids=lambda p: p.stem)
def test_the_raw_tables_exactness_test_checks_the_key_the_model_builds(path):
    _, inputs = model_key(path)
    source = SOURCE.search(path.read_text()).groups()
    tests = [t["duplicates_are_exact"] for t in source_tests()[source] if isinstance(t, dict) and "duplicates_are_exact" in t]
    assert len(tests) == 1, f"{source[1]} needs one duplicates_are_exact test"
    expected = [item.replace("source.", "").replace("(geom)", f"({RAW_GEOMETRY})") for item in inputs]
    assert tests[0]["arguments"]["key_columns"] == expected, (
        f"{path.stem} builds its key from {expected}, but {source[1]}'s duplicates_are_exact checks "
        f"{tests[0]['arguments']['key_columns']}"
    )


@cache
def _socrata_tables() -> frozenset[str]:
    """The raw tables extract/_kinds.py's SocrataDataset lands, each row carrying Socrata's `:id` as `_socrata_id`."""
    from extract._contract import all_resources, discover, discover_shared
    from extract._kinds import SocrataDataset

    resources = all_resources(discover() + discover_shared())
    return frozenset(resource.table for resource in resources if isinstance(resource, SocrataDataset))


SOCRATA_MODELS = [path for path in MODELS if SOURCE.search(path.read_text()).group(2) in _socrata_tables()]
#: Where duplicates_are_exact's default row ids live: row_hash_row_ids(), which the row-history snapshots share.
ROW_HASH_MACROS = DBT / "macros" / "row_hash.sql"


def test_the_socrata_models_are_the_seven_nyc_base_models():
    assert {path.stem for path in SOCRATA_MODELS} == {
        "base_nycdot__nyc_cscl_paths",
        "base_nycdot__nyc_dot_greenways",
        "base_nycdot__nyc_park_drives",
        "base_nycparks__nyc_drinking_fountains",
        "base_nycparks__nyc_park_polygons",
        "base_nycparks__nyc_parks_trails",
        "base_nycparks__nyc_public_restrooms",
    }


@pytest.mark.parametrize("path", SOCRATA_MODELS, ids=lambda p: p.stem)
def test_each_socrata_tables_duplicates_are_exact_skips_socrata_id_as_a_row_id(path):
    """Socrata mints `:id` per row, so two copies of one record always differ in it.

    Without `_socrata_id` among the row ids, duplicates_are_exact failed the monthly lane's first live
    build (refresh-reference.yml run 37109384156) on nyc_dot_greenways, nyc_parks_trails and
    nyc_public_restrooms, whose repeated rows differ in nothing else (measured 2026-10-03).
    """
    source = SOURCE.search(path.read_text()).groups()
    (test,) = [t["duplicates_are_exact"] for t in source_tests()[source] if isinstance(t, dict) and "duplicates_are_exact" in t]
    row_ids = test["arguments"].get("row_id_columns")
    if row_ids is None:
        default = re.search(r"macro row_hash_row_ids\(\).*?return\((\[.*?\])\)", ROW_HASH_MACROS.read_text(), re.S)
        assert default, f"{ROW_HASH_MACROS.name}: no row_hash_row_ids() list to read"
        row_ids = ast.literal_eval(default.group(1))
    assert "_socrata_id" in row_ids, f"{source[1]}'s duplicates_are_exact compares `_socrata_id`, so every copy fails it"


@pytest.mark.parametrize("path", SOCRATA_MODELS, ids=lambda p: p.stem)
def test_each_socrata_model_keeps_the_copy_with_the_lowest_socrata_id(path):
    """`_socrata_id` is the published id of a Socrata POI or line, so the survivor is chosen by it, not by `_dlt_id`.

    dlt mints `_dlt_id` at random on each load, so ordering by it could publish a different copy's id
    from the same upstream rows each month; parity.py's _exact_copy_reasons expects the lowest id kept.
    """
    assert DEDUPE.search(path.read_text().rstrip()).group(2) == "_socrata_id"
