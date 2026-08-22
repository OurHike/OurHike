"""an account can be deleted, and the row has to survive to say so

Revision ID: d8f3b62a4c17
Revises: c4a7e91d5f38
Create Date: 2026-08-22 11:40:00.000000

Phase E of features/ACCOUNT_SYNC.md (#895). One nullable column, and the
whole argument for it is in app/models/profile.py: five tables hold a NOT
NULL foreign key to `profiles.id` on rows that are not only the hiker's -
a closure other hikers route around, a photo under an irrevocable CC BY-SA
4.0 grant - so `DELETE FROM profiles` either takes those with it or leaves
a dangling key. What gets deleted is the person; the key stays.

No RLS change: `profiles` was locked by b3d1c7a94e02 and adding a column
does not unlock it.

No backfill. Null is the right answer for every row that exists: they are
all live accounts, and a DEFAULT here would be a value nobody meant.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d8f3b62a4c17"
down_revision: Union[str, Sequence[str], None] = "c4a7e91d5f38"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("profiles", sa.Column("deleted_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Drop the column.

    Worth naming what this loses, because it is not symmetric: downgrading
    past this revision erases the only record that an account was ever
    deleted, and the scrubbed rows it left behind stay scrubbed. The trail
    names are already gone; this just stops the database admitting why.
    """
    op.drop_column("profiles", "deleted_at")
