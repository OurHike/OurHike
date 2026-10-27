"""The engine and the request-scoped session.

`prepare_threshold: None` for the reason backend/app/db/session.py gives at
length: through Supabase's transaction-mode pooler, psycopg's automatic
prepared statements fail on the sixth execution of a warm query.
"""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import Request
from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker


def make_engine(database_url: str, **extra: object) -> Engine:
    options: dict = {"pool_pre_ping": True, **extra}
    if make_url(database_url).get_driver_name() == "psycopg":
        options["connect_args"] = {"prepare_threshold": None}
    return create_engine(database_url, **options)


def make_sessionmaker(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db(request: Request) -> Iterator[Session]:
    session = request.app.state.sessionmaker()
    try:
        yield session
    finally:
        session.close()
