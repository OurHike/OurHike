"""Every dbt model has one id: a column that is unique and not null (decision 197).

The maintainer, 2026-10-15: "Every dbt model should have a unique id that is unique and not null.
If you made exceptions, we need to talk about that", then "surrogate key is fine too", and, asked
how to enforce it, "Multi column is fine if it is based on the dbt generate surrogate key macro".
So a key is ONE COLUMN of the model, and a key over several columns is a
dbt_utils.generate_surrogate_key column, never a bare dbt_utils.unique_combination_of_columns test.

What counts, for every `ourhike` model in the parsed manifest, each version of a versioned model
on its own:

- an unfiltered `unique` test at error on the column, and
- on the same column, an unfiltered `not_null` test at error, or a not_null constraint under an
  enforced contract, which the build itself enforces.

"Unfiltered at error" is a test that fails the build on its first failing row: dbt's own
`unique` or `not_null` generic test (macro.dbt.test_unique, macro.dbt.test_not_null), no
`where`, severity error, dbt's default `fail_calc`, and no tolerance in either threshold: dbt's
default `!= 0`, or `>0`, which dbt_project.yml declares for every test since decision 204. A
`where` or a threshold above that lets some duplicates through, which is no key. The severity
is read as dev and CI parse it, with OURHIKE_DATA_ENV unset, where decision 204's switch makes
it error; in production and UA the same switch makes a failing key test a warning that
build_marts.py reports as an error, and the build goes on.

WHY dbt_project_evaluator IS NOT ENOUGH. Its fct_missing_primary_key_tests reads neither a test's
severity nor its `where` (int_model_test_summary.sql, 1.4.0), and its default
primary_key_test_macros counts unique_combination_of_columns as a key. dbt_project.yml's
`primary_key_test_macros` now names only the unique and not_null pair, which closes the second;
this file closes the first. Measured on ad932107's manifest (2026-10-15, before decision 197 was
built): of 1,593 models, 1,579 met this rule, 12 were keyed only by a combination test, and 2 had
their key at warn. The 12 now carry a generate_surrogate_key column; the 2 are the exceptions.

THE EXCEPTIONS are rows of dbt/seeds/model_key_exceptions.csv: the maintainer's, in the same poll,
for the two hourly area-cut models whose key tests warn, "Keep warn, a recorded exception". This
file fails a model with no key and no row, a row naming no model, a row whose model now meets the
rule, and a row whose column does not carry both tests at the row's severity, so a row cannot
outlive its reason or describe a key that is not there.

What this cannot check: that a test it counts is selected by every lane that builds the model
(a lane's --select can leave it out), or that the column means what a reader would call an id
(line_sample_key hashes a position along a line, as the key it replaced did). It reads the
manifest, so the part that needs one runs only where OURHIKE_DBT names dbt 2.0.6
(pipeline-tests.yml's dbt job and scripts/test.sh's dbt suite); the checker itself is tested here
on hand-made manifests without one.
"""

import csv
import datetime
import itertools
import json
import os
import subprocess
from collections import defaultdict
from pathlib import Path

import pytest
import yaml

DBT_DIR = Path(__file__).parent.parent / "dbt"
EXCEPTIONS_PATH = DBT_DIR / "seeds" / "model_key_exceptions.csv"
COLUMNS = ["model", "column_name", "severity", "reason", "decided"]
DBT = os.environ.get("OURHIKE_DBT")
PROJECT = "ourhike"

#: The two halves of a key, as dbt's own generic tests: the evaluator's primary_key_test_macros
#: names them dbt.test_unique and dbt.test_not_null, and a test node depends on the macro.
KEY_TESTS = {"unique": "macro.dbt.test_unique", "not_null": "macro.dbt.test_not_null"}


def model_name(node: dict) -> str:
    """A model as the evaluator names it (int_all_graph_resources.sql): `name.vN` for one version, else `name`."""
    return f"{node['name']}.v{node['version']}" if node.get("version") is not None else node["name"]


#: A threshold with no tolerance, spaces aside: dbt's default, and decision 204's form (dbt_project.yml).
NO_TOLERANCE = frozenset({"!=0", ">0", ">=1", "<>0"})


def _is(test: dict, severity: str) -> bool:
    """Unfiltered at `severity`, failing on its first failing row: no `where`, no tolerance in either threshold."""
    config = test.get("config") or {}
    return (
        not config.get("where")
        and str(config.get("severity", "error")).lower() == severity
        and "".join(str(config.get("error_if", "!= 0")).split()) in NO_TOLERANCE
        and "".join(str(config.get("warn_if", "!= 0")).split()) in NO_TOLERANCE
        and config.get("fail_calc", "count(*)") == "count(*)"
    )


