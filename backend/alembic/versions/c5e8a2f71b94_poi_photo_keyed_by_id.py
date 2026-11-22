"""Whether a waypoint photo's object is keyed by the row's id.

#1918 item 2: a waypoint photo's object key was
`poi-photos/{poi_id}/{contributor_id}.jpg`, and the public gallery's signed
URL shows the key, so a photo shared inside its hiker's anonymity window
named the same account id as that hiker's credited photos. New uploads are
keyed by the row's own random id instead (core/photos.py `poi_photo_key`).

The objects already in the bucket are not moved by this revision, because a
migration has no business in the photo bucket. So every existing row starts
false and is still read at its old key (`stored_poi_photo_key`). Its URL
keeps naming its contributor until that hiker uploads again, or until
somebody copies the legacy objects and sets the flag.

`server_default` false, so the release still running during the rollout,
which writes no value, writes rows that are read at the key it stored them
under.

Revision ID: c5e8a2f71b94
Revises: f2b9d4c7e1a3
Create Date: 2026-11-22
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "c5e8a2f71b94"
down_revision = "f2b9d4c7e1a3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "poi_photos",
        sa.Column("keyed_by_id", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("poi_photos", "keyed_by_id")
