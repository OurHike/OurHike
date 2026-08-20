"""FastAPI application entrypoint."""

import math

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.routers import (
    app_failures,
    closures,
    field_notes,
    hikes,
    maintainer_assignments,
    moderation,
    poi_photos,
    preferences,
    profiles,
    reports,
    volunteer_hours,
    wrong_way,
)

app = FastAPI(title="OurHike backend")

# Browsing endpoints are meant to be reachable from the client PWA's own
# origin (and, during local dev, from Vite's dev server) with no auth token
# required - see TESTING.md's Backend section. Auth is a bearer JWT in an
# Authorization header (Supabase Auth), never a cookie, so credentialed
# CORS isn't needed - allow_credentials stays False, which is what makes a
# wildcard origin safe here. Tighten to an env-driven allowlist once real
# deployed origins are known.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _json_safe(value):
    """`value` with non-finite floats replaced by their spelling.

    A validation error echoes the offending input back in its detail, and
    when that input is the NaN or Infinity the finite-float guard (#658,
    schemas/common.py) just refused, the default 422 rendering crashes on
    its own payload - json.dumps refuses the very value the error is about,
    and the caller gets a 500 for sending the thing the 422 exists to name.
    """
    if isinstance(value, float) and not math.isfinite(value):
        return repr(value)
    if isinstance(value, dict):
        return {key: _json_safe(inner) for key, inner in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(inner) for inner in value]
    return value


@app.exception_handler(RequestValidationError)
async def _validation_error_survives_its_own_payload(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": _json_safe(jsonable_encoder(exc.errors()))},
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(profiles.router)
app.include_router(hikes.router)
app.include_router(preferences.router)
app.include_router(reports.router)
app.include_router(poi_photos.router)
app.include_router(closures.router)
app.include_router(wrong_way.router)
app.include_router(maintainer_assignments.router)
app.include_router(moderation.router)
app.include_router(app_failures.router)
app.include_router(field_notes.router)
app.include_router(volunteer_hours.router)
