"""carry the trail mile a report was written at

Revision ID: d4a91c3e7b25
Revises: c7e5a21f8b40
Create Date: 2026-08-07 22:30:00.000000

The report form has been computing this value and throwing it away (#244). It
snaps the GPS fix to the trail index the app already holds, renders it on the
form as "mi 1,407.2", and then submits `lat`/`lon` alone - so the one number
the serious-warnings feature filters on was known at the exact moment it was
discarded, and unavailable to anything server-side forever after.

`features/HIKER_SAFETY.md` §1 is what makes that matter: the warning banner
counts serious reports between a hiker and the end of their route, and the
range it filters is a mile range. The client can re-derive one from `lat`/`lon`
and does - but only when it has both, which a report filed against a `poi_id`
with no fix does not have, and only on a phone, which `/maintainer-assignments`
resolving a thanks by mile is not.

**Nullable, and no backfill.** Null means "not placed on the trail", which is
the honest state for an off-trail fix, for a phone that had not downloaded the
trail index yet, and for every row filed before this column existed. Zero is
Springer Mountain, so it is not a stand-in for "unknown" - the same rule
`describeLocation` keeps on the form and `chrome/Header.tsx` keeps on the mile
readout. Backfilling would mean deriving a position for reports whose position
we do not have, which is a guess wearing a number.

**No RLS statement here, and that is not an oversight.** RLS is a TABLE
property (b3d1c7a94e02) and this adds no table, so the guard in
tests/test_migration_rls.py - which compares `Base.metadata.tables` against
every migration's `RLS_TABLES` - stays satisfied without this revision naming
anything. `reports` is already locked.
"""

import sqlalchemy as sa

from alembic import op

revision = "d4a91c3e7b25"
down_revision = "c7e5a21f8b40"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("reports", sa.Column("mile", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("reports", "mile")
