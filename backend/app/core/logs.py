"""One logger for the backend, JSON on stdout, and a request id on every line (#1759).

THE GAP. Before this, `grep getLogger app/` found one file, `core/photos.py`.
Account deletion's catch-all and the registry sign-off's refused pull request
both dropped their cause, and Uvicorn's access log was the only record of a
401 or a 5xx. The access log carries no id the hiker can quote, so "it failed
at 3 pm" could not be tied to a line.

WHAT THIS IS. The `app` logger (every module's `logging.getLogger(__name__)`
is a child of it), one handler writing one JSON object per line to stderr, and
a middleware that mints a request id, returns it as `X-Request-Id`, and logs
one line for each 401 and each 5xx.

Minted here, never read from the request: an id a caller chooses is a string
a caller can use to forge or split log lines, and nothing in this repository
has a reason to correlate with a caller's own id.

WHAT IT MUST NEVER PUT IN A LINE. A presigned URL, a bearer token, the R2
endpoint. `core/photos.py` already keeps that rule. This module logs the
method, the route path and the status - not the query string, which is where
a presigned URL would sit, and not any header.

@unvalidated: the 401-and-5xx filter on the request line is picked, not
measured. It is the two classes the issue names as invisible; whether 403, 429
or a slow 200 belong beside them is a question for the first week of real logs.
"""

from __future__ import annotations

import contextvars
import json
import logging
import sys
import uuid
from datetime import UTC, datetime

from starlette.types import ASGIApp, Message, Receive, Scope, Send

REQUEST_ID_HEADER = "X-Request-Id"

_request_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("request_id", default=None)

logger = logging.getLogger("app")
_request_logger = logging.getLogger("app.request")


def current_request_id() -> str | None:
    """The id of the request being served, or None outside one."""
    return _request_id.get()


class JsonFormatter(logging.Formatter):
    """One JSON object per record, with the request id when there is one."""

    def format(self, record: logging.LogRecord) -> str:
        line: dict[str, object] = {
            "time": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = current_request_id()
        if request_id is not None:
            line["request_id"] = request_id
        if record.exc_info:
            line["exception"] = self.formatException(record.exc_info)
        return json.dumps(line, default=str)


def configure_logging() -> None:
    """Attach the JSON handler to the `app` logger, once.

    Idempotent because the module that calls it is imported by every test.
    `propagate` is off so a line is not also written by the root handler
    Uvicorn installs, in a second format.
    """
    if any(isinstance(handler.formatter, JsonFormatter) for handler in logger.handlers):
        return
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


class RequestIdMiddleware:
    """Mint a request id, answer it in `X-Request-Id`, log the failures."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = uuid.uuid4().hex
        token = _request_id.set(request_id)
        status_code = 500  # what a handler that raises before responding becomes

        async def send_with_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                headers = list(message.get("headers", []))
                headers.append((REQUEST_ID_HEADER.lower().encode(), request_id.encode()))
                message = {**message, "headers": headers}
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            if status_code == 401 or status_code >= 500:
                _request_logger.warning("%s %s -> %s", scope.get("method"), scope.get("path"), status_code)
            _request_id.reset(token)
