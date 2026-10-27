"""The app factory. `uvicorn steward_api.main:app` serves it with the environment's settings."""

from __future__ import annotations

import re

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from steward_api import limits
from steward_api.auth import TokenVerifier
from steward_api.body_limit import BodyLimitMiddleware
from steward_api.clubs import ClubDirectory
from steward_api.config import Settings
from steward_api.db import make_engine, make_sessionmaker
from steward_api.photos import PhotoStore
from steward_api.routes import claims, lists, me, weights


def create_app(
    settings: Settings | None = None,
    *,
    verifier: TokenVerifier | None = None,
    clubs: ClubDirectory | None = None,
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
    app.state.clubs = clubs or ClubDirectory.from_url(settings.summary_url)
    #: None when this deployment has no photo bucket: uploads then answer 503.
    app.state.photos = photos if photos is not None else settings.photo_storage()

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

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
