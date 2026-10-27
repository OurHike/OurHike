"""Refuse any request body past limits.MAX_BODY_BYTES, before it is buffered.

backend/app/core/body_limit.py's design, reduced: a Content-Length past the
ceiling is answered 413 before a byte is read, and a body without one is cut
off the moment the running total crosses it, because the header is only a claim.
"""

from __future__ import annotations

import re

from fastapi import HTTPException
from starlette import status
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

TOO_LARGE = "Request body is too large."


class BodyLimitMiddleware:
    """`larger` names the few paths allowed a bigger body, by a pattern on the
    path and that path's own ceiling: the photo upload, which also caps itself."""

    def __init__(self, app: ASGIApp, max_bytes: int, larger: tuple[tuple[re.Pattern[str], int], ...] = ()) -> None:
        self.app = app
        self.default_max = max_bytes
        self.larger = larger

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path", "")
        max_bytes = next((ceiling for pattern, ceiling in self.larger if pattern.fullmatch(path)), self.default_max)
        for name, value in scope.get("headers", []):
            if name == b"content-length":
                try:
                    declared = int(value)
                except ValueError:
                    response = JSONResponse({"detail": "Malformed Content-Length."}, status_code=status.HTTP_400_BAD_REQUEST)
                    await response(scope, receive, send)
                    return
                if declared > max_bytes:
                    response = JSONResponse({"detail": TOO_LARGE}, status_code=status.HTTP_413_CONTENT_TOO_LARGE)
                    await response(scope, receive, send)
                    return
        seen = 0

        async def capped() -> Message:
            nonlocal seen
            message = await receive()
            if message["type"] == "http.request":
                seen += len(message.get("body", b""))
                if seen > max_bytes:
                    raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, TOO_LARGE)
            return message

        await self.app(scope, capped, send)
