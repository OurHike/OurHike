"""hand_off.py: an hourly build's warehouse handed to the run that checks it, through the leg's history store.

Every test runs on a local directory standing in for the store, as tests/test_row_history.py does: Store reads and
writes a directory and an s3:// URL through the same methods.
"""

from __future__ import annotations

import json

import duckdb
import pytest

import hand_off


def _warehouse(path, rows=3):
    path.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(path)) as con:
        con.execute("create schema if not exists marts")
        con.execute("create or replace table marts.closures as select range as closure_id from range(?)", [rows])
    return path


def _closures(path):
    with duckdb.connect(str(path), read_only=True) as con:
        return con.execute("select count(*) from marts.closures").fetchone()[0]


def test_a_warehouse_put_by_one_run_is_taken_by_the_checks_of_that_run_whole(tmp_path):
    store = tmp_path / "store"
    built = _warehouse(tmp_path / "build" / "warehouse.duckdb")

    put = hand_off.put(str(store), built, "37800000001", "2")
    taken = hand_off.take(str(store), tmp_path / "checks" / "warehouse.duckdb", "37800000001")

    pointer = json.loads((store / hand_off.POINTER).read_text())
    assert (pointer["run"], pointer["attempt"], pointer["bytes"]) == ("37800000001", "2", built.stat().st_size)
    assert pointer["gzip_bytes"] == (store / hand_off.WAREHOUSE).stat().st_size < pointer["bytes"], "the upload is gzipped"
    assert "handed run 37800000001.2's warehouse" in put and "took run 37800000001.2's warehouse" in taken
    assert _closures(tmp_path / "checks" / "warehouse.duckdb") == 3
    assert (tmp_path / "checks" / "warehouse.duckdb").read_bytes() == built.read_bytes(), "the same file, byte for byte"


def test_each_build_overwrites_the_last_so_the_checks_of_an_older_run_find_nothing_of_theirs(tmp_path):
    store = tmp_path / "store"
    hand_off.put(str(store), _warehouse(tmp_path / "first.duckdb", rows=3), "1")
    hand_off.put(str(store), _warehouse(tmp_path / "second.duckdb", rows=5), "2")

    with pytest.raises(hand_off.NotHandedOff, match="holds run 2's warehouse"):
        hand_off.take(str(store), tmp_path / "late.duckdb", "1")
    hand_off.take(str(store), tmp_path / "now.duckdb", "2")

    assert not (tmp_path / "late.duckdb").exists() and _closures(tmp_path / "now.duckdb") == 5
    assert sorted(path.name for path in (store / hand_off.FOLDER).iterdir()) == ["hand_off.json", "warehouse.duckdb.gz"]


def test_take_answers_nothing_handed_off_with_its_own_exit_and_a_torn_upload_with_1(tmp_path, capsys):
    store = tmp_path / "store"
    taken = tmp_path / "checks.duckdb"
    args = ["take", "--url", str(store), "--warehouse", str(taken), "--run", "7"]
    (store / hand_off.FOLDER).mkdir(parents=True)

    assert hand_off.main(args) == hand_off.NOT_HANDED_OFF
    hand_off.put(str(store), _warehouse(tmp_path / "build.duckdb"), "7")
    with (store / hand_off.WAREHOUSE).open("ab") as torn:
        torn.write(b"a later upload, half landed")

    assert hand_off.main(args) == 1
    assert "::error title=Warehouse not handed off::" in capsys.readouterr().out
    assert not taken.exists(), "nothing torn is left where the checks would read it"


def test_take_refuses_an_upload_whose_own_hash_matches_but_whose_warehouse_does_not(tmp_path, capsys):
    """Both are checked: the upload before it is unpacked, the warehouse after, so a pointer naming another
    warehouse's size and hash stops the checks rather than letting them read the wrong hour."""
    store = tmp_path / "store"
    taken = tmp_path / "checks.duckdb"
    hand_off.put(str(store), _warehouse(tmp_path / "build.duckdb"), "7")
    pointer = json.loads((store / hand_off.POINTER).read_text())
    (store / hand_off.POINTER).write_text(json.dumps({**pointer, "sha256": "0" * 64}))

    assert hand_off.main(["take", "--url", str(store), "--warehouse", str(taken), "--run", "7"]) == 1
    assert "the warehouse unpacked from" in capsys.readouterr().out and not taken.exists()


def test_the_checks_of_a_build_take_its_warehouse_only_from_the_commit_their_checkout_is(tmp_path, capsys):
    """A push between the build and its checks makes the checkout a later commit than the build's, whose project the
    warehouse was not built from: nothing to check, the same exit as a build that handed off nothing."""
    store = tmp_path / "store"
    built, build_commit = _warehouse(tmp_path / "build.duckdb"), "27f4ee3a73330ef3364a664132f2dbc73502984d"
    hand_off.put(str(store), built, "7", commit=build_commit)
    later = "fc32a8e6" + "0" * 32
    args = ["take", "--url", str(store), "--warehouse", str(tmp_path / "checks.duckdb"), "--run", "7"]

    assert hand_off.main([*args, "--commit", later]) == hand_off.NOT_HANDED_OFF
    assert "run 7's build ran on 27f4ee3a7333 and this checkout is fc32a8e60000" in capsys.readouterr().out
    assert not (tmp_path / "checks.duckdb").exists()
    assert json.loads((store / hand_off.POINTER).read_text())["commit"] == build_commit
    assert hand_off.main([*args, "--commit", build_commit]) == 0 and _closures(tmp_path / "checks.duckdb") == 3


def test_put_refuses_a_warehouse_that_is_not_there(tmp_path, capsys):
    args = ["put", "--url", str(tmp_path / "store"), "--warehouse", str(tmp_path / "none.duckdb"), "--run", "7"]

    assert hand_off.main(args) == 1
    assert "there is no warehouse at" in capsys.readouterr().out
