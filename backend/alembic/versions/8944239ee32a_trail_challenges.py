"""trail challenges

Revision ID: 8944239ee32a
Revises: a7c2e9f41d06
Create Date: 2026-09-30 12:00:00.000000

The server half of #1780 - Let a club publish a challenge - places on its
own trails that hikers opt into and tag at camp - starting with the ATC's
A.T. Summer Bucket List (features/CHALLENGES.md "On the server"). Three
tables, all new, so nothing here touches a running release:

- `challenge_tags`: one row per place a hiker tagged, keyed by the outbox's
  own id and unique on (hiker, challenge, item).
- `challenge_entries`: what a hiker sent a club at the finish - an entry, or
  a finished notice - one per hiker per challenge.
- `club_challenges`: a club's saved definition, and the link that makes a
  challenge id that club's.

See app/models/trail_challenge.py for why `challenge_id` and `item_id` are
soft strings rather than foreign keys (a challenge is a reviewed file the
pipeline publishes, `volunteer_hours.work_project_id`'s precedent).

Indexed on `user_id` for both hiker tables and on `club_id` for the console's
list, beside the unique constraints. Not on `challenge_id`, which the
console's counts and CSV filter on: those are an admin's occasional reads,
e9f4a2c73b51's reason for leaving the moderator queue's `state` unindexed.
What would change that is those reads showing up slow.

RLS is enabled here because this revision adds the tables (b3d1c7a94e02's
rule, tests/test_migration_rls.py's union). `challenge_entries` is the one
that matters most: names, email addresses and home addresses a hiker sent
one club, which PostgREST would otherwise serve to anyone holding the anon
key.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8944239ee32a"
down_revision: Union[str, Sequence[str], None] = "a7c2e9f41d06"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# The tables this revision locks - see b3d1c7a94e02 for the mechanism.
RLS_TABLES: tuple[str, ...] = ("challenge_tags", "challenge_entries", "club_challenges")


def rls_statements(dialect_name: str, *, enable: bool) -> list[str]:
    """Same shape as b3d1c7a94e02's, for the same testability reason."""
    if dialect_name != "postgresql":
        return []
    verb = "ENABLE" if enable else "DISABLE"
    return [f"ALTER TABLE public.{table} {verb} ROW LEVEL SECURITY" for table in RLS_TABLES]


def upgrade() -> None:
    """Create the three tables, and lock them before anything can reach them."""
    op.create_table(
        "challenge_tags",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("challenge_id", sa.String(length=120), nullable=False),
        sa.Column("item_id", sa.String(length=120), nullable=False),
        sa.Column(
            "how",
            sa.Enum("gps", "hand", name="taghow", native_enum=False, length=10),
            nullable=False,
        ),
        sa.Column("authored_at", sa.DateTime(), nullable=False),
        sa.Column("received_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "challenge_id", "item_id", name="uq_challenge_tags_user_challenge_item"),
    )
    op.create_index(op.f("ix_challenge_tags_user_id"), "challenge_tags", ["user_id"], unique=False)

    op.create_table(
        "challenge_entries",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("challenge_id", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("mailing_address", sa.Text(), nullable=True),
        sa.Column("item_ids", sa.JSON(), nullable=False),
        sa.Column("finished_only", sa.Boolean(), nullable=False),
        sa.Column("consented_at", sa.DateTime(), nullable=False),
        sa.Column("sent_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "challenge_id", name="uq_challenge_entries_user_challenge"),
    )
    op.create_index(op.f("ix_challenge_entries_user_id"), "challenge_entries", ["user_id"], unique=False)

    op.create_table(
        "club_challenges",
        sa.Column("challenge_id", sa.String(length=120), nullable=False),
        sa.Column("club_id", sa.String(), nullable=False),
        sa.Column("definition", sa.JSON(), nullable=False),
        sa.Column("window_closes", sa.Date(), nullable=True),
        sa.Column("takes_entries", sa.Boolean(), nullable=False),
        sa.Column("pr_url", sa.String(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("updated_by", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["club_id"], ["clubs.id"]),
        sa.ForeignKeyConstraint(["updated_by"], ["profiles.id"]),
        sa.PrimaryKeyConstraint("challenge_id"),
    )
    op.create_index(op.f("ix_club_challenges_club_id"), "club_challenges", ["club_id"], unique=False)

    for statement in rls_statements(op.get_context().dialect.name, enable=True):
        op.execute(statement)


def downgrade() -> None:
    """Drop the tables; the locks go with them."""
    op.drop_index(op.f("ix_club_challenges_club_id"), table_name="club_challenges")
    op.drop_table("club_challenges")
    op.drop_index(op.f("ix_challenge_entries_user_id"), table_name="challenge_entries")
    op.drop_table("challenge_entries")
    op.drop_index(op.f("ix_challenge_tags_user_id"), table_name="challenge_tags")
    op.drop_table("challenge_tags")
