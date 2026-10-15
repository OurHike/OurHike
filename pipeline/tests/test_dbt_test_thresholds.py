"""Every dbt test has both a warning and an error threshold, and the data environment decides who stops on an error.

Decision 204, the maintainer, 2026-10-15: "Every test should have both the warning and error thresholds. If an
error like freshness would prevent building the model, then that should be enabled/disabled based on the
environment. prod environment should ignore those, dev & ci should not." His poll answer the same day, "Build as
proposed", took the shape dbt/dbt_project.yml's comment above `data_tests:` describes:

- every test declares `warn_if` and `error_if`, in the `>N` form, which dbt's own default (`!= 0`) never takes, so
  a manifest tells a declared threshold from a missing one. The default for this project's tests and the
  evaluator's is `>0` and `>0`, dbt_project.yml's; a kind with a tolerance declares its own pair, in its YAML (the
  challenges refusals' `>50`), in its generic test's config() (tests/generic/rows_named.sql,
  equal_rowcount_to_raw.sql), in a singular test's config(), or in make_dbt_staging.py's elementary_check_config()
  for Elementary's checks;
- `severity` is the switch: dbt_project.yml's expression on OURHIKE_DATA_ENV, warn in production and UA and error
  everywhere else. A test may set its own only to `error` (a pub_ writer's test, through the publish folder; a test
  of the six marts a hiker's safety reads, through the `marts:` gates, or in a singular test's own config(); an
  Elementary check), to the switch itself (a hold of decision 81's inside a gated folder), to the row dates'
  expression, which also warns with the history off, or to `warn` with `meta.stays_at_warn` saying whose decision
  that is (decision 197's four closures key tests).

Two halves. The first reads the YAML and SQL as they stand, generated files included (tests/conftest.py refuses to
start without them), with no dbt, so it runs in the pytest job too. The second parses the project with dbt 2.0.6,
Elementary's checks on, and reads every test node of the manifest, this project's and the evaluator's, so a
default nobody wrote down still counts; it runs only where OURHIKE_DBT names that dbt (pipeline-tests.yml's dbt job
and scripts/test.sh's dbt suite).

What has no threshold in dbt at all, a unit test, a contract or a constraint, and a test that cannot run, fails
or passes; decision 204's answer for those is build_marts.py's, which in production and UA holds what such a
failure reaches and builds the rest (its docstring, "EVERY TEST HAS TWO THRESHOLDS").
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

import pytest
import yaml

import make_dbt_staging

DBT_DIR = Path(__file__).resolve().parent.parent / "dbt"
DBT = os.environ.get("OURHIKE_DBT")
#: A threshold as decision 204 writes it.
DECLARED = re.compile(r">\s*[0-9]+")
#: The six marts whose tests dbt_project.yml gates at error in every environment, CLAUDE.md's four harms.
SAFETY_MARTS = ("closures", "warnings", "points_of_interest", "elevation", "trail_lines", "trail_network")
#: dbt_project.yml's switch, and the row dates' (tests/test_dbt_row_dates.py's SEVERITY).
SWITCH = "{{ 'warn' if env_var('OURHIKE_DATA_ENV', 'dev') in ['production', 'ua'] else 'error' }}"
ROW_DATES = (
    "{{ 'warn' if env_var('OURHIKE_ROW_HISTORY', 'on') == 'off' "
    "or env_var('OURHIKE_DATA_ENV', 'dev') in ['production', 'ua'] else 'error' }}"
)
STAYS_AT_WARN = "stays_at_warn"
CONFIG_CALL = re.compile(r"\{\{\s*config\((.*?)\)\s*\}\}", re.S)


def _project() -> dict:
    return yaml.safe_load((DBT_DIR / "dbt_project.yml").read_text(encoding="utf-8"))


def _tests(items) -> list[tuple[str, dict]]:
    """A `data_tests` list as (test name, its body): `unique` is ("unique", {})."""
    found = []
    for item in items or []:
        if isinstance(item, str):
            found.append((item, {}))
        else:
            ((name, body),) = item.items()
            found.append((name, body or {}))
    return found


def _yaml_tests() -> list[tuple[str, str, dict]]:
    """(where, test name, body) for every generic test a YAML file under models/, seeds/ or snapshots/ declares, on a
    model, a source table, a seed or a snapshot, or on one of their columns, generated files included."""
    found = []
    for folder in ("models", "seeds", "snapshots"):
        for path in sorted((DBT_DIR / folder).rglob("*.yml")):
            document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            where = str(path.relative_to(DBT_DIR))
            nodes = [*(document.get("models") or []), *(document.get("seeds") or []), *(document.get("snapshots") or [])]
            for source in document.get("sources") or []:
                nodes += source.get("tables") or []
            for node in nodes:
                for version in [node, *(node.get("versions") or [])]:
                    for name, body in _tests(version.get("data_tests") or version.get("tests")):
                        found.append((f"{where}: {node.get('name')}", name, body))
                    for column in version.get("columns") or []:
                        for name, body in _tests(column.get("data_tests") or column.get("tests")):
                            found.append((f"{where}: {node.get('name')}.{column.get('name')}", name, body))
    return found


YAML_TESTS = _yaml_tests()


def _sql_configs(folder: str) -> list[tuple[str, str]]:
    """(file, the text of its config() call) for every SQL test under tests/`folder` that calls config()."""
    found = []
    for path in sorted((DBT_DIR / "tests" / folder).rglob("*.sql")):
        for match in CONFIG_CALL.finditer(path.read_text(encoding="utf-8")):
            found.append((str(path.relative_to(DBT_DIR)), match.group(1)))
    return found


def _keyword(config: str, key: str) -> str | None:
    """`key`'s value in a config() call's text, quoted either way, or None."""
    match = re.search(rf"\b{key}\s*=\s*(['\"])(.*?)\1", config, re.S)
    return match.group(2) if match else None


# --- what the project declares, read without dbt -------------------------------------------------------------------


def test_the_project_gives_its_tests_and_the_evaluators_both_thresholds_and_the_switch():
    data_tests = _project()["data_tests"]
    ours, evaluator = data_tests["ourhike"], data_tests["dbt_project_evaluator"]
    for package in (ours, evaluator):
        assert DECLARED.fullmatch(package["+warn_if"]) and DECLARED.fullmatch(package["+error_if"]), package
    assert ours["+severity"] == SWITCH
    assert ours["publish"] == {"+severity": "error"}, "a pub_ writer's test removes its file in every environment"
    assert ours["marts"] == {mart: {"+severity": "error"} for mart in SAFETY_MARTS}, "the safety marts' gates"


def test_every_threshold_a_yaml_test_writes_is_in_the_declared_form():
    loose = [
        f"{where}: {name} {key}={value!r}"
        for where, name, body in YAML_TESTS
        for key, value in (body.get("config") or {}).items()
        if key in ("warn_if", "error_if") and not DECLARED.fullmatch(str(value))
    ]
    assert loose == []


def test_every_severity_a_yaml_test_writes_is_error_the_switch_the_row_dates_or_a_recorded_warn():
    """A test's own `severity: warn` would never stop dev or CI, which is the one thing decision 204 asks of them."""
    stray = []
    for where, name, body in YAML_TESTS:
        config = body.get("config") or {}
        if "severity" not in config:
            continue
        severity = str(config["severity"])
        if severity in ("error", SWITCH, ROW_DATES):
            continue
        if severity == "warn" and (config.get("meta") or {}).get(STAYS_AT_WARN):
            continue
        stray.append(f"{where}: {name} severity={severity!r}")
    assert stray == []


