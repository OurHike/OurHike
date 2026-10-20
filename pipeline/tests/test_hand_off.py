"""hand_off.py: an hourly build's warehouse handed to the run that checks it, through the leg's history store.

Every test runs on a local directory standing in for the store, as tests/test_row_history.py does: Store reads and
writes a directory and an s3:// URL through the same methods.
"""

from __future__ import annotations

import gzip
import json
from datetime import UTC, datetime, timedelta

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


def test_a_later_builds_put_landing_while_take_downloads_is_nothing_to_check_rather_than_a_torn_upload(
    tmp_path, monkeypatch, capsys
):
    """check-conditions.yml shares no concurrency group with publish-conditions.yml any more (#1513 — A queued publish is
    silently cancelled when another one joins publish-data, and it looks like a green build), so the next build's put
    can land between a take's read of hand_off.json and its download: that hour is not checked, and nothing goes red."""
    store, taken = tmp_path / "store", tmp_path / "checks.duckdb"
    hand_off.put(str(store), _warehouse(tmp_path / "first.duckdb", rows=3), "7")
    real_get = hand_off.Store.get

    def get_after_a_later_put(self, relative, local, pointer=hand_off.POINTER):
        hand_off.put(str(store), _warehouse(tmp_path / "second.duckdb", rows=5), "8")
        real_get(self, relative, local, pointer)

    monkeypatch.setattr(hand_off.Store, "get", get_after_a_later_put)
    code = hand_off.main(["take", "--url", str(store), "--warehouse", str(taken), "--run", "7"])

    assert code == hand_off.NOT_HANDED_OFF
    assert "replaced run 7's while this take was downloading it" in capsys.readouterr().out
    assert not taken.exists(), "nothing of either build is left where the checks would read it"


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


# --- the hour's comparison bundle (hourly_parity.py), beside the warehouse ---------------------------------------


def _bundle(folder, marker="1"):
    (folder / "raw" / "conditions").mkdir(parents=True, exist_ok=True)
    (folder / "new").mkdir(parents=True, exist_ok=True)
    (folder / "raw" / "conditions" / "nws_alerts.json").write_text('{"type": "FeatureCollection", "features": []}')
    (folder / "new" / "conditions_closures.json").write_text(json.dumps({"generated_at": marker, "closures": []}))
    (folder / "bundle.json").write_text(json.dumps({"format": "ourhike-hourly-parity-bundle/1"}))
    return folder


def _files(folder):
    return {path.relative_to(folder).as_posix(): path.read_text() for path in folder.rglob("*") if path.is_file()}


def test_a_bundle_put_by_one_run_is_taken_by_that_runs_comparison_file_for_file(tmp_path):
    store, built, commit = tmp_path / "store", _bundle(tmp_path / "bundle"), "27f4ee3a" + "0" * 32

    put = hand_off.put_bundle(str(store), built, "37800000001", "2", commit=commit)
    taken = hand_off.take_bundle(str(store), tmp_path / "taken", "37800000001", commit=commit)

    assert _files(tmp_path / "taken") == _files(built), "every file, every character of its text"
    pointer = json.loads((store / hand_off.BUNDLE_POINTER).read_text())
    assert (pointer["run"], pointer["attempt"], pointer["files"]) == ("37800000001", "2", 3)
    assert "handed run 37800000001.2's comparison bundle, 3 files" in put
    assert "took run 37800000001.2's comparison bundle" in taken


def test_the_bundle_and_the_warehouse_keep_pointers_of_their_own_so_neither_take_reads_the_other(tmp_path):
    """The checks take the warehouse and never the bundle; the comparison the bundle and never the warehouse. A put of
    one leaves the other's pointer as it was, so a failed bundle can never cost the checks their hour."""
    store = tmp_path / "store"
    hand_off.put(str(store), _warehouse(tmp_path / "build.duckdb"), "7")
    warehouse_pointer = (store / hand_off.POINTER).read_text()

    hand_off.put_bundle(str(store), _bundle(tmp_path / "bundle"), "7")

    assert (store / hand_off.POINTER).read_text() == warehouse_pointer
    assert sorted(path.name for path in (store / hand_off.FOLDER).iterdir()) == [
        "hand_off.json",
        "parity_inputs.json",
        "parity_inputs.json.gz",
        "warehouse.duckdb.gz",
    ]
    hand_off.take(str(store), tmp_path / "checks.duckdb", "7")
    assert _closures(tmp_path / "checks.duckdb") == 3


