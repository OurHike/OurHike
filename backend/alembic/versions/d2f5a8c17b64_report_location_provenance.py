"""where a report's coordinates came from, who signed it, and whether they may be contacted

Revision ID: d2f5a8c17b64
Revises: c3a8f1d6e2b7
Create Date: 2026-09-17 15:30:00.000000

Six columns on `reports`, for #1563 - A one-tap report can file with no
place at all, and nothing records how sure the phone was about where it
stood - and the maintainer's three additions to it on 2026-09-17.

THE PLACE, AND HOW FAR TO TRUST IT: three nullable columns.

`location_source` - `poi`, `gps` or `map`: whether `lat`/`lon` are a named
waypoint's, the phone's own fix, or a spot the hiker marked by hand.
`location_accuracy_m` - the platform's stated radius for a fix, in metres, as
`position.coords.accuracy` gives it (a 95% radius under the W3C definition;
the client records the web watch only, never the native plugin's 68% figure
lib/gpsTrace.ts keeps apart). `location_fix_age_s` - how many seconds old the
fix was when the report took it, which is the number that says whether a
5 m radius means anything: the client's watch keeps the last fix through a
pocketed pause (#313), so a report filed as the phone comes out of a pack can
carry a fix from a mile back. app/models/report.py's column comment is the
full reasoning.

**No backfill, and none is possible.** Every existing row was filed by a
client that stated none of this, and a null here is the honest record of that
- the same refusal d4a91c3e7b25 made about `mile`. Zero would be a claim of a
perfect fix that no phone ever made.

WHO SIGNED IT, AND WHETHER THEY MAY BE CONTACTED: `signed_name`, the name
the hiker chose to put behind this one report, and `signed_name_kind` -
`trail` or `real` - saying which of their names it is; `contact_ok`, their
answer to "You can contact me for more information", NOT NULL and false by
server default, because an unticked box is not a yes and the previous release
is still inserting rows that know nothing about the column (the same rollout
window c9d1a7f48b62's `photo_count` default is for). Never served to the
public - app/schemas/report.py withholds all three like `reporter_id` - and
cleared by account deletion.

**Expand only.** Nothing is dropped or renamed; the previous release keeps
inserting rows that know nothing about these columns, and they land as null,
which is what RELEASING.md §8c's rollout window needs.

**No RLS statement, and that is not an oversight.** RLS is a table property
(b3d1c7a94e02) and this adds no table; `reports` is already locked.

Revises c3a8f1d6e2b7 because that is the head of the chain on `main` as this
is written (2026-09-17); a second head cannot migrate.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "d2f5a8c17b64"
down_revision: Union[str, Sequence[str], None] = "c3a8f1d6e2b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "reports",
        sa.Column(
            "location_source",
            sa.Enum("poi", "gps", "map", name="locationsource", native_enum=False, length=20),
            nullable=True,
        ),
    )
    op.add_column("reports", sa.Column("location_accuracy_m", sa.Float(), nullable=True))
    op.add_column("reports", sa.Column("location_fix_age_s", sa.Integer(), nullable=True))
    op.add_column("reports", sa.Column("signed_name", sa.Text(), nullable=True))
    op.add_column(
        "reports",
        sa.Column(
            "signed_name_kind",
            sa.Enum("trail", "real", name="signednamekind", native_enum=False, length=20),
            nullable=True,
        ),
    )
    op.add_column(
        "reports",
        sa.Column("contact_ok", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )


def downgrade() -> None:
    op.drop_column("reports", "contact_ok")
    op.drop_column("reports", "signed_name_kind")
    op.drop_column("reports", "signed_name")
    op.drop_column("reports", "location_fix_age_s")
    op.drop_column("reports", "location_accuracy_m")
    op.drop_column("reports", "location_source")
