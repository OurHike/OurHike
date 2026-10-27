"""Crew places marked left, and receipts for photos by the phone's own id: the adversarial review's third and fourth passes, N7, P2 and C (#1910).

The backfill marks left the places of accounts still marked deleted. An
account that deleted its data and signed in again while 0003 was the head
had deleted_at cleared on its return (auth.current_user), so nothing here
can tell its places apart: they stay live. No deployment has run 0003 (the
API has no host yet, apps/steward/PLAN.md section 11), so that is no account.

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
    op.execute(
        "update claim_member set left_at = steward_user.deleted_at "
        "from steward_user where steward_user.id = claim_member.user_id and steward_user.deleted_at is not null"
    )
    op.create_table(
        "photo_receipt",
        sa.Column("claim_id", sa.Uuid(), sa.ForeignKey("claim.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("client_id", sa.String(length=64), primary_key=True),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("photo_receipt")
    op.drop_column("claim_member", "left_at")
