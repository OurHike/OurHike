"""Raw store -> the warehouse's `raw` schema, reading only what a committed load wrote.

load_raw.py's successor (pipeline/ELT.md, "Where data lands") for the tables
pipeline/extract/ lands; load_raw.py loads the rest until each club's folder
replaces its fetcher, and is then deleted.

THE FILES ARE AN EXPLICIT LIST, NEVER A GLOB: each table is read from the
files of the one load `_extract_runs` records as its latest `loaded` run, and
only when `_dlt_loads` records that load complete. On plain Parquet a
`replace` load that fails half-way can leave its first new file and nothing
else, so a glob would read a closures table as one closure, or none, and pass
every check (ELT.md, "A full reload that cannot empty a safety table",
measured 2026-10-01). A table with no committed file refuses the build:
"no closures" is a claim, and a missing file is not evidence for it.

A PINNED RAW_RUN (`pin` in refresh-reference.yml's pin job, `load --raw-run`
in build-reference.yml's build and parity jobs) is a write-once copy, at
`<steps-url>/raw_inputs/<raw_run>/`, of what a
build of one extract run (its `run_id`, the raw_run) reads: each table's
committed rows as of that run, its `_extract_runs` rows and its as-landed
files, `raw_inputs.json` last. The production promotion builds from it alone,
so it reads the rows UA verified rather than whatever the next `replace` left,
and an expired or purged pin stops it (ELT.md, "Storage tiers" and "Why a
scheduled run cannot reach production"). DuckLake replaces this for the
monthly tables at stage 3's first step, once its three go/no-go runs pass
(ELT.md, "DuckLake at phases 3 and 4").

THE SERVED COPY (`serve`, `add-served`) is how the hourly build reads a
notices leg (decision 61). The notices job, extract-notices.yml, writes its
store every 4 hours, in runs that may overlap publish-conditions.yml's. A
`replace` load deletes a table's files before it writes the new ones, and
the run log lands after both (extract/_run.py's _extract_and_load()), so a
read of the store itself in that window finds the logged load's files gone,
or some of them: a torn read. So once its run has committed, the notices job
copies what a build reads of it, write-once, to
`<bucket-url>/served/<run_id>/`: each committed table of its job as one
Parquet file, the hints of each table created empty (a proven zero, a table
not yet loaded), and the run log rows of those tables, with `manifest.json`
last, holding each file's sha256 (write_served_copy()). The hourly build
reads the newest finished copy, which no load in flight can touch, and a
copy that will not read falls back to the one before, the notices' last good
rows (load_served()). SERVED_KEEP copies are kept. A copy whose run began
more than SERVED_STALE_HOURS before the read is still read, and add-served
says so in its exit; when that run began is handed to dbt either way
(NOTICES_READ_AT_ENV). A leg with no copy at all has owed one since its
first committed run, and past SERVED_STALE_HOURS of that add-served says so
in its exit too (SERVED_OVERDUE_EXIT).
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import sys
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from itertools import islice
from pathlib import Path
from urllib.parse import urlsplit

import duckdb
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from extract._run import (
    AS_LANDED_INDEX,
    AS_LANDED_PREFIX,
    INCOMPLETE,
    ISOLATED_OUTCOME,
    LANES,
    LEGS,
    PARTIAL_EXIT,
    RUNS_TABLE,
    UNAVAILABLE,
    _client,
    as_landed_index,
    as_landed_path,
    committed_load_ids,
    fs_path,
    left_out_on_its_own,
    leg_run_log_files,
    make_pipeline,
    proven_zero,
    raw_store_url,
    run_log_bytes,
    run_log_rows,
    table_files,
    table_listing,
)
from lib.store_names import StoreNameRefused, quote_identifier, relative_path, table_name


class BuildRefused(RuntimeError):
    """A table the run log says exists has no committed file to read, or the store names one this repository never
    writes."""


# NAMES READ BACK FROM THE STORE are checked before one becomes SQL or a path (lib/store_names.py): the run log's
# table names, a pin's, a served copy's and an as-landed index's paths. Each check refuses the build, as a missing
# file does: a name no run of this repository writes is not evidence of anything a build should read.


def _stored_table(name: object, where: str) -> str:
    """`name`, a table name read back from the store, or BuildRefused (lib/store_names.py's table_name())."""
    try:
        return table_name(name, where)
    except StoreNameRefused as refused:
        raise BuildRefused(str(refused)) from refused


def _stored_path(path: object, where: str) -> str:
    """`path`, a path read back from the store, or BuildRefused when it could leave where it is joined on."""
    try:
        return relative_path(path, where)
    except StoreNameRefused as refused:
        raise BuildRefused(str(refused)) from refused


# dlt data types -> DuckDB, for a proven-empty table created from its hints.
# `json` lands VARCHAR, as the filesystem destination's Parquet writes it
# (ELT.md, rule 1 of the four measured hazards), so a base model casts both alike.
DUCKDB_TYPES = {
    "bigint": "BIGINT",
    "double": "DOUBLE",
    "text": "VARCHAR",
    "json": "VARCHAR",
    "bool": "BOOLEAN",
    "timestamp": "TIMESTAMP",
    "date": "DATE",
}


def _naming(pipeline):
    """The pipeline schema's naming, or sql_ci_v1's own on a fresh working directory, which holds no schema yet.

    A build job starts from an empty dlt directory (build-reference.yml), and
    `default_schema` raises there; extract/_run.py and .dlt/config.toml set
    `sql_ci_v1` for every run, so its convention is the one the files were named by.
    """
    try:
        return pipeline.default_schema.naming
    except Exception:  # noqa: BLE001 - dlt raises its own config errors for a pipeline with no schema
        from dlt.common.normalizers.naming.sql_ci_v1 import NamingConvention

        return NamingConvention()


def _create_proven_empty(con, schema: str, table: str, hints: dict, pipeline) -> None:
    """An empty table with the columns its resource hinted, plus dlt's own, under dlt's naming.

    For a load the run log shows as a proven zero (no rows, and the upstream's
    own count read zero in the same run): dlt writes no file for a table's
    first load when it holds no rows (a later empty replace does write a
    zero-row file), so without this a closures layer empty the first time it
    is read would refuse the whole build. Also for a table
    not yet loaded (not_yet_loaded()), which load_warehouse() names in a
    `::warning` annotation.
    """
    _stored_table(table, "the store's record of a table to create empty")
    naming = _naming(pipeline)
    columns = {
        naming.normalize_identifier(name): DUCKDB_TYPES.get(hint.get("data_type"), "VARCHAR") for name, hint in hints.items()
    }
    # TIMESTAMPTZ, as dlt writes `_loaded_at` into every table it loads: a
    # naive UTC stamp lands `TIMESTAMP WITH TIME ZONE` (measured 2026-10-01,
    # dlt 1.30.0, filesystem destination, Parquet). An empty closures table is
    # a normal state, so its type must not differ from a full one's.
    columns.update({"_loaded_at": "TIMESTAMPTZ", "_dlt_load_id": "VARCHAR", "_dlt_id": "VARCHAR"})
    # Every column quoted too: sql_ci_v1 reduces a hint's name to [a-z0-9_], but _naming() takes whatever naming the
    # stored schema declares, so nothing here leans on that.
    body = ", ".join(f"{quote_identifier(name)} {type_}" for name, type_ in columns.items())
    con.execute(f"CREATE OR REPLACE TABLE {quote_identifier(schema)}.{quote_identifier(table)} ({body})")


def committed_tables(
    pipeline, as_of: str | None = None, *, log: list[dict] | None = None, complete: set[str] | None = None
) -> dict[str, str]:
    """{table: the load id holding its current rows}, from each table's latest `loaded` run that committed.

    A table whose latest run found it unavailable is withdrawn, whatever it
    loaded before: rows the reader can no longer see are not current, and an
    absent table is how the build says unknown (extract/_contract.py's
    Unavailable).

    `as_of` is a run_id: runs after it are not read, so the answer is what a
    build right after that run would have read (`pin`). `log` and `complete`
    are the run log and the committed load ids where the caller has read them
    already, since each is a read of every file under its prefix.
    """
    complete = committed_load_ids(pipeline) if complete is None else complete
    latest: dict[str, tuple[str, str]] = {}
    withdrawn: dict[str, str] = {}
    for row in run_log_rows(pipeline) if log is None else log:
        if as_of is not None and row["run_id"] > as_of:
            continue
        table = row["table_name"]
        if row.get("outcome") == UNAVAILABLE:
            withdrawn[table] = max(withdrawn.get(table, ""), row["run_id"])
            continue
        if row.get("outcome") != "loaded" or not row.get("load_id") or row["load_id"] not in complete:
            continue
        previous = latest.get(table)
        if previous is None or row["run_id"] > previous[0]:
            latest[table] = (row["run_id"], row["load_id"])
    return {table: load_id for table, (run_id, load_id) in latest.items() if run_id > withdrawn.get(table, "")}


def not_yet_loaded(pipeline, committed: dict[str, str], log: list[dict] | None = None) -> dict[str, dict]:
    """{table: column hints} for each table that has never committed a load, nor been withdrawn since.

    Its resource answered Incomplete (extract/_contract.py), as ATC's
    trail-updates pages do on a first run, read over several hours at their
    Crawl-delay; or a conditions leg refused it on its own (`refused`, with
    hints) on every run so far. The hints are the latest such row's.
    """
    log = run_log_rows(pipeline) if log is None else log
    latest: dict[str, tuple[str, dict]] = {}
    withdrawn: dict[str, str] = {}
    for row in log:
        table = row["table_name"]
        if row.get("outcome") == UNAVAILABLE:
            withdrawn[table] = max(withdrawn.get(table, ""), row["run_id"])
        elif row.get("outcome") in (INCOMPLETE, ISOLATED_OUTCOME) and row.get("column_hints") and table not in committed:
            if table not in latest or row["run_id"] > latest[table][0]:
                latest[table] = (row["run_id"], json.loads(row["column_hints"]))
    return {table: hints for table, (run_id, hints) in latest.items() if run_id > withdrawn.get(table, "")}


def load_warehouse(
    con: duckdb.DuckDBPyConnection,
    pipeline,
    schema: str = "raw",
    log: list[dict] | None = None,
    readers: int = 1,
    tables: set[str] | None = None,
) -> dict[str, int]:
    """Replace each extracted table in `schema` with its committed rows. Returns {table: rows}.

    `log` is `_extract_runs` where the caller has read it already; it is read once otherwise.

    `readers` tables are read from the store at once, in a window that holds
    no more than that many tables' rows: one for the monthly lane, whose
    tables run to hundreds of megabytes and whose ninth run ran out of memory,
    and LEG_READERS for a leg, whose 92 tables took about 55 s one after
    another in soak run 508 (publish-conditions.yml 37158027469). The files
    are listed once (table_listing()), and only this thread writes to `con`,
    so the window changes how long the read takes, never what lands.

    `tables`, for a leg, is the tables its job reads now (extract/_run.py's
    leg_tables()): only those, and only their run log rows, are loaded. A
    leg's store keeps every table it ever loaded, one whose resource has
    moved to the other job included: the conditions legs' stores keep the 80
    notice layers decision 61 moved to the notices legs, frozen at the last
    run before the move, and reading them would serve rows days old as this
    hour's.
    """
    client = _client(pipeline)
    con.execute(f"CREATE SCHEMA IF NOT EXISTS {quote_identifier(schema)}")
    loaded = {}
    log = run_log_rows(pipeline) if log is None else log
    if tables is not None:
        log = [row for row in log if row["table_name"] in tables]
    log_rows = {(row["table_name"], row.get("load_id")): row for row in log}
    committed = committed_tables(pipeline, log=log)
    # Every name before any is read or created (the note above _stored_table()): the monthly lane passes no `tables`,
    # so the run log's own names are all there is.
    for table in committed:
        _stored_table(table, "the run log (_extract_runs)")
    listing = table_listing(pipeline, list(committed))

    def read(item: tuple[str, str]):
        table, load_id = item
        files = [path for path in listing.get(table, []) if os.path.basename(path).startswith(f"{load_id}.")]
        if not files:
            return files, None
        return files, pa.concat_tables(
            [pq.read_table(client.fs_client.open(path)) for path in files], promote_options="permissive"
        )

    for (table, load_id), (files, arrow) in windowed(read, sorted(committed.items()), readers):
        if not files:
            row = log_rows.get((table, load_id)) or {}
            if proven_zero(row):
                _create_proven_empty(con, schema, table, json.loads(row["column_hints"]), pipeline)
                loaded[table] = 0
                continue
            raise BuildRefused(f"{table}: no committed file from load {load_id}; refusing rather than reading it as empty")
        con.register("_committed", arrow)
        con.execute(f"CREATE OR REPLACE TABLE {quote_identifier(schema)}.{quote_identifier(table)} AS SELECT * FROM _committed")
        con.unregister("_committed")
        loaded[table] = arrow.num_rows
    # NOT YET LOADED IS NOT A REFUSAL OF EVERYONE ELSE. A table with no
    # committed load yet (not_yet_loaded()) has no file, and a missing table
    # would stop every model downstream of it, every other club's closures
    # included. So it is created empty from its own hints and named in an
    # annotation. For ATC's trail-updates pages that publishes the reviewed
    # rows without the automatic ones, as export_atc_updates.py does today
    # when fetch_atc_updates.py's cache is missing (export_atc_updates.py's
    # CACHE_PATH comment).
    for table, hints in sorted(not_yet_loaded(pipeline, committed, log).items()):
        print(f"::warning title={table} not yet loaded::no load of it has committed yet, so it is empty in this build")
        _create_proven_empty(con, schema, table, hints, pipeline)
        loaded[table] = 0
    if log:
        con.register("_runs", pa.Table.from_pylist(log))
        con.execute(f"CREATE OR REPLACE TABLE {quote_identifier(schema)}.{quote_identifier(RUNS_TABLE)} AS SELECT * FROM _runs")
        con.unregister("_runs")
    return loaded


#: A conditions leg's warehouse read: tables read from the store at once (load_warehouse()).
#: 8 is @unvalidated: a leg's tables are small (soak run 508's 92 held 11,999 rows),
#: and the step summary's warehouse timing on the next runs settles whether it is enough.
LEG_READERS = 8


def windowed(work, items: list, size: int):
    """(item, work(item)) for each item, in order, with at most `size` running or waiting to be taken at once."""
    if size <= 1:
        for item in items:
            yield item, work(item)
        return
    pending = deque()
    with ThreadPoolExecutor(max_workers=size) as pool:
        queue = iter(items)
        for item in islice(queue, size):
            pending.append((item, pool.submit(work, item)))
        while pending:
            item, future = pending.popleft()
            answer = future.result()
            following = next(queue, None)
            if following is not None:
                pending.append((following, pool.submit(work, following)))
            yield item, answer


# --- The served copy (the module docstring, "THE SERVED COPY") ---

#: Tables write_served_copy() reads, writes and reads back at once. One at a time, a notices
#: leg's 261 tables took 2 min 47 s in extract-notices.yml run 6 (2026-10-05T14:22Z), 4 min 15 s in
#: run 7 (18:51Z), and passed the step's 5 minutes in run 8 (22:25Z), which served no copy, so the
#: hourly build read run 7's until it was 8 hours old (publish-conditions.yml run 561, red): about
#: 0.6 to 1 s a table, each several round trips to R2 for a few dozen rows. At 8, run 10
#: (37423240098, 2026-10-06) copied the 261 in 39 s (Measured from its log), the one run so far. 8 is
#: @unvalidated, as LEG_READERS is: the step's own time on the next runs settles it.
SERVE_COPIERS = 8

SERVED_PREFIX = "served"
#: Written last, as a pin's raw_inputs.json is: a copy without it did not finish, and is never read.
SERVED_MANIFEST = "manifest.json"
#: Finished copies kept after each write, the newest first. 3 at a 4-hourly
#: cadence is about 12 hours of them. A reader picks the newest when it starts,
#: so a purge reaches the copy it is reading only if the reader is slower than
#: two notices runs; publish-conditions.yml caps its read step at minutes
#: (Reasoned).
SERVED_KEEP = 3
#: add-served's exits besides 0 (the newest copy read) and 1 (none could be):
#: an older copy was read because the newest could not be, or no copy has been
#: written yet and none is overdue. Neither stops the hourly build;
#: publish-conditions.yml says which. SERVED_STALE_EXIT and
#: SERVED_OVERDUE_EXIT, below, are the third and fourth.
SERVED_OLDER_EXIT, SERVED_NONE_EXIT = 5, 6
#: A COPY WHOSE RUN BEGAN MORE THAN THIS MANY HOURS BEFORE add-served READ IT
#: IS STALE. It is still added, so the hourly build still publishes, but
#: add-served exits SERVED_STALE_EXIT and publish-conditions.yml turns the run
#: red at the end. Before this bound a copy of any age read as the newest and
#: the run stayed green: soak run 538 (publish-conditions.yml 37250913570,
#: 2026-10-05) read one whose run began 3 h 01 min earlier. 8 is
#: @unvalidated: twice extract-notices.yml's 4-hour cron, so a copy reaches
#: it only once the notices run after it has failed or not fired, and the one after that has not yet finished (Reasoned from the
#: cron alone). What would settle it: the gaps between consecutive copies'
#: run ids over a few weeks of the schedule, which #1346 — Every cron in this
#: repository fires about five times a day, whatever it declares — including
#: the conditions bake says may be hours longer than the cron declares, plus
#: how long a notices run takes to write its copy.
SERVED_STALE_HOURS = 8
SERVED_STALE_EXIT = 7
#: A LEG WITH NO SERVED COPY COUNTS AS ONE OLDER THAN SERVED_STALE_HOURS ONCE
#: IT HAS OWED A COPY THAT LONG (decision 96, the maintainer's poll of
#: 2026-10-06: "Red after 8 h, like stale"). Before it, `none` read as a
#: cold start however long it lasted, so the hourly run stayed green while a
#: copy 8 h 01 min old turned it red (review finding PY-3 of PR #1805 — dlt →
#: dbt re-platform as one go/no-go change). A leg owes a copy from its first
#: committed load, the instant in that load's id (copy_due_since()), not its
#: newest: a leg whose copy step keeps failing, as extract-notices.yml run 8's
#: did on 2026-10-05, keeps committing runs under 8 hours old, and the copy it
#: owes is as old as its first (Reasoned). A leg that has committed no load
#: has no instant to count from, and is overdue at once, the stricter rule
#: is_stale() keeps for a copy of unknown age. add-served then exits this, no
#: tables of the leg are added, the hourly build publishes the rest, and
#: publish-conditions.yml turns the run red at the end. The 8 is
#: SERVED_STALE_HOURS's, @unvalidated there.
SERVED_OVERDUE_EXIT = 8
#: What add-served appends to --env-file ($GITHUB_ENV in publish-conditions.yml),
#: so every later step, build_marts.py's dbt commands among them, inherits it:
#: the instant the run of the copy it read began, which is also the
#: `checked_at` of every run log row that run wrote. It is there for
#: pub_conditions_notices.sql to publish as `notices_read_at`, which that
#: writer does not do yet. Never written when no copy was read, so a missing
#: or empty value means unknown.
NOTICES_READ_AT_ENV = "OURHIKE_NOTICES_READ_AT"
#: How many times load_served() lists the copies and reads the newest before it
#: falls back to an older one, and the seconds between. A copy is write-once,
#: so what this waits out is a transient error from the store, or a copy that
#: vanished under the read (a purge). 3 x 5 s is a round figure, @unvalidated:
#: the 33 soak dispatches from run 527 to 566 (publish-conditions.yml,
#: 2026-10-04 to 06) each read the newest copy and none fell back to an older
#: one (Measured 2026-10-06 from their logs), so no failure has yet shown what
#: this has to wait out.
SERVED_ATTEMPTS, SERVED_WAIT_SECONDS = 3, 5.0


def served_root(bucket_url: str) -> str:
    """`<bucket-url>/served`, as the raw store's filesystem client names it."""
    return f"{fs_path(bucket_url)}/{SERVED_PREFIX}"


def served_copies(fs, bucket_url: str) -> list[str]:
    """The run ids of every finished copy (one with a manifest), newest first; run ids sort in time order.

    The listing is asked of the store each time: s3fs keeps a listings cache
    per filesystem, which would answer a re-list with the copies it saw first.
    """
    fs.invalidate_cache(served_root(bucket_url))
    try:
        found = fs.glob(f"{served_root(bucket_url)}/*/{SERVED_MANIFEST}")
    except FileNotFoundError:
        return []
    return sorted({os.path.basename(os.path.dirname(path.rstrip("/"))) for path in found}, reverse=True)


def _log_arrow(pipeline, tables: set[str], cache: Path | None = None) -> pa.Table | None:
    """A leg's run log as dlt wrote it, with its column types, less the rows of tables not in `tables`: the kept log
    and the `_extract_runs` files after it, or every file where no kept log has committed (extract/_run.py's
    leg_run_log_files(), KEPT_LOG_TABLE).

    Kept as Arrow, never as Python rows, so a column that is null on every
    row keeps the type dlt declared for it (RUNS_COLUMNS) instead of landing
    as DuckDB's INTEGER. With `cache`, a run log file the extract step kept
    there is read from it, not from the store again (extract/_run.py's
    run_log_bytes()).
    """
    kept, files = leg_run_log_files(pipeline, committed_load_ids(pipeline))
    if not kept and not files:
        return None
    client = _client(pipeline)
    arrow = pa.concat_tables(
        [pq.read_table(client.fs_client.open(path)) for path in kept]
        + [pq.read_table(io.BytesIO(run_log_bytes(pipeline, path, cache))) for path in files],
        promote_options="permissive",
    )
    return arrow.filter(pc.is_in(arrow["table_name"], value_set=pa.array(sorted(tables), pa.string())))


def _previous_manifest(fs, bucket_url: str, before: str) -> tuple[str, dict] | None:
    """The newest finished copy older than run `before`, and its manifest, or None."""
    for run_id in served_copies(fs, bucket_url):
        if run_id < before:
            with fs.open(f"{served_root(bucket_url)}/{run_id}/{SERVED_MANIFEST}", "r") as handle:
                return run_id, json.load(handle)
    return None


@dataclass
class ServedWrite:
    """What write_served_copy() did: the copy's manifest, whether this call wrote it, and each table it could not
    copy from the store, with why and what it did instead (carried from the copy before, or left out)."""

    manifest: dict
    wrote: bool
    problems: list[str] = field(default_factory=list)


def write_served_copy(pipeline, bucket_url: str, tables: set[str], run_log_cache: Path | None = None) -> ServedWrite:
    """Copy what a build reads of this leg, as of its newest run, to `<bucket-url>/served/<run_id>/`, manifest last.

    WRITE-ONCE, as a pin is: a copy that exists is read back, never rewritten.
    `tables` is the leg's job's tables (extract/_run.py's leg_tables()); a
    table outside it, and its run log rows, are never copied.

    A TABLE THE STORE CANNOT GIVE BACK WHOLE DOES NOT HOLD BACK THE OTHERS.
    One whose logged load has no file, or whose files hold another count of
    rows than the run log says that load landed, is a table a run left torn:
    killed between its load, which deletes a table's files before it writes
    the new ones, and its run log. That table is carried from the copy
    before, its last good rows, and named in `problems`; with no copy
    before, it is left out and named. The next run that reads it whole mends
    the store. A carried table's run log rows are carried with it, from the
    copy its rows came from, and a table left out takes none, so the hourly
    build never dates a table's rows by a read whose rows it does not hold.

    Then every finished copy past the newest SERVED_KEEP is deleted, and so
    is any unfinished one older than this. `run_log_cache` is the extract
    step's --run-log-cache, so the run log is read from the store once a run.
    """
    fs = _client(pipeline).fs_client
    log_arrow = _log_arrow(pipeline, tables, run_log_cache)
    if log_arrow is None or log_arrow.num_rows == 0:
        raise BuildRefused("the run log holds no run of this leg's tables, so there is nothing to serve")
    log = log_arrow.to_pylist()
    run_id = max(row["run_id"] for row in log)
    root = f"{served_root(bucket_url)}/{run_id}"
    if fs.exists(f"{root}/{SERVED_MANIFEST}"):
        with fs.open(f"{root}/{SERVED_MANIFEST}", "r") as handle:
            return ServedWrite(json.load(handle), False)
    committed = committed_tables(pipeline, log=log)
    listing = table_listing(pipeline, list(committed))
    by_load = {(row["table_name"], row.get("load_id")): row for row in log}
    previous = _previous_manifest(fs, bucket_url, run_id)
    entries: dict[str, dict] = {}
    problems: list[str] = []
    # Tables whose run log rows this copy takes from the copy before, and tables it leaves out with no rows at all.
    carried_logs: set[str] = set()
    left_out: set[str] = set()
    previous_log: list[pa.Table] = []

    def log_before() -> pa.Table:
        """The copy before's run log, verified, read once and only when a table is carried from it."""
        if not previous_log:
            runs = previous[1]["extract_runs"]
            file = _stored_path(runs["file"], f"served copy {previous[0]}'s {SERVED_MANIFEST}")
            path = f"{served_root(bucket_url)}/{previous[0]}/{file}"
            previous_log.append(pq.read_table(io.BytesIO(_verified_bytes(fs, path, runs["sha256"]))))
        return previous_log[0]

    fs.makedirs(f"{root}/tables", exist_ok=True)

    def copy_table(item: tuple[str, str]) -> tuple[dict, pa.Table | None, dict | None]:
        """One table's run log row, its rows as read, and its entry when it was copied whole; nothing else touched."""
        table, load_id = item
        files = [path for path in listing.get(table, []) if os.path.basename(path).startswith(f"{load_id}.")]
        row = by_load.get((table, load_id)) or {}
        if not files and proven_zero(row):
            return row, None, {"load_id": load_id, "rows": 0, "file": None, "column_hints": json.loads(row["column_hints"])}
        arrow = None
        if files:
            arrow = pa.concat_tables([pq.read_table(fs.open(path)) for path in files], promote_options="permissive")
        if arrow is None or arrow.num_rows != row.get("rows"):
            return row, arrow, None
        relative = f"tables/{_stored_table(table, 'the run log (_extract_runs)')}.parquet"
        with fs.open(f"{root}/{relative}", "wb") as handle:
            pq.write_table(arrow, handle, compression="zstd")
        return (
            row,
            arrow,
            {"load_id": load_id, "rows": arrow.num_rows, "file": relative, "sha256": _sha256(fs, f"{root}/{relative}")},
        )

    # Each table is read, written and read back by SERVE_COPIERS at once, and taken in table order.
    for (table, load_id), (row, arrow, copied) in windowed(copy_table, sorted(committed.items()), SERVE_COPIERS):
        if copied is not None:
            entries[table] = copied
            continue
        # Torn: carried from the copy before, or left out (the docstring).
        found = "no file" if arrow is None else f"{arrow.num_rows} rows in its files"
        why = f"{table}: load {load_id} has {found}, and the run log says it landed {row.get('rows')}"
        carried = previous[1]["tables"].get(table) if previous else None
        if carried is not None:
            try:
                log_before()
            except SERVED_READ_ERRORS as failure:
                why += f"; copy {previous[0]}'s run log will not read ({type(failure).__name__}: {failure})"
                carried = None
        if carried is None:
            left_out.add(table)
            problems.append(f"{why}; no copy before this one can give it, so it is left out")
            continue
        if carried.get("file"):
            file = _stored_path(carried["file"], f"served copy {previous[0]}'s {SERVED_MANIFEST}")
            fs.copy(f"{served_root(bucket_url)}/{previous[0]}/{file}", f"{root}/{file}")
        entries[table] = dict(carried, carried_from=previous[0])
        carried_logs.add(table)
        problems.append(f"{why}; carried from copy {previous[0]}, its last good rows and their run log rows")
    for table, hints in sorted(not_yet_loaded(pipeline, committed, log).items()):
        entries[table] = {"load_id": None, "rows": 0, "file": None, "column_hints": hints, "not_yet_loaded": True}
    if carried_logs or left_out:
        replaced = pa.array(sorted(carried_logs | left_out), pa.string())
        log_arrow = log_arrow.filter(pc.invert(pc.is_in(log_arrow["table_name"], value_set=replaced)))
        if carried_logs:
            before = log_before()
            before = before.filter(pc.is_in(before["table_name"], value_set=pa.array(sorted(carried_logs), pa.string())))
            log_arrow = pa.concat_tables([log_arrow, before], promote_options="permissive")
    with fs.open(f"{root}/{RUNS_TABLE}.parquet", "wb") as handle:
        pq.write_table(log_arrow, handle, compression="zstd")
    manifest = {
        "run_id": run_id,
        "written_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tables": entries,
        "problems": problems,
        "extract_runs": {
            "file": f"{RUNS_TABLE}.parquet",
            "rows": log_arrow.num_rows,
            "sha256": _sha256(fs, f"{root}/{RUNS_TABLE}.parquet"),
        },
    }
    with fs.open(f"{root}/{SERVED_MANIFEST}", "w") as handle:
        handle.write(json.dumps(manifest, indent=2, sort_keys=True))
    purge_served(fs, bucket_url, run_id)
    return ServedWrite(manifest, True, problems)


def purge_served(fs, bucket_url: str, newest: str) -> list[str]:
    """Delete every finished copy past the newest SERVED_KEEP, and every unfinished one older than `newest`. Returns them."""
    root = served_root(bucket_url)
    keep = set(served_copies(fs, bucket_url)[:SERVED_KEEP])
    try:
        children = [os.path.basename(path.rstrip("/")) for path in fs.ls(root, detail=False)]
    except FileNotFoundError:
        return []
    doomed = sorted(run_id for run_id in children if run_id not in keep and run_id < newest)
    for run_id in doomed:
        fs.rm(f"{root}/{run_id}", recursive=True)
    return doomed


def _verified_bytes(fs, path: str, sha256: str) -> bytes:
    with fs.open(path, "rb") as handle:
        data = handle.read()
    if hashlib.sha256(data).hexdigest() != sha256:
        raise BuildRefused(f"{path} does not match the sha256 its served copy recorded")
    return data


def _read_served(fs, bucket_url: str, run_id: str, tables: set[str]) -> tuple[dict, dict[str, pa.Table], pa.Table]:
    """One copy's manifest, its tables of `tables` that have a file, and its run log rows of `tables`, each verified."""
    root = f"{served_root(bucket_url)}/{run_id}"
    with fs.open(f"{root}/{SERVED_MANIFEST}", "r") as handle:
        manifest = json.load(handle)
    # Only the leg's own table names are used (`tables`, from discover()), so only the manifest's paths are read
    # back; one that could leave the copy makes the copy one that will not read (SERVED_READ_ERRORS).
    where = f"served copy {run_id}'s {SERVED_MANIFEST}"
    wanted = sorted(
        (table, _stored_path(entry["file"], where), entry["sha256"])
        for table, entry in manifest["tables"].items()
        if table in tables and entry.get("file")
    )

    def read(item):
        _, path, sha256 = item
        return pq.read_table(io.BytesIO(_verified_bytes(fs, f"{root}/{path}", sha256)))

    arrows = {item[0]: arrow for item, arrow in windowed(read, wanted, LEG_READERS)}
    runs = manifest["extract_runs"]
    log = pq.read_table(io.BytesIO(_verified_bytes(fs, f"{root}/{_stored_path(runs['file'], where)}", runs["sha256"])))
    log = log.filter(pc.is_in(log["table_name"], value_set=pa.array(sorted(tables), pa.string())))
    return manifest, arrows, log


@dataclass
class ServedRead:
    """What load_served() read: the copy (None when none had been written), whether it was the newest, each table's
    rows, and why each copy it could not read could not be read."""

    run_id: str | None
    newest: bool
    loaded: dict[str, int] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)


