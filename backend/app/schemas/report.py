"""Pydantic request/response models for the `/reports` router."""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

from app.core.time import UtcDatetime
from app.models.profile import MODERATOR_ROLES, Profile
from app.models.report import (
    Report,
    ReporterType,
    ReportStatus,
    ReportType,
    Severity,
    Visibility,
)


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
    #
    # Typed UUID rather than str, and that is a security boundary rather
    # than tidiness (#265). This value becomes the row's PRIMARY KEY, and
    # moderation addresses a report by URL path segment
    # (`POST /reports/{report_id}/verify`). An unconstrained string let a
    # caller choose an id that no route can ever match - `a/b`, ``, `..` -
    # and since there is no delete endpoint for reports, the row was
    # unreachable forever. Measured on the merged version: a `bad_hikers`
    # report filed with id `a/b` returned 404 from BOTH verify and dismiss,
    # so anyone with an account could park un-clearable notes about named
    # people in the queue that closures and serious warnings share.
    #
    # UUID is the right constraint rather than merely a safe one: the only
    # producer is the client outbox's `crypto.randomUUID()`, so nothing
    # legitimate sends anything else.
    id: uuid.UUID | None = None

    type: ReportType
    poi_id: str | None = None
    lat: float | None = None
    lon: float | None = None

    # Where along the centerline, in miles (#244). The third sanctioned
    # client claim, and it exists for the same reason `authored_at` does:
    # the value is knowable on the phone and nowhere else. This backend holds
    # no centerline geometry - the trail is a published artifact, not a table
    # here - so a mile the client does not send is a mile that does not exist
    # server-side, and `/maintainer-assignments` resolving a thanks by mile
    # has nothing to resolve against.
    #
    # The form has been computing it all along and dropping it at submit,
    # which is what made this a defect rather than a missing feature.
    mile: float | None = None

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

    @field_validator("mile")
    @classmethod
    def _reject_an_impossible_mile(cls, value: float | None) -> float | None:
        """Bounded at the one end this server can bound (#244).

        Below zero is south of the southern terminus, which no trail index
        produces and no snap can return - so a negative is a bug or a lie
        either way, and it would sort into every route range that starts at
        mile 0.

        NaN and the infinities are refused because a mile has to be
        comparable at all: every `>=` and `<=` against NaN is false, so a
        serious warning carrying one is silently absent from every banner
        rather than wrong in a visible way. **JSON cannot deliver them** -
        FastAPI's parser refuses the bare `NaN` token and `JSON.stringify`
        writes `null` - so this guards the model rather than the wire, which
        matters because pydantic accepts both as floats by default
        (`allow_inf_nan`) for anything constructing a `ReportCreate` in
        Python.

        **No upper bound, deliberately.** The trail's length is a property of
        the published centerline (~2,197 miles today, and it moves every
        year as relocations land), and this backend does not hold it. A
        constant here would be a second copy of a number the pipeline owns,
        wrong the first time the trail is re-measured, and it would start
        refusing real reports from the northern end.
        """
        if value is None:
            return None
        # `!=` on itself is the NaN test that survives without importing math.
        if value != value or value in (float("inf"), float("-inf")):
            raise ValueError("mile must be a real number")
        if value < 0:
            raise ValueError("mile cannot be negative")
        return value


