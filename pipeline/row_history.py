"""row_history: keep the warehouse's row-history snapshots, and Elementary's history, between runs, outside the warehouse.

    python row_history.py restore --url URL --warehouse W [--cold-start] [--elementary-cold-start]
        [--elementary-on-failure fail|degrade]
    python row_history.py save --url URL --warehouse W [--keep-days N] [--elementary-on-failure fail|degrade]

build_marts.py runs `restore` before its first dbt command and `save` after
its last one has succeeded, so a failed build never saves. Everything else
about the snapshots is macros/row_history.sql's (pipeline/dbt/). Elementary's
history rides in the same two commands and the same store, beside the
snapshots and apart from them ("ELEMENTARY'S HISTORY", below).

WHY OUTSIDE THE WAREHOUSE. Each lane builds its warehouse from the raw pin on
a fresh runner, so the snapshot tables (int_<mart>__history, one per mart, in
the `intermediate` schema: decision 57) would start over every run, and every
mart row would read as first seen that day. GitHub's Actions cache evicts an entry not read for 7
days, and the monthly lane runs once a month, so the cache cannot hold them
either. So they are stored at a URL of their own: OURHIKE_HISTORY_URL, which
build_marts.py passes here.

THE STORE AT URL, a local directory, a file:// URL or s3://<bucket>/<prefix>:

    history.json                       the pointer, written last
    saves/<save_id>/<snapshot>.parquet  one folder per save, written once
    elementary.json                    Elementary's pointer ("ELEMENTARY'S HISTORY")
    elementary/<save_id>/<table>.parquet

history.json names the current save, the save before it, and for every
snapshot table its file, row count, sha256 and history start (its earliest
dbt_valid_from: a row first seen then was already upstream when history
began). The newest KEEP_SAVES folders are kept, so a save that recorded a bad
load can be undone by pointing history.json at the one before.

s3:// goes through s3fs, with the credentials the workflows already give the
raw store's key for dlt (DESTINATION__FILESYSTEM__CREDENTIALS__AWS_ACCESS_KEY_ID,
..._AWS_SECRET_ACCESS_KEY, ..._ENDPOINT_URL, ..._REGION_NAME) and
fixed_upload_size, which R2 needs (extract/_run.py's S3_KWARGS says how a
monthly run measured that). R2 itself is @unvalidated for this file: its
tests run on a local directory, and the first monthly or conditions run that
saves settles it.

EVERY FAILURE IS LOUD: an exit code of 1, or 2 for a refused cold start, a
message saying what to do, and nothing written to the store.

restore
  - history.json is absent and the run did not allow a cold start (exit 2).
    A silent cold start would date every row as first seen in this build.
    build_marts.py allows one only under --fixtures, for a store
    row_history_stores.toml does not list as started, or with
    --history-cold-start.
  - the store cannot be read at all (a credential, the network, a bucket that
    is not there). Never read as "no history".
  - a file history.json names is missing, or its sha256 or row count is not
    what history.json says.
save
  - this warehouse has no restore receipt: `restore` never ran against it,
    so what it holds is not the stored history plus one build.
  - the receipt names another URL than the one being saved to.
  - a snapshot table that was restored is gone, or holds fewer rows than were
    restored. dbt adds versions and sets dbt_valid_to; it never deletes one,
    so a smaller table means history was lost in this run.
  - history.json at the URL no longer names the save this warehouse restored:
    another run saved in between, and saving over it would drop its changes.
  - an upload fails: history.json is written last, so the previous save stays
    current.

WHAT NONE OF THIS CATCHES. A raw table that a failed load left empty is a
legitimate build to dbt, so its snapshot invalidates every key and the save
records it (ELT.md's eighth snapshot trap). The committed-load reads
(extract/_warehouse.py) are what keep a failed load out of the warehouse, and
KEEP_SAVES is the way back if one gets through.

ELEMENTARY'S HISTORY (decision 102, pipeline/ELT.md "Memory between runs").
Each lane builds its warehouse from nothing, so without it an anomaly check
would never see an earlier build and a schema check never an earlier column.
`restore` puts it into the warehouse's `elementary` schema before
build_marts.py's "Elementary's own tables", whose incremental models then add
this build to it rather than starting empty; `save` writes it out with the
snapshots. Its own pointer, elementary.json, and its own folders,
elementary/<save_id>/, so neither part's failure touches the other's pointer,
and a save by a row_history.py from before decision 102, which knows only
history.json and saves/, leaves it alone. Both parts of one `save` share its
save id.

FOUR OF ELEMENTARY'S TABLES ARE KEPT (KEPT), each read back by a check or by
the data-quality page, all Reasoned from Elementary 0.26.0's macros:
  - data_monitoring_metrics: every anomaly check's training set.
    get_anomaly_scores_query() reads its rows with bucket_end after the start
    of the check's days_back, and get_metric_buckets_min_and_max() reads which
    buckets are already there, so a check with a timestamp_column on a source
    computes only the missing ones and its last backfill_days.
  - schema_columns_snapshot: schema_changes compares a table's columns with
    the rows at that table's latest detected_at, and only those
    (get_columns_snapshot_query(), get_columns_changes_from_last_run_query()).
  - elementary_test_results: one row per check per build. No check reads it
    back; the page does, for how long a check has warned and how many builds
    the history holds (decision 102's step 4).
  - dbt_invocations: one row per dbt command, which the results' invocation_id
    names, so the page can tell a build's checks run from its other commands.
Left out on purpose: dbt_run_results, read back only by
get_latest_full_refresh() for an incremental model, and this project has
none; test_result_rows, one build's failing rows and anomaly scores, because
no row leaves the warehouse (dbt_project.yml's test_sample_row_count);
dbt_source_freshness_results, which no check and no page reads; and the
tables describing the project itself, which "Elementary's own tables"
rebuilds every build.

ELEMENTARY REWRITES ITS RECENT METRIC BUCKETS. A check with a
timestamp_column computes buckets it already has again, every build: on a
source or an incremental model those of its last backfill_days (2 by
default), on any other model every bucket of its days_back
(get_metric_buckets_min_and_max(); measured 2026-10-08, the second of two
fixture builds rewrote all 14 daily buckets of a table's check). Each is
appended as a new row with the same `id` and a later `updated_at`, and its
readers keep the newest row of each id (row_number() over (partition by id
order by updated_at desc), get_anomaly_scores_query()). So
the row history's rule, never fewer rows than were restored, is the wrong
guard here: the warehouse table only grows, while the saved copy keeps one row
per id inside the window and so may hold fewer rows than were restored. The
guard is by key instead. `restore` records every restored row's KEPT key in
its receipt, and `save` refuses when one is gone from the warehouse: Elementary
only appends to these four tables (0.26.0's insert_data_monitoring_metrics(),
insert_schema_columns_snapshot() and insert_rows(), and the four models'
incremental runs select no row), and a rewrite keeps its key, so a missing key
is history lost in this build and never a rewrite. What the save writes is
then RETENTION's, and only that may shrink.

RETENTION, so the store stops growing. A save keeps, of each table:
  - data_monitoring_metrics: the newest row of each id (its readers' own
    order, so dropping the older rows changes nothing a check reads) whose
    bucket_end is inside --keep-days;
  - elementary_test_results and dbt_invocations: the rows whose detected_at
    or created_at is inside --keep-days;
  - schema_columns_snapshot: each table's latest snapshot whatever its age,
    the only one a schema check reads, and nothing older.
A row with no time at all is dropped: no check can place it in a window
(bucket_end after a start is never true of a null). build_marts.py passes
--keep-days per lane (its ELEMENTARY_KEEP_DAYS, the lane's training window
plus a margin); a save not told keeps ELEMENTARY_KEEP_DAYS, the longest, so
more, never less. WHAT BOUNDS THE STORE: KEEP_SAVES Elementary saves, each at
most --keep-days of builds (a lane's rows per build, times its builds in the
window) plus one snapshot of every table the lane has ever checked. The
pointer records each file's bytes, so every save says its size.

THE COLD START. An absent elementary.json is a cold start only when allowed:
with --cold-start (a store that may start its row history may start
Elementary's), or --elementary-cold-start, which build_marts.py passes for a
store row_history_stores.toml's [elementary_started] does not list. Every
store saved before decision 102 holds a history.json and no elementary.json,
and that is Elementary's first build there, not a loss. Once a store is
listed, an absent elementary.json is refused (exit 2) as lost history.

ITS FAILURES ARE THE ROW HISTORY'S, and one more thing the conditions legs
need. Under the default --elementary-on-failure fail, a failure of
Elementary's part fails the command as a whole, exit 1 (2 for a refused cold
start), with no receipt left and nothing written, which stops the monthly
lane before dbt runs or before its release, as the row history does. Under
degrade, which build_marts.py passes with --history-on-failure degrade, the
row history's part still restores or saves, and Elementary's restores nothing
(its kept tables are dropped, so its checks see no earlier build rather than
part of one) or saves nothing (elementary.json keeps naming the last good
save, so a passing failure heals on the next run); a ::error says which, and
the command exits ELEMENTARY_DEGRADED_EXIT (3). build_marts.py then builds and
publishes as usual and goes red after (PARTIAL_EXIT), so a failure of
Elementary's history never nulls a hiker's row dates. A save after a restore
that degraded saves the row history alone and exits 0: the restore already
said so.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import unquote, urlsplit

import duckdb

#: The warehouse schema dbt's snapshots are built in (dbt_project.yml's `snapshots: +schema`), which they share
#: with the intermediate models, so a snapshot table is the one whose name ends in SUFFIX (int_<mart>__history).
#: Nothing else in the schema is restored, dropped or saved.
SCHEMA = "intermediate"
SUFFIX = "__history"
#: Where restore leaves its receipt in the warehouse, which save reads back. Not SCHEMA, so the receipt is
#: never saved as if it were a snapshot.
RECEIPT_SCHEMA = "row_history"
RECEIPT_TABLE = "restored"
POINTER = "history.json"
SAVES = "saves"
FORMAT = 1
#: How many save folders stay in the store, the current one included. @unvalidated: two years of monthly saves
#: and a day of hourly ones, a round number. How long a bad load goes unnoticed before someone points
#: history.json back, which nobody has measured, would settle it. Elementary's folders keep the same number.
KEEP_SAVES = 24

#: Elementary's schema in the warehouse: dbt_project.yml's `elementary: +schema`, which macros/generate_schema_name.sql
#: keeps as it is. Only KEPT's tables in it are restored, dropped or saved.
ELEMENTARY_SCHEMA = "elementary"
ELEMENTARY_POINTER = "elementary.json"
#: Elementary's save folders, apart from SAVES (the module docstring, "ELEMENTARY'S HISTORY").
ELEMENTARY_SAVES = "elementary"
ELEMENTARY_FORMAT = 1
#: The receipt of Elementary's part, beside RECEIPT_TABLE: one row per restored table, and every restored row's key.
ELEMENTARY_RECEIPT = "elementary_restored"
ELEMENTARY_KEYS = "elementary_restored_keys"
#: What ELEMENTARY_RECEIPT says the restore did with Elementary's history.
RESTORED, COLD_START, NOT_RESTORED = "restored", "cold start", "not restored"
#: The exit of a command under --elementary-on-failure degrade whose row-history part passed and whose Elementary part
#: did not (the module docstring, "ITS FAILURES ARE THE ROW HISTORY'S"). build_marts.py's ELEMENTARY_DEGRADED_EXIT.
ELEMENTARY_DEGRADED_EXIT = 3
ELEMENTARY_ON_FAILURE = ("fail", "degrade")
#: How many days of Elementary's history a save keeps when it is not told: the longest build_marts.py's
#: ELEMENTARY_KEEP_DAYS gives any lane (tests/test_row_history.py holds the two equal), so a save keeps more, never less.
ELEMENTARY_KEEP_DAYS = 430


@dataclass(frozen=True)
class Kept:
    """One of Elementary's tables kept between builds (the module docstring, "FOUR OF ELEMENTARY'S TABLES ARE KEPT")."""

    #: SQL over the table's columns naming one row across builds, which a rewrite keeps.
    key: str
    #: What a save keeps (the module docstring, "RETENTION"): a query over {table}, {cutoff} the oldest instant kept.
    keep: str
    #: The column the pointer gives the oldest and newest of.
    at: str


