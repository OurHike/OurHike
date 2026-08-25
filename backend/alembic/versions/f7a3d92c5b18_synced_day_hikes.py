"""day hikes follow the account

Revision ID: f7a3d92c5b18
Revises: d8f3b62a4c17
Create Date: 2026-08-25 12:00:00.000000

#976, the maintainer's decision (2026-08-25) that day hikes sync from day
one. The table is c4a7e91d5f38's `synced_trips` shape exactly - client id as
the primary key, an opaque nullable `document`, server-assigned `updated_at`,
a `deleted_at` tombstone, and the one composite index the sync queries on -
because a day hike is the same kind of thing a trip is, and every argument
in app/models/synced_trip.py transfers.

Its own table rather than rows in `synced_trips`, and this is the decision a
reviewer should weigh: `/trips/sync` returns every row for the profile past
the watermark with nothing to filter on, so day hikes mixed in would ride
back through the exchange deployed clients already consume, to be re-dropped
(or mis-filed as trips) by `client/src/lib/tripsSync.ts` on every sync.
app/models/synced_day_hike.py carries the full argument. The conflict rule
is not duplicated - both routers call app/core/trip_sync.resolve_upload.

RLS: the table joins the union tests/test_migration_rls.py checks against
Base.metadata, so leaving it out fails the suite. These rows are a hiker's
own private planning, served to nobody - PostgREST would otherwise hand the
whole document to anyone holding the anon key.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f7a3d92c5b18"
down_revision: Union[str, Sequence[str], None] = "d8f3b62a4c17"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# The table this revision locks - see b3d1c7a94e02 for the mechanism and
# tests/test_migration_rls.py for the guard that unions these lists.
RLS_TABLES: tuple[str, ...] = ("synced_day_hikes",)


def rls_statements(dialect_name: str, *, enable: bool) -> list[str]:
    """Same shape as b3d1c7a94e02's, for the same testability reason."""
    if dialect_name != "postgresql":
        return []
    verb = "ENABLE" if enable else "DISABLE"
    return [f"ALTER TABLE public.{table} {verb} ROW LEVEL SECURITY" for table in RLS_TABLES]


def upgrade() -> None:
    """Create the table, and lock it before anything can reach it."""
    op.create_table(
        "synced_day_hikes",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("profile_id", sa.String(), nullable=False),
        sa.Column("document", sa.JSON(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    # The sync's only query: this hiker's rows, changed since a watermark.
    # Both columns together, because `profile_id` alone would scan a hiker's
    # whole history to answer the question every sync asks.
    op.create_index(
        "ix_synced_day_hikes_profile_updated",
        "synced_day_hikes",
        ["profile_id", "updated_at"],
        unique=False,
    )

    for statement in rls_statements(op.get_context().dialect.name, enable=True):
        op.execute(statement)


def downgrade() -> None:
    """Drop the table; the lock goes with it."""
    op.drop_index("ix_synced_day_hikes_profile_updated", table_name="synced_day_hikes")
    op.drop_table("synced_day_hikes")