class ReportOut(BaseModel):
    """One report, as much of it as the caller is entitled to (#252).

    **Build these with `for_viewer`, never by returning the ORM row.** Four
    fields are withheld from anyone who is neither the reporter nor a
    moderator, and the withholding happens at construction so a caller cannot
    leak them by forgetting to check - the same posture
    app/routers/maintainer_assignments.py takes with `display_name`.

    Nothing structural stops `return report` from a handler, and it is worth
    being honest about that rather than claiming otherwise. Dropping
    `from_attributes` looks like it would - `ReportOut.model_validate(row)`
    then raises - but FastAPI validates response models with
    `validate_python(value, from_attributes=True)` passed explicitly
    (fastapi/_compat/v2.py), so `response_model=ReportOut` would go on
    serialising the whole ORM row regardless. A comment claiming the leak is
    impossible would be worse than no comment. The guard is
    tests/test_routers_reports.py's route-table check, which walks the real
    app and fails on any handler returning a report by another path.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    type: ReportType
    poi_id: str | None
    lat: float | None
    lon: float | None

    # Public, alongside `lat`/`lon` and for the same reason they are (#244):
    # it says nothing about the reporter that the coordinates next to it do
    # not already say, and anyone holding the published centerline can derive
    # it from them anyway. Withholding it would hide it from the app while
    # leaving it computable with the trail file and a script.
    mile: float | None

    reporter_type: ReporterType
    timestamp: UtcDatetime
    note: str | None
    photo_url: str | None
    follow_up: Any | None
    status: ReportStatus
    visibility: Visibility
    severity: Severity

    # When a moderator confirmed this, or null if none has (#292).
    #
    # Public, and matching what `ClosureOut` has published all along - the
    # same pair, split the same way: `verified_at` goes out, `verified_by`
    # stays behind, so the audit trail is intact in the database and only the
    # person-fact stops being handed to anonymous callers.
    #
    # It is worth saying why this is not `received_at`, which sits withheld
    # ten lines below for being "a second clock". That one narrows "when was
    # this person there", because a report arrives when its author next has
    # signal. This one is a fact about a MODERATOR at a desk, days later as
    # often as not - it says nothing about where the reporter was or when,
    # and `timestamp` is already public and exact.
    #
    # Withholding it would cost something real. `SeriousWarningSheet` renders
    # "Confirmed by club moderators - <date>", and a hiker weighing a strong
    # claim about a person is entitled to check when somebody stood behind
    # it. `status` alone says a moderator acted; only this says when.
    verified_at: UtcDatetime | None = None

    # ---- Withheld from the public. Null is "not for you", not "unset". ----

    # A stable account UUID next to a trail position and a time is the
    # linkability features/IDENTITY_AND_PRIVACY.md names: group by it and a
    # hiker's route down the corridor falls out, with curl and no account.
    # `reporter_type` is the public attribution by design - it informs
    # without identifying.
    reporter_id: str | None = None

    # A second clock. Even with `timestamp` left exact, the pair narrows
    # "when was this person there" further than either alone, and nothing
    # public reads it - the client's ReportSummary does not even declare it.
    received_at: UtcDatetime | None = None

    # Only meaningful on a `thanks`, which is `club_only` and so never
    # reaches a non-owner through these endpoints anyway. They are withheld
    # because `create_report` copies them from the request for EVERY type
    # while only a `thanks` is forced to `club_only` - so a `blowdown`
    # carrying an arbitrary real profile id is `public`, and `maintainer_id`
    # was a second reporter_id nobody had noticed.
    maintainer_id: str | None = None
    club_id: str | None = None

    @classmethod
    def for_viewer(cls, report: "Report", viewer: "Profile | None") -> "ReportOut":
        """The only correct way to build one. `viewer` is None when anonymous.

        Privileged means the reporter reading their own report, or a
        moderator - the two audiences that already authenticate, and the two
        `MODERATOR_ROLES` exists to keep in step.

        Per (row, viewer) rather than per route, which is what rules out a
        public-schema/privileged-subclass split: `GET /reports` with a token
        returns the caller's own rows AND other people's public rows in one
        response, so the decision has to be made row by row inside it.
        """
        privileged = viewer is not None and (report.reporter_id == viewer.id or viewer.role in MODERATOR_ROLES)

        return cls(
            id=report.id,
            type=report.type,
            poi_id=report.poi_id,
            lat=report.lat,
            lon=report.lon,
            mile=report.mile,
            reporter_type=report.reporter_type,
            timestamp=report.timestamp,
            note=report.note,
            photo_url=report.photo_url,
            follow_up=report.follow_up,
            status=report.status,
            visibility=report.visibility,
            severity=report.severity,
            verified_at=report.verified_at,
            reporter_id=report.reporter_id if privileged else None,
            received_at=report.received_at if privileged else None,
            maintainer_id=report.maintainer_id if privileged else None,
            club_id=report.club_id if privileged else None,
        )


class ReportPhotoLink(BaseModel):
    """A short-lived URL that fetches one report's photo (#385).

    The answer from `GET /reports/{id}/photo/link`, for the caller that
    cannot follow the redirect form: an `<img>` carries no `Authorization`
    header, so the token goes on this JSON call and the URL goes in `src`.

    **This body is a bearer capability, not a description of one.** Whoever
    holds the string can fetch that object until it expires, with no further
    check - so it is never stored, never logged, and the response is
    `no-store`. app/core/photos.py's header is the full trade.

    No `photo_url`, deliberately: the object KEY is a stored field the client
    already has from the queue, and repeating it here would invite a client
    to build its own URL from it. The signed URL is the only spelling that
    was authorised.
    """

    url: str

    # Seconds, matching `PHOTO_URL_TTL_SECONDS`. Sent so a screen that holds a
    # link open - a moderation queue worked through slowly - re-asks on a
    # number from the server rather than one it guessed. The alternative to
    # re-asking is a longer TTL, which is a real weakening of the trade above
    # rather than a tuning knob (#385).
    expires_in: int