KEPT: dict[str, Kept] = {
    "data_monitoring_metrics": Kept(
        key="id",
        keep="select * from {table} where bucket_end > {cutoff} qualify id is null or row_number() over "
        "(partition by id order by updated_at desc nulls last, created_at desc nulls last) = 1",
        at="bucket_end",
    ),
    "schema_columns_snapshot": Kept(
        key="column_state_id || '|' || cast(detected_at as varchar)",
        keep="select * from {table} qualify detected_at = max(detected_at) over (partition by lower(full_table_name)) "
        "and row_number() over (partition by lower(full_table_name), column_state_id, detected_at "
        "order by created_at desc nulls last) = 1",
        at="detected_at",
    ),
    "elementary_test_results": Kept(
        key="id",
        keep="select * from {table} where detected_at > {cutoff} qualify id is null or row_number() over "
        "(partition by id order by created_at desc nulls last) = 1",
        at="detected_at",
    ),
    "dbt_invocations": Kept(
        key="invocation_id",
        keep="select * from {table} where created_at > {cutoff} qualify invocation_id is null or row_number() over "
        "(partition by invocation_id order by created_at desc nulls last) = 1",
        at="created_at",
    ),
}


class Refused(Exception):
    """A failure this file names, with what to do; exit 1."""

    title = "Row history refused"


