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

ROWS HELD are summed from `analytics_intake`'s `stored` counts, which the
rollup deletes on the same date line as the rows (app/core/analytics_rollup.py
`run`). Reading the table's own count would mean a full scan on every batch.
The sum can be off at the edges, by reasoning rather than measurement: high
by the rows of deleted accounts, which take their events with them but leave
their counts; low by a row a phone dated a day ahead that arrived the day
before the line. Running high turns batches away early, which is the safe
direction.

`analytics_storage_ceiling_mb` (app/config.py) stays in megabytes, because
the plan it is sized against is quoted in megabytes. It becomes rows at
`STORED_ROW_BYTES`.
"""

from __future__ import annotations

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
ROWS_HELD_SQL = "select coalesce(sum(rows), 0) from analytics_intake where outcome = 'stored'"
_ROWS_HELD = text(ROWS_HELD_SQL)


def ceiling_rows() -> int:
    """How many rows `analytics_storage_ceiling_mb` allows."""
    return settings.analytics_storage_ceiling_mb * 1024 * 1024 // STORED_ROW_BYTES


def rows_held(db: Session) -> int:
    """How many usage rows are held now, as `analytics_intake` counted them in."""
    return int(db.execute(_ROWS_HELD).scalar_one())
