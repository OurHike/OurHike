"""Pydantic request/response models for the `/closures` router."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, TypeAdapter, ValidationError, field_validator
from pydantic.networks import HttpUrl

from app.core.time import UtcDatetime
from app.models.closure import ClosureStatus, ModerationStatus, ReasonType

# Validates scheme and shape without changing the stored type. `HttpUrl`
# accepts http and https and nothing else, which is the property that matters:
# `reroute_url` is rendered as a link a hiker taps from a safety sheet, so a
# `javascript:` or `data:` URL there is the failure being excluded. The value
# is kept as the maintainer's own string rather than `str(HttpUrl(...))`,
# because that round trip normalises - appending a trailing slash to a bare
# host, lowercasing - and a stored URL that differs from the one pasted is a
# surprise nobody asked for.
_HTTP_URL = TypeAdapter(HttpUrl)


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

    **Omitted and explicitly null mean different things for the three fields
    added by #245.** They are the fields whose value legitimately goes back to
    unknown: a reopening date slips or is withdrawn, a club takes its reroute
    notice down. With `None` read as "absent" - the rule the older fields keep
    - there would be no way to express that, and a stale promised date would
    outlive the promise. So the router consults `model_fields_set`, and
    `{"expected_reopen": null}` clears while `{}` leaves it alone.

    `status` and `reason_type` keep the older rule, and not just for
    compatibility: both are `nullable=False`, so there is no null state for an
    explicit null to mean. `note` is nullable and could take the newer rule,
    but changing it would alter the behaviour of an endpoint this issue did
    not ask about - left as it is, deliberately.
    """

    status: ClosureStatus | None = None
    reason_type: ReasonType | None = None
    note: str | None = None

    # When the TRAIL shut - not when this was filed (`reported_at`) or
    # confirmed (`verified_at`). See app/models/closure.py.
    closed_since: datetime | None = None
    expected_reopen: datetime | None = None
    reroute_url: str | None = None

    @field_validator("reroute_url")
    @classmethod
    def _require_a_followable_link(cls, value: str | None) -> str | None:
        if value is None:
            return None

        # An empty string is the shape a form sends for "I cleared this box",
        # and storing it would give the client a truthy value that renders an
        # anchor pointing nowhere. Read as the clear it plainly is.
        if not value.strip():
            return None

        try:
            _HTTP_URL.validate_python(value)
        except ValidationError as exc:
            raise ValueError("reroute_url must be an http or https URL") from exc
        return value


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

    # The three the sheet renders (#245). `UtcDatetime` rather than bare
    # `datetime` for the same reason every other timestamp here uses it: an
    # unstamped value is read as local time by `new Date()`, which would move
    # "Closed since August 1" by the reader's offset.
    closed_since: UtcDatetime | None
    expected_reopen: UtcDatetime | None
    reroute_url: str | None