class ColdStartRefused(Refused):
    """No history at the URL and no permission to start it; exit 2."""

    title = "Row history not restored"


class ElementaryRefused(Refused):
    """A failure of Elementary's part (the module docstring, "ELEMENTARY'S HISTORY"); exit 1, or 3 under degrade."""

    title = "Elementary's history refused"


class ElementaryColdStartRefused(ColdStartRefused):
    """No elementary.json at the URL and no permission to start Elementary's history; exit 2, or 3 under degrade."""

    title = "Elementary's history not restored"


class ElementaryDegraded(Exception):
    """Under --elementary-on-failure degrade, the row history's part passed and Elementary's did not; exit 3."""

    def __init__(self, done: str, failure: str):
        super().__init__(failure)
        self.done = done
        self.failure = failure


class Store:
    """The files under one URL: a local directory, or a prefix in an S3 bucket."""

    def __init__(self, url: str):
        self.url = url.rstrip("/")
        parts = urlsplit(self.url)
        if parts.scheme in ("", "file"):
            self.fs = None
            self.root = unquote(parts.path) if parts.scheme == "file" else self.url
        elif parts.scheme == "s3":
            import s3fs

            env = os.environ.get
            prefix = "DESTINATION__FILESYSTEM__CREDENTIALS__"
            self.fs = s3fs.S3FileSystem(
                key=env(f"{prefix}AWS_ACCESS_KEY_ID"),
                secret=env(f"{prefix}AWS_SECRET_ACCESS_KEY"),
                endpoint_url=env(f"{prefix}ENDPOINT_URL"),
                client_kwargs={"region_name": env(f"{prefix}REGION_NAME") or "auto"},
                fixed_upload_size=True,
            )
            self.root = f"{parts.netloc}{unquote(parts.path)}".rstrip("/")
            self.bucket = parts.netloc
        else:
            raise Refused(f"{url}: a history store is a directory, a file:// URL or an s3:// URL")

    def _path(self, relative: str) -> str:
        return f"{self.root}/{relative}"

    def check_reachable(self) -> None:
        """Raise unless the store's bucket (or the local directory's parent) can be listed."""
        if self.fs is None:
            parent = Path(self.root).parent
            if not parent.is_dir():
                raise Refused(f"{self.url}: its parent directory {parent} does not exist")
            return
        try:
            self.fs.ls(self.bucket, detail=False)
        except Exception as error:  # noqa: BLE001 - any failure to list is the refusal
            raise Refused(f"{self.url}: the bucket {self.bucket} cannot be listed ({error!r})") from error

    def read_text(self, relative: str) -> str | None:
        """The file's text, or None when it does not exist. Any other failure raises."""
        if self.fs is None:
            path = Path(self._path(relative))
            return path.read_text(encoding="utf-8") if path.exists() else None
        try:
            return self.fs.cat_file(self._path(relative)).decode("utf-8")
        except FileNotFoundError:
            return None

    def write_text(self, relative: str, text: str) -> None:
        if self.fs is None:
            path = Path(self._path(relative))
            path.parent.mkdir(parents=True, exist_ok=True)
            partial = path.with_name(path.name + ".partial")
            partial.write_text(text, encoding="utf-8")
            partial.replace(path)
            return
        self.fs.pipe_file(self._path(relative), text.encode("utf-8"))

    def put(self, local: Path, relative: str) -> None:
        if self.fs is None:
            path = Path(self._path(relative))
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(local.read_bytes())
            return
        self.fs.put_file(str(local), self._path(relative))

    def get(self, relative: str, local: Path, pointer: str = POINTER) -> None:
        if self.fs is None:
            source = Path(self._path(relative))
            if not source.exists():
                raise Refused(f"{self.url}/{relative} is named by {pointer} and is not there")
            local.write_bytes(source.read_bytes())
            return
        try:
            self.fs.get_file(self._path(relative), str(local))
        except FileNotFoundError as error:
            raise Refused(f"{self.url}/{relative} is named by {pointer} and is not there") from error

    def save_folders(self, folder: str = SAVES) -> list[str]:
        if self.fs is None:
            path = Path(self._path(folder))
            return sorted(each.name for each in path.iterdir() if each.is_dir()) if path.is_dir() else []
        try:
            return sorted(each.rstrip("/").rsplit("/", 1)[-1] for each in self.fs.ls(self._path(folder), detail=False))
        except FileNotFoundError:
            return []

    def remove_save(self, save_id: str, folder: str = SAVES) -> None:
        if self.fs is None:
            path = Path(self._path(f"{folder}/{save_id}"))
            for each in path.iterdir():
                each.unlink()
            path.rmdir()
            return
        self.fs.rm(self._path(f"{folder}/{save_id}"), recursive=True)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def _quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _tables(con: duckdb.DuckDBPyConnection, schema: str) -> list[str]:
    rows = con.execute(
        "select table_name from information_schema.tables where table_schema = ? and table_type = 'BASE TABLE' "
        "order by table_name",
        [schema],
    ).fetchall()
    return [name for (name,) in rows]


