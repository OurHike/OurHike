"""FastAPI application entrypoint."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import (
    closures,
    hikes,
    maintainer_assignments,
    moderation,
    preferences,
    profiles,
    reports,
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


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(profiles.router)
app.include_router(hikes.router)
app.include_router(preferences.router)
app.include_router(reports.router)
app.include_router(closures.router)
app.include_router(wrong_way.router)
app.include_router(maintainer_assignments.router)
app.include_router(moderation.router)