def _key_tests(manifest: dict) -> dict:
    """{model id: {column: {"unique": [test, ...], "not_null": [...]}}}, dbt's own two tests only."""
    found = defaultdict(lambda: defaultdict(lambda: {"unique": [], "not_null": []}))
    for node in (manifest.get("nodes") or {}).values():
        if node.get("resource_type") != "test":
            continue
        kind = (node.get("test_metadata") or {}).get("name")
        macros = (node.get("depends_on") or {}).get("macros") or []
        if kind in KEY_TESTS and KEY_TESTS[kind] in macros and node.get("attached_node") and node.get("column_name"):
            found[node["attached_node"]][node["column_name"].lower()][kind].append(node)
    return found


def _not_null_constrained(node: dict) -> set[str]:
    """The columns a not_null constraint holds: none unless the contract is enforced, which is what enforces it."""
    if not (node.get("contract") or {}).get("enforced"):
        return set()
    held = {
        name.lower()
        for name, column in (node.get("columns") or {}).items()
        if any(constraint.get("type") == "not_null" for constraint in column.get("constraints") or [])
    }
    for constraint in node.get("constraints") or []:
        if constraint.get("type") == "not_null":
            held |= {name.lower() for name in constraint.get("columns") or []}
    return held


def _columns_keyed_at(node: dict, tests: dict, severity: str) -> set[str]:
    """The columns carrying an unfiltered unique test and an unfiltered not_null (or an enforced constraint) at `severity`."""
    held = _not_null_constrained(node) if severity == "error" else set()
    return {
        column
        for column, kinds in tests.items()
        if any(_is(test, severity) for test in kinds["unique"])
        and (column in held or any(_is(test, severity) for test in kinds["not_null"]))
    }


def check(manifest: dict, rows: list[dict]) -> dict[str, list[str]]:
    """Decision 197 over a parsed manifest and the exceptions seed's rows: every list empty means it holds.

    - `unkeyed`: a model with no key and no row;
    - `unknown`: a row naming no model of the project;
    - `keyed_now`: a row whose model meets the rule, so the row excepts nothing;
    - `not_as_recorded`: a row whose column does not carry both tests at the row's severity.
    """
    tests = _key_tests(manifest)
    models = {
        model_name(node): (unique_id, node)
        for unique_id, node in (manifest.get("nodes") or {}).items()
        if node.get("resource_type") == "model" and node.get("package_name") == PROJECT
    }
    excepted = {row["model"]: row for row in rows}
    verdict = {"unkeyed": [], "unknown": [], "keyed_now": [], "not_as_recorded": [], "keyed": []}
    for name, (unique_id, node) in sorted(models.items()):
        if _columns_keyed_at(node, tests.get(unique_id, {}), "error"):
            verdict["keyed_now" if name in excepted else "keyed"].append(name)
        elif name not in excepted:
            verdict["unkeyed"].append(name)
    for name, row in sorted(excepted.items()):
        if name not in models:
            verdict["unknown"].append(name)
            continue
        unique_id, node = models[name]
        if row["column_name"].lower() not in _columns_keyed_at(node, tests.get(unique_id, {}), row["severity"].lower()):
            verdict["not_as_recorded"].append(f"{name}.{row['column_name']} at {row['severity']}")
    return verdict


