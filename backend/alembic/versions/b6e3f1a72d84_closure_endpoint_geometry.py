"""give a closure's two ends a position, so a re-measure cannot move it

Revision ID: b6e3f1a72d84
Revises: a1b7c3d95e04
Create Date: 2026-08-19 16:40:00.000000

`closures` stored only `start_mile_marker`/`end_mile_marker` (#674,
features/POI_IDENTITY.md's "Miles are a projection, not an anchor"). A mile is
a reading against one particular measurement of the centerline, and the ATC
re-measures: the same physical stretch gets a slightly different number, so a
closure authored against this year's measurement refers to a subtly different
stretch under next year's. Nothing about the row changes; the ground under it
does.

`reports.mile` (d4a91c3e7b25) never had this problem, because it travels with
a `lat`/`lon` that no re-measure moves - the mile there is the convenience and
the geometry is the anchor. These four columns give closures the same shape
from the other direction: the author's client turns the miles it was given
into two points via `trailPointAtMile`, and the mile becomes a per-release
projection of the geometry rather than the only thing stored.

**Four columns rather than two, because a closure is a line.** A closure runs
between two miles and both ends move independently under a re-measure - the
ATC does not shift the whole trail by a constant. Storing one midpoint would
lose the length, which is the part a hiker plans around.

**Nullable, and no backfill - deliberately, not as a shortcut.** There is
nothing to backfill *from*: deriving a position for an existing row would mean
projecting its mile through the centerline of whichever release it was
authored against, and pipeline/DATA_RELEASES.md prunes a release 90 days after
supersession, so for most rows that centerline is already gone. Inventing the
position from *today's* centerline would fabricate exactly the accuracy this
column exists to provide - it would record, as a measured anchor, a point
derived from the very measurement the anchor is supposed to survive. Null
means "this closure predates the anchor", the client projects nothing, and the
stored mile is shown as it always was.

**No RLS statement here, and that is not an oversight.** RLS is a TABLE
property (b3d1c7a94e02) and this adds no table, so the guard in
tests/test_migration_rls.py stays satisfied without this revision naming
anything. `closures` is already locked. (e8b4d2f61c93 says the same thing for
the same reason, and it is repeated rather than cross-referenced because the
next person adding a column will read whichever revision they land on.)

**Expand only.** Nothing is dropped and nothing stops being written, so a
release running the previous code against this schema is unaffected
(RELEASING.md §8c). `downgrade` drops all four, which
tests/test_migration_expand_contract.py checks for symmetry per revision
rather than only across the whole chain.
"""

import sqlalchemy as sa

from alembic import op

revision = "b6e3f1a72d84"
down_revision = "a1b7c3d95e04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("closures", sa.Column("start_lat", sa.Float(), nullable=True))
    op.add_column("closures", sa.Column("start_lon", sa.Float(), nullable=True))
    op.add_column("closures", sa.Column("end_lat", sa.Float(), nullable=True))
    op.add_column("closures", sa.Column("end_lon", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("closures", "end_lon")
    op.drop_column("closures", "end_lat")
    op.drop_column("closures", "start_lon")
    op.drop_column("closures", "start_lat")
