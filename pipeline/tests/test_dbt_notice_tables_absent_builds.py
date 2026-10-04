"""A real dbt build of the conditions files on a warehouse that holds no club notice table (decision 61).

The hourly warehouse adds the newest served copy of the 4-hourly notices
store, so a notices table can be absent from it: one still waiting its turn
(a table with no hints is never created empty), one a served copy left out,
or every one when no copy could be read (pipeline/ELT.md, Phase F, "What this
does not settle"). This builds the last and widest case on the fixtures:
every generated club notice source's raw table dropped and its run-log rows
deleted, as a warehouse with only the hourly store's tables has them. Then:

(a) the build succeeds, its tests included, so one absent table never stops
    ATC's, NYNJTC's or OurHike's files;
(b) every generated notice source is held in int_closures__gate, never passed
    as having no notices: one the registry ships with the absent table as its
    reason (int_closures__notice_tables), one it holds with
    int_sources__publication's;
(c) ATC's, NYNJTC's, NYS Parks', OurHike's and NWS's gate rows pass, and the
    three conditions writers write their files;
(d) no club notice reaches the closures or warnings mart.

The narrower cases run in every fixture build: four notice tables have no
fixture rows and are never created, and
tests/singular/assert_a_notice_source_whose_raw_table_is_absent_is_held.sql
fails the build unless each is held with a reason.

It needs dbt 2.0.6 with the packages under pipeline/dbt/dbt_packages/, and
runs only when OURHIKE_DBT names that dbt, as tests/test_dbt_row_dates_builds.py
does. Measured 2026-10-04 on 3df39f10's fixtures: 272 s on a four-core
sandbox, 231 s of it the fixture load, the seeds and the build.
"""

from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
from pathlib import Path

import duckdb
import pytest

PIPELINE_DIR = Path(__file__).resolve().parent.parent
DBT_DIR = PIPELINE_DIR / "dbt"
DBT = os.environ.get("OURHIKE_DBT")
pytestmark = pytest.mark.skipif(not DBT, reason="OURHIKE_DBT names no dbt (the dbt job and scripts/test.sh set it)")

#: The sources int_closures__gate answers that read no club notice table: ATC's, NYNJTC's and NYS Parks' hand
#: staged notices, and the four typed rows.
HOURLY_SOURCES = {
    "atc_trail_updates",
    "nynjtc_trail_alerts",
    "oprhp_trail_closures",
    "ourhike_closures",
    "ourhike_reports",
    "nws_alerts",
    "reference/work_projects.json",
}
WRITERS = ("pub_conditions_atc_updates", "pub_conditions_nynjtc_alerts", "pub_conditions_closures")


def _generated_tables() -> set[str]:
    with (DBT_DIR / "seeds" / "notice_readers.csv").open(newline="") as handle:
        return {row["raw_table"] for row in csv.DictReader(handle) if row["staged_by"] != "hand"}


def _run(arguments: list[str], cwd: Path, env: dict) -> None:
    completed = subprocess.run(arguments, cwd=cwd, env=env, capture_output=True, text=True, check=False)
    assert completed.returncode == 0, completed.stdout[-4000:] + completed.stderr[-2000:]


def _query(warehouse: Path, sql: str) -> list[tuple]:
    with duckdb.connect(str(warehouse), read_only=True) as con:
        return con.execute(sql).fetchall()


@pytest.fixture(scope="module")
def build(tmp_path_factory) -> dict:
    root = tmp_path_factory.mktemp("notices_absent")
    raw, warehouse, processed = root / "raw", root / "warehouse.duckdb", root / "processed"
    processed.mkdir()  # the writers' directory, which build_marts.py makes in a real build
    env = {**os.environ, "RUNTIME__DLTHUB_TELEMETRY": "false", "TZ": "UTC"}
    _run([sys.executable, "make_dbt_fixtures.py", "--raw-dir", str(raw)], PIPELINE_DIR, env)
    _run(
        [
            sys.executable,
            "-m",
            "extract._fixtures",
            "--raw-dir",
            str(raw),
            "--warehouse",
            str(warehouse),
            "--store",
            str(root / "store"),
        ],
        PIPELINE_DIR,
        env,
    )

    # The no-copy case: no club notice table, and no run of one in the log.
    generated = _generated_tables()
    with duckdb.connect(str(warehouse)) as con:
        present = {
            name
            for (name,) in con.execute("select table_name from information_schema.tables where table_schema = 'raw'").fetchall()
        }
        dropped = sorted(generated & present)
        for table in dropped:
            con.execute(f'drop table raw."{table}"')
        con.execute("delete from raw._extract_runs where list_contains(?, table_name)", [sorted(generated)])

    dbt_env = {
        **env,
        "OURHIKE_WAREHOUSE": str(warehouse),
        "OURHIKE_PROCESSED_DIR": str(processed),
        "DBT_ENGINE_SEND_ANONYMOUS_USAGE_STATS": "false",
        # A conditions leg whose restore failed (decision 58): the marts build from their finals, no snapshot.
        "OURHIKE_ROW_HISTORY": "off",
    }
    paths = ["--profiles-dir", ".", "--target-path", str(root / "target"), "--log-path", str(root / "logs")]
    _run([DBT, "seed", *paths], DBT_DIR, dbt_env)
    selection = ["+closures", "+warnings", *(f"+{writer}" for writer in WRITERS)]
    _run(
        [DBT, "build", "-s", *selection, "--exclude", "resource_type:snapshot", "--indirect-selection", "cautious", *paths],
        DBT_DIR,
        dbt_env,
    )
    return {
        "dropped": dropped,
        "generated": {
            row[0] for row in _query(warehouse, "select source_key from seeds.notice_readers where staged_by != 'hand'")
        },
        "gate": {
            key: (passed, why)
            for key, passed, why in _query(
                warehouse, "select source_key, passed, held_because from intermediate.int_closures__gate"
            )
        },
        "club_rows": _query(
            warehouse,
            "select count(*) from marts.closures_v1 where starts_with(notice_kind, 'club_') "
            "union all select count(*) from marts.warnings_v1 where starts_with(notice_kind, 'club_')",
        ),
        "atc_rows": _query(warehouse, "select count(*) from marts.warnings_v1 where source_key = 'atc_trail_updates'")[0][0]
        + _query(warehouse, "select count(*) from marts.closures_v1 where source_key = 'atc_trail_updates'")[0][0],
        "files": {writer: processed / f"conditions_{writer.removeprefix('pub_conditions_')}.json" for writer in WRITERS},
    }


def test_the_build_dropped_the_club_notice_tables_and_still_succeeded(build):
    assert len(build["dropped"]) > 200, "the fixture warehouse held club notice tables to drop"


def test_every_generated_notice_source_is_held_and_says_why(build):
    absent = 0
    for key in build["generated"]:
        passed, why = build["gate"][key]
        assert passed is False, key
        # A source the registry still holds back gives that reason first; every other names its absent table.
        assert "is not in this warehouse" in why or "int_sources__publication holds" in why, (key, why)
        absent += "is not in this warehouse" in why
    assert absent > 100, "the sources the registry ships were held for their absent tables"


def test_the_hourly_sources_pass_and_their_files_are_written(build):
    for key in HOURLY_SOURCES:
        assert build["gate"][key][0] is True, (key, build["gate"][key])
    assert build["atc_rows"] > 0
    for writer, path in build["files"].items():
        assert path.exists(), f"{writer} wrote nothing"
        json.loads(path.read_text(encoding="utf-8"))


def test_no_club_notice_reaches_a_mart(build):
    assert build["club_rows"] == [(0,), (0,)]
