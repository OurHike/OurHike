"""give the closure sheet the three fields it renders

Revision ID: e8b4d2f61c93
Revises: d4a91c3e7b25
Create Date: 2026-08-08 02:20:00.000000

`ClosureDetail` in client/src/chrome/ClosureSheet.tsx extends the shared
`Closure` shape with four fields, and the backend could supply none of them
(#245). Three of the four are facts about the closure and get a column here.
The fourth, `marked_by`, is a fact about a *person*, and is deleted from the
client type in the same change rather than given a column - see below.

**`closed_since`** is not `reported_at` and not `verified_at`. Those are when
somebody filed it and when a moderator confirmed it; neither is when the trail
shut. A closure reported four days after a storm is four days old on the day it
arrives, and the sheet's "Closed since <date>" is the line a hiker reads to
decide whether the information is about this week's washout or last spring's.

**`expected_reopen`** is the other half of that question and has no analogue at
all in the existing columns.

**`reroute_url`** was the one this issue proposed deleting, on the grounds that
it sits oddly beside the app's stated no-detours position. Reading the
component settles it the other way: the sheet's own closing line is "OurHike
does not work out detours. Follow the club's notice, or the signage on the
ground", and `reroute_url` is the link to that notice. The no-detours position
is about OurHike not computing a route - it is not a position against pointing
at what the club published. `ClosureStatus.reroute_available` has existed since
the initial schema and, without this column, was a status the app could show
while having nowhere to say where the reroute is.

**All three are maintainer-set, not reporter-set.** They join `ClosureUpdate`,
which is role-gated to maintainer/club_admin, and stay out of `ClosureCreate`
entirely - matching the reasoning already written into
app/models/closure.py's `status` column, where reporting that a trail is shut
and judging when it will reopen are different jobs. `reroute_url` in
particular renders as an outbound link, so accepting one from any authenticated
reporter would put an unreviewed destination on a safety sheet.

**Nullable, and no backfill.** Null means "not known", which is the honest
state for every closure filed before these existed and for most after - a
storm closure rarely arrives with a reopening date. The client already treats
each as optional and omits the line rather than rendering "unknown", with the
comment "expected reopen: unknown reads as a promise nobody made".

**No RLS statement here, and that is not an oversight.** RLS is a TABLE
property (b3d1c7a94e02) and this adds no table, so the guard in
tests/test_migration_rls.py - which compares `Base.metadata.tables` against
every migration's `RLS_TABLES` - stays satisfied without this revision naming
anything. `closures` is already locked.
"""

import sqlalchemy as sa

from alembic import op

revision = "e8b4d2f61c93"
down_revision = "d4a91c3e7b25"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("closures", sa.Column("closed_since", sa.DateTime(), nullable=True))
    op.add_column("closures", sa.Column("expected_reopen", sa.DateTime(), nullable=True))
    op.add_column("closures", sa.Column("reroute_url", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("closures", "reroute_url")
    op.drop_column("closures", "expected_reopen")
    op.drop_column("closures", "closed_since")
