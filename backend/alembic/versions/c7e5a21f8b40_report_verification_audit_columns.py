"""record who verified a report, and when

Revision ID: c7e5a21f8b40
Revises: b3d1c7a94e02
Create Date: 2026-08-07 02:40:00.000000

`closure` has carried `verified_by`/`verified_at` since the initial schema.
`report` never did, so "who marked this dangerous-person report serious,
and when" was unanswerable for the resource where the question matters most
- and answerable for a washed-out footbridge (#251).

features/REPORT_A_PROBLEM.md says closures and warning escalation reuse
"this exact moderation-queue mechanism... not building a second review
workflow". They shared the endpoint file and the role gate; they did not
share this, which made that claim structurally false at exactly the point
somebody would go looking.

**Nullable, and no backfill.** Null means "nobody has verified this", which
is the honest state for every row that has not been through moderation -
and, right now, for every row full stop, since `report.status` has no way
to have reached `verified` without going through the action this revision
is fixing. Inventing a moderator id for historical rows would be worse than
the gap: an audit trail that contains a guess is not an audit trail.

**No RLS statement here, and that is not an oversight.** RLS is a TABLE
property (b3d1c7a94e02) and this adds no table, so the guard in
tests/test_migration_rls.py - which compares `Base.metadata.tables` against
every migration's `RLS_TABLES` - stays satisfied without this revision
naming anything. `reports` is already locked.
"""

import sqlalchemy as sa

from alembic import op

revision = "c7e5a21f8b40"
down_revision = "b3d1c7a94e02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("reports", sa.Column("verified_by", sa.String(), nullable=True))
    op.add_column("reports", sa.Column("verified_at", sa.DateTime(), nullable=True))
    op.create_foreign_key(
        "fk_reports_verified_by_profiles",
        "reports",
        "profiles",
        ["verified_by"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_reports_verified_by_profiles", "reports", type_="foreignkey")
    op.drop_column("reports", "verified_at")
    op.drop_column("reports", "verified_by")
