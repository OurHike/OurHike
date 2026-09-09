"""long hikes and the active-hike pointer follow the account

Revision ID: a3f6b81d2e94
Revises: f7a3d92c5b18
Create Date: 2026-09-09 05:00:00.000000

#1317. The `Hike` that groups sections became a real object - a trail, an
ordered list of points, a status - and the design handoff asks for
`activeHikeId` to follow the account. A pointer that syncs while the thing
it points at does not is a pointer to nothing on the second device, so both
travel or neither does.

`synced_hikes` is f7a3d92c5b18's shape exactly - client id as the primary
key, an opaque nullable `document`, server-assigned `updated_at`, a
`deleted_at` tombstone, and the one composite index the sync queries on.
Its own table rather than rows in `synced_trips`, for that revision's
reason: `/trips/sync` returns every row past the watermark with nothing to
filter on, so a hike mixed in would ride back to deployed clients and be
dropped by `validateTripStore` as a trip whose plan will not parse.

`synced_active_hikes` is `synced_planned_hikes`' shape - one row per
profile, last write wins - because it is a singleton with no id of its own.
Its `hike_id` is deliberately NOT a foreign key to `synced_hikes.id`: a
device sends the pointer in the same exchange as the hike it names, and
ordering those writes to satisfy a constraint would fail the pointer for a
reason no hiker can act on. app/models/synced_hike.py carries both
arguments, including why hikes are last-write-wins where a trip keeps both.

EXPAND, NOT CONTRACT (RELEASING.md §8c). Nothing is dropped or renamed and
every new request field defaults, so a client running any shipped build
keeps syncing its trips through the same endpoint and simply says nothing
about hikes.

RLS: both tables join the union tests/test_migration_rls.py checks against
Base.metadata, so leaving either out fails the suite. These rows are a
hiker's own private record, served to nobody.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3f6b81d2e94"
down_revision: Union[str, Sequence[str], None] = "f7a3d92c5b18"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# The tables this revision locks - see b3d1c7a94e02 for the mechanism and
# tests/test_migration_rls.py for the guard that unions these lists.
RLS_TABLES: tuple[str, ...] = ("synced_hikes", "synced_active_hikes")


def rls_statements(dialect_name: str, *, enable: bool) -> list[str]:
    """Same shape as b3d1c7a94e02's, for the same testability reason."""
    if dialect_name != "postgresql":
        return []
    verb = "ENABLE" if enable else "DISABLE"
    return [f"ALTER TABLE public.{table} {verb} ROW LEVEL SECURITY" for table in RLS_TABLES]


def upgrade() -> None:
    """Create both tables, and lock them before anything can reach them."""
    op.create_table(
        "synced_hikes",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("profile_id", sa.String(), nullable=False),
        sa.Column("document", sa.JSON(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    # Both columns together: `profile_id` alone would scan a hiker's whole
    # history to answer the question every sync asks.
    op.create_index(
        "ix_synced_hikes_profile_updated",
        "synced_hikes",
        ["profile_id", "updated_at"],
        unique=False,
    )

    op.create_table(
        "synced_active_hikes",
        sa.Column("profile_id", sa.String(), nullable=False),
        # Nullable because null is a real answer - the hiker leaving the
        # long-hike state, which is a decision with a date on it. A missing
        # row means they have never said, and the two are different claims.
        sa.Column("hike_id", sa.String(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"]),
        sa.PrimaryKeyConstraint("profile_id"),
    )

    for statement in rls_statements(op.get_context().dialect.name, enable=True):
        op.execute(statement)


def downgrade() -> None:
    """Drop both tables; the locks go with them."""
    op.drop_table("synced_active_hikes")
    op.drop_index("ix_synced_hikes_profile_updated", table_name="synced_hikes")
    op.drop_table("synced_hikes")
