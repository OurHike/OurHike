"""`/reports` endpoints - community condition reports.

See ../../../features/REPORT_A_PROBLEM.md. Browsing (`GET`) needs no
account, matching every other browsing endpoint in this app; submitting
(`POST`) requires a real identity so a report has a reporter to attribute
it to and, later, moderate against.
"""

from datetime import datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import and_, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.assignments import assignments_covering
from app.core.auth import bearer_scheme, get_current_user
from app.core.orm import commit_and_refresh, get_or_404
from app.core.photos import (
    ALLOWED_CONTENT_TYPE,
    JPEG_MAGIC,
    MAX_PHOTO_BYTES,
    PHOTO_URL_TTL_SECONDS,
    PhotoStorageUnavailable,
    photo_storage_configured,
    photo_uploads_enabled,
    presigned_photo_url,
    store_photo,
)
from app.core.time import to_naive_utc, utc_now
from app.db.session import get_db
from app.models.maintainer_assignment import MaintainerAssignment
from app.models.profile import MODERATOR_ROLES, Profile
from app.models.report import Report, ReportStatus, ReportType, Visibility
from app.schemas.report import ReportCreate, ReportOut, ReportPhotoLink

router = APIRouter(prefix="/reports", tags=["reports"])

# `bad_hikers` is the one type that reports on people rather than trail
# conditions - REPORT_A_PROBLEM.md's "Bad hikers needs different handling"
# section routes it privately to maintainers/moderators instead of a
# public map pin; every other type defaults to public.
_INTERNAL_ONLY_TYPES = {ReportType.bad_hikers}

# The statuses at which a report has been through moderation, and so may be
# shown to hikers who are not its author.
#
# REPORT_A_PROBLEM.md's "Architecture fit" section is the rule this encodes:
# reports are "submitted-by-many-people data that needs moderation before
# anything becomes visible to other hikers" - the stated reason a live
# backend is in v1 MVP at all. Listing by `status != dismissed` let a
# `submitted` report straight through, which made verification a label on
# something already public rather than the gate it is described as.
#
# `resolved` stays public deliberately: it was verified once, and it reads as
# "Fixed" (client/src/lib/reportStatus.ts). A blowdown someone has since
# cleared is information, not noise.
#
# Closures have always gated their own list this way (app/routers/closures.py
# filters on `moderation_status == verified`); this is reports catching up to
# the queue both features are documented as sharing.
_MODERATED_STATUSES = (ReportStatus.verified, ReportStatus.resolved)


def _visibility_for(report_type: ReportType) -> Visibility:
    # Three audiences, not two. A thanks is club-facing: not a public hazard
    # pin, and not the safety-moderator inbox internal_only means.
    if report_type is ReportType.thanks:
        return Visibility.club_only
    return Visibility.internal_only if report_type in _INTERNAL_ONLY_TYPES else Visibility.public


def _get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Profile | None:
    """Like `get_current_user`, but returns None instead of raising.

    Used by endpoints that work with or without auth (browsing needs no
    account) but still want to know who's asking, if anyone, e.g. so a
    reporter can see their own otherwise-hidden report.
    """
    if credentials is None:
        return None
    try:
        return get_current_user(credentials=credentials, db=db)
    except HTTPException:
        return None


def _already_filed(db: Session, report_id: str, current_user: Profile) -> Report | None:
    """The caller's own report under this id, if it is already stored.

    None means "go ahead and file it". A row belonging to somebody else is
    neither, and raises: returning it would make a guessed id a way to read
    another person's report, and for `bad_hikers` a way to read an incident
    note about a named individual.
    """
    existing = db.get(Report, report_id)
    if existing is None:
        return None

    if existing.reporter_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That report id belongs to someone else.",
        )
    return existing