def test_take_bundle_finds_nothing_for_another_run_or_commit_with_its_own_exit(tmp_path, capsys):
    store = tmp_path / "store"
    (store / hand_off.FOLDER).mkdir(parents=True)
    args = ["take-bundle", "--url", str(store), "--out", str(tmp_path / "taken"), "--run", "7"]

    assert hand_off.main(args) == hand_off.NOT_HANDED_OFF
    hand_off.put_bundle(str(store), _bundle(tmp_path / "bundle"), "8", commit="27f4ee3a" + "0" * 32)
    assert hand_off.main(args) == hand_off.NOT_HANDED_OFF
    assert "holds run 8's comparison bundle" in capsys.readouterr().out
    other = [*args[:-1], "8", "--commit", "fc32a8e6" + "0" * 32]
    assert hand_off.main(other) == hand_off.NOT_HANDED_OFF
    assert "not this checkout's fc32a8e60000" in capsys.readouterr().out
    assert not (tmp_path / "taken").exists()


def test_a_torn_bundle_is_a_warning_and_a_replaced_one_is_nothing_to_compare(tmp_path, monkeypatch, capsys):
    """Never the warehouse's ::error: a bundle that does not come back costs this hour its comparison and nothing else."""
    store = tmp_path / "store"
    hand_off.put_bundle(str(store), _bundle(tmp_path / "bundle"), "7")
    with (store / hand_off.BUNDLE).open("ab") as torn:
        torn.write(b"half of a later upload")
    args = ["take-bundle", "--url", str(store), "--out", str(tmp_path / "taken"), "--run", "7"]

    assert hand_off.main(args) == 1
    out = capsys.readouterr().out
    assert "::warning title=Comparison bundle not moved::" in out and "::error" not in out
    assert not (tmp_path / "taken").exists()

    hand_off.put_bundle(str(store), _bundle(tmp_path / "bundle"), "7")
    real_get = hand_off.Store.get

    def get_after_a_later_put(self, relative, local, pointer=hand_off.POINTER):
        hand_off.put_bundle(str(store), _bundle(tmp_path / "later", marker="2"), "8")
        real_get(self, relative, local, pointer)

    monkeypatch.setattr(hand_off.Store, "get", get_after_a_later_put)
    assert hand_off.main(args) == hand_off.NOT_HANDED_OFF
    assert "a later build replaced run 7's bundle" in capsys.readouterr().out


@pytest.mark.parametrize("name", ["../escape.json", "/etc/passwd", "raw/../../escape.json", "raw/a b.json"])
def test_a_bundle_path_that_is_absolute_or_climbs_out_is_refused_and_nothing_is_written(tmp_path, name):
    store = tmp_path / "store"
    hand_off.put_bundle(str(store), _bundle(tmp_path / "bundle"), "7")
    with gzip.open(store / hand_off.BUNDLE, "rb") as packed:
        document = json.loads(packed.read())
    document["files"][name] = "planted"
    with gzip.GzipFile(store / hand_off.BUNDLE, "wb", mtime=0) as packed:
        packed.write(json.dumps(document).encode())
    pointer = json.loads((store / hand_off.BUNDLE_POINTER).read_text())
    pointer["gzip_bytes"] = (store / hand_off.BUNDLE).stat().st_size
    pointer["gzip_sha256"] = hand_off._sha256(store / hand_off.BUNDLE)
    (store / hand_off.BUNDLE_POINTER).write_text(json.dumps(pointer))

    with pytest.raises(hand_off.Refused, match="not a path a bundle may carry"):
        hand_off.take_bundle(str(store), tmp_path / "taken", "7")
    assert not (tmp_path / "taken").exists() and not (tmp_path / "escape.json").exists()


def test_put_bundle_refuses_a_folder_holding_a_name_a_bundle_may_not_carry(tmp_path, capsys):
    built = _bundle(tmp_path / "bundle")
    (built / "raw" / "a name with spaces.json").write_text("{}")

    code = hand_off.main(["put-bundle", "--url", str(tmp_path / "store"), "--bundle", str(built), "--run", "7"])

    assert code == 1 and "is not a path a bundle may carry" in capsys.readouterr().out
    assert not (tmp_path / "store" / hand_off.BUNDLE_POINTER).exists()


# --- none in 2.5 h is red (the maintainer, 2026-10-15) -------------------


def _put_hours_ago(store, pointer_file, hours):
    """Rewrite the store's pointer as if its put landed `hours` ago."""
    pointer = json.loads((store / pointer_file).read_text())
    pointer["put_at"] = (datetime.now(UTC) - timedelta(hours=hours)).isoformat().replace("+00:00", "Z")
    (store / pointer_file).write_text(json.dumps(pointer))


