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

THE BACKFILL MARKS ONLY ROWS NO PERSON WROTE. The old reading,
`created_by IS NULL`, is exactly what account deletion fakes, so applying it
once would have carried #1913 forward onto every organization whose
registrant, claimer or nominator had already deleted their account - which
is what the 2026-10-29 review of this branch reproduced, downgrading and
upgrading over rows written through the API. Every self-service path leaves
a trace that deletion does not remove: registering or claiming moves the
organization out of `unclaimed` (and gives it seats, though deletion takes
the deleted person's own), and a nomination leaves its `org_nominations`
row. So a row is a maintainer's when `created_by` is null, it is still
`unclaimed`, nobody holds a seat at it, and nobody nominated it.
Reasoned from the writers in app/routers/clubs.py,
app/routers/nominations.py and load_assignments.py, and pinned by
tests/test_migrations.py; nobody has queried production's or UA's clubs.

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
    op.execute(
        """
        UPDATE clubs SET maintainer_written = true
        WHERE created_by IS NULL
          AND state = 'unclaimed'
          AND NOT EXISTS (SELECT 1 FROM club_admins a WHERE a.club_id = clubs.id)
          AND NOT EXISTS (SELECT 1 FROM org_nominations n WHERE n.club_id = clubs.id)
        """
    )


def downgrade() -> None:
    op.drop_column("clubs", "maintainer_written")
