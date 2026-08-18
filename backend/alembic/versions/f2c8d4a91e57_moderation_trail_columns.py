"""record who dismissed and who resolved, not only who verified

Revision ID: f2c8d4a91e57
Revises: e5b2f7c1a903
Create Date: 2026-08-18 03:00:00.000000

The moderation trail recorded escalation and nothing else (#658). Dismissal
recorded no actor at all - "who removed this bad_hikers report" was
unanswerable, the question c7e5a21f8b40's own docstring calls the one that
matters most - and `resolved`, the status the public contract and the
client's "Fixed" rendering promise, had no columns to record who declared a
hazard cleared, because no endpoint could set it.

Same shape as c7e5a21f8b40, for the same reasons: **nullable, no
backfill** (null means "nobody has done this", the honest state for every
existing row), and **no RLS statement** (RLS is a table property and this
adds no table - `reports` and `closures` are already locked).

`resolved_*` lands on reports only: a closure's lifecycle ends at
reopened/dismissed, and inventing a resolved state for it here would be a
schema deciding a feature.
"""

import sqlalchemy as sa

from alembic import op

revision = "f2c8d4a91e57"
down_revision = "e5b2f7c1a903"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("reports", sa.Column("dismissed_by", sa.String(), nullable=True))
    op.add_column("reports", sa.Column("dismissed_at", sa.DateTime(), nullable=True))
    op.add_column("reports", sa.Column("resolved_by", sa.String(), nullable=True))
    op.add_column("reports", sa.Column("resolved_at", sa.DateTime(), nullable=True))
    op.create_foreign_key("fk_reports_dismissed_by_profiles", "reports", "profiles", ["dismissed_by"], ["id"])
    op.create_foreign_key("fk_reports_resolved_by_profiles", "reports", "profiles", ["resolved_by"], ["id"])

    op.add_column("closures", sa.Column("dismissed_by", sa.String(), nullable=True))
    op.add_column("closures", sa.Column("dismissed_at", sa.DateTime(), nullable=True))
    op.create_foreign_key("fk_closures_dismissed_by_profiles", "closures", "profiles", ["dismissed_by"], ["id"])


def downgrade() -> None:
    op.drop_constraint("fk_closures_dismissed_by_profiles", "closures", type_="foreignkey")
    op.drop_column("closures", "dismissed_at")
    op.drop_column("closures", "dismissed_by")

    op.drop_constraint("fk_reports_resolved_by_profiles", "reports", type_="foreignkey")
    op.drop_constraint("fk_reports_dismissed_by_profiles", "reports", type_="foreignkey")
    op.drop_column("reports", "resolved_at")
    op.drop_column("reports", "resolved_by")
    op.drop_column("reports", "dismissed_at")
    op.drop_column("reports", "dismissed_by")
