"""Pydantic request/response models for the `/reports` router."""

from datetime import datetime, timedelta, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

from app.models.report import ReporterType, ReportStatus, ReportType, Severity, Visibility


class ReportCreate(BaseModel):
    """The client-submitted shape of a new report.

    Deliberately has no `visibility` and no `severity` field - both are
    server-controlled (see app/models/report.py's module docstring) and
    are silently ignored if a client sends them anyway (pydantic's default
    "ignore unknown fields" behavior), rather than being accepted and then
    overridden after the fact. Likewise no `timestamp`, `status`,
    `received_at` or `reporter_id` - all server-assigned.

    `id` is the second sanctioned exception, and it is an idempotency key
    rather than a convenience (#243). On trail-side signal the classic
    failure is a request that commits here and whose 201 never arrives: the
    client's send throws, the item stays in its outbox, and the next flush
    files the same report again. The outbox already mints a UUID per item
    and documents it as "stable across retries, so a resend is recognisably
    the same report" - it just had nowhere to send it. Accepting it here is
    what makes that sentence true.

    `authored_at` is the one sanctioned exception, and it exists because
    OurHike is offline-first: a report written on the trail and synced days
    later has to keep the time it was WRITTEN (WIREFRAMES.md's "the moment
    of writing, not of sending", and `9c`'s outbox syncing "with their
    original timestamps"). Recording the sync time instead would tell a
    maintainer a three-day-old blowdown is fresh.

    It is a claim rather than a fact, so it is bounded: the server keeps its
    own `received_at` alongside, and a future-dated value is refused. The
    past is deliberately NOT bounded - being off-grid for two weeks is
    ordinary on a thru hike, not suspicious.
    """

    # Optional, and falls back to a server-generated UUID exactly the way
    # `authored_at` falls back to the server clock - the same pattern, for
    # the same reason: a field the server can supply itself should not be a
    # 422 waiting to happen for a caller that omits it. The outbox always
    # sends one, which is what gives the retry path its guarantee.
    id: str | None = None

    type: ReportType
    poi_id: str | None = None
    lat: float | None = None
    lon: float | None = None
    reporter_type: ReporterType
    note: str | None = None
    photo_url: str | None = None
    authored_at: datetime | None = None

    # Only meaningful for `thanks`; both optional, both may be absent.
    maintainer_id: str | None = None
    club_id: str | None = None

    @field_validator("authored_at")
    @classmethod
    def _reject_future_authoring(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None

        # Phone clocks drift, so a small lead is skew rather than tampering.
        skew = timedelta(minutes=5)
        now = datetime.now(timezone.utc)
        compared = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)

        if compared > now + skew:
            raise ValueError("authored_at cannot be in the future")
        return value


class ReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    reporter_id: str
    type: ReportType
    poi_id: str | None
    lat: float | None
    lon: float | None
    reporter_type: ReporterType
    timestamp: datetime
    note: str | None
    photo_url: str | None
    follow_up: Any | None
    received_at: datetime
    maintainer_id: str | None
    club_id: str | None
    status: ReportStatus
    visibility: Visibility
    severity: Severity