def test_only_decision_197s_four_closures_key_tests_stay_at_warn():
    stays = sorted(
        f"{where}: {name}" for where, name, body in YAML_TESTS if str((body.get("config") or {}).get("severity")) == "warn"
    )
    assert len(stays) == 4 and all("_closures__intermediate.yml" in where for where in stays), stays
    assert {name for where, name, body in YAML_TESTS if f"{where}: {name}" in stays} == {"not_null", "unique"}


def test_every_check_carries_its_kinds_two_thresholds():
    """tests/test_elementary_checks.py holds each check to elementary_check_config(); this, that every kind it gives
    is one of the two forms: a level scored past `>1`, or the project's zero tolerance."""
    for kind in ("volume_anomalies", "column_anomalies", "dimension_anomalies", "all_columns_anomalies", "schema_changes"):
        config = make_dbt_staging.elementary_check_config(kind)
        assert (config["warn_if"], config["error_if"], config["severity"]) == (">0", ">1", "error"), kind
        assert config["fail_calc"].startswith("{{ var('elementary_"), kind
    config = make_dbt_staging.elementary_check_config("exposure_schema_validity")
    assert config["severity"] == "error" and "warn_if" not in config and "fail_calc" not in config


@pytest.mark.parametrize("folder", ["generic", "singular"])
def test_every_sql_test_that_sets_a_threshold_or_a_level_sets_both_thresholds_in_the_declared_form(folder):
    """A `fail_calc` that scores a level needs its own pair, or the project's `>0` would make its first level an
    error. A SQL test may set its own severity only to `error`, a gate that holds what it reaches in every
    environment (assert_pois_land_in_the_region_this_build_covers.sql), never `warn`, which dev and CI would not
    stop on."""
    problems = []
    for where, config in _sql_configs(folder):
        warn_if, error_if = _keyword(config, "warn_if"), _keyword(config, "error_if")
        if "fail_calc" in config and (warn_if is None or error_if is None):
            problems.append(f"{where}: a fail_calc with warn_if={warn_if!r} error_if={error_if!r}")
        for key, value in (("warn_if", warn_if), ("error_if", error_if)):
            if value is not None and not DECLARED.fullmatch(value):
                problems.append(f"{where}: {key}={value!r}")
        severity = _keyword(config, "severity")
        if severity is not None and severity != "error":
            problems.append(f"{where}: severity={severity!r}")
        elif severity is None and re.search(r"\bseverity\s*=", config):
            problems.append(f"{where}: a severity this test cannot read")
    assert problems == []


