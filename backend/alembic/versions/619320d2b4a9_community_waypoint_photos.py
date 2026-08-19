"""community waypoint photos

Revision ID: 619320d2b4a9
Revises: b6e3f1a72d84
Create Date: 2026-08-19 23:27:53.321627

The store behind rung 2 of the waypoint card's photo ladder (#576,
features/POI_PHOTOS.md "Source 3"). One row per (poi, contributor) - the
unique constraint IS the one-per-person rule, and a re-share upserts into it
rather than being refused. The bytes live in the private R2 photo bucket
under a key derived from the same pair; this row is the authoritative half.

Indexes on the two columns every hot query filters on (the gallery scans
poi_id, withdrawal scans the pair, moderation will scan status), following
a1b7c3d95e04's reasoning: cheap while the table is small, which is exactly
when adding them is a one-line decision instead of an incident.

RLS is enabled here rather than in a later revision because this revision
adds the table: b3d1c7a94e02 is explicit that its own list is a statement
about the schema at its point in time, and that a table added later brings
its own lock. tests/test_migration_rls.py unions every revision's
RLS_TABLES, so leaving this out fails the suite.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "619320d2b4a9"
down_revision: Union[str, Sequence[str], None] = "b6e3f1a72d84"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# The tables this revision locks - see b3d1c7a94e02 for the mechanism and
# tests/test_migration_rls.py for the guard that unions these lists.
RLS_TABLES: tuple[str, ...] = ("poi_photos",)


def rls_statements(dialect_name: str, *, enable: bool) -> list[str]:
    """Same shape as b3d1c7a94e02's, for the same testability reason."""
    if dialect_name != "postgresql":
        return []
    verb = "ENABLE" if enable else "DISABLE"
    return [f"ALTER TABLE public.{table} {verb} ROW LEVEL SECURITY" for table in RLS_TABLES]


def upgrade() -> None:
    """Create the table, and lock it before anything can reach it."""
    op.create_table(
        "poi_photos",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("poi_id", sa.String(), nullable=False),
        sa.Column("contributor_id", sa.String(), nullable=False),
        sa.Column("taken", sa.Date(), nullable=True),
        sa.Column("shared_at", sa.DateTime(), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(), nullable=True),
        sa.Column("attribution_name", sa.String(), nullable=False),
        sa.Column("masked_until", sa.DateTime(), nullable=True),
        sa.Column("license", sa.String(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("live", "dismissed", name="poiphotostatus", native_enum=False, length=20),
            nullable=False,
        ),
        sa.Column("pinned_at", sa.DateTime(), nullable=True),
        sa.Column("pinned_by", sa.String(), nullable=True),
        sa.Column("dismissed_at", sa.DateTime(), nullable=True),
        sa.Column("dismissed_by", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["contributor_id"], ["profiles.id"]),
        sa.ForeignKeyConstraint(["dismissed_by"], ["profiles.id"]),
        sa.ForeignKeyConstraint(["pinned_by"], ["profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("poi_id", "contributor_id", name="uq_poi_photos_poi_contributor"),
    )
    op.create_index(op.f("ix_poi_photos_contributor_id"), "poi_photos", ["contributor_id"], unique=False)
    op.create_index(op.f("ix_poi_photos_poi_id"), "poi_photos", ["poi_id"], unique=False)
    op.create_index(op.f("ix_poi_photos_status"), "poi_photos", ["status"], unique=False)

    for statement in rls_statements(op.get_context().dialect.name, enable=True):
        op.execute(statement)


def downgrade() -> None:
    """Drop the table; the lock goes with it."""
    op.drop_index(op.f("ix_poi_photos_status"), table_name="poi_photos")
    op.drop_index(op.f("ix_poi_photos_poi_id"), table_name="poi_photos")
    op.drop_index(op.f("ix_poi_photos_contributor_id"), table_name="poi_photos")
    op.drop_table("poi_photos")
