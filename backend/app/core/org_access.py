"""Who may do what, at one organization.

See ../../../features/ORG_ONBOARDING.md's permissions table. Four tiers, and
the sentence that shapes this whole module:

    A person can hold several at once, and the UI shows the union of what
    they allow - never a role picker.

**So there is no "current role" anywhere in this file.** A caller asks "may
this person do X at this org", and the answer is computed from every seat
they hold. Somebody who is a trails chair at Ramapo and a maintainer at
Hudson Highlands is the normal case, not the edge one, and a model with a
single active role would make them choose.

**Why this is org-scoped rather than `Profile.role`.** #1169 decided on
2026-08-28 that `Profile.role` should become a set, because a club admin who
also coordinates invasives has to pick one and the next person to hit the
wall widens some gate. That is right, and it points here: almost every role
in this design is a fact about a person **and an organization**, and no set
of global enum values can say that without inventing a value per
organization. `Profile.role` keeps doing its own job - gating the moderation
queue - and this answers the org questions.

**The client never claims a tier.** Every gate here reads the database. A
flag in the client's state is a display detail; if it were a gate, the
permission model would be whatever the browser said it was.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_email, get_current_user
from app.core.role_invites import apply_pending_invites, normalise_email
from app.db.session import get_db
from app.models.club import Club, OrgAdmin, OrgState
from app.models.maintainer_assignment import MaintainerAssignment
from app.models.org_role import OrgRole, RoleInvite
from app.models.profile import MODERATOR_ROLES, Profile


@dataclass(frozen=True)
class OrgAccess:
    """What one person may do at one organization, resolved once per request.

    A frozen dataclass rather than a dict so a typo in a caller
    (`access.is_admn`) is an AttributeError here rather than a silently
    falsy permission check somewhere a roster gets rendered.
    """

    club: Club
    person_id: str

    # An approved admin. A pending or declined seat is not one - `approved_at`
    # is the gate, so an invited secretary who has not answered cannot
    # publish a registry.
    is_admin: bool

    # A codeowner among the admins. Three of these approve a registry change;
    # everything else takes one admin.
    is_codeowner: bool

    # Somebody who supervises other volunteers here: they hold a role that
    # another live role reports to. Derived rather than stored, because
    # "supervisor" is a position in the reporting line rather than a title
    # somebody is given, and storing it would let the two disagree.
    is_supervisor: bool

    # Anybody with a live assignment at this org, admins included.
    is_volunteer: bool

    @property
    def can_manage_volunteers(self) -> bool:
        """Workdays, signup replies, hours confirmation, roster loading.

        Admins and supervisors both. Running crews is a job supervisors and
        chairs already do off-app; the registry and the org's own details
        stay with the codeowners.
        """
        return self.is_admin or self.is_supervisor

    @property
    def can_read_roster(self) -> bool:
        """Names, emails and assignments - everything rule 4 keeps unpublished."""
        return self.is_admin or self.is_supervisor

    @property
    def can_touch_registry(self) -> bool:
        return self.is_admin


def resolve_access(db: Session, club: Club, person_id: str) -> OrgAccess:
    """Every seat `person_id` holds at `club`, as one answer."""
    seat = db.query(OrgAdmin).filter(OrgAdmin.club_id == club.id, OrgAdmin.person_id == person_id).one_or_none()
    is_admin = seat is not None and seat.approved_at is not None
    is_codeowner = bool(is_admin and seat is not None and seat.is_codeowner)

    live_assignments = (
        db.query(MaintainerAssignment)
        .filter(
            MaintainerAssignment.club_id == club.id,
            MaintainerAssignment.maintainer_id == person_id,
            MaintainerAssignment.effective_to.is_(None),
        )
        .all()
    )
    # A proposal nobody has confirmed holds no role yet (#1635). Counting it
    # let a supervisor propose a friend into a lead role and so make them a
    # supervisor - able to invite, sync and propose in turn - with no admin
    # having agreed to any of it. `is_volunteer` below still counts the
    # proposal: it lets somebody step back from it, which grants nothing.
    held_role_ids = {
        a.role_id for a in live_assignments if a.role_id is not None and (a.proposed_by is None or a.confirmed_at is not None)
    }

    # A supervisor is somebody a live role reports to. `retired_at is None`
    # on the reporting role, because a retired role's holders are history and
    # supervising history is not a permission.
    is_supervisor = False
    if held_role_ids:
        is_supervisor = (
            db.query(OrgRole.id)
            .filter(
                OrgRole.club_id == club.id,
                OrgRole.reports_to_role_id.in_(held_role_ids),
                OrgRole.retired_at.is_(None),
            )
            .first()
            is not None
        )

    return OrgAccess(
        club=club,
        person_id=person_id,
        is_admin=is_admin,
        is_codeowner=is_codeowner,
        is_supervisor=is_supervisor,
        is_volunteer=bool(live_assignments),
    )


NO_SUCH_ORGANIZATION = "No such organization"


def club_by_slug(db: Session, slug: str) -> Club:
    """The org a route names, or 404.

    A deleted org answers 404 rather than 410: a person who should not know
    an org ever existed learns nothing from a 404, and the only people
    entitled to know it was deleted already have its export.

    **A HELD (`pending`) REGISTRATION IS FOUND HERE AND HIDDEN FROM THE
    PUBLIC READS**, which ask `club_for_a_public_read` below instead: `GET
    /clubs/{slug}`, `GET /clubs/{slug}/scoreboard` and `GET
    /clubs/{slug}/registry`. They served a `pending` org's name, domain,
    website and typed links to anybody with the slug (the 2026-11-04
    security review), while `list_orgs` and `list_workdays` hid it because
    listing it "puts our word behind a row a stranger typed" - and a slug is
    no secret: it is in the embed snippet and the console's address. A
    `pending` org is one whose only address at its domain was typed by the
    registrant for somebody else (`OrgState`), so the organization may not
    know it exists here, and nothing about it is published until somebody
    at the domain agrees.

    Not hidden in this function itself, because the paths that end a held
    registration have to find it for people who hold nothing there yet:
    `claim_org` (the real organization claiming over a stranger's
    registration), `approve_seat` and `org_access`, which turns a waiting
    invitation into a seat. Two kinds of caller still read it through the
    public routes: **a moderator**, because a held registration is what
    "a person has to pick it up" hands them; and **somebody holding a seat
    on it** - the registrant, and every admin they named, who needs the
    console to see the seat waiting for them and say yes or no - which is
    the same `OrgAdmin` row `_as_viewer_reads_it` in routers/clubs.py reads
    as "own seat", approved or not.
    """
    club = db.query(Club).filter(Club.slug == slug).one_or_none()
    if club is None or club.state == OrgState.deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NO_SUCH_ORGANIZATION)
    return club


def club_for_a_public_read(db: Session, slug: str, viewer: Profile | None, email: str | None) -> Club:
    """`club_by_slug` for a read anybody may make, with a held registration answering 404 to most.

    `viewer` is None when anonymous; `email` is the caller's verified
    address from the token, or None. `club_by_slug`'s docstring says why
    `pending` is hidden and who still sees it. The 404 is the same status
    and sentence as a slug nobody registered, so it does not tell a stranger
    that a held registration exists.
    """
    club = club_by_slug(db, slug)
    if club.state == OrgState.pending and not _reads_a_held_registration(db, club, viewer, email):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NO_SUCH_ORGANIZATION)
    return club


def _reads_a_held_registration(db: Session, club: Club, viewer: Profile | None, email: str | None) -> bool:
    """A moderator, a seat holder, or somebody an admin invitation is about to seat.

    **THE INVITATION COUNTS BECAUSE THE CONSOLE RACES ITS OWN SEAT.**
    `useOrgData` in client/src/org/OrgConsole.tsx fetches `GET
    /clubs/{slug}` and `GET /clubs/{slug}/access` together
    (`Promise.all`), and `org_access` is where a waiting admin invitation
    becomes a seat for somebody who already had an account. So the first
    time an invited secretary opens the console, the read can run before
    their seat is written; refusing it on that ground failed the whole
    console for exactly the person whose approval releases the
    registration. An unclaimed admin invitation at their verified address
    is the seat `_seat_from` in core/role_invites.py will write on that
    same page load (reasoned from the code; not reproduced against a
    browser), so it reads as one here.
    """
    if viewer is None:
        return False
    if viewer.role in MODERATOR_ROLES:
        return True
    seat = db.query(OrgAdmin.id).filter(OrgAdmin.club_id == club.id, OrgAdmin.person_id == viewer.id).first()
    if seat is not None:
        return True
    if not email:
        return False
    invited = (
        db.query(RoleInvite.id)
        .filter(
            RoleInvite.club_id == club.id,
            RoleInvite.email == normalise_email(email),
            RoleInvite.grants_admin_seat.is_(True),
            RoleInvite.claimed_at.is_(None),
        )
        .first()
    )
    return invited is not None


def org_access(
    slug: str,
    current_user: Profile = Depends(get_current_user),
    email: str | None = Depends(get_current_email),
    db: Session = Depends(get_db),
) -> OrgAccess:
    """FastAPI dependency: the caller's access at the org in the path.

    Deliberately does NOT refuse anybody - it resolves, and the endpoint
    decides. A signed-in hiker with no seat gets an `OrgAccess` with every
    flag false, which is what the public org page and the claim flow both
    need, and what the console's own sidebar reads to decide which sections
    to render at all.

    **WAITING INVITES ARE CLAIMED HERE, WHICH IS A WRITE ON A READ PATH.**
    `core/auth.py` claims them when it provisions a profile, and that is the
    only place they were claimed until #1547's review - so an invite written
    AFTER somebody's first sign-in never applied at all, which is every
    invite to a person who already uses OurHike. The address only exists on
    the request's own token (`Profile` stores no email), so there is nowhere
    to do this except a request that carries one.

    Here rather than in `get_current_user`, which is the seam EVERY
    authenticated request crosses and would pay the query. `/clubs/{slug}/
    access` is the console's first call when somebody opens an organization,
    so a person following an invitation lands on it, which is exactly when
    the seat needs to exist.
    """
    apply_pending_invites(db, current_user, email)
    return resolve_access(db, club_by_slug(db, slug), current_user.id)


def require_org_admin(access: OrgAccess = Depends(org_access)) -> OrgAccess:
    if not access.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only an approved admin of this organization can do that",
        )
    return access


def require_manage_volunteers(access: OrgAccess = Depends(org_access)) -> OrgAccess:
    if not access.can_manage_volunteers:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only an admin or a supervisor at this organization can do that",
        )
    return access
