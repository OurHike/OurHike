"""several photos on a report, and a place named in words

Revision ID: c9d1a7f48b62
Revises: a3f6b81d2e94
Create Date: 2026-09-15 04:10:00.000000

Two additions, both from the front-end review's report-form decisions (#1439).

`photo_count` - HOW MANY OBJECTS THIS REPORT HOLDS. The store has expected
this since it shipped: app/core/photos.py keys a photo `reports/{id}/{n}.jpg`
and says why - "The key is numbered anyway, because the alternative,
`photo.jpg`, would have to be renamed the day a second one is allowed, and
every stored key with it." `FIRST_PHOTO_INDEX = 1` is that day. The keys stay
derived; this column supplies the only part the report id cannot, which is how
far the numbering runs.

Not a `report_photos` table. Every column such a table would hold - the
report, the index, the key - is already derivable from the id, so it would be
a join whose only content is a count.

**Backfilled, and the backfill is not a guess.** A row with a non-null
`photo_url` has exactly one object, because until now one was all the uploader
could write; a row without has none. That is a fact about what the bucket
holds, not an estimate of it, which is the difference between this and
d4a91c3e7b25's refusal to backfill `mile`.

**`photo_url` is untouched.** tests/test_migration_expand_contract.py enforces
RELEASING.md §8c - a column dropped in the same release that stops writing it
breaks the previous release, which is still running during the rollout - so
this revision expands only. The writer keeps both in step (see
`_record_photo` in app/routers/reports.py) and a later revision contracts.

`place_words` - WHERE THE HIKER SAYS IT WAS, when the phone cannot say. Set
only for a report with no coordinates and no `poi_id`, and **never geocoded**:
a typed name turned into coordinates is a confident wrong dot on every phone
that downloads the report, which is exactly what the omitted-not-zeroed rule
on `lat`/`lon`/`mile` exists to prevent. Those three stay null beside it and a
moderator places the report.

**No RLS statement, and that is not an oversight.** RLS is a TABLE property
(b3d1c7a94e02) and this adds no table, so the guard in
tests/test_migration_rls.py stays satisfied without this revision naming
anything. `reports` is already locked.
"""

import sqlalchemy as sa

from alembic import op

revision = "c9d1a7f48b62"
down_revision = "a3f6b81d2e94"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # server_default rather than a Python default alone: the column is NOT
    # NULL and the previous release is still inserting rows that know nothing
    # about it, which is the same rollout window §8c is about.
    op.add_column(
        "reports",
        sa.Column("photo_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("reports", sa.Column("place_words", sa.Text(), nullable=True))

    # One object per report with a photo, none for the rest - see the header
    # for why this is a reading of the bucket rather than an estimate of it.
    op.execute("UPDATE reports SET photo_count = 1 WHERE photo_url IS NOT NULL")


def downgrade() -> None:
    op.drop_column("reports", "place_words")
    op.drop_column("reports", "photo_count")
