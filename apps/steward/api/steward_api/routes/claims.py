"""Claims: a volunteer takes a site for 14 days, brings a crew, photographs it
before and after, and someone off the crew verifies it (PLAN.md §6, #1910).

    claimed ──first before photo──► in_progress ──submit──► submitted ──verify──► verified
       │                                │                       ├──send back──► in_progress
       └──── release, or due_at passes ─┴──► released ◄──reject──┘

The clock is due_at. It stops at submitted, so a slow reviewer never costs a
crew its claim. A send-back restarts it with whatever the crew had left when
they submitted, and at least limits.SEND_BACK_DAYS; the after photos must then
be retaken. A reject releases the site: the work was not done, and someone else
may claim it. Running out is not a scheduled job: every request that reads
claims first releases the ones past due (release_overdue), so a released claim
is never shown as live.

Only sites the latest analysis says need work may be claimed (analysis.py),
and an account holds at most limits.LIVE_CLAIMS_PER_USER sites at once,
counting the ones it has submitted and that wait for review. Before the
adversarial review (2026-10-27, finding 2) one account could hold any number:
the cap counted only open claims, any string could be claimed, and a
send-back could be resubmitted at once with the same photos.

Who may do what:
- anyone signed in: claim an open site, read any claim, review a submitted
  claim they are not crew on (verify, send back, or reject);
- the crew (the claimer and whoever joined by invite link): photograph,
  log their own hours, submit, make an invite link;
- the claimer: release.
"""

from __future__ import annotations

import asyncio
import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Path, Query, Request, Response, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from steward_api import limits
from steward_api.analysis import AnalysisUnavailable
from steward_api.auth import current_user
from steward_api.db import get_db
from steward_api.locks import lock_user
from steward_api.models import HOLDING_STATES, Claim, ClaimMember, Hours, Photo, StewardUser
from steward_api.photos import NOT_SET_UP, PhotoStorageUnavailable, PhotoStore, UnusablePhoto, photo_key, reencode
from steward_api.schemas import (
    ClaimCreate,
    ClaimDetail,
    ClaimSummary,
    CrewMember,
    HoursEntry,
    HoursTotals,
    InviteLink,
    JoinClaim,
    PhotoView,
    Review,
    Submission,
)

router = APIRouter(tags=["claims"])

#: The states in which the crew can still work on a claim.
WORKING_STATES = ("claimed", "in_progress")


def _now() -> datetime:
    return datetime.now(UTC)


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def release_overdue(db: Session) -> None:
    """Release every working claim whose clock has run out. Idempotent and cheap:
    one UPDATE on an indexed state, run before anything reads claims."""
    db.execute(
        update(Claim)
        .where(Claim.state.in_(WORKING_STATES), Claim.due_at < func.now())
        .values(state="released", released_at=Claim.due_at, invite_token_sha256=None)
    )
    db.commit()


def _names(db: Session, ids: set[str]) -> dict[str, str | None]:
    if not ids:
        return {}
    return dict(db.execute(select(StewardUser.id, StewardUser.display_name).where(StewardUser.id.in_(ids))).all())


def _crew_ids(claim: Claim) -> set[str]:
    """The crew as it is now: who may work on the claim, and who is listed."""
    return {member.user_id for member in claim.members if member.left_at is None}


def _ever_crew_ids(claim: Claim) -> set[str]:
    """Everyone who has been on the crew, including places left by deleting
    one's data: none of them may review the claim."""
    return {member.user_id for member in claim.members}


def _summary(claim: Claim, user: StewardUser, names: dict[str, str | None]) -> ClaimSummary:
    return ClaimSummary(
        id=claim.id,
        rims_id=claim.rims_id,
        state=claim.state,
        claimed_at=claim.claimed_at,
        due_at=claim.due_at,
        submitted_at=claim.submitted_at,
        claimer=names.get(claim.claimer_id) if claim.claimer_id else None,
        crew_size=len(_crew_ids(claim)),
        you_are_crew=user.id in _crew_ids(claim),
    )


