"""The migrations actually run, against the database they target.

tests/test_migration_rls.py opens by noting that "migrations are the one
part of this backend nothing else exercises" - the suite builds its schema
with `Base.metadata.create_all`, so no test had ever run one. That was true
while local dev ran on an embedded database that could not execute this
revision's `ALTER TABLE ... ENABLE ROW LEVEL SECURITY` at all. It is not
true any more: the test database is Postgres now (see conftest.py), so the
migration chain can simply be run.

What that buys, beyond the pure-function checks in test_migration_rls.py:
`rls_statements` returning the right strings is not the same claim as
Postgres accepting them, and `upgrade()` emitting DDL is not the same claim
as the DDL leaving row-level security switched on. This asserts the state of
the real database afterward, read back out of `pg_class`.

These tests deliberately do not use the `db_engine` fixture - the whole
point is to build the schema the way a deploy does, not the way the rest of
the suite does.
"""

from pathlib import Path

import pytest
import sqlalchemy
from alembic.config import Config

from alembic import command
from app.config import settings
from app.db.base import Base
from tests.conftest import _reset_schema

BACKEND_DIR = Path(__file__).resolve().parents[1]

RLS_QUERY = sqlalchemy.text(
    "select relname, relrowsecurity, relforcerowsecurity "
    "from pg_class "
    "where relnamespace = 'public'::regnamespace and relkind = 'r'"
)


def _alembic_config() -> Config:
    """Alembic's own config, resolved absolutely.

    `alembic/env.py` already overrides `sqlalchemy.url` from
    `app.config.settings` - the same single source of truth the app uses -
    so nothing here has to say which database to run against, and nothing
    here can disagree with the app about it.

    The paths are made absolute because the ini's `script_location` is
    relative to the working directory Alembic is normally invoked from
    (backend/), and pytest can be invoked from anywhere.
    """
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    return config


VERSION_TABLE = "alembic_version"


def _public_tables(engine) -> dict[str, tuple[bool, bool]]:
    """Every ordinary table in `public`, with its RLS flags.

    `alembic_version` is dropped here because it is Alembic's, not this
    schema's - the tests below are about the tables the revisions create,
    and the version table's own lifecycle is Alembic's business.

    That exclusion used to mean nothing checked its RLS at all, which is a
    different claim and was wrong: PostgREST serves every table in `public`
    to anyone holding the anon key, and does not care which tool created
    them. Supabase's advisors found it on UA within minutes of the first
    real migration. `test_the_version_table_is_locked_too` is the assertion
    that gap needed, and revision e5b2f7c1a903 is the fix.
    """
    with engine.connect() as connection:
        rows = connection.execute(RLS_QUERY).all()
    return {name: (rls, force) for name, rls, force in rows if name != VERSION_TABLE}


def _version_table_flags(engine) -> tuple[bool, bool] | None:
    with engine.connect() as connection:
        rows = connection.execute(RLS_QUERY).all()
    for name, rls, force in rows:
        if name == VERSION_TABLE:
            return rls, force
    return None


@pytest.fixture()
def migration_engine():
    """A connection to the test database, with the schema torn down around it.

    Both directions matter. Before: the rest of the suite leaves the database
    empty, but a run interrupted mid-test does not, and `upgrade head` onto a
    half-built schema fails in a way that has nothing to do with the
    migration. After: whatever revision the test left applied is undone, so
    the next test starts from the empty database every other fixture assumes.

    `_reset_schema` reflects the live schema rather than working from
    `Base.metadata`, which is what makes it drop Alembic's own
    `alembic_version` table too - the one table these tests create that the
    models know nothing about.
    """
    engine = sqlalchemy.create_engine(settings.database_url)
    _reset_schema(engine)
    try:
        yield engine
    finally:
        _reset_schema(engine)
        engine.dispose()


def test_upgrade_head_builds_the_schema_with_rls_on(migration_engine):
    command.upgrade(_alembic_config(), "head")

    tables = _public_tables(migration_engine)

    assert set(tables) == set(Base.metadata.tables), (
        "The migrations and the models disagree about which tables exist. "
        "`alembic revision --autogenerate` is the fix, not editing this test."
    )
    for table, (rls_enabled, rls_forced) in sorted(tables.items()):
        # Enabled, and specifically NOT forced: forcing applies RLS to the
        # table owner, which is the role the backend connects as, and would
        # break every endpoint at once while looking like a tightening.
        # test_migration_rls.py asserts the word never appears in the DDL;
        # this asserts the database ended up in that state.
        assert rls_enabled, f"{table} was created without row level security"
        assert not rls_forced, f"{table} has FORCE row level security"


def test_the_version_table_is_locked_too(migration_engine):
    """The eighth table, and the one nothing was asserting about.

    `alembic_version` is created by Alembic rather than by any revision
    here, which is why it sat outside `_public_tables` and outside
    `supabase_keepalive.py`'s sweep of the seven. PostgREST exposes it
    regardless. Reading it leaks only which revision is deployed; writing it
    is the real hazard - change the row and the next `upgrade head` re-runs
    or skips migrations, delete it and the database reads as EMPTY and an
    upgrade tries to create tables that already exist.

    Not forced, for a reason sharper here than anywhere else: forcing
    applies RLS to the owner, which is what Alembic connects as, and would
    lock it out of its own bookkeeping - breaking every future migration.
    """
    command.upgrade(_alembic_config(), "head")

    flags = _version_table_flags(migration_engine)

    assert flags is not None, f"{VERSION_TABLE} does not exist after upgrade head - has Alembic renamed it?"
    rls_enabled, rls_forced = flags
    assert rls_enabled, (
        f"{VERSION_TABLE} was left without row level security, so anyone holding the anon key can read and rewrite "
        f"the revision pointer over PostgREST. Revision e5b2f7c1a903 is what locks it."
    )
    assert not rls_forced, f"{VERSION_TABLE} has FORCE row level security, which locks Alembic out of its own table"


def test_migrations_still_run_against_the_locked_version_table(migration_engine):
    """The risk the lock introduces, exercised rather than reasoned about.

    RLS on the table Alembic uses to know where it is would be a poor place
    to be wrong: every future migration fails at once. It is safe because
    RLS does not apply to a table's owner and Alembic connects as the owner
    - but that is an argument, and this is a second `upgrade head` against a
    database whose version table is already locked, which is the thing the
    argument claims works.
    """
    command.upgrade(_alembic_config(), "head")
    assert _version_table_flags(migration_engine)[0], "precondition: the lock is on"

    command.upgrade(_alembic_config(), "head")  # a no-op that still reads and writes alembic_version

    command.downgrade(_alembic_config(), "base")
    assert _public_tables(migration_engine) == {}


def test_downgrade_base_removes_everything_it_created(migration_engine):
    command.upgrade(_alembic_config(), "head")
    assert _public_tables(migration_engine)  # precondition, not the assertion

    command.downgrade(_alembic_config(), "base")

    assert _public_tables(migration_engine) == {}


def test_the_models_match_the_migrations(migration_engine):
    """No pending autogenerate diff - `alembic check`, as a test.

    A model changed without a matching revision is the failure this catches,
    and it is one that otherwise surfaces at deploy time as a column the
    application queries and the database does not have.
    """
    command.upgrade(_alembic_config(), "head")

    # `alembic check` exits non-zero by raising AutogenerateDiffsDetected,
    # whose message lists the diffs - which is exactly the failure message
    # this test wants, so it is left to propagate rather than caught and
    # re-raised as something less informative.
    command.check(_alembic_config())