#: What load_served() may meet reading a copy, each a reason to try again or try the one before.
SERVED_READ_ERRORS = (OSError, BuildRefused, ValueError, KeyError, pa.ArrowException)


def load_served(
    con: duckdb.DuckDBPyConnection,
    pipeline,
    bucket_url: str,
    tables: set[str],
    schema: str = "raw",
    attempts: int = SERVED_ATTEMPTS,
    wait: float = SERVED_WAIT_SECONDS,
    sleep=time.sleep,
) -> ServedRead:
    """Add a leg's served copy to a warehouse another leg has loaded: its tables of `tables`, each replaced, and its run
    log rows of `tables` beside the rows `_extract_runs` already holds. Read-only on the store.

    The newest finished copy is read up to `attempts` times, `wait` seconds
    apart, listing the copies again each time; then each older copy in turn,
    whose rows are the leg's last good ones. Nothing is written to `con`
    until one copy has read whole. Raises BuildRefused when copies exist and
    none could be read; a store with no copy yet answers a ServedRead whose
    run_id is None.
    """
    fs = _client(pipeline).fs_client
    problems: list[str] = []
    found = None
    copies: list[str] = []
    for attempt in range(attempts):
        copies = served_copies(fs, bucket_url)
        if not copies:
            return ServedRead(None, False, problems=problems)
        try:
            found = (copies[0], True, *_read_served(fs, bucket_url, copies[0], tables))
            break
        except SERVED_READ_ERRORS as failure:
            problems.append(f"copy {copies[0]}: {type(failure).__name__}: {failure}")
            if attempt + 1 < attempts:
                sleep(wait)
    if found is None:
        for run_id in copies[1:]:
            try:
                found = (run_id, False, *_read_served(fs, bucket_url, run_id, tables))
                break
            except SERVED_READ_ERRORS as failure:
                problems.append(f"copy {run_id}: {type(failure).__name__}: {failure}")
    if found is None:
        raise BuildRefused("no served copy could be read: " + "; ".join(problems))
    run_id, newest, manifest, arrows, log = found
    con.execute(f"CREATE SCHEMA IF NOT EXISTS {quote_identifier(schema)}")
    loaded: dict[str, int] = {}
    for table, entry in sorted(manifest["tables"].items()):
        if table not in tables:
            continue
        if table in arrows:
            con.register("_served", arrows[table])
            con.execute(f"CREATE OR REPLACE TABLE {quote_identifier(schema)}.{quote_identifier(table)} AS SELECT * FROM _served")
            con.unregister("_served")
            loaded[table] = arrows[table].num_rows
            continue
        if entry.get("not_yet_loaded"):
            print(f"::warning title={table} not yet loaded::no load of it has committed yet, so it is empty in this build")
        _create_proven_empty(con, schema, table, entry["column_hints"], pipeline)
        loaded[table] = 0
    if log.num_rows:
        con.register("_runs", log)
        (exists,) = con.execute(
            "select count(*) from information_schema.tables where table_schema = ? and table_name = ?", [schema, RUNS_TABLE]
        ).fetchone()
        # BY NAME, because the two logs' column types need not agree: the
        # conditions leg's lands through Python rows (load_warehouse()), so a
        # column null on every row there is INTEGER, which DuckDB widens to
        # this one's type.
        runs_table = f"{quote_identifier(schema)}.{quote_identifier(RUNS_TABLE)}"
        union = f"SELECT * FROM {runs_table} UNION ALL BY NAME " if exists else ""
        con.execute(f"CREATE OR REPLACE TABLE {runs_table} AS {union}SELECT * FROM _runs")
        con.unregister("_runs")
    return ServedRead(run_id, newest, loaded, problems)


