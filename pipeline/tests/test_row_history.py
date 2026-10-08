"""row_history.py: the row-history snapshots and Elementary's history kept between runs, and every way a restore
or a save refuses.

Each test builds a small warehouse with an int_<mart>__history table in the `intermediate` schema shaped
like a dbt snapshot (key, _row_hash and the four dbt_ columns), so nothing here runs dbt. tests/test_dbt_row_dates_builds.py drives
dbt itself through two builds and a restore. Elementary's tables are shaped the same way, further down.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta

import duckdb
import pytest

import row_history
from row_history import POINTER, ColdStartRefused, Refused, restore, save


def _snapshot(warehouse, table="int_things__history", rows=((("a", "h1", datetime(2026, 10, 3, 14, 0), None)),)):
    with duckdb.connect(str(warehouse)) as con:
        con.execute("create schema if not exists intermediate")
        con.execute(
            f"create or replace table intermediate.{table} (thing_key varchar, _row_hash varchar, dbt_scd_id varchar, "
            "dbt_updated_at timestamp, dbt_valid_from timestamp, dbt_valid_to timestamp)"
        )
        con.executemany(
            f"insert into intermediate.{table} values (?, ?, ?, ?, ?, ?)",
            [(key, hashed, f"{key}{hashed}", started, started, ended) for key, hashed, started, ended in rows],
        )


def _rows(warehouse, table="int_things__history"):
    with duckdb.connect(str(warehouse)) as con:
        return con.execute(f"select * from intermediate.{table} order by all").fetchall()


def _cold_then_saved(tmp_path, rows=None):
    """A store that one build has started: restore with a cold start, a snapshot built, saved."""
    store, warehouse = tmp_path / "store", tmp_path / "first.duckdb"
    restore(str(store), warehouse, cold_start=True)
    _snapshot(warehouse, **({"rows": rows} if rows else {}))
    save(str(store), warehouse)
    return store, warehouse


def test_restore_refuses_an_empty_store_unless_a_cold_start_is_allowed(tmp_path):
    with pytest.raises(ColdStartRefused, match="refusing to start the row history again"):
        restore(str(tmp_path / "store"), tmp_path / "w.duckdb", cold_start=False)


def test_main_answers_a_refused_cold_start_with_exit_2_and_another_refusal_with_1(tmp_path, capsys):
    store, warehouse = str(tmp_path / "store"), str(tmp_path / "w.duckdb")
    assert row_history.main(["restore", "--url", store, "--warehouse", warehouse]) == 2
    assert row_history.main(["save", "--url", store, "--warehouse", warehouse]) == 1
    assert "::error title=Row history" in capsys.readouterr().out


def test_a_saved_history_restores_into_a_new_warehouse_row_for_row(tmp_path):
    rows = (("a", "h1", datetime(2026, 10, 3, 14, 0), None), ("b", "h2", datetime(2026, 10, 3, 14, 0), datetime(2026, 11, 3)))
    store, first = _cold_then_saved(tmp_path, rows)
    second = tmp_path / "second.duckdb"

    message = restore(str(store), second, cold_start=False)

    assert "restored save" in message
    assert _rows(second) == _rows(first)
    with duckdb.connect(str(second)) as con:
        columns = "select data_type from information_schema.columns where table_name = 'int_things__history'"
        types = con.execute(columns).fetchall()
    assert ("TIMESTAMP",) in types, "dbt_valid_from comes back as the TIMESTAMP dbt wrote, not as text"


def test_history_json_records_rows_sha256_and_each_snapshots_history_start(tmp_path):
    store, _ = _cold_then_saved(tmp_path)
    pointer = json.loads((store / POINTER).read_text())

    entry = pointer["tables"]["int_things__history"]
    assert entry["rows"] == 1 and len(entry["sha256"]) == 64
    assert entry["history_started_at"] == "2026-10-03T14:00:00Z"
    assert pointer["previous_save_id"] is None, "the first save follows a cold start"
    assert (store / entry["file"]).exists()


def test_restore_refuses_a_file_whose_sha256_is_not_what_history_json_says(tmp_path):
    store, _ = _cold_then_saved(tmp_path)
    entry = json.loads((store / POINTER).read_text())["tables"]["int_things__history"]
    (store / entry["file"]).write_bytes(b"not the parquet that was saved")

    with pytest.raises(Refused, match="has sha256"):
        restore(str(store), tmp_path / "second.duckdb", cold_start=False)


def test_restore_refuses_a_file_history_json_names_that_is_gone(tmp_path):
    store, _ = _cold_then_saved(tmp_path)
    entry = json.loads((store / POINTER).read_text())["tables"]["int_things__history"]
    (store / entry["file"]).unlink()

    with pytest.raises(Refused, match="is not there"):
        restore(str(store), tmp_path / "second.duckdb", cold_start=True)


def test_a_restore_that_fails_leaves_no_receipt_so_its_warehouse_cannot_be_saved(tmp_path):
    store, warehouse = _cold_then_saved(tmp_path)
    entry = json.loads((store / POINTER).read_text())["tables"]["int_things__history"]
    (store / entry["file"]).write_bytes(b"torn")

    with pytest.raises(Refused):
        restore(str(store), warehouse, cold_start=False)
    with pytest.raises(Refused, match="no restore receipt"):
        save(str(store), warehouse)


def test_save_refuses_a_warehouse_restore_never_ran_against(tmp_path):
    warehouse = tmp_path / "w.duckdb"
    _snapshot(warehouse)

    with pytest.raises(Refused, match="no restore receipt"):
        save(str(tmp_path / "store"), warehouse)


def test_save_refuses_a_store_other_than_the_one_restored_from(tmp_path):
    store, warehouse = _cold_then_saved(tmp_path)

    with pytest.raises(Refused, match="was restored from"):
        save(str(tmp_path / "elsewhere"), warehouse)


def test_save_refuses_a_snapshot_that_holds_fewer_rows_than_were_restored(tmp_path):
    rows = (("a", "h1", datetime(2026, 10, 3), None), ("b", "h2", datetime(2026, 10, 3), None))
    store, _ = _cold_then_saved(tmp_path, rows)
    second = tmp_path / "second.duckdb"
    restore(str(store), second, cold_start=False)
    _snapshot(second, rows=rows[:1])

    with pytest.raises(Refused, match="fewer rows than were restored"):
        save(str(store), second)


def test_save_refuses_when_another_run_saved_after_this_warehouse_restored(tmp_path):
    store, _ = _cold_then_saved(tmp_path)
    late, early = tmp_path / "late.duckdb", tmp_path / "early.duckdb"
    restore(str(store), late, cold_start=False)
    restore(str(store), early, cold_start=False)
    save(str(store), early)

    with pytest.raises(Refused, match="another run saved in between"):
        save(str(store), late)


def test_a_second_save_points_back_at_the_first_and_old_saves_beyond_keep_saves_go(tmp_path, monkeypatch):
    monkeypatch.setattr(row_history, "KEEP_SAVES", 2)
    store, _ = _cold_then_saved(tmp_path)
    first = json.loads((store / POINTER).read_text())["save_id"]
    for name in ("b.duckdb", "c.duckdb"):
        restore(str(store), tmp_path / name, cold_start=False)
        save(str(store), tmp_path / name)

    pointer = json.loads((store / POINTER).read_text())
    folders = sorted(path.name for path in (store / "saves").iterdir())
    assert len(folders) == 2 and pointer["save_id"] in folders and first not in folders
    assert pointer["previous_save_id"] in folders


def test_a_cold_start_drops_whatever_history_the_warehouse_already_held(tmp_path):
    warehouse = tmp_path / "w.duckdb"
    _snapshot(warehouse)

    restore(str(tmp_path / "store"), warehouse, cold_start=True)

    with duckdb.connect(str(warehouse)) as con:
        tables = "select count(*) from information_schema.tables where table_schema = 'intermediate'"
        assert con.execute(tables).fetchone() == (0,)


def test_only_tables_named_history_are_saved_restored_or_dropped_never_the_intermediate_models_beside_them(tmp_path):
    store, warehouse = tmp_path / "store", tmp_path / "w.duckdb"
    restore(str(store), warehouse, cold_start=True)
    _snapshot(warehouse)
    with duckdb.connect(str(warehouse)) as con:
        con.execute("create table intermediate.int_things__final as select 1 as thing")
    save(str(store), warehouse)

    assert set(json.loads((store / POINTER).read_text())["tables"]) == {"int_things__history"}
    restore(str(store), warehouse, cold_start=False)
    with duckdb.connect(str(warehouse)) as con:
        assert con.execute("select thing from intermediate.int_things__final").fetchall() == [(1,)]


def test_a_store_url_that_is_not_a_directory_file_or_s3_is_refused():
    with pytest.raises(Refused, match="a history store is a directory"):
        row_history.Store("https://example.org/history")


# --- Elementary's history (row_history.py's docstring, "ELEMENTARY'S HISTORY") ---
#
# Each warehouse below holds Elementary 0.26.0's four kept tables with the columns row_history.py reads and one value,
# filled the way Elementary fills them: a check with no timestamp column adds one metric row a build, bucket_end the
# build's start; a check with one appends buckets it already has again under the same `id` with a later `updated_at`
# (handle_tests_results.sql's insert_data_monitoring_metrics(); get_anomaly_scores_query.sql reads the newest).

BUILD_1, BUILD_2 = datetime(2026, 10, 1, 6, 0), datetime(2026, 10, 2, 6, 0)
ELEMENTARY_TABLES = {
    "data_monitoring_metrics": "id varchar, full_table_name varchar, metric_name varchar, metric_value float, "
    "bucket_start timestamp, bucket_end timestamp, updated_at timestamp, created_at timestamp",
    "schema_columns_snapshot": "column_state_id varchar, full_table_name varchar, column_name varchar, "
    "data_type varchar, detected_at timestamp, created_at timestamp",
    "elementary_test_results": "id varchar, test_unique_id varchar, status varchar, invocation_id varchar, "
    "detected_at timestamp, created_at timestamp",
    "dbt_invocations": "invocation_id varchar, command varchar, created_at timestamp",
}


def _elementary_tables(warehouse):
    """Elementary's own tables as `dbt run --select package:elementary` leaves them: created empty on a cold start,
    and left as they are over a restored history, whose rows its incremental models keep."""
    with duckdb.connect(str(warehouse)) as con:
        con.execute("create schema if not exists elementary")
        for table, columns in ELEMENTARY_TABLES.items():
            con.execute(f"create table if not exists elementary.{table} ({columns})")


def _elementary_build(warehouse, at, invocation, *, rows=100.0, columns=("id", "name")):
    """What one build's checks add: a row count with no timestamp column, today's bucket of a timestamped one (the
    same id for every build that day, so a second is a rewrite), a schema snapshot of `things`, two test results and
    the invocation."""
    day = at.replace(hour=0)
    with duckdb.connect(str(warehouse)) as con:
        con.executemany(
            "insert into elementary.data_monitoring_metrics values (?, 'things', ?, ?, ?, ?, ?, ?)",
            [
                (f"row_count {at}", "row_count", rows, None, at, at, at),
                (f"by_day {day}", "row_count_by_day", rows / 2, day, day + timedelta(days=1), at, at),
            ],
        )
        con.executemany(
            "insert into elementary.schema_columns_snapshot values (?, 'things', ?, 'varchar', ?, ?)",
            [(f"things.{column}", column, at, at) for column in columns],
        )
        con.executemany(
            "insert into elementary.elementary_test_results values (?, ?, 'pass', ?, ?, ?)",
            [(f"{invocation}.{test}", test, invocation, at, at) for test in ("volume", "schema")],
        )
        con.execute("insert into elementary.dbt_invocations values (?, 'test', ?)", [invocation, at])


def _elementary_rows(warehouse, table, columns="*"):
    with duckdb.connect(str(warehouse)) as con:
        return con.execute(f"select {columns} from elementary.{table} order by all").fetchall()


def _elementary_pointer(store):
    return json.loads((store / row_history.ELEMENTARY_POINTER).read_text())


def _first_build(tmp_path, **build):
    """A store one build has started, Elementary's history with it: a cold start, a build, a save at BUILD_1."""
    store, warehouse = tmp_path / "store", tmp_path / "first.duckdb"
    restore(str(store), warehouse, cold_start=True)
    _snapshot(warehouse)
    _elementary_tables(warehouse)
    _elementary_build(warehouse, BUILD_1, "inv1", **build)
    save(str(store), warehouse, keep_days=21, now=BUILD_1)
    return store, warehouse


