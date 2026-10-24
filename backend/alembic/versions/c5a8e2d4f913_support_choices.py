"""support choices

Revision ID: c5a8e2d4f913
Revises: b4d8e1f7a263
Create Date: 2026-10-23 01:00:00.000000

What a hiker chose to give OurHike, paid choices only (#1876): a $0 answer
stays on the phone and never reaches a table. See app/models/support.py for
the life of a row and why the email is stored here when core/auth.py's own
rule is that nothing stores it.

Indexed on `profile_id` (the signed-in "my support" read), `email` and
`provider_ref` (the two keys Buy Me a Coffee's webhook can match on), and
`status`. Plain `ix_<table>_<column>` names, as the models declare them, so
the drift check compares like with like.

RLS is enabled here because this revision adds the table (b3d1c7a94e02's
rule, tests/test_migration_rls.py's union): PostgREST would otherwise serve
every supporter's email and amount to anyone holding the anon key.

Additive and reversible: downgrade drops the table and nothing else.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c5a8e2d4f913"
down_revision: Union[str, Sequence[str], None] = "b4d8e1f7a263"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# The tables this revision locks - see b3d1c7a94e02 for the mechanism.
RLS_TABLES: tuple[str, ...] = ("support_choices",)


def rls_statements(dialect_name: str, *, enable: bool) -> list[str]:
    """Same shape as b3d1c7a94e02's, for the same testability reason."""
    if dialect_name != "postgresql":
        return []
    verb = "ENABLE" if enable else "DISABLE"
    return [f"ALTER TABLE public.{table} {verb} ROW LEVEL SECURITY" for table in RLS_TABLES]


def upgrade() -> None:
    """Create the table, and lock it before anything can reach it."""
    op.create_table(
        "support_choices",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("profile_id", sa.String(), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("provider_ref", sa.String(length=100), nullable=True),
        sa.Column("psp_ref", sa.String(length=100), nullable=True),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column(
            "cadence",
            sa.Enum("year", "month", name="supportcadence", native_enum=False, length=10),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "active",
                "stop_requested",
                "stopped",
                name="supportstatus",
                native_enum=False,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("accounting_email", sa.Boolean(), nullable=False),
        sa.Column("migrate_notice_at", sa.DateTime(), nullable=True),
        sa.Column("chosen_at", sa.DateTime(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("stop_requested_at", sa.DateTime(), nullable=True),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_support_choices_profile_id", "support_choices", ["profile_id"])
    op.create_index("ix_support_choices_email", "support_choices", ["email"])
    op.create_index("ix_support_choices_provider_ref", "support_choices", ["provider_ref"])
    op.create_index("ix_support_choices_status", "support_choices", ["status"])

    for statement in rls_statements(op.get_bind().dialect.name, enable=True):
        op.execute(statement)


def downgrade() -> None:
    """Unlock, then drop - the reverse of upgrade, and only this table."""
    for statement in rls_statements(op.get_bind().dialect.name, enable=False):
        op.execute(statement)
    op.drop_index("ix_support_choices_status", table_name="support_choices")
    op.drop_index("ix_support_choices_provider_ref", table_name="support_choices")
    op.drop_index("ix_support_choices_email", table_name="support_choices")
    op.drop_index("ix_support_choices_profile_id", table_name="support_choices")
    op.drop_table("support_choices")
