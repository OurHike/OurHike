"""Mark an admin invitation as one, and give each nominated contact their own link.

#1635 - The organization console's new endpoints trust self-registered orgs
with maintainer powers, seats and mail. Two of its five defects needed a
column, and both columns are here:

`role_invites.grants_admin_seat`. Until this revision an invite with no
`role_id` WAS an admin invitation (`core/role_invites.py`'s `_seat_from`),
and two writers a supervisor can reach - `invite_volunteer` with its optional
role, and `sync_roster` when a role name matches nothing - write exactly that
shape. So an invitation meant as "a volunteer whose role we have not decided"
arrived as a seat at the organization. Now a seat needs the flag, and only
`routers/clubs.py`'s admin paths set it.

Existing rows backfill to FALSE, which means a role-less invite written
before this revision and not yet claimed no longer grants a seat. That is
the fail-closed direction and it costs nothing today: no production backend
has run (#600), so the only rows it can touch are UA's, and an admin
re-sends the invitation from the console.

`nomination_contacts.decision_token`. One link went to every contact, so
whoever held one could cast all three approvals. Each contact now gets their
own, and a decision is recorded against the contact whose link was used.
Nullable because rows written before this revision have none; those contacts
can still read the proposal through the shared token and can no longer
decide through it.

Revision ID: a7c2e9f41d06
Revises: f4a9d38e5c71
Create Date: 2026-09-23
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "a7c2e9f41d06"
down_revision = "f4a9d38e5c71"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # server_default rather than a Python default alone: NOT NULL, and the
    # previous release keeps inserting invites that know nothing about the
    # column during the rollout (RELEASING.md §8c).
    op.add_column(
        "role_invites",
        sa.Column("grants_admin_seat", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("nomination_contacts", sa.Column("decision_token", sa.String(), nullable=True))
    op.create_index(
        "ix_nomination_contacts_decision_token",
        "nomination_contacts",
        ["decision_token"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_nomination_contacts_decision_token", table_name="nomination_contacts")
    op.drop_column("nomination_contacts", "decision_token")
    op.drop_column("role_invites", "grants_admin_seat")