def _next_build(tmp_path, store, name="second.duckdb", **policy):
    """A fresh warehouse restored from the store, Elementary's own tables over it, as build_marts.py runs them."""
    warehouse = tmp_path / name
    restore(str(store), warehouse, cold_start=False, **policy)
    _elementary_tables(warehouse)
    return warehouse


def test_two_builds_one_store_the_third_restores_both_builds_rows_and_a_rewritten_bucket_once(tmp_path):
    store, _ = _first_build(tmp_path)
    second = _next_build(tmp_path, store)
    assert _elementary_rows(second, "dbt_invocations", "invocation_id") == [("inv1",)]

    _elementary_build(second, BUILD_1.replace(hour=18), "inv2", rows=104.0)
    message = save(str(store), second, keep_days=21, now=BUILD_1.replace(hour=18))
    third = _next_build(tmp_path, store, "third.duckdb")

    assert "Elementary's history: saved" in message
    assert _elementary_rows(third, "dbt_invocations", "invocation_id") == [("inv1",), ("inv2",)]
    assert len(_elementary_rows(third, "elementary_test_results")) == 4, "two results a build, both builds"
    metrics = _elementary_rows(third, "data_monitoring_metrics", "metric_name, metric_value")
    assert metrics == [("row_count", 100.0), ("row_count", 104.0), ("row_count_by_day", 52.0)], (
        "one row count a build, and the day's bucket once, as build 2 rewrote it"
    )


