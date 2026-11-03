"""The warehouse's `derived` schema: the tables the Python steps (step_*.py) write for dbt to read."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

import duckdb

SCHEMA = "derived"


def replace_table(con: duckdb.DuckDBPyConnection, table: str, columns: Sequence[tuple[str, str]], rows: Iterable[tuple]) -> int:
    """Replace derived.<table> with `rows`, under `columns` as (name, SQL type) pairs. Returns the row count.

    No rows is an empty table, not an error: executemany refuses an empty list, so it is skipped."""
    con.execute(f"create schema if not exists {SCHEMA}")
    declared = ", ".join(f"{name} {kind}" for name, kind in columns)
    con.execute(f"create or replace table {SCHEMA}.{table} ({declared})")
    rows = list(rows)
    if rows:
        marks = ", ".join("?" for _ in columns)
        con.executemany(f"insert into {SCHEMA}.{table} values ({marks})", rows)
    return con.execute(f"select count(*) from {SCHEMA}.{table}").fetchone()[0]