def _snapshot_tables(con: duckdb.DuckDBPyConnection) -> list[str]:
    """The row-history snapshot tables: SCHEMA's tables named *SUFFIX, never the intermediate models beside them."""
    return [name for name in _tables(con, SCHEMA) if name.endswith(SUFFIX)]


def _kept_tables(con: duckdb.DuckDBPyConnection) -> list[str]:
    """KEPT's tables that are in the warehouse, never Elementary's other tables beside them."""
    return [name for name in _tables(con, ELEMENTARY_SCHEMA) if name in KEPT]


def _count(con: duckdb.DuckDBPyConnection, table: str, schema: str = SCHEMA) -> int:
    return con.execute(f"select count(*) from {schema}.{_quote(table)}").fetchone()[0]


def _instant(value: datetime | None) -> str | None:
    """A timestamp the warehouse holds in UTC without a zone, as the pointers write it."""
    return None if value is None else value.isoformat() + "Z"


def _history_start(con: duckdb.DuckDBPyConnection, table: str) -> str | None:
    return _instant(con.execute(f"select min(dbt_valid_from) from {SCHEMA}.{_quote(table)}").fetchone()[0])


def _new_save_id() -> str:
    # Sorted by name is sorted by time, which the pruning relies on: to the microsecond, so two saves in one second
    # (a test's, never a lane's) still sort in the order they were made. The suffix only keeps two machines' ids apart.
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ") + "-" + secrets.token_hex(3)


def _prune(store: Store, folder: str, save_id: str, kept: str | None) -> None:
    """Remove `folder`'s saves beyond the newest KEEP_SAVES, never this save or the one it was built on."""
    for old in store.save_folders(folder)[:-KEEP_SAVES]:
        if old not in (save_id, kept):
            store.remove_save(old, folder)


def _write_receipt(con: duckdb.DuckDBPyConnection, url: str, save_id: str | None, rows: dict[str, int]) -> None:
    con.execute(f"create schema if not exists {RECEIPT_SCHEMA}")
    con.execute(
        f"create or replace table {RECEIPT_SCHEMA}.{RECEIPT_TABLE} (url varchar, save_id varchar, table_name varchar, "
        "rows bigint)"
    )
    if rows:
        con.executemany(
            f"insert into {RECEIPT_SCHEMA}.{RECEIPT_TABLE} values (?, ?, ?, ?)",
            [(url, save_id, table, count) for table, count in sorted(rows.items())],
        )
    else:
        con.execute(f"insert into {RECEIPT_SCHEMA}.{RECEIPT_TABLE} values (?, ?, null, null)", [url, save_id])