def test_a_store_saved_before_elementary_starts_its_history_only_when_allowed(tmp_path):
    """Every store saved before decision 102 holds a history.json and no elementary.json."""
    store, _ = _cold_then_saved(tmp_path)
    (store / row_history.ELEMENTARY_POINTER).unlink()

    with pytest.raises(row_history.ElementaryColdStartRefused, match="refusing to start Elementary's history again"):
        restore(str(store), tmp_path / "refused.duckdb", cold_start=False)
    message = restore(str(store), tmp_path / "second.duckdb", cold_start=False, elementary_cold_start=True)

    assert "restored save" in message and "Elementary's history: cold start" in message
    assert row_history.main(["restore", "--url", str(store), "--warehouse", str(tmp_path / "w.duckdb")]) == 2


def test_elementary_json_records_each_tables_rows_bytes_sha256_and_window_and_the_save_before(tmp_path):
    store, _ = _first_build(tmp_path)
    second = _next_build(tmp_path, store)
    _elementary_build(second, BUILD_2, "inv2")
    save(str(store), second, keep_days=21, now=BUILD_2)

    pointer, rows_pointer = _elementary_pointer(store), json.loads((store / POINTER).read_text())
    entry = pointer["tables"]["dbt_invocations"]
    assert set(pointer["tables"]) == set(row_history.KEPT)
    assert entry["rows"] == 2 and entry["bytes"] == (store / entry["file"]).stat().st_size and len(entry["sha256"]) == 64
    assert (entry["oldest"], entry["newest"]) == ("2026-10-01T06:00:00Z", "2026-10-02T06:00:00Z")
    assert pointer["keep_days"] == 21 and pointer["kept_since"] == "2026-09-11T06:00:00Z"
    assert pointer["save_id"] == rows_pointer["save_id"], "one save id for both parts of one save"
    assert pointer["previous_save_id"] == rows_pointer["previous_save_id"] is not None


