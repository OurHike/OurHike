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
    `received_at`, `reporter_id`, or `id` - all server-assigned.

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

    type: ReportType
    poi_id: str | None = None
    lat: float | None = None
    lon: float | None = None
    reporter_type: ReporterType
    note: str | None = None
    photo_url: str | None = None
    authored_at: datetime | None = None

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
    status: ReportStatus
    visibility: Visibility
    severity: Severity
