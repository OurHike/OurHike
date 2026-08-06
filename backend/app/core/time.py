"""Small shared helpers for time values used across the backend."""

from datetime import datetime, timezone
from typing import Annotated

from pydantic import PlainSerializer, WithJsonSchema


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _stamp_utc(value: datetime) -> str:
    """Render a stored datetime with the UTC designator it was always meant to carry.

    Everything is stored naive-UTC (see app/models/profile.py for the
    convention and its history), which is unambiguous right up
    until it leaves the server. `2026-08-06T12:00:00` with no `Z` and no
    offset is, per ECMAScript, *local* time to `new Date()` - so every
    timestamp would shift by the viewer's UTC offset, four to five hours
    along the trail. That lands on exactly the signal reports were built to
    protect: `authored_at` exists so a report written Monday still reads as
    Monday, and the naive form quietly moves Monday evening to Tuesday for
    an east-coast reader.

    Stamping happens here, on the way out, so storage stays naive exactly as
    the convention requires. An already-aware value is converted rather than
    assumed, so a value that somehow arrives with an offset still leaves as
    the same instant in UTC.
    """
    aware = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    return aware.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


# Applied to response-model fields rather than to the models' storage: the
# serializer is scoped to JSON so `model_dump()` in Python mode still yields
# real `datetime` objects, and only the wire format changes.
#
# The explicit JSON schema keeps OpenAPI honest. `PlainSerializer`'s
# `return_type=str` would otherwise document these fields as bare strings,
# losing `format: date-time` - the contract would get less precise in the
# same change that made the values correct.
UtcDatetime = Annotated[
    datetime,
    PlainSerializer(_stamp_utc, return_type=str, when_used="json"),
    WithJsonSchema({"type": "string", "format": "date-time"}, mode="serialization"),
]
