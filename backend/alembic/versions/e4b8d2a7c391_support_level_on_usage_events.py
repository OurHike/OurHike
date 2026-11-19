"""support level on usage events

Revision ID: e4b8d2a7c391
Revises: c5a8e2d4f913
Create Date: 2026-10-27 21:00:00.000000

#1876 on #1902: a support choice is counted as a seventh usage event,
`support_chosen`, carrying its level and nothing else (the maintainer, poll
2026-10-27). The event name needs nothing here - `analytics_events.event` is a
non-native enum, a VARCHAR(24) - so this is one nullable column, the level in
US cents a year.

THE ROLLUP'S ROLE READS COLUMN BY COLUMN. `ourhike_analytics_rollup` is
granted SELECT on a list of named columns, every one but `sealed`
(features/EVENTING.md §0, "The rollup's role"), so a column added after the
role was made is one it cannot read, and the nightly rollup would fail on it
with "permission denied". Granted here when the role already exists; the SQL
in EVENTING.md names it too, for a role made after this migration.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e4b8d2a7c391"
down_revision: Union[str, Sequence[str], None] = "c5a8e2d4f913"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ROLLUP_ROLE = "ourhike_analytics_rollup"


def grant_statements(dialect_name: str) -> list[str]:
    """The grant for a rollup role made before this column existed. Postgres only:
    the role, and column grants, are Postgres's."""
    if dialect_name != "postgresql":
        return []
    return [
        f"""
        DO $$ BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{ROLLUP_ROLE}') THEN
            GRANT SELECT (support_cents) ON public.analytics_events TO {ROLLUP_ROLE};
          END IF;
        END $$;
        """
    ]


def upgrade() -> None:
    op.add_column("analytics_events", sa.Column("support_cents", sa.Integer(), nullable=True))
    for statement in grant_statements(op.get_bind().dialect.name):
        op.execute(statement)


def downgrade() -> None:
    # Dropping the column drops its column grant with it.
    op.drop_column("analytics_events", "support_cents")
