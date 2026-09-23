"""Grants waiting for somebody who has not signed in yet.

#1169's problem 3, and its decided answer. **OurHike cannot create a user,
deliberately**: `core/auth.py`'s `_get_or_create_profile` provisions a row
from the JWT's `sub`, and minting a Supabase Auth user needs a service-role
key `app/config.py` pointedly does not hold - "a credential that can act as
any user", per features/AUTHENTICATION.md. So the pattern is invite, not
create.

An organization loads a roster of two hundred people, most of whom have never
opened OurHike. Each becomes a `RoleInvite` keyed by email, and the grant is
applied the first time that person signs in.

**Its own module rather than living in `core/org_access.py`**, which is where
it was first written, because `core/auth.py` has to call it at profile
creation and `core/org_access.py` imports `core/auth.py` for
`get_current_user`. Two modules that import each other is a circular import
waiting for whichever one loads second; one small module both can depend on
is not.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.core.time import utc_now
from app.models.club import OrgAdmin
from app.models.org_role import RoleInvite
from app.models.profile import Profile


def normalise_email(email: str) -> str:
    """An address, lowercased and trimmed.

    A roster upload contains both spellings of the same person, and an invite
    that matches only one of them is an invite that silently never applies.
    """
    return email.strip().lower()


def apply_pending_invites(db: Session, profile: Profile, email: str | None) -> list[RoleInvite]:
    """Claim every invite waiting for `email`, now that a profile exists for it.

    **Sound only because the provider verified the address.**
    AUTHENTICATION.md treats a provider-verified email as "a Provider fact to
    trust", and Google and Apple both verify. Against a self-hosted provider
    that skipped verification this would become an account-takeover path -
    anybody could sign up as `chair@ramapotrails.org` and collect its seats.
    That is a constraint on where this backend may be deployed, written here
    because here is where it would bite.

    A claimed invite is kept rather than deleted: it is the audit row saying
    where a role came from, which is what an organization asks when somebody
    turns out to hold something they should not.
    """
    if not email:
        return []

    pending = db.query(RoleInvite).filter(RoleInvite.email == normalise_email(email), RoleInvite.claimed_at.is_(None)).all()
    if not pending:
        return []

    now = utc_now()
    for invite in pending:
        invite.claimed_at = now
        invite.claimed_by = profile.id
        _seat_from(db, invite, profile, now)
    db.commit()
    return pending


def _seat_from(db: Session, invite: RoleInvite, profile: Profile, now: datetime) -> None:
    """Turn an admin invitation into the seat it was always promising.

    **An invite with `grants_admin_seat` is an admin invitation, and nothing
    else is.** `routers/clubs.py` sets it when an organization registers or
    an admin invites a colleague. Until #1635 - The organization console's
    new endpoints trust self-registered orgs with maintainer powers, seats
    and mail - the test here was "no `role_id`", and a supervisor's
    `invite_volunteer` or a roster row whose role matched nothing wrote that
    same shape, so either could mint a seat.

    Nothing did this until #1547's review found it, and the consequence was
    not a missing convenience: an organization registered through the
    product had exactly one admin, permanently, so `is_codeowner`'s
    three-approvals rule - which every registry change needs - could not be
    satisfied by anybody, ever.

    **The seat arrives un-approved.** Being invited is not agreeing, and
    `approve_seat` is where the person says yes. `is_codeowner` is false for
    the same reason: the three codeowners are a decision the organization
    makes, not a side effect of being named on a form.
    """
    if not invite.grants_admin_seat:
        return
    already = db.query(OrgAdmin).filter(OrgAdmin.club_id == invite.club_id, OrgAdmin.person_id == profile.id).one_or_none()
    if already is not None:
        return
    db.add(
        OrgAdmin(
            club_id=invite.club_id,
            person_id=profile.id,
            title=invite.note,
            is_codeowner=False,
            # The organization's own date, not today's: the invitation was
            # issued when they sent it, and a roster showing "invited today"
            # for a message sent in March would be wrong about the one thing
            # the column is for.
            invited_at=invite.invited_at or now,
            approved_at=None,
        )
    )
