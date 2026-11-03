"""Bind a challenge entry to the club it was given to, and freeze its tag columns.

Three columns on `challenge_entries`, each closing a hole the second review of
**#1780 — Let a club publish a challenge — places on its own trails that
hikers opt into and tag at camp — starting with the ATC's A.T. Summer Bucket
List** found after 8944239ee32a had already reached UA (migrate.yml ran it on
the merge, 2026-10-01 07:23 UTC), so they are a revision of their own rather
than an edit to that one:

- `club_id`: the club the entry was given to. The CSV used to select by
  `challenge_id` alone, so an id that changed hands - an org deleted, the id
  saved again by another club - handed every earlier entry, names and home
  addresses included, to the new owner.
- `hand_item_ids`, `untagged_item_ids`: how this server held each listed item
  as the entry arrived. The CSV used to compute them from `challenge_tags` at
  download time, so a hiker who pressed Leave after entering (which takes
  their tags back) read as having tagged nothing - an honest entry looking
  fabricated in the one column a club judges it by.

NULLABLE, ALL THREE, and that is the expand half of RELEASING.md §8c rather
than an oversight: the release before this one keeps inserting entries that
know nothing about these columns for as long as the rollout takes, and a NOT
NULL here would fail those inserts. `club_id` cannot take a server default at
all (it is a foreign key to a row that depends on the challenge), and an empty
list as the tag columns' default would claim "nothing untagged", which is the
false sentence this revision exists to stop the CSV printing. Setting NOT NULL
is a later contract revision's, once no running release writes without them.

THE BACKFILL, for rows that exist when this runs. Reasoned, not measured: no
entry can have reached UA yet - `challenges.json` has not been published there
(publish-vector-data has failed on #1797 — The first publish to export all 29
external sources dies after the closures step: silent for 19 minutes, then the
hosted runner is shut down, since before the merge) - so on UA this is
expected to touch nothing. It is written for the deployment where that is not
true:

- `club_id` from `club_challenges` - the club that owns the id now, which is
  the one the CSV would have handed the row to before this revision. A row
  whose id no club owns stays NULL and is downloadable by nobody, as it was
  before (the CSV route has always required the club to own the id).
- The tag columns from `challenge_tags` as they stand now: exactly what the
  old live CSV would have printed at this moment, frozen. That is the best
  this revision can know; what the server held on the day of sending is gone.

A row the previous release inserts during the rollout, after this backfill,
keeps NULLs: no club reads it, and the tag cells print empty. The window is
the length of a rollout, not a feature's lifetime.

Revision ID: d922b35687d9
Revises: 8944239ee32a
Create Date: 2026-10-01
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "d922b35687d9"
down_revision = "8944239ee32a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("challenge_entries", sa.Column("club_id", sa.String(), nullable=True))
    op.add_column("challenge_entries", sa.Column("hand_item_ids", sa.JSON(), nullable=True))
    op.add_column("challenge_entries", sa.Column("untagged_item_ids", sa.JSON(), nullable=True))
    op.create_foreign_key(
        "fk_challenge_entries_club_id_clubs",
        "challenge_entries",
        "clubs",
        ["club_id"],
        ["id"],
    )
    op.create_index(op.f("ix_challenge_entries_club_id"), "challenge_entries", ["club_id"], unique=False)

    _backfill(op.get_bind())


def _backfill(bind: sa.engine.Connection) -> None:
    """See the module docstring's "THE BACKFILL". In Python rather than SQL so
    the JSON lists are built the same way on every dialect the suite runs."""
    entries = sa.table(
        "challenge_entries",
        sa.column("id", sa.String()),
        sa.column("user_id", sa.String()),
        sa.column("challenge_id", sa.String()),
        sa.column("item_ids", sa.JSON()),
        sa.column("club_id", sa.String()),
        sa.column("hand_item_ids", sa.JSON()),
        sa.column("untagged_item_ids", sa.JSON()),
    )
    owners = sa.table("club_challenges", sa.column("challenge_id", sa.String()), sa.column("club_id", sa.String()))
    tags = sa.table(
        "challenge_tags",
        sa.column("user_id", sa.String()),
        sa.column("challenge_id", sa.String()),
        sa.column("item_id", sa.String()),
        sa.column("how", sa.String()),
    )

    owner_of = dict(bind.execute(sa.select(owners.c.challenge_id, owners.c.club_id)).all())
    for row in bind.execute(sa.select(entries.c.id, entries.c.user_id, entries.c.challenge_id, entries.c.item_ids)).all():
        held = dict(
            bind.execute(
                sa.select(tags.c.item_id, tags.c.how).where(
                    tags.c.user_id == row.user_id, tags.c.challenge_id == row.challenge_id
                )
            ).all()
        )
        item_ids = [str(item) for item in (row.item_ids or [])]
        bind.execute(
            entries.update()
            .where(entries.c.id == row.id)
            .values(
                club_id=owner_of.get(row.challenge_id),
                hand_item_ids=[item for item in item_ids if held.get(item) == "hand"],
                untagged_item_ids=[item for item in item_ids if item not in held],
            )
        )


def downgrade() -> None:
    op.drop_index(op.f("ix_challenge_entries_club_id"), table_name="challenge_entries")
    op.drop_constraint("fk_challenge_entries_club_id_clubs", "challenge_entries", type_="foreignkey")
    op.drop_column("challenge_entries", "untagged_item_ids")
    op.drop_column("challenge_entries", "hand_item_ids")
    op.drop_column("challenge_entries", "club_id")
