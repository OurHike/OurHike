"""poi photo dismissals ledger

Revision ID: c3a8f1d6e2b7
Revises: b1e4c7a9d2f6
Create Date: 2026-09-17 12:20:00.000000

The ledger behind #1551: one row per takedown of a community photo, kept
when the `poi_photos` row it was about is replaced by a re-share or deleted
by a withdrawal - the two things a hiker can do that erased a moderator's
decision. app/models/poi_photo.py's `PoiPhotoDismissal` is the reasoning and
the maintainer's decision (2026-09-17) between this, a count on the photo
row, and leaving it.

Indexes on what the two readers filter by: the queue asks "has this (place,
contributor) pair been taken down before" for every row it lists, and the
export and deletion paths read by contributor. a1b7c3d95e04's reasoning -
cheap while the table is small, which is exactly when adding them is a
one-line decision instead of an incident.

RLS is enabled here rather than in a later revision because this revision
adds the table, 619320d2b4a9's rule: a table added later brings its own
lock, and tests/test_migration_rls.py unions every revision's RLS_TABLES.
Stacked on b1e4c7a9d2f6 rather than branched from c9d1a7f48b62 because two
heads cannot merge, which is why #1551 rides the same pull request as #1545.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "c3a8f1d6e2b7"
down_revision: Union[str, Sequence[str], None] = "b1e4c7a9d2f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

RLS_TABLES: tuple[str, ...] = ("poi_photo_dismissals",)


def rls_statements(dialect_name: str, *, enable: bool) -> list[str]:
    """Same shape as b3d1c7a94e02's, for the same testability reason."""
    if dialect_name != "postgresql":
        return []
    verb = "ENABLE" if enable else "DISABLE"
    return [f"ALTER TABLE public.{table} {verb} ROW LEVEL SECURITY" for table in RLS_TABLES]


def upgrade() -> None:
    """Create the table, and lock it before anything can reach it."""
    op.create_table(
        "poi_photo_dismissals",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("poi_id", sa.String(), nullable=False),
        sa.Column("contributor_id", sa.String(), nullable=False),
        sa.Column("photo_id", sa.String(), nullable=False),
        sa.Column("dismissed_by", sa.String(), nullable=False),
        sa.Column("dismissed_at", sa.DateTime(), nullable=False),
        sa.Column("reported_reason", sa.String(), nullable=True),
        sa.Column("flagged", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["contributor_id"], ["profiles.id"]),
        sa.ForeignKeyConstraint(["dismissed_by"], ["profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_poi_photo_dismissals_contributor_id"), "poi_photo_dismissals", ["contributor_id"], unique=False)
    op.create_index(
        "ix_poi_photo_dismissals_place_contributor", "poi_photo_dismissals", ["poi_id", "contributor_id"], unique=False
    )
    for statement in rls_statements(op.get_context().dialect.name, enable=True):
        op.execute(statement)


def downgrade() -> None:
    """Drop the table; the lock goes with it, and so does every takedown on record."""
    op.drop_index("ix_poi_photo_dismissals_place_contributor", table_name="poi_photo_dismissals")
    op.drop_index(op.f("ix_poi_photo_dismissals_contributor_id"), table_name="poi_photo_dismissals")
    op.drop_table("poi_photo_dismissals")