def test_retention_keeps_the_window_and_each_tables_latest_snapshot_whatever_its_age(tmp_path):
    store, _ = _first_build(tmp_path, columns=("id", "name", "gone"))
    second = _next_build(tmp_path, store)
    later = BUILD_1 + timedelta(days=30)
    _elementary_build(second, later, "inv2", columns=("id", "name"))
    with duckdb.connect(str(second)) as con:
        con.execute(
            "insert into elementary.schema_columns_snapshot values ('other.id', 'other', 'id', 'varchar', ?, ?)",
            [BUILD_1 - timedelta(days=200)] * 2,
        )

    save(str(store), second, keep_days=21, now=later)
    third = _next_build(tmp_path, store, "third.duckdb")

    assert _elementary_rows(third, "dbt_invocations", "invocation_id") == [("inv2",)], "inv1 is 30 days old"
    assert {row[0] for row in _elementary_rows(third, "elementary_test_results", "invocation_id")} == {"inv2"}
    assert {row[0] for row in _elementary_rows(third, "data_monitoring_metrics", "bucket_end")} == {
        later,
        later.replace(hour=0) + timedelta(days=1),
    }
    assert _elementary_rows(third, "schema_columns_snapshot", "full_table_name, column_name, detected_at") == [
        ("other", "id", BUILD_1 - timedelta(days=200)),
        ("things", "id", later),
        ("things", "name", later),
    ], "a schema check reads only a table's latest snapshot: that one is kept whatever its age, and an older one is not"


