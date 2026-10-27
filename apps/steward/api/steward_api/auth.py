"""Who is calling: a Supabase access token, verified, mapped to a steward_user row.

The verification is backend/app/core/auth.py's, copied rather than imported:
the two services deploy separately, and importing backend's module would
import its settings, which require OurHike's whole environment. What is kept
exactly, because each line of it is a fix with a reason there:

- the token's own `alg` header selects the key, and each branch is pinned to
  one key source: ES256/RS256 to the project's JWKS, HS256 to a configured
  secret, anything else refused (no algorithm confusion);
- `exp` is required, and the audience is checked;
- an unknown `kid` forces at most one JWKS fetch a minute, so random `kid`s
  cannot turn every request into an outbound call (backend's #1754);
- a JWKS that cannot be fetched is a 503, not a 401.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from functools import cached_property

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from steward_api.config import Settings
from steward_api.db import get_db
from steward_api.models import StewardUser

ASYMMETRIC_ALGORITHMS = ("ES256", "RS256")

#: `@unvalidated`, both: backend/app/core/auth.py's values, for its reasons.
JWKS_FORCED_REFRESH_MIN_SECONDS = 60.0
JWKS_FETCH_TIMEOUT_SECONDS = 5.0

bearer_scheme = HTTPBearer(auto_error=False)


class _ThrottledJWKClient(jwt.PyJWKClient):
    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self._refresh_lock = threading.Lock()
        self._last_forced_refresh: float | None = None

    def get_signing_keys(self, refresh: bool = False) -> list:
        if refresh:
            with self._refresh_lock:
                now = time.monotonic()
                last = self._last_forced_refresh
                if last is not None and now - last < JWKS_FORCED_REFRESH_MIN_SECONDS:
                    refresh = False
                else:
                    self._last_forced_refresh = now
        return super().get_signing_keys(refresh=refresh)


class TokenVerifier:
    """Verifies one project's tokens. `signing_key` is a seam for tests, which
    sign with a key of their own rather than fetch anybody's JWKS."""

    def __init__(self, settings: Settings, signing_key: Callable[[str], object] | None = None) -> None:
        self.settings = settings
        self._signing_key = signing_key

    @cached_property
    def _jwks(self) -> jwt.PyJWKClient:
        return _ThrottledJWKClient(
            f"{self.settings.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json", timeout=JWKS_FETCH_TIMEOUT_SECONDS
        )

    def signing_key(self, token: str) -> object:
        if self._signing_key is not None:
            return self._signing_key(token)
        return self._jwks.get_signing_key_from_jwt(token).key

    def verify(self, token: str) -> dict:
        algorithm = jwt.get_unverified_header(token).get("alg")
        if algorithm in ASYMMETRIC_ALGORITHMS:
            key: object = self.signing_key(token)
        elif algorithm == "HS256":
            if not self.settings.supabase_jwt_secret:
                raise jwt.InvalidKeyError("Token is signed with HS256 but STEWARD_SUPABASE_JWT_SECRET is not set.")
            key = self.settings.supabase_jwt_secret
        else:
            raise jwt.InvalidAlgorithmError(f"Unsupported signing algorithm: {algorithm!r}")
        audience = self.settings.jwt_audience
        return jwt.decode(
            token,
            key,
            algorithms=[algorithm],
            options={"require": ["exp", "sub"], **({} if audience else {"verify_aud": False})},
            **({"audience": audience} if audience else {}),
        )


def current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> StewardUser:
    """The caller's row, made on first sight. 401 without a valid token."""
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not signed in", headers={"WWW-Authenticate": "Bearer"})
    verifier: TokenVerifier = request.app.state.verifier
    try:
        claims = verifier.verify(credentials.credentials)
    except jwt.PyJWKClientConnectionError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "The sign-in keys could not be fetched, so this token could not be checked. Try again shortly.",
            headers={"Retry-After": "30"},
        ) from exc
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Invalid or expired token", headers={"WWW-Authenticate": "Bearer"}
        ) from exc

    user_id = str(claims["sub"])
    if not user_id or len(user_id) > 64:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token subject is not usable")
    user = db.get(StewardUser, user_id)
    if user is None:
        db.add(StewardUser(id=user_id))
        try:
            db.commit()
        except IntegrityError:
            # A person's parallel first requests race to create the row; the
            # loser takes the winner's (backend's #658).
            db.rollback()
        user = db.get(StewardUser, user_id)
        if user is None:
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Could not create the account row")
    return user
