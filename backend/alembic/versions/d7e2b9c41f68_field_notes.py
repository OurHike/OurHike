"""field notes

Revision ID: d7e2b9c41f68
Revises: c2f47a8d1b60
Create Date: 2026-08-20 03:30:00.000000

The record behind features/FIELD_NOTES.md: a dated observation about a
place (`field_notes`), and the flag that is the whole moderation entry
point for one (`note_flags`). See app/models/field_note.py for why a note
publishes immediately and is hidden-never-deleted, and for the
`observed_at`/`posted_at` split.

Indexes follow a1b7c3d95e04's rule - the columns the hot queries filter on,
added while the table is empty. The public list filters `hidden_at IS NULL`
on every read; the card's read and the bake's per-POI roll-up filter
`poi_id`; the queue joins `note_flags.note_id`; "this account's notes" (a
moderator reviewing a pattern) scans `reporter_id`.

RLS is enabled here because this revision adds the tables - b3d1c7a94e02's
list describes the schema at its own point in time, and
tests/test_migration_rls.py unions every revision's RLS_TABLES and fails on
anything left out. It matters here for the same reason it does on reports:
PostgREST would otherwise serve `reporter_id` beside `observed_at` and a
position to anyone holding the anon key, which is the
route-reconstruction pair #252 removed from the report API.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d7e2b9c41f68"
down_revision: Union[str, Sequence[str], None] = "c2f47a8d1b60"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# The tables this revision locks - see b3d1c7a94e02 for the mechanism and
# tests/test_migration_rls.py for the guard that unions these lists.
RLS_TABLES: tuple[str, ...] = ("field_notes", "note_flags")


def rls_statements(dialect_name: str, *, enable: bool) -> list[str]:
    """Same shape as b3d1c7a94e02's, for the same testability reason."""
    if dialect_name != "postgresql":
        return []
    verb = "ENABLE" if enable else "DISABLE"
    return [f"ALTER TABLE public.{table} {verb} ROW LEVEL SECURITY" for table in RLS_TABLES]


def upgrade() -> None:
    """Create both tables, and lock them before anything can reach them."""
    op.create_table(
        "field_notes",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("reporter_id", sa.String(), nullable=False),
        sa.Column("poi_id", sa.String(), nullable=True),
        sa.Column("lat", sa.Float(), nullable=True),
        sa.Column("lon", sa.Float(), nullable=True),
        sa.Column("mile", sa.Float(), nullable=True),
        sa.Column(
            "observation",
            sa.Enum(
                "flowing",
                "trickling",
                "dry",
                "fine",
                "damaged",
                "full",
                "open",
                "limited",
                "closed",
                "not_found",
                name="observation",
                native_enum=False,
                length=20,
            ),
            nullable=True,
        ),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("observed_at", sa.DateTime(), nullable=False),
        sa.Column("posted_at", sa.DateTime(), nullable=False),
        sa.Column(
            "reporter_type",
            sa.Enum("thru", "section", "day", "maintainer", name="reportertype", native_enum=False, length=20),
            nullable=False,
        ),
        sa.Column("hidden_at", sa.DateTime(), nullable=True),
        sa.Column("hidden_by", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["reporter_id"], ["profiles.id"]),
        sa.ForeignKeyConstraint(["hidden_by"], ["profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_field_notes_reporter_id"), "field_notes", ["reporter_id"], unique=False)
    op.create_index(op.f("ix_field_notes_poi_id"), "field_notes", ["poi_id"], unique=False)
    op.create_index(op.f("ix_field_notes_hidden_at"), "field_notes", ["hidden_at"], unique=False)

    op.create_table(
        "note_flags",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("note_id", sa.String(), nullable=False),
        sa.Column("flagged_by", sa.String(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["note_id"], ["field_notes.id"]),
        sa.ForeignKeyConstraint(["flagged_by"], ["profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_note_flags_note_id"), "note_flags", ["note_id"], unique=False)

    for statement in rls_statements(op.get_context().dialect.name, enable=True):
        op.execute(statement)


def downgrade() -> None:
    """Drop both tables; the locks go with them. Flags first - they hold the
    only foreign key between the two."""
    op.drop_index(op.f("ix_note_flags_note_id"), table_name="note_flags")
    op.drop_table("note_flags")
    op.drop_index(op.f("ix_field_notes_hidden_at"), table_name="field_notes")
    op.drop_index(op.f("ix_field_notes_poi_id"), table_name="field_notes")
    op.drop_index(op.f("ix_field_notes_reporter_id"), table_name="field_notes")
    op.drop_table("field_notes")
