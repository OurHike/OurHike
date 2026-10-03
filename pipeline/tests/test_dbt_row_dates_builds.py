"""Real dbt builds of the podcasts mart, a fresh warehouse each, with the row history saved and restored between.

The production shape on a small fixture (decision 57): every run builds its
warehouse from raw on a new machine, and what carries a mart row's dates from
one build to the next is row_history.py's store. The podcasts mart is the
smallest whose rows come from a file the extract lands (podcast episodes,
with sources.json and an empty POI ledger beside it). Build 1 lands
episodes A, B and C; build 2 lands A as it was, B retitled, C gone and D new,
every row reloaded with a new `_dlt_id` and `_loaded_at`, as a dlt reload
stamps them. Then:

(a) A keeps the `_changed_at` and `_first_seen_at` build 1 gave it, so the
    load's own columns do not count as a change (macros/row_hash.sql);
(b) B's `_changed_at` moves to build 2's time while its `_first_seen_at`
    stays at build 1's;
(c) C leaves the mart, and its version in int_podcasts__history gets a
    dbt_valid_to, keeping its last title, which row_history_removed() reads;
and D is first seen, and changed, at build 2's time; each version records
the build that wrote it in `_built_by`. Build 3 runs as a conditions leg
whose restore failed (OURHIKE_ROW_HISTORY=off, snapshots left out): the mart
still builds, with both dates null, and the snapshot is untouched.

It needs the dbt requirements-dbt.txt pins, with the packages under
pipeline/dbt/dbt_packages/, and runs only when OURHIKE_DBT names that dbt:
pipeline-tests.yml's dbt job and scripts/test.sh's dbt suite set it; the
pytest job, which has no dbt, skips.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import duckdb
import pytest

import row_history

PIPELINE_DIR = Path(__file__).resolve().parent.parent
DBT_DIR = PIPELINE_DIR / "dbt"
DBT = os.environ.get("OURHIKE_DBT")
pytestmark = pytest.mark.skipif(not DBT, reason="OURHIKE_DBT names no dbt (the dbt job and scripts/test.sh set it)")

POI_LEDGER_COLUMNS = (
    "first_seen varchar, retired varchar, superseded_by varchar, poi_id varchar, fingerprint varchar, "
    "history varchar, lat double, lon double, name varchar, poi_type varchar, source varchar, "
    "source_feature_id varchar, _row bigint, _file varchar, _path varchar, _loaded_at timestamptz, "
    "_dlt_load_id varchar, _dlt_id varchar, stream_id varchar"
)


def _episode(letter: str, title: str, mile: float) -> dict:
    return {
        "spotify_id": letter * 22,
        "title": title,
        "show": "The Row Dates Hour",
        "minutes": 30,
        "at_miles": [[mile, mile + 2]],
        "reviewed": "2026-10-03",
    }


BUILD_1 = [_episode("A", "Alpha", 10.0), _episode("B", "Bravo", 20.0), _episode("C", "Charlie", 30.0)]
BUILD_2 = [_episode("A", "Alpha", 10.0), _episode("B", "Bravo, retitled", 20.0), _episode("D", "Delta", 40.0)]


def _raw(warehouse: Path, episodes: list[dict], load: str) -> None:
    """The three raw tables the podcasts mart reads, as the extract lands them, each row with this load's stamps."""
    registry = (PIPELINE_DIR / "sources.json").read_text(encoding="utf-8")
    with duckdb.connect(str(warehouse)) as con:
        con.execute("create schema raw")
        con.execute(
            "create table raw.raw_podcasts__podcast_episodes (row_json varchar, _row bigint, _file varchar, "
            "_path varchar, _loaded_at timestamptz, _dlt_load_id varchar, _dlt_id varchar)"
        )
        con.executemany(
            "insert into raw.raw_podcasts__podcast_episodes values (?, ?, 'podcast_episodes.json', "
            "'reference/podcast_episodes.json', now(), ?, ?)",
            [(json.dumps(episode), row, load, f"{load}-{row}") for row, episode in enumerate(episodes)],
        )
        con.execute(
            "create table raw.raw_registry__sources (row_json varchar, _row bigint, _path varchar, "
            "_loaded_at timestamptz, _dlt_load_id varchar, _dlt_id varchar)"
        )
        con.execute("insert into raw.raw_registry__sources values (?, 0, 'sources.json', now(), ?, ?)", [registry, load, load])
        con.execute(f"create table raw.raw_ourhike__poi_identity ({POI_LEDGER_COLUMNS})")


def _dbt(warehouse: Path, scratch: Path, *arguments: str, history: bool = True) -> None:
    env = {
        **os.environ,
        "OURHIKE_WAREHOUSE": str(warehouse),
        "DBT_ENGINE_SEND_ANONYMOUS_USAGE_STATS": "false",
        "TZ": "UTC",
        "OURHIKE_BUILT_BY": f"test {warehouse.parent.name}",
        "OURHIKE_ROW_HISTORY": "on" if history else "off",
    }
    paths = ("--target-path", str(scratch / "target"), "--log-path", str(scratch / "logs"))
    completed = subprocess.run(
        [DBT, *arguments, "--profiles-dir", ".", *paths], cwd=DBT_DIR, env=env, capture_output=True, text=True, check=False
    )
    assert completed.returncode == 0, completed.stdout[-4000:] + completed.stderr[-2000:]


