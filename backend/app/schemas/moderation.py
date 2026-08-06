"""Pydantic request/response models for moderation-queue actions."""

from pydantic import BaseModel

from app.models.report import Severity
from app.schemas.closure import ClosureOut
from app.schemas.report import ReportOut


class ReportVerifyRequest(BaseModel):
    """`severity` is optional - a moderator verifying a report doesn't have
    to escalate it; when omitted, severity stays at whatever it already was
    (normal, since there's no path to set it before this action exists)."""

    severity: Severity = Severity.normal


class ModerationQueue(BaseModel):
    """Everything awaiting a moderator, in one response.

    One combined object rather than a `pending=true` flag on each public
    list, because this is one queue: REPORT_A_PROBLEM.md has closures and
    warning escalation reusing "this exact moderation-queue mechanism...
    not building a second review workflow", and MAP_OPTIONS.md says the same
    from the closures side. Two shapes come back because a closure really is
    a different shape - a line along the trail, not a pin - which is a fact
    about the data, not a reason to make a moderator ask twice.

    Reusing `ReportOut`/`ClosureOut` rather than defining leaner queue rows:
    a moderator deciding whether a bear sighting is real needs the note, the
    location, the reporter type and the authored time, which is very nearly
    the whole record already.
    """

    reports: list[ReportOut]
    closures: list[ClosureOut]
