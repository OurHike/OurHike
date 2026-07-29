"""Pydantic request models for moderation-queue actions."""

from pydantic import BaseModel

from app.models.report import Severity


class ReportVerifyRequest(BaseModel):
    """`severity` is optional - a moderator verifying a report doesn't have
    to escalate it; when omitted, severity stays at whatever it already was
    (normal, since there's no path to set it before this action exists)."""

    severity: Severity = Severity.normal
