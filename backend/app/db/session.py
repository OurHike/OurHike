"""Engine, sessionmaker, and the `get_db` FastAPI dependency.

Reads DATABASE_URL from app.config.settings - a local Postgres by default,
CI's Postgres service container under CI, Supabase's Postgres in production.
Same engine in all three. See backend/README.md.

The engine options below are the part that only matters in production, which
is exactly why they are worked out here rather than discovered there - see
`engine_options` for what a connection pool sitting between this process and
Postgres does to the assumptions a direct connection lets you make.
"""

from collections.abc import Generator
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings


def engine_options(database_url: str, *, prepared_statements: bool) -> dict[str, Any]:
    """The keyword arguments `create_engine` gets, and why each one is there.

    A pure function of the URL so the reasoning is testable without opening a
    connection - see tests/test_engine_options.py.

    **`pool_pre_ping`** costs a round trip on checkout and buys the difference
    between a 500 and a retry. Anything between this process and Postgres -
    Supabase's pooler, a load balancer, an idle timeout on either side - can
    drop a connection that SQLAlchemy still believes is good, and the first
    request to borrow it is the one that fails.

    **`prepare_threshold: None`** turns off psycopg's automatic prepared
    statements, and is the setting this whole function exists for. psycopg
    prepares a query server-side after it has run 5 times on a connection,
    then refers to it by name. Through Supabase's *transaction*-mode pooler
    (port 6543, the connection string its dashboard offers first), each
    transaction can land on a different Postgres backend, so the name refers
    to something that backend has never heard of - or worse, to a name it
    already has under a different plan.

    Reproduced locally against pgbouncer in transaction mode rather than
    reasoned about: with the default threshold the 6th execution fails with
    `psycopg.errors.DuplicatePreparedStatement: prepared statement "_pg3_0"
    already exists`; with it off, the same loop runs clean. It surfaces only
    under a pooler, only after a query gets warm, and it takes the endpoint
    down rather than slowing it - which is why the default here is the safe
    one and `DATABASE_PREPARED_STATEMENTS=true` is the opt-in for a
    deployment on a direct connection that wants the plan caching back.

    The psycopg-only argument is passed only when psycopg is actually the
    driver: `connect_args` goes straight to the DBAPI, so handing it to any
    other driver would be a TypeError at connect time rather than a helpful
    message.
    """
    options: dict[str, Any] = {"pool_pre_ping": True}

    if not prepared_statements and make_url(database_url).get_driver_name() == "psycopg":
        options["connect_args"] = {"prepare_threshold": None}

    return options


engine = create_engine(
    settings.database_url,
    **engine_options(settings.database_url, prepared_statements=settings.database_prepared_statements),
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Yield a request-scoped SQLAlchemy session, closing it afterward."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
