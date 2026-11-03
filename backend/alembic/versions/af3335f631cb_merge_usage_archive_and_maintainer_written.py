"""merge the usage-archive and maintainer-written heads

Revision ID: af3335f631cb
Revises: 8f6794da722d, c3a9e5d27f18
Create Date: 2026-11-03 01:55:00.000000

#1946 - main has two Alembic heads, 8f6794da722d and c3a9e5d27f18, so
migrate.yml cannot upgrade UA and the migration tests fail. Both revisions
were written against 897b71ad5fff: 8f6794da722d in #1936 (Move each closed
month's unlinked usage rows to Parquet in a private R2 bucket, nightly before
the rollup), c3a9e5d27f18 in #1927 (Keep who wrote an org's row in
clubs.maintainer_written, which account deletion cannot null). Each was
linear against main when it was checked, and they merged minutes apart.

NOTHING TO DO IN EITHER DIRECTION. The two branches touch different tables:
8f6794da722d creates `analytics_archive_parts` and `analytics_archived_daily`,
and c3a9e5d27f18 adds one column to `clubs`. So either order gives the same
schema, and this revision only gives `upgrade head` one head to reach again.

A MERGE, NOT A RE-POINTED PARENT. UA was already at 8f6794da722d when this
was written (Migrate run 44 succeeded; run 45, for #1927, could only fail),
and a database that applied the two in the other order would be at
c3a9e5d27f18. Re-pointing either file's `down_revision` would leave one of
those databases calling a head "current" with the other branch's tables
missing. A merge revision is reachable from both.
"""

from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "af3335f631cb"
down_revision: Union[str, Sequence[str], None] = ("8f6794da722d", "c3a9e5d27f18")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Nothing: the two branches it joins touch different tables."""


def downgrade() -> None:
    """Nothing, for the same reason."""
