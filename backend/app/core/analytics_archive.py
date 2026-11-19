"""Move each closed month's unlinked usage rows out of Postgres and into R2 (#1923).

Six months of every usage row outgrows the 250 MB the intake gate allows
(`analytics_storage_ceiling_mb`) at roughly 300 to 540 phones a day. Poll 5
(2026-10-27) answered that by moving the cold half: once a month has closed,
its rows with no `user_key` leave `analytics_events` for a Parquet file in a
private R2 bucket. The rows linked to an account stay here to their six
months, so account deletion, unlinking and the export stay immediate and never
have to rewrite a file. The maintainer chose the rest by poll on 2026-10-29:
a database role of its own for this step, `ourhike_analytics_archive`, so the
rollup's role still cannot read `sealed`; one bucket per environment, each
with its own token; and a table of daily counts, so the readers that need
days which have left stay on Postgres (app/models/analytics.py
`AnalyticsArchivedDaily`).

WHAT A RUN DOES, IN THIS ORDER

1. **Retention.** A month before `retention_start(today)` loses every file
   under its prefix, its ledger rows are marked deleted, and its daily counts
   go - on the date line the rollup deletes that month's linked rows on.
2. **Archive.** For each closed month inside retention that still holds
   unlinked rows: take them all, every column, `sealed` included; write them
   as one zstd Parquet part sorted by date, event and platform (sorted, not in
   arrival order, which also removes the batch grouping #1903's review found
   through Postgres's `xmin`); upload it; and only once R2 holds it, in one
   transaction, record the part, add what its rows counted to the daily
   counts, and delete exactly those rows by id.

Run nightly by .github/workflows/analytics-rollup.yml BEFORE the rollup, so
the rollup's count of rows held (`_SNAPSHOT_HELD`) no longer counts what moved
and the intake ceiling frees up the same night. A month the rollup closes
tonight is archived tomorrow night.

WHY A ROW IS IN EXACTLY ONE PLACE

- **Nothing is deleted before the file is in R2.** A failed upload raises
  before the transaction opens, and the rows stay here for tomorrow.
- **Rows are deleted by id, never by the predicate that found them.** A late
  unlinked row for the same month can arrive between the read and the delete;
  deleting by "month, no user_key" would delete it without archiving it.
- **A run that dies after the upload and before the commit leaves a file with
  no ledger row.** The next run numbers its part from the ledger, so it writes
  the same part number again, over that file, with the same rows and any that
  arrived since. Nothing reads a part the ledger does not hold.
- **Two runs cannot interleave on a month.** Each month is read, uploaded,
  recorded and deleted inside one transaction that holds `ARCHIVE_LOCK`, and a
  run that cannot take the lock stops (`ArchiveBusy`) rather than wait to
  archive rows another run is moving. Held for a month, not for the night:
  the transaction stays open across that month's upload, a few seconds, and
  a run that dies mid-month rolls the month back whole.
- **A month's rows are streamed, not loaded.** At 3,000 phones a day a month
  can hold several hundred thousand unlinked rows; they reach the file in
  batches of `READ_BATCH`, so the job's memory is the file and the ids, not
  the rows.

Rows that arrive after a month's first part, or are unlinked after it
(app/core/analytics_accounts.py `forget_link` takes the `user_key` off), go
into part 2, 3 and on, in later runs.

Parquet is written by `scripts/analytics_archive.py`, the only importer of
pyarrow, which is installed by the nightly job and the tests and not by the
API's image (`backend/requirements-archive.in`). This module holds what the
database and the bucket see.
"""

from __future__ import annotations

import base64
import hashlib
import os
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field
from datetime import date, datetime

import boto3
from botocore.config import Config
from sqlalchemy import bindparam, select, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Session
from sqlalchemy.types import String

from app.core.analytics_quality import DAILY_COUNTS
from app.core.analytics_rollup import add_months, retention_start
from app.core.time import utc_now
from app.models.analytics import AnalyticsArchivePart, AnalyticsEvent

# One run per month at a time: taken at the start of each month's transaction
# and released by its commit or rollback, so it covers the read, the upload
# and the delete together. `try`, so a second run says so and stops rather
# than waiting to archive rows the first has already moved. Named apart from
# the rollup's own lock (app/core/analytics_rollup.py `_ONE_RUN_AT_A_TIME`).
ARCHIVE_LOCK = text("select pg_try_advisory_xact_lock(hashtext('analytics-archive'))")

# Rows per batch read from Postgres and handed to the Parquet writer.
READ_BATCH = 10_000

# Ids per DELETE and per count, so one statement never binds a month's worth.
# Reasoned, not measured: 5,000 ids of 36 characters is about 180 KB a
# statement, and a month at 3,000 phones a day is a few hundred statements.
ID_CHUNK = 5000

