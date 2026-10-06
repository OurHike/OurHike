"""extract/_warehouse.py's served copy: how the hourly build reads a notices leg's store (decision 61).

The notices legs write their store every 4 hours (extract-notices.yml), in
runs that may overlap the hourly job's (publish-conditions.yml), and a
`replace` load deletes a table's files before it writes the new ones. So a
notices run that has committed copies what a build reads of it, write-once,
under `<bucket-url>/served/<run_id>/` (write_served_copy()), and the hourly
build reads the newest finished copy beside its own conditions leg's tables
(load_served()). These hold that a read never depends on the store's own
files, that a copy which will not verify falls back to the one before with
its last good rows, that a table the store left torn is carried rather than
holding back the rest, that only the leg's job's tables cross, and the
command line's exits. Everything runs against a `file://` raw store under
tmp_path, under conftest.py's socket guard.
"""

from __future__ import annotations

import json
import os
import re
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path

import duckdb
import pyarrow.parquet as pq
import pytest

from extract import _contract, _run, _warehouse
from extract._run import committed_load_ids, kept_log, make_pipeline, run_log_rows, run_pipeline, table_files
from extract._warehouse import (
    SERVED_KEEP,
    SERVED_MANIFEST,
    SERVED_NONE_EXIT,
    SERVED_OLDER_EXIT,
    BuildRefused,
    load_served,
    load_warehouse,
    served_copies,
    served_root,
    write_served_copy,
)
from tests.test_extract_conditions_legs import club_closures, nynjtc_alerts, ourhike_closures

LEG = "notices_ua"


@pytest.fixture
def stores(tmp_path):
    return {
        "notices": (tmp_path / "notices-store").as_uri(),
        "conditions": (tmp_path / "conditions-store").as_uri(),
        "dir": str(tmp_path / "pipelines"),
    }


def notices_run(stores, *resources):
    return run_pipeline(LEG, stores["notices"], resources=list(resources), pipelines_dir=stores["dir"])


def notices_pipeline(stores):
    return make_pipeline(LEG, stores["notices"], stores["dir"])


def serve(stores, tables):
    return write_served_copy(notices_pipeline(stores), stores["notices"], set(tables))


def hourly_warehouse(stores, path: Path, tables) -> _warehouse.ServedRead:
    """What publish-conditions.yml's dbt path does: the conditions leg's run and its warehouse, then the served copy."""
    conditions = run_pipeline(
        "conditions_ua",
        stores["conditions"],
        resources=[ourhike_closures("o1", count=1), nynjtc_alerts("n1", count=1)],
        pipelines_dir=stores["dir"],
    )
    with duckdb.connect(str(path)) as con:
        load_warehouse(con, make_pipeline("conditions_ua", stores["conditions"], stores["dir"]), log=conditions.run_log)
        return load_served(con, notices_pipeline(stores), stores["notices"], set(tables), sleep=lambda seconds: None)


def ids(path: Path) -> dict[str, list[str]]:
    with duckdb.connect(str(path), read_only=True) as con:
        tables = [
            name
            for (name,) in con.execute(
                "select table_name from information_schema.tables where table_schema = 'raw' and table_name <> '_extract_runs'"
            ).fetchall()
        ]
        return {table: sorted(i for (i,) in con.execute(f'select id from raw."{table}"').fetchall()) for table in tables}


def store_files(url: str) -> dict[str, float]:
    root = _warehouse.fs_path(url)
    return {
        os.path.join(folder, name): os.path.getmtime(os.path.join(folder, name))
        for folder, _, names in os.walk(root)
        for name in names
        if f"{os.sep}served{os.sep}" not in os.path.join(folder, name)
    }


USFS, NPS = club_closures("usfs", "u1", "u2", count=2), club_closures("nps", "p1", count=1)
TABLES = (USFS.table, NPS.table)


