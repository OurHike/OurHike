"""Where an organization's registry pull request is, once three have signed.

The connection that was missing: three codeowners agreeing produced three
rows in `registry_signoffs` and stopped, which is why the console screens
described a pull request nothing opened. `routers/org_registry.py` now opens
one on the third signature and records it here, so the console can link an
organization to the thing its own people are being asked to approve.

Null for an organization that has not signed off, and for every organization
on a deployment where `registry_pr_enabled` is off - which is all of them
until a service identity's token is issued.

Two columns rather than the number alone: the console shows the link and
should not have to know how to build a GitHub URL, and the host differs
between a fork and this repository.

Revision ID: f4a9d38e5c71
Revises: e3b7c21f9a04
Create Date: 2026-09-21
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "f4a9d38e5c71"
down_revision = "e3b7c21f9a04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("clubs", sa.Column("registry_pr_number", sa.Integer(), nullable=True))
    op.add_column("clubs", sa.Column("registry_pr_url", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("clubs", "registry_pr_url")
    op.drop_column("clubs", "registry_pr_number")
