"""volunteer hours

Revision ID: e9f4a2c73b51
Revises: d7e2b9c41f68
Create Date: 2026-08-20 04:00:00.000000

The self-logged, club-confirmed hours behind VOLUNTEERING.md §4 (#761):
claimed on filing, confirmed when a club admin stands behind the number,
disputed when one refuses to. See app/models/volunteer_hours.py for why
`club_id` is nullable against the design sketch and why `work_project_id`
is a soft string rather than a foreign key.

Indexed on `user_id` alone - the dashboard's "my hours" is the hot query.
The moderator queue filters `state`, and a1b7c3d95e04's cheap-while-small
argument would cover an index there too; left off because the queue is a
moderation surface read occasionally by few, and `reports.status` earned
its index by being on the public list every phone loads.

RLS is enabled here because this revision adds the table (b3d1c7a94e02's
rule, tests/test_migration_rls.py's union): PostgREST would otherwise serve
every volunteer's hours - with locations and free-text notes - to anyone
holding the anon key, on the resource whose whole design is that the record
is private.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e9f4a2c73b51"
down_revision: Union[str, Sequence[str], None] = "d7e2b9c41f68"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# The tables this revision locks - see b3d1c7a94e02 for the mechanism.
RLS_TABLES: tuple[str, ...] = ("volunteer_hours",)


def rls_statements(dialect_name: str, *, enable: bool) -> list[str]:
    """Same shape as b3d1c7a94e02's, for the same testability reason."""
    if dialect_name != "postgresql":
        return []
    verb = "ENABLE" if enable else "DISABLE"
    return [f"ALTER TABLE public.{table} {verb} ROW LEVEL SECURITY" for table in RLS_TABLES]


def upgrade() -> None:
    """Create the table, and lock it before anything can reach it."""
    op.create_table(
        "volunteer_hours",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("club_id", sa.String(), nullable=True),
        sa.Column("worked_on", sa.Date(), nullable=False),
        sa.Column("hours", sa.Float(), nullable=False),
        sa.Column("work_project_id", sa.String(), nullable=True),
        sa.Column(
            "activity",
            sa.Enum(
                "maintenance",
                "cleanup",
                "monitoring",
                "education",
                "admin",
                "other",
                name="hoursactivity",
                native_enum=False,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("mile", sa.Float(), nullable=True),
        sa.Column("lat", sa.Float(), nullable=True),
        sa.Column("lon", sa.Float(), nullable=True),
        sa.Column(
            "state",
            sa.Enum("claimed", "confirmed", "disputed", name="hoursstate", native_enum=False, length=20),
            nullable=False,
        ),
        sa.Column("confirmed_by", sa.String(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
        sa.Column("recorded_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["profiles.id"]),
        sa.ForeignKeyConstraint(["club_id"], ["clubs.id"]),
        sa.ForeignKeyConstraint(["confirmed_by"], ["profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_volunteer_hours_user_id"), "volunteer_hours", ["user_id"], unique=False)

    for statement in rls_statements(op.get_context().dialect.name, enable=True):
        op.execute(statement)


def downgrade() -> None:
    """Drop the table; the lock goes with it."""
    op.drop_index(op.f("ix_volunteer_hours_user_id"), table_name="volunteer_hours")
    op.drop_table("volunteer_hours")
