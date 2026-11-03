"""Archive closed months' unlinked usage rows to R2 as Parquet, and retire expired months (#1923).

    DATABASE_URL=<the archive role's URL> \\
    USAGE_ARCHIVE_R2_ENDPOINT_URL=... USAGE_ARCHIVE_R2_BUCKET=... \\
    USAGE_ARCHIVE_R2_ACCESS_KEY_ID=... USAGE_ARCHIVE_R2_SECRET_ACCESS_KEY=... \\
    python scripts/analytics_archive.py

What a run does, and why a row is always in exactly one place, is
app/core/analytics_archive.py's docstring. This file is the command around
it, and the one place pyarrow is imported for writing: each part is zstd
Parquet, typed from the `analytics_events` model (`arrow_schema`), so a column
added to the table later - #1885's `support_cents` is the first - is archived
without a change here, and a column of a type with no Parquet mapping stops
the run rather than archiving it as text nobody chose.

It prints what was done as month and part names - never a row and never a
count, because Actions logs on this repository are public and a month's row
count is its traffic. A failed run exits 1 and names what failed
(app/core/logs.py `describe_failure`), never a traceback. `--today` later
than the real UTC date is refused with exit 2 before anything runs: it decides
which months' files are past retention, and those are deleted for real.

Run nightly by .github/workflows/analytics-rollup.yml before the rollup. Safe
to run by hand and to run twice.
"""

from __future__ import annotations

import argparse
import enum
import json
import sys
from collections.abc import Iterable
from datetime import date
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from sqlalchemy import JSON, Boolean, Date, DateTime, Float, Integer, LargeBinary, Numeric, SmallInteger, String

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.analytics_archive import ArchiveError, R2Store, run  # noqa: E402
from app.core.analytics_rollup import retention_start  # noqa: E402
from app.core.logs import describe_failure  # noqa: E402
from app.core.time import utc_now  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models.analytics import AnalyticsEvent  # noqa: E402


def _arrow_type(column) -> pa.DataType:
    """The Parquet type for one column of `analytics_events`. Most specific SQLAlchemy type first:
    `SmallInteger` is an `Integer`, `Float` is a `Numeric`, and an `Enum` is a `String`."""
    kind = column.type
    if isinstance(kind, Boolean):
        return pa.bool_()
    if isinstance(kind, String):
        return pa.string()
    if isinstance(kind, DateTime):
        return pa.timestamp("us")
    if isinstance(kind, Date):
        return pa.date32()
    if isinstance(kind, SmallInteger):
        return pa.int16()
    if isinstance(kind, Integer):
        return pa.int64()
    if isinstance(kind, Float):
        return pa.float64()
    if isinstance(kind, Numeric):
        return pa.decimal128(kind.precision, kind.scale)
    if isinstance(kind, JSON):
        return pa.string()
    if isinstance(kind, LargeBinary):
        return pa.binary()
    raise ArchiveError(f"analytics_events.{column.name} is a {type(kind).__name__}, which has no Parquet type here")


def arrow_schema() -> pa.Schema:
    """Every column of `analytics_events`, in the table's order."""
    return pa.schema([pa.field(column.name, _arrow_type(column), nullable=True) for column in AnalyticsEvent.__table__.columns])


def _value(value, field: pa.Field):
    """A row's value as the file stores it: an enum by its name, JSON as compact text, binary as bytes."""
    if value is None:
        return None
    if isinstance(value, enum.Enum):
        return value.value
    if pa.types.is_string(field.type) and not isinstance(value, str):
        return json.dumps(value, separators=(",", ":"))
    if pa.types.is_binary(field.type):
        return bytes(value)
    return value


def _record_batch(rows: list[dict], schema: pa.Schema) -> pa.RecordBatch:
    columns = [pa.array([_value(row[field.name], field) for row in rows], type=field.type) for field in schema]
    return pa.RecordBatch.from_arrays(columns, schema=schema)


def write_parquet(batches: Iterable[list[dict]]) -> bytes:
    """One part's bytes: every batch, in the order given, zstd-compressed."""
    schema = arrow_schema()
    sink = pa.BufferOutputStream()
    with pq.ParquetWriter(sink, schema, compression="zstd") as writer:
        for rows in batches:
            if rows:
                writer.write_batch(_record_batch(rows, schema))
    return sink.getvalue().to_pybytes()


def read_parquet(body: bytes) -> list[dict]:
    """A part's rows, as `write_parquet` was handed them less the enums: what `open` and the tests read."""
    return pq.read_table(pa.BufferReader(body)).to_pylist()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--today",
        type=date.fromisoformat,
        default=None,
        help="Run as if today were this date (YYYY-MM-DD), never later than the real one.",
    )
    args = parser.parse_args(argv)

    real_today = utc_now().date()
    if args.today is not None and args.today > real_today:
        print(
            f"Refused: --today {args.today} is after today's UTC date, {real_today}. It decides which "
            "months' files are past retention, and those are deleted for real. Nothing was run.",
            file=sys.stderr,
        )
        return 2

    try:
        store = R2Store.from_env()
        with SessionLocal() as db:
            result = run(db, store, write_parquet, today=args.today)
    except Exception as failure:
        # Caught rather than left to print its traceback: this log is public.
        # Every month archived before the failure stays archived.
        print(f"The archive stopped: {describe_failure(failure)}", file=sys.stderr)
        if isinstance(failure, ArchiveError):
            print(f"  {failure}", file=sys.stderr)
        return 1

    today = args.today or real_today
    for month, part in result.archived:
        print(f"Archived {month:%Y-%m} as part {part}")
    if not result.archived:
        print("Nothing to archive: no closed month inside retention holds unlinked rows.")
    for month in result.retired:
        print(f"Deleted the archived files of {month:%Y-%m} (past retention)")
    print(f"Archived months are kept from {retention_start(today):%Y-%m-%d}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
