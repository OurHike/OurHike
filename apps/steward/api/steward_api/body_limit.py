"""Refuse any request body past limits.MAX_BODY_BYTES, before it is buffered.

backend/app/core/body_limit.py's design, reduced: a Content-Length past the
ceiling is answered 413 before a byte is read, and a body without one is cut
off the moment the running total crosses it, because the header is only a claim.
"""

from __future__ import annotations

from fastapi import HTTPException
from starlette import status
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

TOO_LARGE = "Request body is too large."


class BodyLimitMiddleware:
    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        for name, value in scope.get("headers", []):
            if name == b"content-length":
                try:
                    declared = int(value)
                except ValueError:
                    response = JSONResponse({"detail": "Malformed Content-Length."}, status_code=status.HTTP_400_BAD_REQUEST)
                    await response(scope, receive, send)
                    return
                if declared > self.max_bytes:
                    response = JSONResponse({"detail": TOO_LARGE}, status_code=status.HTTP_413_CONTENT_TOO_LARGE)
                    await response(scope, receive, send)
                    return
        seen = 0

        async def capped() -> Message:
            nonlocal seen
            message = await receive()
            if message["type"] == "http.request":
                seen += len(message.get("body", b""))
                if seen > self.max_bytes:
                    raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, TOO_LARGE)
            return message

        await self.app(scope, capped, send)
