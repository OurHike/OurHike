"""Pydantic request/response models for the `/closures` router."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.closure import ClosureStatus, ModerationStatus, ReasonType


class ClosureCreate(BaseModel):
    """The client-submitted shape of a new closure report.

    No `moderation_status`, `verified_by`, or `verified_at` - all
    server-assigned, matching ReportCreate's "server-controlled fields have
    no field at all" pattern (see app/schemas/report.py).
    """

    reason_type: ReasonType
    note: str | None = None
    start_mile_marker: float
    end_mile_marker: float


class ClosureUpdate(BaseModel):
    """Fields a maintainer/club_admin can change via PATCH.

    All optional so a caller can update just the piece that changed (e.g.
    only `status`, without resending reason/note).
    """

    status: ClosureStatus | None = None
    reason_type: ReasonType | None = None
    note: str | None = None


class ClosureOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    reported_by: str
    reported_at: datetime
    trail_id: str
    start_mile_marker: float
    end_mile_marker: float
    reason_type: ReasonType
    note: str | None
    status: ClosureStatus
    moderation_status: ModerationStatus
    verified_by: str | None
    verified_at: datetime | None