def _write_elementary_receipt(
    con: duckdb.DuckDBPyConnection, url: str, save_id: str | None, status: str, rows: dict[str, int]
) -> None:
    """Every restored row's key first, then the one table save looks for, so a receipt is never half there."""
    con.execute(f"create schema if not exists {RECEIPT_SCHEMA}")
    con.execute(f"create or replace table {RECEIPT_SCHEMA}.{ELEMENTARY_KEYS} (table_name varchar, key varchar)")
    for table in sorted(rows):
        con.execute(
            f"insert into {RECEIPT_SCHEMA}.{ELEMENTARY_KEYS} select ?, {KEPT[table].key} "
            f"from {ELEMENTARY_SCHEMA}.{_quote(table)}",
            [table],
        )
    con.execute(
        f"create or replace table {RECEIPT_SCHEMA}.{ELEMENTARY_RECEIPT} (url varchar, save_id varchar, status varchar, "
        "table_name varchar, rows bigint)"
    )
    receipt = [(url, save_id, status, table, count) for table, count in sorted(rows.items())]
    con.executemany(
        f"insert into {RECEIPT_SCHEMA}.{ELEMENTARY_RECEIPT} values (?, ?, ?, ?, ?)",
        receipt or [(url, save_id, status, None, None)],
    )


def _drop_receipts(con: duckdb.DuckDBPyConnection) -> None:
    for table in (RECEIPT_TABLE, ELEMENTARY_RECEIPT, ELEMENTARY_KEYS):
        con.execute(f"drop table if exists {RECEIPT_SCHEMA}.{table}")


def _drop_kept(con: duckdb.DuckDBPyConnection) -> None:
    for table in _kept_tables(con):
        con.execute(f"drop table {ELEMENTARY_SCHEMA}.{_quote(table)}")


def _failure(error: Exception) -> str:
    return str(error) if isinstance(error, Refused) else f"{type(error).__name__}: {error}"


def _restore_rows(store: Store, url: str, con: duckdb.DuckDBPyConnection, cold_start: bool) -> tuple[str, str | None, dict]:
    """The snapshots into SCHEMA: what it did, the save it restored, and each table's rows. Writes no receipt."""
    text = store.read_text(POINTER)
    con.execute(f"create schema if not exists {SCHEMA}")
    for table in _snapshot_tables(con):
        con.execute(f"drop table {SCHEMA}.{_quote(table)}")
    if text is None:
        if not cold_start:
            raise ColdStartRefused(
                f"no {POINTER} at {url}: refusing to start the row history again, which would date every row as "
                "first seen in this build. If this store has never been saved to, run with a cold start allowed "
                "(build_marts.py --history-cold-start, or leave the store out of row_history_stores.toml); if it "
                "has, find out where its history went before running again."
            )
        return f"cold start: no {POINTER} at {url}, so every snapshot's history starts in this build", None, {}
    pointer = json.loads(text)
    if pointer.get("format") != FORMAT:
        raise Refused(f"{url}/{POINTER} is format {pointer.get('format')!r}; this file reads format {FORMAT}")
    restored = {}
    with tempfile.TemporaryDirectory() as scratch:
        for table, entry in sorted(pointer["tables"].items()):
            local = Path(scratch) / f"{table}.parquet"
            store.get(entry["file"], local)
            if (found := _sha256(local)) != entry["sha256"]:
                raise Refused(f"{url}/{entry['file']} has sha256 {found}, and {POINTER} says {entry['sha256']}")
            con.execute(f"create table {SCHEMA}.{_quote(table)} as select * from read_parquet(?)", [str(local)])
            if (rows := _count(con, table)) != entry["rows"]:
                raise Refused(f"{url}/{entry['file']} holds {rows} rows, and {POINTER} says {entry['rows']}")
            restored[table] = rows
    total = sum(restored.values())
    message = f"restored save {pointer['save_id']} from {url}: {len(restored)} snapshot tables, {total} rows"
    return message, pointer["save_id"], restored


def _restore_elementary(store: Store, url: str, con: duckdb.DuckDBPyConnection, cold_start: bool) -> str:
    """Elementary's kept tables into ELEMENTARY_SCHEMA, and its receipt. Returns what it did, for the log."""
    started = time.monotonic()
    _drop_kept(con)
    text = store.read_text(ELEMENTARY_POINTER)
    if text is None:
        if not cold_start:
            raise ElementaryColdStartRefused(
                f"no {ELEMENTARY_POINTER} at {url}: refusing to start Elementary's history again, which every anomaly "
                "check would answer by learning from nothing. If no run has saved Elementary's history here, leave the "
                "store out of row_history_stores.toml's [elementary_started] (or run build_marts.py "
                "--history-cold-start); if one has, find out where it went before running again."
            )
        _write_elementary_receipt(con, url, None, COLD_START, {})
        return f"Elementary's history: cold start: no {ELEMENTARY_POINTER} at {url}, so its checks see no earlier build"
    pointer = json.loads(text)
    if pointer.get("format") != ELEMENTARY_FORMAT:
        raise ElementaryRefused(
            f"{url}/{ELEMENTARY_POINTER} is format {pointer.get('format')!r}; this file reads format {ELEMENTARY_FORMAT}"
        )
    restored = {}
    # A table a later version of this file keeps and this one does not is left in the store, not restored.
    tables = sorted(name for name in pointer["tables"] if name in KEPT)
    if tables:
        con.execute(f"create schema if not exists {ELEMENTARY_SCHEMA}")
    with tempfile.TemporaryDirectory() as scratch:
        for table in tables:
            entry = pointer["tables"][table]
            local = Path(scratch) / f"{table}.parquet"
            store.get(entry["file"], local, ELEMENTARY_POINTER)
            if (found := _sha256(local)) != entry["sha256"]:
                raise ElementaryRefused(
                    f"{url}/{entry['file']} has sha256 {found}, and {ELEMENTARY_POINTER} says {entry['sha256']}"
                )
            con.execute(f"create table {ELEMENTARY_SCHEMA}.{_quote(table)} as select * from read_parquet(?)", [str(local)])
            if (rows := _count(con, table, ELEMENTARY_SCHEMA)) != entry["rows"]:
                raise ElementaryRefused(f"{url}/{entry['file']} holds {rows} rows, and {ELEMENTARY_POINTER} says {entry['rows']}")
            restored[table] = rows
    _write_elementary_receipt(con, url, pointer["save_id"], RESTORED, restored)
    each = ", ".join(f"{table} {rows}" for table, rows in sorted(restored.items())) or "no table"
    return (
        f"Elementary's history: restored save {pointer['save_id']} from {url}: {each} rows, in {time.monotonic() - started:.2f} s"
    )


