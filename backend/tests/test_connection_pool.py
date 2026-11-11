"""The connection pool's sizes are settings, and a full pool answers 503.

#1764 - The connection pool is the default five plus ten overflow under a
forty-thread request pool, and no figure exists for what a cold-start outbox
burst needs. Three things are held here:

  - `DATABASE_POOL_SIZE`, `DATABASE_MAX_OVERFLOW` and
    `DATABASE_POOL_TIMEOUT_SECONDS` reach the engine the app actually runs on,
    and the three values SQLAlchemy reads as "unbounded" or "never" are
    refused at startup.
  - A request that waits out the checkout timeout is answered 503 with a
    one-sentence detail, not a 500 - so the phone's outbox retries it.
  - Nothing here measures what size the pool should be. That figure still
    does not exist; app/config.py says what would produce it.
"""

import time

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import Settings, settings
from app.db.session import engine, engine_options, get_db
from app.main import app

DIRECT_URL = "postgresql+psycopg://ourhike:ourhike@localhost:5432/ourhike_dev"


# --- The settings reach the engine -------------------------------------------


def test_engine_options_pass_each_pool_size_it_is_given():
    options = engine_options(DIRECT_URL, prepared_statements=False, pool_size=7, max_overflow=3, pool_timeout=2.5)

    assert (options["pool_size"], options["max_overflow"], options["pool_timeout"]) == (7, 3, 2.5)


def test_engine_options_leave_out_a_pool_size_nobody_gave():
    """tests/test_pooler.py builds its own `pool_size=1` engine from these
    options, so a key it did not ask for would be a duplicate keyword."""
    options = engine_options(DIRECT_URL, prepared_statements=False)

    assert not {"pool_size", "max_overflow", "pool_timeout"} & options.keys()


def test_the_apps_engine_is_built_with_the_pool_settings():
    assert engine.pool.size() == settings.database_pool_size
    assert engine.pool._max_overflow == settings.database_max_overflow
    assert engine.pool._timeout == settings.database_pool_timeout_seconds


@pytest.fixture()
def _no_dot_env(monkeypatch, tmp_path):
    """Settings() reads `.env` from the working directory; a developer's own must not decide these."""
    monkeypatch.chdir(tmp_path)
    for name in ("DATABASE_POOL_SIZE", "DATABASE_MAX_OVERFLOW", "DATABASE_POOL_TIMEOUT_SECONDS"):
        monkeypatch.delenv(name, raising=False)


def test_pool_defaults_are_sqlalchemys_sizes_and_a_five_second_wait(_no_dot_env):
    """Size and overflow unchanged from what every deployment has run on; the
    wait cut from SQLAlchemy's 30 s (app/config.py says why, and that 5 is
    unvalidated)."""
    built = Settings()

    assert (built.database_pool_size, built.database_max_overflow, built.database_pool_timeout_seconds) == (5, 10, 5.0)


def test_pool_settings_are_read_from_the_environment(_no_dot_env, monkeypatch):
    monkeypatch.setenv("DATABASE_POOL_SIZE", "12")
    monkeypatch.setenv("DATABASE_MAX_OVERFLOW", "0")
    monkeypatch.setenv("DATABASE_POOL_TIMEOUT_SECONDS", "1.5")

    built = Settings()

    assert (built.database_pool_size, built.database_max_overflow, built.database_pool_timeout_seconds) == (12, 0, 1.5)


@pytest.mark.parametrize(
    ("name", "value"),
    [
        # SQLAlchemy reads a pool_size of 0 as "no limit".
        ("DATABASE_POOL_SIZE", "0"),
        # And a max_overflow of -1 as "unlimited overflow".
        ("DATABASE_MAX_OVERFLOW", "-1"),
        ("DATABASE_POOL_TIMEOUT_SECONDS", "0"),
        ("DATABASE_POOL_TIMEOUT_SECONDS", "-2"),
    ],
)
def test_a_pool_setting_that_would_unbound_the_pool_or_never_wait_is_refused(_no_dot_env, monkeypatch, name, value):
    monkeypatch.setenv(name, value)

    with pytest.raises(ValidationError, match=name):
        Settings()


# --- A full pool answers 503 --------------------------------------------------
#
# A pool of one connection with no overflow, that one connection held by the
# test, and a checkout timeout short enough that the request gives up in a
# fraction of a second. Not timing-dependent: the connection is held for the
# whole request, so the checkout cannot succeed however slow the machine is.

_CHECKOUT_TIMEOUT_SECONDS = 0.2


def test_a_request_that_cannot_get_a_connection_is_answered_503(db_engine, client, monkeypatch):
    one_connection = create_engine(settings.database_url, pool_size=1, max_overflow=0, pool_timeout=_CHECKOUT_TIMEOUT_SECONDS)
    sessions = sessionmaker(autocommit=False, autoflush=False, bind=one_connection)

    def one_connection_db():
        session = sessions()
        try:
            yield session
        finally:
            session.close()

    monkeypatch.setitem(app.dependency_overrides, get_db, one_connection_db)

    held = one_connection.connect()
    try:
        started = time.monotonic()
        response = client.get("/closures")
        waited = time.monotonic() - started
    finally:
        held.close()
        one_connection.dispose()

    assert response.status_code == 503
    assert response.json() == {"detail": "The server is busy. Try again shortly."}
    # It waited for the checkout timeout rather than failing some other way first.
    assert waited >= _CHECKOUT_TIMEOUT_SECONDS


def test_the_same_request_succeeds_once_the_connection_is_free(db_engine, client, monkeypatch):
    """The 503 above is the pool being full, not the route being broken."""
    one_connection = create_engine(settings.database_url, pool_size=1, max_overflow=0, pool_timeout=_CHECKOUT_TIMEOUT_SECONDS)
    sessions = sessionmaker(autocommit=False, autoflush=False, bind=one_connection)

    def one_connection_db():
        session = sessions()
        try:
            yield session
        finally:
            session.close()

    monkeypatch.setitem(app.dependency_overrides, get_db, one_connection_db)

    try:
        response = client.get("/closures")
    finally:
        one_connection.dispose()

    assert response.status_code == 200
