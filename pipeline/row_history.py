"""row_history: keep the warehouse's row-history snapshots between runs, outside the warehouse.

    python row_history.py restore --url URL --warehouse W [--cold-start]
    python row_history.py save --url URL --warehouse W

build_marts.py runs `restore` before its first dbt command and `save` after
its last one has succeeded, so a failed build never saves. Everything else
about the snapshots is macros/row_history.sql's (pipeline/dbt/).

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
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import sys
import tempfile
from datetime import UTC, datetime
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
#: history.json back, which nobody has measured, would settle it.
KEEP_SAVES = 24


class Refused(Exception):
    """A failure this file names, with what to do; exit 1."""


class ColdStartRefused(Refused):
    """No history at the URL and no permission to start it; exit 2."""


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

    def get(self, relative: str, local: Path) -> None:
        if self.fs is None:
            source = Path(self._path(relative))
            if not source.exists():
                raise Refused(f"{self.url}/{relative} is named by {POINTER} and is not there")
            local.write_bytes(source.read_bytes())
            return
        try:
            self.fs.get_file(self._path(relative), str(local))
        except FileNotFoundError as error:
            raise Refused(f"{self.url}/{relative} is named by {POINTER} and is not there") from error

    def save_folders(self) -> list[str]:
        if self.fs is None:
            folder = Path(self._path(SAVES))
            return sorted(path.name for path in folder.iterdir() if path.is_dir()) if folder.is_dir() else []
        try:
            return sorted(path.rstrip("/").rsplit("/", 1)[-1] for path in self.fs.ls(self._path(SAVES), detail=False))
        except FileNotFoundError:
            return []

    def remove_save(self, save_id: str) -> None:
        if self.fs is None:
            folder = Path(self._path(f"{SAVES}/{save_id}"))
            for path in folder.iterdir():
                path.unlink()
            folder.rmdir()
            return
        self.fs.rm(self._path(f"{SAVES}/{save_id}"), recursive=True)


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


def _count(con: duckdb.DuckDBPyConnection, table: str) -> int:
    return con.execute(f"select count(*) from {SCHEMA}.{_quote(table)}").fetchone()[0]


def _history_start(con: duckdb.DuckDBPyConnection, table: str) -> str | None:
    started = con.execute(f"select min(dbt_valid_from) from {SCHEMA}.{_quote(table)}").fetchone()[0]
    return None if started is None else started.isoformat() + "Z"


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


def restore(url: str, warehouse: Path, cold_start: bool) -> str:
    """Replace the warehouse's snapshot tables with the store's current save. Returns what it did, for the log."""
    store = Store(url)
    store.check_reachable()
    text = store.read_text(POINTER)
    with duckdb.connect(str(warehouse)) as con:
        # No receipt until this restore has finished, so a restore that fails half-way cannot be saved.
        con.execute(f"drop table if exists {RECEIPT_SCHEMA}.{RECEIPT_TABLE}")
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
            _write_receipt(con, url, None, {})
            return f"cold start: no {POINTER} at {url}, so every snapshot's history starts in this build"
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
                con.execute(
                    f"create table {SCHEMA}.{_quote(table)} as select * from read_parquet(?)",
                    [str(local)],
                )
                if (rows := _count(con, table)) != entry["rows"]:
                    raise Refused(f"{url}/{entry['file']} holds {rows} rows, and {POINTER} says {entry['rows']}")
                restored[table] = rows
        _write_receipt(con, url, pointer["save_id"], restored)
    total = sum(restored.values())
    return f"restored save {pointer['save_id']} from {url}: {len(restored)} snapshot tables, {total} rows"


def save(url: str, warehouse: Path) -> str:
    """Write the warehouse's snapshot tables to the store as a new save, then point history.json at it."""
    store = Store(url)
    store.check_reachable()
    with duckdb.connect(str(warehouse)) as con:
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
        save_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(3)
        entries = {}
        with tempfile.TemporaryDirectory() as scratch:
            for table in tables:
                local = Path(scratch) / f"{table}.parquet"
                con.execute(
                    f"copy {SCHEMA}.{_quote(table)} to '{local}' (format parquet, compression zstd)",
                )
                relative = f"{SAVES}/{save_id}/{table}.parquet"
                store.put(local, relative)
                entries[table] = {
                    "file": relative,
                    "rows": counts[table],
                    "sha256": _sha256(local),
                    "history_started_at": _history_start(con, table),
                }
    pointer = {
        "format": FORMAT,
        "save_id": save_id,
        "saved_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "previous_save_id": restored_save,
        "tables": entries,
    }
    store.write_text(POINTER, json.dumps(pointer, indent=2, sort_keys=True) + "\n")
    for old in store.save_folders()[:-KEEP_SAVES]:
        if old != save_id:
            store.remove_save(old)
    return f"saved {len(entries)} snapshot tables, {sum(counts.values())} rows, to {url} as save {save_id}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    commands = parser.add_subparsers(dest="command", required=True)
    for name, help_ in (("restore", "the store's current save into the warehouse"), ("save", "the warehouse's history out")):
        command = commands.add_parser(name, help=help_)
        command.add_argument("--url", required=True, help="the history store (OURHIKE_HISTORY_URL)")
        command.add_argument("--warehouse", required=True, type=Path)
        if name == "restore":
            command.add_argument("--cold-start", action="store_true", help="allow a store with no history.json")
    args = parser.parse_args(argv)
    try:
        if args.command == "restore":
            print(f"row_history: {restore(args.url, args.warehouse, args.cold_start)}", flush=True)
        else:
            print(f"row_history: {save(args.url, args.warehouse)}", flush=True)
    except ColdStartRefused as refused:
        print(f"::error title=Row history not restored::{refused}", flush=True)
        return 2
    except Refused as refused:
        print(f"::error title=Row history refused::{refused}", flush=True)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
