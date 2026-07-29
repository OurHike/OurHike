"""The auth seam: verifying a Supabase-issued JWT and resolving/provisioning
the local Profile row it maps to.

Supabase Auth (../../../features/AUTHENTICATION.md) issues and verifies its
own JWTs on sign-in (Google/Apple/email, MFA, email verification all happen
there) - this backend never issues a token itself, only verifies the one
Supabase's client SDK hands back on each request.

`verify_supabase_jwt` is kept as one small, isolated function on purpose:
*how* to verify isn't fully pinned down yet. A Supabase project can be
configured for either a shared HS256 secret (`SUPABASE_JWT_SECRET`, what's
implemented below) or asymmetric JWKS-based verification, and which one a
real project actually uses isn't knowable until a real Supabase project
exists. Swapping the verification strategy later means editing this one
function, not every call site that depends on it.
"""

from collections.abc import Iterable

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import get_db
from app.models.profile import Profile, Role

# auto_error=False so a missing/malformed Authorization header doesn't short
# -circuit into FastAPI's own default response - `HTTPBearer`'s built-in
# auto_error path returns 403, not 401, on a missing header, which would be
# the wrong status for "not authenticated". get_current_user below raises
# 401 itself instead, in every no-credentials case.
bearer_scheme = HTTPBearer(auto_error=False)


def verify_supabase_jwt(token: str) -> dict:
    """Decode and verify a Supabase-issued JWT, returning its claims.

    Raises `jwt.PyJWTError` (or a subclass, e.g. `InvalidSignatureError` /
    `ExpiredSignatureError`) on a bad signature or an expired token -
    callers are expected to translate that into an HTTP 401, not to treat a
    verification failure as a 500.
    """
    return jwt.decode(token, settings.supabase_jwt_secret, algorithms=["HS256"])


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Profile:
    """Resolve the current Profile from a bearer JWT, provisioning one if needed.

    On first successful verification of a Supabase user id with no matching
    local `profiles` row, a new one is auto-provisioned (role defaults to
    `hiker`) - this is the "at least enough to identify a reporter and a
    moderator" local identity TECHNICAL_ARCHITECTURE.md's Backend section
    calls for, without duplicating Supabase's own user data.
    """
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    try:
        claims = verify_supabase_jwt(credentials.credentials)
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token") from exc

    user_id = claims.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token missing subject claim")

    profile = db.get(Profile, user_id)
    if profile is None:
        profile = Profile(id=user_id, role=Role.hiker)
        db.add(profile)
        db.commit()
        db.refresh(profile)

    return profile


def require_role(*roles: str):
    """Return a FastAPI dependency that only lets the given roles through.

    `roles` are plain strings (e.g. "maintainer", "club_admin") - `Role` is a
    `str` subclass, so `profile.role` compares equal to the matching string
    directly, no need to coerce either side.
    """

    def dependency(profile: Profile = Depends(get_current_user)) -> Profile:
        allowed: Iterable[str] = roles
        if profile.role not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return profile

    return dependency