def _visible_to(report: Report, viewer: Profile | None) -> bool:
    """Whether `viewer` (possibly anonymous) may see `report`.

    The reporter can always see their own report, regardless of visibility
    or status - that is what gives "Waiting" something to appear on while a
    moderator has not looked at it yet. Everyone else only sees reports that
    are public and moderated.

    **A moderator sees any of them, and that is the clause `internal_only`
    was always naming (#385).** Without it this function refused the one
    audience the private routing exists to reach: a `bad_hikers` report is
    `internal_only` and `submitted`, so a maintainer matched neither branch
    above and got a 404 on the photo of the person they were deciding about -
    the same 404 as "no photo", from the one screen built to tell those apart.

    It grants a moderator nothing they were not already being handed.
    `GET /moderation/queue` returns the whole `ReportOut` - note, `photo_url`,
    `reporter_id` - for every submitted report to exactly `MODERATOR_ROLES`,
    and `ReportOut.for_viewer` has spelled privileged as "the reporter, or a
    moderator" since #252. This is the third place that same pair is written,
    and the last one where it was missing.

    What it does widen is `GET /{report_id}`: a moderator can now read a
    report the queue does not list - a dismissed one, a `thanks`, one they
    verified an hour ago. That is deliberate rather than incidental. A
    decision that cannot be looked at again after it is made is a decision
    nobody can review, and the alternative - a second rule that says "in the
    queue" instead of "a moderator" - is the drift this docstring's last
    paragraph exists to warn about.

    Kept in step with the list endpoint's filter by construction: both read
    `_MODERATED_STATUSES`, and `list_reports` composes the same two rules in
    SQL. They disagreed once - the detail endpoint would hand out a
    `submitted` report by id - and a shared constant is what stops that
    being two separate things to remember. `list_reports` deliberately does
    NOT gain the moderator clause: a maintainer browsing the map is a hiker,
    and every unmoderated report on the trail appearing as a pin for them is
    a different feature from the queue, not this one.
    """
    if viewer is not None and (report.reporter_id == viewer.id or viewer.role in MODERATOR_ROLES):
        return True
    return report.visibility == Visibility.public and report.status in _MODERATED_STATUSES


def _credit_for(db: Session, payload: ReportCreate, authored: datetime) -> tuple[str | None, str | None]:
    """Who a thanks is for: what the hiker said, and what location says otherwise.

    **The second half is the resolution `client/src/lib/maintainerLookup.ts`
    has been promising since it was written** - "the authoritative answer is
    worked out server-side when the thanks is finally received, from its
    location and authored date" - and which nothing performed (#249). The
    outbox says the same thing from the other side: `maintainer_id` and
    `club_id` are "both optional... not knowing who to thank is the ordinary
    case, and the server resolves it from location and authored date
    instead". Nothing resolved anything; the two fields were copied out of
    the request and stored.

    So the rule is: **what the hiker named wins, and what they left blank is
    resolved.** Someone who knows the name is the case SAYING_THANKS.md's
    "optionally tagging the maintainer responsible" exists for, and a lookup
    must not overrule them. The two fields resolve independently - naming a
    club without a person is the ordinary way to thank a stretch.

    **On any other type, both are dropped.** They were copied for every type,
    which is the hole `ReportOut` already documents: these are foreign keys to
    real people, so a `blowdown` could arrive carrying any profile id a caller
    cared to name, on a report that is `public`, and `maintainer_id` was a
    second `reporter_id` nobody had noticed. Nothing legitimate sends them -
    the form only offers them on a thanks - so they are ignored rather than
    refused, the same way `ReportCreate` already ignores a submitted
    `visibility`.

    **The authored date, never today's.** A thanks written in June about a
    stretch reassigned in July and synced from an outbox in August belongs to
    June's maintainer; resolving against now would hand a stranger someone
    else's credit and quietly rob the person who earned it
    (SAYING_THANKS.md).

    **Resolved only when the answer is unambiguous, and null is common.**
    Resolution returns zero or more, never exactly one - so a single foreign
    key cannot hold the answer when two stretches overlap, and a null here is
    not a failure to deliver. Delivery is `GET /reports/thanks`, which re-asks
    the same question and reaches every covering maintainer. What these two
    columns record is the narrower thing they can honestly record: who was
    credited when exactly one person, or one club, was.

    A club can be named even where the individual cannot - two assignments
    from the same club overlapping a boundary still say which club the work
    belongs to, which is the club-level default SAYING_THANKS.md describes.
    """
    if payload.type is not ReportType.thanks:
        return None, None

    named_maintainer, named_club = payload.maintainer_id, payload.club_id
    if named_maintainer is not None and named_club is not None:
        return named_maintainer, named_club

    if payload.mile is None:
        # Nothing to resolve against. A thanks with no fix is still a
        # complete thanks - inventing a position for it would credit a
        # volunteer for a stretch nobody said this was about.
        return named_maintainer, named_club

    covering = assignments_covering(db, payload.mile, authored.date())
    maintainers = {assignment.maintainer_id for assignment, _, _ in covering}
    clubs = {assignment.club_id for assignment, _, _ in covering}
    # When the hiker NAMED the maintainer and that person has a covering
    # assignment of their own, the club is THAT assignment's club (#658):
    # resolving the two fields independently credited a named volunteer's
    # thanks to a stranger's club wherever two clubs' stretches overlap.
    # When the named person has no covering assignment, the general
    # resolution below stands - "the half they left blank is still
    # resolved", the reviewed #249 decision the test suite pins: a thanks
    # names a person AND lands on a stretch, and the stretch's club is real
    # information even when it is not the named person's own.
    if named_maintainer is not None:
        own_clubs = {assignment.club_id for assignment, _, _ in covering if assignment.maintainer_id == named_maintainer}
        if own_clubs:
            clubs = own_clubs

    return (
        named_maintainer or (maintainers.pop() if len(maintainers) == 1 else None),
        named_club or (clubs.pop() if len(clubs) == 1 else None),
    )


