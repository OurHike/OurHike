"""`/clubs/{slug}` roles, invites, the roster, and the sync that loads it.

See ../../../features/ORG_ONBOARDING.md, #1169 (roles that can be granted at
all) and #1154 (a live endpoint an organization's IT configures).

**This is the file `backend/README.md`'s no-HTTP-writes rule said should not
exist, and the reason it does is worth carrying in front of the code.** That
rule forbade HTTP writes to `clubs` and `maintainer_assignments` because *"an
assignment says a named volunteer is at a known place on a predictable
schedule, which is the fact features/SAYING_THANKS.md declines to publish
without consent."* Read closely, **that is a rule about publication, not
about access**, and the two come apart: RLS answers who may write, and it was
publication that needed the reviewed file. Nothing a named volunteer does is
published at all - thanks attach to a place and a category - so the roster is
private by construction and the reviewed-file path stays where it belongs, on
the registry, which is public by definition.

Two guardrails replace it, and both are in this file:

1. **A bad sync cannot empty a roster.** A run that would deactivate more
   than `DEACTIVATION_HOLD_FRACTION` of an org's live assignments applies its
   additions and holds its deactivations for a person.
2. **Supervisors propose, admins confirm.** RLS says who may write, never
   whether a write was right - and a wrong section assignment sends a hiker's
   report to the wrong person.

`load_assignments.py` stays exactly as it is. It is still the right answer
for one organization getting started from a file, and its own docstring
already said the larger module is where an admin surface belongs.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.org_access import OrgAccess, org_access, require_manage_volunteers, require_org_admin
from app.core.orm import commit_and_refresh
from app.core.role_invites import normalise_email
from app.core.time import utc_now
from app.db.session import get_db
from app.models.maintainer_assignment import MaintainerAssignment
from app.models.org_registry import OrgPark, OrgSection, OrgTrail
from app.models.org_role import DEACTIVATION_HOLD_FRACTION, OrgRole, RoleInvite, RosterSyncRun
from app.models.profile import Profile
from app.schemas.org_role import (
    AssignmentCreate,
    AssignmentOut,
    OrgRoleCreate,
    OrgRoleOut,
    OrgRoleUpdate,
    RoleInviteCreate,
    RoleInviteOut,
    RosterEntry,
    RosterSyncRequest,
    RosterSyncResult,
)

router = APIRouter(prefix="/clubs", tags=["org-roles"])


def _section_here_or_422(db: Session, club_id: str, section_id: str) -> OrgSection:
    """A section of THIS organization's registry, or a refusal naming why.

    #1635: `section_id` used to be stored as given, so a role or an
    assignment could point at another organization's section - and the
    roster and coverage report would then show one org's volunteer on the
    other's trail. 422 rather than 404, because the org in the path exists
    and it is the body that is wrong.
    """
    section = (
        db.query(OrgSection)
        .join(OrgTrail, OrgTrail.id == OrgSection.trail_id)
        .join(OrgPark, OrgPark.id == OrgTrail.park_id)
        .filter(OrgSection.id == section_id, OrgPark.club_id == club_id)
        .one_or_none()
    )
    if section is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="That section is not in this organization's registry",
        )
    return section


def _inside_our_own_sections_or_422(
    db: Session, club_id: str, section: OrgSection | None, start_mile: float, end_mile: float
) -> None:
    """Refuse a stretch no section of this organization's registry contains.

    #1635: an assignment's miles were stored as given, so an organization
    could put somebody on miles 0 to 2,200 of a trail it has never
    described. The stretch now has to fit inside one section the
    organization has drawn - the named one when there is one, otherwise any
    of theirs. A section whose miles are not filled in yet contains nothing,
    because a stretch that cannot be checked is not one to take on trust.

    This bounds what the console can SAY about an organization's own
    volunteers. It is not what makes an assignment count for hikers - an
    organization draws its own sections too - which is
    `core/assignments.py`'s `stood_behind`.
    """
    if start_mile > end_mile:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The stretch starts after it ends",
        )
    if section is not None:
        candidates = [section]
    else:
        candidates = (
            db.query(OrgSection)
            .join(OrgTrail, OrgTrail.id == OrgSection.trail_id)
            .join(OrgPark, OrgPark.id == OrgTrail.park_id)
            .filter(OrgPark.club_id == club_id)
            .all()
        )
    for candidate in candidates:
        if candidate.start_mile is None or candidate.end_mile is None:
            continue
        if candidate.start_mile <= start_mile and end_mile <= candidate.end_mile:
            return
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=(
            "That stretch is not inside any section of this organization's registry. Add the section, with its miles, first."
        ),
    )


def _role_or_404(db: Session, club_id: str, role_id: str) -> OrgRole:
    role = db.query(OrgRole).filter(OrgRole.id == role_id, OrgRole.club_id == club_id).one_or_none()
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such role here")
    return role


@router.get("/{slug}/roles", response_model=list[OrgRoleOut])
def list_roles(
    slug: str,
    include_retired: bool = False,
    access: OrgAccess = Depends(require_manage_volunteers),
    db: Session = Depends(get_db),
) -> list[OrgRole]:
    """Every role this organization defines.

    Retired roles are excluded by default and available on request, because
    they are history rather than nothing: a retired role keeps its holders'
    record, and a screen reconstructing who covered a mile last June needs to
    be able to ask for it.
    """
    query = db.query(OrgRole).filter(OrgRole.club_id == access.club.id)
    if not include_retired:
        query = query.filter(OrgRole.retired_at.is_(None))
    return query.order_by(OrgRole.category, OrgRole.name).all()


@router.post("/{slug}/roles", response_model=OrgRoleOut, status_code=status.HTTP_201_CREATED)
def create_role(
    slug: str,
    payload: OrgRoleCreate,
    access: OrgAccess = Depends(require_org_admin),
    db: Session = Depends(get_db),
) -> OrgRole:
    """Define a role. Admin-only: the reporting line decides who confirms whom."""
    if payload.reports_to_role_id:
        _role_or_404(db, access.club.id, payload.reports_to_role_id)
    if payload.section_id:
        _section_here_or_422(db, access.club.id, payload.section_id)
    role = OrgRole(
        club_id=access.club.id,
        name=payload.name,
        category=payload.category,
        reports_to_role_id=payload.reports_to_role_id,
        section_id=payload.section_id,
        required=payload.required,
        required_by=payload.required_by,
    )
    db.add(role)
    return commit_and_refresh(db, role)


@router.patch("/{slug}/roles/{role_id}", response_model=OrgRoleOut)
def update_role(
    slug: str,
    role_id: str,
    payload: OrgRoleUpdate,
    access: OrgAccess = Depends(require_org_admin),
    db: Session = Depends(get_db),
) -> OrgRole:
    role = _role_or_404(db, access.club.id, role_id)
    fields = payload.model_dump(exclude_unset=True)

    # A role reporting to itself is a cycle of length one, and the hierarchy
    # visual renders it as an infinite regress. Longer cycles are possible
    # and not checked here - a deeper walk belongs with whatever draws the
    # tree, and refusing the obvious case cheaply beats refusing none.
    if fields.get("reports_to_role_id") == role_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A role cannot report to itself",
        )
    if fields.get("reports_to_role_id"):
        _role_or_404(db, access.club.id, fields["reports_to_role_id"])
    if fields.get("section_id"):
        _section_here_or_422(db, access.club.id, fields["section_id"])

    for field, value in fields.items():
        setattr(role, field, value)
    return commit_and_refresh(db, role)


@router.delete("/{slug}/roles/{role_id}", response_model=OrgRoleOut)
def retire_role(
    slug: str,
    role_id: str,
    access: OrgAccess = Depends(require_org_admin),
    db: Session = Depends(get_db),
) -> OrgRole:
    """Retire a role, or delete it if nobody has ever held it.

    **A retired role keeps its holders' history; only an unheld role is
    deletable.** A delete that took the history with it would destroy the
    answer to "who covered this in June", which is the question the whole
    assignment model is versioned to preserve.

    Answers with the retired role rather than 204, because the screen shows
    it moving into the retired list rather than vanishing.
    """
    role = _role_or_404(db, access.club.id, role_id)
    ever_held = db.query(MaintainerAssignment).filter(MaintainerAssignment.role_id == role_id).first() is not None
    if not ever_held:
        db.delete(role)
        db.commit()
        role.retired_at = utc_now()
        return role

    role.retired_at = utc_now()
    return commit_and_refresh(db, role)


@router.get("/{slug}/roster", response_model=list[RosterEntry])
def read_roster(
    slug: str,
    access: OrgAccess = Depends(require_manage_volunteers),
    db: Session = Depends(get_db),
) -> list[RosterEntry]:
    """Everybody this organization has, signed in or not.

    Two identity shapes in one list, and the distinction is the point: a
    `person_id` means they have signed in and the record is theirs too; a row
    with only an email is a pending invite - somebody the org knows and
    OurHike has never met. An org's roster is its roster whether or not its
    people have discovered this app, and a screen that showed only the
    signed-in half would look like the org had lost most of its volunteers.
    """
    roles = {role.id: role.name for role in db.query(OrgRole).filter(OrgRole.club_id == access.club.id).all()}
    sections = {
        section.id: section.name
        for section in db.query(OrgSection)
        .join(OrgTrail, OrgTrail.id == OrgSection.trail_id)
        .join(OrgPark, OrgPark.id == OrgTrail.park_id)
        .filter(OrgPark.club_id == access.club.id)
        .all()
    }

    by_person: dict[str, RosterEntry] = {}
    live = (
        db.query(MaintainerAssignment)
        .filter(
            MaintainerAssignment.club_id == access.club.id,
            MaintainerAssignment.effective_to.is_(None),
        )
        .all()
    )
    for assignment in live:
        entry = by_person.setdefault(assignment.maintainer_id, RosterEntry(person_id=assignment.maintainer_id))
        if assignment.role_id and roles.get(assignment.role_id):
            entry.roles.append(roles[assignment.role_id])
        if assignment.section_id and sections.get(assignment.section_id):
            entry.sections.append(sections[assignment.section_id])

    if by_person:
        for profile in db.query(Profile).filter(Profile.id.in_(list(by_person))).all():
            by_person[profile.id].display_name = profile.display_name

    pending = [
        RosterEntry(
            email=invite.email,
            full_name=invite.full_name,
            roles=[roles[invite.role_id]] if invite.role_id and roles.get(invite.role_id) else [],
            pending_invite=True,
        )
        for invite in db.query(RoleInvite)
        .filter(RoleInvite.club_id == access.club.id, RoleInvite.claimed_at.is_(None))
        .order_by(RoleInvite.email)
        .all()
    ]
    return [*by_person.values(), *pending]


@router.post("/{slug}/invites", response_model=RoleInviteOut, status_code=status.HTTP_201_CREATED)
def invite_volunteer(
    slug: str,
    payload: RoleInviteCreate,
    access: OrgAccess = Depends(require_manage_volunteers),
    db: Session = Depends(get_db),
) -> RoleInvite:
    """Add one person by email, whether or not they have ever opened OurHike.

    **Roles come later.** `role_id` is optional because an org adding a name
    at a meeting does not always know yet what that person will do, and
    refusing the row until they decide loses the name.

    **Never a seat at the organization**, with or without a role. A
    role-less invite used to BE an admin invitation (#1635), which let a
    supervisor mint admins; `grants_admin_seat` is now the only thing that
    offers a seat, and only `routers/clubs.py`'s admin paths set it.
    """
    if payload.role_id:
        _role_or_404(db, access.club.id, payload.role_id)

    email = normalise_email(payload.email)
    existing = (
        db.query(RoleInvite)
        .filter(
            RoleInvite.club_id == access.club.id,
            RoleInvite.email == email,
            RoleInvite.role_id == payload.role_id,
            RoleInvite.grants_admin_seat.is_(False),
            RoleInvite.claimed_at.is_(None),
        )
        .one_or_none()
    )
    if existing is not None:
        return existing

    invite = RoleInvite(
        club_id=access.club.id,
        email=email,
        role_id=payload.role_id,
        full_name=payload.full_name,
        note=payload.note,
        invited_by=access.person_id,
    )
    db.add(invite)
    return commit_and_refresh(db, invite)


@router.post("/{slug}/assignments", response_model=AssignmentOut, status_code=status.HTTP_201_CREATED)
def create_assignment(
    slug: str,
    payload: AssignmentCreate,
    access: OrgAccess = Depends(require_manage_volunteers),
    db: Session = Depends(get_db),
) -> MaintainerAssignment:
    """Put somebody on a stretch.

    **Supervisors propose, admins confirm.** An admin's write is live
    immediately; a supervisor's carries `proposed_by` and waits. RLS says who
    may write, never whether a write was right, and a wrong section
    assignment sends a hiker's report to the wrong person for as long as
    nobody notices.

    Append-only, like every write to this table: a hand-off closes one row
    and opens another. Nothing here overwrites an existing assignment.
    """
    if payload.role_id:
        _role_or_404(db, access.club.id, payload.role_id)
    section = _section_here_or_422(db, access.club.id, payload.section_id) if payload.section_id else None
    _inside_our_own_sections_or_422(db, access.club.id, section, payload.start_mile, payload.end_mile)

    assignment = MaintainerAssignment(
        maintainer_id=payload.person_id,
        club_id=access.club.id,
        role_id=payload.role_id,
        section_id=payload.section_id,
        start_mile=payload.start_mile,
        end_mile=payload.end_mile,
        effective_from=payload.effective_from or date.today(),
        proposed_by=None if access.is_admin else access.person_id,
        confirmed_by=access.person_id if access.is_admin else None,
        confirmed_at=utc_now() if access.is_admin else None,
    )
    db.add(assignment)
    try:
        return commit_and_refresh(db, assignment)
    except IntegrityError as exc:
        db.rollback()
        # Somebody who has never signed in has no profile row to point at, and
        # that is #1169's problem 3 rather than a bug: OurHike cannot create a
        # user. The message names the route that does work, because "foreign
        # key violation" tells an admin nothing they can act on.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "That person has not signed in to OurHike yet, so there is no record to attach a "
                "section to. Invite them by email instead and the role is applied the first time "
                "they open the app."
            ),
        ) from exc


@router.post("/{slug}/assignments/{assignment_id}/confirm", response_model=AssignmentOut)
def confirm_assignment(
    slug: str,
    assignment_id: str,
    access: OrgAccess = Depends(require_org_admin),
    db: Session = Depends(get_db),
) -> MaintainerAssignment:
    """An admin standing behind a supervisor's proposal."""
    assignment = (
        db.query(MaintainerAssignment)
        .filter(MaintainerAssignment.id == assignment_id, MaintainerAssignment.club_id == access.club.id)
        .one_or_none()
    )
    if assignment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such assignment here")

    assignment.confirmed_by = access.person_id
    assignment.confirmed_at = utc_now()
    return commit_and_refresh(db, assignment)


@router.post("/{slug}/assignments/{assignment_id}/step-back", response_model=AssignmentOut)
def step_back(
    slug: str,
    assignment_id: str,
    access: OrgAccess = Depends(org_access),
    db: Session = Depends(get_db),
) -> MaintainerAssignment:
    """Close an assignment - a hand-off, or a volunteer stepping back.

    **A volunteer can step back themselves, any time, without asking**, which
    is why the gate below lets the assignment's own holder through even when
    they can manage nobody. The org's feed can already deactivate them; they
    should have at least that much say.

    It closes the row rather than deleting it - `effective_to`, so the
    history survives - and it frees the section, which is what makes the
    coverage report correct the same day rather than whenever somebody
    remembers to tidy up.
    """
    assignment = (
        db.query(MaintainerAssignment)
        .filter(MaintainerAssignment.id == assignment_id, MaintainerAssignment.club_id == access.club.id)
        .one_or_none()
    )
    if assignment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such assignment here")

    # Their own, or somebody they are entitled to move. Checked in that
    # order, because the volunteer's own right to step back is the one this
    # endpoint exists for and the management case is the addition.
    its_holder = assignment.maintainer_id == access.person_id
    if not (its_holder or access.can_manage_volunteers):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can step back from your own section, or manage one as an admin or supervisor",
        )

    assignment.effective_to = date.today()
    return commit_and_refresh(db, assignment)


