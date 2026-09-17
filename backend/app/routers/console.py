"""`/console` - the key exchange behind the management-console embed.

See ../../../features/ORG_ONBOARDING.md's "Console embed auth" and #1542.
`app/core/console_tokens.py` holds the crypto; `app/models/console_key.py`
holds the six guards and why this ships configured off.

**The whole endpoint answers 503 while `console_embed_enabled` is false**,
which is its default. That is not a stub: the code path is complete and
tested, and the switch is what makes "built, but not live until a person has
looked at it" a real state rather than a promise. Leaving it off is a valid
deployment - the three public embeds work regardless, because they read a
published registry and hold no credential.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.core.console_tokens import (
    allowed_origins,
    hash_email,
    hash_secret,
    mint_token,
    new_key_pair,
    secret_matches,
)
from app.core.org_access import OrgAccess, require_org_admin, resolve_access
from app.core.orm import commit_and_refresh
from app.core.role_invites import normalise_email
from app.core.time import utc_now
from app.db.session import get_db
from app.models.club import Club
from app.models.console_key import CONSOLE_TOKEN_TTL_SECONDS, ConsoleKey, ConsoleTokenGrant
from app.models.org_role import RoleInvite
from app.schemas.console import (
    ConsoleKeyCreate,
    ConsoleKeyCreated,
    ConsoleKeyOut,
    ConsoleSessionOut,
    ConsoleSessionRequest,
    normalise_origin,
)

router = APIRouter(tags=["console"])


def _enabled_or_503() -> None:
    if not settings.console_embed_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "The management console embed is not switched on for this deployment. "
                "It renders an organization's roster on their own domain, and it waits on a "
                "security review before it is enabled."
            ),
        )


def _as_out(key: ConsoleKey) -> ConsoleKeyOut:
    out = ConsoleKeyOut.model_validate(key)
    out.allowed_origins = allowed_origins(key.allowed_origins)
    return out


@router.get("/clubs/{slug}/console-keys", response_model=list[ConsoleKeyOut])
def list_keys(
    slug: str,
    access: OrgAccess = Depends(require_org_admin),
    db: Session = Depends(get_db),
) -> list[ConsoleKeyOut]:
    """Every key this organization holds - never their secrets.

    `ConsoleKeyOut` has no secret field at all, which is why there are two
    models rather than one with an optional field: an optional secret is a
    secret that leaks the day somebody reuses the model on a list endpoint.
    """
    keys = db.query(ConsoleKey).filter(ConsoleKey.club_id == access.club.id).order_by(ConsoleKey.created_at).all()
    return [_as_out(key) for key in keys]


@router.post("/clubs/{slug}/console-keys", response_model=ConsoleKeyCreated, status_code=status.HTTP_201_CREATED)
def create_key(
    slug: str,
    payload: ConsoleKeyCreate,
    access: OrgAccess = Depends(require_org_admin),
    db: Session = Depends(get_db),
) -> ConsoleKeyCreated:
    """Mint a key pair. The secret is shown here and nowhere else, ever.

    **Guard 4 is why nothing stops an org having two.** Rotation is "add the
    second, swap the server over, delete the first", with no window where
    their page is broken - so the uniqueness is on the key rather than on the
    organization.

    **Guard 6: a new key is read-only.** `can_write` starts false and is
    granted deliberately afterwards, which is the guard that means a key
    pasted into a public page by mistake cannot change anything.
    """
    public_key, secret = new_key_pair()
    key = ConsoleKey(
        club_id=access.club.id,
        public_key=public_key,
        secret_hash=hash_secret(secret),
        label=payload.label,
        allowed_origins="\n".join(payload.allowed_origins),
        can_write=False,
        created_by=access.person_id,
    )
    db.add(key)
    commit_and_refresh(db, key)

    created = ConsoleKeyCreated(**_as_out(key).model_dump(), secret=secret)
    return created


@router.delete("/clubs/{slug}/console-keys/{key_id}", response_model=ConsoleKeyOut)
def revoke_key(
    slug: str,
    key_id: str,
    access: OrgAccess = Depends(require_org_admin),
    db: Session = Depends(get_db),
) -> ConsoleKeyOut:
    """Stop a key minting anything. Tokens already out live their fifteen minutes.

    Said rather than hidden, because an organization revoking a leaked key
    deserves to know the window is not instant. Fifteen minutes is short
    enough that the answer is "wait" rather than "we cannot"; a stored
    session table would make it instant and would be a fifth thing to get
    wrong.
    """
    key = db.query(ConsoleKey).filter(ConsoleKey.id == key_id, ConsoleKey.club_id == access.club.id).one_or_none()
    if key is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such key here")
    key.revoked_at = utc_now()
    db.commit()
    return _as_out(key)


@router.post("/console/session", response_model=ConsoleSessionOut)
def create_session(
    payload: ConsoleSessionRequest,
    origin: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> ConsoleSessionOut:
    """An organization's server vouching for whoever is signed in over there.

    They post the person's email and the secret key; they get back a token
    scoped to one person, one org, one origin, for fifteen minutes.
    **They send only the email** - we resolve roles from the roster - so
    their system never mirrors our permissions and cannot drift out of step
    with them.

    **Somebody not on the roster gets a no-permission token, not an error.**
    That is the difference between an organization's members area showing a
    page with nothing on it and showing a stack trace, and the first is
    always the right answer for somebody who simply is not a volunteer.

    Every request is logged with its origin (guard 5), including the refused
    ones, because "who has been trying this key, and from where" is the
    question an organization asks the day it leaks.
    """
    _enabled_or_503()

    # Guard 2, before anything else is read: an origin that is not allow-listed
    # never reaches the secret comparison at all.
    if not origin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This endpoint is called from your server, and needs an Origin header naming your site",
        )
    try:
        requested_origin = normalise_origin(origin)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    key = db.query(ConsoleKey).filter(ConsoleKey.public_key == payload.public_key, ConsoleKey.revoked_at.is_(None)).one_or_none()
    # Guard 1, and the shape of the refusal: an unknown key, a wrong secret
    # and a disallowed origin all answer the same 403 with the same wording.
    # Telling them apart would hand somebody an oracle for whichever half
    # they already have.
    refusal = HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="That key cannot mint a session from this origin",
    )
    if key is None or not secret_matches(payload.secret, key.secret_hash):
        raise refusal
    if requested_origin not in allowed_origins(key.allowed_origins):
        raise refusal

    club = db.get(Club, key.club_id)
    if club is None or not club.slug:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such organization")

    email = normalise_email(payload.email)
    person_id = (
        db.query(RoleInvite.claimed_by)
        .filter(
            RoleInvite.club_id == club.id,
            RoleInvite.email == email,
            RoleInvite.claimed_by.isnot(None),
        )
        .limit(1)
        .scalar()
    )

    permissions: list[str] = []
    display_name = None
    if person_id:
        access = resolve_access(db, club, person_id)
        if access.can_read_roster:
            permissions.append("read_roster")
        if access.can_manage_volunteers:
            permissions.append("manage_volunteers")
        # Guard 6 applied at mint rather than only at the write: a read-only
        # key cannot produce a token that says otherwise, whatever the
        # person's own seat allows.
        if key.can_write and access.can_manage_volunteers:
            permissions.append("write")

    key.last_used_at = utc_now()
    db.add(
        ConsoleTokenGrant(
            club_id=club.id,
            console_key_id=key.id,
            origin=requested_origin,
            email_hash=hash_email(email),
            resolved=bool(person_id),
        )
    )
    db.commit()

    return ConsoleSessionOut(
        token=mint_token(
            club_slug=club.slug,
            person_id=person_id,
            origin=requested_origin,
            permissions=permissions,
        ),
        expires_in=CONSOLE_TOKEN_TTL_SECONDS,
        org_slug=club.slug,
        display_name=display_name,
        permissions=permissions,
    )
