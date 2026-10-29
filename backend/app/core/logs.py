"""One logger for the backend, JSON on stderr, and a request id on every line (#1759).

THE GAP. Before this, `grep getLogger app/` found one file, `core/photos.py`.
Account deletion's catch-all and the registry sign-off's refused pull request
both dropped their cause, and Uvicorn's access log was the only record of a
401 or a 5xx. The access log carries no id the hiker can quote, so "it failed
at 3 pm" could not be tied to a line.

WHAT THIS IS. The `app` logger (every module's `logging.getLogger(__name__)`
is a child of it), one handler writing one JSON object per line to stderr, and
a middleware that mints a request id, returns it as `X-Request-Id`, and logs
one line for each 401 and each 5xx - including the 500 an unhandled exception
becomes, which `RequestIdMiddleware` answers itself so that it carries the id
too (the reason is on the class).

Minted here, never read from the request: an id a caller chooses is a string
a caller can use to forge or split log lines, and nothing in this repository
has a reason to correlate with a caller's own id.

WHAT IT MUST NEVER PUT IN A LINE. A presigned URL, a bearer token, the R2
endpoint. `core/photos.py` already keeps that rule. This module logs the
method, the route path and the status - not the query string, which is where
a presigned URL would sit, and not any header - and the route's template, so an
id or a token in the path stays out too. Nor the values a failed database
statement was bound to: `describe_failure` below is how a caller logs a
database error by its names alone.

@unvalidated: the 401-and-5xx filter on the request line is picked, not
measured. It is the two classes the issue names as invisible; whether 403, 429
or a slow 200 belong beside them is a question for the first week of real logs.

AND ONE LINE UVICORN WRITES IS DROPPED. Uvicorn's access log (the
`uvicorn.access` logger) opens every line with the client's address. For
`POST /usage-events` that is an IP beside the moment a phone found signal -
exactly what that endpoint promises never to keep (app/routers/analytics.py,
and the Privacy Policy: no IP is recorded with these counts) - so
`DropUnloggedPaths` removes those lines before any handler sees them. What it
cannot reach, said rather than implied: the host's own edge, which may log
the address of every request it forwards.
"""

from __future__ import annotations

import contextvars
import json
import logging
import sys
import uuid
from datetime import UTC, datetime

from starlette.responses import PlainTextResponse
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


# Requests the access log must not record, by path (the module docstring says why).
UNLOGGED_PATHS = ("/usage-events",)


class DropUnloggedPaths(logging.Filter):
    """Drop Uvicorn's access line for a request to one of `UNLOGGED_PATHS`.

    Uvicorn 0.54 (requirements.txt) logs `'%s - "%s %s HTTP/%s" %d'` with the
    client address, method, path-with-query, HTTP version and status as the
    record's args, so the path is the third. A record of any other shape is
    let through untouched: this decides about one line, not about logging.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args if isinstance(record.args, tuple) else ()
        if len(args) < 3:
            return True
        path = str(args[2]).split("?", 1)[0]
        return not any(path == unlogged or path.startswith(f"{unlogged}/") for unlogged in UNLOGGED_PATHS)


def configure_logging() -> None:
    """Attach the JSON handler to the `app` logger, and the access-log filter to Uvicorn's, once each.

    Idempotent because the module that calls it is imported by every test.
    `propagate` is off so a line is not also written by the root handler
    Uvicorn installs, in a second format. The filter sits on the logger, not
    a handler, so it holds whatever handlers Uvicorn's own logging config
    attaches - and that config removes handlers, never filters.
    """
    access = logging.getLogger("uvicorn.access")
    if not any(isinstance(existing, DropUnloggedPaths) for existing in access.filters):
        access.addFilter(DropUnloggedPaths())
    if any(isinstance(handler.formatter, JsonFormatter) for handler in logger.handlers):
        return
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def describe_failure(exc: BaseException) -> str:
    """Name what failed - exception classes, SQLSTATE, constraint, table, column - and no value.

    `str()` of a SQLAlchemy `DBAPIError` ends in `[parameters: ...]`, the
    values bound to the failed statement, and the psycopg error it wraps (and
    that `logger.exception` would print as its cause) carries Postgres's DETAIL
    line, which quotes the row: `Key (id)=(...) already exists`. On account
    deletion those values are the deleting hiker's own. The names kept here are
    schema, not data, and they are what an operator needs to find "a constraint
    the deletion did not expect". tests/test_logs.py raises a real Postgres
    unique violation through `DELETE /profiles/me` and checks that neither the
    row's id nor its display name reaches the line.

    Anything that is not a database error is named by its class alone, for the
    same reason: its message is free text nobody here has read.
    """
    parts = [type(exc).__name__]
    driver_error = getattr(exc, "orig", None)  # set on sqlalchemy.exc.DBAPIError
    if driver_error is not None:
        parts.append(type(driver_error).__name__)
        diag = getattr(driver_error, "diag", None)
        names = {
            "sqlstate": getattr(driver_error, "sqlstate", None),
            "constraint": getattr(diag, "constraint_name", None),
            "table": getattr(diag, "table_name", None),
            "column": getattr(diag, "column_name", None),
        }
        parts.extend(f"{label}={value}" for label, value in names.items() if value)
    return " ".join(parts)


class RequestIdMiddleware:
    """Mint a request id, answer it in `X-Request-Id`, log the failures.

    A CRASH'S 500 IS ANSWERED HERE. Starlette's `ServerErrorMiddleware`, which
    turns an unhandled exception into a 500, wraps every middleware
    `add_middleware` installs - this one included - so its response goes out
    through a `send` this class never sees, with no `X-Request-Id`: the one
    response whose id a hiker most needs to quote. So when the app raises
    before it has started a response, this class sends the same bare
    `Internal Server Error` 500 through `send_with_id`, then re-raises.
    `ServerErrorMiddleware` sees a response already started, sends nothing of
    its own, and still hands the exception to the server, so the traceback is
    logged exactly where it was before.

    That 500 still carries no CORS headers, as it did not before: the exception
    passed up through `CORSMiddleware`, which only adds them to a response sent
    inside it. A browser on another origin reads it as a network error, so the
    id reaches the operator's log and a non-browser caller, not the client's
    JavaScript.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = uuid.uuid4().hex
        token = _request_id.set(request_id)
        status_code = 500  # what a handler that raises before responding becomes
        response_started = False

        async def send_with_id(message: Message) -> None:
            nonlocal status_code, response_started
            if message["type"] == "http.response.start":
                response_started = True
                status_code = message["status"]
                headers = list(message.get("headers", []))
                headers.append((REQUEST_ID_HEADER.lower().encode(), request_id.encode()))
                message = {**message, "headers": headers}
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        except Exception:
            if not response_started:
                await PlainTextResponse("Internal Server Error", status_code=500)(scope, receive, send_with_id)
            raise
        finally:
            if status_code == 401 or status_code >= 500:
                # The route's template, never the path the caller sent: a path
                # can carry a capability (`/nominations/{token}` is a vote that
                # lasts `TOKEN_DAYS`, 45), and the template is what a reader needs to
                # find the handler. FastAPI leaves the matched route in the
                # scope; a request no route matched has none to name.
                route = getattr(scope.get("route"), "path", None) or "(no route)"
                _request_logger.warning("%s %s -> %s", scope.get("method"), route, status_code)
            _request_id.reset(token)
