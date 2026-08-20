"""photo flags reports and reviews

Revision ID: af2ec6bf88f0
Revises: 619320d2b4a9
Create Date: 2026-08-20 00:02:31.020211

The moderation half of the photo store's row (#579, #837): what the phone's
own check claimed at share time (`flagged` - a nudity flag holds the photo
from the gallery until one human glance), a hiker's report against a photo
(`reported_*` - the mechanism that keeps the report-driven rolling twelve
safe without pre-approval), and the glance itself (`reviewed_*`).

Same shape as c7e5a21f8b40 and f2c8d4a91e57, for the same reasons:
nullable, no backfill - null means "nothing found", "nobody reported" and
"nobody has looked", the honest state for every existing row - and no RLS
statement, because RLS is a table property and 619320d2b4a9 already locked
`poi_photos`.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "af2ec6bf88f0"
down_revision: Union[str, Sequence[str], None] = "619320d2b4a9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("poi_photos", sa.Column("flagged", sa.String(), nullable=True))
    op.add_column("poi_photos", sa.Column("reported_at", sa.DateTime(), nullable=True))
    op.add_column("poi_photos", sa.Column("reported_by", sa.String(), nullable=True))
    op.add_column("poi_photos", sa.Column("reported_reason", sa.String(), nullable=True))
    op.add_column("poi_photos", sa.Column("reviewed_at", sa.DateTime(), nullable=True))
    op.add_column("poi_photos", sa.Column("reviewed_by", sa.String(), nullable=True))
    op.create_foreign_key("fk_poi_photos_reported_by_profiles", "poi_photos", "profiles", ["reported_by"], ["id"])
    op.create_foreign_key("fk_poi_photos_reviewed_by_profiles", "poi_photos", "profiles", ["reviewed_by"], ["id"])


def downgrade() -> None:
    op.drop_constraint("fk_poi_photos_reviewed_by_profiles", "poi_photos", type_="foreignkey")
    op.drop_constraint("fk_poi_photos_reported_by_profiles", "poi_photos", type_="foreignkey")
    op.drop_column("poi_photos", "reviewed_by")
    op.drop_column("poi_photos", "reviewed_at")
    op.drop_column("poi_photos", "reported_reason")
    op.drop_column("poi_photos", "reported_by")
    op.drop_column("poi_photos", "reported_at")
    op.drop_column("poi_photos", "flagged")
