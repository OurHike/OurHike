"""Shared pytest fixtures.

Each test gets a clean-schema engine, plus a FastAPI TestClient wired to use
that same engine via a dependency override. Nothing here talks to a real
network. Which database engine that is follows DATABASE_URL (app.config.settings)
exactly like the real app does, not something hardcoded here:

- **Local default: DuckDB**, a fresh temp-file database per test (see the
  docstring below for why a temp file, not `:memory:`).
- **CI's Postgres job: real Postgres**, via `DATABASE_URL` pointed at the
  `postgres:16` service container (see ../.github/workflows/backend-tests.yml).
  That's a single shared database across the whole test run, so isolation
  instead comes from dropping every table the test created before the next
  test starts (see `_reset_postgres_schema` below).

This split matters: it's what makes "DuckDB locally, real Postgres in CI"
(see backend/README.md) an actual correctness gate rather than CI quietly
re-testing DuckDB under a different job name.
"""

import os
import uuid
from pathlib import Path

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

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import MetaData, create_engine  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402

from app.config import settings  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402


def _reset_postgres_schema(engine) -> None:
    """Drop every table currently in the database.

    Covers both app.db.base's Base.metadata (currently empty) and any
    throwaway tables a test defined directly on its own declarative base
    (see tests/test_db_session.py) - reflecting the live schema rather than
    trusting a fixed metadata object catches both.
    """
    live_metadata = MetaData()
    live_metadata.reflect(bind=engine)
    live_metadata.drop_all(bind=engine)


@pytest.fixture()
def db_engine(tmp_path: Path):
    """A fresh, clean-schema engine per test, per DATABASE_URL.

    DuckDB's SQLAlchemy dialect (duckdb-engine) supports a `:memory:` file
    too, but each new connection to `duckdb:///:memory:` gets its *own*
    separate in-memory database - there's no way to share one in-memory
    database across the multiple connections a connection-pooled engine (and
    FastAPI's request-scoped `get_db`) will open. A per-test temp file
    sidesteps that entirely and is still fast/isolated: unique per test via
    `tmp_path`, deleted with the rest of the test's temp directory afterward.
    """
    if settings.database_url.startswith("duckdb"):
        db_path = tmp_path / f"test_{uuid.uuid4().hex}.duckdb"
        engine = create_engine(f"duckdb:///{db_path}")
        Base.metadata.create_all(engine)
        try:
            yield engine
        finally:
            engine.dispose()
    else:
        engine = create_engine(settings.database_url)
        Base.metadata.create_all(engine)
        try:
            yield engine
        finally:
            _reset_postgres_schema(engine)
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