def test_save_refuses_a_restored_row_gone_from_the_warehouse_and_writes_nothing(tmp_path):
    store, _ = _first_build(tmp_path)
    before = (store / POINTER).read_text(), (store / row_history.ELEMENTARY_POINTER).read_text()
    second = _next_build(tmp_path, store)
    _elementary_build(second, BUILD_2, "inv2")
    with duckdb.connect(str(second)) as con:
        con.execute(
            "delete from elementary.data_monitoring_metrics where metric_name = 'row_count' and bucket_end = ?", [BUILD_1]
        )

    with pytest.raises(row_history.ElementaryRefused, match=r"restored and now gone .*data_monitoring_metrics 1 of 2"):
        save(str(store), second, keep_days=21, now=BUILD_2)
    assert ((store / POINTER).read_text(), (store / row_history.ELEMENTARY_POINTER).read_text()) == before


def test_a_rewritten_bucket_keeps_its_id_so_the_guard_lets_it_through_and_its_newest_row_is_saved(tmp_path):
    """The row history's rule has it backwards here: the saved copy holds fewer metric rows than the warehouse."""
    store, _ = _first_build(tmp_path)
    second = _next_build(tmp_path, store)
    with duckdb.connect(str(second)) as con:
        con.execute(
            "insert into elementary.data_monitoring_metrics select id, full_table_name, metric_name, 61, bucket_start, "
            "bucket_end, ?, ? from elementary.data_monitoring_metrics where metric_name = 'row_count_by_day'",
            [BUILD_1.replace(hour=9)] * 2,
        )
        assert con.execute("select count(*) from elementary.data_monitoring_metrics").fetchone() == (3,)

    save(str(store), second, keep_days=21, now=BUILD_1.replace(hour=9))

    assert _elementary_pointer(store)["tables"]["data_monitoring_metrics"]["rows"] == 2
    third = _next_build(tmp_path, store, "third.duckdb")
    assert ("row_count_by_day", 61.0) in _elementary_rows(third, "data_monitoring_metrics", "metric_name, metric_value")


