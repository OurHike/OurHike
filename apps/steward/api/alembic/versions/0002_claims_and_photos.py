"""Claims, crews, photos and hours: phase 3 (#1910).

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-27
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "claim",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("rims_id", sa.String(length=64), nullable=False),
        sa.Column("claimer_id", sa.String(length=64), nullable=True),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("steps_done", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("notes", sa.String(length=1000), nullable=True),
        sa.Column("reviewed_by", sa.String(length=64), nullable=True),
        sa.Column("review_note", sa.String(length=500), nullable=True),
        sa.Column("invite_token_sha256", sa.String(length=64), nullable=True),
        sa.CheckConstraint("state in ('claimed', 'in_progress', 'submitted', 'verified', 'released')", name="ck_claim_state"),
        sa.ForeignKeyConstraint(["claimer_id"], ["steward_user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["steward_user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("invite_token_sha256"),
    )
    op.create_index(op.f("ix_claim_claimer_id"), "claim", ["claimer_id"], unique=False)
    op.create_index(op.f("ix_claim_rims_id"), "claim", ["rims_id"], unique=False)
    op.create_index(
        "uq_claim_one_live_per_site",
        "claim",
        ["rims_id"],
        unique=True,
        postgresql_where=sa.text("state in ('claimed', 'in_progress', 'submitted')"),
    )
    op.create_table(
        "claim_member",
        sa.Column("claim_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["claim_id"], ["claim.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["steward_user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("claim_id", "user_id"),
    )
    op.create_index(op.f("ix_claim_member_user_id"), "claim_member", ["user_id"], unique=False)
    op.create_table(
        "hours",
        sa.Column("claim_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("tenths", sa.Integer(), nullable=False),
        sa.Column("verified", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.CheckConstraint("tenths > 0 and tenths <= 720", name="ck_hours_range"),
        sa.ForeignKeyConstraint(["claim_id"], ["claim.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["steward_user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("claim_id", "user_id"),
    )
    op.create_index(op.f("ix_hours_user_id"), "hours", ["user_id"], unique=False)
    op.create_table(
        "photo",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("claim_id", sa.Uuid(), nullable=False),
        sa.Column("phase", sa.String(length=10), nullable=False),
        sa.Column("point", sa.Integer(), nullable=True),
        sa.Column("content_type", sa.String(length=20), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("uploaded_by", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("(phase = 'extra') = (point is null)", name="ck_photo_point_only_on_points"),
        sa.CheckConstraint("phase in ('before', 'after', 'extra')", name="ck_photo_phase"),
        sa.ForeignKeyConstraint(["claim_id"], ["claim.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by"], ["steward_user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_photo_claim_id"), "photo", ["claim_id"], unique=False)
    op.create_index(
        "uq_photo_point", "photo", ["claim_id", "phase", "point"], unique=True, postgresql_where=sa.text("point is not null")
    )


def downgrade() -> None:
    op.drop_index("uq_photo_point", table_name="photo", postgresql_where=sa.text("point is not null"))
    op.drop_index(op.f("ix_photo_claim_id"), table_name="photo")
    op.drop_table("photo")
    op.drop_index(op.f("ix_hours_user_id"), table_name="hours")
    op.drop_table("hours")
    op.drop_index(op.f("ix_claim_member_user_id"), table_name="claim_member")
    op.drop_table("claim_member")
    op.drop_index(
        "uq_claim_one_live_per_site",
        table_name="claim",
        postgresql_where=sa.text("state in ('claimed', 'in_progress', 'submitted')"),
    )
    op.drop_index(op.f("ix_claim_rims_id"), table_name="claim")
    op.drop_index(op.f("ix_claim_claimer_id"), table_name="claim")
    op.drop_table("claim")
