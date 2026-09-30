"""Minting and reading the management-console embed's scoped tokens.

See ../../../features/ORG_ONBOARDING.md's "Console embed auth", #1542, and
`app/models/console_key.py` for the six guards.

**This is a first-party credential rendering an organization's roster on a
third-party origin, and nobody has security-reviewed it.** The maintainer's
call on 2026-09-17 was to build all four embeds including this one, against a
recommendation to stop at the three public ones. It ships behind
`settings.console_embed_enabled`, which defaults False - the same posture the
five `R2_PHOTO_*` settings already take, where leaving them unset is a valid
deployment that simply cannot serve photos.

**Signed, not stored.** A token carries its own claims under an HMAC over the
backend's existing JWT secret material; there is no session table. A stored
session would be a fifth thing to revoke and a fifth thing to get wrong, and
the fifteen-minute life is what makes storage unnecessary: revoking the key
stops the next mint, and the worst case is one window of one person's
read-only view.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time

from app.config import settings
from app.models.console_key import CONSOLE_TOKEN_TTL_SECONDS

# What a console token may say the holder can do. Deliberately coarse: the
# embed decides what to draw, and the backend re-checks every write against
# the roster anyway. A permission list that were the only gate would be a
# permission model living in a string.
CONSOLE_PERMISSIONS = ("read_roster", "manage_volunteers", "write")


class ConsoleKeyMaterialMissing(RuntimeError):
    """`supabase_jwt_secret` is unset, so nothing here can be signed safely."""


def _signing_key() -> bytes:
    """The key these tokens are signed with.

    Derived from the secret this deployment already holds rather than adding
    a sixth environment variable nobody would remember to rotate. HKDF-style
    domain separation via a fixed label, so a console token can never be
    mistaken for - or replayed as - a Supabase one.

    **IT IS `supabase_jwt_secret` AND NOTHING ELSE, AND AN UNSET ONE RAISES.**
    The first version of this fell back to `supabase_anon_key` and then to
    `""`, which was a forgeable-token bug in two directions and is the reason
    this docstring is long:

    - The anon key is **published to every browser**: `client/.env.example`
      names it `your-anon-public-key` and `lib/supabase.ts` reads it from the
      bundle. Signing with it means anybody who opens the app's JavaScript can
      mint a console token claiming any org, any person and `perms: ["write"]`.
    - The `""` fallback was worse. It made the signing key a fixed value
      derivable from this file, which is in a public repository.

    Neither was reachable in a deployment that set the JWT secret, and
    `console_embed_enabled` defaults False, so nothing shipped forgeable. But
    a deployment CAN legitimately set the anon key and not the JWT secret -
    the anon key is what the client needs - and that configuration silently
    produced signable tokens. Raising turns a silent forgery into a loud
    misconfiguration, which is the only version of this a person notices.
    """
    base = (settings.supabase_jwt_secret or "").encode("utf-8")
    if not base:
        raise ConsoleKeyMaterialMissing(
            "The console embed needs SUPABASE_JWT_SECRET set. It is never signed with the anon key, "
            "which is published to every browser."
        )
    return hmac.new(b"ourhike-console-embed-v1", base, hashlib.sha256).digest()


def new_key_pair() -> tuple[str, str]:
    """A public key and a secret, for one organization.

    The public half is in the HTML of somebody's website by design, so it is
    prefixed to be recognisable in a support conversation. The secret is
    returned once and stored only as a hash.
    """
    return f"ohk_{secrets.token_urlsafe(18)}", f"ohs_{secrets.token_urlsafe(32)}"


def hash_secret(secret: str) -> str:
    """A bare SHA-256, and that is correct here rather than a shortcut.

    A password KDF - bcrypt, argon2 - exists to make guessing a LOW-entropy
    human-chosen string expensive. `new_key_pair` returns
    `secrets.token_urlsafe(32)`: 256 bits from the OS CSPRNG, with no
    dictionary to guess from and nothing for a work factor to slow down. The
    reason to say so in a comment is that "SHA-256 on a credential" is the
    right thing to flag on sight, and the next reader should be able to settle
    it here rather than by changing it.
    """
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def secret_matches(secret: str, stored_hash: str) -> bool:
    """Constant-time, because a timing comparison on a credential is a
    credential that can be guessed a byte at a time."""
    return hmac.compare_digest(hash_secret(secret), stored_hash)


def hash_email(email: str) -> str:
    """What the grant log stores instead of the address itself.

    The log exists to show an organization a pattern - who has been minting
    tokens against our key, and from where - not to build a second copy of
    their membership list in a table nobody thinks of as one.
    """
    return hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def mint_token(*, club_slug: str, person_id: str | None, origin: str, permissions: list[str]) -> str:
    """A token scoped to one person, one org, one origin, for fifteen minutes.

    `person_id` is None for somebody not on the roster, and that is a
    **success rather than an error**: they get a no-permission token so the
    organization's page still renders, instead of showing their own members a
    stack trace.
    """
    payload = {
        "org": club_slug,
        "sub": person_id,
        "org_origin": origin,
        "perms": sorted(set(permissions) & set(CONSOLE_PERMISSIONS)),
        "exp": int(time.time()) + CONSOLE_TOKEN_TTL_SECONDS,
    }
    body = _b64(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    signature = _b64(hmac.new(_signing_key(), body.encode("ascii"), hashlib.sha256).digest())
    return f"{body}.{signature}"


def read_token(token: str, *, origin: str) -> dict[str, object] | None:
    """The token's claims, or None if it is not one we minted for this origin.

    Every failure returns None rather than raising a distinguishable error:
    a caller learning *why* their forged token was refused is a caller being
    handed an oracle.
    """
    try:
        body, signature = token.split(".", 1)
    except ValueError:
        return None

    try:
        expected = _b64(hmac.new(_signing_key(), body.encode("ascii"), hashlib.sha256).digest())
    except ConsoleKeyMaterialMissing:
        # A deployment with no signing key cannot have minted this, so it
        # cannot verify it either. Refusing is the same answer every other
        # failure gets.
        return None
    if not hmac.compare_digest(signature, expected):
        return None

    try:
        claims = json.loads(_unb64(body))
    except (ValueError, json.JSONDecodeError):
        return None

    if not isinstance(claims, dict):
        return None
    if int(claims.get("exp", 0)) < time.time():
        return None
    # Guard 2, enforced on use as well as on mint: a token minted for one
    # organization's site is worthless on another's, so a stolen one cannot
    # simply be pasted somewhere else.
    if claims.get("org_origin") != origin:
        return None
    return claims


def allowed_origins(raw: str) -> list[str]:
    return [line.strip() for line in (raw or "").splitlines() if line.strip()]
