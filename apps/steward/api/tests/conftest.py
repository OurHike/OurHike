"""A real Postgres, as backend/tests/conftest.py uses, and tokens signed by a key of our own.

The database is the one STEWARD_TEST_DATABASE_URL names, default `steward_test` on
the local Postgres backend/scripts/local-postgres.sh starts. It is built once by
running the migrations, which is how the migrations are tested, and emptied
between tests. It must be named `*_test`, because emptying is what this does.

Nothing reaches the network: the token verifier is handed the test key, and the
club list is handed in rather than fetched.
"""

from __future__ import annotations

import os
import time
import uuid

import jwt
import pytest
from alembic.config import Config
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ProgrammingError

from alembic import command
from steward_api.auth import TokenVerifier
from steward_api.clubs import ClubDirectory
from steward_api.config import Settings
from steward_api.main import create_app
from steward_api.models import Base

DATABASE_URL = os.environ.get("STEWARD_TEST_DATABASE_URL", "postgresql+psycopg://ourhike:ourhike@localhost:5432/steward_test")
CLUBS = frozenset({"Example Trail Club", "Second Example Club"})
ORIGIN = "https://steward.example"

SIGNING_KEY = ec.generate_private_key(ec.SECP256R1())
OTHER_KEY = ec.generate_private_key(ec.SECP256R1())


def token(sub: str | None = None, *, key=SIGNING_KEY, **claims) -> str:
    body = {"sub": sub or str(uuid.uuid4()), "aud": "authenticated", "exp": int(time.time()) + 600, **claims}
    return jwt.encode({k: v for k, v in body.items() if v is not None}, key, algorithm="ES256", headers={"kid": "test"})


def bearer(sub: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token(sub)}"}


def _require_disposable(url: str) -> None:
    if not (make_url(url).database or "").endswith("_test"):
        raise RuntimeError(f"Refusing to empty {make_url(url).database!r}: the steward API suite only runs on a *_test database")


def _ensure_database(url: str) -> None:
    parsed = make_url(url)
    admin = create_engine(parsed.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as connection:
            if not connection.execute(text("select 1 from pg_database where datname = :n"), {"n": parsed.database}).scalar():
                try:
                    connection.execute(text(f'create database "{parsed.database}"'))
                except ProgrammingError:
                    pass
    finally:
        admin.dispose()


@pytest.fixture(scope="session")
def database_url() -> str:
    _require_disposable(DATABASE_URL)
    _ensure_database(DATABASE_URL)
    engine = create_engine(DATABASE_URL)
    with engine.begin() as connection:
        connection.execute(text("drop schema public cascade"))
        connection.execute(text("create schema public"))
    engine.dispose()
    config = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    config.set_main_option("script_location", os.path.join(os.path.dirname(__file__), "..", "alembic"))
    config.attributes["database_url"] = DATABASE_URL
    command.upgrade(config, "head")
    return DATABASE_URL


@pytest.fixture
def settings(database_url) -> Settings:
    return Settings(database_url=database_url, supabase_url="https://project.example", allowed_origins=[ORIGIN])


@pytest.fixture
def app(settings):
    public = SIGNING_KEY.public_key()
    application = create_app(
        settings,
        verifier=TokenVerifier(settings, signing_key=lambda _token: public),
        clubs=ClubDirectory(lambda: CLUBS),
    )
    yield application
    with application.state.engine.begin() as connection:
        tables = ", ".join(table.name for table in Base.metadata.sorted_tables)
        connection.execute(text(f"truncate {tables} restart identity cascade"))
    application.state.engine.dispose()


@pytest.fixture
def client(app) -> TestClient:
    return TestClient(app)
