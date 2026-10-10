"""Elementary's checks (decision 102) are where pipeline/ELT.md's "The checks, and where each goes" puts them, at warn.

Read from the project's YAML as it stands, the generated tree included (tests/conftest.py refuses to start without
it), so nothing here runs dbt:

- every Elementary check warns, carries the `elementary_check` tag and is enabled with the checks' own switch alone,
  and no other test carries the tag, because build_marts.py leaves it out of every dbt build and runs it in a pass of
  its own after the writers;
- every raw table, generated or hand-written, carries exactly make_dbt_staging.py's raw_table_checks() for its
  cadence, the one home of them;
- no pub_ writer carries one (ELT.md: each is one row holding a whole phone file);
- every mart carries its own, the safety columns theirs, and exposure_schema_validity sits exactly where
  Elementary 0.26.0 can check something on dbt 2.0.6: a mart one phone file reads, whose exposure names the columns
  it reads in Elementary's type words.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml

import make_dbt_staging

DBT = Path(make_dbt_staging.DBT)
MODELS = DBT / "models"
TAG = make_dbt_staging.ELEMENTARY_CHECK
#: Elementary 0.26.0's normalized type words (utils/data_types/normalize_data_type.sql). The spike measured that an
#: exposure declaring `integer` fails against an INTEGER column and `numeric` passes (ELT.md, "What the spike
#: measured"), so a referenced column's type is one of these.
TYPE_WORDS = {"string", "numeric", "timestamp", "boolean", "other"}


def _documents() -> list[tuple[Path, dict]]:
    return [(path, yaml.safe_load(path.read_text()) or {}) for path in sorted(MODELS.rglob("*.yml"))]


DOCUMENTS = _documents()


def _tests(items: list | None) -> list[tuple[str, dict]]:
    """A `data_tests` list as (test name, its body): `unique` is ("unique", {})."""
    found = []
    for item in items or []:
        if isinstance(item, str):
            found.append((item, {}))
        else:
            ((name, body),) = item.items()
            found.append((name, body or {}))
    return found


def _every_test() -> list[tuple[str, str, dict]]:
    """(where, test name, body) for every generic test any YAML file under models/ declares."""
    found = []
    for path, document in DOCUMENTS:
        where = str(path.relative_to(MODELS))
        for source in document.get("sources") or []:
            for table in source.get("tables") or []:
                holders = [table, *(table.get("columns") or [])]
                found += [(f"{where}: {table['name']}", *test) for holder in holders for test in _tests(holder.get("data_tests"))]
        for model in document.get("models") or []:
            holders = [model, *(model.get("columns") or [])]
            for version in model.get("versions") or []:
                holders += [version, *(column for column in version.get("columns") or [] if "name" in column)]
            found += [(f"{where}: {model['name']}", *test) for holder in holders for test in _tests(holder.get("data_tests"))]
    return found


EVERY_TEST = _every_test()


def _elementary(tests: list[tuple[str, dict]]) -> dict[str, list[dict]]:
    """{Elementary test name: [its bodies]} among `tests`."""
    found: dict[str, list[dict]] = {}
    for name, body in tests:
        if name.startswith("elementary."):
            found.setdefault(name.removeprefix("elementary."), []).append(body)
    return found


def test_there_are_checks_of_every_kind_elt_md_names():
    kinds = {name.removeprefix("elementary.") for _, name, _ in EVERY_TEST if name.startswith("elementary.")}
    assert kinds == {
        "volume_anomalies",
        "schema_changes",
        "freshness_anomalies",
        "event_freshness_anomalies",
        "dimension_anomalies",
        "column_anomalies",
        "all_columns_anomalies",
        "exposure_schema_validity",
    }, "schema_changes_from_baseline is the one kind with nothing to check: every mart's contract is enforced"


def test_every_elementary_check_warns_and_carries_the_tag_and_no_other_test_carries_it():
    """build_marts.py runs exactly the tagged tests in its checks pass and leaves them out of every build: a check that
    lost the tag would run inside a build and could fail it, and a dbt test that gained it would stop blocking."""
    untagged, tagged_other = [], []
    for where, name, body in EVERY_TEST:
        config = body.get("config") or {}
        tags = config.get("tags") or []
        if name.startswith("elementary."):
            # Enabled with the checks' own switch alone (make_dbt_staging.ELEMENTARY_ENABLED says why and when).
            if (
                config.get("severity") != "warn"
                or TAG not in tags
                or config.get("enabled") != make_dbt_staging.ELEMENTARY_ENABLED
            ):
                untagged.append(f"{where}: {name} {config}")
        elif TAG in tags:
            tagged_other.append(f"{where}: {name}")
    assert untagged == []
    assert tagged_other == []
    project = (DBT / "dbt_project.yml").read_text()
    assert TAG not in project, "a project-wide config would tag or untag tests no YAML file shows"


def _cadence(source: dict, table: dict) -> str | None:
    for holder in (table, source):
        found = ((holder.get("config") or {}).get("meta") or {}).get("cadence") or (holder.get("meta") or {}).get("cadence")
        if found:
            return found
    return None


def _loaded_at(source: dict, table: dict) -> str:
    for holder in (table, source):
        found = (holder.get("config") or {}).get("loaded_at_field") or holder.get("loaded_at_field")
        if found:
            return found
    return "_loaded_at"


def _raw_tables() -> list[tuple[str, dict, dict]]:
    return [
        (str(path.relative_to(MODELS)), source, table)
        for path, document in DOCUMENTS
        for source in document.get("sources") or []
        if source.get("schema", source["name"]) == "raw"
        for table in source.get("tables") or []
    ]


def test_every_raw_table_generated_or_hand_written_carries_exactly_the_raw_table_checks_for_its_cadence():
    """make_dbt_staging.py's raw_table_checks() is the one home: both generators write it, and a hand-written source's
    table carries the same list, freshness by its loaded_at_field on an hourly or daily source."""
    tables = _raw_tables()
    assert len(tables) >= 715, "every raw table at d5e97f8c: 631 generated, 84 hand-written"
    wrong = []
    for where, source, table in tables:
        expected = make_dbt_staging.raw_table_checks(_cadence(source, table), _loaded_at(source, table))
        found = [{name: body} for name, body in _tests(table.get("data_tests")) if name.startswith("elementary.")]
        if sorted(map(repr, found)) != sorted(map(repr, expected)):
            wrong.append(f"{where}: {table['name']}")
    assert wrong == []


def test_no_pub_writer_carries_an_elementary_check():
    """ELT.md, "The checks, and where each goes": each writer is one row holding a whole phone file."""
    assert [where for where, name, _ in EVERY_TEST if where.startswith("publish/") and name.startswith("elementary.")] == []


def _marts() -> dict[tuple[str, int | None], dict]:
    """Each mart node, (name, version or None), with its contract columns and the Elementary checks it carries."""
    found = {}
    for path, document in DOCUMENTS:
        if not str(path.relative_to(MODELS)).startswith("marts/"):
            continue
        for model in document.get("models") or []:
            if "columns" not in model:
                continue  # a unit test's own entry
            columns = {column["name"]: column for column in model["columns"]}
            enforced = (((model.get("config") or {}).get("contract")) or {}).get("enforced") is True
            versions = model.get("versions") or [None]
            for version in versions:
                own = columns
                tests = _tests(model.get("data_tests"))
                if version is not None and "columns" in version:
                    included = next((item for item in version["columns"] if "include" in item), {})
                    own = {name: column for name, column in columns.items() if name not in included.get("exclude", [])}
                    own |= {column["name"]: column for column in version["columns"] if "name" in column}
                if version is not None and "data_tests" in version:
                    tests = _tests(version["data_tests"])  # dbt: a version's own list replaces the model's
                key = (model["name"], version["v"] if version is not None else None)
                found[key] = {"columns": own, "enforced": enforced, "checks": _elementary(tests)}
    return found


MARTS = _marts()


def _phone_files_reading() -> dict[tuple[str, int | None], list[str]]:
    """{mart node: the phone-file exposures (meta.r2_keys) whose depends_on names it}, a bare ref to a versioned mart
    being its latest version (every one is v1 here)."""
    versioned = {name for name, version in MARTS if version is not None}
    readers: dict[tuple[str, int | None], list[str]] = {}
    for _, document in DOCUMENTS:
        for exposure in document.get("exposures") or []:
            if "r2_keys" not in ((exposure.get("config") or {}).get("meta") or {}):
                continue
            for ref in exposure.get("depends_on") or []:
                found = re.fullmatch(r"ref\('(\w+)'(?:,\s*v=(\d+))?\)", ref)
                if found and any(name == found.group(1) for name, _ in MARTS):
                    version = int(found.group(2)) if found.group(2) else (1 if found.group(1) in versioned else None)
                    readers.setdefault((found.group(1), version), []).append(exposure["name"])
    return readers


READERS = _phone_files_reading()


@pytest.mark.parametrize("mart", sorted(MARTS, key=str), ids=lambda mart: f"{mart[0]}_v{mart[1]}")
def test_every_mart_carries_its_rows_its_null_rates_and_its_rows_per_club_and_source(mart):
    node = MARTS[mart]
    checks = node["checks"]
    assert len(checks.get("volume_anomalies", [])) == 1
    (all_columns,) = checks.get("all_columns_anomalies", [{}])
    assert all_columns.get("arguments", {}).get("column_anomalies") == ["null_percent"], "null rate only (ELT.md)"
    excluded = re.compile(all_columns["arguments"].get("exclude_regexp") or "^$", re.IGNORECASE)
    assert "geom_geojson" not in node["columns"] or excluded.match("geom_geojson"), "geometry is left out"
    by_club = {"club", "source_key"} <= set(node["columns"])
    assert [body["arguments"]["dimensions"] for body in checks.get("dimension_anomalies", [])] == (
        [["club", "source_key"]] if by_club else []
    ), "rows per club and source wherever a mart has both"
    # A contracted mart already fails its build on a changed column (ELT.md), so the baseline check is for the others.
    assert ("schema_changes_from_baseline" in checks) == (not node["enforced"])


@pytest.mark.parametrize("mart", sorted(MARTS, key=str), ids=lambda mart: f"{mart[0]}_v{mart[1]}")
def test_exposure_schema_validity_sits_exactly_on_each_mart_one_phone_file_reads(mart):
    """With more than one exposure on a mart, Elementary 0.26.0 matches each column to its mart through
    context["render"], which dbt 2.0.6 does not have: the test errored there (measured 2026-10-08), and without a `node`
    it passes having checked nothing. So it goes only where one phone file reads the mart."""
    readers = READERS.get(mart, [])
    assert ("exposure_schema_validity" in MARTS[mart]["checks"]) == (len(readers) == 1), readers


def _referenced_columns() -> dict[str, list[dict]]:
    return {
        exposure["name"]: exposure["config"]["meta"]["referenced_columns"]
        for _, document in DOCUMENTS
        for exposure in document.get("exposures") or []
        if "referenced_columns" in ((exposure.get("config") or {}).get("meta") or {})
    }


def _normalized(data_type: str) -> str:
    """A contract type in Elementary 0.26.0's words, as its duckdb__data_type_list() sorts DuckDB's types."""
    base = data_type.lower().split("(")[0].strip()
    if base in ("varchar", "text", "string"):
        return "string"
    if base in ("integer", "bigint", "smallint", "tinyint", "decimal", "numeric", "double", "float", "real", "hugeint"):
        return "numeric"
    if base in ("date", "timestamp", "timestamptz"):
        return "timestamp"
    return "boolean" if base == "boolean" else "other"


def test_each_one_reader_exposure_names_the_columns_it_reads_in_elementarys_words_and_no_other_exposure_does():
    referenced = _referenced_columns()
    only = {readers[0]: mart for mart, readers in READERS.items() if len(readers) == 1}
    assert set(referenced) == set(only), "referenced_columns on another exposure would be checked nowhere"
    for exposure, columns in referenced.items():
        contract = MARTS[only[exposure]]["columns"]
        assert columns, exposure
        for column in columns:
            assert set(column) == {"column_name", "data_type"}, f"{exposure}: no `node`, which needs context['render']"
            assert column["data_type"] in TYPE_WORDS, f"{exposure}: {column}"
            assert column["column_name"] in contract, f"{exposure}: {column['column_name']} is no column of {only[exposure]}"
            assert column["data_type"] == _normalized(contract[column["column_name"]]["data_type"]), f"{exposure}: {column}"


#: The safety columns (decision 102: water distance, elevation, trail status, closure dates) and the monitors each
#: carries: Elementary's minimum and maximum are numeric monitors only (0.26.0's get_available_monitors()).
SAFETY_COLUMNS = {
    ("points_of_interest", 1, "water_distance_ft"): ["null_percent", "min", "max"],
    ("points_of_interest", 2, "water_distance_ft"): ["null_percent", "min", "max"],
    ("elevation", 1, "elevation_ft"): ["null_percent", "min", "max"],
    ("elevation", 2, "elevation_deci_ft"): ["null_percent", "min", "max"],
    ("trail_lines", 1, "trail_status"): ["null_percent"],
    ("trail_lines", 2, "trail_status"): ["null_percent"],
    ("closures", 1, "starts_on"): ["null_percent"],
    ("closures", 1, "ends_on"): ["null_percent"],
    ("closures", 1, "expected_reopen"): ["null_percent"],
}


@pytest.mark.parametrize(("mart", "version", "column"), sorted(SAFETY_COLUMNS), ids=lambda part: str(part))
def test_each_safety_column_carries_its_null_rate_and_where_numeric_its_range(mart, version, column):
    found = _elementary(_tests(MARTS[(mart, version)]["columns"][column].get("data_tests")))
    assert [body["arguments"]["column_anomalies"] for body in found.get("column_anomalies", [])] == [
        SAFETY_COLUMNS[(mart, version, column)]
    ]


def test_no_other_column_carries_a_column_check():
    carried = {
        (name, version, column)
        for (name, version), node in MARTS.items()
        for column, body in node["columns"].items()
        if "column_anomalies" in _elementary(_tests(body.get("data_tests")))
    }
    assert carried == set(SAFETY_COLUMNS)


def test_elementarys_training_and_detection_settings_are_its_defaults_written_where_dbt_reads_them():
    """dbt_project.yml's vars say why each, and why min_training_set_size is not among them (0.26.0 reads it nowhere)."""
    variables = yaml.safe_load((DBT / "dbt_project.yml").read_text())["vars"]
    assert {name: variables.get(name) for name in ("days_back", "backfill_days", "anomaly_sensitivity")} == {
        "days_back": 14,
        "backfill_days": 2,
        "anomaly_sensitivity": 3,
    }
    assert "min_training_set_size" not in variables
    assert variables["test_sample_row_count"] == 0, "no failing row is kept (decision 102's rules)"


