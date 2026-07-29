"""Pydantic request/response models for the `/reports` router."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.models.report import ReporterType, ReportStatus, ReportType, Severity, Visibility


class ReportCreate(BaseModel):
    """The client-submitted shape of a new report.

    Deliberately has no `visibility` and no `severity` field - both are
    server-controlled (see app/models/report.py's module docstring) and
    are silently ignored if a client sends them anyway (pydantic's default
    "ignore unknown fields" behavior), rather than being accepted and then
    overridden after the fact. Likewise no `timestamp`, `status`,
    `reporter_id`, or `id` - all server-assigned.
    """

    type: ReportType
    poi_id: str | None = None
    lat: float | None = None
    lon: float | None = None
    reporter_type: ReporterType
    note: str | None = None
    photo_url: str | None = None


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
    status: ReportStatus
    visibility: Visibility
    severity: Severity
