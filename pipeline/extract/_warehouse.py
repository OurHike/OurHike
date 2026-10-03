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

A PINNED RAW_RUN (`pin`, `load --raw-run`; refresh-reference.yml's monthly
run) is a write-once copy, at `<steps-url>/raw_inputs/<raw_run>/`, of what a
build of one extract run (its `run_id`, the raw_run) reads: each table's
committed rows as of that run, its `_extract_runs` rows and its as-landed
files, `raw_inputs.json` last. The production promotion builds from it alone,
so it reads the rows UA verified rather than whatever the next `replace` left,
and an expired or purged pin stops it (ELT.md, "Storage tiers" and "Why a
scheduled run cannot reach production"). DuckLake replaces this for the
monthly tables at stage 3's first step, once its three go/no-go runs pass
(ELT.md, "DuckLake at phases 3 and 4").
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from itertools import islice
from pathlib import Path
from urllib.parse import urlsplit

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

from extract._run import (
    AS_LANDED_PREFIX,
    INCOMPLETE,
    ISOLATED_OUTCOME,
    LANES,
    RUNS_TABLE,
    UNAVAILABLE,
    _client,
    as_landed_index,
    as_landed_path,
    committed_load_ids,
    fs_path,
    make_pipeline,
    proven_zero,
    run_log_rows,
    table_files,
    table_listing,
)


class BuildRefused(RuntimeError):
    """A table the run log says exists has no committed file to read."""


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

    A build job starts from an empty dlt directory (refresh-reference.yml), and
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
    naming = _naming(pipeline)
    columns = {
        naming.normalize_identifier(name): DUCKDB_TYPES.get(hint.get("data_type"), "VARCHAR") for name, hint in hints.items()
    }
    # TIMESTAMPTZ, as dlt writes `_loaded_at` into every table it loads: a
    # naive UTC stamp lands `TIMESTAMP WITH TIME ZONE` (measured 2026-10-01,
    # dlt 1.30.0, filesystem destination, Parquet). An empty closures table is
    # a normal state, so its type must not differ from a full one's.
    columns.update({"_loaded_at": "TIMESTAMPTZ", "_dlt_load_id": "VARCHAR", "_dlt_id": "VARCHAR"})
    body = ", ".join(f'"{name}" {type_}' for name, type_ in columns.items())
    con.execute(f'CREATE OR REPLACE TABLE "{schema}"."{table}" ({body})')


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
    con: duckdb.DuckDBPyConnection, pipeline, schema: str = "raw", log: list[dict] | None = None, readers: int = 1
) -> dict[str, int]:
    """Replace each extracted table in `schema` with its committed rows. Returns {table: rows}.

    `log` is `_extract_runs` where the caller has read it already; it is read once otherwise.

    `readers` tables are read from the store at once, in a window that holds
    no more than that many tables' rows: one for the monthly lane, whose
    tables run to hundreds of megabytes and whose ninth run ran out of memory,
    and LEG_READERS for a conditions leg, whose 92 tables took about 55 s one
    after another in soak run 508 (publish-conditions.yml 37158027469). The
    files are listed once (table_listing()), and only this thread writes to
    `con`, so the window changes how long the read takes, never what lands.
    """
    client = _client(pipeline)
    con.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
    loaded = {}
    log = run_log_rows(pipeline) if log is None else log
    log_rows = {(row["table_name"], row.get("load_id")): row for row in log}
    committed = committed_tables(pipeline, log=log)
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
        con.execute(f'CREATE OR REPLACE TABLE "{schema}"."{table}" AS SELECT * FROM _committed')
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
        con.execute(f'CREATE OR REPLACE TABLE "{schema}"."{RUNS_TABLE}" AS SELECT * FROM _runs')
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


# --- A pinned raw_run (the module docstring, "A PINNED RAW_RUN") ---

RAW_INPUTS_PREFIX = "raw_inputs"
#: Written last: a pin without it is a pin that did not finish, and is never read.
PIN_MANIFEST = "raw_inputs.json"
#: A run that ended either way may not be pinned: its loads are not what the
#: run check passed (extract/_run.py's run_check and committed()).
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

    WRITE-ONCE. An existing pin is the answer, never overwritten: a rerun of a
    build job reads the pin its first attempt wrote, and so does the
    promotion. `extras` are other files the build read that no dlt table
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
    ended = sorted({row["outcome"] for row in this_run} & set(UNPINNABLE_OUTCOMES))
    if ended:
        raise BuildRefused(f"run {raw_run} ended {', '.join(ended)}; a run the checks did not pass is never pinned")
    by_load = {(row["table_name"], row.get("load_id")): row for row in log}
    tables: dict[str, dict] = {}
    for table, load_id in sorted(committed_tables(pipeline, as_of=raw_run).items()):
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
    con.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
    loaded: dict[str, int] = {}
    for table, entry in sorted(manifest["tables"].items()):
        if entry.get("file") is None:
            _create_proven_empty(con, schema, table, entry["column_hints"], pipeline)
            loaded[table] = 0
            continue
        path = _verified(fs, f"{root}/{entry['file']}", entry["sha256"])
        arrow = pq.read_table(fs.open(path))
        con.register("_pinned", arrow)
        con.execute(f'CREATE OR REPLACE TABLE "{schema}"."{table}" AS SELECT * FROM _pinned')
        con.unregister("_pinned")
        loaded[table] = arrow.num_rows
    runs = manifest["extract_runs"]
    arrow = pq.read_table(fs.open(_verified(fs, f"{root}/{runs['file']}", runs["sha256"])))
    if arrow.num_rows:
        con.register("_runs", arrow)
        con.execute(f'CREATE OR REPLACE TABLE "{schema}"."{RUNS_TABLE}" AS SELECT * FROM _runs')
        con.unregister("_runs")
    return loaded


def materialize_pinned(pipeline, steps_url: str, raw_run: str, raw_dir: Path) -> list[str]:
    """Write the pin's as-landed files (and extras) under `raw_dir`, at today's fetchers' paths. Returns the paths."""
    manifest = read_pin(pipeline, steps_url, raw_run)
    fs = _client(pipeline).fs_client
    root = raw_inputs_root(steps_url, raw_run)
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
    written = []
    for table, load_id in sorted(committed_tables(pipeline, as_of=raw_run).items()):
        path = _landed_path(fs, bucket_url, table, load_id, indexes, landed_tables)
        if path is None:
            continue
        target = raw_dir / path
        target.parent.mkdir(parents=True, exist_ok=True)
        fs.get_file(f"{fs_path(bucket_url)}/{AS_LANDED_PREFIX}/{load_id}/{path}", str(target))
        written.append(path)
    return written


def _step_key(key: str) -> str:
    if not key or key.startswith("/") or ".." in key.split("/"):
        raise ValueError(f"{key!r} is not a step-cache key")
    return key


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
    args = parser.parse_args(argv)

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