def _detail(claim: Claim, user: StewardUser, db: Session, store: PhotoStore | None) -> ClaimDetail:
    crew = _crew_ids(claim)
    names = _names(db, crew | ({claim.claimer_id} if claim.claimer_id else set()))
    hours = {h.user_id: h.tenths / 10 for h in claim.hours}
    photos: list[PhotoView] = []
    if store is not None:
        try:
            photos = [
                PhotoView(
                    id=p.id, phase=p.phase, point=p.point, url=store.url(photo_key(claim.id, p.id)), created_at=p.created_at
                )
                for p in claim.photos
            ]
        except PhotoStorageUnavailable:
            photos = []
    return ClaimDetail(
        **_summary(claim, user, names).model_dump(),
        started_at=claim.started_at,
        sent_back_at=claim.sent_back_at,
        verified_at=claim.verified_at,
        released_at=claim.released_at,
        steps_done=list(claim.steps_done or []),
        notes=claim.notes,
        review_note=claim.review_note,
        reviewed_by=claim.reviewed_by_name,
        crew=[
            CrewMember(name=names.get(m.user_id), you=m.user_id == user.id, hours=hours.get(m.user_id))
            for m in claim.members
            if m.left_at is None
        ],
        photos=photos,
        you_may_review=claim.state == "submitted" and user.id not in _ever_crew_ids(claim),
    )


def _claim(db: Session, claim_id: uuid.UUID) -> Claim:
    claim = db.get(Claim, claim_id)
    if claim is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such claim")
    return claim


def _crew_claim(db: Session, claim_id: uuid.UUID, user: StewardUser, states: tuple[str, ...] = WORKING_STATES) -> Claim:
    claim = _claim(db, claim_id)
    if user.id not in _crew_ids(claim):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only this claim's crew can do that")
    if claim.state not in states:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"This claim is {claim.state.replace('_', ' ')}, so that cannot be done now"
        )
    return claim


def _store(request: Request) -> PhotoStore:
    store: PhotoStore | None = request.app.state.photos
    if store is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, NOT_SET_UP)
    return store


# --- Claiming ---------------------------------------------------------------------


@router.post("/claims", response_model=list[ClaimSummary], status_code=status.HTTP_201_CREATED)
def claim_sites(
    body: ClaimCreate, request: Request, user: StewardUser = Depends(current_user), db: Session = Depends(get_db)
) -> list[ClaimSummary]:
    """Claim one site, or several at once (a site and its cluster). All or none:
    if any of them is already held, or is not one the analysis says needs work,
    nothing is claimed and the answer says which."""
    sites = list(dict.fromkeys(body.rims_ids))
    try:
        workable = request.app.state.analysis.current().workable
    except AnalysisUnavailable as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "The site list cannot be read right now, so no claim can be checked"
        ) from exc
    not_work = [rims_id for rims_id in sites if rims_id not in workable]
    if not_work:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, f"Not a site the latest analysis says needs work: {', '.join(not_work)}"
        )
    release_overdue(db)
    lock_user(db, user.id)
    rejected = db.scalars(
        select(Claim.rims_id).where(
            Claim.rims_id.in_(sites),
            Claim.rejected_by == user.id,
            Claim.released_at > _now() - timedelta(days=limits.REJECTER_WAIT_DAYS),
        )
    ).all()
    if rejected:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"You rejected the last claim on {', '.join(sorted(set(rejected)))}, so someone else gets the next "
            f"{limits.REJECTER_WAIT_DAYS} days to claim it",
        )
    # Places left by deleting one's data do not count: that account starts
    # empty (routes/me.delete_me), as a second address would anyway.
    held_by_you = db.scalar(
        select(func.count())
        .select_from(Claim)
        .join(ClaimMember, ClaimMember.claim_id == Claim.id)
        .where(ClaimMember.user_id == user.id, ClaimMember.left_at.is_(None), Claim.state.in_(HOLDING_STATES))
    )
    if (held_by_you or 0) + len(sites) > limits.LIVE_CLAIMS_PER_USER:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"One account holds at most {limits.LIVE_CLAIMS_PER_USER} sites at a time, counting ones waiting for review",
        )
    held = db.scalars(select(Claim.rims_id).where(Claim.rims_id.in_(sites), Claim.state.in_(HOLDING_STATES))).all()
    if held:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Already claimed: {', '.join(sorted(held))}")
    now = _now()
    claims = []
    for rims_id in sites:
        claim = Claim(
            rims_id=rims_id, claimer_id=user.id, state="claimed", claimed_at=now, due_at=now + timedelta(days=limits.CLAIM_DAYS)
        )
        claim.members = [ClaimMember(user_id=user.id)]
        db.add(claim)
        claims.append(claim)
    try:
        db.commit()
    except IntegrityError as exc:
        # Someone else claimed one of them between the check and the insert;
        # the partial unique index refused it.
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Someone claimed one of these sites a moment ago") from exc
    names = {user.id: user.display_name}
    return [_summary(claim, user, names) for claim in claims]