def test_the_hourly_warehouse_holds_its_own_tables_and_the_notices_copy_and_both_run_logs(stores, tmp_path):
    notices_run(stores, USFS, NPS)
    written = serve(stores, TABLES)
    assert written.wrote and not written.problems
    assert set(written.manifest["tables"]) == set(TABLES)

    read = hourly_warehouse(stores, tmp_path / "warehouse.duckdb", TABLES)

    assert read.newest and read.run_id == written.manifest["run_id"] and read.loaded == {USFS.table: 2, NPS.table: 1}
    assert ids(tmp_path / "warehouse.duckdb") == {
        "raw_ourhike__closures": ["o1"],
        "raw_nynjtc__nynjtc_trail_alerts": ["n1"],
        USFS.table: ["u1", "u2"],
        NPS.table: ["p1"],
    }
    with duckdb.connect(str(tmp_path / "warehouse.duckdb"), read_only=True) as con:
        logged = con.execute("select pipeline, table_name from raw._extract_runs order by 1, 2").fetchall()
        types = dict(
            con.execute(
                "select column_name, data_type from information_schema.columns where table_name = '_extract_runs'"
            ).fetchall()
        )
    assert logged == [
        ("conditions_ua", "raw_nynjtc__nynjtc_trail_alerts"),
        ("conditions_ua", "raw_ourhike__closures"),
        ("notices_ua", NPS.table),
        ("notices_ua", USFS.table),
    ]
    assert types["column_hints"] == "VARCHAR" and types["rows"] == "BIGINT" and types["checked_at"] == "TIMESTAMP WITH TIME ZONE"


def test_a_copy_is_write_once_and_reading_it_writes_nothing_to_the_store(stores, tmp_path):
    notices_run(stores, USFS)
    first = serve(stores, TABLES)
    before = store_files(stores["notices"])
    copy = Path(served_root(stores["notices"])) / first.manifest["run_id"]
    copied = {path: path.stat().st_mtime for path in copy.rglob("*")}

    again = serve(stores, TABLES)
    hourly_warehouse(stores, tmp_path / "warehouse.duckdb", TABLES)

    assert not again.wrote and again.manifest == first.manifest
    assert {path: path.stat().st_mtime for path in copy.rglob("*")} == copied
    assert store_files(stores["notices"]) == before, "the hourly read is read-only on the notices store"


def test_a_notices_load_in_flight_cannot_tear_the_hourly_read(stores, tmp_path):
    """A `replace` load deletes the table's files before it writes the new ones; the copy never reads them."""
    notices_run(stores, USFS)
    serve(stores, TABLES)
    for path in table_files(notices_pipeline(stores), USFS.table):
        os.remove(path)

    read = hourly_warehouse(stores, tmp_path / "warehouse.duckdb", TABLES)

    assert read.newest and ids(tmp_path / "warehouse.duckdb")[USFS.table] == ["u1", "u2"]


def test_a_newest_copy_that_will_not_verify_falls_back_to_the_last_good_one_after_its_retries(stores, tmp_path):
    notices_run(stores, USFS)
    good = serve(stores, TABLES).manifest["run_id"]
    notices_run(stores, club_closures("usfs", "u1", "u2", "u3", count=3))
    newest = serve(stores, TABLES).manifest
    broken = Path(served_root(stores["notices"])) / newest["run_id"] / newest["tables"][USFS.table]["file"]
    broken.write_bytes(b"not the bytes the manifest hashed")
    waits = []

    with duckdb.connect(str(tmp_path / "warehouse.duckdb")) as con:
        read = load_served(con, notices_pipeline(stores), stores["notices"], set(TABLES), sleep=waits.append)

    assert (read.run_id, read.newest) == (good, False)
    assert waits == [_warehouse.SERVED_WAIT_SECONDS] * (_warehouse.SERVED_ATTEMPTS - 1), "the newest is retried first"
    assert len(read.problems) == _warehouse.SERVED_ATTEMPTS and "sha256" in read.problems[0]
    assert ids(tmp_path / "warehouse.duckdb")[USFS.table] == ["u1", "u2"], "its last good rows, never an empty table"


def test_copies_that_exist_and_none_of_which_reads_refuse_and_write_nothing(stores, tmp_path):
    notices_run(stores, USFS)
    manifest = serve(stores, TABLES).manifest
    (Path(served_root(stores["notices"])) / manifest["run_id"] / manifest["tables"][USFS.table]["file"]).unlink()

    with duckdb.connect(str(tmp_path / "warehouse.duckdb")) as con:
        with pytest.raises(BuildRefused, match="no served copy could be read"):
            load_served(con, notices_pipeline(stores), stores["notices"], set(TABLES), sleep=lambda seconds: None)
        assert con.execute("select count(*) from information_schema.tables where table_schema = 'raw'").fetchone() == (0,)


