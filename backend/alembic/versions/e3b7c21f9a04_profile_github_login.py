"""Which GitHub account a person is, when they have signed in with one.

Option A of #1547's registry-approval decision: an organization's three
codeowners approve the registry pull request on GitHub with their own
accounts, so `.github/CODEOWNERS` has to name those accounts. CODEOWNERS is
generated from the roster at a moment when no admin is making a request,
which is why this is a column rather than a claim read off a token the way
`get_current_email` reads the address.

Nullable because almost nobody has one: a hiker who never administers an
organization never links an account, and an admin who has not signed in
through GitHub yet has not either. Unique because a CODEOWNERS entry stands
for one seat - see `Profile.github_login` for why the second claimant is
refused rather than given it.

Revision ID: e3b7c21f9a04
Revises: c7f2a91d4b60
Create Date: 2026-09-21
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "e3b7c21f9a04"
down_revision = "c7f2a91d4b60"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("profiles", sa.Column("github_login", sa.String(), nullable=True))
    # Unique AND indexed: the uniqueness is the guarantee a CODEOWNERS entry
    # rests on, and the index is what the roster read uses. One unique index
    # serves both rather than a constraint plus a second index.
    op.create_index("ix_profiles_github_login", "profiles", ["github_login"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_profiles_github_login", table_name="profiles")
    op.drop_column("profiles", "github_login")
