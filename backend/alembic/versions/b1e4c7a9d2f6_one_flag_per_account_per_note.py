"""one flag per account per note

Revision ID: b1e4c7a9d2f6
Revises: c9d1a7f48b62
Create Date: 2026-09-17 06:40:00.000000

`POST /field-notes/{note_id}/flag` promises "one flag per account per note"
and enforced it with a SELECT before the INSERT (app/routers/field_notes.py)
- the #265 shape. Two flags from one account, sent close enough together,
both find nothing and both insert, and the queue that says it counts
"people, not taps" then counts taps (#1545, item 1). Reasoned from the code
rather than measured under load: the race needs two requests inside one
round trip. The same shape has produced a 500 at every other seam it was
found at (#265, #658).

The constraint is what makes the router's promise true by construction. The
router's own recovery - roll back, answer 200 "already flagged" - is what
keeps the loser from being a 500, exactly as `create_field_note` recovers.

DUPLICATES ALREADY IN THE TABLE are collapsed first, because a unique
constraint cannot be created over rows that violate it. The earliest flag of
each pair is kept: it is the one that put the note in front of a moderator,
and what a duplicate loses is only its own `reason` text, which the queue
reads one-per-account anyway. On the databases this has run against - the
test database, empty - the DELETE removes nothing. Nobody has counted
duplicates on UA or production; run it there and read the row count.
"""

from alembic import op

revision = "b1e4c7a9d2f6"
down_revision = "c9d1a7f48b62"
branch_labels = None
depends_on = None

# The name the model declares (app/models/field_note.py). `alembic check`
# compares the two, so they have to agree on more than existence.
CONSTRAINT = "uq_note_flags_note_flagger"


def upgrade() -> None:
    op.execute(
        """
        DELETE FROM note_flags later
         USING note_flags earlier
         WHERE later.note_id = earlier.note_id
           AND later.flagged_by = earlier.flagged_by
           AND (earlier.created_at, earlier.id) < (later.created_at, later.id)
        """
    )
    op.create_unique_constraint(CONSTRAINT, "note_flags", ["note_id", "flagged_by"])


def downgrade() -> None:
    # The collapsed duplicates do not come back; they were rows the design
    # never meant to hold, and there is nothing to reconstruct them from.
    op.drop_constraint(CONSTRAINT, "note_flags", type_="unique")
