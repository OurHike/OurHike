"""One failing test, built as CI builds it and as production does: both thresholds on a real dbt build.

The maintainer, 2026-10-15: "Every test should have both the warning and error thresholds. If an error like
freshness would prevent building the model, then that should be enabled/disabled based on the environment. prod
environment should ignore those, dev & ci should not." His poll answer the same day, "Build as proposed", made
OURHIKE_DATA_ENV the switch dbt_project.yml reads for every test's severity, and build_marts.py the one that reports
a warning past its own `error_if` as an error (its docstring, "EVERY TEST HAS TWO THRESHOLDS").

The podcasts mart, the smallest whose rows come from a file the extract lands (tests/test_dbt_row_dates_builds.py
builds it the same way), is built twice, each in a fresh warehouse, from raw rows in which two episodes share one
row key, `_row` 1, with different titles. duplicates_are_exact on the raw table, at the project's zero tolerance
(`warn_if` and `error_if` both `>0`), fails on that key:

(a) as CI and dev build it, OURHIKE_DATA_ENV unset: the test is an error, dbt skips every model below the raw
    table, the mart among them, and the build exits 1;
(b) as production builds it, OURHIKE_DATA_ENV=production: the same test warns with the same count, everything
    below it builds, the mart holds one row a key, and the build exits 0; build_marts.relabelled_errors(), which
    build_marts.py runs on every dbt build's results, reports that test as an error, and the dedupe count below it,
    one copy of four rows, as the warning it is (macros/test_levels.sql: an error at half the raw table).

Measured 2026-10-15 in the shared 4-core sandbox: 3 passed in about 80 s, two seeds and two builds. It needs dbt
2.0.6 with the packages under pipeline/dbt/dbt_packages/, and runs only where OURHIKE_DBT names that dbt.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import duckdb
import pytest
from test_dbt_row_dates_builds import POI_LEDGER_COLUMNS, _episode

import build_marts

PIPELINE_DIR = Path(__file__).resolve().parent.parent
DBT_DIR = PIPELINE_DIR / "dbt"
DBT = os.environ.get("OURHIKE_DBT")
pytestmark = pytest.mark.skipif(not DBT, reason="OURHIKE_DBT names no dbt (the dbt job and scripts/test.sh set it)")

#: (`_row`, episode): the second and the fourth share row 1, which the base model's key is built on.
ROWS = [
    (0, _episode("A", "Alpha", 10.0)),
    (1, _episode("B", "Bravo", 20.0)),
    (2, _episode("C", "Charlie", 30.0)),
    (1, _episode("B", "Bravo, the same row told twice", 20.0)),
]
DUPLICATES = "source_duplicates_are_exact_podcasts_raw_podcasts__podcast_episodes"
MART = "model.ourhike.podcasts.v1"


def _raw(warehouse: Path) -> None:
    """The three raw tables the podcasts mart reads, as the extract lands them, with ROWS as the episodes."""
    registry = (PIPELINE_DIR / "sources.json").read_text(encoding="utf-8")
    with duckdb.connect(str(warehouse)) as con:
        con.execute("create schema raw")
        con.execute(
            "create table raw.raw_podcasts__podcast_episodes (row_json varchar, _row bigint, _file varchar, "
            "_path varchar, _loaded_at timestamptz, _dlt_load_id varchar, _dlt_id varchar)"
        )
        con.executemany(
            "insert into raw.raw_podcasts__podcast_episodes values (?, ?, 'podcast_episodes.json', "
            "'reference/podcast_episodes.json', now(), 'load-1', ?)",
            [(json.dumps(episode), row, f"load-1-{index}") for index, (row, episode) in enumerate(ROWS)],
        )
        con.execute(
            "create table raw.raw_registry__sources (row_json varchar, _row bigint, _path varchar, "
            "_loaded_at timestamptz, _dlt_load_id varchar, _dlt_id varchar)"
        )
        con.execute("insert into raw.raw_registry__sources values (?, 0, 'sources.json', now(), 'load-1', 'load-1')", [registry])
        con.execute(f"create table raw.raw_ourhike__poi_identity ({POI_LEDGER_COLUMNS})")


def _build(root: Path, environment: str | None) -> dict:
    """`dbt seed`, then the podcasts mart and everything above it, in a fresh warehouse, in `environment`."""
    warehouse = root / "warehouse.duckdb"
    _raw(warehouse)
    env = {name: value for name, value in os.environ.items() if name != "OURHIKE_DATA_ENV"}
    env.update(
        {
            "OURHIKE_WAREHOUSE": str(warehouse),
            "OURHIKE_PROCESSED_DIR": str(root / "processed"),
            "DBT_ENGINE_SEND_ANONYMOUS_USAGE_STATS": "false",
            "TZ": "UTC",
            # No snapshot: the row history is tests/test_dbt_row_dates_builds.py's.
            "OURHIKE_ROW_HISTORY": "off",
        }
    )
    if environment is not None:
        env["OURHIKE_DATA_ENV"] = environment
    paths = ("--profiles-dir", ".", "--target-path", str(root / "target"), "--log-path", str(root / "logs"))
    seeded = subprocess.run([DBT, "seed", *paths], cwd=DBT_DIR, env=env, capture_output=True, text=True, check=False)
    assert seeded.returncode == 0, seeded.stdout[-4000:] + seeded.stderr[-2000:]
    built = subprocess.run(
        [DBT, "build", "-s", "+podcasts", "--exclude", "resource_type:snapshot", "--indirect-selection", "cautious", *paths],
        cwd=DBT_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    results = json.loads((root / "target" / "run_results.json").read_text(encoding="utf-8"))["results"]
    manifest = json.loads((root / "target" / "manifest.json").read_text(encoding="utf-8"))
    with duckdb.connect(str(warehouse), read_only=True) as con:
        tables = {name for (name,) in con.execute("select table_name from information_schema.tables").fetchall()}
        titles = (
            sorted(title for (title,) in con.execute("select title from marts.podcasts_v1").fetchall())
            if "podcasts_v1" in tables
            else None
        )
    return {"built": built, "results": results, "manifest": manifest, "titles": titles}


@pytest.fixture(scope="module")
def builds(tmp_path_factory) -> dict:
    return {
        "ci": _build(tmp_path_factory.mktemp("thresholds_ci"), None),
        "production": _build(tmp_path_factory.mktemp("thresholds_production"), "production"),
    }


def _result(build: dict, fragment: str) -> dict:
    (result,) = [result for result in build["results"] if fragment in result["unique_id"]]
    return result


def test_ci_stops_the_mart_below_the_failing_test(builds):
    ci = builds["ci"]
    duplicates = _result(ci, DUPLICATES)
    assert ci["built"].returncode == 1, ci["built"].stdout[-4000:]
    assert (duplicates["status"], duplicates["failures"]) == ("fail", 1)
    assert _result(ci, MART)["status"] == "skipped"
    assert ci["titles"] is None, "the mart was never written"


def test_production_builds_the_mart_and_reports_the_same_failure_as_an_error(builds):
    production = builds["production"]
    duplicates = _result(production, DUPLICATES)
    assert production["built"].returncode == 0, production["built"].stdout[-4000:]
    assert (duplicates["status"], duplicates["failures"]) == ("warn", 1), "the same count, as a warning"
    assert _result(production, MART)["status"] == "success"
    assert production["titles"] == ["Alpha", "Bravo", "Charlie"] or production["titles"] == [
        "Alpha",
        "Bravo, the same row told twice",
        "Charlie",
    ], "one row a key: the dedupe kept one of the two"
    # As build_marts.py reads a build with the row history off: the mart's two dates are null by design there.
    errors = build_marts.relabelled_errors(production["results"], production["manifest"], history_off=True)
    assert [test for test in errors if DUPLICATES in test] and len(errors) == 1, errors
    assert next(iter(errors.values())) == "1 against error_if >0"


def test_the_dedupe_count_below_it_warns_in_both_and_is_no_error(builds):
    """One copy of four raw rows is a warning: macros/test_levels.sql's dedupe_copies_level() scores 1, and an error
    takes copies of half the raw table. CI never reaches it, as its model was skipped."""
    production = _result(builds["production"], "equal_rowcount_to_raw_base_podcasts__podcast_episodes")
    assert (production["status"], production["failures"]) == ("warn", 1)
    assert _result(builds["ci"], "equal_rowcount_to_raw_base_podcasts__podcast_episodes")["status"] == "skipped"