@router.post("/{slug}/roster/sync", response_model=RosterSyncResult)
def sync_roster(
    slug: str,
    payload: RosterSyncRequest,
    access: OrgAccess = Depends(require_manage_volunteers),
    db: Session = Depends(get_db),
) -> RosterSyncResult:
    """Load a roster from a file or an organization's own live endpoint.

    **The guardrail is the point of this endpoint, not a safety net on it.**
    A run that would deactivate more than `DEACTIVATION_HOLD_FRACTION` of the
    live assignments applies its additions and **holds every deactivation**
    for an admin. A changed API field at 4am must not release three hundred
    roles and blank the coverage report before anyone wakes up - and an org's
    IT department changing a column name is a Tuesday, not a catastrophe, so
    the app has to survive it without help.

    The held people are returned by id rather than merely counted, so the
    screen can show an admin exactly who would have been released instead of
    asking them to trust a number.

    Every run writes a `RosterSyncRun` - who, when, what changed - which is
    the audit row that made writing this over HTTP defensible in the first
    place.
    """
    live = (
        db.query(MaintainerAssignment)
        .filter(
            MaintainerAssignment.club_id == access.club.id,
            MaintainerAssignment.effective_to.is_(None),
        )
        .all()
    )
    live_by_person: dict[str, list[MaintainerAssignment]] = {}
    for assignment in live:
        live_by_person.setdefault(assignment.maintainer_id, []).append(assignment)

    roles_by_name = {
        role.name.strip().lower(): role for role in db.query(OrgRole).filter(OrgRole.club_id == access.club.id).all()
    }
    claimed = {
        invite.email: invite.claimed_by
        for invite in db.query(RoleInvite).filter(RoleInvite.club_id == access.club.id, RoleInvite.claimed_by.isnot(None)).all()
    }

    incoming_active_people: set[str] = set()
    added = updated = 0

    for entry in payload.entries:
        person_id = claimed.get(entry.email)
        if entry.active and person_id:
            incoming_active_people.add(person_id)

        if not entry.active:
            continue

        if person_id is None:
            # Never signed in. An invite is the grant that waits for them -
            # #1169's problem 3 - and a duplicate invite is a no-op rather
            # than an error, because a roster re-uploaded weekly contains
            # every name every time.
            role = roles_by_name.get((entry.role_name or "").strip().lower())
            exists = (
                db.query(RoleInvite)
                .filter(
                    RoleInvite.club_id == access.club.id,
                    RoleInvite.email == entry.email,
                    RoleInvite.role_id == (role.id if role else None),
                    RoleInvite.grants_admin_seat.is_(False),
                    RoleInvite.claimed_at.is_(None),
                )
                .first()
            )
            if exists is None:
                db.add(
                    RoleInvite(
                        club_id=access.club.id,
                        email=entry.email,
                        role_id=role.id if role else None,
                        full_name=entry.full_name,
                        invited_by=access.person_id,
                    )
                )
                added += 1
            else:
                updated += 1
            continue

        if person_id not in live_by_person:
            role = roles_by_name.get((entry.role_name or "").strip().lower())
            db.add(
                MaintainerAssignment(
                    maintainer_id=person_id,
                    club_id=access.club.id,
                    role_id=role.id if role else None,
                    start_mile=0.0,
                    end_mile=0.0,
                    effective_from=date.today(),
                    # Stamped either way, as `create_assignment` does. A
                    # supervisor's sync used to write neither stamp, which
                    # is the shape only the reviewed-file loader may have
                    # (`core/assignments.py`'s `stood_behind`, #1635) - so
                    # a proposal nobody confirmed read as a maintainer's row.
                    proposed_by=None if access.is_admin else access.person_id,
                    confirmed_by=access.person_id if access.is_admin else None,
                    confirmed_at=utc_now() if access.is_admin else None,
                )
            )
            added += 1
        else:
            updated += 1

    # Everybody with a live assignment the feed no longer lists as active.
    would_deactivate = [person for person in live_by_person if person not in incoming_active_people]
    live_people = len(live_by_person)
    over_the_hold = bool(live_people and (len(would_deactivate) / live_people) > DEACTIVATION_HOLD_FRACTION)

    deactivated = 0
    held: list[str] = []
    held_reason = None
    if over_the_hold:
        held = would_deactivate
        held_reason = (
            f"This run would have released {len(would_deactivate)} of {live_people} people - "
            f"more than {int(DEACTIVATION_HOLD_FRACTION * 100)}%. "
            "Everything it added is in. Nothing was released; check the list and confirm it yourself."
        )
    else:
        for person in would_deactivate:
            for assignment in live_by_person[person]:
                assignment.effective_to = date.today()
                deactivated += 1

    run = RosterSyncRun(
        club_id=access.club.id,
        run_by=access.person_id,
        source=payload.source,
        added=str(added),
        updated=str(updated),
        deactivated=str(deactivated),
        deactivations_held=str(len(held)),
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    return RosterSyncResult(
        run_id=run.id,
        added=added,
        updated=updated,
        deactivated=deactivated,
        deactivations_held=len(held),
        held_person_ids=held,
        held_reason=held_reason,
    )
