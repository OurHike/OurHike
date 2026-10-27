"""Lists, list items, users and club weights: phase 2 (#1906).

Revision ID: 0001
Create Date: 2026-10-27
"""

import sqlalchemy as sa

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "steward_user",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=40), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "club_weights",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("club", sa.String(length=120), nullable=False),
        sa.Column("deficit", sa.Integer(), nullable=False),
        sa.Column("water", sa.Integer(), nullable=False),
        sa.Column("trail", sa.Integer(), nullable=False),
        sa.Column("cluster", sa.Integer(), nullable=False),
        sa.Column("restricted", sa.Integer(), nullable=False),
        sa.Column("note", sa.String(length=200), nullable=True),
        sa.Column("restored_from", sa.Integer(), nullable=True),
        sa.Column("changed_by", sa.String(length=64), nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("cluster between 0 and 100", name="ck_club_weights_cluster_range"),
        sa.CheckConstraint("deficit between 0 and 100", name="ck_club_weights_deficit_range"),
        sa.CheckConstraint("restricted between 0 and 100", name="ck_club_weights_restricted_range"),
        sa.CheckConstraint("trail between 0 and 100", name="ck_club_weights_trail_range"),
        sa.CheckConstraint("water between 0 and 100", name="ck_club_weights_water_range"),
        sa.ForeignKeyConstraint(["changed_by"], ["steward_user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["restored_from"], ["club_weights.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_club_weights_changed_by"), "club_weights", ["changed_by"], unique=False)
    op.create_index("ix_club_weights_club_changed_at", "club_weights", ["club", "changed_at"], unique=False)
    op.create_table(
        "site_list",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("share_token_sha256", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["steward_user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("share_token_sha256"),
    )
    op.create_index(op.f("ix_site_list_owner_id"), "site_list", ["owner_id"], unique=False)
    op.create_table(
        "site_list_item",
        sa.Column("list_id", sa.Uuid(), nullable=False),
        sa.Column("rims_id", sa.String(length=64), nullable=False),
        sa.Column("added_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["list_id"], ["site_list.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("list_id", "rims_id"),
    )


def downgrade() -> None:
    op.drop_table("site_list_item")
    op.drop_index(op.f("ix_site_list_owner_id"), table_name="site_list")
    op.drop_table("site_list")
    op.drop_index("ix_club_weights_club_changed_at", table_name="club_weights")
    op.drop_index(op.f("ix_club_weights_changed_by"), table_name="club_weights")
    op.drop_table("club_weights")
    op.drop_table("steward_user")