@router.get("/claims/site/{rims_id}", response_model=ClaimSummary | None)
def claim_for_site(
    rims_id: str = Path(pattern=limits.RIMS_ID_PATTERN), user: StewardUser = Depends(current_user), db: Session = Depends(get_db)
) -> ClaimSummary | None:
    """The claim holding a site now, or null when it is open."""
    release_overdue(db)
    claim = db.scalars(select(Claim).where(Claim.rims_id == rims_id, Claim.state.in_(HOLDING_STATES))).first()
    if claim is None:
        return None
    return _summary(claim, user, _names(db, {claim.claimer_id} if claim.claimer_id else set()))


@router.get("/claims/mine", response_model=list[ClaimSummary])
def my_claims(user: StewardUser = Depends(current_user), db: Session = Depends(get_db)) -> list[ClaimSummary]:
    release_overdue(db)
    claims = db.scalars(
        select(Claim)
        .join(ClaimMember, ClaimMember.claim_id == Claim.id)
        .where(ClaimMember.user_id == user.id, ClaimMember.left_at.is_(None))
        .order_by(Claim.claimed_at.desc())
        .limit(100)
    ).all()
    names = _names(db, {c.claimer_id for c in claims if c.claimer_id})
    return [_summary(claim, user, names) for claim in claims]


@router.get("/claims/{claim_id}", response_model=ClaimDetail)
def read_claim(
    claim_id: uuid.UUID, request: Request, user: StewardUser = Depends(current_user), db: Session = Depends(get_db)
) -> ClaimDetail:
    release_overdue(db)
    return _detail(_claim(db, claim_id), user, db, request.app.state.photos)


@router.post("/claims/{claim_id}/release", response_model=ClaimDetail)
def release_claim(
    claim_id: uuid.UUID, request: Request, user: StewardUser = Depends(current_user), db: Session = Depends(get_db)
) -> ClaimDetail:
    release_overdue(db)
    claim = _crew_claim(db, claim_id, user)
    if claim.claimer_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the person who claimed the site can release it")
    claim.state = "released"
    claim.released_at = _now()
    claim.invite_token_sha256 = None
    db.commit()
    return _detail(claim, user, db, request.app.state.photos)


# --- The crew ---------------------------------------------------------------------


@router.post("/claims/{claim_id}/invite", response_model=InviteLink)
def invite(claim_id: uuid.UUID, user: StewardUser = Depends(current_user), db: Session = Depends(get_db)) -> InviteLink:
    """A crew invite link, replacing any earlier one. Usable by anyone signed in
    while the claim is being worked on and the crew has room."""
    release_overdue(db)
    claim = _crew_claim(db, claim_id, user)
    token = secrets.token_urlsafe(24)
    claim.invite_token_sha256 = _hash(token)
    db.commit()
    return InviteLink(token=token)


@router.post("/claims/join", response_model=ClaimSummary)
def join(body: JoinClaim, user: StewardUser = Depends(current_user), db: Session = Depends(get_db)) -> ClaimSummary:
    release_overdue(db)
    claim = db.scalars(select(Claim).where(Claim.invite_token_sha256 == _hash(body.token)).with_for_update()).first()
    if claim is None or claim.state not in WORKING_STATES:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This invite is not valid any more. Ask the crew for a new one.")
    if user.id not in _crew_ids(claim):
        if len(_crew_ids(claim)) >= limits.CREW_MAX:
            raise HTTPException(status.HTTP_409_CONFLICT, f"This crew is full at {limits.CREW_MAX}")
        left = next((m for m in claim.members if m.user_id == user.id), None)
        if left is not None:
            # Someone who deleted their data and was invited back.
            left.left_at = None
        else:
            claim.members.append(ClaimMember(user_id=user.id))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
        db.refresh(claim)
    return _summary(claim, user, _names(db, {claim.claimer_id} if claim.claimer_id else set()))


