"""A real dbt build of decision 128: a PTNY section draws only while its match to the trail's closures page stands.

Decision 128 (the maintainer's poll of 2026-10-09, shown w6-ptny-closures.html):
Parks & Trails New York's closures layer (ptny_est_closures) says 'Closed' on
every Empire State Trail section it serves, with no date, reason or link, so a
section draws as closed only once a person has matched it to an item on the
trail's dated closures page (oprhp_est_trail_closures_page), and only while
that page's latest read still carries the item; its row then carries the
page's link and date. The dbt unit tests hold each model's rule; this holds
the three states end to end, from the raw tables to conditions/notices.json,
in one fixture warehouse, the history on, as successive hourly builds would:

1. the empty join, as the seed ships: no section reaches the closures mart or
   the file, each held for having no match;
2. a match, written as the session approving one would write it (the
   fixture's PTNY row and the fixture page's first item): the section is in
   the closures mart and in the file, with the page's link and its own date;
3. the page's next read no longer carries that item: the section leaves the
   mart and the file, and the warn test on int_closures__page_matches names
   the match for somebody to look at again.

PTNY's registry row is read as the commit approving its first match writes it,
`reaches_hikers` true, so rule 7 is the only thing that holds a section here
(tests/test_notice_page_matches_seed.py holds the two together in the files).

It needs dbt 2.0.6 with the packages under pipeline/dbt/dbt_packages/, and
runs only when OURHIKE_DBT names that dbt, as
tests/test_dbt_notice_source_held_for_its_rows_builds.py does.
"""

from __future__ import annotations

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
#: The Python that runs extract._fixtures, which imports dlt (tests/test_dbt_notice_tables_absent_builds.py says why).
EXTRACT_PYTHON = os.environ.get("OURHIKE_EXTRACT_PYTHON") or sys.executable
pytestmark = pytest.mark.skipif(not DBT, reason="OURHIKE_DBT names no dbt (the dbt job and scripts/test.sh set it)")

SOURCE = "ptny_est_closures"
PAGE = "oprhp_est_trail_closures_page"
PAGE_URL = "https://empiretrail.ny.gov/trail-closures"
#: make_dbt_fixtures.py's FIXTURE_DAY, the date its closures page states ('Updated September 21, 2026').
PAGE_DAY = "2026-09-21"
WARN_TEST = "dbt_utils_expression_is_true_int_closures__page_matches_held_because_is_null_or_not_page_read"
#: The singular test that every row of a confirming source in a mart has a standing match.
INVARIANT = "assert_every_row_of_a_confirming_source_carries_its_page"


def _ok(arguments: list[str], cwd: Path, env: dict) -> None:
    completed = subprocess.run(arguments, cwd=cwd, env=env, capture_output=True, text=True, check=False)
    assert completed.returncode == 0, completed.stdout[-4000:] + completed.stderr[-2000:]


def _rows(warehouse: Path, sql: str, parameters: list | None = None) -> list[tuple]:
    with duckdb.connect(str(warehouse), read_only=True) as con:
        con.execute("load spatial")  # the base models are views that cast their geometry
        return con.execute(sql, parameters or []).fetchall()


def _state(warehouse: Path, processed: Path, target: Path) -> dict:
    """What one build left: PTNY's rows in the closures mart and the notices file, why the club rule held each, and
    which tests warned."""
    notices = json.loads((processed / "conditions_notices.json").read_text(encoding="utf-8"))["notices"]
    results = json.loads((target / "run_results.json").read_text())["results"]
    return {
        "mart": _rows(warehouse, "select closure_id, obstructs_trail from marts.closures_v1 where source_key = ?", [SOURCE]),
        "file": [notice for notice in notices if notice["source_key"] == SOURCE],
        "held": dict(
            _rows(
                warehouse,
                "select notice_id, held_because from intermediate.int_closures__club_notices where source_key = ?",
                [SOURCE],
            )
        ),
        "matches": _rows(warehouse, "select notice_id, held_because from intermediate.int_closures__page_matches"),
        "warned": {result["unique_id"].split(".")[2] for result in results if result["status"] == "warn"},
    }


