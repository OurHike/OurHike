"""`/workdays` - posting one, putting your hand up, and the organization's reply.

features/VOLUNTEERING.md phase D (#762) and §6 (#763), and
../../../features/ORG_ONBOARDING.md's Workdays screen.

**A signup is an introduction, not an enrolment.** There is no path in this
file that sets `confirmed` except an organization explicitly replying with
it: `WorkProjectSignupCreate` has no `state` field, and `WorkProjectSignupReply`
refuses `interested` because replying "interested" says nothing a volunteer
cannot already see. The app must never leave somebody believing they are on a
roster when they are not, and the way that is enforced is by the wire not
carrying the value rather than by anybody remembering.

**Both signup paths are first-class.** A `mirrored` workday is authoritative
on the organization's own calendar and its signup goes to their form; an
`ourhike` one uses ours. An org with a working calendar is not going to
abandon it, so `create_signup` refuses to file an in-app signup against a
mirrored project rather than quietly collecting hands the org will never see.

**Nothing here notifies anybody.** OurHike sends no push notification of any
kind, and per value #9, no broadcasting of large gatherings and nothing that
turns a workday into an event to be amplified.
"""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.org_access import OrgAccess, club_by_slug, require_manage_volunteers, resolve_access
from app.core.orm import commit_and_refresh
from app.core.time import utc_now
from app.db.session import get_db
from app.models.club import Club
from app.models.profile import Profile
from app.models.work_project import (
    ProjectSource,
    ProjectStatus,
    SignupMode,
    SignupState,
    WorkProject,
    WorkProjectSignup,
)
from app.schemas.work_project import (
    WorkProjectAttendance,
    WorkProjectCreate,
    WorkProjectOut,
    WorkProjectSignupCreate,
    WorkProjectSignupOut,
    WorkProjectSignupReply,
)

router = APIRouter(tags=["workdays"])

# The window a hiker is shown, from VOLUNTEERING.md §2. Fourteen days is the
# design's figure and is @unvalidated - nothing has measured how far ahead a
# hiker actually plans a workday around. What would settle it: the lead time
# on real signups once any organization runs one.
UPCOMING_WINDOW_DAYS = 14


def _counts(db: Session, project_ids: list[str]) -> dict[str, tuple[int, int]]:
    """Hands up and hands confirmed, per project, in one query.

    Two numbers rather than one, because a cap applies to the confirmed count
    and somebody reading "12 of 10" on an uncapped interest list would take
    it for a queue position they do not have.
    """
    if not project_ids:
        return {}
    rows = db.query(WorkProjectSignup).filter(WorkProjectSignup.work_project_id.in_(project_ids)).all()
    counts: dict[str, tuple[int, int]] = {}
    for row in rows:
        interested, confirmed = counts.get(row.work_project_id, (0, 0))
        if row.state in (SignupState.declined, SignupState.cancelled_by_volunteer):
            continue
        counts[row.work_project_id] = (
            interested + 1,
            confirmed + (1 if row.state == SignupState.confirmed else 0),
        )
    return counts


def _as_out(project: WorkProject, counts: dict[str, tuple[int, int]]) -> WorkProjectOut:
    out = WorkProjectOut.model_validate(project)
    out.interested_count, out.confirmed_count = counts.get(project.id, (0, 0))
    return out


def _club(db: Session, club_id: str) -> Club:
    """The organization a workday belongs to, for resolving the caller's seat."""
    club = db.get(Club, club_id)
    if club is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such organization")
    return club