def test_no_generic_test_gives_its_model_an_alias():
    """Given a `where`, dbt hands a generic test `{{ model }}` as an aliased subquery, `(select ... where ...)
    dbt_subquery`, which takes no second alias. rows_named.sql once wrote `from {{ model }} as checked`, and every test
    of it with a `where` could not run: "Parser Error: syntax error at or near "as"" on
    closures_other_miles_are_inside_the_trail_and_in_order, in the CI-mode fixture build of thresholds204b
    (2026-10-15), which stopped stage A."""
    aliased = [
        str(path.relative_to(DBT_DIR))
        for path in sorted((DBT_DIR / "tests" / "generic").glob("*.sql"))
        if re.search(r"\{\{\s*model\s*\}\}\s+as\b", path.read_text(encoding="utf-8"), re.I)
    ]
    assert aliased == []


def test_the_level_tests_warn_at_one_and_are_errors_at_two():
    """rows_named, equal_rowcount_to_raw and the review aids score 0, 1 or 2 (macros/test_levels.sql)."""
    levels = {
        where: (_keyword(config, "warn_if"), _keyword(config, "error_if"))
        for folder in ("generic", "singular")
        for where, config in _sql_configs(folder)
        if "fail_calc" in config
    }
    assert {"tests/generic/rows_named.sql", "tests/generic/equal_rowcount_to_raw.sql"} <= set(levels)
    assert set(levels.values()) == {(">0", ">1")}, levels


# --- every test node, as dbt parses the project ------------------------------------------------------------------


def _parse(root: Path, environment: str | None) -> dict:
    """The project as dbt parses it with Elementary's checks on, in `environment` (None: OURHIKE_DATA_ENV unset)."""
    env = {name: value for name, value in os.environ.items() if name != "OURHIKE_DATA_ENV"}
    env.update(
        {
            "DBT_ENGINE_SEND_ANONYMOUS_USAGE_STATS": "false",
            "OURHIKE_WAREHOUSE": str(root / "warehouse.duckdb"),
            "OURHIKE_PROCESSED_DIR": str(root / "processed"),
            "OURHIKE_ELEMENTARY": "true",
            "OURHIKE_ELEMENTARY_CHECKS": "true",
        }
    )
    if environment is not None:
        env["OURHIKE_DATA_ENV"] = environment
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