@router.post("", response_model=ReportOut, status_code=status.HTTP_201_CREATED)
def create_report(
    payload: ReportCreate,
    response: Response,
    current_user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReportOut:
    """Submit a new report. `visibility` and `severity` are never taken
    from the request - `visibility` is derived from `type` here, and
    `severity` stays at the model's `normal` default until a later verify
    action (built elsewhere) can raise it.

    `timestamp` is the moment the report was WRITTEN, which for an
    offline-first app is not the moment it arrived: the client supplies
    `authored_at` when flushing its outbox, and the server falls back to now
    only when it is absent. `received_at` is always server truth.

    **Idempotent on `id` (#243).** Re-sending a report that already arrived
    returns the stored one with `200` instead of filing a second copy, so the
    lost-response case - committed here, connection dropped before the 201,
    client retries - costs a duplicate request rather than a duplicate
    report. `201` still means newly created, which is what lets a test tell
    the two apart; a client only needs to see a 2xx either way.

    A resend is only ever *the same reporter's*. An id that belongs to
    somebody else is refused outright rather than returned, because handing
    back another person's report would turn a guessed UUID into a way to
    read one - and for `bad_hikers`, into a way to read an incident note
    about a named individual.
    """
    # A UUID on the way in (app/schemas/report.py); the column is a String,
    # so it is stored in the one canonical spelling `uuid.UUID` renders -
    # lowercase, hyphenated. Without this, `{ID}` and `{id}` of the same
    # UUID would be two different primary keys and two different reports.
    report_id = str(payload.id) if payload.id is not None else None

    if report_id is not None:
        settled = _already_filed(db, report_id, current_user)
        if settled is not None:
            response.status_code = status.HTTP_200_OK
            return settled

    now = utc_now()
    # Stored naive-UTC throughout (see app/models/profile.py), so an aware
    # value is converted to UTC rather than stored as it arrived.
    authored = to_naive_utc(payload.authored_at)

    timestamp = authored if authored is not None else now
    credited_maintainer, credited_club = _credit_for(db, payload, timestamp)

    report = Report(
        # None lets the model's own default mint one - the same fallback
        # `authored_at` gets from the server clock just below.
        **({"id": report_id} if report_id is not None else {}),
        reporter_id=current_user.id,
        type=payload.type,
        poi_id=payload.poi_id,
        lat=payload.lat,
        lon=payload.lon,
        # Stored as sent, not re-derived: there is no centerline here to
        # re-derive it against (#244). A client that omits it leaves the
        # column null, which is the honest answer for an off-trail fix.
        mile=payload.mile,
        reporter_type=payload.reporter_type,
        note=payload.note,
        photo_url=payload.photo_url,
        visibility=_visibility_for(payload.type),
        maintainer_id=credited_maintainer,
        club_id=credited_club,
        timestamp=timestamp,
        received_at=now,
    )
    db.add(report)
    try:
        return ReportOut.for_viewer(commit_and_refresh(db, report), current_user)
    except IntegrityError as exc:
        # The check above and this insert are two statements, so two
        # concurrent sends of the same id both see "not filed yet" and both
        # insert. That is not a rare interleaving to shrug at - it is
        # precisely what the retry path exists to produce, and losing the
        # race used to surface as a 500 from the one endpoint whose whole
        # promise is that sending twice is safe (#265).
        db.rollback()
        settled = _already_filed(db, report_id, current_user) if report_id is not None else None
        if settled is None:
            # A thanks naming a profile or club that does not exist is the
            # caller's error, not a server fault (#658): the FK violation
            # used to re-raise here as a 500. Named, per field, because
            # "unprocessable" without a field name is a form nobody can fix.
            constraint = str(getattr(exc, "orig", exc))
            for field in ("maintainer_id", "club_id"):
                if field in constraint:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=f"{field} does not name a known {'profile' if field == 'maintainer_id' else 'club'}",
                    ) from exc
            # The conflict was neither the id nor a named credit, so it is
            # not ours to interpret.
            raise
        response.status_code = status.HTTP_200_OK
        return ReportOut.for_viewer(settled, current_user)