@pytest.fixture(scope="module")
def builds(tmp_path_factory) -> dict:
    root = tmp_path_factory.mktemp("page_matched")
    raw, warehouse, processed, target = root / "raw", root / "warehouse.duckdb", root / "processed", root / "target"
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
    paths = ["--profiles-dir", ".", "--target-path", str(target), "--log-path", str(root / "logs")]

    # PTNY's registry row as the commit approving its first match writes it.
    with duckdb.connect(str(warehouse)) as con:
        ((document,),) = con.execute("select row_json from raw.raw_registry__sources").fetchall()
        registry = json.loads(document)
        for entry in registry["sources"]:
            if entry["key"] == SOURCE:
                entry["reaches_hikers"] = True
        con.execute("update raw.raw_registry__sources set row_json = ?", [json.dumps(registry)])

    # 1. The empty join: the whole conditions chain, seeds first.
    _ok([DBT, "seed", *paths], DBT_DIR, dbt_env)
    selection = ["+pub_conditions_notices", f"+{INVARIANT}"]
    _ok([DBT, "build", "-s", *selection, "--indirect-selection", "cautious", *paths], DBT_DIR, dbt_env)
    empty = _state(warehouse, processed, target)

    # 2. A match, as an approving session writes it: the fixture's one PTNY row, by its id and raw key, and the
    # fixture page's first item, by its sha256. Into the seed's table, and then only what reads it is rebuilt, so
    # dbt seed does not put the shipped (empty) file back over it.
    ((notice_id, row_key),) = _rows(
        warehouse,
        f"select '{SOURCE}:' || objectid, notice_key from staging.base_nysparks__ptny_est_closures",
    )
    ((items,),) = _rows(warehouse, f"select item_sha256s from raw.raw_nysparks__{PAGE}")
    first, *rest = json.loads(items)
    with duckdb.connect(str(warehouse)) as con:
        con.execute(
            "insert into seeds.notice_page_matches values (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                notice_id,
                row_key,
                PAGE,
                "Fixture Town, Fixture County: The trail is closed between Fixture Road and Fixture Street for repairs.",
                first,
                "2026-10-09",
                "the maintainer's poll of 2026-10-09, PR #1805 — dlt → dbt re-platform as one go/no-go change",
                "Fixture",
            ],
        )
    # Only what lies between the match and what step 1 built: int_closures__page_matches+ alone also reaches
    # pub_conditions_weather_alerts (through int_closures__gate), which reads stg_derived__weather_squares, a model
    # step 1 never built. The singular test by name: under cautious selection a test runs only when every parent is
    # selected, and one of its parents is a seed.
    between = [f"int_closures__page_matches+,+{end}" for end in ("pub_conditions_notices", INVARIANT)]
    downstream = ["-s", *between, INVARIANT, "--indirect-selection", "cautious", *paths]
    _ok([DBT, "build", *downstream], DBT_DIR, dbt_env)
    matched = _state(warehouse, processed, target)

    # 3. The page's next read no longer carries that item. The base model is a view, so the raw row is what moves.
    with duckdb.connect(str(warehouse)) as con:
        con.execute(f"update raw.raw_nysparks__{PAGE} set item_sha256s = ?", [json.dumps(rest, separators=(",", ":"))])
    _ok([DBT, "build", *downstream], DBT_DIR, dbt_env)
    gone = _state(warehouse, processed, target)
    return {"empty": empty, "matched": matched, "gone": gone, "notice_id": notice_id}


def test_an_empty_join_draws_no_section_and_holds_each_for_having_no_match(builds):
    empty = builds["empty"]
    assert empty["mart"] == [] and empty["file"] == []
    assert empty["held"] and all(why.startswith("nobody has matched it") for why in empty["held"].values())
    assert empty["matches"] == []


def test_a_matched_section_draws_with_the_pages_link_and_the_pages_own_date(builds):
    matched, notice_id = builds["matched"], builds["notice_id"]
    assert matched["mart"] == [(notice_id, True)]
    (row,) = matched["file"]
    assert row["obstructs_trail"] is True and row["notice_id"] == notice_id
    assert row["matched_page"] == {"url": PAGE_URL, "updated_on": PAGE_DAY}
    assert row["updated_at"] is None, "the page's date is the page's, never PTNY's, which dates nothing"
    assert matched["held"][notice_id] is None
    assert WARN_TEST not in matched["warned"] and INVARIANT not in matched["warned"]


def test_a_section_whose_item_left_the_page_draws_nothing_and_its_match_is_named_for_a_person(builds):
    gone, notice_id = builds["gone"], builds["notice_id"]
    assert gone["mart"] == [] and gone["file"] == []
    ((matched_id, why),) = gone["matches"]
    assert matched_id == notice_id and "no longer carries the item it was matched to" in why
    assert gone["held"][notice_id].startswith("its match no longer stands: the latest read of its page")
    assert WARN_TEST in gone["warned"]
