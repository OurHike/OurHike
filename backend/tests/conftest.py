"""Shared pytest fixtures.

Each test gets a clean-schema engine, plus a FastAPI TestClient wired to use
that same engine via a dependency override. Nothing here talks to a real
network - a local Postgres is not the network, and is the only thing these
fixtures connect to.

That database is Postgres everywhere: locally (via
`backend/scripts/local-postgres.sh`) and in CI (a `postgres:16` service
container, see ../.github/workflows/backend-tests.yml). The engine the suite
runs against is the engine production runs on, so a passing run means
something about Supabase's Postgres rather than about a local stand-in.

It is one shared database per *worker* rather than a fresh one per test, so
isolation comes from dropping every table the test created before the next
test starts (see `_reset_schema` below). Serially that is one database for
the whole run; under `pytest -n` it is one each, for the reason
`_worker_database_url` gives.
"""

import os

# app.config.Settings requires SUPABASE_JWT_SECRET/SUPABASE_URL/SUPABASE_ANON_KEY
# (no default - see app/config.py) so a missing real credential fails loudly
# in any real environment. Tests aren't a real environment and don't
# exercise Supabase-backed auth yet, so setdefault here supplies harmless
# placeholder values - only if the real environment hasn't already set them
# - purely so importing app.main below doesn't require live Supabase
# credentials just to run `pytest`. This must run before the `from app...`
# imports below, which is why it's at the top of this file ahead of them.
os.environ.setdefault("SUPABASE_JWT_SECRET", "test-only-placeholder-secret")
os.environ.setdefault("SUPABASE_URL", "https://test-only-placeholder.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY", "test-only-placeholder-anon-key")

# The suite gets its own database, never the dev one app/config.py defaults
# to: `_reset_schema` below drops every table it finds, and pointing that at a
# database someone was working in would be a nasty way to find that out. Same
# setdefault posture as above - CI exports DATABASE_URL for its service
# container and that always wins.
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://ourhike:ourhike@localhost:5432/ourhike_test")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import MetaData, create_engine, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402
from sqlalchemy.exc import ProgrammingError  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402


def _worker_database_url(url: str, worker: str) -> str:
    """`url` with the running xdist worker's name appended to the database.

    The isolation model in this file's docstring is "drop every table between
    tests", and that is only safe while one process is doing it. Point four
    `pytest -n` workers at one database and they drop each other's tables
    mid-test: measured here, that is not a handful of failures but a
    deadlock - workers block on locks held by tables another worker is in the
    middle of dropping, and a run that takes 60s serially took 1785s before
    it was killed.

    So parallelism is bought with a database per worker rather than by
    weakening the isolation. Each worker still runs its own tests serially
    against its own database, which is exactly the model that was there
    before - `gw0` simply cannot see `gw1`'s tables to drop them.
    """
    parsed = make_url(url)
    return parsed.set(database=f"{parsed.database}_{worker}").render_as_string(hide_password=False)


def _ensure_database(url: str) -> None:
    """Create `url`'s database if it is not there yet.

    `scripts/local-postgres.sh` creates `ourhike_test`; it cannot create the
    per-worker ones because how many there are is decided by the `-n` on the
    command line. Creating them here keeps that script's contract intact and
    means a parallel run needs no setup step of its own.

    CREATE DATABASE has no IF NOT EXISTS, and two workers racing on the same
    name is the normal case rather than an edge one, so the duplicate is
    caught instead of tested for.
    """
    parsed = make_url(url)
    admin = create_engine(parsed.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as connection:
            already_there = connection.execute(
                text("select 1 from pg_database where datname = :name"), {"name": parsed.database}
            ).scalar()
            if not already_there:
                try:
                    connection.execute(text(f'create database "{parsed.database}"'))
                except ProgrammingError:
                    # Another worker got there between the check and the
                    # create. Its database is as good as this one would be.
                    pass
    finally:
        admin.dispose()


# Before `from app.config import settings` below, because that reads
# DATABASE_URL once at import and every other reader in the codebase - the
# module-level engine in app/db/session.py, alembic/env.py, and the tests that
# call `settings.database_url` directly - goes through that one object. Setting
# the variable is therefore the whole change; nothing else has to learn about
# workers.
_XDIST_WORKER = os.environ.get("PYTEST_XDIST_WORKER")
if _XDIST_WORKER:
    os.environ["DATABASE_URL"] = _worker_database_url(os.environ["DATABASE_URL"], _XDIST_WORKER)
    _ensure_database(os.environ["DATABASE_URL"])

from app.config import settings  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402


def _reset_schema(engine) -> None:
    """Drop every table currently in the database.

    Covers both app.db.base's Base.metadata and any throwaway tables a test
    defined directly on its own declarative base (see
    tests/test_db_session.py) - reflecting the live schema rather than
    trusting a fixed metadata object catches both.
    """
    live_metadata = MetaData()
    live_metadata.reflect(bind=engine)
    live_metadata.drop_all(bind=engine)


@pytest.fixture()
def db_engine():
    """A clean-schema engine per test, against DATABASE_URL's Postgres.

    Built up and torn down around every test rather than shared, because the
    database itself is shared: one local (or CI) Postgres serves the whole
    run, so a test that left tables behind would be the next test's starting
    state. The teardown drops what the setup created, in both directions of
    that trade.

    A connection failure here is almost always "no local Postgres running" -
    `backend/scripts/local-postgres.sh` is the fix, and README.md's Setup
    section says so.
    """
    engine = create_engine(settings.database_url)
    # Ahead of create_all rather than only afterward: a previous run that died
    # mid-test (or a Ctrl-C) leaves tables behind, and create_all would then
    # quietly reuse a schema this test never built.
    _reset_schema(engine)
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        _reset_schema(engine)
        engine.dispose()


@pytest.fixture()
def db_session(db_engine):
    """A SQLAlchemy session bound to the per-test engine."""
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    session = testing_session_local()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db_engine):
    """A FastAPI TestClient with `get_db` overridden to use the test engine.

    Each request gets its own session (matching the real `get_db`'s
    per-request lifecycle), all bound to the same per-test engine.
    """
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)

    def override_get_db():
        session: Session = testing_session_local()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