# The environment variables the bucket is read from - the archive's own names,
# not the R2_* the pipeline publishes with or the R2_PHOTO_* report photos use
# (app/config.py), so no other job's token can reach these files and this
# job's token can reach nothing else.
ENV = {
    "endpoint_url": "USAGE_ARCHIVE_R2_ENDPOINT_URL",
    "bucket": "USAGE_ARCHIVE_R2_BUCKET",
    "access_key_id": "USAGE_ARCHIVE_R2_ACCESS_KEY_ID",
    "secret_access_key": "USAGE_ARCHIVE_R2_SECRET_ACCESS_KEY",
}

PARQUET_TYPE = "application/vnd.apache.parquet"


class ArchiveError(RuntimeError):
    """The archive stopped short, and nothing it had not finished was deleted."""


class ArchiveBusy(ArchiveError):
    """Another run holds `ARCHIVE_LOCK`."""


def object_key(month: date, part: int) -> str:
    """`2026-11/part-0001.parquet`: one prefix per month, so retention deletes by prefix."""
    return f"{month:%Y-%m}/part-{part:04d}.parquet"


def month_of_key(key: str) -> date | None:
    """The month a key's prefix names, or None for a key this module did not write."""
    try:
        return date.fromisoformat(f"{key.split('/', 1)[0]}-01")
    except ValueError:
        return None


class R2Store:
    """The environment's archive bucket, over R2's S3-compatible API.

    The same client shape as report photos (app/core/photos.py `_client`). A
    put is confirmed twice: R2 refuses a body whose MD5 is not the one sent
    (`ContentMD5`), and the object's size is read back before the caller may
    delete the rows the body holds.
    """

    def __init__(self, client, bucket: str) -> None:
        self._client = client
        self.bucket = bucket

    @classmethod
    def from_env(cls, environ: dict | None = None) -> R2Store:
        environ = os.environ if environ is None else environ
        missing = [name for name in ENV.values() if not environ.get(name)]
        if missing:
            raise ArchiveError(f"the usage archive's bucket is not configured: {', '.join(missing)} unset")
        client = boto3.client(
            "s3",
            endpoint_url=environ[ENV["endpoint_url"]],
            aws_access_key_id=environ[ENV["access_key_id"]],
            aws_secret_access_key=environ[ENV["secret_access_key"]],
            # R2 ignores the region but boto3 insists on one; `auto` is what
            # Cloudflare's own documentation uses.
            region_name="auto",
            config=Config(signature_version="s3v4"),
        )
        return cls(client, environ[ENV["bucket"]])

    def put(self, key: str, body: bytes) -> None:
        digest = base64.b64encode(hashlib.md5(body, usedforsecurity=False).digest()).decode()
        self._client.put_object(Bucket=self.bucket, Key=key, Body=body, ContentMD5=digest, ContentType=PARQUET_TYPE)
        held = self._client.head_object(Bucket=self.bucket, Key=key)["ContentLength"]
        if held != len(body):
            # No sizes in the message: it reaches a public log, and a file's
            # size is its row count to within a few percent.
            raise ArchiveError(f"{key}: R2 holds a different size from the one written")

    def get(self, key: str) -> bytes:
        return self._client.get_object(Bucket=self.bucket, Key=key)["Body"].read()

    def keys(self) -> list[str]:
        found: list[str] = []
        for page in self._client.get_paginator("list_objects_v2").paginate(Bucket=self.bucket):
            found.extend(item["Key"] for item in page.get("Contents", ()))
        return found

    def delete(self, keys: list[str]) -> None:
        for start in range(0, len(keys), 1000):  # DeleteObjects takes 1,000 keys at most
            chunk = keys[start : start + 1000]
            answer = self._client.delete_objects(
                Bucket=self.bucket, Delete={"Objects": [{"Key": key} for key in chunk], "Quiet": True}
            )
            if answer.get("Errors"):
                failed = ", ".join(error["Key"] for error in answer["Errors"])
                raise ArchiveError(f"R2 did not delete: {failed}")


@dataclass
class ArchiveResult:
    """What a run did, by month and part - never by row count, for the log's sake."""

    archived: list[tuple[date, int]] = field(default_factory=list)
    retired: list[date] = field(default_factory=list)


_MONTHS_TO_ARCHIVE = text(
    """
    select m.month from analytics_months m
    where m.status = 'closed' and m.month >= :cutoff
      and exists (
        select 1 from analytics_events e
        where e.local_date >= m.month and e.local_date < (m.month + interval '1 month')::date
          and e.user_key is null
      )
    order by m.month
    """
)

_NEXT_PART = text("select coalesce(max(part), 0) + 1 from analytics_archive_parts where month = :month")

_IDS = bindparam("ids", type_=ARRAY(String()))

_COUNT_COLUMNS = ("rows", *DAILY_COUNTS)