@pytest.fixture(scope="module")
def manifests(tmp_path_factory) -> dict:
    return {
        "dev": _parse(tmp_path_factory.mktemp("thresholds_dev"), None),
        "production": _parse(tmp_path_factory.mktemp("thresholds_production"), "production"),
    }


def _test_nodes(manifest: dict) -> dict[str, dict]:
    return {uid: node for uid, node in (manifest.get("nodes") or {}).items() if node.get("resource_type") == "test"}


def _gated(node: dict) -> bool:
    """A test the `marts:` gates reach: one defined under a safety mart's folder."""
    path = str(node.get("original_file_path") or "")
    return any(path.startswith(f"models/marts/{mart}/") for mart in SAFETY_MARTS)


def _writer_test(node: dict) -> bool:
    return any(
        parent.split(".")[2].startswith("pub_")
        for parent in (node.get("depends_on") or {}).get("nodes") or []
        if parent.startswith("model.")
    )


@pytest.mark.skipif(not DBT, reason="OURHIKE_DBT names no dbt (the dbt job and scripts/test.sh set it)")
def test_every_test_dbt_parses_has_both_thresholds_in_the_declared_form(manifests):
    tests = _test_nodes(manifests["dev"])
    assert len(tests) > 5000, "the parse read the whole project, Elementary's checks included"
    missing = sorted(
        f"{uid}: warn_if={(node.get('config') or {}).get('warn_if')!r} error_if={(node.get('config') or {}).get('error_if')!r}"
        for uid, node in tests.items()
        if not all(DECLARED.fullmatch(str((node.get("config") or {}).get(key))) for key in ("warn_if", "error_if"))
    )
    assert missing == []
    packages = {node.get("package_name") for node in tests.values()}
    assert {"ourhike", "dbt_project_evaluator"} <= packages


@pytest.mark.skipif(not DBT, reason="OURHIKE_DBT names no dbt (the dbt job and scripts/test.sh set it)")
def test_dev_and_ci_stop_on_every_error_and_production_warns_on_all_but_its_gates(manifests):
    """Unset (dev and CI), every test is an error but decision 197's four. In production every test the switch
    decides warns, and what stays an error is a pub_ writer's test, a test of a safety mart's folder, a test whose own
    config says `error`, and Elementary's checks, which never change a production run's exit (build_marts.py)."""
    dev, production = _test_nodes(manifests["dev"]), _test_nodes(manifests["production"])
    assert set(dev) == set(production)
    warns_in_dev = sorted(uid for uid, node in dev.items() if str(node["config"].get("severity")).lower() != "error")
    assert len(warns_in_dev) == 4 and all(STAYS_AT_WARN in (dev[uid]["config"].get("meta") or {}) for uid in warns_in_dev)
    errors_in_production = {uid for uid, node in production.items() if str(node["config"].get("severity")).lower() == "error"}
    for uid in errors_in_production:
        node = production[uid]
        written = str((node.get("unrendered_config") or {}).get("severity"))
        tags = set(node.get("tags") or []) | set(node["config"].get("tags") or [])
        assert (
            node.get("package_name") == "dbt_project_evaluator"
            or _writer_test(node)
            or _gated(node)
            or written == "error"
            or make_dbt_staging.ELEMENTARY_CHECK in tags
        ), uid
    # An Elementary check on a versioned mart (elevation_v2, say) shows the project's switch in its unrendered config
    # and its own `error` in its config (measured on dbt 2.0.6, 2026-10-15), so the checks are read by their tag.
    switched = [
        uid
        for uid, node in production.items()
        if str((node.get("unrendered_config") or {}).get("severity")) == SWITCH
        and make_dbt_staging.ELEMENTARY_CHECK not in set(node.get("tags") or []) | set(node["config"].get("tags") or [])
        and (not _gated(node) or ((node["config"].get("meta") or {}).get("holds_a_source")))
    ]
    assert len(switched) > 5000 and all(str(production[uid]["config"]["severity"]).lower() == "warn" for uid in switched)