# --- Photos -----------------------------------------------------------------------


@router.post("/claims/{claim_id}/photos", response_model=ClaimDetail, status_code=status.HTTP_201_CREATED)
async def upload_photo(
    claim_id: uuid.UUID,
    request: Request,
    response: Response,
    phase: str = Query(pattern="^(before|after|extra)$"),
    point: int | None = Query(default=None),
    client_id: str | None = Query(default=None, pattern=limits.CLIENT_ID_PATTERN),
    user: StewardUser = Depends(current_user),
) -> ClaimDetail:
    """The photo is the raw request body. One before and one after per photo
    point (a new one replaces the old), and any number of extras up to the cap.
    The first before photo moves a claim from claimed to in progress.

    `client_id` is the phone's own id for a photo it queued with no signal.
    A photo already on the claim under that id is not stored again: the
    answer is the claim as it stands, with 200 rather than 201. Without it, a
    response lost after the photo was stored sent the photo a second time,
    and extras piled up toward the cap (the third pass's P2, 2026-10-27).

    In this order, each step holding nothing the next does not need (the
    adversarial review's finding 1, 2026-10-27): the caller is checked against
    the claim before a byte of body is read; the body is read with no database
    connection held, cut off after PHOTO_IDLE_SECONDS without a byte or
    PHOTO_READ_SECONDS in all; it is re-encoded in a worker thread; it is
    written to R2 outside any transaction; and only then is the row written,
    after checking the claim again, since it may have changed meanwhile."""
    store = _store(request)
    if (phase == "extra") != (point is None) or (point is not None and point not in limits.PHOTO_POINTS):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "A before or after photo needs photo point 1 or 2; an extra needs none"
        )
    already = await run_in_threadpool(_check_upload, request.app, store, user, claim_id, client_id)
    body = bytearray()
    try:
        async with asyncio.timeout(limits.PHOTO_READ_SECONDS):
            chunks = request.stream().__aiter__()
            while True:
                try:
                    chunk = await asyncio.wait_for(chunks.__anext__(), limits.PHOTO_IDLE_SECONDS)
                except StopAsyncIteration:
                    break
                body.extend(chunk)
                if len(body) > limits.PHOTO_MAX_BYTES:
                    raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "That photo is too large")
    except TimeoutError as exc:
        raise HTTPException(
            status.HTTP_408_REQUEST_TIMEOUT, "The photo took too long to arrive. Try again with a better signal."
        ) from exc
    if already is not None:
        # Read in full all the same, so the phone gets its answer on a
        # connection that finished cleanly rather than one cut off mid-send.
        response.status_code = status.HTTP_200_OK
        return already
    try:
        jpeg = await run_in_threadpool(reencode, bytes(body))
    except UnusablePhoto as exc:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, str(exc)) from exc
    return await run_in_threadpool(_store_photo, request.app, store, user, claim_id, phase, point, client_id, jpeg)


def _sent_before(claim: Claim, user: StewardUser, client_id: str | None) -> bool:
    """This crew member's phone already delivered this photo. Asked before the
    claim's state: a photo that arrived before the claim was submitted is
    still there afterwards, and the phone should hear that, not a refusal."""
    return client_id is not None and user.id in _crew_ids(claim) and any(photo.client_id == client_id for photo in claim.photos)


def _check_upload(
    app: FastAPI, store: PhotoStore, user: StewardUser, claim_id: uuid.UUID, client_id: str | None
) -> ClaimDetail | None:
    """Refuses an upload that could not be kept, before its body is read.
    Returns the claim instead when this photo is already on it."""
    with app.state.sessionmaker() as db:
        release_overdue(db)
        claim = _claim(db, claim_id)
        if _sent_before(claim, user, client_id):
            return _detail(claim, user, db, store)
        claim = _crew_claim(db, claim_id, user)
        if len(claim.photos) >= limits.PHOTOS_PER_CLAIM:
            raise HTTPException(status.HTTP_409_CONFLICT, f"A claim holds at most {limits.PHOTOS_PER_CLAIM} photos")
        return None