def test_a_store_with_no_copy_yet_says_so_and_loads_nothing(stores, tmp_path):
    notices_run(stores, USFS)

    read = hourly_warehouse(stores, tmp_path / "warehouse.duckdb", TABLES)

    assert read.run_id is None and read.loaded == {}
    assert USFS.table not in ids(tmp_path / "warehouse.duckdb")


def test_only_the_legs_jobs_tables_cross_and_a_not_yet_loaded_one_is_empty_with_its_hints(stores, tmp_path):
    notices_run(stores, USFS, club_closures("nps", error="NPS answered 500"))
    written = serve(stores, TABLES)
    assert written.manifest["tables"][NPS.table]["not_yet_loaded"] is True

    read = hourly_warehouse(stores, tmp_path / "warehouse.duckdb", {USFS.table, NPS.table, "raw_never__closures"})
    assert read.loaded == {USFS.table: 2, NPS.table: 0}

    with duckdb.connect(str(tmp_path / "other.duckdb")) as con:
        only = load_served(con, notices_pipeline(stores), stores["notices"], {NPS.table}, sleep=lambda seconds: None)
        logged = {name for (name,) in con.execute("select distinct table_name from raw._extract_runs").fetchall()}
    assert only.loaded == {NPS.table: 0} and logged == {NPS.table}


def test_a_copy_made_eight_tables_at_a_time_is_the_copy_made_one_at_a_time(stores, monkeypatch):
    """extract-notices.yml run 8 (2026-10-05) passed its copy step's 5 minutes copying 261 tables one at a time, so
    no copy was served. They are copied SERVE_COPIERS at once now, a torn one among them, and the copy is the same."""
    clubs = [club_closures(f"club{n}", f"c{n}a", f"c{n}b", count=2) for n in range(12)]
    notices_run(stores, *clubs)
    before = serve(stores, [club.table for club in clubs]).manifest["run_id"]
    notices_run(stores, *[club_closures(f"club{n}", f"c{n}a", f"c{n}b", f"c{n}c", count=3) for n in range(12)])
    for path in table_files(notices_pipeline(stores), clubs[5].table):
        os.remove(path)
    monkeypatch.setattr(_warehouse, "SERVE_COPIERS", 1)
    one = serve(stores, [club.table for club in clubs])
    shutil.rmtree(_warehouse.fs_path(f"{served_root(stores['notices'])}/{one.manifest['run_id']}"))
    monkeypatch.setattr(_warehouse, "SERVE_COPIERS", 8)

    eight = serve(stores, [club.table for club in clubs])

    assert eight.wrote and eight.problems == one.problems
    assert {k: v for k, v in eight.manifest.items() if k != "written_at"} == {
        k: v for k, v in one.manifest.items() if k != "written_at"
    }
    assert eight.manifest["tables"][clubs[5].table]["carried_from"] == before
    assert [eight.manifest["tables"][club.table]["rows"] for club in clubs] == [3] * 5 + [2] + [3] * 6


def test_a_table_the_store_left_torn_is_carried_from_the_copy_before_and_the_rest_still_serve(stores):
    """A run killed between its load and its run log leaves a logged load whose files are gone."""
    notices_run(stores, USFS, NPS)
    before = serve(stores, TABLES).manifest["run_id"]
    notices_run(stores, club_closures("usfs", "u1", "u2", "u3", count=3), club_closures("nps", "p1", "p2", count=2))
    for path in table_files(notices_pipeline(stores), USFS.table):
        os.remove(path)

    written = serve(stores, TABLES)

    entry = written.manifest["tables"][USFS.table]
    assert entry["carried_from"] == before and entry["rows"] == 2
    assert written.manifest["tables"][NPS.table]["rows"] == 2, "the other club's new rows still serve"
    (problem,) = written.problems
    assert USFS.table in problem and "carried from copy" in problem


