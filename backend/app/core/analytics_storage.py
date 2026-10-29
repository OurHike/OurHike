"""How many usage rows this database may hold, and how many it holds now (#1902).

`POST /usage-events` turns a batch away as `over_budget` once the rows held
reach the ceiling (app/routers/analytics.py), and the nightly checks warn
before they do (app/core/analytics_quality.py `storage_near_ceiling`). Both
read the two functions here, so the line they compare against is one line.

THE CEILING IS ON ROWS HELD, NOT ON THE TABLE'S SIZE ON DISK. The first
version read `pg_total_relation_size('analytics_events')`, and a file that
size never comes back down: Postgres keeps a deleted row's space inside the
table for the next insert rather than handing it back. Measured 2026-10-27 on
Postgres 16: a 30 MB table with its oldest month deleted and vacuumed was
still 30 MB, and still 30 MB after a new month of the same size went in. So
a ceiling on file size, once met, would have turned every batch away for
good - months after the rollup had deleted the rows that filled it. Rows
held come down when the rollup deletes a month, and the reused space means
the file stays near the high-water mark the ceiling set.

ROWS HELD are the nightly rollup's own count of the table, taken after its
deletes and kept as the day's `held` row in `analytics_intake`, plus the
`stored` rows counted since. Reading the table's own count would mean a full
scan on every batch. Summing every `stored` count, as this did first, kept
deleted rows in the sum for six months: rows are deleted by the month they
describe, and their counts by the day they arrived, so 2,800 rows dated in
May and sent in November were deleted on 1 December and still held the
ceiling shut until the next June (#1903's second review). The sum runs high
by the rows stored on the snapshot's own day before the rollup counted them
- at most a day's budget - and by the rows of an account deleted since; both
turn batches away early, which is the safe direction. Before the first
snapshot, every `stored` count is summed.

`analytics_storage_ceiling_mb` (app/config.py) stays in megabytes, because
the plan it is sized against is quoted in megabytes. It becomes rows at
`STORED_ROW_BYTES`.

THE ROOM ON DISK IS WHAT THE PLAN COUNTS, so the warnings read it too
(`Storage`): the usage tables' size, against the same ceiling, and the whole
database's, against `database_quota_mb` - the line past which Supabase's Free
plan turns the database read-only, every write the app makes and not only
usage rows. Both are shown in one place, the storage strip at the top of the
usage report's data-quality panel (app/core/analytics_report.py), and raised
as findings by the nightly checks.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings

# Bytes one stored usage row takes, both indexes included. Measured
# 2026-10-27 on Postgres 16: 100,000 synthetic rows of all six events, half
# of them sealed, inserted into an empty `analytics_events`, came to 380 and
# 382 bytes a row by `pg_total_relation_size` on two runs. The higher one is
# used, so the ceiling errs early. Real rows may run larger - more of them
# sealed, longer club lists - and if they run a fifth larger, a 250 MB ceiling
# holds about 300 MB on disk, still inside the 500 MB plan
# (LAUNCH_CHECKLIST.md 4.1).
STORED_ROW_BYTES = 382

# The one definition of rows held: the nightly checks run it alone, and the
# intake gate runs it inside its own query, to keep one round trip a batch.
ROWS_HELD_SQL = """
    with snapshot as (
      select received_on, rows from analytics_intake where outcome = 'held' order by received_on desc limit 1
    )
    select coalesce((select rows from snapshot), 0) + coalesce((
      select sum(rows) from analytics_intake
      where outcome = 'stored' and received_on >= coalesce((select received_on from snapshot), date '-infinity')
    ), 0)