def _store_photo(
    app: FastAPI,
    store: PhotoStore,
    user: StewardUser,
    claim_id: uuid.UUID,
    phase: str,
    point: int | None,
    client_id: str | None,
    jpeg: bytes,
) -> ClaimDetail:
    photo_id = uuid.uuid4()
    key = photo_key(claim_id, photo_id)
    # Object first, with no transaction open: R2 can take seconds, and a row
    # whose object failed to write would show a photo that is not there.
    try:
        store.put(key, jpeg, "image/jpeg")
    except PhotoStorageUnavailable as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    with app.state.sessionmaker() as db:
        try:
            release_overdue(db)
            claim = db.get(Claim, claim_id, with_for_update=True)
            if claim is not None and _sent_before(claim, user, client_id):
                # The same queued photo, sent twice at once: the first one in keeps its place.
                db.rollback()
                store.delete(key)
                return _detail(_claim(db, claim_id), user, db, store)
            if claim is None or user.id not in _crew_ids(claim) or claim.state not in WORKING_STATES:
                raise HTTPException(status.HTTP_409_CONFLICT, "This claim changed while the photo was being sent")
            if len(claim.photos) >= limits.PHOTOS_PER_CLAIM:
                raise HTTPException(status.HTTP_409_CONFLICT, f"A claim holds at most {limits.PHOTOS_PER_CLAIM} photos")
            replaced = [p for p in claim.photos if point is not None and p.phase == phase and p.point == point]
            for old in replaced:
                claim.photos.remove(old)
            db.flush()
            claim.photos.append(
                Photo(
                    id=photo_id,
                    phase=phase,
                    point=point,
                    content_type="image/jpeg",
                    size_bytes=len(jpeg),
                    uploaded_by=user.id,
                    client_id=client_id,
                )
            )
            if phase == "before" and claim.state == "claimed":
                claim.state = "in_progress"
                claim.started_at = _now()
            db.commit()
        except BaseException:
            db.rollback()
            store.delete(key)
            raise
        for old in replaced:
            store.delete(photo_key(claim_id, old.id))
        db.refresh(claim)
        return _detail(claim, user, db, store)


@router.delete("/claims/{claim_id}/photos/{photo_id}", response_model=ClaimDetail)
def delete_photo(
    claim_id: uuid.UUID,
    photo_id: uuid.UUID,
    request: Request,
    user: StewardUser = Depends(current_user),
    db: Session = Depends(get_db),
) -> ClaimDetail:
    store = _store(request)
    release_overdue(db)
    claim = _crew_claim(db, claim_id, user)
    photo = next((p for p in claim.photos if p.id == photo_id), None)
    if photo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such photo on this claim")
    claim.photos.remove(photo)
    db.commit()
    store.delete(photo_key(claim.id, photo_id))
    db.refresh(claim)
    return _detail(claim, user, db, store)


# --- Hours, submitting, reviewing ---------------------------------------------------


@router.put("/claims/{claim_id}/hours", response_model=ClaimDetail)
def log_hours(
    claim_id: uuid.UUID,
    body: HoursEntry,
    request: Request,
    user: StewardUser = Depends(current_user),
    db: Session = Depends(get_db),
) -> ClaimDetail:
    """Your own hours on this claim, across all your visits. Each person logs their own."""
    release_overdue(db)
    claim = _crew_claim(db, claim_id, user)
    entry = next((h for h in claim.hours if h.user_id == user.id), None)
    tenths = round(body.hours * 10)
    if entry is None:
        claim.hours.append(Hours(user_id=user.id, tenths=tenths))
    else:
        entry.tenths = tenths
    db.commit()
    db.refresh(claim)
    return _detail(claim, user, db, request.app.state.photos)


def _missing_photos(claim: Claim) -> list[str]:
    """Each photo point needs a before and an after. After a send-back, only
    after photos taken since count: resubmitting the same pictures is not a fix."""
    have = {
        (p.phase, p.point)
        for p in claim.photos
        if not (p.phase == "after" and claim.sent_back_at is not None and p.created_at <= claim.sent_back_at)
    }
    return [
        f"{phase} at point {point}" + (" (retaken since it was sent back)" if phase == "after" and claim.sent_back_at else "")
        for point in limits.PHOTO_POINTS
        for phase in ("before", "after")
        if (phase, point) not in have
    ]