def logged_runs(path: Path, table: str) -> list[tuple[str, str, int | None]]:
    with duckdb.connect(str(path), read_only=True) as con:
        return con.execute(
            "select run_id, outcome, rows from raw._extract_runs where pipeline = ? and table_name = ? order by run_id",
            [LEG, table],
        ).fetchall()


def test_a_carried_tables_run_log_rows_are_those_of_the_copy_its_rows_came_from(stores, tmp_path):
    """A copy used to carry run 1's 2 rows while its run log still said run 2 loaded 3, so the hourly build would
    date run 1's rows by run 2's read. Twice torn, the rows and their log still agree."""
    first = notices_run(stores, USFS, NPS)
    serve(stores, TABLES)
    second = notices_run(stores, club_closures("usfs", "u1", "u2", "u3", count=3), club_closures("nps", "p1", "p2", count=2))
    for path in table_files(notices_pipeline(stores), USFS.table):
        os.remove(path)
    assert serve(stores, TABLES).manifest["tables"][USFS.table]["rows"] == 2, "carried"

    hourly_warehouse(stores, tmp_path / "warehouse.duckdb", TABLES)

    assert logged_runs(tmp_path / "warehouse.duckdb", USFS.table) == [(first.run_id, "loaded", 2)]
    # NPS was not carried, so its rows are the leg's kept log's (extract/_run.py's KEPT_LOG_TABLE): its latest
    # committed load and after, which is all a reader of the run log answers from.
    assert logged_runs(tmp_path / "warehouse.duckdb", NPS.table) == [(second.run_id, "loaded", 2)]

    notices_run(stores, club_closures("usfs", "u1", "u2", "u3", "u4", count=4), NPS)
    for path in table_files(notices_pipeline(stores), USFS.table):
        os.remove(path)
    assert serve(stores, TABLES).manifest["tables"][USFS.table]["rows"] == 2, "carried from a copy that carried it"

    hourly_warehouse(stores, tmp_path / "again.duckdb", TABLES)

    assert logged_runs(tmp_path / "again.duckdb", USFS.table) == [(first.run_id, "loaded", 2)]


def test_a_torn_table_with_no_copy_before_is_left_out_and_named(stores):
    notices_run(stores, USFS, NPS)
    for path in table_files(notices_pipeline(stores), USFS.table):
        os.remove(path)

    written = serve(stores, TABLES)

    assert set(written.manifest["tables"]) == {NPS.table}
    (problem,) = written.problems
    assert USFS.table in problem and "left out" in problem
    copy = Path(served_root(stores["notices"])) / written.manifest["run_id"]
    logged = set(pq.read_table(copy / written.manifest["extract_runs"]["file"])["table_name"].to_pylist())
    assert logged == {NPS.table}, "no run log row says a load of the table left out is here"


def test_each_write_keeps_the_newest_copies_and_clears_an_unfinished_one(stores):
    unfinished = Path(served_root(stores["notices"])) / "20000101T000000.000000Z"
    unfinished.mkdir(parents=True)
    (unfinished / "tables").mkdir()
    written = []
    for run in range(SERVED_KEEP + 2):
        notices_run(stores, club_closures("usfs", *(f"u{n}" for n in range(run + 1)), count=run + 1))
        written.append(serve(stores, TABLES).manifest["run_id"])

    fs = _warehouse._client(notices_pipeline(stores)).fs_client
    assert served_copies(fs, stores["notices"]) == sorted(written, reverse=True)[:SERVED_KEEP]
    assert sorted(path.name for path in Path(served_root(stores["notices"])).iterdir()) == sorted(written)[-SERVED_KEEP:]


def test_a_copy_holds_the_run_log_rows_of_its_tables_with_their_types(stores):
    notices_run(stores, USFS)
    manifest = serve(stores, TABLES).manifest
    copy = Path(served_root(stores["notices"])) / manifest["run_id"]

    log = run_log_rows(notices_pipeline(stores))
    served = pq.read_table(copy / manifest["extract_runs"]["file"])
    assert served.num_rows == manifest["extract_runs"]["rows"] == len(log)
    assert str(served.schema.field("column_hints").type) == "string", "a column null on a row keeps dlt's type"
    assert json.loads((copy / SERVED_MANIFEST).read_text())["run_id"] == max(row["run_id"] for row in log)


