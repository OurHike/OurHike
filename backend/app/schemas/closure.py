"""Pydantic request/response models for the `/closures` router."""

import uuid
from datetime import datetime, timedelta, timezone

from pydantic import BaseModel, ConfigDict, TypeAdapter, ValidationError, field_validator, model_validator
from pydantic.networks import HttpUrl

from app.core.time import UtcDatetime
from app.models.closure import ClosureStatus, ModerationStatus, ReasonType
from app.schemas.common import FiniteFloat, NoteText
from app.schemas.partial import reject_explicit_null

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

    # The outbox's idempotency key (#832), exactly as `ReportCreate.id` is
    # and for the same failure: a closure is authored at the washout, with no
    # signal, and flushed whenever signal returns - so the request that
    # commits here and loses its response on the way back is the ordinary
    # case rather than the unlucky one. Without this, the retry that failure
    # forces would file a second closure over the same stretch.
    #
    # Optional, because every client that predates the authoring form sends
    # nothing and the server still has to accept a closure from a maintainer
    # with curl.
    id: uuid.UUID | None = None

    reason_type: ReasonType
    note: NoteText | None = None
    start_mile_marker: FiniteFloat
    end_mile_marker: FiniteFloat

    # When somebody stood in front of it, not when the phone got signal
    # (#832). `reported_at` is what the sheet ages a closure by, and the
    # column's own comment already makes the point that a closure can arrive
    # days old - "a closure reported four days after a storm is already four
    # days old when it arrives". A queued closure that reads as filed on the
    # day its phone found a bar makes that number a lie in the safe-looking
    # direction: fresher than it is.
    #
    # Client claim, server fallback - `ReportCreate.authored_at`'s posture,
    # with its skew allowance, because the same phone clocks are involved.
    reported_at: datetime | None = None

    @field_validator("reported_at")
    @classmethod
    def _reject_future_reporting(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None

        # Five minutes of lead is drift; more is a clock nobody should be
        # taking dictation from. ReportCreate's number, deliberately shared.
        skew = timedelta(minutes=5)
        now = datetime.now(timezone.utc)
        compared = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)

        if compared > now + skew:
            raise ValueError("reported_at cannot be in the future")
        return value

    # Where the two ends physically are (#674). Optional, because plenty of
    # callers send nothing - a maintainer with curl, a client older than
    # #832's form - see app/models/closure.py for why null is the ordinary
    # state rather than a gap. Client-supplied and derived, the same posture
    # `ReportCreate.mile` documents.
    start_lat: FiniteFloat | None = None
    start_lon: FiniteFloat | None = None
    end_lat: FiniteFloat | None = None
    end_lon: FiniteFloat | None = None

    @model_validator(mode="after")
    def _require_whole_points(self) -> "ClosureCreate":
        """A latitude without its longitude is not a position (#674).

        Refused rather than dropped, and refused rather than half-stored.
        The whole value of this geometry is that it still means something
        after a re-measure; half of it means nothing at any time, and
        storing a lone `start_lat` would put a row in the table that looks
        anchored and is not - the failure mode a null pair is specifically
        designed to avoid, wearing a disguise.
        """
        for end in ("start", "end"):
            lat, lon = getattr(self, f"{end}_lat"), getattr(self, f"{end}_lon")
            if (lat is None) != (lon is None):
                raise ValueError(f"{end}_lat and {end}_lon must be sent together or not at all")
        return self

    @model_validator(mode="after")
    def _order_the_mile_markers(self) -> "ClosureCreate":
        """A reversed pair is normalised, not refused (#257).

        The client's own consumers split on this - warningsOnRoute normalises
        ordering, closureBanner assumes start <= end - and a reversed pair
        made the inside-the-closure check unsatisfiable and the banner's
        distance wrong. The fix belongs at the source, and it is a swap
        rather than a 422 because the reporter's meaning is unambiguous:
        "the trail is closed between these two miles" says the same thing
        in either order, and a hiker reporting a closure from a trailhead
        should not be bounced over which end they named first.

        **The geometry swaps with the miles (#674), and must.** Each point
        is the position OF its mile, so normalising one without the other
        would silently pair the southern end's coordinates with the northern
        end's mile - a closure whose two ends are each other's, which is
        worse than the reversed pair this validator exists to fix and
        invisible in a way the reversed pair was not. Ordering runs after
        `_require_whole_points`, so either both ends carry a full point or
        neither does, and the swap cannot manufacture a half-point.
        """
        if self.start_mile_marker > self.end_mile_marker:
            self.start_mile_marker, self.end_mile_marker = (
                self.end_mile_marker,
                self.start_mile_marker,
            )
            self.start_lat, self.end_lat = self.end_lat, self.start_lat
            self.start_lon, self.end_lon = self.end_lon, self.start_lon
        return self