@router.post("/claims/{claim_id}/submit", response_model=ClaimDetail)
def submit(
    claim_id: uuid.UUID,
    body: Submission,
    request: Request,
    user: StewardUser = Depends(current_user),
    db: Session = Depends(get_db),
) -> ClaimDetail:
    release_overdue(db)
    claim = _crew_claim(db, claim_id, user, states=("in_progress",))
    missing = _missing_photos(claim)
    if missing:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"Still needed before submitting: {', '.join(missing)}")
    claim.steps_done = list(dict.fromkeys(body.steps_done))
    claim.notes = body.notes
    claim.state = "submitted"
    claim.submitted_at = _now()
    claim.invite_token_sha256 = None
    db.commit()
    return _detail(claim, user, db, request.app.state.photos)


@router.get("/reviews", response_model=list[ClaimSummary])
def waiting_for_review(user: StewardUser = Depends(current_user), db: Session = Depends(get_db)) -> list[ClaimSummary]:
    """Submitted claims this caller may review: oldest first, none of their own crew's."""
    release_overdue(db)
    mine = select(ClaimMember.claim_id).where(ClaimMember.user_id == user.id)
    claims = db.scalars(
        select(Claim).where(Claim.state == "submitted", Claim.id.not_in(mine)).order_by(Claim.submitted_at).limit(50)
    ).all()
    names = _names(db, {c.claimer_id for c in claims if c.claimer_id})
    return [_summary(claim, user, names) for claim in claims]


@router.post("/claims/{claim_id}/review", response_model=ClaimDetail)
def review(
    claim_id: uuid.UUID, body: Review, request: Request, user: StewardUser = Depends(current_user), db: Session = Depends(get_db)
) -> ClaimDetail:
    """Never by anyone who is or was on the crew: deleting your data marks your
    crew places left rather than removing them (models.ClaimMember), so
    leaving does not make a person eligible to verify their own work.

    - verify: confirms the crew's hours;
    - send back: needs a note; the crew gets back the time they had left when
      they submitted, and at least limits.SEND_BACK_DAYS, so one reviewer
      cannot shorten a crew's clock by sending it back (the review's finding 9);
      the after photos must be retaken;
    - reject: needs a note; the site is released and the hours are not counted,
      and the reviewer may not claim it for limits.REJECTER_WAIT_DAYS.
    """
    claim = db.get(Claim, claim_id, with_for_update=True)
    if claim is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such claim")
    if user.id in _ever_crew_ids(claim):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Someone off the crew has to review this")
    if claim.state != "submitted":
        raise HTTPException(status.HTTP_409_CONFLICT, "Only a submitted claim can be reviewed")
    if body.verdict != "verify" and not body.note:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Say what is missing when sending back or rejecting")
    now = _now()
    claim.reviewed_by = user.id
    claim.reviewed_by_name = user.display_name
    claim.review_note = body.note
    if body.verdict == "verify":
        claim.state = "verified"
        claim.verified_at = now
        for entry in claim.hours:
            entry.verified = True
    elif body.verdict == "send_back":
        remaining = claim.due_at - (claim.submitted_at or now)
        claim.state = "in_progress"
        claim.sent_back_at = now
        claim.submitted_at = None
        claim.due_at = now + max(remaining, timedelta(days=limits.SEND_BACK_DAYS))
    else:
        claim.state = "released"
        claim.released_at = now
        claim.rejected_by = user.id
        claim.invite_token_sha256 = None
    db.commit()
    return _detail(claim, user, db, request.app.state.photos)


@router.get("/hours/mine", response_model=HoursTotals)
def my_hours(user: StewardUser = Depends(current_user), db: Session = Depends(get_db)) -> HoursTotals:
    rows = db.scalars(select(Hours).where(Hours.user_id == user.id)).all()
    return HoursTotals(
        verified=sum(h.tenths for h in rows if h.verified) / 10,
        waiting=sum(h.tenths for h in rows if not h.verified) / 10,
        claims=len(rows),
    )
