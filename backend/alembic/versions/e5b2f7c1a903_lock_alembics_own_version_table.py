"""lock alembic's own version table

Revision ID: e5b2f7c1a903
Revises: d4a91c3e7b25
Create Date: 2026-08-08 03:50:00.000000

`b3d1c7a94e02` locked every table this schema creates. It did not lock the
one Alembic creates, because nothing here creates it and nothing here knew
it was there. Supabase's advisors found it within minutes of the first real
migration landing on UA:

    public.alembic_version has Row Level Security disabled - fully exposed
    to the anon and authenticated roles.

**The exclusion was deliberate and was answering a different question.**
`tests/test_migrations.py` drops `alembic_version` from its RLS assertions
as "Alembic's own bookkeeping, not part of the schema under test", which is
right about ownership and wrong about exposure: PostgREST serves every table
in `public` to anyone holding the anon key, and it does not care which tool
created them. `supabase_keepalive.py`'s live check sweeps the seven model
tables for the same reason and would not have caught this either.

**Writing to it is worse than reading it,** which is the opposite of the
other seven. The table holds one row: the revision this database is at.

- Change it, and the next `upgrade head` re-runs migrations already applied
  or skips ones that never were.
- Delete it, and the database reads as `EMPTY` - `check_schema_drift.py`
  says so, and an upgrade then tries to create tables that already exist.

Neither leaks a hiker's data. Both put the schema somewhere no revision
describes, which is the state this whole mechanism exists to prevent.

**It also closes a hole in LAUNCH_CHECKLIST.md 5a's argument**, which is that
shipping the anon key inside the client bundle is safe *because* RLS is on.
That was true of seven tables out of eight.

**No policies, and the backend is unaffected**, for exactly the reasons
`b3d1c7a94e02` gives: nothing in the client talks to PostgREST, and RLS does
not apply to a table's owner - which is what Alembic connects as. Its
`FORCE ROW LEVEL SECURITY` warning applies here with more force than
anywhere else: forcing it would lock Alembic out of its own bookkeeping and
break every future migration at once.

**The table is named by the migration context, not hardcoded.** Alembic's
`version_table` and `version_table_schema` are configurable, and a revision
that hardcoded `public.alembic_version` would keep passing while quietly
locking nothing if either were ever set.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5b2f7c1a903"
down_revision: Union[str, Sequence[str], None] = "d4a91c3e7b25"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Deliberately NOT named RLS_TABLES. tests/test_migration_rls.py unions that
# name across every revision to prove each *model* table is locked, and this
# is not a model table - it belongs to Alembic. Sharing the name would make
# the union quietly larger than the thing it is compared against.
BOOKKEEPING_TABLE_FALLBACK = "alembic_version"


def rls_statement(dialect_name: str, table: str, schema: str | None, *, enable: bool) -> list[str]:
    """The DDL this revision runs, for a given dialect and version table.

    Pure, and taking the table name as an argument rather than reading it
    off a live context, so both things worth checking are testable without a
    database: that Postgres gets exactly one statement naming whatever
    version table it was given, and that every other dialect gets none.

    The non-Postgres guard is inherited from `b3d1c7a94e02` and kept for its
    reason: these are raw strings handed to `op.execute`, so they reach
    whatever dialect Alembic is pointed at, verbatim and unchecked.
    """
    if dialect_name != "postgresql":
        return []

    verb = "ENABLE" if enable else "DISABLE"
    qualified = f"{schema}.{table}" if schema else table
    return [f"ALTER TABLE {qualified} {verb} ROW LEVEL SECURITY"]


def _version_table(context) -> tuple[str, str | None]:
    """What Alembic is actually calling its version table here.

    Defaults rather than assumptions: `version_table` is unset in this
    repository's alembic.ini, so it is `alembic_version`, and
    `version_table_schema` is unset, so it is the connection's schema -
    `public` on Supabase, which is the one PostgREST exposes. Reading them
    means setting either later moves this lock with them.
    """
    table = getattr(context, "version_table", None) or BOOKKEEPING_TABLE_FALLBACK
    schema = getattr(context, "version_table_schema", None) or "public"
    return table, schema


def upgrade() -> None:
    """Lock it."""
    # get_context(), not get_bind(): the latter raises in Alembic's offline
    # mode, and `alembic upgrade --sql` is a reasonable way to review a
    # change to the table Alembic uses to know where it is.
    context = op.get_context()
    table, schema = _version_table(context)
    for statement in rls_statement(context.dialect.name, table, schema, enable=True):
        op.execute(statement)


def downgrade() -> None:
    """Unlock it again.

    Reversible, and worth being clear-eyed about in the same way
    `b3d1c7a94e02` is: downgrading this reopens the revision pointer to
    anyone holding the anon key.
    """
    context = op.get_context()
    table, schema = _version_table(context)
    for statement in rls_statement(context.dialect.name, table, schema, enable=False):
        op.execute(statement)
