"""The app factory. `uvicorn steward_api.main:app` serves it with the environment's settings."""

from __future__ import annotations

import re

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

    # Its own pool of one connection with short timeouts, so health checks
    # never queue for a connection a real request needs, and a flood of them
    # (the one route that needs no sign-in and touches the database) gets fast
    # 503s rather than the main pool (the re-check's N6).
    health_engine = make_engine(settings.database_url, pool_size=1, max_overflow=0, pool_timeout=2, pool_recycle=300)
    expected_schema = schema_head()

    @app.get("/health")
    def health() -> JSONResponse:
        """Up means the database answers and its schema is the one this code
        expects. A deployment that fell back to the localhost default reported
        healthy while every request failed (the review's finding 13); so did one
        whose migrations had not run, while every signed-in request was a 500
        reading a column that was not there yet (the re-check's N3)."""
        try:
            with health_engine.connect() as connection:
                version = connection.execute(text("select version_num from alembic_version")).scalar()
        except SQLAlchemyError:
            return JSONResponse({"status": "database unreachable"}, status_code=503)
        if version != expected_schema:
            return JSONResponse(
                {"status": f"database schema is at {version}, this code needs {expected_schema}: run the migrations"},
                status_code=503,
            )
        return JSONResponse({"status": "ok"})

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


def __getattr__(name: str) -> FastAPI:
    # `steward_api.main:app` for uvicorn, built on first access rather than at
    # import, so importing this module (tests do) needs no environment.
    if name == "app":
        return create_app()
    raise AttributeError(name)