def restore(
    url: str,
    warehouse: Path,
    cold_start: bool,
    elementary_cold_start: bool | None = None,
    elementary_on_failure: str = "fail",
) -> str:
    """Replace the warehouse's snapshot tables with the store's current save, and Elementary's kept tables with its
    current Elementary save (`elementary_cold_start` None: as `cold_start`). Returns what it did, for the log; raises
    ElementaryDegraded when Elementary's part failed under `elementary_on_failure` degrade."""
    if elementary_on_failure not in ELEMENTARY_ON_FAILURE:
        raise ValueError(f"elementary_on_failure is one of {ELEMENTARY_ON_FAILURE}, not {elementary_on_failure!r}")
    started = time.monotonic()
    store = Store(url)
    store.check_reachable()
    with duckdb.connect(str(warehouse)) as con:
        # No receipt until this restore has finished, so a restore that fails half-way cannot be saved.
        _drop_receipts(con)
        rows, save_id, restored = _restore_rows(store, url, con, cold_start)
        rows += f", in {time.monotonic() - started:.2f} s"
        try:
            elementary = _restore_elementary(
                store, url, con, cold_start if elementary_cold_start is None else elementary_cold_start
            )
        except Exception as error:  # noqa: BLE001 - every failure of Elementary's part is answered by the policy
            _drop_receipts(con)
            _drop_kept(con)
            if elementary_on_failure != "degrade":
                raise
            _write_receipt(con, url, save_id, restored)
            _write_elementary_receipt(con, url, None, NOT_RESTORED, {})
            raise ElementaryDegraded(
                rows,
                f"{_failure(error)}. The row history was restored; Elementary's history was not, so its checks see no "
                "earlier build in this run and none of it is saved, and the store keeps its last good save. Fix the "
                "store before the next run.",
            ) from error
        _write_receipt(con, url, save_id, restored)
    return f"{rows}\n{elementary}"


@dataclass(frozen=True)
class _RowsSave:
    tables: list[str]
    counts: dict[str, int]
    restored_save: str | None


@dataclass(frozen=True)
class _ElementarySave:
    tables: list[str]
    restored_save: str | None


def _check_rows_save(store: Store, url: str, con: duckdb.DuckDBPyConnection, warehouse: Path) -> _RowsSave:
    if RECEIPT_TABLE not in _tables(con, RECEIPT_SCHEMA):
        raise Refused(
            f"{warehouse} has no restore receipt ({RECEIPT_SCHEMA}.{RECEIPT_TABLE}): restore never ran against it, so "
            "its snapshots are not the stored history plus one build. Refusing to save them over it."
        )
    receipt = con.execute(f"select url, save_id, table_name, rows from {RECEIPT_SCHEMA}.{RECEIPT_TABLE}").fetchall()
    urls = {row[0] for row in receipt}
    if urls != {url}:
        raise Refused(f"this warehouse's history was restored from {sorted(urls)}, not {url}; refusing to save there")
    restored_save = receipt[0][1]
    restored = {table: rows for _, _, table, rows in receipt if table is not None}
    tables = _snapshot_tables(con)
    counts = {table: _count(con, table) for table in tables}
    if lost := sorted(set(restored) - set(counts)):
        raise Refused(f"snapshot tables restored and now gone: {', '.join(lost)}. History only grows; not saving")
    if shrank := sorted(t for t, rows in restored.items() if counts[t] < rows):
        detail = ", ".join(f"{t} {restored[t]} -> {counts[t]}" for t in shrank)
        raise Refused(f"snapshot tables with fewer rows than were restored: {detail}. History only grows; not saving")
    current = store.read_text(POINTER)
    current_save = json.loads(current)["save_id"] if current is not None else None
    if current_save != restored_save:
        raise Refused(
            f"{url}/{POINTER} names save {current_save}, and this warehouse restored {restored_save}: another run "
            "saved in between. Not saving over it; rerun to build on that save."
        )
    return _RowsSave(tables, counts, restored_save)


