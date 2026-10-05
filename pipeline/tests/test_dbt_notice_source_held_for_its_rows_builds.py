"""A real dbt build of the conditions files in which one club's row leaks its wording and another's lands outside its box.

Decision 81 (the maintainer's poll, 2026-10-05: "Hold that source and
publish the rest"; review finding ARCH-1 of PR #1805 — dlt → dbt re-platform
as one go/no-go change). Until it, the wording-leak test and the closures and
warnings marts' region tests failed the build at severity error, so one
club's row stopped every hourly file: soak runs 525 to 527 and 530 published
nothing for anyone. This builds the fixtures' conditions files twice in one
warehouse, with the row history on, as two hourly runs would:

1. clean, so the history holds every club's rows;
2. after two invented edits to the raw rows. GRSM's trail access layer has
   a `notes` sentence with an ampersand in it, which the wording union reads
   as GRSM's wording, and a `trailname` (its notices' title) that carries the
   same sentence with the ampersand escaped, `&amp;`. The union reads the
   title as written, so the sentence is no fact of GRSM's; the published
   title is unescaped (int_closures__club_notices' python_html_unescape), so
   it carries the sentence whole: a leak. And CT DEEP's property access point
   has its longitude and latitude swapped, landing at lat -74.

Then, of the second build:

(a) it succeeds, its tests included, where before decision 81 it failed on
    those two tests and wrote no file;
(b) int_closures__gate holds GRSM for its wording and CT DEEP for its region,
    each with that reason, and every other source that passed the first build
    passes again;
(c) every conditions writer the build selects writes its file;
(d) conditions/notices.json carries both clubs' last good rows, marked
    `carried_since`, and none of the edited content: no leaked paragraph and
    no swapped point;
(e) the tests that hold a source warned, naming both, so the log has the
    rows and build_marts.py turns the run red after the publish.

It needs dbt 2.0.6 with the packages under pipeline/dbt/dbt_packages/, and
runs only when OURHIKE_DBT names that dbt, as
tests/test_dbt_notice_tables_absent_builds.py does.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import duckdb
import pytest

PIPELINE_DIR = Path(__file__).resolve().parent.parent
DBT_DIR = PIPELINE_DIR / "dbt"
DBT = os.environ.get("OURHIKE_DBT")
#: The Python that runs extract._fixtures, which imports dlt (tests/test_dbt_notice_tables_absent_builds.py says why).
EXTRACT_PYTHON = os.environ.get("OURHIKE_EXTRACT_PYTHON") or sys.executable
pytestmark = pytest.mark.skipif(not DBT, reason="OURHIKE_DBT names no dbt (the dbt job and scripts/test.sh set it)")

LEAKING = "grsm_trails_access"
OUTSIDE = "ct_deep_property_access_status"
#: The fixture value of GRSM's `notes`, which int_warnings__notice_wording_unioned reads as GRSM's own wording.
GRSM_NOTES = "Fixture closed beyond the first mile"
#: The sentence the edit puts in `notes`, and in `trailname` escaped as HTML, invented for this test.
LEAKED = "Fixture closed beyond the first mile & the ford"
WRITERS = (
    "pub_conditions_atc_updates",
    "pub_conditions_nynjtc_alerts",
    "pub_conditions_closures",
    "pub_conditions_reports",
    "pub_conditions_work_projects",
    "pub_conditions_notices",
)
HOLDING_TESTS = (
    "dbt_utils_expression_is_true_int_warnings__wording_leaks_false",
    "dbt_utils_expression_is_true_int_closures__rows_outside_region_false",
)


def _run(arguments: list[str], cwd: Path, env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(arguments, cwd=cwd, env=env, capture_output=True, text=True, check=False)


def _ok(arguments: list[str], cwd: Path, env: dict) -> None:
    completed = _run(arguments, cwd, env)
    assert completed.returncode == 0, completed.stdout[-4000:] + completed.stderr[-2000:]


def _query(warehouse: Path, sql: str) -> list[tuple] | None:
    """The rows, or None for a relation this build does not have (a build before decision 81 has neither model the
    gate reads), so a red build reads as the tests' own failures rather than as the fixture's."""
    with duckdb.connect(str(warehouse), read_only=True) as con:
        try:
            return con.execute(sql).fetchall()
        except duckdb.CatalogException:
            return None


def _gate(warehouse: Path) -> dict[str, tuple[bool, str | None]]:
    rows = _query(warehouse, "select source_key, passed, held_because from intermediate.int_closures__gate")
    return {key: (passed, why) for key, passed, why in rows}


@pytest.fixture(scope="module")
def builds(tmp_path_factory) -> dict:
    root = tmp_path_factory.mktemp("held_for_its_rows")
    raw, warehouse, processed = root / "raw", root / "warehouse.duckdb", root / "processed"
    processed.mkdir()  # the writers' directory, which build_marts.py makes in a real build
    env = {**os.environ, "RUNTIME__DLTHUB_TELEMETRY": "false", "TZ": "UTC"}
    env.pop("OURHIKE_ROW_HISTORY", None)  # the history on, as an hourly leg whose restore worked
    _ok([sys.executable, "make_dbt_fixtures.py", "--raw-dir", str(raw)], PIPELINE_DIR, env)
    _ok(
        [EXTRACT_PYTHON, "-m", "extract._fixtures", "--raw-dir", str(raw), "--warehouse", str(warehouse)]
        + ["--store", str(root / "store")],
        PIPELINE_DIR,
        env,
    )
    dbt_env = {
        **env,
        "OURHIKE_WAREHOUSE": str(warehouse),
        "OURHIKE_PROCESSED_DIR": str(processed),
        "DBT_ENGINE_SEND_ANONYMOUS_USAGE_STATS": "false",
    }
    target = root / "target"
    paths = ["--profiles-dir", ".", "--target-path", str(target), "--log-path", str(root / "logs")]
    # The wording-leak model by name as well: since decision 81 the gate reads it, and before, nothing a writer read
    # did, so a build of the writers alone would not have run its test.
    selection = ["+closures", "+warnings", "+int_warnings__wording_leaks", *(f"+{writer}" for writer in WRITERS)]
    build = [DBT, "build", "-s", *selection, "--indirect-selection", "cautious", *paths]
    _ok([DBT, "seed", *paths], DBT_DIR, dbt_env)
    _ok(build, DBT_DIR, dbt_env)
    first_gate = _gate(warehouse)

    with duckdb.connect(str(warehouse)) as con:
        con.execute(
            "update raw.raw_nps__grsm_trails_access set notes = ?, trailname = trailname || ': ' || ? where notes = ?",
            [LEAKED, LEAKED.replace("&", "&amp;"), GRSM_NOTES],
        )
        con.execute(
            "update raw.raw_ct_deep__ct_deep_property_access_status "
            """set geometry = '{"type":"Point","coordinates":[41.0,-74.0]}'"""
        )
    started = time.time()
    second = _run(build, DBT_DIR, dbt_env)
    results = {}
    if (target / "run_results.json").exists():
        results = {r["unique_id"]: r for r in json.loads((target / "run_results.json").read_text())["results"]}
    notices = processed / "conditions_notices.json"
    return {
        "second": second,
        "first_gate": first_gate,
        "gate": _gate(warehouse),
        "written": {
            writer: (processed / f"conditions_{writer.removeprefix('pub_conditions_')}.json").exists()
            and (processed / f"conditions_{writer.removeprefix('pub_conditions_')}.json").stat().st_mtime >= started
            for writer in WRITERS
        },
        "notices": json.loads(notices.read_text(encoding="utf-8"))["notices"] if notices.exists() else None,
        "notices_text": notices.read_text(encoding="utf-8") if notices.exists() else "",
        "results": results,
        "leaks": _query(warehouse, "select distinct source_key from intermediate.int_warnings__wording_leaks"),
        "outside": _query(warehouse, "select distinct source_key from intermediate.int_closures__rows_outside_region"),
    }


def test_a_club_row_that_leaks_its_wording_or_lands_outside_its_box_no_longer_fails_the_build(builds):
    second = builds["second"]
    assert second.returncode == 0, second.stdout[-4000:] + second.stderr[-2000:]


def test_the_gate_holds_each_of_those_two_sources_with_its_own_reason_and_passes_the_rest(builds):
    gate, first = builds["gate"], builds["first_gate"]
    assert first[LEAKING][0] is True and first[OUTSIDE][0] is True, "both passed the clean build"
    passed, why = gate[LEAKING]
    assert passed is False and "hold the source's own wording in a published column" in why, why
    passed, why = gate[OUTSIDE]
    # CT DEEP is held to the box macros/generated_notice_regions.sql gives it, which lat -74 is outside of too.
    assert passed is False and re.search(r"row\(s\) reach outside the \w+ box its source publishes in", why), why
    newly_held = {key for key, (passed, _) in gate.items() if not passed and first.get(key, (False,))[0]}
    assert newly_held == {LEAKING, OUTSIDE}


def test_every_conditions_writer_the_build_selects_writes_its_file(builds):
    assert builds["written"] == {writer: True for writer in WRITERS}


def test_the_notices_file_carries_both_clubs_last_good_rows_and_none_of_the_edited_content(builds):
    notices = builds["notices"]
    assert notices is not None
    held = {notice["source_key"]: notice for notice in notices if notice["source_key"] in (LEAKING, OUTSIDE)}
    assert set(held) == {LEAKING, OUTSIDE}, "each held club keeps its last good row"
    assert all(notice["carried_since"] for notice in held.values())
    assert held[LEAKING]["title"] == "Fixture Creek Trail"
    assert held[OUTSIDE]["place"] == {"kind": "geometry", "geometry": {"type": "Point", "coordinates": [-74.0, 41.0]}}
    assert "the ford" not in builds["notices_text"]


def test_the_tests_that_hold_a_source_warn_and_name_both(builds):
    statuses = {name: result["status"] for uid, result in builds["results"].items() for name in HOLDING_TESTS if name in uid}
    assert statuses == {name: "warn" for name in HOLDING_TESTS}
    assert builds["leaks"] == [(LEAKING,)]
    assert builds["outside"] == [(OUTSIDE,)]