def _project_or_404(db: Session, project_id: str) -> WorkProject:
    project = db.get(WorkProject, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such workday")
    return project


@router.get("/workdays", response_model=list[WorkProjectOut])
def list_workdays(
    org: str | None = None,
    days: int = UPCOMING_WINDOW_DAYS,
    db: Session = Depends(get_db),
) -> list[WorkProjectOut]:
    """Upcoming workdays, soonest first. Public - no account needed to look.

    `days` is capped rather than trusted, because an unbounded window on a
    public endpoint is a full table scan anybody can ask for.
    """
    window = max(1, min(days, 365))
    query = db.query(WorkProject).filter(
        WorkProject.status == ProjectStatus.upcoming,
        WorkProject.ends_on >= date.today(),
        WorkProject.starts_on <= date.today() + timedelta(days=window),
    )
    if org:
        query = query.filter(WorkProject.club_id == club_by_slug(db, org).id)

    projects = query.order_by(WorkProject.starts_on, WorkProject.title).all()
    counts = _counts(db, [project.id for project in projects])
    return [_as_out(project, counts) for project in projects]


@router.post("/clubs/{slug}/workdays", response_model=WorkProjectOut, status_code=status.HTTP_201_CREATED)
def create_workday(
    slug: str,
    payload: WorkProjectCreate,
    access: OrgAccess = Depends(require_manage_volunteers),
    db: Session = Depends(get_db),
) -> WorkProjectOut:
    """Post a workday.

    **This is the one thing an organization may change self-service that
    reaches a hiker's screen**, and ORG_ONBOARDING.md relaxes
    SOURCE_REGISTRY.md's no-self-service rule for it explicitly: a workday
    carries no geometry a hiker navigates by, and a wrong one costs somebody
    a Saturday rather than a wrong turn. A trail line is a different risk
    class and keeps the reviewed-file path.
    """
    project = WorkProject(
        club_id=access.club.id,
        title=payload.title,
        description=payload.description,
        starts_on=payload.starts_on,
        ends_on=payload.ends_on or payload.starts_on,
        meet_point=payload.meet_point,
        mile=payload.mile,
        lat=payload.lat,
        lon=payload.lon,
        cap=payload.cap,
        source=payload.source,
        signup_mode=payload.signup_mode,
        signup_contact=payload.signup_contact,
        signup_url=payload.signup_url,
        created_by=access.person_id,
    )
    db.add(project)
    return _as_out(commit_and_refresh(db, project), {})


@router.post("/workdays/{project_id}/cancel", response_model=WorkProjectOut)
def cancel_workday(
    project_id: str,
    current_user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkProjectOut:
    """Call one off.

    Cancelling rather than deleting, because people have already put their
    hands up and a row that vanishes tells them nothing. VOLUNTEERING.md's
    own worst case is somebody driving to a trailhead for a workday cancelled
    on Thursday, and a cancelled project that is still readable is what lets
    every surface say so.
    """
    project = _project_or_404(db, project_id)
    access = resolve_access(db, _club(db, project.club_id), current_user.id)
    if not access.can_manage_volunteers:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only an admin or a supervisor at this organization can cancel a workday",
        )

    project.status = ProjectStatus.cancelled
    db.commit()
    return _as_out(project, _counts(db, [project.id]))


@router.post("/workdays/{project_id}/signups", response_model=WorkProjectSignupOut, status_code=status.HTTP_201_CREATED)
def create_signup(
    project_id: str,
    payload: WorkProjectSignupCreate,
    response: Response,
    current_user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkProjectSignup:
    """Put your hand up. It is an expression of interest and says so.

    **Born `interested`, always.** The organization sets anything else.

    A mirrored workday is refused rather than accepted quietly: its
    organization's own calendar is authoritative and never sees this table,
    so a hand up here would be a hand up nobody reads. The message names
    where to go instead.
    """
    project = _project_or_404(db, project_id)

    if project.status == ProjectStatus.cancelled:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="That workday has been called off")
    if project.source == ProjectSource.mirrored or project.signup_mode == SignupMode.contact:
        where = project.signup_url or project.signup_contact or "the organization's own site"
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"This organization takes signups on their own system: {where}",
        )

    signup = WorkProjectSignup(
        work_project_id=project.id,
        person_id=current_user.id,
        note=payload.note,
        state=SignupState.interested,
    )
    db.add(signup)
    try:
        return commit_and_refresh(db, signup)
    except IntegrityError:
        db.rollback()
        # Already signed up. Returning the existing row at 200 rather than
        # 409 because the outbox retries, and a second tap should not read
        # as an error to somebody who did nothing wrong.
        existing = (
            db.query(WorkProjectSignup)
            .filter(
                WorkProjectSignup.work_project_id == project.id,
                WorkProjectSignup.person_id == current_user.id,
            )
            .one()
        )
        response.status_code = status.HTTP_200_OK
        return existing