def test_save_refuses_an_elementary_table_restored_and_gone(tmp_path):
    store, _ = _first_build(tmp_path)
    second = _next_build(tmp_path, store)
    with duckdb.connect(str(second)) as con:
        con.execute("drop table elementary.elementary_test_results")

    with pytest.raises(row_history.ElementaryRefused, match="restored and now gone: elementary_test_results"):
        save(str(store), second, keep_days=21, now=BUILD_2)


def test_save_refuses_when_another_run_saved_elementarys_history_after_this_warehouse_restored(tmp_path):
    store, _ = _first_build(tmp_path)
    late, early = _next_build(tmp_path, store, "late.duckdb"), _next_build(tmp_path, store, "early.duckdb")
    save(str(store), early, keep_days=21, now=BUILD_2)
    # The snapshots' receipt is moved on, so that only Elementary's own check stands between `late` and the store.
    with duckdb.connect(str(late)) as con:
        con.execute("update row_history.restored set save_id = ?", [json.loads((store / POINTER).read_text())["save_id"]])

    with pytest.raises(row_history.ElementaryRefused, match="another run saved Elementary's history in between"):
        save(str(store), late, keep_days=21, now=BUILD_2)


def test_a_torn_elementary_file_fails_the_whole_restore_by_default_and_leaves_no_receipt(tmp_path):
    store, _ = _first_build(tmp_path)
    entry = _elementary_pointer(store)["tables"]["elementary_test_results"]
    (store / entry["file"]).write_bytes(b"torn")
    warehouse = tmp_path / "second.duckdb"

    with pytest.raises(row_history.ElementaryRefused, match="has sha256"):
        restore(str(store), warehouse, cold_start=False)
    with pytest.raises(Refused, match="no restore receipt"):
        save(str(store), warehouse)
    assert row_history.main(["restore", "--url", str(store), "--warehouse", str(warehouse)]) == 1


def test_under_degrade_a_torn_elementary_file_restores_the_snapshots_and_none_of_elementarys_history(tmp_path, capsys):
    store, _ = _first_build(tmp_path)
    good = _elementary_pointer(store)["save_id"]
    entry = _elementary_pointer(store)["tables"]["elementary_test_results"]
    (store / entry["file"]).write_bytes(b"torn")
    warehouse = tmp_path / "second.duckdb"

    code = row_history.main(["restore", "--url", str(store), "--warehouse", str(warehouse), "--elementary-on-failure", "degrade"])

    assert code == row_history.ELEMENTARY_DEGRADED_EXIT
    assert "::error title=Elementary's history not restored::" in capsys.readouterr().out
    assert _rows(warehouse) == _rows(tmp_path / "first.duckdb"), "the snapshots, a hiker's row dates, are restored"
    with duckdb.connect(str(warehouse)) as con:
        tables = "select count(*) from information_schema.tables where table_schema = 'elementary'"
        assert con.execute(tables).fetchone() == (0,), "its checks see no earlier build rather than part of one"
    _elementary_tables(warehouse)
    _elementary_build(warehouse, BUILD_2, "inv2")

    message = save(str(store), warehouse, keep_days=21, elementary_on_failure="degrade", now=BUILD_2)

    assert "none of it is saved" in message
    assert json.loads((store / POINTER).read_text())["previous_save_id"] is not None, "the snapshots were saved"
    assert _elementary_pointer(store)["save_id"] == good, "elementary.json keeps naming the last good save"