def _build(warehouse: Path, scratch: Path, history: bool = True) -> None:
    _dbt(warehouse, scratch, "seed", history=history)
    leave_out = () if history else ("--exclude", "resource_type:snapshot")
    _dbt(warehouse, scratch, "build", "-s", "+podcasts", "--indirect-selection", "cautious", *leave_out, history=history)


def _query(warehouse: Path, sql: str) -> list[tuple]:
    with duckdb.connect(str(warehouse), read_only=True) as con:
        return con.execute(sql).fetchall()


# The marts' dates are TIMESTAMPTZ, and DuckDB hands one to Python only with
# pytz installed, which the dbt job's venv (requirements.txt) does not carry:
# every test here errored "No module named 'pytz'" on f06f8b1b. So the SQL
# turns each into naive UTC, and _DATE_TYPES reads the column type instead.
_DATES = "timezone('UTC', _first_seen_at), timezone('UTC', _changed_at)"
_DATE_TYPES = "select distinct typeof(_first_seen_at), typeof(_changed_at) from marts.podcasts_v1"


def _dates(warehouse: Path) -> dict[str, tuple]:
    rows = _query(warehouse, f"select title, {_DATES} from marts.podcasts_v1")
    return {title[0]: (first, changed) for title, first, changed in rows}


@pytest.fixture(scope="module")
def builds(tmp_path_factory) -> dict:
    root = tmp_path_factory.mktemp("row_dates")
    store = str(root / "history")
    one, two, three = (root / name / "warehouse.duckdb" for name in ("one", "two", "three"))
    for warehouse in (one, two, three):
        warehouse.parent.mkdir()

    _raw(one, BUILD_1, "load-1")
    row_history.restore(store, one, cold_start=True)
    _build(one, root)
    row_history.save(store, one)

    _raw(two, BUILD_2, "load-2")
    restored = row_history.restore(store, two, cold_start=False)
    _build(two, root)
    row_history.save(store, two)
    versions = _query(
        two,
        "select spotify_id, title, dbt_valid_from, dbt_valid_to, _built_by from intermediate.int_podcasts__history "
        "order by spotify_id, dbt_valid_from",
    )

    _raw(three, BUILD_2, "load-3")
    row_history.restore(store, three, cold_start=False)
    before = _query(three, "select count(*) from intermediate.int_podcasts__history")
    _build(three, root, history=False)
    return {
        "first": _dates(one),
        "types": _query(one, _DATE_TYPES),
        "second": _dates(two),
        "versions": versions,
        "restored": restored,
        "pointer": json.loads((root / "history" / row_history.POINTER).read_text()),
        "degraded": _query(three, f"select title, {_DATES} from marts.podcasts_v1 order by title"),
        "untouched": (before, _query(three, "select count(*) from intermediate.int_podcasts__history")),
    }


def test_the_second_build_restored_the_first_builds_history_into_its_fresh_warehouse(builds):
    assert builds["restored"].startswith("restored save")
    assert builds["pointer"]["previous_save_id"] is not None


def test_a_row_reloaded_unchanged_keeps_its_changed_at_and_first_seen_at(builds):
    assert builds["second"]["A"] == builds["first"]["A"]


def test_an_edited_row_moves_its_changed_at_to_the_second_build_and_keeps_its_first_seen_at(builds):
    first_seen, changed = builds["second"]["B"]
    assert first_seen == builds["first"]["B"][0]
    assert changed > builds["first"]["B"][1]
    assert changed == builds["second"]["D"][0], "B changed in the build that first saw D"


def test_a_removed_row_leaves_the_mart_and_its_last_version_closes_with_its_content(builds):
    assert "C" not in builds["second"]
    (closed,) = [row for row in builds["versions"] if row[0] == "C" * 22]
    _, title, _, valid_to, _ = closed
    assert title == "Charlie" and valid_to is not None
    assert valid_to >= builds["first"]["C"][1], "valid_to is naive UTC, as _DATES makes the mart's"


def test_a_new_row_is_first_seen_and_changed_in_the_build_that_first_saw_it(builds):
    first_seen, changed = builds["second"]["D"]
    assert first_seen == changed > builds["first"]["A"][1]


def test_each_version_names_the_build_that_wrote_it_and_an_unchanged_row_keeps_its_first(builds):
    by_build = {(spotify_id[0], title): built_by for spotify_id, title, _, _, built_by in builds["versions"]}
    assert by_build[("A", "Alpha")] == "test one", "A's one version is build 1's: _built_by is never hashed"
    assert by_build[("B", "Bravo, retitled")] == by_build[("D", "Delta")] == "test two"


def test_the_dates_are_utc_timestamptz_and_every_first_build_row_shares_the_history_start(builds):
    assert builds["types"] == [("TIMESTAMP WITH TIME ZONE", "TIMESTAMP WITH TIME ZONE")]
    starts = {first_seen for first_seen, _ in builds["first"].values()}
    assert len(starts) == 1
    recorded = builds["pointer"]["tables"]["int_podcasts__history"]["history_started_at"]
    assert recorded == next(iter(starts)).isoformat() + "Z"


def test_a_build_without_its_history_still_builds_the_mart_with_both_dates_null(builds):
    assert [title for title, _, _ in builds["degraded"]] == ["Alpha", "Bravo, retitled", "Delta"]
    assert all(first is None and changed is None for _, first, changed in builds["degraded"])
    before, after = builds["untouched"]
    assert before == after, "no snapshot ran, so the restored history is as it was"
