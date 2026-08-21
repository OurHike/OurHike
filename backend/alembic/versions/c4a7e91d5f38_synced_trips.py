"""trips and the planned hike follow the account

Revision ID: c4a7e91d5f38
Revises: b6d3f18a2c74
Create Date: 2026-08-21 12:20:00.000000

Phase B of features/ACCOUNT_SYNC.md (#892). A section hiker lays out four
days on a laptop and leaves with a phone, and until these tables the
laptop's plan did not exist on the phone in any form.

Two tables rather than one, and app/models/synced_trip.py argues both at
length. In short: trips are many and need a delta, so `id`, `updated_at` and
`deleted_at` are real columns - they are exactly what the sync queries on,
and a JSON blob you have to open to find the changed rows is not a delta.
The planned hike is a singleton with no id and the one thing here that does
NOT keep both on a conflict, so it is visibly separate rather than quietly
mixed in.

`document` is nullable because a tombstone drops it: what a hiker deleted is
not something this table should go on holding. The ROW stays, because a
deletion has to exist in order to travel - a row that vanished would be
indistinguishable from one a device has not heard about yet, and "a phone
that has not synced since March" must never read as "March's trips are
gone".

RLS: both tables are added to the union tests/test_migration_rls.py checks
against Base.metadata, so leaving either out fails the suite. It matters
more here than for most: these rows are a hiker's own private planning,
served to nobody, and PostgREST would otherwise hand the whole document to
anyone holding the anon key.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4a7e91d5f38"
down_revision: Union[str, Sequence[str], None] = "b6d3f18a2c74"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# The tables this revision locks - see b3d1c7a94e02 for the mechanism and
# tests/test_migration_rls.py for the guard that unions these lists.
RLS_TABLES: tuple[str, ...] = ("synced_trips", "synced_planned_hikes")


def rls_statements(dialect_name: str, *, enable: bool) -> list[str]:
    """Same shape as b3d1c7a94e02's, for the same testability reason."""
    if dialect_name != "postgresql":
        return []
    verb = "ENABLE" if enable else "DISABLE"
    return [f"ALTER TABLE public.{table} {verb} ROW LEVEL SECURITY" for table in RLS_TABLES]


def upgrade() -> None:
    """Create the tables, and lock them before anything can reach them."""
    op.create_table(
        "synced_trips",
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
        "ix_synced_trips_profile_updated",
        "synced_trips",
        ["profile_id", "updated_at"],
        unique=False,
    )

    op.create_table(
        "synced_planned_hikes",
        sa.Column("profile_id", sa.String(), nullable=False),
        sa.Column("start_mile", sa.Float(), nullable=True),
        sa.Column("end_mile", sa.Float(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"]),
        sa.PrimaryKeyConstraint("profile_id"),
    )

    for statement in rls_statements(op.get_context().dialect.name, enable=True):
        op.execute(statement)


def downgrade() -> None:
    """Drop the tables; the locks go with them."""
    op.drop_table("synced_planned_hikes")
    op.drop_index("ix_synced_trips_profile_updated", table_name="synced_trips")
    op.drop_table("synced_trips")
