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


def _public_tables(engine) -> dict[str, tuple[bool, bool]]:
    """Every ordinary table in `public`, with its RLS flags.

    `alembic_version` is Alembic's own bookkeeping table, not part of the
    schema under test, so it is dropped from the result rather than being
    asserted about.
    """
    with engine.connect() as connection:
        rows = connection.execute(RLS_QUERY).all()
    return {name: (rls, force) for name, rls, force in rows if name != "alembic_version"}


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
