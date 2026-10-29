"""clubs.maintainer_written: who wrote the row, kept apart from who registered it

Revision ID: c3a9e5d27f18
Revises: 897b71ad5fff
Create Date: 2026-10-27 15:30:00.000000

**#1913 — Deleting the registrant's account turns a self-registered
organization into a maintainer-written one, and lets an accomplice keep an
admin seat.** `stood_behind()` (app/core/assignments.py) and the
held-registration revocation (`_revoke_the_registrants_unverified_seat` in
app/routers/clubs.py) both read "a maintainer wrote this" off
`clubs.created_by IS NULL`, and account deletion nulls `created_by`
(app/core/account_deletion.py). This column says it on its own, and nothing
that deletes an account touches it.

THE BACKFILL IS THE OLD READING, ONCE. `created_by IS NULL` is what every
reader assumed until this revision, so the rows that exist keep the meaning
they had. It misreads exactly the rows the bug already produced: a
self-registered club whose registrant deleted their account before this ran.
Reasoned, not measured: no production backend has served the console yet
(#600 — Nothing owns standing up the production backend, and the image has
never run against a real Docker daemon), so no self-service path can have
written a production clubs row. Nobody queried production's clubs to confirm
it.

Additive and reversible: downgrade drops the column. The code that reads it
must not run before this upgrade (backend/HOSTING.md, the migration-skew
section): `stood_behind()` is in every hiker-facing read of assignments.
"""

import sqlalchemy as sa

from alembic import op

revision = "c3a9e5d27f18"
down_revision = "897b71ad5fff"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "clubs",
        sa.Column("maintainer_written", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.execute("UPDATE clubs SET maintainer_written = true WHERE created_by IS NULL")


def downgrade() -> None:
    op.drop_column("clubs", "maintainer_written")
