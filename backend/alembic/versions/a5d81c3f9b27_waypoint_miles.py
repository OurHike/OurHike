"""waypoint_miles: where each waypoint sits on the A.T., for GET /disputes

Revision ID: a5d81c3f9b27
Revises: b4d8e1f7a263
Create Date: 2026-10-27 16:00:00.000000

**#1917 — A maintainer's note settles a water dispute anywhere on the trail,
because the covering check reads the mile the note's author typed, not where
the waypoint is.** The maintainer chose option 2 by poll on 2026-10-27: give
the backend the waypoint miles. One row per waypoint the published export
gives a mile, loaded by `load_waypoint_miles.py`; nothing writes it over HTTP.

Created empty. Until the loader has run against an environment, no waypoint
has a mile there, so no maintainer's note carries a maintainer's weight in
`GET /disputes`: every note counts as anybody's, two to put "reported
missing" on a pin and two to take it off. That is the state to load out of,
not one to leave a deployment in.

Locked like every other table (b3d1c7a94e02, tests/test_migration_rls.py).
Additive and reversible: downgrade drops the table.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a5d81c3f9b27"
down_revision: str | Sequence[str] | None = "b4d8e1f7a263"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The table this revision locks - see b3d1c7a94e02 for the mechanism and
# tests/test_migration_rls.py for the guard that unions these lists.
RLS_TABLES: tuple[str, ...] = ("waypoint_miles",)


def rls_statements(dialect_name: str, *, enable: bool) -> list[str]:
    """Same shape as b3d1c7a94e02's, for the same testability reason."""
    if dialect_name != "postgresql":
        return []
    verb = "ENABLE" if enable else "DISABLE"
    return [f"ALTER TABLE public.{table} {verb} ROW LEVEL SECURITY" for table in RLS_TABLES]


def upgrade() -> None:
    """Create the table, and lock it before anything can reach it."""
    op.create_table(
        "waypoint_miles",
        sa.Column("poi_id", sa.String(), nullable=False),
        sa.Column("mile", sa.Float(), nullable=False),
        sa.Column("loaded_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("poi_id"),
    )
    for statement in rls_statements(op.get_context().dialect.name, enable=True):
        op.execute(statement)


def downgrade() -> None:
    op.drop_table("waypoint_miles")
