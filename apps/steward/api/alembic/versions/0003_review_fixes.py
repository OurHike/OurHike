"""Tombstones, name snapshots and send-back time: the adversarial review's findings 2, 3 and 10 (#1910).

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-27
"""

import sqlalchemy as sa

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("claim", sa.Column("reviewed_by_name", sa.String(length=40), nullable=True))
    op.add_column("claim", sa.Column("sent_back_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("club_weights", sa.Column("changed_by_name", sa.String(length=40), nullable=True))
    op.add_column("steward_user", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    # Rows written before the snapshot columns existed take the names as they are now.
    op.execute(
        "update club_weights set changed_by_name = steward_user.display_name "
        "from steward_user where steward_user.id = club_weights.changed_by"
    )
    op.execute(
        "update claim set reviewed_by_name = steward_user.display_name "
        "from steward_user where steward_user.id = claim.reviewed_by"
    )


def downgrade() -> None:
    op.drop_column("steward_user", "deleted_at")
    op.drop_column("club_weights", "changed_by_name")
    op.drop_column("claim", "sent_back_at")
    op.drop_column("claim", "reviewed_by_name")