@router.get("", response_model=list[ReportOut])
def list_reports(
    db: Session = Depends(get_db),
    current_user: Profile | None = Depends(_get_current_user_optional),
) -> list[ReportOut]:
    """List reports the caller may see: public and moderated, plus their own
    at any status.

    No auth required - browsing needs no account, and an anonymous caller
    gets the public set. A token is read when one is sent, which is what
    lets a reporter see their own report waiting in the queue rather than it
    vanishing from the app between submitting and being verified.
    """
    moderated = and_(Report.visibility == Visibility.public, Report.status.in_(_MODERATED_STATUSES))

    # ORDERED, and by the id rather than by anything meaningful.
    #
    # Unordered, this returned rows in whatever order Postgres happened to
    # scan them, which for a small table is heap order, which is insertion
    # order. The array index was then a covert copy of `received_at` - the
    # field ReportOut withholds - recoverable with `jq 'to_entries'` and no
    # account. Worse, the client outbox flushes strictly serially
    # (client/src/lib/outbox.ts), so one hiker's days-long backlog arrives as
    # consecutive INSERTs and came back as a CONTIGUOUS RUN: adjacent
    # indices, positions advancing along the corridor at walking pace. That
    # is the reporter grouping withholding `reporter_id` was meant to end,
    # rebuilt out of array order.
    #
    # `Report.id` is a random UUID - the client's `crypto.randomUUID()`, or
    # `uuid4()` here - so ordering by it correlates with nothing, which is
    # the entire requirement. Anything meaningful (a date, a mile) would just
    # be a different channel.
    query = db.query(Report).order_by(Report.id)

    if current_user is None:
        rows = query.filter(moderated).all()
    else:
        rows = query.filter(or_(moderated, Report.reporter_id == current_user.id)).all()

    return [ReportOut.for_viewer(row, current_user) for row in rows]