@pytest.fixture
def command(stores, monkeypatch):
    """_warehouse.main, discovering the two clubs' notices and a conditions table as the leg's whole world."""
    resources = [USFS, NPS, ourhike_closures("o1", count=1)]
    monkeypatch.setattr(_contract, "discover", list)
    monkeypatch.setattr(_contract, "discover_shared", list)
    monkeypatch.setattr(_contract, "all_resources", lambda files: resources)
    monkeypatch.setattr(_warehouse.time, "sleep", lambda seconds: None)

    def run(*args):
        return _warehouse.main([*args, "--lane", LEG, "--bucket-url", stores["notices"], "--pipelines-dir", stores["dir"]])

    return run


def test_the_command_line_serves_then_adds_the_newest_copy(stores, command, tmp_path):
    notices_run(stores, USFS, NPS)
    summary = tmp_path / "summary.md"

    assert command("serve", "--summary", str(summary)) == 0
    assert command("add-served", "--warehouse", str(tmp_path / "warehouse.duckdb"), "--summary", str(summary)) == 0

    assert ids(tmp_path / "warehouse.duckdb") == {USFS.table: ["u1", "u2"], NPS.table: ["p1"]}
    text = summary.read_text()
    assert "### The served copy: `notices_ua`" in text and "the newest: 2 tables, 3 rows." in text


def test_the_command_line_says_when_no_copy_exists_and_when_an_older_one_was_read(stores, command, tmp_path):
    notices_run(stores, USFS)
    assert command("add-served", "--warehouse", str(tmp_path / "none.duckdb")) == SERVED_NONE_EXIT

    command("serve")
    notices_run(stores, club_closures("usfs", "u1", "u2", "u3", count=3))
    command("serve")
    (newest,) = served_copies(_warehouse._client(notices_pipeline(stores)).fs_client, stores["notices"])[:1]
    manifest = json.loads((Path(served_root(stores["notices"])) / newest / SERVED_MANIFEST).read_text())
    (Path(served_root(stores["notices"])) / newest / manifest["tables"][USFS.table]["file"]).write_bytes(b"torn")

    assert command("add-served", "--warehouse", str(tmp_path / "older.duckdb")) == SERVED_OLDER_EXIT
    assert ids(tmp_path / "older.duckdb")[USFS.table] == ["u1", "u2"]


def test_a_notices_run_and_its_serve_read_each_run_log_file_from_the_store_once_between_them(
    stores, command, tmp_path, monkeypatch
):
    """Every `_extract_runs` file is a GET on R2, one file per past run, and the serve step used to read them all
    again right after the extract step had. extract-notices.yml hands the serve the extract's read through
    --run-log-cache, so a notices run reads its run log from the store once. And a leg reads only its kept log and the
    files after it (review finding PY-5 of PR #1805 — dlt → dbt re-platform as one go/no-go change; KEPT_LOG_TABLE), so
    of `_extract_runs` the sixth run reads only the file it wrote, and the copy holds the kept log's rows."""
    import fsspec.implementations.local as local

    resources = [USFS, NPS]
    monkeypatch.setattr(_run, "discover", list)
    monkeypatch.setattr(_run, "discover_shared", list)
    monkeypatch.setattr(_run, "all_resources", lambda files: resources)
    extract = ["--lane", LEG, "--bucket-url", stores["notices"], "--pipelines-dir", stores["dir"]]
    for _ in range(5):
        _run.main(extract)
    cache = str(tmp_path / "run_log")
    opened = []
    first_open = local.LocalFileSystem._open

    def counting_open(self, path, mode="rb", *rest, **options):
        if "r" in mode and "/_extract_runs/" in str(path) and "/served/" not in str(path):
            opened.append(os.path.basename(str(path)))
        return first_open(self, path, mode, *rest, **options)

    monkeypatch.setattr(local.LocalFileSystem, "_open", counting_open)

    _run.main([*extract, "--run-log-cache", cache])
    assert command("serve", "--run-log-cache", cache) == 0

    assert len(opened) == len(set(opened)) == 1, "the run log file the sixth run wrote, read from the store once"
    copy = (
        Path(served_root(stores["notices"]))
        / served_copies(_warehouse._client(notices_pipeline(stores)).fs_client, stores["notices"])[0]
    )
    pipeline = notices_pipeline(stores)
    kept = kept_log(run_log_rows(pipeline), committed_load_ids(pipeline))
    assert pq.read_table(copy / "_extract_runs.parquet").num_rows == len(kept) < len(run_log_rows(pipeline))


