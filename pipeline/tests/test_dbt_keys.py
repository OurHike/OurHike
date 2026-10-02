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
from pathlib import Path

import pytest
import yaml

DBT = Path(__file__).resolve().parent.parent / "dbt"
STAGING = DBT / "models" / "staging"
KEY_LINE = re.compile(r"\{\{\s*dbt_utils\.generate_surrogate_key\((\[.*?\])\)\s*\}\}\s+as\s+(\w+_key)\b", re.S)
DEDUPE = re.compile(
    r"\{\{\s*dbt_utils\.deduplicate\(\s*relation='renamed',\s*partition_by='(\w+)',\s*order_by='(\w+)'\s*\)\s*\}\}\s*$"
)
SOURCE = re.compile(r"source\('([a-z_]+)',\s*'([a-z_]+)'\)")
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


def models_yaml() -> dict:
    found = {}
    for path in [*STAGING.rglob("_*__models.yml"), *STAGING.rglob("_*__base.yml")]:
        for model in yaml.safe_load(path.read_text())["models"]:
            found[model["name"]] = model
    return found


def source_tests() -> dict:
    found = {}
    for path in STAGING.rglob("_*__sources.yml"):
        for source in yaml.safe_load(path.read_text())["sources"]:
            for table in source.get("tables", []):
                found[(source["name"], table["name"])] = table.get("data_tests") or []
    return found


def test_there_are_staging_models_to_check():
    assert len(MODELS) >= 27 + 28


def _reviewed_tables() -> set[str]:
    """The raw tables the extract loads from reviewed files in git, which carry no geometry."""
    from extract._contract import all_resources, discover, discover_shared
    from extract._kinds import ReviewedDir, ReviewedFile

    resources = all_resources(discover() + discover_shared())
    return {resource.table for resource in resources if isinstance(resource, ReviewedFile | ReviewedDir)}


def _row_tables() -> set[str]:
    """The raw tables of the kinds whose rows have no geometry column: WordPress posts and their place
    terms, OurHike's own conditions queries, whose closures, reports and notes give a place as lat/lon,
    and ATC's Trail Updates pages, which give one as an A.T. mile."""
    from extract._contract import all_resources, discover, discover_shared
    from extract._kinds import AtcTrailUpdatePages, ConditionsQuery, WordpressPosts, WordpressTerms

    resources = all_resources(discover() + discover_shared())
    kinds = WordpressPosts | WordpressTerms | ConditionsQuery | AtcTrailUpdatePages
    return {resource.table for resource in resources if isinstance(resource, kinds)}


SPATIAL_MODELS = [path for path in MODELS if SOURCE.search(path.read_text()).group(2) not in _reviewed_tables() | _row_tables()]


def test_the_row_kinds_models_read_no_geometry():
    assert {path.stem for path in MODELS if SOURCE.search(path.read_text()).group(2) in _row_tables()} == {
        "base_nynjtc__nynjtc_trail_alerts",
        "base_nynjtc__nynjtc_trail_alerts_terms",
        "base_ourhike__closures",
        "base_ourhike__reports",
        "base_ourhike__notes",
        "base_ourhike__disputes",
        "base_atc__atc_trail_updates_pages",
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
