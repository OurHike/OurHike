"""Raw store -> the warehouse's `raw` schema, reading only what a committed load wrote.

load_raw.py's successor (pipeline/ELT.md, "Where data lands"), for the tables
pipeline/extract/ lands; load_raw.py keeps loading the rest until each club's
folder replaces its fetcher, and is deleted once this loads every table it did.

THE FILES ARE AN EXPLICIT LIST, NEVER A GLOB. For each table, the warehouse
reads the files of exactly one load: the one `_extract_runs` recorded as that
table's latest `loaded` run, and only when `_dlt_loads` records that load as
complete. A glob would also read the files an interrupted load left behind -
on plain Parquet a replace load that fails half-way leaves the new first file
beside nothing, so a closures table would read as one closure, or none, and
pass every check (ELT.md, "A full reload that cannot empty a safety table",
measured 2026-10-01). A table with no committed file refuses the build rather
than loading as empty, because "no closures" is a claim and a missing file is
not evidence for it.
"""

from __future__ import annotations

import json

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

from extract._run import INCOMPLETE, RUNS_TABLE, UNAVAILABLE, _client, committed_load_ids, run_log_rows, table_files


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


def _create_proven_empty(con, schema: str, table: str, hints: dict, pipeline) -> None:
    """An empty table with the columns its resource hinted, plus dlt's own, under dlt's naming.

    Only for a load the run log shows as a proven zero: no rows, and the
    upstream's own count read zero in the same run. dlt writes no file for a
    table's first load when it holds no rows (a later empty replace does write
    a zero-row file), so without this a closures layer that is empty the first
    time it is read would refuse the whole build. And for a table not yet
    loaded at all (not_yet_loaded()), which the annotation beside it names.
    """
    naming = pipeline.default_schema.naming
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


def committed_tables(pipeline, *, log: list[dict] | None = None, complete: set[str] | None = None) -> dict[str, str]:
    """{table: the load id holding its current rows}, from each table's latest `loaded` run that committed.

    A table whose latest run found it unavailable is withdrawn, whatever it
    loaded before: rows the reader can no longer see are not current, and an
    absent table is how the build says unknown (extract/_contract.py's
    Unavailable). `log` and `complete` are the run log and the committed load
    ids where the caller has read them already, since each is a read of
    every file under its prefix.
    """
    complete = committed_load_ids(pipeline) if complete is None else complete
    latest: dict[str, tuple[str, str]] = {}
    withdrawn: dict[str, str] = {}
    for row in run_log_rows(pipeline) if log is None else log:
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
    """{table: column hints} for each table a carrying read is still reading for the first time.

    A table whose resource answered Incomplete (extract/_contract.py) and has
    never committed a load, nor been withdrawn since: a first run on an empty
    raw store, reading ATC's trail-updates pages over several hours at their
    Crawl-delay. The hints are the latest incomplete row's.
    """
    log = run_log_rows(pipeline) if log is None else log
    latest: dict[str, tuple[str, dict]] = {}
    withdrawn: dict[str, str] = {}
    for row in log:
        table = row["table_name"]
        if row.get("outcome") == UNAVAILABLE:
            withdrawn[table] = max(withdrawn.get(table, ""), row["run_id"])
        elif row.get("outcome") == INCOMPLETE and row.get("column_hints") and table not in committed:
            if table not in latest or row["run_id"] > latest[table][0]:
                latest[table] = (row["run_id"], json.loads(row["column_hints"]))
    return {table: hints for table, (run_id, hints) in latest.items() if run_id > withdrawn.get(table, "")}


def load_warehouse(con: duckdb.DuckDBPyConnection, pipeline, schema: str = "raw") -> dict[str, int]:
    """Replace each extracted table in `schema` with its committed rows. Returns {table: rows}."""
    client = _client(pipeline)
    con.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
    loaded = {}
    log_rows = {(row["table_name"], row.get("load_id")): row for row in run_log_rows(pipeline)}
    for table, load_id in sorted(committed_tables(pipeline).items()):
        files = table_files(pipeline, table, load_id)
        if not files:
            row = log_rows.get((table, load_id)) or {}
            if row.get("rows") == 0 and row.get("count_proof") == 0 and row.get("column_hints") is not None:
                _create_proven_empty(con, schema, table, json.loads(row["column_hints"]), pipeline)
                loaded[table] = 0
                continue
            raise BuildRefused(f"{table}: no committed file from load {load_id}; refusing rather than reading it as empty")
        arrow = pa.concat_tables([pq.read_table(client.fs_client.open(path)) for path in files], promote_options="permissive")
        con.register("_committed", arrow)
        con.execute(f'CREATE OR REPLACE TABLE "{schema}"."{table}" AS SELECT * FROM _committed')
        con.unregister("_committed")
        loaded[table] = arrow.num_rows
    # NOT YET LOADED IS NOT A REFUSAL OF EVERYONE ELSE. A carrying read still
    # on its first pass has no committed file, and a missing table would stop
    # every model downstream of it, so every other club's closures with it.
    # It is created empty, from its own hints, and named in an annotation. For
    # ATC's trail-updates pages that publishes the reviewed rows without the
    # automatic ones, which is what export_atc_updates.py publishes today when
    # fetch_atc_updates.py's cache is missing ("A missing or unreadable cache
    # costs the auto-published rows and nothing else", its CACHE_PATH).
    for table, hints in sorted(not_yet_loaded(pipeline, committed_tables(pipeline)).items()):
        print(f"::warning title={table} not yet loaded::its first read is still in progress, so it is empty in this build")
        _create_proven_empty(con, schema, table, hints, pipeline)
        loaded[table] = 0
    log = run_log_rows(pipeline)
    if log:
        con.register("_runs", pa.Table.from_pylist(log))
        con.execute(f'CREATE OR REPLACE TABLE "{schema}"."{RUNS_TABLE}" AS SELECT * FROM _runs')
        con.unregister("_runs")
    return loaded