@router.get("/workdays/{project_id}/signups", response_model=list[WorkProjectSignupOut])
def list_signups(
    project_id: str,
    current_user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[WorkProjectSignup]:
    """Who has put their hand up - for the organization only.

    Names attached to a workday are exactly the class of fact rule 4 keeps
    unpublished, so this is gated to people who run the crew. A volunteer
    reads their own signup through their own record, not through this list.
    """
    project = _project_or_404(db, project_id)
    access = resolve_access(db, _club(db, project.club_id), current_user.id)
    if not access.can_manage_volunteers:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only an admin or a supervisor at this organization can see who signed up",
        )
    return (
        db.query(WorkProjectSignup)
        .filter(WorkProjectSignup.work_project_id == project.id)
        .order_by(WorkProjectSignup.created_at)
        .all()
    )


@router.post("/workdays/{project_id}/signups/{signup_id}/reply", response_model=WorkProjectSignupOut)
def reply_to_signup(
    project_id: str,
    signup_id: str,
    payload: WorkProjectSignupReply,
    current_user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkProjectSignup:
    """The organization's own answer - confirmed, waitlisted or declined.

    The reply message travels with the state wherever the state is shown,
    because **the message is what makes the answer the organization's own
    rather than the app's.** A volunteer reading "waitlisted" and nothing
    else learns less than one reading "waitlisted - we are full for the
    sawyer crew but short on the Tuesday one, if that suits you."
    """
    project = _project_or_404(db, project_id)
    access = resolve_access(db, _club(db, project.club_id), current_user.id)
    if not access.can_manage_volunteers:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only an admin or a supervisor at this organization can answer a signup",
        )

    signup = (
        db.query(WorkProjectSignup)
        .filter(WorkProjectSignup.id == signup_id, WorkProjectSignup.work_project_id == project.id)
        .one_or_none()
    )
    if signup is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such signup on that workday")

    signup.state = payload.state
    signup.reply_message = payload.message
    signup.replied_by = current_user.id
    signup.replied_at = utc_now()
    return commit_and_refresh(db, signup)


@router.post("/workdays/{project_id}/signups/{signup_id}/attendance", response_model=WorkProjectSignupOut)
def record_attendance(
    project_id: str,
    signup_id: str,
    payload: WorkProjectAttendance,
    current_user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkProjectSignup:
    """Record that somebody turned up, which pre-fills an hours claim.

    **It pre-fills; it does not create.** Hours are claimed, not computed -
    the person who worked four hours is the one who knows it was four, and a
    number this app wrote is a number no organization should report onward to
    ATC or a land agency.
    """
    project = _project_or_404(db, project_id)
    access = resolve_access(db, _club(db, project.club_id), current_user.id)
    if not access.can_manage_volunteers:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only an admin or a supervisor at this organization can record attendance",
        )

    signup = (
        db.query(WorkProjectSignup)
        .filter(WorkProjectSignup.id == signup_id, WorkProjectSignup.work_project_id == project.id)
        .one_or_none()
    )
    if signup is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such signup on that workday")

    signup.attended = payload.attended
    return commit_and_refresh(db, signup)


@router.get("/workdays/signups/mine", response_model=list[WorkProjectSignupOut])
def list_my_signups(
    current_user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[WorkProjectSignup]:
    """Every hand this person has put up, with the organization's reply."""
    return (
        db.query(WorkProjectSignup)
        .filter(WorkProjectSignup.person_id == current_user.id)
        .order_by(WorkProjectSignup.created_at.desc())
        .all()
    )


@router.post("/workdays/{project_id}/signups/mine/cancel", response_model=WorkProjectSignupOut)
def cancel_my_signup(
    project_id: str,
    current_user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkProjectSignup:
    """Pull out. One tap, and utterly consequence-free.

    #762's open question, answered the way that issue's own instinct pointed.
    A no-show costs an organization a crew slot, and the alternative
    mitigation is tracking reliability - which is a reputation score, and
    rule 1 rules those out. **Nothing anywhere counts how often somebody has
    been in this state**, and that absence is the design rather than an
    omission.
    """
    signup = (
        db.query(WorkProjectSignup)
        .filter(
            WorkProjectSignup.work_project_id == project_id,
            WorkProjectSignup.person_id == current_user.id,
        )
        .one_or_none()
    )
    if signup is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="You have not signed up to that one")

    signup.state = SignupState.cancelled_by_volunteer
    return commit_and_refresh(db, signup)