"""
_ROWS_HELD = text(ROWS_HELD_SQL)


def ceiling_rows() -> int:
    """How many rows `analytics_storage_ceiling_mb` allows."""
    return settings.analytics_storage_ceiling_mb * 1024 * 1024 // STORED_ROW_BYTES


def rows_held(db: Session) -> int:
    """How many usage rows are held now, as `analytics_intake` counted them in."""
    return int(db.execute(_ROWS_HELD).scalar_one())


# Every table usage measurement keeps (app/models/analytics.py). A table left
# off would take room on disk that no warning counts, so
# tests/test_analytics_storage.py fails when the models hold one this does not.
USAGE_TABLES = (
    "analytics_events",
    "analytics_intake",
    "analytics_anomalies",
    "analytics_months",
    "analytics_monthly",
    "analytics_users",
    "analytics_seal_keys",
    "analytics_openings",
    # The usage archive's ledger and daily counts (#1923): small, but in the
    # database the plan counts.
    "analytics_archive_parts",
    "analytics_archived_daily",
)

# A table's size with its indexes and TOAST. `pg_total_relation_size` needs
# no privilege on the table, so the rollup's role - which may not read
# `sealed` - can run it: checked 2026-10-27 on Postgres 16, as a role granted
# SELECT on two columns of one table. `to_regclass` counts a table not yet
# migrated as nothing rather than failing the night.
_USAGE_BYTES = text(
    "select coalesce(sum(pg_total_relation_size(to_regclass(name))), 0) from unnest(cast(:names as text[])) as name"
)

# Supabase counts a project's database size over every database in it, by
# exactly this sum (supabase.com/docs/guides/platform/database-size, read
# 2026-10-27), so this does too - over each one this role may connect to,
# because `pg_database_size` refuses the others. One it may not connect to is
# left out and the figure reads low by its size, which is the late direction
# for a warning: @unvalidated whether a hosted project has one, which
# `select datname from pg_database where not has_database_privilege(oid,
# 'CONNECT')`, run as the rollup's role, would settle.
_DATABASE_BYTES = text(
    "select coalesce(sum(pg_database_size(oid)), 0) from pg_database where has_database_privilege(oid, 'CONNECT')"
)

_MB = 1024 * 1024


def usage_tables_bytes(db: Session) -> int:
    """The room every usage table takes on disk, indexes included."""
    return int(db.execute(_USAGE_BYTES, {"names": list(USAGE_TABLES)}).scalar_one())


def database_bytes(db: Session) -> int:
    """The database's size as the plan counts it: every database this role may connect to."""
    return int(db.execute(_DATABASE_BYTES).scalar_one())


@dataclass(frozen=True)
class Storage:
    """Where usage measurement stands against the two limits it is held to.

    `ceiling_share` is the nearer of two readings of the same ceiling: rows
    held, which the intake gate counts and which come down when the rollup
    deletes a month, and the usage tables' size on disk, which the plan
    counts. The second runs higher when real rows are larger than the
    measured `STORED_ROW_BYTES`, and stays at its high-water mark after a
    month is deleted, because the file keeps that room for the next rows
    rather than giving it back. So a warning raised by it does not clear when
    rows go: it clears when the ceiling is raised, or when `VACUUM FULL
    analytics_events` rewrites the table, which locks it while it runs.

    A limit of 0 has no share: a ceiling of 0 turns every batch away, which
    `rows_over_budget` already says, and a quota of 0 is none configured.
    """

    rows_held: int
    usage_bytes: int
    database_bytes: int

    @property
    def rows_share(self) -> float | None:
        ceiling = ceiling_rows()
        return self.rows_held / ceiling if ceiling else None

    @property
    def usage_share(self) -> float | None:
        ceiling = settings.analytics_storage_ceiling_mb * _MB
        return self.usage_bytes / ceiling if ceiling else None

    @property
    def ceiling_share(self) -> float | None:
        if self.rows_share is None or self.usage_share is None:
            return None
        return max(self.rows_share, self.usage_share)

    @property
    def quota_share(self) -> float | None:
        quota = settings.database_quota_mb * _MB
        return self.database_bytes / quota if quota else None


def measure(db: Session) -> Storage:
    """Rows held, and the room on disk, as of now."""
    return Storage(rows_held=rows_held(db), usage_bytes=usage_tables_bytes(db), database_bytes=database_bytes(db))
