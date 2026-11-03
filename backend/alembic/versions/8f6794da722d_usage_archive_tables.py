"""usage archive tables

Revision ID: 8f6794da722d
Revises: 897b71ad5fff
Create Date: 2026-10-29 01:30:00.000000

#1923 - Move each closed month's unlinked usage rows out of Postgres into a
Parquet file in a private R2 bucket. Two tables, both new, nothing existing
touched:

- `analytics_archive_parts`, one row per Parquet file the nightly archive
  step wrote: which month, which part, how many rows, and the file's size and
  SHA-256.
- `analytics_archived_daily`, what the archived rows of each day counted, so
  the nightly checks and the usage report can keep reading daily series from
  Postgres alone (the maintainer's choice, poll 2026-10-29, over handing those
  readers an R2 token).

RLS: both join the union tests/test_migration_rls.py checks, for the reason
897b71ad5fff gives for every usage table - PostgREST would otherwise serve
them to anyone holding the anon key.

THE ROLLUP'S ROLE NEEDS TO READ BOTH, and is granted that here when it
already exists. `_count_late` adds a closed month's archived rows back
(app/core/analytics_rollup.py) and the checks it runs read the daily counts
(app/core/analytics_quality.py), so without these grants the nightly job
would fail with "permission denied" on the night this deployed. The SQL in
features/EVENTING.md §0 grants the same, for a role made after this
migration. The archive's own role, `ourhike_analytics_archive`, is made by
that SQL and only by it: it is new with this revision, so no database holds
it yet.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8f6794da722d"
down_revision: Union[str, Sequence[str], None] = "897b71ad5fff"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# The tables this revision locks - see b3d1c7a94e02 for the mechanism and
# tests/test_migration_rls.py for the guard that unions these lists.
RLS_TABLES: tuple[str, ...] = (
    "analytics_archive_parts",
    "analytics_archived_daily",
)

ROLLUP_ROLE = "ourhike_analytics_rollup"


def rls_statements(dialect_name: str, *, enable: bool) -> list[str]:
    """Same shape as b3d1c7a94e02's, for the same testability reason."""
    if dialect_name != "postgresql":
        return []
    verb = "ENABLE" if enable else "DISABLE"
    return [f"ALTER TABLE public.{table} {verb} ROW LEVEL SECURITY" for table in RLS_TABLES]


def grant_statements(dialect_name: str, role: str = ROLLUP_ROLE) -> list[str]:
    """Read access for a rollup role made before these tables existed. Postgres only.

    `role` is a parameter for tests/test_analytics_archive.py, which runs the
    statement against its own user: the test database's user may not create
    roles, and a typo inside a PL/pgSQL branch nobody took would otherwise
    first be found by the deploy that took it.
    """
    if dialect_name != "postgresql":
        return []
    grants = "\n".join(
        f"    GRANT SELECT ON public.{table} TO {role};\n"
        f"    CREATE POLICY rollup_{table.removeprefix('analytics_')} ON public.{table} "
        f"FOR SELECT TO {role} USING (true);"
        for table in RLS_TABLES
    )
    return [f"DO $$ BEGIN\n  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN\n{grants}\n  END IF;\nEND $$;"]


def upgrade() -> None:
    """Create the two tables, lock them, and let an existing rollup role read them."""
    op.create_table(
        "analytics_archive_parts",
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("part", sa.Integer(), nullable=False),
        sa.Column("object_key", sa.String(length=64), nullable=False),
        sa.Column("rows", sa.Integer(), nullable=False),
        sa.Column("bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("written_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("month", "part"),
    )
    op.create_table(
        "analytics_archived_daily",
        sa.Column("local_date", sa.Date(), nullable=False),
        sa.Column("received_on", sa.Date(), nullable=False),
        sa.Column("platform", sa.String(length=8), nullable=False),
        sa.Column("app_version", sa.String(length=40), nullable=False),
        sa.Column("rows", sa.Integer(), nullable=False),
        sa.Column("installs", sa.Integer(), nullable=False),
        sa.Column("logins", sa.Integer(), nullable=False),
        sa.Column("plans_made", sa.Integer(), nullable=False),
        sa.Column("plans_completed", sa.Integer(), nullable=False),
        sa.Column("map_views", sa.Integer(), nullable=False),
        sa.Column("sessions", sa.Integer(), nullable=False),
        sa.Column("pageviews", sa.Integer(), nullable=False),
        sa.Column("phones_this_week", sa.Integer(), nullable=False),
        sa.Column("no_key", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("local_date", "received_on", "platform", "app_version"),
    )

    dialect = op.get_context().dialect.name
    for statement in rls_statements(dialect, enable=True) + grant_statements(dialect):
        op.execute(statement)


def downgrade() -> None:
    """Drop the two tables; their locks, grants and policies go with them."""
    op.drop_table("analytics_archived_daily")
    op.drop_table("analytics_archive_parts")