@router.get("/thanks", response_model=list[ReportOut])
def list_my_thanks(
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_user),
) -> list[ReportOut]:
    """Every thanks meant for the caller. **The reader `club_only` never had.**

    A thanks is forced to `visibility = club_only` on create, and that value
    appeared in no query anywhere (#249): the public list excludes it, the
    moderation queue excludes `thanks` deliberately (verify refuses one -
    gratitude has nothing to verify), and nothing else read it. So a thanks
    was readable by exactly one person forever - its own author - which is
    the whole feature not happening. `models/report.py` says `club_only`
    "goes to the club and the maintainer"; this is the half that delivers.

    **Three ways to be a recipient, and the third is the one that matters.**

    1. Named directly. A hiker who knew the name tagged it.
    2. Addressed to a club the caller CURRENTLY holds an assignment for.
       Club-level is SAYING_THANKS.md's default, and the common case - the
       hiker knew the stretch, not the person. "Currently" is load-bearing
       (#642): this clause used to match every club the caller had EVER held
       an assignment for, which delivered club mail to people years out of
       the club. Leaving the club ends the subscription; a thanks for the
       caller's own work still arrives through 1 and 3, which do not expire.
    3. Written at a mile inside one of the caller's own assignments, on a
       date that assignment was effective.

    Three exists because resolution "returns zero or more, never exactly
    one". Where two stretches overlap, `report.maintainer_id` is null - one
    foreign key cannot name two people - and delivery by that column alone
    would silently drop both recipients in exactly the case the design calls
    normal. Re-asking the question at read time reaches both.

    **The assignment's own dates, against the report's AUTHORED time.** A
    thanks written in June about a stretch reassigned in July belongs to
    June's maintainer even when it syncs in August, so a maintainer who took
    the section over in July does not inherit it - and the one who did the
    work still sees it after handing off. Same rule as resolution, from the
    other end.

    Auth required and no role gate: holding an assignment is what makes
    somebody a recipient, and a `club_admin` with no assignment is not one.
    A hiker with no assignments gets an empty list, which is the true answer
    rather than a 403 about a resource that concerns them not at all.
    """
    mine = db.query(MaintainerAssignment).filter(MaintainerAssignment.maintainer_id == current_user.id).all()

    # Named directly. Stands alone: somebody can be thanked by name without
    # holding any assignment at all - a maintainer between sections, or one
    # whose club has not been loaded into the table yet.
    recipient = [Report.maintainer_id == current_user.id]

    # Club membership is judged now, not ever (#642). The stretch clause
    # below judges by the report's authored time because the work has a date;
    # being in the club is a standing relationship, and it stands or it
    # doesn't. utc_now() rather than date.today(): the assignment dates are
    # club records kept in trail-local terms, but the server's own idea of
    # "today" should not move with whatever timezone the host happens to run in.
    today = utc_now().date()
    clubs = {
        assignment.club_id
        for assignment in mine
        if assignment.effective_from <= today and (assignment.effective_to is None or today <= assignment.effective_to)
    }
    if clubs:
        recipient.append(Report.club_id.in_(clubs))

    for assignment in mine:
        # Half-open on the upper end rather than `<= effective_to`, because
        # `timestamp` is a moment and `effective_to` is a whole day: a thanks
        # written at 14:00 on a maintainer's last day is theirs.
        covers = [
            Report.mile.is_not(None),
            Report.mile >= assignment.start_mile,
            Report.mile <= assignment.end_mile,
            Report.timestamp >= datetime.combine(assignment.effective_from, time.min),
        ]
        if assignment.effective_to is not None:
            covers.append(Report.timestamp < datetime.combine(assignment.effective_to + timedelta(days=1), time.min))
        recipient.append(and_(*covers))

    rows = (
        db.query(Report)
        # Dismissal is the abuse-removal path - the one moderation action a
        # thanks can receive - and this inbox is the only surface a thanks is
        # delivered to. Without this filter the removal removed it from
        # nowhere: the target kept reading it, newest-first, forever (#642).
        .filter(
            Report.type == ReportType.thanks,
            Report.status != ReportStatus.dismissed,
            or_(*recipient),
        )
        # Newest first: this is an inbox, and the useful end of one is the
        # end that just arrived.
        .order_by(Report.timestamp.desc())
        .all()
    )

    return [ReportOut.for_viewer(row, current_user) for row in rows]


