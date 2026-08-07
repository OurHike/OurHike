"""Pydantic request/response models for the `/closures` router."""

from pydantic import BaseModel, ConfigDict

from app.core.time import UtcDatetime
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


class ClosureVerify(BaseModel):
    """What a moderator may settle in the same breath as verifying.

    Optional, and the endpoint accepts no body at all - because for the
    ordinary closure there is nothing to settle. A closure is born `closed`
    (#246), so "yes, this is real" needs no second thought about status.

    The case this exists for is the reroute. A moderator who has confirmed
    both that the trail is shut AND that there is a marked way round is
    making one judgment, and without this they would have to follow the
    verify with a separate `PATCH /closures/{id}` that nothing in the flow
    tells them about - which is the same trap #246 was, one size smaller.

    `reason_type` and `note` are deliberately NOT here. Correcting what a
    reporter wrote is editing their report, not verifying it, and PATCH is
    where that belongs.
    """

    status: ClosureStatus | None = None


class ClosureOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    reported_by: str
    reported_at: UtcDatetime
    trail_id: str
    start_mile_marker: float
    end_mile_marker: float
    reason_type: ReasonType
    note: str | None
    status: ClosureStatus
    moderation_status: ModerationStatus
    verified_by: str | None
    verified_at: UtcDatetime | None