class ClosureUpdate(BaseModel):
    """Fields a maintainer/club_admin can change via PATCH.

    All optional so a caller can update just the piece that changed (e.g.
    only `status`, without resending reason/note).

    **Omitted and explicitly null mean different things** (#245 established
    it for the three detail fields; #255 made it the convention for every
    nullable field here). A field's value legitimately goes back to unknown:
    a reopening date slips or is withdrawn, a club takes its reroute notice
    down, a stale note is cleared rather than overwritten. With `None` read
    as "absent" there would be no way to express any of that. So the router
    consults `model_fields_set`, and `{"note": null}` clears while `{}`
    leaves it alone.

    `status` and `reason_type` are `nullable=False`, so there is no null
    state for an explicit null to mean - it is a 422 naming the field, per
    the shared convention in app/schemas/partial.py (#255). Before that it
    was silently dropped, which read as success and did nothing.
    """

    status: ClosureStatus | None = None
    reason_type: ReasonType | None = None
    note: NoteText | None = None

    _no_explicit_nulls = reject_explicit_null("status", "reason_type")

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
    """What `/closures` answers with.

    **`reported_by` and `verified_by` are deliberately absent (#430).** They
    are profile ids - which are Supabase auth user ids - and `GET /closures`
    needs no account, so every one of them was readable by anybody. Joined
    across closures they say which maintainer verifies which stretch of trail
    and how often, which is the fact `features/SAYING_THANKS.md` declines to
    publish without consent and the reason `maintainer_assignments` withholds
    a display name behind `publicly_creditable` rather than filtering it
    downstream.

    Nothing read them. `ClosureSheet.tsx` used to render "Marked by <name>"
    from exactly these two and that field was deleted before this, on the
    grounds that it was "a fact about a person, and the app has not settled
    when it shows those"; `ClosureDetail` has never carried either.

    **The columns stay.** This is the wire, not the record - `closures.py`
    still stamps `reported_by` on create and `moderation.py` still stamps
    `verified_by` on verify, so the audit trail is intact in the database and
    only stops being handed to anonymous HTTP callers. Since #658 that
    sentence is true rather than aspirational: the moderation surface
    answers with `ClosureModerationOut` (schemas/moderation.py), which is
    this shape plus the trail, for exactly the role-gated audience the
    trail exists for.

    If attribution is ever wanted on the closure sheet, the mechanism already
    exists and is not a new field here: `publicly_creditable` plus
    `display_name`, opt-in and revocable, as `routers/maintainer_assignments.py`
    already does it.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    reported_at: UtcDatetime
    trail_id: str
    start_mile_marker: float
    end_mile_marker: float

    # The two ends' positions (#674), published for the same reason
    # `ReportOut` publishes `lat`/`lon`: the client is the only thing that
    # can use them. The mile a hiker reads is a projection of these against
    # whichever release their phone is holding, and the projection has to
    # happen where the centerline is - which is the client, never here (see
    # app/models/report.py: "this backend holds no centerline geometry").
    #
    # Null on every row filed before the column existed, and on every row
    # filed until a client learns to send them. The client's contract is to
    # fall back to the stored mile rather than to hide the closure, so an
    # unanchored closure reads exactly as it does today.
    start_lat: float | None
    start_lon: float | None
    end_lat: float | None
    end_lon: float | None
    reason_type: ReasonType
    note: str | None
    status: ClosureStatus
    moderation_status: ModerationStatus
    verified_at: UtcDatetime | None

    # The three the sheet renders (#245). `UtcDatetime` rather than bare
    # `datetime` for the same reason every other timestamp here uses it: an
    # unstamped value is read as local time by `new Date()`, which would move
    # "Closed since August 1" by the reader's offset.
    closed_since: UtcDatetime | None
    expected_reopen: UtcDatetime | None
    reroute_url: str | None