@router.get("/{report_id}", response_model=ReportOut)
def get_report(
    report_id: str,
    db: Session = Depends(get_db),
    current_user: Profile | None = Depends(_get_current_user_optional),
) -> ReportOut:
    """Return a single report, with the same visibility filtering as the
    list endpoint - except the reporter can always see their own report."""
    report = db.get(Report, report_id)
    if report is None or not _visible_to(report, current_user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    return ReportOut.for_viewer(report, current_user)


def _too_large() -> HTTPException:
    # The client downscales before uploading (#234), so this is the guard for
    # one that did not - a full-size phone photo is several MB, and egress is
    # the cost R2 was chosen to keep flat.
    return HTTPException(
        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        detail="Photo is too large; it should be downscaled before upload.",
    )


async def read_capped_body(request: Request, limit: int) -> bytes:
    """Read a request body, refusing it the moment it grows past `limit`.

    `await request.body()` buffers the whole stream and lets the caller measure
    afterwards, which makes a size limit into an accounting exercise: a 500 MB
    upload is a 500 MB allocation followed by a polite 413, and the server has
    already paid the cost the limit exists to avoid. Nothing upstream catches
    it either - backend/Dockerfile runs uvicorn with no `--limit-*` flag,
    uvicorn has no default body cap, and there is no proxy in front holding a
    `client_max_body_size` (#379).

    `Content-Length` is consulted first because refusing before reading a byte
    is strictly cheaper, but it is only ever an optimisation: the header is a
    claim, a chunked request omits it entirely, and neither case is allowed to
    decide anything on its own. The running total over `request.stream()` is
    what actually enforces the limit, so a body that lies about being small is
    still cut off `limit` bytes into arriving.
    """
    declared = request.headers.get("content-length")
    if declared is not None:
        try:
            promised = int(declared)
        except ValueError:
            # An unparseable header decides nothing; the stream below still does.
            promised = None
        if promised is not None and promised > limit:
            raise _too_large()

    chunks: list[bytes] = []
    received = 0
    async for chunk in request.stream():
        received += len(chunk)
        if received > limit:
            raise _too_large()
        chunks.append(chunk)
    return b"".join(chunks)


@router.put(
    "/{report_id}/photo",
    response_model=ReportOut,
    summary="Attach a photo to a report you filed",
)
async def upload_report_photo(
    report_id: str,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    current_user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReportOut:
    """Store the photo for an existing report and record its key (#234).

    **After the report, not before, and that ordering is the design.** The key
    is derived from the report id, so an upload could in principle happen
    first - but nothing could then check who is allowed to make it, or whether
    the id belongs to a report at all. Requiring the row means every upload is
    attributable and every stored object has a reason to exist. The client's
    outbox already flushes in order, and `POST /reports` is idempotent on the
    same id (#243), so a retry of either half is safe.

    **Owner only.** A photo is evidence attached to somebody's account, and
    `bad_hikers` photos are photos of people - letting a second account attach
    one to a report it did not file would put an image under a stranger's name
    in a queue that treats attribution as meaningful.

    The body is the image itself rather than a multipart form: the client has
    bytes in hand after downscaling and stripping EXIF, and a form part would
    be a wrapper around the same bytes with a filename nobody reads.

    Returns the report, with `photo_url` now holding the object KEY - not a
    URL. See app/core/photos.py for why, and for why the object is private:
    the bucket answers nobody directly, and reading a photo goes through
    `GET /reports/{id}/photo` below, which checks the report's own visibility
    and status first. Nothing here makes a photo reachable.
    """
    if not photo_uploads_enabled():
        # 503 rather than 500: nothing is broken, this deployment simply has
        # no bucket - which is true of every developer machine. The client
        # keeps the photo queued rather than discarding it as rejected.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Photo uploads are not configured on this server.",
        )

    report = get_or_404(db, Report, report_id, detail="Report not found")
    if report.reporter_id != current_user.id:
        # 404, not 403: a report that is not yours is one you have no business
        # knowing exists, and distinguishing "wrong owner" from "no such id"
        # turns a guessed UUID into a way to confirm one - the same reasoning
        # create_report applies to a resend under someone else's id.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    content_type = (request.headers.get("content-type") or "").split(";")[0].strip()
    if content_type != ALLOWED_CONTENT_TYPE:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Report photos must be {ALLOWED_CONTENT_TYPE}.",
        )

    body = await read_capped_body(request, MAX_PHOTO_BYTES)
    if not body:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No photo in the request body.")
    if not body.startswith(JPEG_MAGIC):
        # The `Content-Type` checked above is the sender describing their own
        # bytes. This is the bytes. They disagree exactly when it matters:
        # the object is stored as `.jpg` with `ContentType: image/jpeg` set by
        # us, and served back under that label to a browser (#379).
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Report photos must be {ALLOWED_CONTENT_TYPE}.",
        )

    try:
        key = store_photo(report.id, body)
    except PhotoStorageUnavailable as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error

    # The row last, and only once the object is really there: the report is
    # the authoritative half, so a `photo_url` pointing at nothing would be
    # the one direction of drift this design refuses (app/core/photos.py).
    report.photo_url = key
    return ReportOut.for_viewer(commit_and_refresh(db, report), current_user)


