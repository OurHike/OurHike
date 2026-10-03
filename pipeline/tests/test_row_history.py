"""row_history.py: the row-history snapshots kept between runs, and every way a restore or a save refuses.

Each test builds a small warehouse with an int_<mart>__history table in the `intermediate` schema shaped
like a dbt snapshot (key, _row_hash and the four dbt_ columns), so nothing here runs dbt. tests/test_dbt_row_dates_builds.py drives
dbt itself through two builds and a restore.
"""

from __future__ import annotations

import json
from datetime import datetime

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
        types = con.execute("select data_type from information_schema.columns where table_name = 'int_things__history'").fetchall()
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
        assert con.execute("select count(*) from information_schema.tables where table_schema = 'intermediate'").fetchone() == (0,)


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
