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

from extract._run import RUNS_TABLE, UNAVAILABLE, _client, committed_load_ids, run_log_rows, table_files


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
    time it is read would refuse the whole build.
    """
    naming = pipeline.default_schema.naming
    columns = {
        naming.normalize_identifier(name): DUCKDB_TYPES.get(hint.get("data_type"), "VARCHAR") for name, hint in hints.items()
    }
    columns.update({"_loaded_at": "TIMESTAMP", "_dlt_load_id": "VARCHAR", "_dlt_id": "VARCHAR"})
    body = ", ".join(f'"{name}" {type_}' for name, type_ in columns.items())
    con.execute(f'CREATE OR REPLACE TABLE "{schema}"."{table}" ({body})')


def committed_tables(pipeline) -> dict[str, str]:
    """{table: the load id holding its current rows}, from each table's latest `loaded` run that committed.

    A table whose latest run found it unavailable is withdrawn, whatever it
    loaded before: rows the reader can no longer see are not current, and an
    absent table is how the build says unknown (extract/_contract.py's
    Unavailable).
    """
    complete = committed_load_ids(pipeline)
    latest: dict[str, tuple[str, str]] = {}
    withdrawn: dict[str, str] = {}
    for row in run_log_rows(pipeline):
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
    log = run_log_rows(pipeline)
    if log:
        con.register("_runs", pa.Table.from_pylist(log))
        con.execute(f'CREATE OR REPLACE TABLE "{schema}"."{RUNS_TABLE}" AS SELECT * FROM _runs')
        con.unregister("_runs")
    return loaded