def test_the_command_line_serve_exits_partial_when_a_table_was_not_copied_whole(stores, command):
    notices_run(stores, USFS, NPS)
    for path in table_files(notices_pipeline(stores), USFS.table):
        os.remove(path)

    assert command("serve") == _warehouse.PARTIAL_EXIT


def notices_run_hours_ago(stores, monkeypatch, hours: float, *resources):
    """A notices run whose clock read `hours` before now, so its run id and every run log row it writes are that old."""
    then = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=hours)
    with monkeypatch.context() as patched:
        patched.setattr(_run, "utc_now_naive", lambda: then)
        return notices_run(stores, *resources)


def test_add_served_still_adds_a_notices_copy_whose_run_began_9_hours_ago_but_exits_stale(
    stores, command, tmp_path, monkeypatch, capsys
):
    """A copy of any age used to read as the newest and leave the run green; soak run 538 read one 3 h 01 min old.
    Past SERVED_STALE_HOURS the copy is still added, so the build still publishes, and the exit says it is stale,
    so publish-conditions.yml turns the run red at the end."""
    report = notices_run_hours_ago(stores, monkeypatch, 9, USFS, NPS)
    assert command("serve") == 0
    capsys.readouterr()

    status = command("add-served", "--warehouse", str(tmp_path / "warehouse.duckdb"))

    assert status != 0, "a copy whose run began 9 hours ago was read as the newest, and the run stayed green"
    assert status == _warehouse.SERVED_STALE_EXIT
    assert ids(tmp_path / "warehouse.duckdb") == {USFS.table: ["u1", "u2"], NPS.table: ["p1"]}, "still added"
    out = capsys.readouterr().out
    assert re.search(rf"copy {report.run_id}, whose run began 9 h \d\d min before this read", out), out
    assert "::error title=The notices copy is stale::" in out


def test_add_served_reads_a_notices_copy_under_8_hours_old_as_the_newest_and_says_its_age(
    stores, command, tmp_path, monkeypatch, capsys
):
    report = notices_run_hours_ago(stores, monkeypatch, 7.5, USFS)
    command("serve")
    summary = tmp_path / "summary.md"
    capsys.readouterr()

    assert command("add-served", "--warehouse", str(tmp_path / "warehouse.duckdb"), "--summary", str(summary)) == 0

    assert re.search(rf"copy {report.run_id}, whose run began 7 h \d\d min before this read", capsys.readouterr().out)
    assert re.search(r"Its run began `\S+Z`, 7 h \d\d min before this read\.", summary.read_text())


def test_add_served_hands_dbt_the_instant_its_copys_run_began_and_nothing_when_no_copy_was_read(stores, command, tmp_path):
    """The copy's run time, for pub_conditions_notices to write as `notices_read_at`: the instant every run log row of
    that run carries as `checked_at`, appended to the file publish-conditions.yml names as $GITHUB_ENV."""
    env_file = tmp_path / "github_env"
    report = notices_run(stores, USFS)
    assert command("add-served", "--warehouse", str(tmp_path / "none.duckdb"), "--env-file", str(env_file)) == SERVED_NONE_EXIT
    assert not env_file.exists(), "no copy read, so no read time: the build's notices_read_at is unknown"

    command("serve")
    assert command("add-served", "--warehouse", str(tmp_path / "warehouse.duckdb"), "--env-file", str(env_file)) == 0

    (line,) = env_file.read_text().splitlines()
    name, _, value = line.partition("=")
    assert name == _warehouse.NOTICES_READ_AT_ENV == "OURHIKE_NOTICES_READ_AT"
    (checked_at,) = {row["checked_at"] for row in run_log_rows(notices_pipeline(stores)) if row["run_id"] == report.run_id}
    assert datetime.fromisoformat(value) == checked_at.replace(tzinfo=UTC), "the copy's run, as its rows' checked_at"
