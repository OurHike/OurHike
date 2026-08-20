"""app failure reports

Revision ID: c2f47a8d1b60
Revises: af2ec6bf88f0
Create Date: 2026-08-20 02:14:00.000000

The private inbox behind "It broke while I was out there" (#848,
features/APP_FAILURE_REPORTS.md). One row per report: what broke, where they
were, how to reach them, and which of CLAUDE.md's four harms they say it came
near.

Separate from `reports` on purpose, not for tidiness - see
app/models/app_failure.py. `reports` is serialised to anonymous callers;
this table holds a contact detail, and the two must not be one schema away
from each other.

`reporter_id` is nullable here and NOT NULL on `reports`, which is the
schema-level statement of the same decision: this is the one write in the
app that does not need an account.

Indexed on `reporter_id` only. The other query a maintainer runs is "what
came in since Tuesday", and `received_at` is left unindexed deliberately -
a1b7c3d95e04's reasoning is that an index is cheap while the table is small,
and a sequential scan is cheaper still on a table nobody expects to be large.
If this table ever IS large, something has gone very wrong with the app and
the index is not the finding.

RLS is enabled here rather than in a later revision because this revision
adds the table - b3d1c7a94e02 is explicit that its own list describes the
schema at its point in time, and tests/test_migration_rls.py unions every
revision's RLS_TABLES and fails on anything left out. It matters more than
usual here: PostgREST would otherwise serve `contact` to anyone holding the
anon key, which ships in the client bundle by design.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c2f47a8d1b60"
down_revision: Union[str, Sequence[str], None] = "af2ec6bf88f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# The tables this revision locks - see b3d1c7a94e02 for the mechanism and
# tests/test_migration_rls.py for the guard that unions these lists.
RLS_TABLES: tuple[str, ...] = ("app_failures",)


def rls_statements(dialect_name: str, *, enable: bool) -> list[str]:
    """Same shape as b3d1c7a94e02's, for the same testability reason."""
    if dialect_name != "postgresql":
        return []
    verb = "ENABLE" if enable else "DISABLE"
    return [f"ALTER TABLE public.{table} {verb} ROW LEVEL SECURITY" for table in RLS_TABLES]


def upgrade() -> None:
    """Create the table, and lock it before anything can reach it."""
    op.create_table(
        "app_failures",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("reporter_id", sa.String(), nullable=True),
        sa.Column("what_happened", sa.Text(), nullable=False),
        sa.Column("whereabouts", sa.Text(), nullable=True),
        sa.Column("contact", sa.Text(), nullable=True),
        sa.Column("harms", sa.JSON(), nullable=True),
        sa.Column("build", sa.String(), nullable=True),
        sa.Column("was_offline", sa.Boolean(), nullable=True),
        sa.Column("authored_at", sa.DateTime(), nullable=False),
        sa.Column("received_at", sa.DateTime(), nullable=False),
        sa.Column("answered_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["reporter_id"], ["profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_app_failures_reporter_id"), "app_failures", ["reporter_id"], unique=False)

    for statement in rls_statements(op.get_context().dialect.name, enable=True):
        op.execute(statement)


def downgrade() -> None:
    """Drop the table; the lock goes with it."""
    op.drop_index(op.f("ix_app_failures_reporter_id"), table_name="app_failures")
    op.drop_table("app_failures")