def served_run_at(run_id: str) -> datetime | None:
    """The instant a copy's run began, from its run id (extract/_run.py's run_pipeline() stamps one from the other),
    or None for a name no run gave."""
    try:
        return datetime.strptime(run_id, "%Y%m%dT%H%M%S.%fZ").replace(tzinfo=UTC)
    except ValueError:
        return None


def served_age(run_id: str, now: datetime) -> timedelta | None:
    """How long before `now` a copy's run began; None when its run id says no time. Never below zero."""
    run_at = served_run_at(run_id)
    return None if run_at is None else max(timedelta(0), now - run_at)


def _hours_minutes(age: timedelta | None) -> str:
    if age is None:
        return "an unknown time"
    minutes = int(age.total_seconds() // 60)
    return f"{minutes // 60} h {minutes % 60:02d} min"


def is_stale(age: timedelta | None) -> bool:
    """Past SERVED_STALE_HOURS, or of no known age: an unknown is held to the stricter rule."""
    return age is None or age > timedelta(hours=SERVED_STALE_HOURS)


def copy_due_since(load_ids: set[str]) -> datetime | None:
    """When a leg with no served copy began to owe one: its first committed load, from the Unix time dlt writes as each
    load id (dlt 1.30.0's create_load_id()); None when it has committed none, or no id says a time."""
    instants = []
    for load_id in load_ids:
        try:
            instants.append(datetime.fromtimestamp(float(load_id), UTC))
        except (ValueError, OverflowError, OSError):
            continue
    return min(instants, default=None)


def _committed_loads(pipeline) -> set[str]:
    """committed_load_ids(), or none on a store nothing has been written to yet."""
    try:
        return committed_load_ids(pipeline)
    except FileNotFoundError:
        return set()


def served_summary(
    leg: str,
    read: ServedRead | None,
    failure: BaseException | None = None,
    now: datetime | None = None,
    due_since: datetime | None = None,
) -> str:
    """add-served's evidence, as Markdown, for `$GITHUB_STEP_SUMMARY`. `due_since` is copy_due_since()'s answer for a
    leg with no copy."""
    lines = [f"### The served copy: `{leg}`", ""]
    if read is None:
        lines += [f"**Not read**, so this build has none of its tables: `{type(failure).__name__}: {failure}`", ""]
    elif read.run_id is None:
        lines += ["**No copy has been written yet**, so this build has none of its tables.", ""]
        owed = None if due_since is None else max(timedelta(0), (now or datetime.now(UTC)) - due_since)
        if due_since is None:
            lines += ["The leg has never committed a run, so nothing says since when it has owed one.", ""]
        else:
            lines += [
                f"Its first committed run was `{due_since:%Y-%m-%dT%H:%M:%SZ}`, {_hours_minutes(owed)} before this read.",
                "",
            ]
        if is_stale(owed):
            lines += [f"**Overdue past {SERVED_STALE_HOURS} h** (SERVED_STALE_HOURS), so the run turns red at the end.", ""]
    else:
        which = "the newest" if read.newest else "**an older copy**, because the newest could not be read"
        lines += [f"Copy `{read.run_id}`, {which}: {len(read.loaded)} tables, {sum(read.loaded.values())} rows.", ""]
        age = served_age(read.run_id, now or datetime.now(UTC))
        run_at = served_run_at(read.run_id)
        began = f"`{run_at:%Y-%m-%dT%H:%M:%SZ}`" if run_at else "at no time its run id says"
        lines += [f"Its run began {began}, {_hours_minutes(age)} before this read.", ""]
        if is_stale(age):
            lines += [f"**Older than {SERVED_STALE_HOURS} h** (SERVED_STALE_HOURS), so the run turns red at the end.", ""]
    if read is not None and read.problems:
        lines += ["**Could not be read:**", "", *[f"- {problem}" for problem in read.problems], ""]
    return "\n".join(lines) + "\n"


# --- A pinned raw_run (the module docstring, "A PINNED RAW_RUN") ---

RAW_INPUTS_PREFIX = "raw_inputs"
#: Written last: a pin without it is a pin that did not finish, and is never read.
PIN_MANIFEST = "raw_inputs.json"
#: A run that ended either way may not be pinned: its loads are not what the
#: run check passed (extract/_run.py's run_check and committed()). A table an
#: isolating run left out on its own logs `refused` too, and does not stop
#: the pin: it loaded nothing that run, and its last committed load is what
#: the pin holds (left_out_on_its_own()). Monthly run 16
#: (refresh-reference.yml 37210020925) extracted in 112 minutes, left some
#: layers out, and its pin refused the whole run on their rows.
UNPINNABLE_OUTCOMES = ("refused", "unverified")
CHUNK = 1 << 20


def raw_inputs_root(steps_url: str, raw_run: str) -> str:
    """`<steps-url>/raw_inputs/<raw_run>`, as the raw store's filesystem client names it."""
    if not raw_run or "/" in raw_run or raw_run in (".", ".."):
        raise ValueError(f"{raw_run!r} is not a raw_run; it is one extract run's run_id")
    return f"{fs_path(steps_url)}/{RAW_INPUTS_PREFIX}/{raw_run}"


def _same_bucket(bucket_url: str, steps_url: str) -> None:
    """The step cache shares the raw store's bucket and key (decision 43), so its paths go through the same client."""
    raw, steps = urlsplit(bucket_url), urlsplit(steps_url)
    local = ("", "file")
    if (raw.scheme in local) != (steps.scheme in local) or (raw.scheme not in local and raw.netloc != steps.netloc):
        raise ValueError(f"{steps_url} is not in the raw store's bucket ({bucket_url}); one key reads both (decision 43)")


def _sha256(fs, path: str) -> str:
    digest = hashlib.sha256()
    with fs.open(path, "rb") as handle:
        while chunk := handle.read(CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def has_pin(pipeline, steps_url: str, raw_run: str) -> bool:
    return _client(pipeline).fs_client.exists(f"{raw_inputs_root(steps_url, raw_run)}/{PIN_MANIFEST}")


def read_pin(pipeline, steps_url: str, raw_run: str) -> dict:
    """The pin's manifest. Refuses when there is none, rather than reading current raw in its place."""
    path = f"{raw_inputs_root(steps_url, raw_run)}/{PIN_MANIFEST}"
    fs = _client(pipeline).fs_client
    if not fs.exists(path):
        raise BuildRefused(
            f"no pinned raw inputs for raw_run {raw_run} ({path}): the pin was never written, or has been purged. "
            "Refusing rather than building from whatever the raw store holds now."
        )
    with fs.open(path, "r") as handle:
        return json.load(handle)


def as_landed_tables() -> set[str]:
    """The tables whose resource writes an as-landed file (extract/_run.py's as_landed_path()), from discover()."""
    from extract._contract import all_resources, discover, discover_shared

    return {resource.table for resource in all_resources(discover() + discover_shared()) if as_landed_path(resource)}


def _landed_path(fs, bucket_url: str, table: str, load_id: str, indexes: dict, landed_tables) -> str | None:
    """The table's as-landed path in its load's index; refuses one of `landed_tables` whose load wrote none."""
    path = as_landed_index(fs, bucket_url, load_id, indexes).get(table)
    if path is None and table in (landed_tables or ()):
        raise BuildRefused(
            f"{table}: load {load_id} wrote no as-landed file, and the build reads one; "
            "the next --as-landed extract reads it again"
        )
    return path


def pin_raw_inputs(
    pipeline,
    bucket_url: str,
    steps_url: str,
    raw_run: str,
    extras: dict[str, Path] | None = None,
    *,
    landed_tables: set[str] | None = None,
) -> tuple[dict, bool]:
    """Copy what a build of `raw_run` reads to `<steps-url>/raw_inputs/<raw_run>/`. Returns (manifest, whether this call wrote it).

    WRITE-ONCE. An existing pin is the answer, never overwritten: a rerun of
    refresh-reference.yml's pin job finds the pin its first attempt wrote,
    and every build of that raw_run reads it, as the promotion will.
    `extras` are other files the build read that no dlt table
    holds, by their path under data/raw/ (the DEM tile index
    fetch_elevation.py writes), pinned beside the as-landed copies. A table
    in `landed_tables` (as_landed_tables(), from the command line) whose
    load wrote no as-landed file refuses the pin.
    """
    _same_bucket(bucket_url, steps_url)
    fs = _client(pipeline).fs_client
    root = raw_inputs_root(steps_url, raw_run)
    if fs.exists(f"{root}/{PIN_MANIFEST}"):
        return read_pin(pipeline, steps_url, raw_run), False
    log = [row for row in run_log_rows(pipeline) if row["run_id"] <= raw_run]
    this_run = [row for row in log if row["run_id"] == raw_run]
    if not this_run:
        raise BuildRefused(f"_extract_runs holds no run {raw_run}, so there is nothing to pin")
    ended = sorted({row["outcome"] for row in this_run if not left_out_on_its_own(row)} & set(UNPINNABLE_OUTCOMES))
    if ended:
        raise BuildRefused(f"run {raw_run} ended {', '.join(ended)}; a run the checks did not pass is never pinned")
    by_load = {(row["table_name"], row.get("load_id")): row for row in log}
    tables: dict[str, dict] = {}
    committed = committed_tables(pipeline, as_of=raw_run)
    # Every name before anything is listed or written (the note above _stored_table()): each becomes a store path.
    for table in committed:
        _stored_table(table, "the run log (_extract_runs)")
    for table, load_id in sorted(committed.items()):
        files = table_files(pipeline, table, load_id)
        if not files:
            row = by_load.get((table, load_id)) or {}
            if proven_zero(row):
                tables[table] = {"load_id": load_id, "rows": 0, "file": None, "column_hints": json.loads(row["column_hints"])}
                continue
            raise BuildRefused(f"{table}: no committed file from load {load_id}; refusing rather than pinning it as empty")
        arrow = pa.concat_tables([pq.read_table(fs.open(path)) for path in files], promote_options="permissive")
        relative = f"tables/{table}.parquet"
        fs.makedirs(f"{root}/tables", exist_ok=True)
        with fs.open(f"{root}/{relative}", "wb") as handle:
            pq.write_table(arrow, handle, compression="zstd")
        tables[table] = {
            "load_id": load_id,
            "rows": arrow.num_rows,
            "file": relative,
            "sha256": _sha256(fs, f"{root}/{relative}"),
            "source_files": [os.path.basename(path) for path in files],
        }

    landed: dict[str, dict] = {}
    indexes: dict[str, dict] = {}
    for table, entry in tables.items():
        path = _landed_path(fs, bucket_url, table, entry["load_id"], indexes, landed_tables)
        if path is None:
            continue
        # Read under <bucket>/as_landed/<load_id>/ and written under the pin's as_landed/: neither may be left.
        _stored_path(f"{entry['load_id']}/{path}", f"load {entry['load_id']}'s as-landed {AS_LANDED_INDEX}")
        target = f"{root}/{AS_LANDED_PREFIX}/{path}"
        fs.makedirs(os.path.dirname(target), exist_ok=True)
        fs.copy(f"{fs_path(bucket_url)}/{AS_LANDED_PREFIX}/{entry['load_id']}/{path}", target)
        landed[path] = {"table": table, "load_id": entry["load_id"], "sha256": _sha256(fs, target)}
    for path, local in sorted((extras or {}).items()):
        target = f"{root}/{AS_LANDED_PREFIX}/{path}"
        fs.makedirs(os.path.dirname(target), exist_ok=True)
        fs.put_file(str(local), target)
        landed[path] = {"table": None, "load_id": None, "sha256": _sha256(fs, target)}

    fs.makedirs(root, exist_ok=True)  # a pin of proven zeros alone has written no table file to make it
    with fs.open(f"{root}/{RUNS_TABLE}.parquet", "wb") as handle:
        pq.write_table(pa.Table.from_pylist(log), handle, compression="zstd")
    manifest = {
        "raw_run": raw_run,
        "lane": this_run[0].get("pipeline"),
        "pinned_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tables": tables,
        "as_landed": landed,
        "extract_runs": {
            "file": f"{RUNS_TABLE}.parquet",
            "rows": len(log),
            "sha256": _sha256(fs, f"{root}/{RUNS_TABLE}.parquet"),
        },
    }
    with fs.open(f"{root}/{PIN_MANIFEST}", "w") as handle:
        handle.write(json.dumps(manifest, indent=2, sort_keys=True))
    return manifest, True


def _verified(fs, path: str, sha256: str) -> str:
    if _sha256(fs, path) != sha256:
        raise BuildRefused(f"{path} does not match the sha256 its pin recorded; refusing a pin that changed")
    return path


def load_pinned(con: duckdb.DuckDBPyConnection, pipeline, steps_url: str, raw_run: str, schema: str = "raw") -> dict[str, int]:
    """Build the warehouse's `schema` from a pin alone, as load_warehouse builds it from the committed loads. Returns {table: rows}."""
    manifest = read_pin(pipeline, steps_url, raw_run)
    fs = _client(pipeline).fs_client
    root = raw_inputs_root(steps_url, raw_run)
    # Every name and path before anything is read or created (the note above _stored_table()).
    where = f"pin {raw_run}'s {PIN_MANIFEST}"
    for table, entry in manifest["tables"].items():
        _stored_table(table, where)
        if entry.get("file") is not None:
            _stored_path(entry["file"], where)
    runs = manifest["extract_runs"]
    _stored_path(runs["file"], where)
    con.execute(f"CREATE SCHEMA IF NOT EXISTS {quote_identifier(schema)}")
    loaded: dict[str, int] = {}
    for table, entry in sorted(manifest["tables"].items()):
        if entry.get("file") is None:
            _create_proven_empty(con, schema, table, entry["column_hints"], pipeline)
            loaded[table] = 0
            continue
        path = _verified(fs, f"{root}/{entry['file']}", entry["sha256"])
        arrow = pq.read_table(fs.open(path))
        con.register("_pinned", arrow)
        con.execute(f"CREATE OR REPLACE TABLE {quote_identifier(schema)}.{quote_identifier(table)} AS SELECT * FROM _pinned")
        con.unregister("_pinned")
        loaded[table] = arrow.num_rows
    arrow = pq.read_table(fs.open(_verified(fs, f"{root}/{runs['file']}", runs["sha256"])))
    if arrow.num_rows:
        con.register("_runs", arrow)
        con.execute(f"CREATE OR REPLACE TABLE {quote_identifier(schema)}.{quote_identifier(RUNS_TABLE)} AS SELECT * FROM _runs")
        con.unregister("_runs")
    return loaded


def materialize_pinned(pipeline, steps_url: str, raw_run: str, raw_dir: Path) -> list[str]:
    """Write the pin's as-landed files (and extras) under `raw_dir`, at today's fetchers' paths. Returns the paths."""
    manifest = read_pin(pipeline, steps_url, raw_run)
    fs = _client(pipeline).fs_client
    root = raw_inputs_root(steps_url, raw_run)
    # Every path before any file is written, so a pin naming one that leaves raw_dir writes nothing at all.
    for path in manifest["as_landed"]:
        _stored_path(path, f"pin {raw_run}'s {PIN_MANIFEST}")
    written = []
    for path, entry in sorted(manifest["as_landed"].items()):
        source = _verified(fs, f"{root}/{AS_LANDED_PREFIX}/{path}", entry["sha256"])
        target = raw_dir / path
        target.parent.mkdir(parents=True, exist_ok=True)
        fs.get_file(source, str(target))
        written.append(path)
    return written


def materialize_committed(
    pipeline, bucket_url: str, raw_run: str, raw_dir: Path, *, landed_tables: set[str] | None = None
) -> list[str]:
    """Before a pin exists: the as-landed files of each table's committed load as of `raw_run`, under `raw_dir`.

    For the steps that read today's fetchers' files to make an input the pin
    then holds (fetch_elevation.py's tile index, from centerline.geojson).
    `landed_tables` refuses as pin_raw_inputs() does.
    """
    fs = _client(pipeline).fs_client
    indexes: dict[str, dict] = {}
    # Every path before any file is written (as materialize_pinned()): read under <bucket>/as_landed/<load_id>/ and
    # written under raw_dir, neither of which it may leave.
    found = []
    for table, load_id in sorted(committed_tables(pipeline, as_of=raw_run).items()):
        path = _landed_path(fs, bucket_url, table, load_id, indexes, landed_tables)
        if path is not None:
            _stored_path(f"{load_id}/{path}", f"load {load_id}'s as-landed {AS_LANDED_INDEX}")
            found.append((load_id, path))
    written = []
    for load_id, path in found:
        target = raw_dir / path
        target.parent.mkdir(parents=True, exist_ok=True)
        fs.get_file(f"{fs_path(bucket_url)}/{AS_LANDED_PREFIX}/{load_id}/{path}", str(target))
        written.append(path)
    return written


def _step_key(key: str) -> str:
    """`key`, or ValueError: lib/store_names.py's relative_path(), the rule that began here."""
    try:
        return relative_path(key, "the step-cache key")
    except StoreNameRefused as refused:
        raise ValueError(f"{key!r} is not a step-cache key") from refused


def store_once(pipeline, bucket_url: str, steps_url: str, key: str, files: list[Path]) -> list[str]:
    """Put each file under `<steps-url>/<key>/`, write-once. Returns what it wrote: [] when every file is already there.

    A rerun of the build that stored them finds them all, keeps the first
    attempt's (the step cache is write-once) and says so. Some there and some
    not is a torn earlier write, and is refused rather than completed with
    files from another build.
    """
    _same_bucket(bucket_url, steps_url)
    fs = _client(pipeline).fs_client
    root = f"{fs_path(steps_url)}/{_step_key(key)}"
    targets = [f"{root}/{local.name}" for local in files]
    present = [target for target in targets if fs.exists(target)]
    if present and len(present) == len(targets):
        return []
    if present:
        raise BuildRefused(f"part of {root} is already in the step cache ({', '.join(present)}); refusing to complete it")
    fs.makedirs(root, exist_ok=True)
    for local, target in zip(files, targets, strict=True):
        fs.put_file(str(local), target)
    return targets


def fetch_stored(pipeline, steps_url: str, key: str, names: list[str], out: Path) -> list[Path]:
    """Copy `<steps-url>/<key>/<name>` for each name into `out`. Refuses a name that is not there."""
    fs = _client(pipeline).fs_client
    root = f"{fs_path(steps_url)}/{_step_key(key)}"
    if missing := [name for name in names if not fs.exists(f"{root}/{name}")]:
        raise BuildRefused(f"not in the step cache under {root}: {', '.join(missing)}")
    out.mkdir(parents=True, exist_ok=True)
    fetched = []
    for name in names:
        fs.get_file(f"{root}/{name}", str(out / name))
        fetched.append(out / name)
    return fetched


def _leg_command(args) -> int:
    """`serve` and `add-served`, on the tables the leg's job reads now (extract/_run.py's leg_tables())."""
    from extract._contract import all_resources, discover, discover_shared
    from extract._run import leg_tables

    bucket_url = args.bucket_url or raw_store_url(args.raw_bucket, args.lane)
    pipeline = make_pipeline(args.lane, bucket_url, args.pipelines_dir)
    tables = leg_tables(args.lane, all_resources(discover() + discover_shared()))

    def summarise(text: str) -> None:
        if args.summary is not None:
            with open(args.summary, "a", encoding="utf-8") as handle:
                handle.write(text)

    if args.command == "serve":
        written = write_served_copy(pipeline, bucket_url, tables, args.run_log_cache)
        manifest = written.manifest
        rows = sum(entry["rows"] for entry in manifest["tables"].values())
        verb = "copied" if written.wrote else "was already copied, so it was read back and not rewritten:"
        line = f"{args.lane} run {manifest['run_id']} {verb} {len(manifest['tables'])} tables, {rows} rows, for the hourly build"
        print(line)
        for problem in written.problems:
            print(f"::error title=A table was not copied from the store::{problem}")
        summarise(
            f"### The served copy: `{args.lane}`\n\n{line}\n\n"
            + "".join(f"- {problem}\n" for problem in written.problems)
            + ("\n" if written.problems else "")
        )
        return PARTIAL_EXIT if written.problems else 0
    try:
        with duckdb.connect(str(args.warehouse)) as con:
            read = load_served(con, pipeline, bucket_url, tables)
    except BuildRefused as refused:
        summarise(served_summary(args.lane, None, refused))
        raise
    now = datetime.now(UTC)
    due = copy_due_since(_committed_loads(pipeline)) if read.run_id is None else None
    summarise(served_summary(args.lane, read, now=now, due_since=due))
    if read.run_id is None:
        owed = None if due is None else max(timedelta(0), now - due)
        if due is None:
            print(
                f"::error title=No notices copy::{args.lane} has never committed a run, so it has no served copy and "
                "nothing says since when one is owed: this build has none of its tables, everything else is published, "
                "and the run turns red at the end. extract-notices.yml's leg for this environment has not run, or no "
                "run of it has committed."
            )
            return SERVED_OVERDUE_EXIT
        if is_stale(owed):
            print(
                f"::error title=No notices copy::{args.lane} has written no served copy, and its first committed run was "
                f"{_hours_minutes(owed)} before this read, past SERVED_STALE_HOURS ({SERVED_STALE_HOURS} h): this build "
                "has none of its tables, everything else is published, and the run turns red at the end. Look at "
                "extract-notices.yml's copy step."
            )
            return SERVED_OVERDUE_EXIT
        print(
            f"::warning title=No served copy yet::{args.lane} has written no copy yet, so this build has none of its "
            f"tables. Its first committed run was {_hours_minutes(owed)} before this read, and this turns the run red "
            f"once that is over {SERVED_STALE_HOURS} h (SERVED_STALE_HOURS)."
        )
        return SERVED_NONE_EXIT
    age = served_age(read.run_id, now)
    run_at = served_run_at(read.run_id)
    if args.env_file is not None and run_at is not None:
        with open(args.env_file, "a", encoding="utf-8") as handle:
            handle.write(f"{NOTICES_READ_AT_ENV}={run_at:%Y-%m-%dT%H:%M:%S.%fZ}\n")
    print(
        f"{len(read.loaded)} tables, {sum(read.loaded.values())} rows, from {args.lane}'s copy {read.run_id}, "
        f"whose run began {_hours_minutes(age)} before this read, into {args.warehouse}"
    )
    if not read.newest:
        print(
            f"::error title=An older served copy was read::{args.lane}'s newest copy could not be read, so this build has "
            f"its last good rows, from copy {read.run_id}: {'; '.join(read.problems)}"
        )
        return SERVED_OLDER_EXIT
    if is_stale(age):
        print(
            f"::error title=The notices copy is stale::{args.lane}'s newest copy, {read.run_id}, began its run "
            f"{_hours_minutes(age)} before this read, past SERVED_STALE_HOURS ({SERVED_STALE_HOURS} h): it is added and "
            "published, and the run turns red at the end. extract-notices.yml has written no copy since."
        )
        return SERVED_STALE_EXIT
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="The raw store into the warehouse, and a raw_run's pin (this module's docstring)."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    def add(name: str, help_: str, pinned: bool = True) -> argparse.ArgumentParser:
        command = commands.add_parser(name, help=help_)
        command.add_argument("--lane", required=True, choices=sorted(LANES))
        command.add_argument("--bucket-url", required=True, help="the lane's raw store, as extract/_run.py was given it")
        command.add_argument("--pipelines-dir", help="dlt's working directory (default: dlt's own)")
        if pinned:
            command.add_argument("--steps-url", required=True, help="the step cache: <bucket>/steps (decision 43)")
            command.add_argument("--raw-run", required=True, help="the extract run's run_id")
        return command

    add("has-pin", "exit 0 when the raw_run is pinned, 1 when it is not")
    pin = add("pin", "pin the raw_run's committed tables, run log and as-landed files (write-once)")
    pin.add_argument(
        "--extra", action="append", default=[], metavar="PATH=FILE", help="another input, by its path under data/raw/"
    )
    load = add("load", "build the warehouse, and/or data/raw/'s as-landed files, from a pin alone")
    load.add_argument("--warehouse", type=Path)
    load.add_argument("--raw-dir", type=Path, help="write the pin's as-landed files here, at today's fetchers' paths")
    landed = add("as-landed", "before the pin: the committed loads' as-landed files as of the raw_run, into --raw-dir")
    landed.add_argument("--raw-dir", type=Path, required=True)
    current = add("load-committed", "the committed loads, unpinned, into --warehouse", pinned=False)
    current.add_argument("--warehouse", type=Path, required=True)
    store = add("store", "put files under <steps-url>/<key>/, write-once", pinned=False)
    store.add_argument("--steps-url", required=True)
    store.add_argument("--key", required=True)
    store.add_argument("files", nargs="+", type=Path)
    fetch = add("fetch", "copy named files from <steps-url>/<key>/ into --out", pinned=False)
    fetch.add_argument("--steps-url", required=True)
    fetch.add_argument("--key", required=True)
    fetch.add_argument("--out", type=Path, required=True)
    fetch.add_argument("names", nargs="+")

    def add_leg(name: str, help_: str) -> argparse.ArgumentParser:
        command = commands.add_parser(name, help=help_)
        command.add_argument("--lane", required=True, choices=sorted(LEGS), help="the leg whose store this reads")
        where = command.add_mutually_exclusive_group(required=True)
        where.add_argument("--bucket-url", help="the leg's raw store, as extract/_run.py was given it")
        where.add_argument("--raw-bucket", help="the private raw bucket's name, as R2_RAW_BUCKET holds it")
        command.add_argument("--pipelines-dir", help="dlt's working directory (default: dlt's own)")
        command.add_argument("--summary", type=Path, help="append what was copied or read, as Markdown, to this file")
        return command

    serve = add_leg("serve", "after a leg's run: copy what a build reads of it under <bucket-url>/served/<run_id>/ (write-once)")
    serve.add_argument(
        "--run-log-cache", type=Path, help="the extract step's --run-log-cache: run log files read there, not from the store"
    )
    served = add_leg("add-served", "add a leg's newest readable served copy to --warehouse, beside what is there")
    served.add_argument("--warehouse", type=Path, required=True)
    served.add_argument(
        "--env-file", type=Path, help=f"append {NOTICES_READ_AT_ENV}=<when the copy's run began> here ($GITHUB_ENV)"
    )
    args = parser.parse_args(argv)

    if args.command in ("serve", "add-served"):
        return _leg_command(args)
    pipeline = make_pipeline(args.lane, args.bucket_url, args.pipelines_dir)
    if args.command == "has-pin":
        found = has_pin(pipeline, args.steps_url, args.raw_run)
        where = raw_inputs_root(args.steps_url, args.raw_run)
        print(f"raw_run {args.raw_run}: {'pinned' if found else 'not pinned'} under {where}")
        return 0 if found else 1
    if args.command == "pin":
        extras = {}
        for item in args.extra:
            path, _, local = item.partition("=")
            if not path or not local:
                parser.error(f"--extra takes PATH=FILE, not {item!r}")
            extras[path] = Path(local)
        manifest, wrote = pin_raw_inputs(
            pipeline, args.bucket_url, args.steps_url, args.raw_run, extras, landed_tables=as_landed_tables()
        )
        rows = sum(entry["rows"] for entry in manifest["tables"].values())
        verb = "pinned" if wrote else "was already pinned, so it was read back and not rewritten:"
        print(
            f"raw_run {args.raw_run} {verb} {len(manifest['tables'])} tables, {rows} rows, "
            f"{len(manifest['as_landed'])} as-landed files"
        )
        return 0
    if args.command == "load":
        if args.warehouse is None and args.raw_dir is None:
            parser.error("load needs --warehouse, --raw-dir or both")
        if args.raw_dir is not None:
            written = materialize_pinned(pipeline, args.steps_url, args.raw_run, args.raw_dir)
            print(f"{len(written)} as-landed files from raw_run {args.raw_run} into {args.raw_dir}")
        if args.warehouse is not None:
            with duckdb.connect(str(args.warehouse)) as con:
                counts = load_pinned(con, pipeline, args.steps_url, args.raw_run)
            print(f"{len(counts)} tables, {sum(counts.values())} rows, from raw_run {args.raw_run} into {args.warehouse}")
        return 0
    if args.command == "as-landed":
        written = materialize_committed(pipeline, args.bucket_url, args.raw_run, args.raw_dir, landed_tables=as_landed_tables())
        print(f"{len(written)} as-landed files as of raw_run {args.raw_run} into {args.raw_dir}")
        return 0
    if args.command == "load-committed":
        with duckdb.connect(str(args.warehouse)) as con:
            counts = load_warehouse(con, pipeline)
        print(f"{len(counts)} tables, {sum(counts.values())} rows, from the committed loads into {args.warehouse}")
        return 0
    if args.command == "fetch":
        fetched = fetch_stored(pipeline, args.steps_url, args.key, args.names, args.out)
        print("fetched: " + ", ".join(str(path) for path in fetched))
        return 0
    targets = store_once(pipeline, args.bucket_url, args.steps_url, args.key, args.files)
    if targets:
        print("stored: " + ", ".join(targets))
    else:
        print(f"::warning title=already stored::{args.key} was stored by an earlier attempt; kept as it is (write-once)")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BuildRefused as refused:
        print(refused, file=sys.stderr)
        sys.exit(1)
