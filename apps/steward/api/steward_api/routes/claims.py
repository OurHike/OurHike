"""Claims: a volunteer takes a site for 14 days, brings a crew, photographs it
before and after, and someone off the crew verifies it (PLAN.md §6, #1910).

    claimed ──first before photo──► in_progress ──submit──► submitted ──verify──► verified
       │                                │                       │
       └──── release, or due_at passes ─┴──► released           └──send back──► in_progress

The clock is due_at. It stops at submitted, so a slow reviewer never costs a
crew its claim; a send-back restarts it with limits.SEND_BACK_DAYS. Running out
is not a scheduled job: every request that reads claims first releases the ones
past due (release_overdue), so a released claim is never shown as live.

Who may do what:
- anyone signed in: claim an open site, read any claim, review a submitted
  claim they are not crew on;
- the crew (the claimer and whoever joined by invite link): photograph,
  log their own hours, submit, make an invite link;
- the claimer: release.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from steward_api import limits
from steward_api.auth import current_user
from steward_api.db import get_db
from steward_api.models import HOLDING_STATES, Claim, ClaimMember, Hours, Photo, StewardUser
from steward_api.photos import NOT_SET_UP, PhotoStorageUnavailable, PhotoStore, carries_location_metadata, photo_key, sniff
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
        crew_size=len(claim.members),
        you_are_crew=user.id in _crew_ids(claim),
    )


def _detail(claim: Claim, user: StewardUser, db: Session, store: PhotoStore | None) -> ClaimDetail:
    crew = _crew_ids(claim)
    names = _names(db, crew | {i for i in (claim.claimer_id, claim.reviewed_by) if i})
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
        verified_at=claim.verified_at,
        released_at=claim.released_at,
        steps_done=list(claim.steps_done or []),
        notes=claim.notes,
        review_note=claim.review_note,
        reviewed_by=names.get(claim.reviewed_by) if claim.reviewed_by else None,
        crew=[CrewMember(name=names.get(m.user_id), you=m.user_id == user.id, hours=hours.get(m.user_id)) for m in claim.members],
        photos=photos,
        you_may_review=claim.state == "submitted" and user.id not in crew,
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
    body: ClaimCreate, user: StewardUser = Depends(current_user), db: Session = Depends(get_db)
) -> list[ClaimSummary]:
    """Claim one site, or several at once (a site and its cluster). All or none:
    if any of them is already held, nothing is claimed and the answer says which."""
    release_overdue(db)
    sites = list(dict.fromkeys(body.rims_ids))
    live = db.scalar(
        select(func.count())
        .select_from(Claim)
        .join(ClaimMember, ClaimMember.claim_id == Claim.id)
        .where(ClaimMember.user_id == user.id, Claim.state.in_(WORKING_STATES))
    )
    if (live or 0) + len(sites) > limits.LIVE_CLAIMS_PER_USER:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"One account works on at most {limits.LIVE_CLAIMS_PER_USER} claims at a time"
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
        .where(ClaimMember.user_id == user.id)
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
    claim = db.scalars(select(Claim).where(Claim.invite_token_sha256 == _hash(body.token))).first()
    if claim is None or claim.state not in WORKING_STATES:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This invite is not valid any more. Ask the crew for a new one.")
    if user.id not in _crew_ids(claim):
        if len(claim.members) >= limits.CREW_MAX:
            raise HTTPException(status.HTTP_409_CONFLICT, f"This crew is full at {limits.CREW_MAX}")
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
    phase: str = Query(pattern="^(before|after|extra)$"),
    point: int | None = Query(default=None),
    user: StewardUser = Depends(current_user),
    db: Session = Depends(get_db),
) -> ClaimDetail:
    """The photo is the raw request body. One before and one after per photo
    point (a new one replaces the old), and any number of extras up to the cap.
    The first before photo moves a claim from claimed to in progress.

    Async only to read the body as it arrives, so the cap holds before the
    bytes are all in memory; the database and storage work then runs in a
    worker thread, because the session is synchronous."""
    store = _store(request)
    if (phase == "extra") != (point is None) or (point is not None and point not in limits.PHOTO_POINTS):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "A before or after photo needs photo point 1 or 2; an extra needs none"
        )
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > limits.PHOTO_MAX_BYTES:
            raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "That photo is too large")
    content_type = sniff(bytes(body))
    if content_type is None:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Only JPEG, PNG and WebP photos are accepted")
    if carries_location_metadata(bytes(body), content_type):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "This photo still carries its camera data, which can include where it was taken. Upload it from the app, which removes it.",
        )
    return await run_in_threadpool(_store_photo, db, store, user, claim_id, phase, point, bytes(body), content_type)


def _store_photo(
    db: Session,
    store: PhotoStore,
    user: StewardUser,
    claim_id: uuid.UUID,
    phase: str,
    point: int | None,
    body: bytes,
    content_type: str,
) -> ClaimDetail:
    release_overdue(db)
    claim = _crew_claim(db, claim_id, user)
    if len(claim.photos) >= limits.PHOTOS_PER_CLAIM:
        raise HTTPException(status.HTTP_409_CONFLICT, f"A claim holds at most {limits.PHOTOS_PER_CLAIM} photos")
    replaced = [p for p in claim.photos if point is not None and p.phase == phase and p.point == point]
    photo = Photo(id=uuid.uuid4(), phase=phase, point=point, content_type=content_type, size_bytes=len(body), uploaded_by=user.id)
    # Object first, row second: a row whose object failed to write would show a
    # photo that is not there; an object whose row failed is swept as an orphan.
    try:
        store.put(photo_key(claim.id, photo.id), body, content_type)
    except PhotoStorageUnavailable as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    for old in replaced:
        claim.photos.remove(old)
    db.flush()
    claim.photos.append(photo)
    if phase == "before" and claim.state == "claimed":
        claim.state = "in_progress"
        claim.started_at = _now()
    db.commit()
    for old in replaced:
        store.delete(photo_key(claim.id, old.id))
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
    have = {(p.phase, p.point) for p in claim.photos}
    return [
        f"{phase} at point {point}"
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
    """Verify, which confirms the crew's hours; or send back, which gives the
    crew limits.SEND_BACK_DAYS more. Never by the claimer or anyone on the crew."""
    claim = db.get(Claim, claim_id, with_for_update=True)
    if claim is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such claim")
    if user.id in _crew_ids(claim):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Someone off the crew has to review this")
    if claim.state != "submitted":
        raise HTTPException(status.HTTP_409_CONFLICT, "Only a submitted claim can be reviewed")
    claim.reviewed_by = user.id
    claim.review_note = body.note
    if body.verdict == "verify":
        claim.state = "verified"
        claim.verified_at = _now()
        for entry in claim.hours:
            entry.verified = True
    else:
        if not body.note:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Say what needs doing when sending a submission back")
        claim.state = "in_progress"
        claim.submitted_at = None
        claim.due_at = _now() + timedelta(days=limits.SEND_BACK_DAYS)
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
