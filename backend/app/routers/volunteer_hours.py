"""`/volunteer-hours` endpoints - the self-logged half of VOLUNTEERING.md §4.

Every read here is somebody's own logbook or a club admin's confirmation
queue; there is deliberately no public list, no per-hiker totals endpoint,
and nothing an anonymous caller can see - the impact record is private by
design (#761), and the four rules that keep it from becoming a scoreboard
live where the numbers are rendered (client Volunteer tab), not here.

The state machine is small and the audit is the point: `claimed` on filing,
`confirmed` when a club admin stands behind the number, `disputed` when one
refuses to. Maintainer decision 2026-08-20 (on #761): claimed counts
everywhere until disputed, so a dispute is the removal action and carries
the same latest-wins audit pair every removal here carries.
"""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import get_current_user, require_role
from app.core.orm import commit_and_refresh, get_or_404
from app.core.time import utc_now
from app.db.session import get_db
from app.models.profile import MODERATOR_ROLES, Profile
from app.models.volunteer_hours import HoursState, VolunteerHoursRecord
from app.schemas.volunteer_hours import VolunteerHoursCreate, VolunteerHoursOut

router = APIRouter(prefix="/volunteer-hours", tags=["volunteer-hours"])


def _already_filed(db: Session, record_id: str, current_user: Profile) -> VolunteerHoursRecord | None:
    """Reports' idempotency contract, verbatim: the caller's own record under
    this id, None to proceed, and somebody else's id refused outright."""
    existing = db.get(VolunteerHoursRecord, record_id)
    if existing is None:
        return None
    if existing.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That record id belongs to someone else.",
        )
    return existing


@router.post("", response_model=VolunteerHoursOut, status_code=status.HTTP_201_CREATED)
def log_hours(
    payload: VolunteerHoursCreate,
    response: Response,
    current_user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> VolunteerHoursRecord:
    """File a day's work. Born `claimed` - immediately real to the volunteer,
    provisional to everyone else until a club confirms it (VOLUNTEERING.md).

    Idempotent on `id` for the outbox's sake: hours are logged at camp, and
    camp has no signal.
    """
    record_id = str(payload.id) if payload.id is not None else None

    if record_id is not None:
        settled = _already_filed(db, record_id, current_user)
        if settled is not None:
            response.status_code = status.HTTP_200_OK
            return settled

    record = VolunteerHoursRecord(
        **({"id": record_id} if record_id is not None else {}),
        user_id=current_user.id,
        club_id=payload.club_id,
        worked_on=payload.worked_on,
        hours=payload.hours,
        work_project_id=payload.work_project_id,
        activity=payload.activity,
        note=payload.note,
        mile=payload.mile,
        lat=payload.lat,
        lon=payload.lon,
        recorded_at=utc_now(),
    )
    db.add(record)
    try:
        return commit_and_refresh(db, record)
    except IntegrityError as exc:
        db.rollback()
        settled = _already_filed(db, record_id, current_user) if record_id is not None else None
        if settled is None:
            # A club_id naming no known club is the caller's error, named so
            # the form can be fixed (reports' #658 lesson).
            if "club_id" in str(getattr(exc, "orig", exc)):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="club_id does not name a known club",
                ) from exc
            raise
        response.status_code = status.HTTP_200_OK
        return settled


@router.get("/mine", response_model=list[VolunteerHoursOut])
def list_my_hours(
    current_user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[VolunteerHoursRecord]:
    """The caller's own logbook, newest work first - every state included,
    because a disputed record is still theirs to see and re-raise with the
    club. Totals are the CLIENT's to compute and label: which states count
    is a display rule (the 2026-08-20 decision), not a second endpoint."""
    return (
        db.query(VolunteerHoursRecord)
        .filter(VolunteerHoursRecord.user_id == current_user.id)
        .order_by(VolunteerHoursRecord.worked_on.desc(), VolunteerHoursRecord.id)
        .all()
    )


@router.get("/queue", response_model=list[VolunteerHoursOut])
def list_claimed_hours(
    current_user: Profile = Depends(require_role(*MODERATOR_ROLES)),
    db: Session = Depends(get_db),
) -> list[VolunteerHoursRecord]:
    """Everything still waiting on a club's word, oldest work first - the
    confirmation surface Phase D's attendance pre-fill will feed. Listed for
    every moderator rather than per club, the same one-club honesty
    moderation.py's queue records: enough for one club, not for thirty."""
    return (
        db.query(VolunteerHoursRecord)
        .filter(VolunteerHoursRecord.state == HoursState.claimed)
        .order_by(VolunteerHoursRecord.worked_on, VolunteerHoursRecord.id)
        .all()
    )


@router.post("/{record_id}/confirm", response_model=VolunteerHoursOut)
def confirm_hours(
    record_id: str,
    current_user: Profile = Depends(require_role(*MODERATOR_ROLES)),
    db: Session = Depends(get_db),
) -> VolunteerHoursRecord:
    """A club admin stands behind the number - the 'grant' that makes an
    hour reportable upward with the club's name on it. Set once, never
    overwritten: who FIRST granted it is the fact an audit needs
    (moderation.py's verify rule)."""
    record = get_or_404(db, VolunteerHoursRecord, record_id, detail="Record not found")

    record.state = HoursState.confirmed
    if record.confirmed_at is None:
        record.confirmed_by = current_user.id
        record.confirmed_at = utc_now()
    return commit_and_refresh(db, record)


@router.post("/{record_id}/dispute", response_model=VolunteerHoursOut)
def dispute_hours(
    record_id: str,
    current_user: Profile = Depends(require_role(*MODERATOR_ROLES)),
    db: Session = Depends(get_db),
) -> VolunteerHoursRecord:
    """A club declines to stand behind the number. This is the removal
    action under the 2026-08-20 decision - a disputed record drops out of
    every total - so the audit pair is latest-wins, like every dismissal:
    'who took this out' means the operative refusal. The record stays, and
    stays visible to its volunteer: a dispute is a disagreement to be taken
    up with the club, not an erasure."""
    record = get_or_404(db, VolunteerHoursRecord, record_id, detail="Record not found")

    record.state = HoursState.disputed
    record.confirmed_by = current_user.id
    record.confirmed_at = utc_now()
    return commit_and_refresh(db, record)
