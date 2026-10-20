"""indexes on nine columns the routers filter or order on

Revision ID: b4d8e1f7a263
Revises: d922b35687d9
Create Date: 2026-10-08 03:00:00.000000

**#1766 — Seven columns the routers filter or order on have no index** lists
them from reading each router's query against the models on `main` at
0efac90; nothing here has been measured with EXPLAIN against a populated table,
so this migration rests on that reading and on no query plan. It is the second
batch after a1b7c3d95e04, which added the first indexes deliberately late.

Plain `ix_<table>_<column>` names, because the models declare the same indexes
with `index=True` and the drift check compares the two.

Additive and reversible: no data moves, and downgrade drops exactly these.
"""

from alembic import op

revision = "b4d8e1f7a263"
down_revision = "d922b35687d9"
branch_labels = None
depends_on = None

_INDEXES = [
    ("ix_hikes_user_id", "hikes", "user_id"),
    ("ix_reports_timestamp", "reports", "timestamp"),
    ("ix_reports_type", "reports", "type"),
    ("ix_reports_maintainer_id", "reports", "maintainer_id"),
    ("ix_reports_club_id", "reports", "club_id"),
    ("ix_field_notes_observed_at", "field_notes", "observed_at"),
    ("ix_closures_reported_by", "closures", "reported_by"),
    ("ix_volunteer_hours_club_id", "volunteer_hours", "club_id"),
    ("ix_volunteer_hours_state", "volunteer_hours", "state"),
]


def upgrade() -> None:
    for name, table, column in _INDEXES:
        op.create_index(name, table, [column])


def downgrade() -> None:
    for name, table, _column in reversed(_INDEXES):
        op.drop_index(name, table_name=table)
