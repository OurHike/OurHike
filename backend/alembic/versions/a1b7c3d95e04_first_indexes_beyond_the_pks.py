"""the first indexes beyond the primary keys

Revision ID: a1b7c3d95e04
Revises: f2c8d4a91e57
Create Date: 2026-08-18 03:20:00.000000

Beyond the PKs there were no indexes at all (#658) - fine while every table
fits in one page of buffer cache, and exactly the kind of fine that becomes
an incident the week it stops. Added now, while it is a one-line decision:
the public lists scan `reports.status` and `closures.moderation_status` on
every anonymous GET, "my reports" scans `reporter_id`, and thanks
delivery/credit resolution look assignments up by who holds them.

Names match SQLAlchemy's `ix_<table>_<column>` convention because the
models declare the same indexes with `index=True` - the drift check
compares the two, so they have to agree on more than existence.
"""

from alembic import op

revision = "a1b7c3d95e04"
down_revision = "f2c8d4a91e57"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_reports_status", "reports", ["status"])
    op.create_index("ix_reports_reporter_id", "reports", ["reporter_id"])
    op.create_index("ix_closures_moderation_status", "closures", ["moderation_status"])
    op.create_index("ix_maintainer_assignments_maintainer_id", "maintainer_assignments", ["maintainer_id"])
    op.create_index("ix_maintainer_assignments_club_id", "maintainer_assignments", ["club_id"])


def downgrade() -> None:
    op.drop_index("ix_maintainer_assignments_club_id", table_name="maintainer_assignments")
    op.drop_index("ix_maintainer_assignments_maintainer_id", table_name="maintainer_assignments")
    op.drop_index("ix_closures_moderation_status", table_name="closures")
    op.drop_index("ix_reports_reporter_id", table_name="reports")
    op.drop_index("ix_reports_status", table_name="reports")
