"""Pydantic request/response models for moderation-queue actions."""

from pydantic import BaseModel

from app.models.report import Severity
from app.schemas.closure import ClosureOut
from app.schemas.report import ReportOut


class ReportVerifyRequest(BaseModel):
    """`severity` is optional, and omitting it LEAVES IT ALONE.

    This docstring used to say that and the code did the opposite: the field
    defaulted to `normal` and `verify_report` assigned it unconditionally, so
    the parenthetical excuse - "normal, since there's no path to set it
    before this action exists" - was false the moment anybody used this same
    action a second time (#251).

    What that cost: moderator A escalates a `bad_hikers` report to `serious`,
    which is what makes the 44px warning pin exist on every phone
    (features/HIKER_SAFETY.md §1, client/src/map/warningPin.ts). Moderator B
    re-verifies it with `{}` - or with a client that simply does not send the
    field - and the pin disappears from the map. No error, no record, and the
    disappearance looks exactly like the warning having been withdrawn on
    purpose.

    `None` rather than a default value is what makes "omitted" and
    "explicitly normal" different requests. They mean different things: one
    is a moderator saying nothing about severity, the other is a moderator
    de-escalating, and only the second should change anything.
    """

    severity: Severity | None = None


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