def _authorised_photo_url(report_id: str, db: Session, viewer: Profile | None) -> str:
    """A signed URL for a report's photo, or the HTTPException that refuses it.

    **The whole check, in one place, because two endpoints hand out the same
    capability** (#385) - the redirect below and the JSON link after it. A
    signed URL is a bearer token for the object, so a second copy of these
    four lines is a second place for the `internal_only` rule to drift, and
    the rule that drifts is the one deciding who sees a photo of a person.
    That is the same argument app/core/photos.py makes for not writing
    `_visible_to` again inside a Cloudflare Worker.

    **404 for everything it refuses**, uniformly: no such report, a report
    somebody else may not see, and a report with no photo all answer the same
    way. A distinct 403 would confirm that an id names a real report to
    somebody who may not read it, which for `bad_hikers` is confirmation that
    an incident note about a named individual exists.
    """
    if not photo_storage_configured():
        # 503 rather than 404: there is no bucket on this deployment, which is
        # not the same as this report having no photo, and a client that is
        # told "not found" would stop asking.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Report photos are not configured on this server.",
        )

    report = db.get(Report, report_id)
    if report is None or not _visible_to(report, viewer) or report.photo_url is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report photo not found")

    try:
        return presigned_photo_url(report.id)
    except PhotoStorageUnavailable as error:  # pragma: no cover - guarded above
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error


