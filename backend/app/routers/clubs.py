"""`/clubs` endpoints - registering an organization, and running one.

`Org` is the word every screen uses; `clubs` is the table and the route. See
../../../features/ORG_ONBOARDING.md's conflict 2 for why the route was not
renamed to match the UI, and #1539 for the public half this serves.

**Two rules hold across every endpoint here and are worth reading before the
code:**

*Nothing here publishes anything to a hiker.* Registering, approving, editing
the org's own details - none of it changes a byte on a phone. What reaches a
phone comes out of the pipeline after a person merges a pull request, which
is SOURCE_REGISTRY.md's rule and the thing that makes it safe to give an
outside organization a seat at all.

*Every gate reads the database.* `core/org_access.py` resolves what the
caller may do at this org from the seats they actually hold. The client shows
the union of what they allow and never claims one.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import get_current_email, get_current_user, get_current_user_optional
from app.core.org_access import OrgAccess, club_by_slug, org_access, require_org_admin, resolve_access
from app.core.orm import commit_and_refresh
from app.core.time import utc_now
from app.db.session import get_db
from app.models.club import Club, OrgAdmin, OrgState, VerifiedBy
from app.models.org_role import RoleInvite
from app.models.profile import Profile
from app.schemas.org import (
    OrgAdminInvite,
    OrgAdminOut,
    OrgClaimRequest,
    OrgCreate,
    OrgDeclineRequest,
    OrgNomination,
    OrgOut,
    OrgSettingsUpdate,
)

router = APIRouter(prefix="/clubs", tags=["clubs"])


def _with_admins(db: Session, club: Club) -> OrgOut:
    """One org plus its seats, which is how every screen reads it.

    Assembled here rather than by a relationship because `Club` deliberately
    declares none: the models in this backend are plain tables, and a lazy
    relationship is a query that fires somewhere nobody expected it.
    """
    admins = db.query(OrgAdmin).filter(OrgAdmin.club_id == club.id).order_by(OrgAdmin.invited_at).all()
    out = OrgOut.model_validate(club)
    out.admins = [OrgAdminOut.model_validate(admin) for admin in admins]
    return out


def _domain_of(email: str | None) -> str | None:
    if not email or "@" not in email:
        return None
    return email.rsplit("@", 1)[1].strip().lower()


def _somebody_holds_the_domain(domain: str, addresses: list[str | None]) -> bool:
    """At least one admin on an org's own domain.

    ORG_ONBOARDING.md's form rule, enforced here rather than only in the
    form, because the form is a screen and this is the actual gate. A
    subdomain counts (`trails.ramapotrails.org`), because organizations
    really do run mail that way and refusing it would fail a legitimate
    registration with a message nobody could act on.
    """
    domain = domain.strip().lower()
    for address in addresses:
        candidate = _domain_of(address)
        if candidate and (candidate == domain or candidate.endswith("." + domain)):
            return True
    return False


@router.get("", response_model=list[OrgOut])
def list_orgs(db: Session = Depends(get_db)) -> list[OrgOut]:
    """Every organization anyone may look at.

    Public, and no account needed - the same posture as every other browsing
    endpoint here. A deleted org is excluded; an `unclaimed` one is NOT,
    because an unclaimed org is exactly what the claim flow needs to be able
    to find, and because it has live trails a hiker is already walking.
    """
    clubs = db.query(Club).filter(Club.state != OrgState.deleted).order_by(Club.name).all()
    return [_with_admins(db, club) for club in clubs]


@router.get("/{slug}", response_model=OrgOut)
def read_org(slug: str, db: Session = Depends(get_db)) -> OrgOut:
    """One organization. Public: what an org publishes about itself is public
    by construction - that is what registering is. The roster, the hours and
    the unpublished registry are other resources with their own gates."""
    return _with_admins(db, club_by_slug(db, slug))


@router.get("/{slug}/access")
def read_my_access(access: OrgAccess = Depends(org_access)) -> dict[str, bool | str]:
    """What the caller may do here - the console's sidebar in one request.

    The sidebar shows only the sections the current person's seats permit, so
    it needs this before it can draw itself. Returning it rather than letting
    the client infer it from a roster read is the difference between a
    permission model and a decoration: the client cannot see the seats, and
    should not have to.
    """
    return {
        "org_slug": access.club.slug or "",
        "is_admin": access.is_admin,
        "is_codeowner": access.is_codeowner,
        "is_supervisor": access.is_supervisor,
        "is_volunteer": access.is_volunteer,
        "can_manage_volunteers": access.can_manage_volunteers,
        "can_read_roster": access.can_read_roster,
        "can_touch_registry": access.can_touch_registry,
    }


@router.post("", response_model=OrgOut, status_code=status.HTTP_201_CREATED)
def register_org(
    payload: OrgCreate,
    current_user: Profile = Depends(get_current_user),
    email: str | None = Depends(get_current_email),
    db: Session = Depends(get_db),
) -> OrgOut:
    """Register an organization, naming the caller as its first admin.

    **Signed in, always.** Registering names you as the org's first admin, so
    there is no anonymous path and the form says so before it asks for
    anything else.

    **At least one admin has to hold an email at the org's domain**, checked
    against the caller's *verified* address plus the invited ones. An address
    somebody typed proves nothing; this is the whole verification the design
    asks for, so it is not somewhere to be generous.

    The other admins become `RoleInvite` rows rather than seats, because
    OurHike cannot create a user (#1169's problem 3) - their seat appears the
    moment they first sign in.
    """
    invited = [admin.email for admin in payload.admins]
    if not _somebody_holds_the_domain(payload.domain, [email, *invited]):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"At least one admin needs an email at {payload.domain}. "
                "It is the only thing that shows us this organization is yours."
            ),
        )

    club = Club(
        name=payload.name,
        slug=payload.slug,
        domain=payload.domain,
        website=payload.website,
        region=payload.region,
        membership_url=payload.membership_url,
        donation_url=payload.donation_url,
        # Email at the domain is what was actually checked above. DNS is the
        # stronger proof and is a later, deliberate step - claiming it here
        # would be recording a verification nobody performed.
        verified_by=VerifiedBy.email,
        state=OrgState.claimed,
        created_by=current_user.id,
    )
    db.add(club)
    try:
        commit_and_refresh(db, club)
    except IntegrityError as exc:
        db.rollback()
        # The unique index on `slug` is the only thing that can collide here,
        # and a slug is chosen by a person looking at a form - so it is named
        # rather than surfaced as a 500.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"The address /org/{payload.slug} is taken. Pick another.",
        ) from exc

    now = utc_now()
    # The person registering approves by the act of registering. Their own
    # seat is the first of the three, and the audit trail says so.
    db.add(
        OrgAdmin(
            club_id=club.id,
            person_id=current_user.id,
            title=None,
            is_codeowner=True,
            invited_at=now,
            approved_at=now,
        )
    )
    for admin in payload.admins:
        if email is not None and admin.email == email:
            continue
        db.add(
            RoleInvite(
                club_id=club.id,
                email=admin.email,
                full_name=None,
                note=admin.title,
                invited_by=current_user.id,
                invited_at=now,
            )
        )
    db.commit()
    return _with_admins(db, club)


@router.post("/{slug}/admins", response_model=OrgOut, status_code=status.HTTP_201_CREATED)
def invite_admin(
    slug: str,
    payload: OrgAdminInvite,
    access: OrgAccess = Depends(require_org_admin),
    current_user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OrgOut:
    """Invite another admin - the "replace admin" the approval screen offers.

    Idempotent on the address, because the button next to a person who has
    not answered is "send a reminder" and pressing it twice should not create
    a second pending invite for the same person.
    """
    existing = (
        db.query(RoleInvite)
        .filter(
            RoleInvite.club_id == access.club.id,
            RoleInvite.email == payload.email,
            RoleInvite.claimed_at.is_(None),
        )
        .one_or_none()
    )
    if existing is None:
        db.add(
            RoleInvite(
                club_id=access.club.id,
                email=payload.email,
                note=payload.title,
                invited_by=current_user.id,
            )
        )
        db.commit()
    return _with_admins(db, access.club)


@router.post("/{slug}/admins/{admin_id}/approve", response_model=OrgOut)
def approve_seat(
    slug: str,
    admin_id: str,
    current_user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OrgOut:
    """Say yes to your own seat. Nobody may approve on anybody else's behalf.

    Not gated by `require_org_admin`: the person answering is by definition
    not yet an approved admin, so that gate would refuse exactly the people
    this endpoint exists for. The gate is that the seat is theirs.
    """
    club = club_by_slug(db, slug)
    seat = db.query(OrgAdmin).filter(OrgAdmin.id == admin_id, OrgAdmin.club_id == club.id).one_or_none()
    if seat is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such admin seat")
    if seat.person_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the person invited can answer their own invitation",
        )

    if seat.approved_at is None:
        seat.approved_at = utc_now()
    # A decline is reversible, so approving after declining clears the
    # refusal rather than leaving a row that says both. The audit trail is
    # the endpoint's caller list, not two contradictory columns.
    seat.declined_at = None
    seat.decline_reason = None
    db.commit()
    return _with_admins(db, club)


@router.post("/{slug}/admins/{admin_id}/decline", response_model=OrgOut)
def decline_seat(
    slug: str,
    admin_id: str,
    payload: OrgDeclineRequest,
    current_user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OrgOut:
    """Say no, for now.

    **A decline pauses the organization and is reversible - it is never a
    rejection.** The common cause is a secretary who does not know what
    OurHike is, not a board that said no, and a model that treated the two
    the same would make the recoverable case look final. `approve_seat` above
    is how it is undone, by the same person, whenever they like.
    """
    club = club_by_slug(db, slug)
    seat = db.query(OrgAdmin).filter(OrgAdmin.id == admin_id, OrgAdmin.club_id == club.id).one_or_none()
    if seat is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such admin seat")
    if seat.person_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the person invited can answer their own invitation",
        )

    seat.declined_at = utc_now()
    seat.decline_reason = payload.reason
    seat.approved_at = None
    db.commit()
    return _with_admins(db, club)


@router.post("/{slug}/claim", response_model=OrgOut)
def claim_org(
    slug: str,
    payload: OrgClaimRequest,
    current_user: Profile = Depends(get_current_user),
    email: str | None = Depends(get_current_email),
    db: Session = Depends(get_db),
) -> OrgOut:
    """Claim an organization that has live trails and no admins.

    This is the migration path for every source a maintainer registered by
    hand - 33 of them across nine organizations, counted 2026-08-27 - rather
    than a new concept. An unclaimed org is precisely one of those: its
    trails are already on phones and nobody at the organization has a seat.

    **An email at the org's domain is the whole check**, and it is the
    verified one from the token.

    **A contested claim freezes and waits for a person.** Two people at the
    same domain claiming the same org is not a race to be won, so `frozen`
    has no automatic exit - a timer would resolve the contest in favour of
    whoever was patient.
    """
    club = club_by_slug(db, slug)

    if club.state == OrgState.frozen:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Somebody else at this domain has already claimed this organization. "
                "We have paused it for a person to look at, and we will be in touch with both of you."
            ),
        )
    if club.state == OrgState.claimed:
        # Already somebody's. Freezing it is the honest answer rather than
        # adding a second admin silently: the people who already hold this
        # org get to decide who else does.
        club.state = OrgState.frozen
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This organization already has admins. We have paused it and a person will "
                "check whether you should be one of them."
            ),
        )

    if not club.domain:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "We do not hold a domain for this organization yet, so there is nothing to check "
                "your address against. Nominate it instead and a person will pick it up."
            ),
        )
    if not _somebody_holds_the_domain(club.domain, [email]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Claiming this organization needs an email at {club.domain}.",
        )

    now = utc_now()
    club.state = OrgState.claimed
    club.verified_by = VerifiedBy.email
    club.created_by = club.created_by or current_user.id
    db.add(
        OrgAdmin(
            club_id=club.id,
            person_id=current_user.id,
            title=payload.title,
            is_codeowner=True,
            invited_at=now,
            approved_at=now,
        )
    )
    db.commit()
    return _with_admins(db, club)


@router.patch("/{slug}", response_model=OrgOut)
def update_org(
    slug: str,
    payload: OrgSettingsUpdate,
    access: OrgAccess = Depends(require_org_admin),
    db: Session = Depends(get_db),
) -> OrgOut:
    """Change the organization's own details.

    `slug` is not here and cannot be. It is in every route, every embed
    snippet already pasted onto somebody's website, and every pull-request
    path - changing it silently breaks all three.
    """
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(access.club, field, value)
    db.commit()
    return _with_admins(db, access.club)


@router.delete("/{slug}", status_code=status.HTTP_204_NO_CONTENT)
def delete_org(
    slug: str,
    response: Response,
    access: OrgAccess = Depends(require_org_admin),
    db: Session = Depends(get_db),
) -> Response:
    """Leave. The org's rows stop being reachable; its volunteers' do not.

    **Hours and reports belong to the volunteer and survive the organization
    deleting itself.** Nothing here touches `volunteer_hours`, `reports` or
    `field_notes` - a person's own record is theirs, and an org winding up is
    not an event that erases somebody else's logbook.

    A soft delete for the same reason `profiles` uses one: other tables hold
    NOT NULL foreign keys to this id on rows that are somebody else's
    business, and taking them with it or dangling the key are both worse than
    a row that says it is gone.
    """
    access.club.state = OrgState.deleted
    db.commit()
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.post("/nominations", status_code=status.HTTP_202_ACCEPTED)
def nominate_org(
    payload: OrgNomination,
    current_user: Profile | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """A hiker submitting an organization's trails on its behalf.

    **This creates nothing and publishes nothing.** It records an unclaimed
    org so a maintainer can look at it, and a maintainer reading terms by
    hand is still what turns it into a source - which is the honest state of
    SOURCE_REGISTRY.md today rather than a shortcut around it.

    The hiker is not claiming to speak for the organization and is not asked
    to. They know their local club has trails and roughly where to find them;
    that is the whole of what this collects.
    """
    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sign in first, so we can come back to you if we have a question",
        )

    club = Club(
        name=payload.name,
        website=payload.website,
        region=payload.region,
        state=OrgState.unclaimed,
        created_by=current_user.id,
    )
    db.add(club)
    db.commit()
    return {
        "status": "received",
        "detail": (
            "Thank you. A person reads every one of these - we check who owns the data and "
            "what their terms say before anything of theirs reaches a map."
        ),
    }


@router.get("/{slug}/export")
def export_org(
    slug: str,
    access: OrgAccess = Depends(require_org_admin),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """Everything this organization has here, as JSON, with no notice needed.

    Value #6's portability commitment pointed at an organization rather than
    a hiker: they can take their data and leave without asking us. Deliberately
    one endpoint rather than a job with an email at the end - an export you
    have to request and wait for is an export that quietly stops working.

    **THE ROSTER IS IN IT, AND IT IS WHY THIS IS ADMIN-ONLY.** Everything
    else here is already published - the registry, the workdays, the org's own
    details - so an export without the roster would be a file an organization
    could have rebuilt from the map, sitting behind an admin check with
    nothing left to protect. The roster is the one thing on this endpoint that
    rule 4 keeps unpublished, and it is theirs to take.

    **IT CARRIES NAMES AND ADDRESSES, WHICH IS THE POINT AND THE RISK.** An
    organization leaving needs to reach its own volunteers; that is the whole
    of value #6's portability promise pointed at an org rather than a hiker.
    It is also why nothing below is reachable by a supervisor - `can_read_roster`
    would be enough to read the roster screen and is deliberately not enough to
    download it - and why the volunteer's own hours and reports are NOT here.
    Those belong to the person, travel with them when the organization is
    deleted, and are theirs to export from their own account.
    """
    from app.models.org_registry import OrgPark, OrgSection, OrgTrail
    from app.models.org_role import OrgRole
    from app.models.work_project import WorkProject
    from app.routers.org_roles import read_roster

    club = access.club
    parks = db.query(OrgPark).filter(OrgPark.club_id == club.id).all()
    park_ids = [park.id for park in parks]
    trails = db.query(OrgTrail).filter(OrgTrail.park_id.in_(park_ids)).all() if park_ids else []
    trail_ids = [trail.id for trail in trails]
    sections = db.query(OrgSection).filter(OrgSection.trail_id.in_(trail_ids)).all() if trail_ids else []

    def row(obj: object, fields: tuple[str, ...]) -> dict[str, object]:
        return {field: getattr(obj, field) for field in fields}

    return {
        "org": row(club, ("id", "slug", "name", "domain", "website", "region", "membership_url", "donation_url")),
        "parks": [row(p, ("id", "name", "kind")) for p in parks],
        "trails": [row(t, ("id", "park_id", "name", "blaze_value_raw", "blaze_mapped", "miles")) for t in trails],
        "sections": [
            row(s, ("id", "trail_id", "name", "start_anchor", "end_anchor", "start_mile", "end_mile", "region")) for s in sections
        ],
        "roles": [
            row(r, ("id", "name", "category", "reports_to_role_id", "section_id", "required", "required_by"))
            for r in db.query(OrgRole).filter(OrgRole.club_id == club.id).all()
        ],
        "workdays": [
            row(w, ("id", "title", "starts_on", "ends_on", "meet_point", "status", "cap", "source"))
            for w in db.query(WorkProject).filter(WorkProject.club_id == club.id).all()
        ],
        "admins": [
            row(a, ("id", "person_id", "title", "is_codeowner", "approved_at", "declined_at"))
            for a in db.query(OrgAdmin).filter(OrgAdmin.club_id == club.id).all()
        ],
        # Assembled by the roster endpoint rather than re-queried here, so the
        # file an organization downloads and the screen they read it on cannot
        # answer differently. Two assemblies of the same list is how an export
        # quietly starts omitting the pending invites.
        "roster": [entry.model_dump() for entry in read_roster(slug, access=access, db=db)],
    }


__all__ = ["router", "resolve_access"]