def _check_elementary_save(store: Store, url: str, con: duckdb.DuckDBPyConnection, warehouse: Path) -> _ElementarySave | None:
    """What Elementary's part will save, None when its restore restored nothing (the module docstring, "ITS FAILURES
    ARE THE ROW HISTORY'S"), or Refused (the module docstring, "ELEMENTARY REWRITES ITS RECENT METRIC BUCKETS")."""
    if ELEMENTARY_RECEIPT not in _tables(con, RECEIPT_SCHEMA):
        raise ElementaryRefused(
            f"{warehouse} has no restore receipt for Elementary's history ({RECEIPT_SCHEMA}.{ELEMENTARY_RECEIPT}): "
            "restore never ran against it, so its Elementary tables are not the stored history plus one build. "
            "Refusing to save them over it."
        )
    receipt = con.execute(f"select url, save_id, status, table_name, rows from {RECEIPT_SCHEMA}.{ELEMENTARY_RECEIPT}").fetchall()
    urls = {row[0] for row in receipt}
    if urls != {url}:
        raise ElementaryRefused(
            f"this warehouse's Elementary history was restored from {sorted(urls)}, not {url}; refusing to save there"
        )
    if receipt[0][2] == NOT_RESTORED:
        return None
    restored_save = receipt[0][1]
    restored = {table: rows for _, _, _, table, rows in receipt if table is not None}
    tables = _kept_tables(con)
    if gone := sorted(set(restored) - set(tables)):
        raise ElementaryRefused(
            f"Elementary tables restored and now gone: {', '.join(gone)}. Elementary only appends to them; not saving"
        )
    lost = {}
    for table in sorted(restored):
        (missing,) = con.execute(
            f"select count(*) from {RECEIPT_SCHEMA}.{ELEMENTARY_KEYS} as restored where restored.table_name = ? and "
            f"not exists (select 1 from {ELEMENTARY_SCHEMA}.{_quote(table)} as kept "
            f"where ({KEPT[table].key}) is not distinct from restored.key)",
            [table],
        ).fetchone()
        if missing:
            lost[table] = missing
    if lost:
        detail = ", ".join(f"{table} {missing} of {restored[table]}" for table, missing in sorted(lost.items()))
        raise ElementaryRefused(
            f"rows of Elementary's history restored and now gone from the warehouse: {detail}. Elementary only "
            "appends to these tables, and a rewritten metric bucket keeps its id, so these were lost in this run; "
            "not saving"
        )
    current = store.read_text(ELEMENTARY_POINTER)
    current_save = json.loads(current)["save_id"] if current is not None else None
    if current_save != restored_save:
        raise ElementaryRefused(
            f"{url}/{ELEMENTARY_POINTER} names save {current_save}, and this warehouse restored {restored_save}: "
            "another run saved Elementary's history in between. Not saving over it; rerun to build on that save."
        )
    return _ElementarySave(tables, restored_save)


def _write_rows(store: Store, url: str, con: duckdb.DuckDBPyConnection, plan: _RowsSave, save_id: str) -> str:
    started = time.monotonic()
    entries = {}
    with tempfile.TemporaryDirectory() as scratch:
        for table in plan.tables:
            local = Path(scratch) / f"{table}.parquet"
            con.execute(f"copy {SCHEMA}.{_quote(table)} to '{local}' (format parquet, compression zstd)")
            relative = f"{SAVES}/{save_id}/{table}.parquet"
            store.put(local, relative)
            entries[table] = {
                "file": relative,
                "rows": plan.counts[table],
                "sha256": _sha256(local),
                "history_started_at": _history_start(con, table),
            }
    pointer = {
        "format": FORMAT,
        "save_id": save_id,
        "saved_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "previous_save_id": plan.restored_save,
        "tables": entries,
    }
    store.write_text(POINTER, json.dumps(pointer, indent=2, sort_keys=True) + "\n")
    _prune(store, SAVES, save_id, plan.restored_save)
    return (
        f"saved {len(entries)} snapshot tables, {sum(plan.counts.values())} rows, to {url} as save {save_id}, "
        f"in {time.monotonic() - started:.2f} s"
    )


def _write_elementary(
    store: Store,
    url: str,
    con: duckdb.DuckDBPyConnection,
    plan: _ElementarySave,
    save_id: str,
    cutoff: datetime,
    keep_days: int,
) -> str:
    """Each kept table's RETENTION as zstd Parquet, then elementary.json. save() prunes once both pointers are written."""
    started = time.monotonic()
    literal = f"timestamp '{cutoff:%Y-%m-%d %H:%M:%S.%f}'"
    version = None
    if "metadata" in _tables(con, ELEMENTARY_SCHEMA):
        version = con.execute(f"select max(dbt_pkg_version) from {ELEMENTARY_SCHEMA}.metadata").fetchone()[0]
    entries = {}
    with tempfile.TemporaryDirectory() as scratch:
        for table in plan.tables:
            local = Path(scratch) / f"{table}.parquet"
            query = KEPT[table].keep.format(table=f"{ELEMENTARY_SCHEMA}.{_quote(table)}", cutoff=literal)
            con.execute(f"copy ({query}) to '{local}' (format parquet, compression zstd)")
            at = KEPT[table].at
            rows, oldest, newest = con.execute(
                f"select count(*), min({at}), max({at}) from read_parquet(?)", [str(local)]
            ).fetchone()
            relative = f"{ELEMENTARY_SAVES}/{save_id}/{table}.parquet"
            store.put(local, relative)
            entries[table] = {
                "file": relative,
                "rows": rows,
                "bytes": local.stat().st_size,
                "sha256": _sha256(local),
                "oldest": _instant(oldest),
                "newest": _instant(newest),
            }
    pointer = {
        "format": ELEMENTARY_FORMAT,
        "save_id": save_id,
        "saved_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "previous_save_id": plan.restored_save,
        "keep_days": keep_days,
        "kept_since": _instant(cutoff),
        "elementary_version": version,
        "tables": entries,
    }
    store.write_text(ELEMENTARY_POINTER, json.dumps(pointer, indent=2, sort_keys=True) + "\n")
    each = ", ".join(f"{table} {entry['rows']} ({entry['bytes']} bytes)" for table, entry in sorted(entries.items()))
    total = sum(entry["bytes"] for entry in entries.values())
    return (
        f"Elementary's history: saved {each or 'no table'}, {total} bytes in all, to {url} as save {save_id}, keeping "
        f"{keep_days} days (since {_instant(cutoff)}), in {time.monotonic() - started:.2f} s"
    )


