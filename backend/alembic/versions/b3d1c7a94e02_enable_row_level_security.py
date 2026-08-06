"""enable row level security

Revision ID: b3d1c7a94e02
Revises: 0f79a37f9358
Create Date: 2026-08-06 11:40:00.000000

Locks every table this schema creates against Supabase's PostgREST front
door, in the same transaction that creates them.

LAUNCH_CHECKLIST.md 5a describes this as a manual step run "in the same
sitting" as the migration, because "between the migration landing and RLS
being on, the database is open." That is correct, and it depends on a
person remembering, once, at a moment that happens under deploy pressure.
Doing it here instead means the open window does not exist - not that it
is short - and there is no separate step left to forget.

**Why it is needed at all.** Supabase serves every table in `public` over
PostgREST at `https://<ref>.supabase.co/rest/v1/` to anyone holding the
anon key, and that key ships inside the client's JS bundle by design.
The backend's own auth does not cover this: `get_current_user` guards
FastAPI's routes, and PostgREST is a second front door into the same
database that never passes through FastAPI. Without RLS, `reports`,
`profiles` and `closures` are readable and writable by anyone who opens
the app, views source, copies the key and calls REST directly.

**No policies, deliberately.** A table with RLS on and no policy refuses
every anon request, which is the correct default here: nothing in the
client talks to PostgREST. Supabase is used for authentication only and
all data reaches the app through the backend, so there is no query to
keep working and nothing to grant. Add policies if and only if something
is later built that genuinely needs direct table access.

**The backend is unaffected**, and that is not luck. RLS does not apply
to a table's owner, and the backend connects with the Postgres
connection string as the owner. This is also why `FORCE ROW LEVEL
SECURITY` must never be added here: it applies RLS to the owner too, and
would break every endpoint at once. tests/test_migration_rls.py asserts
the word does not appear.

**Postgres only, and the guard stays even though every database this
backend now runs against is Postgres.** These are raw
`ALTER TABLE ... ROW LEVEL SECURITY` strings handed to `op.execute`, so
they reach whatever dialect Alembic is pointed at, verbatim and
unchecked. When this was written, that included an embedded local
database with no such syntax; that path is gone (local dev is a real
Postgres now - see backend/scripts/local-postgres.sh), which makes the
guard cheap insurance rather than a live requirement. Deleting it would
trade nothing for a revision that hard-fails on anything unexpected.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b3d1c7a94e02"
down_revision: Union[str, Sequence[str], None] = "0f79a37f9358"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# The tables this revision locks. Written out rather than read from
# Base.metadata on purpose: a migration is a statement about the schema at
# one point in time, and one that consulted the live models would silently
# change meaning every time a model was added.
#
# That does mean a table added by a LATER migration is not covered here.
# tests/test_migration_rls.py is what catches it - it compares the union of
# every migration's RLS_TABLES against Base.metadata and fails on anything
# left out, so a new model cannot land without a revision that locks it.
RLS_TABLES: tuple[str, ...] = (
    "clubs",
    "profiles",
    "closures",
    "hikes",
    "maintainer_assignments",
    "reports",
    "user_preferences",
)


def rls_statements(dialect_name: str, *, enable: bool) -> list[str]:
    """The DDL this revision runs, for a given dialect.

    A pure function rather than a loop inlined into `upgrade()` so the two
    things worth checking - that Postgres gets all seven, and that
    everything else gets none - are testable without a database of either
    kind. Migrations are otherwise the part of this backend nothing
    exercises: the test suite builds its schema with `Base.metadata
    .create_all`, so no test has ever run one.
    """
    if dialect_name != "postgresql":
        return []

    verb = "ENABLE" if enable else "DISABLE"
    # Schema-qualified to match LAUNCH_CHECKLIST.md 5a exactly, and because
    # `public` is precisely the schema PostgREST exposes - the reason any of
    # this is necessary. A future move out of `public` (5a's other option)
    # would need this revision revisited, not merely inherited.
    return [f"ALTER TABLE public.{table} {verb} ROW LEVEL SECURITY" for table in RLS_TABLES]


def upgrade() -> None:
    """Lock the tables."""
    # get_context(), not get_bind(): the latter raises in Alembic's offline
    # mode, where there is no connection, and `alembic upgrade --sql` is a
    # reasonable way to review this particular change before running it.
    for statement in rls_statements(op.get_context().dialect.name, enable=True):
        op.execute(statement)


def downgrade() -> None:
    """Unlock them again.

    Reversible because a migration that cannot be undone is a migration
    nobody dares run, but worth being clear-eyed about: downgrading this
    revision reopens every table to anyone holding the anon key.
    """
    for statement in rls_statements(op.get_context().dialect.name, enable=False):
        op.execute(statement)
