"""Crew places marked left, and photos carrying the phone's own id: the adversarial review's third pass, N7 and P2 (#1910).

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-27
"""

import sqlalchemy as sa

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("claim_member", sa.Column("left_at", sa.DateTime(timezone=True), nullable=True))
    # Places held by accounts that deleted their data before this column existed.
    op.execute(
        "update claim_member set left_at = steward_user.deleted_at "
        "from steward_user where steward_user.id = claim_member.user_id and steward_user.deleted_at is not null"
    )
    op.add_column("photo", sa.Column("client_id", sa.String(length=64), nullable=True))
    op.create_index(
        "uq_photo_client_id",
        "photo",
        ["claim_id", "client_id"],
        unique=True,
        postgresql_where=sa.text("client_id is not null"),
    )


def downgrade() -> None:
    op.drop_index("uq_photo_client_id", table_name="photo")
    op.drop_column("photo", "client_id")
    op.drop_column("claim_member", "left_at")
