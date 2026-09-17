"""Refuse a request body past a fixed size, before it is buffered (#1545, item 2).

THE GAP. `read_capped_body` (app/routers/reports.py) caps the three photo
uploads as their bytes arrive, for the reason #379 gives: a limit measured
after `await request.body()` has already paid the allocation it exists to
avoid. Every JSON endpoint still paid it. Starlette reads the whole body into
memory before pydantic sees a byte, uvicorn has no default request-body cap
(`backend/Dockerfile` runs it with no `--limit-*` flag), and no proxy in
front of this service is known to hold one. `POST /app-failures` needs no
account, so the cheapest request an anonymous caller could make was the one
that cost this process the most.

WHAT THIS IS. One ASGI middleware, outermost but for CORS, applying one
ceiling to every request body. It refuses twice, for the two ways a body
announces itself: a `Content-Length` past the ceiling is answered 413 before
a byte is read, and a body that arrives without one - chunked, or lying - is
cut off the moment the running total crosses the ceiling, by raising from
the `receive` the app is awaiting. That second half is the one that holds;
the header is a claim, and #379's photo cap learned the same lesson.

The photo uploads keep their own, lower cap and their own wording. Theirs
fires first because it is smaller, so nothing about their contract moves.

WHAT THIS IS NOT. A rate limit. A single request is now bounded; a thousand
of them are a thousand bounded requests, and app/routers/app_failures.py
still says out loud that nothing throttles. Nor is it a length bound on the
free-text ids (`ReportCreate.poi_id`, `TripUpload.id` and their siblings):
a `max_length` there is a request constraint an old client never knew to
obey, which is exactly what scripts/check_openapi_compat.py refuses, so
those wait for a release boundary and ride behind this ceiling meanwhile.
"""

from __future__ import annotations

# FastAPI's HTTPException rather than Starlette's, and the choice is
# load-bearing: FastAPI's request handler reads the body inside a `try` that
# re-raises an HTTPException and turns any OTHER exception into a 400 "There
# was an error parsing the body". FastAPI's class subclasses Starlette's, so
# it is recognised whichever of the two that `except` names, and the 413
# reaches the client as a 413. tests/test_body_limit.py streams an oversize
# body through a real pydantic endpoint to hold this.
from fastapi import HTTPException
from starlette import status
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

# The ceiling, in bytes, on any one request body.
#
# @unvalidated. Sixteen mebibytes is picked to sit far above the largest body
# a real client is believed to send and far below anything that would trouble
# the process: a photo is capped at MAX_PHOTO_BYTES (two mebibytes) below
# this, and a `/trips/sync` carries at most 500 trip documents - hand-sized
# JSON each, so even a first sync after a reinstall is expected in the low
# megabytes. "Expected" is the honest word: nothing records the size of a
# real sync body, and the number that would settle this is the largest one an
# account has actually sent. Until somebody measures that, this is a ceiling
# on a class of failure rather than a claim about ordinary traffic.
MAX_REQUEST_BODY_BYTES = 16 * 1024 * 1024

TOO_LARGE_DETAIL = "Request body is too large."


class BodyLimitMiddleware:
    """Pure ASGI, so it costs one header read on the way in and nothing else."""

    def __init__(self, app: ASGIApp, max_bytes: int = MAX_REQUEST_BODY_BYTES) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        declared = _declared_length(scope)
        if declared is not None and declared > self.max_bytes:
            # Refused before a byte of body is read - the cheap half. The
            # shape matches FastAPI's own error body so a client reads one
            # `detail` whichever half refused it.
            response = JSONResponse({"detail": TOO_LARGE_DETAIL}, status_code=status.HTTP_413_CONTENT_TOO_LARGE)
            await response(scope, receive, send)
            return

        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    # Raised into whatever is awaiting the body - Starlette's
                    # request parsing, inside its exception middleware - which
                    # turns it into the same 413 the header check answers.
                    raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail=TOO_LARGE_DETAIL)
            return message

        await self.app(scope, limited_receive, send)


def _declared_length(scope: Scope) -> int | None:
    """The `Content-Length` a request claims, or None when it makes no claim
    this can read. An unparseable header decides nothing; the stream still does."""
    for name, value in scope.get("headers", []):
        if name == b"content-length":
            try:
                return int(value)
            except ValueError:
                return None
    return None
