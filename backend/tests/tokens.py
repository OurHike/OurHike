"""One place that mints test JWTs, shaped like the ones Supabase issues.

Every router test needs a signed token, and until this module existed each
one carried its own copy of a `_make_token` helper - eight of them, all
minting `sub` + `exp` and nothing else. That is a shape Supabase never
produces, and the uniformity of the copies is exactly what hid a real bug:
a Supabase access token always carries `aud: "authenticated"`, PyJWT refuses
a token carrying `aud` unless the caller names an audience, and so
`verify_supabase_jwt` accepted every token the tests minted and would have
rejected every token a real signed-in hiker sent.

Minting the realistic shape here, once, is what stops that drifting back:
a fixture that is wrong in one place gets found, a fixture that is wrong in
eight identical places looks like the truth.
"""

from datetime import datetime, timedelta, timezone
from functools import lru_cache

import jwt
from cryptography.hazmat.primitives.asymmetric import ec

from app.config import settings

# Distinguishes "caller said nothing" from an explicit `audience=None`,
# which is a token shape tests genuinely need to ask about.
_CONFIGURED = object()


def make_token(
    user_id: str,
    *,
    secret: str | None = None,
    expires_delta: timedelta = timedelta(hours=1),
    audience: str | None | object = _CONFIGURED,
) -> str:
    """A signed JWT for `user_id`, carrying the claims Supabase really sends.

    `audience` defaults to the configured one; pass `None` to omit the claim
    entirely, or a string to mint a token for some other consumer.
    """
    payload: dict = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + expires_delta,
        "role": "authenticated",
        "iss": f"{settings.supabase_url}/auth/v1",
    }

    resolved = settings.supabase_jwt_audience if audience is _CONFIGURED else audience
    if resolved:
        payload["aud"] = resolved

    return jwt.encode(payload, secret if secret is not None else settings.supabase_jwt_secret, algorithm="HS256")


def auth_headers(user_id: str) -> dict[str, str]:
    """The Authorization header a signed-in client would send."""
    return {"Authorization": f"Bearer {make_token(user_id)}"}


# The shape a *hosted* Supabase project actually issues: ES256, with a `kid`
# naming the key in the project's published JWKS. Confirmed against a real
# token - see app/core/auth.py.
#
# Minted here with a real generated keypair rather than a canned fixture,
# because the thing worth testing is that a real signature verifies against a
# real public key. A hand-written token and a stubbed verifier would agree
# with each other and prove nothing about either.


@lru_cache(maxsize=1)
def es256_keypair() -> tuple[ec.EllipticCurvePrivateKey, ec.EllipticCurvePublicKey]:
    """One P-256 keypair for the whole test session. Generating a key per test
    is pure cost: nothing here depends on the keys differing."""
    private = ec.generate_private_key(ec.SECP256R1())
    return private, private.public_key()


def other_es256_key() -> ec.EllipticCurvePrivateKey:
    """A second, unrelated key - the one an attacker would have. Deliberately
    not cached alongside the first, so nothing can accidentally match it."""
    return ec.generate_private_key(ec.SECP256R1())


def make_es256_token(
    user_id: str,
    *,
    private_key: ec.EllipticCurvePrivateKey | None = None,
    expires_delta: timedelta = timedelta(hours=1),
    audience: str | None | object = _CONFIGURED,
    kid: str = "0644dbc7-b08b-4eb5-ac49-d754cae66269",
) -> str:
    """An ES256 token carrying the claims and header a hosted project sends."""
    payload: dict = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + expires_delta,
        "role": "authenticated",
        "iss": f"{settings.supabase_url}/auth/v1",
    }

    resolved = settings.supabase_jwt_audience if audience is _CONFIGURED else audience
    if resolved:
        payload["aud"] = resolved

    signing_key = private_key if private_key is not None else es256_keypair()[0]
    return jwt.encode(payload, signing_key, algorithm="ES256", headers={"kid": kid})