@pytest.mark.parametrize(
    ("hours", "code"),
    [(1.1, hand_off.NOT_HANDED_OFF), (2.4, hand_off.NOT_HANDED_OFF), (2.6, hand_off.STALE), (30, hand_off.STALE)],
)
def test_another_runs_warehouse_is_a_warning_inside_the_age_limit_and_red_past_it(tmp_path, capsys, hours, code):
    """One hour without this run's warehouse is the checks' warning, as before; a store whose newest is older than
    check-conditions.yml's MAX_AGE_HOURS is a soak checking nothing, red."""
    store = tmp_path / "store"
    hand_off.put(str(store), _warehouse(tmp_path / "older.duckdb"), "6")
    _put_hours_ago(store, hand_off.POINTER, hours)
    args = ["take", "--url", str(store), "--warehouse", str(tmp_path / "checks.duckdb"), "--run", "7"]

    assert hand_off.main([*args, "--max-age-hours", "2.5"]) == code
    out = capsys.readouterr().out
    assert ("::error title=No warehouse handed off for over 2.5 h::" in out) == (code == hand_off.STALE)
    assert hand_off.main(args) == hand_off.NOT_HANDED_OFF, "without the limit, as before: a warning whatever its age"
    assert not (tmp_path / "checks.duckdb").exists()


@pytest.mark.parametrize(("hours", "code"), [(1.1, hand_off.NOT_HANDED_OFF), (2.6, hand_off.STALE)])
def test_another_runs_bundle_is_a_warning_inside_the_age_limit_and_red_past_it(tmp_path, capsys, hours, code):
    store = tmp_path / "store"
    hand_off.put_bundle(str(store), _bundle(tmp_path / "bundle"), "6")
    _put_hours_ago(store, hand_off.BUNDLE_POINTER, hours)
    args = ["take-bundle", "--url", str(store), "--out", str(tmp_path / "out"), "--run", "7", "--max-age-hours", "2.5"]

    assert hand_off.main(args) == code
    out = capsys.readouterr().out
    assert ("::error title=No comparison bundle handed off for over 2.5 h::" in out) == (code == hand_off.STALE)
    assert "::warning" not in out, "a stale store is the run's red, never also take-bundle's warning"


@pytest.mark.parametrize("command", ["take", "take-bundle"])
def test_a_store_that_holds_none_is_red_under_the_age_limit(tmp_path, capsys, command):
    store = tmp_path / "store"
    (store / hand_off.FOLDER).mkdir(parents=True)
    where = ["--warehouse", str(tmp_path / "checks.duckdb")] if command == "take" else ["--out", str(tmp_path / "out")]
    args = [command, "--url", str(store), *where, "--run", "7"]

    assert hand_off.main(args) == hand_off.NOT_HANDED_OFF
    assert hand_off.main([*args, "--max-age-hours", "2.5"]) == hand_off.STALE
    assert "it holds none" in capsys.readouterr().out


def test_this_runs_own_warehouse_from_another_commit_is_new_so_only_a_warning(tmp_path):
    """A push since the build: the store's newest is this hour's, so the soak is running, and nothing is red."""
    store = tmp_path / "store"
    hand_off.put(str(store), _warehouse(tmp_path / "build.duckdb"), "7", commit="27f4ee3a" + "0" * 32)
    args = ["take", "--url", str(store), "--warehouse", str(tmp_path / "checks.duckdb"), "--run", "7"]

    assert hand_off.main([*args, "--commit", "fc32a8e6" + "0" * 32, "--max-age-hours", "2.5"]) == hand_off.NOT_HANDED_OFF


def test_a_put_at_that_cannot_be_read_is_red_under_the_age_limit(capsys):
    nothing = hand_off.NotHandedOff("the store holds run 6's", put_at="yesterday afternoon")

    assert hand_off.nothing_or_stale(nothing, 2.5, "warehouse") == hand_off.STALE
    assert "put_at, 'yesterday afternoon', cannot be read" in capsys.readouterr().out


def test_the_age_limit_is_inclusive_to_the_second():
    now = datetime(2026, 10, 15, 4, 45, tzinfo=UTC)
    at = (now - timedelta(hours=2.5)).isoformat().replace("+00:00", "Z")

    assert hand_off.nothing_or_stale(hand_off.NotHandedOff("", put_at=at), 2.5, "warehouse", now) == hand_off.NOT_HANDED_OFF
    later = now + timedelta(seconds=1)
    assert hand_off.nothing_or_stale(hand_off.NotHandedOff("", put_at=at), 2.5, "warehouse", later) == hand_off.STALE
