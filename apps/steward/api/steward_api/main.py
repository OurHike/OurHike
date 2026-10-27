"""The app factory. `uvicorn steward_api.main:app` serves it with the environment's settings."""

from __future__ import annotations

import re
import threading
import time
from collections.abc import Callable

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from steward_api import limits
from steward_api.analysis import AnalysisDirectory
from steward_api.auth import TokenVerifier
from steward_api.body_limit import BodyLimitMiddleware
from steward_api.config import Settings
from steward_api.db import make_engine, make_sessionmaker, schema_head
from steward_api.photos import PhotoStore
from steward_api.routes import claims, lists, me, weights


def create_app(
    settings: Settings | None = None,
    *,
    verifier: TokenVerifier | None = None,
    analysis: AnalysisDirectory | None = None,
    photos: PhotoStore | None = None,
) -> FastAPI:
    settings = settings or Settings()
    # No /docs or /openapi.json in a deployment: nothing here is for browsing,
    # and the web app is the only client.
    app = FastAPI(title="Campsite Steward API", docs_url=None, redoc_url=None, openapi_url=None)
    engine = make_engine(settings.database_url)
    app.state.engine = engine
    app.state.sessionmaker = make_sessionmaker(engine)
    app.state.verifier = verifier or TokenVerifier(settings)
    app.state.analysis = analysis or AnalysisDirectory.from_url(settings.sites_url)
    #: None when this deployment has no photo bucket: uploads then answer 503.
    app.state.photos = photos if photos is not None else settings.photo_storage()

    # Its own pool of one connection, so health checks never queue for a
    # connection a real request needs (the re-check's N6).
    health_engine = make_engine(settings.database_url, pool_size=1, max_overflow=0, pool_timeout=2, pool_recycle=300)
    expected_schema = schema_head()

    def check_database() -> tuple[int, str]:
        """Up means the database answers and its schema is the one this code
        expects. A deployment that fell back to the localhost default reported
        healthy while every request failed (the review's finding 13); so did one
        whose migrations had not run, while every signed-in request was a 500
        reading a column that was not there yet (the re-check's N3)."""
        try:
            with health_engine.connect() as connection:
                version = connection.execute(text("select version_num from alembic_version")).scalar()
        except SQLAlchemyError:
            return 503, "database unreachable"
        if version != expected_schema:
            return 503, f"database schema is at {version}, this code needs {expected_schema}: run the migrations"
        return 200, "ok"

    health_check = CachedCheck(check_database, seconds=limits.HEALTH_CHECK_SECONDS)

    @app.get("/health")
    def health() -> JSONResponse:
        code, words = health_check()
        return JSONResponse({"status": words}, status_code=code)

    app.include_router(me.router)
    app.include_router(lists.router)
    app.include_router(weights.router)
    app.include_router(claims.router)

    # Order: Starlette runs the last-added middleware first. The body limit goes
    # inside CORS, so a refused body still carries the CORS headers a browser
    # needs to read the 413.
    app.add_middleware(
        BodyLimitMiddleware,
        max_bytes=limits.MAX_BODY_BYTES,
        larger=((re.compile(r"/claims/[0-9a-fA-F-]{36}/photos"), limits.PHOTO_MAX_BYTES),),
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
        # Bearer tokens, not cookies: nothing here needs the browser to send credentials.
        allow_credentials=False,
        max_age=600,
    )
    return app


class CachedCheck:
    """One check at a time, and its answer reused for `seconds`.

    /health is the one route that needs no sign-in and touches the database.
    Checked on every probe, an unauthenticated flood of them answered 105 of
    600 with 503 (the adversarial review's third pass, 2026-10-27): a probe
    that waited past the health pool's timeout for the one connection was
    counted as the database being down, which is what makes a host pull or
    restart an instance. Now a probe that arrives while a check is running
    gets the last answer at once rather than waiting, so a 503 here means the
    database itself did not answer.
    """

    def __init__(self, check: Callable[[], tuple[int, str]], *, seconds: float, clock: Callable[[], float] = time.monotonic):
        self._check = check
        self._seconds = seconds
        self._clock = clock
        self._lock = threading.Lock()
        self._answer: tuple[int, str] | None = None
        self._at = 0.0

    def __call__(self) -> tuple[int, str]:
        answer = self._answer
        if answer is not None and self._clock() - self._at < self._seconds:
            return answer
        if answer is None:
            # The very first probes, with no answer yet to give, wait for the first check.
            self._lock.acquire()
        elif not self._lock.acquire(blocking=False):
            # Someone else is checking: the last answer, not a place in a queue.
            return answer
        try:
            if self._answer is not None and self._clock() - self._at < self._seconds:
                return self._answer
            self._answer = self._check()
            self._at = self._clock()
            return self._answer
        finally:
            self._lock.release()


def __getattr__(name: str) -> FastAPI:
    # `steward_api.main:app` for uvicorn, built on first access rather than at
    # import, so importing this module (tests do) needs no environment.
    if name == "app":
        return create_app()
    raise AttributeError(name)