def test_under_degrade_a_refused_elementary_save_still_saves_the_snapshots(tmp_path):
    store, _ = _first_build(tmp_path)
    good, rows_before = _elementary_pointer(store)["save_id"], json.loads((store / POINTER).read_text())["save_id"]
    second = _next_build(tmp_path, store)
    with duckdb.connect(str(second)) as con:
        con.execute("delete from elementary.dbt_invocations")

    with pytest.raises(row_history.ElementaryDegraded) as degraded:
        save(str(store), second, keep_days=21, elementary_on_failure="degrade", now=BUILD_2)

    assert "restored and now gone" in degraded.value.failure and "saved 1 snapshot tables" in degraded.value.done
    assert json.loads((store / POINTER).read_text())["previous_save_id"] == rows_before
    assert _elementary_pointer(store)["save_id"] == good


def test_only_the_four_kept_tables_are_restored_dropped_or_saved_never_elementarys_others(tmp_path):
    store, warehouse = tmp_path / "store", tmp_path / "w.duckdb"
    restore(str(store), warehouse, cold_start=True)
    _elementary_tables(warehouse)
    _elementary_build(warehouse, BUILD_1, "inv1")
    with duckdb.connect(str(warehouse)) as con:
        con.execute("create table elementary.dbt_run_results as select 'model.x' as unique_id")
        con.execute("create table elementary.test_result_rows as select 'a failing row' as result_row")
    save(str(store), warehouse, keep_days=21, now=BUILD_1)

    assert set(_elementary_pointer(store)["tables"]) == set(row_history.KEPT)
    restore(str(store), warehouse, cold_start=False)
    assert _elementary_rows(warehouse, "dbt_run_results") == [("model.x",)]
    assert _elementary_rows(warehouse, "test_result_rows") == [("a failing row",)]


def test_elementarys_saves_beyond_keep_saves_go_from_its_own_folder_and_share_the_snapshots_save_ids(tmp_path, monkeypatch):
    monkeypatch.setattr(row_history, "KEEP_SAVES", 2)
    store, _ = _first_build(tmp_path)
    first = _elementary_pointer(store)["save_id"]
    for hour, name in ((7, "b.duckdb"), (8, "c.duckdb")):
        warehouse = _next_build(tmp_path, store, name)
        _elementary_build(warehouse, BUILD_1.replace(hour=hour), name)
        save(str(store), warehouse, keep_days=21, now=BUILD_1.replace(hour=hour))

    folders = sorted(path.name for path in (store / row_history.ELEMENTARY_SAVES).iterdir())
    assert len(folders) == 2 and first not in folders and _elementary_pointer(store)["save_id"] in folders
    assert sorted(path.name for path in (store / "saves").iterdir()) == folders


def test_save_refuses_to_keep_less_than_a_day():
    with pytest.raises(Refused, match="at least one day"):
        save("/nowhere", "/nowhere.duckdb", keep_days=0)


def test_the_default_keep_days_is_the_longest_any_lane_keeps_and_the_exit_codes_agree():
    """build_marts.py imports only the standard library, so it holds its own copies of both numbers."""
    import build_marts

    assert row_history.ELEMENTARY_KEEP_DAYS == max(build_marts.ELEMENTARY_KEEP_DAYS.values())
    assert row_history.ELEMENTARY_DEGRADED_EXIT == build_marts.ELEMENTARY_DEGRADED_EXIT
    assert build_marts.ELEMENTARY_DEGRADED_EXIT not in (0, 1, 2, *build_marts.PUBLISHABLE_EXITS)


# --- ELEMENTARY'S HISTORY ALONE: the hourly lane's checks run after its build (decision 110) ------------------------

CHECKS_AT = BUILD_2.replace(hour=7)


def _hourly_build(tmp_path):
    """A build that restored both parts from a started store, added its own rows and saved both, as
    build_marts.py --lane hourly does: its warehouse, the store, and the build's save id."""
    store, _ = _first_build(tmp_path)
    warehouse = _next_build(tmp_path, store, "build.duckdb")
    _elementary_build(warehouse, BUILD_2, "inv2")
    save(str(store), warehouse, keep_days=21, now=BUILD_2)
    return store, warehouse, _elementary_pointer(store)["save_id"]