def _rows() -> list[dict]:
    with open(EXCEPTIONS_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames == COLUMNS, f"the exceptions seed's columns are exactly {COLUMNS}"
        return list(reader)


# --- the seed, read without dbt ----------------------------------------------------------------------------------


def test_every_exceptions_row_is_filled_with_a_severity_a_sentence_and_a_date():
    rows = _rows()
    for row in rows:
        assert all(row[column].strip() for column in COLUMNS), row
        assert row["severity"] in ("warn", "error"), f"{row['model']}: {row['severity']!r} is not a dbt severity"
        assert len(row["reason"].split()) >= 12, f"{row['model']}: a reason is a sentence, not {row['reason']!r}"
        datetime.date.fromisoformat(row["decided"])
    assert len({row["model"] for row in rows}) == len(rows), "one row per model"


def test_the_evaluator_counts_only_unique_and_not_null_as_a_key():
    """dbt_project_evaluator's own reading of decision 197: its default also counts
    dbt_utils.unique_combination_of_columns, which the maintainer's rule does not."""
    project = yaml.safe_load((DBT_DIR / "dbt_project.yml").read_text(encoding="utf-8"))
    assert project["vars"]["dbt_project_evaluator"]["primary_key_test_macros"] == [["dbt.test_unique", "dbt.test_not_null"]]


# --- the checker, on hand-made manifests -------------------------------------------------------------------------

_TEST_IDS = itertools.count()


def _model(name: str, *, version: int | None = None, enforced: bool = False, not_null_constrained=(), package=PROJECT):
    unique_id = f"model.{package}.{name}" + (f".v{version}" if version is not None else "")
    columns = {column: {"name": column, "constraints": [{"type": "not_null"}]} for column in not_null_constrained}
    node = {
        "resource_type": "model",
        "package_name": package,
        "name": name,
        "version": version,
        "contract": {"enforced": enforced},
        "columns": columns,
    }
    return unique_id, node


def _test(kind: str, model_id: str, column: str | None, **config) -> tuple[str, dict]:
    macro = KEY_TESTS.get(kind, f"macro.dbt_utils.test_{kind}")
    node = {
        "resource_type": "test",
        "test_metadata": {"name": kind, "namespace": None if kind in KEY_TESTS else "dbt_utils"},
        "depends_on": {"macros": [macro], "nodes": [model_id]},
        "attached_node": model_id,
        "column_name": column,
        "config": {"severity": "ERROR", "where": None, "error_if": "!= 0", "warn_if": "!= 0", "fail_calc": "count(*)", **config},
    }
    return f"test.{PROJECT}.{kind}_{column}.{next(_TEST_IDS)}", node


def _manifest(*pairs) -> dict:
    return {"nodes": dict(pairs)}


def test_a_model_keyed_only_by_a_combination_of_columns_has_no_key():
    model = _model("int_elevation__final")
    combination = _test("unique_combination_of_columns", model[0], None)
    not_null = _test("not_null", model[0], "line_id")
    assert check(_manifest(model, combination, not_null), [])["unkeyed"] == ["int_elevation__final"]


def test_a_surrogate_key_column_with_unique_and_not_null_is_a_key():
    model = _model("int_elevation__final")
    tests = [_test("unique", model[0], "line_sample_key"), _test("not_null", model[0], "line_sample_key")]
    verdict = check(_manifest(model, *tests), [])
    assert verdict["unkeyed"] == [] and verdict["keyed"] == ["int_elevation__final"]


def test_a_unique_test_filtered_by_where_makes_no_key():
    model = _model("int_places__resolved")
    tests = [_test("unique", model[0], "place_id", where="broken_text is null"), _test("not_null", model[0], "place_id")]
    assert check(_manifest(model, *tests), [])["unkeyed"] == ["int_places__resolved"]


def test_a_threshold_that_lets_failing_rows_through_makes_no_key():
    model = _model("pub_example")
    tests = [_test("unique", model[0], "id", error_if="> 5"), _test("not_null", model[0], "id")]
    assert check(_manifest(model, *tests), [])["unkeyed"] == ["pub_example"]


def test_decision_204s_declared_zero_tolerance_is_still_a_key():
    """dbt_project.yml writes every test's thresholds as `>0`, which fails on the first row as dbt's `!= 0` does."""
    model = _model("pub_example")
    tests = [
        _test("unique", model[0], "id", error_if=">0", warn_if=">0"),
        _test("not_null", model[0], "id", error_if="> 0", warn_if=">0"),
    ]
    assert check(_manifest(model, *tests), [])["keyed"] == ["pub_example"]


def test_a_key_at_warn_fails_unless_a_row_records_it_at_warn():
    model = _model("int_closures__area_trail_cuts")
    tests = [
        _test("unique", model[0], "notice_id", severity="WARN"),
        _test("not_null", model[0], "notice_id", severity="WARN"),
    ]
    manifest = _manifest(model, *tests)
    assert check(manifest, [])["unkeyed"] == ["int_closures__area_trail_cuts"]

    row = {"model": "int_closures__area_trail_cuts", "column_name": "notice_id", "severity": "warn"}
    assert check(manifest, [row]) == {"unkeyed": [], "unknown": [], "keyed_now": [], "not_as_recorded": [], "keyed": []}
    assert check(manifest, [{**row, "column_name": "area_geojson"}])["not_as_recorded"] == [
        "int_closures__area_trail_cuts.area_geojson at warn"
    ]


def test_a_row_naming_no_model_or_a_model_that_now_has_a_key_excepts_nothing():
    model = _model("int_closures__trail_closure_areas")
    tests = [_test("unique", model[0], "notice_id"), _test("not_null", model[0], "notice_id")]
    rows = [
        {"model": "int_closures__trail_closure_areas", "column_name": "notice_id", "severity": "warn"},
        {"model": "int_closures__renamed_away", "column_name": "notice_id", "severity": "warn"},
    ]
    verdict = check(_manifest(model, *tests), rows)
    assert verdict["keyed_now"] == ["int_closures__trail_closure_areas"]
    assert verdict["unknown"] == ["int_closures__renamed_away"]


def test_not_null_from_an_enforced_contract_counts_and_from_an_unenforced_one_does_not():
    enforced = _model("elevation", version=1, enforced=True, not_null_constrained=["line_sample_key"])
    loose = _model("elevation_copy", enforced=False, not_null_constrained=["line_sample_key"])
    tests = [_test("unique", enforced[0], "line_sample_key"), _test("unique", loose[0], "line_sample_key")]
    verdict = check(_manifest(enforced, loose, *tests), [])
    assert verdict["keyed"] == ["elevation.v1"] and verdict["unkeyed"] == ["elevation_copy"]


def test_unique_on_one_column_and_not_null_on_another_is_no_key():
    model = _model("int_trail_lines__network_name_aliases")
    tests = [_test("unique", model[0], "published_spelling"), _test("not_null", model[0], "source_key")]
    assert check(_manifest(model, *tests), [])["unkeyed"] == ["int_trail_lines__network_name_aliases"]


def test_each_version_of_a_versioned_model_needs_its_own_key():
    v1 = _model("elevation", version=1)
    v2 = _model("elevation", version=2)
    tests = [_test("unique", v1[0], "line_sample_key"), _test("not_null", v1[0], "line_sample_key")]
    assert check(_manifest(v1, v2, *tests), [])["unkeyed"] == ["elevation.v2"]


def test_a_model_of_another_package_is_not_held_to_the_rule():
    model = _model("int_model_test_summary", package="dbt_project_evaluator")
    assert check(_manifest(model), []) == {"unkeyed": [], "unknown": [], "keyed_now": [], "not_as_recorded": [], "keyed": []}


# --- the project, parsed ------------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def manifest(tmp_path_factory) -> dict:
    """The project as dbt parses it now, into a directory of its own."""
    root = tmp_path_factory.mktemp("keyed_manifest")
    env = {
        **{name: value for name, value in os.environ.items() if name != "OURHIKE_DATA_ENV"},
        "DBT_ENGINE_SEND_ANONYMOUS_USAGE_STATS": "false",
        "OURHIKE_WAREHOUSE": str(root / "warehouse.duckdb"),
        "OURHIKE_PROCESSED_DIR": str(root / "processed"),
    }
    completed = subprocess.run(
        [DBT, "parse", "--profiles-dir", ".", "--target-path", str(root / "target"), "--log-path", str(root / "logs")],
        cwd=DBT_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    path = root / "target" / "manifest.json"
    assert completed.returncode == 0 and path.exists(), completed.stdout[-3000:] + completed.stderr[-2000:]
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.skipif(not DBT, reason="OURHIKE_DBT names no dbt (the dbt job and scripts/test.sh set it)")
def test_every_model_has_one_column_unique_and_not_null_or_a_recorded_exception(manifest):
    verdict = check(manifest, _rows())
    assert len(verdict["keyed"]) > 1000, "the rule read the whole project"
    assert not verdict["unkeyed"], (
        "models with no column carrying an unfiltered unique and not_null at error (decision 197): give each a key, "
        f"a dbt_utils.generate_surrogate_key column where it takes several columns: {verdict['unkeyed']}"
    )


@pytest.mark.skipif(not DBT, reason="OURHIKE_DBT names no dbt (the dbt job and scripts/test.sh set it)")
def test_every_exceptions_row_names_a_model_that_still_needs_it_as_recorded(manifest):
    verdict = check(manifest, _rows())
    assert not verdict["unknown"], f"rows naming no model of the project: {verdict['unknown']}"
    assert not verdict["keyed_now"], f"rows whose model now meets the rule, so they except nothing: {verdict['keyed_now']}"
    assert not verdict["not_as_recorded"], (
        f"rows whose column does not carry both tests as recorded: {verdict['not_as_recorded']}"
    )