_ADD_DAILY = text(
    f"""
    insert into analytics_archived_daily (local_date, received_on, platform, app_version, {", ".join(_COUNT_COLUMNS)})
    select local_date, received_on, platform, coalesce(app_version, ''), count(*),
      {", ".join(DAILY_COUNTS.values())}
    from analytics_events where id = any(:ids)
    group by local_date, received_on, platform, coalesce(app_version, '')
    on conflict (local_date, received_on, platform, app_version) do update set
      {", ".join(f"{column} = analytics_archived_daily.{column} + excluded.{column}" for column in _COUNT_COLUMNS)}
    """
).bindparams(_IDS)

_DELETE_IDS = text("delete from analytics_events where id = any(:ids)").bindparams(_IDS)


def months_to_archive(db: Session, today: date) -> list[date]:
    """Closed months inside retention that still hold rows with no `user_key`."""
    return [row[0] for row in db.execute(_MONTHS_TO_ARCHIVE, {"cutoff": retention_start(today)})]


def batches(db: Session, month: date, ids: list[str]) -> Iterator[list[dict]]:
    """Every column of the month's unlinked rows, in the order the file keeps them, `READ_BATCH` at a time.

    Appends each row's id to `ids` as it goes, so the caller deletes exactly
    the rows the writer was handed.
    """
    table = AnalyticsEvent.__table__
    query = (
        select(table)
        .where(
            table.c.local_date >= month,
            table.c.local_date < add_months(month, 1),
            table.c.user_key.is_(None),
        )
        .order_by(table.c.local_date, table.c.event, table.c.platform, table.c.id)
        .execution_options(yield_per=READ_BATCH)
    )
    for partition in db.execute(query).mappings().partitions():
        rows = [dict(row) for row in partition]
        ids.extend(row["id"] for row in rows)
        yield rows


def _chunks(ids: list[str]) -> Iterable[list[str]]:
    for start in range(0, len(ids), ID_CHUNK):
        yield ids[start : start + ID_CHUNK]


def record(db: Session, *, month: date, part: int, ids: list[str], body: bytes, now: datetime) -> None:
    """Record the part, count what it holds, then delete exactly those rows. The caller commits.

    Raises, for the caller to roll back, when fewer rows were deleted than the
    file holds: a row the file holds and this database no longer does was
    deleted by something else meanwhile, and a part whose ledger row
    disagrees with its file is worse than a part written again tomorrow.
    """
    db.add(
        AnalyticsArchivePart(
            month=month,
            part=part,
            object_key=object_key(month, part),
            rows=len(ids),
            bytes=len(body),
            sha256=hashlib.sha256(body).hexdigest(),
            written_at=now,
        )
    )
    db.flush()
    deleted = 0
    for chunk in _chunks(ids):
        db.execute(_ADD_DAILY, {"ids": chunk})
        deleted += db.execute(_DELETE_IDS, {"ids": chunk}).rowcount
    if deleted != len(ids):
        # No counts in the message, for the same public log's sake.
        raise ArchiveError(f"{object_key(month, part)}: fewer rows were deleted than the file holds")


_MARK_RETIRED = text("update analytics_archive_parts set deleted_at = :now where month < :cutoff and deleted_at is null")
_DROP_DAILY = text("delete from analytics_archived_daily where local_date < :cutoff")


def retire(db: Session, store: R2Store, *, today: date, now: datetime) -> list[date]:
    """Delete every file of every month past retention, then the month's ledger and counts.

    Lists the bucket rather than trusting the ledger, so a part written by a
    run that died before its commit - in the bucket, not in the ledger - goes
    on the same date line as the rest. The caller commits.
    """
    cutoff = retention_start(today)
    expired = [key for key in store.keys() if (month := month_of_key(key)) is not None and month < cutoff]
    store.delete(expired)
    months = sorted({month_of_key(key) for key in expired})
    db.execute(_MARK_RETIRED, {"now": now, "cutoff": cutoff})
    db.execute(_DROP_DAILY, {"cutoff": cutoff})
    return months


def _lock(db: Session) -> None:
    if not db.execute(ARCHIVE_LOCK).scalar_one():
        raise ArchiveBusy("another archive run holds the lock")


def run(
    db: Session,
    store: R2Store,
    write: Callable[[Iterable[list[dict]]], bytes],
    *,
    today: date | None = None,
    now: datetime | None = None,
) -> ArchiveResult:
    """One night's archive. `write` turns batches of rows into one Parquet file's bytes
    (scripts/analytics_archive.py). Each month commits on its own, so a failure
    keeps every month archived before it."""
    now = now or utc_now()
    today = today or now.date()
    result = ArchiveResult()
    try:
        _lock(db)
        result.retired = retire(db, store, today=today, now=now)
        db.commit()

        months = months_to_archive(db, today)
        db.rollback()
        for month in months:
            _lock(db)
            part = db.execute(_NEXT_PART, {"month": month}).scalar_one()
            ids: list[str] = []
            body = write(batches(db, month, ids))
            if not ids:
                db.rollback()
                continue
            store.put(object_key(month, part), body)
            record(db, month=month, part=part, ids=ids, body=body, now=now)
            db.commit()
            result.archived.append((month, part))
    except Exception:
        db.rollback()
        raise
    return result