def test_the_checks_run_restores_elementarys_history_alone_and_saves_its_checks_over_the_builds(tmp_path):
    store, warehouse, build_save = _hourly_build(tmp_path)
    rows_pointer, snapshot_rows = (store / POINTER).read_text(), _rows(warehouse)

    restored = row_history.restore_elementary(str(store), warehouse)
    _elementary_build(warehouse, CHECKS_AT, "inv3")
    saved = row_history.save_elementary(str(store), warehouse, keep_days=21, now=CHECKS_AT)
    after = _next_build(tmp_path, store, "next.duckdb")

    assert f"restored save {build_save}" in restored and "Elementary's history: saved" in saved
    assert (store / POINTER).read_text() == rows_pointer, "history.json and the snapshots' saves are the build's"
    assert _rows(warehouse) == snapshot_rows, "the snapshot tables are left as the build left them"
    pointer = _elementary_pointer(store)
    assert pointer["previous_save_id"] == build_save and pointer["save_id"] != build_save
    assert _elementary_rows(after, "dbt_invocations", "invocation_id") == [("inv1",), ("inv2",), ("inv3",)]


def test_the_checks_runs_save_refuses_when_a_build_saved_after_its_restore(tmp_path):
    """The next hourly build waits for the checks run (their shared concurrency group); were it not to, this is the
    refusal that keeps the checks from saving over its history."""
    store, warehouse, _ = _hourly_build(tmp_path)
    row_history.restore_elementary(str(store), warehouse)
    later = _next_build(tmp_path, store, "later.duckdb")
    save(str(store), later, keep_days=21, now=CHECKS_AT)

    with pytest.raises(row_history.ElementaryRefused, match="another run saved Elementary's history in between"):
        row_history.save_elementary(str(store), warehouse, keep_days=21, now=CHECKS_AT)
    assert row_history.main(["save", "--url", str(store), "--warehouse", str(warehouse), "--elementary-only"]) == 1


def test_under_degrade_a_checks_run_whose_restore_fails_checks_with_no_history_and_saves_none(tmp_path, capsys):
    store, warehouse, build_save = _hourly_build(tmp_path)
    entry = _elementary_pointer(store)["tables"]["elementary_test_results"]
    (store / entry["file"]).write_bytes(b"torn")
    args = ["--url", str(store), "--warehouse", str(warehouse), "--elementary-only", "--elementary-on-failure", "degrade"]

    restored = row_history.main(["restore", *args])
    _elementary_tables(warehouse)
    _elementary_build(warehouse, CHECKS_AT, "inv3")
    saved = row_history.main(["save", *args])

    out = capsys.readouterr().out
    assert (restored, saved) == (row_history.ELEMENTARY_DEGRADED_EXIT, 0)
    assert "::error title=Elementary's history not restored::" in out and "none of it is saved" in out
    assert _elementary_rows(warehouse, "dbt_invocations", "invocation_id") == [("inv3",)], "no earlier build, not part of one"
    assert _elementary_pointer(store)["save_id"] == build_save


def test_under_degrade_a_store_the_checks_run_cannot_reach_is_elementarys_failure_too(tmp_path):
    """Its row history is the build's to have restored, so nothing else is at stake in this run."""
    _, warehouse, _ = _hourly_build(tmp_path)
    nowhere = str(tmp_path / "no" / "such" / "store")

    with pytest.raises(row_history.ElementaryDegraded, match="does not exist"):
        row_history.restore_elementary(nowhere, warehouse, elementary_on_failure="degrade")
    with pytest.raises(Refused, match="does not exist"):
        row_history.restore_elementary(nowhere, warehouse)