def save(
    url: str,
    warehouse: Path,
    keep_days: int = ELEMENTARY_KEEP_DAYS,
    elementary_on_failure: str = "fail",
    now: datetime | None = None,
) -> str:
    """Write the warehouse's snapshot tables and Elementary's kept tables to the store as a new save, then point
    history.json and elementary.json at it. Returns what it did, for the log; raises ElementaryDegraded when
    Elementary's part failed under `elementary_on_failure` degrade. `now` is the instant --keep-days counts back from."""
    if elementary_on_failure not in ELEMENTARY_ON_FAILURE:
        raise ValueError(f"elementary_on_failure is one of {ELEMENTARY_ON_FAILURE}, not {elementary_on_failure!r}")
    if keep_days < 1:
        raise Refused(f"--keep-days {keep_days}: a save keeps at least one day of Elementary's history")
    # Elementary's timestamps are UTC without a zone (every dbt command runs with TZ=UTC: build_marts.py), and so is a
    # `now` given without one.
    now = now or datetime.now(UTC)
    if now.tzinfo is not None:
        now = now.astimezone(UTC).replace(tzinfo=None)
    cutoff = now - timedelta(days=keep_days)
    store = Store(url)
    store.check_reachable()
    failure = None
    lines = []
    with duckdb.connect(str(warehouse)) as con:
        # Every check before anything is written, so a refusal under `fail` writes nothing at all.
        rows = _check_rows_save(store, url, con, warehouse)
        elementary = None
        try:
            elementary = _check_elementary_save(store, url, con, warehouse)
            if elementary is None:
                lines.append(
                    "Elementary's history: not restored in this build, so none of it is saved, and "
                    f"{ELEMENTARY_POINTER} keeps naming the last good save"
                )
        except Exception as error:  # noqa: BLE001 - every failure of Elementary's part is answered by the policy
            if elementary_on_failure != "degrade":
                raise
            failure = _failure(error)
        save_id = _new_save_id()
        # Elementary's first, so under `fail` the snapshots, which a hiker's dates come from, are written last.
        written = False
        if elementary is not None:
            try:
                lines.append(_write_elementary(store, url, con, elementary, save_id, cutoff, keep_days))
                written = True
            except Exception as error:  # noqa: BLE001 - as above
                if elementary_on_failure != "degrade":
                    raise
                failure = _failure(error)
        lines.insert(0, _write_rows(store, url, con, rows, save_id))
    if failure is not None:
        failure += (
            f". The row history was saved; Elementary's history was not, and {ELEMENTARY_POINTER} keeps naming its "
            "last good save."
        )
    elif written:
        try:
            _prune(store, ELEMENTARY_SAVES, save_id, elementary.restored_save)
        except Exception as error:  # noqa: BLE001 - as above
            if elementary_on_failure != "degrade":
                raise
            failure = f"{_failure(error)}: both histories were saved, and Elementary's oldest saves are not all removed."
    if failure is not None:
        raise ElementaryDegraded("\n".join(lines), failure)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    commands = parser.add_subparsers(dest="command", required=True)
    for name, help_ in (("restore", "the store's current save into the warehouse"), ("save", "the warehouse's history out")):
        command = commands.add_parser(name, help=help_)
        command.add_argument("--url", required=True, help="the history store (OURHIKE_HISTORY_URL)")
        command.add_argument("--warehouse", required=True, type=Path)
        command.add_argument(
            "--elementary-on-failure",
            choices=ELEMENTARY_ON_FAILURE,
            default="fail",
            help="degrade: a failure of Elementary's history alone still restores or saves the row history, exit 3",
        )
        if name == "restore":
            command.add_argument("--cold-start", action="store_true", help="allow a store with no history.json")
            command.add_argument(
                "--elementary-cold-start", action="store_true", help=f"allow a store with no {ELEMENTARY_POINTER}"
            )
        else:
            command.add_argument(
                "--keep-days",
                type=int,
                default=ELEMENTARY_KEEP_DAYS,
                help=f"days of Elementary's history to keep (default {ELEMENTARY_KEEP_DAYS}, the longest any lane needs)",
            )
    args = parser.parse_args(argv)
    try:
        if args.command == "restore":
            message = restore(
                args.url, args.warehouse, args.cold_start, args.elementary_cold_start or None, args.elementary_on_failure
            )
        else:
            message = save(args.url, args.warehouse, args.keep_days, args.elementary_on_failure)
        for line in message.splitlines():
            print(f"row_history: {line}", flush=True)
    except ElementaryDegraded as degraded:
        for line in degraded.done.splitlines():
            print(f"row_history: {line}", flush=True)
        done = "restored" if args.command == "restore" else "saved"
        print(f"::error title=Elementary's history not {done}::{degraded.failure}", flush=True)
        return ELEMENTARY_DEGRADED_EXIT
    except ColdStartRefused as refused:
        print(f"::error title={refused.title}::{refused}", flush=True)
        return 2
    except Refused as refused:
        print(f"::error title={refused.title}::{refused}", flush=True)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