@router.get(
    "/{report_id}/photo/link",
    response_model=ReportPhotoLink,
    summary="Ask for a report's photo URL, if you may see the report",
    responses={
        404: {"description": "No such report, no photo on it, or not one you may see."},
        503: {"description": "This deployment has no photo bucket configured."},
    },
)
def get_report_photo_link(
    report_id: str,
    response: Response,
    db: Session = Depends(get_db),
    current_user: Profile | None = Depends(_get_current_user_optional),
) -> ReportPhotoLink:
    """The same photo as below, handed back as a URL instead of a redirect (#385).

    **This exists because an `<img>` cannot carry a token.** The endpoint
    below uses optional auth, so an anonymous `<img src>` gets the *public*
    answer - which is a 404 for an `internal_only` `bad_hikers` photo, and a
    404 renders as a broken image indistinguishable from a report with no
    photo at all. A moderator deciding whether to escalate an incident note
    about a person could not tell "there is no evidence" from "there is
    evidence and you are not being shown it".

    So the token travels on this call, where a `fetch` can put it, and the
    URL it answers with goes straight into `<img src>`. Images are exempt
    from CORS, so the private photo bucket needs no CORS policy - the
    property LAUNCH_CHECKLIST 1.7 built it with. Fetching the bytes
    cross-origin instead would have needed one, on the one bucket whose whole
    design is that nothing reaches it without a check.

    **A separate path rather than `Accept: application/json` on the one
    below**, which was the open question in #385. Content negotiation has to
    pick a default for `*/*`, and the default has to stay the redirect -
    which leaves the form the moderation screen depends on reachable only by
    a client that sets the header exactly, and silently wrong for any proxy
    that normalises it. Two paths are also two lines in a log that say which
    one happened. The cost is that one resource has two URLs; that is the
    cheaper of the two mistakes.

    **The TTL is unchanged, and that is the decision rather than an
    oversight** (#385 asked). A queue left open for an hour outlives a
    five-minute URL, and the fix for that is the client asking again - which
    costs one request against a check that has to run every time anyway - not
    a longer-lived bearer token for a photo of a person. `expires_in` is
    returned so the client can re-ask on a number from here rather than one
    it hardcoded.

    Everything else - who may see it, what it refuses, and how uniformly -
    is `_authorised_photo_url` above, shared with the redirect.
    """
    url = _authorised_photo_url(report_id, db, current_user)

    # Same reasoning as the redirect's `no-store`, and it matters more here:
    # this response body IS the bearer token, where the redirect at least
    # kept it in a header. A cache holding it outlives the signature and the
    # visibility decision both.
    response.headers["Cache-Control"] = "private, no-store, max-age=0"
    return ReportPhotoLink(url=url, expires_in=PHOTO_URL_TTL_SECONDS)


@router.get(
    "/{report_id}/photo",
    response_class=RedirectResponse,
    status_code=status.HTTP_302_FOUND,
    summary="Fetch a report's photo, if you may see the report",
    responses={
        302: {"description": "Redirect to a short-lived signed URL for the image."},
        404: {"description": "No such report, no photo on it, or not one you may see."},
        503: {"description": "This deployment has no photo bucket configured."},
    },
)
def get_report_photo(
    report_id: str,
    db: Session = Depends(get_db),
    current_user: Profile | None = Depends(_get_current_user_optional),
) -> RedirectResponse:
    """Serve a report's photo, behind the report's own visibility (#234).

    **The photo inherits the report's audience, and that is the whole reason
    this endpoint exists rather than a public bucket URL.** `bad_hikers` is
    `internal_only` and those are photos of people; `thanks` is `club_only`;
    and every type is attached at create time, before a moderator has looked -
    which #229 established is not publicly visible. A world-readable object
    would publish the image while the report stayed private, undoing the
    routing one layer down. So the answer comes from `_visible_to`, the same
    function `GET /{report_id}` uses, rather than a second copy of the rule -
    reached through `_authorised_photo_url`, which the link endpoint above
    shares so there is one check and not two.

    **A redirect, not the bytes.** R2 serves the object directly from a signed
    URL that lasts minutes, so the image never crosses this backend - egress
    stays free, which is the reason R2 was chosen (#234). app/core/photos.py
    has the full trade, including what a bearer URL costs and why #234's
    Cloudflare Worker is not what got built.

    **Still here, and still the default.** The link form above was added for
    the one caller that cannot follow a hop while carrying a token (#385);
    anything that can follow one should use this, which is every `<img>`
    pointed at a public report and every `curl -L`.
    """
    signed = _authorised_photo_url(report_id, db, current_user)

    response = RedirectResponse(signed, status_code=status.HTTP_302_FOUND)
    # The redirect must not be cached, and this is load-bearing rather than
    # hygiene. A cached 302 outlives two things at once: the signature, so the
    # image breaks once it expires - and the visibility decision, so a report
    # dismissed or made private an hour from now would still be reachable from
    # whatever cached the hop. Re-asking is cheap; the check has to run every
    # time for the answer to mean anything.
    response.headers["Cache-Control"] = "private, no-store, max-age=0"
    return response
