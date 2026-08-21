"""field note photos

Revision ID: b6d3f18a2c74
Revises: e9f4a2c73b51
Create Date: 2026-08-21 02:50:00.000000

The photo DATA_NUDGES.md's opted-in mode has promised since July and #759
deliberately did not deliver (#879): "a photo becomes the default, not the
escalation".

Four columns on `field_notes` rather than a table, because a note has at
most one photo and it belongs to that note - see app/models/field_note.py
for why it is keyed by note id rather than reusing the community photo
store, which holds one photo per hiker per waypoint and would let a second
note replace the first note's picture.

`photo_flagged` and `photo_reviewed_at`/`photo_reviewed_by` mirror
`poi_photos`' own vocabulary deliberately: the same on-device check (#837)
feeds both, only the nudity case is held, and a second set of words for one
mechanism is how the two drift apart.

No RLS list change: `field_notes` already enables RLS in d7e2b9c41f68, and
these columns inherit it. That matters here for the reason it did there -
PostgREST would otherwise serve a photo key beside a position to anyone
holding the anon key.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "b6d3f18a2c74"
down_revision: Union[str, None] = "e9f4a2c73b51"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("field_notes", sa.Column("photo_uploaded_at", sa.DateTime(), nullable=True))
    op.add_column("field_notes", sa.Column("photo_flagged", sa.String(), nullable=True))
    op.add_column("field_notes", sa.Column("photo_reviewed_at", sa.DateTime(), nullable=True))
    op.add_column(
        "field_notes",
        sa.Column("photo_reviewed_by", sa.String(), sa.ForeignKey("profiles.id"), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("field_notes", "photo_reviewed_by")
    op.drop_column("field_notes", "photo_reviewed_at")
    op.drop_column("field_notes", "photo_flagged")
    op.drop_column("field_notes", "photo_uploaded_at")
