"""`/reports` endpoints - community condition reports.

See ../../../features/REPORT_A_PROBLEM.md. Browsing (`GET`) needs no
account, matching every other browsing endpoint in this app; submitting
(`POST`) requires a real identity so a report has a reporter to attribute
it to and, later, moderate against.
"""

from datetime import timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import and_, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import bearer_scheme, get_current_user
from app.core.orm import commit_and_refresh
from app.core.photo_storage import (
    MAX_PHOTO_BYTES,
    PhotoStorageUnavailable,
    photo_rejection,
    store_photo,
)
from app.core.time import utc_now
from app.db.session import get_db
from app.models.profile import Profile
from app.models.report import Report, ReportStatus, ReportType, Visibility
from app.schemas.report import ReportCreate, ReportOut

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

    Kept in step with the list endpoint's filter by construction: both read
    `_MODERATED_STATUSES`, and `list_reports` composes the same two rules in
    SQL. They disagreed once - the detail endpoint would hand out a
    `submitted` report by id - and a shared constant is what stops that
    being two separate things to remember.
    """
    if viewer is not None and report.reporter_id == viewer.id:
        return True
    return report.visibility == Visibility.public and report.status in _MODERATED_STATUSES


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
    authored = payload.authored_at
    if authored is not None and authored.tzinfo is not None:
        # Stored naive-UTC throughout (see app/models/profile.py), so an
        # aware value is converted to UTC rather than stored as it arrived.
        authored = authored.astimezone(timezone.utc).replace(tzinfo=None)

    report = Report(
        # None lets the model's own default mint one - the same fallback
        # `authored_at` gets from the server clock just below.
        **({"id": report_id} if report_id is not None else {}),
        reporter_id=current_user.id,
        type=payload.type,
        poi_id=payload.poi_id,
        lat=payload.lat,
        lon=payload.lon,
        reporter_type=payload.reporter_type,
        note=payload.note,
        photo_url=payload.photo_url,
        visibility=_visibility_for(payload.type),
        maintainer_id=payload.maintainer_id,
        club_id=payload.club_id,
        timestamp=authored if authored is not None else now,
        received_at=now,
    )
    db.add(report)
    try:
        return ReportOut.for_viewer(commit_and_refresh(db, report), current_user)
    except IntegrityError:
        # The check above and this insert are two statements, so two
        # concurrent sends of the same id both see "not filed yet" and both
        # insert. That is not a rare interleaving to shrug at - it is
        # precisely what the retry path exists to produce, and losing the
        # race used to surface as a 500 from the one endpoint whose whole
        # promise is that sending twice is safe (#265).
        db.rollback()
        settled = _already_filed(db, report_id, current_user) if report_id is not None else None
        if settled is None:
            # The conflict was not the id, so it is not ours to interpret.
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


@router.put("/{report_id}/photo", response_model=ReportOut)
async def upload_report_photo(
    report_id: str,
    request: Request,
    current_user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReportOut:
    """Attach a JPEG to a report you filed. Part 1 of #234.

    **After the report exists, never before.** A derived key makes
    upload-before-create possible and it is still the wrong order: nothing
    could check who is allowed to upload, or whether the id names a report at
    all. The outbox flushes in order and `POST /reports` is idempotent on the
    same id (#243), so a retry of either half is safe.

    **A report that is not yours is a 404, not a 403** - the same call
    `_already_filed` makes above, for the same reason. Distinguishing "wrong
    owner" from "no such id" turns a guessed UUID into a way to confirm one,
    and for `bad_hikers` into a way to confirm that an incident note about a
    named individual exists. A moderator is no exception here: reading a
    photo is part 2's business, and this endpoint only ever writes the
    caller's own.

    **The body is the photo**, sent as `image/jpeg` - not multipart. One file
    to one URL is what PUT is for, and a form wrapper would buy nothing but a
    dependency.

    Nothing can read the result yet: the bucket is private and the Worker
    that checks `visibility` and `status` before streaming is part 2. A photo
    uploaded today is stored and unreachable, which is deliberate - the
    alternative is a readable photo whose report is still unmoderated.
    """
    report = db.get(Report, report_id)
    if report is None or report.reporter_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    # Refused before the body is read, when the client says how big it is.
    # Reading first and checking after would buffer the whole upload to reject
    # it, which is the shape that makes a size limit useless against the
    # traffic it exists to stop.
    declared = request.headers.get("content-length")
    if declared is not None and declared.isdigit() and int(declared) > MAX_PHOTO_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"That photo is larger than {MAX_PHOTO_BYTES // (1024 * 1024)} MB.",
        )

    data = await request.body()

    # And again on what actually arrived. The header above is a claim; this is
    # the measurement, and it is the one that decides.
    rejection = photo_rejection(data)
    if rejection is not None:
        status_code = (
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE if len(data) > MAX_PHOTO_BYTES else status.HTTP_422_UNPROCESSABLE_ENTITY
        )
        raise HTTPException(status_code=status_code, detail=rejection)

    try:
        key = store_photo(report.id, data)
    except PhotoStorageUnavailable as unavailable:
        # 503, not 500 or 422: nothing was attempted and nothing is wrong with
        # the photo, so a client should keep it and retry rather than mark it
        # permanently refused. lib/api.ts's `permanentFailureReason` allow-lists
        # only 409 and 422 as permanent for exactly this reason - a 503 leaves
        # the report in the outbox where it belongs.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(unavailable),
        ) from unavailable

    # The key, not a URL. A full URL would bake today's bucket domain into
    # every row permanently (#234).
    report.photo_url = key
    return ReportOut.for_viewer(commit_and_refresh(db, report), current_user)