#: The anomaly-test arguments that would let a check fire before its window holds the 11 points
#: macros/data_quality.sql's `learning.needed` derives from the project's anomaly_sensitivity: a lower sensitivity
#: (either spelling), a zero that fails on sight, or a training set that leaves the scored point out of its own.
EARLIER_FIRING = ("anomaly_sensitivity", "sensitivity", "fail_on_zero", "exclude_detection_period_from_training")


def test_no_check_and_no_project_var_changes_how_many_builds_an_anomaly_check_waits_for():
    """learning.needed is one number for the whole file, worked out from the project's vars alone, so no check may
    carry its own (0.26.0's get_test_argument() would let a check's argument or its model's config win)."""
    variables = yaml.safe_load((DBT / "dbt_project.yml").read_text())["vars"]
    assert [name for name in EARLIER_FIRING[2:] if variables.get(name)] == []
    own = [
        f"{where}: {name} {field}"
        for where, name, body in EVERY_TEST
        if name.startswith("elementary.")
        for field in EARLIER_FIRING
        if field in (body.get("arguments") or {}) or field in body
    ]
    assert own == []
    models = [
        f"{path.relative_to(MODELS)}: {model['name']}"
        for path, document in DOCUMENTS
        for model in document.get("models") or []
        if "elementary" in ((model.get("config") or {}).get("meta") or {}) or "elementary" in (model.get("meta") or {})
    ]
    assert models == [], "a model's own elementary config would set these for every check on it"


def test_no_test_asks_elementary_for_its_failing_rows():
    """dbt_project.yml's test_sample_row_count 0 is the only word on samples: 0.26.0's handle_dbt_test() takes a
    test's own meta test_sample_row_count over the var, and nothing else it reads raises the limit."""
    asking = []
    for where, name, body in EVERY_TEST:
        config = body.get("config") or {}
        meta = {**(body.get("meta") or {}), **(config.get("meta") or {})}
        if "test_sample_row_count" in meta:
            asking.append(f"{where}: {name}")
    singular = [
        str(path.relative_to(DBT))
        for path in sorted((DBT / "tests").rglob("*.sql"))
        if "test_sample_row_count" in path.read_text()
    ]
    assert (asking, singular) == ([], [])
    project = yaml.safe_load((DBT / "dbt_project.yml").read_text())
    assert "test_sample_row_count" not in json.dumps(project.get("data_tests") or {})
