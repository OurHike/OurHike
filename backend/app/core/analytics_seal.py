"""Keying and sealing for usage measurement (#1902, features/EVENTING.md).

Two jobs, and they are kept apart on purpose.

**MASKING: `user_key`.** The account id, hashed with HMAC-SHA256 under
`settings.analytics_user_key_secret` and cut to 128 bits. Reports group and
count by it; nothing reads an account out of it. This backend can recompute it
from an account id, which is what lets account deletion and the export find a
hiker's rows - and is also why the secret stays on the server and out of every
report.

**ENCRYPTING: `seal` / `open_sealed`.** The account id and the exact GPS fix,
sealed so that THIS BACKEND CANNOT OPEN WHAT IT WROTE (the maintainer's
"write-only encryption", poll 2026-10-27). Each row gets a fresh ephemeral
X25519 key; its exchange with the month's public key, through HKDF-SHA256,
gives the AES-256-GCM key; the ciphertext is bound to its month and its event
id as associated data, so a blob copied onto another row, or into another
month, fails to open rather than opening as somebody else's.

THE MONTH IS IN THE KEY, TWICE

"Just add the month name to the key. Not perfect, but a little better" (poll
2026-10-27). Each month's key pair is derived from one secret and the month's
name (`month_private_key`), and the month's name is also in the info string
of every row's data key. What that buys: opening October hands over October's
private key and no other month's, so an opening for one reason does not
quietly open the rest.

**What it does not buy, stated here so nobody reads it as more:** the secret
derives every month's key again on demand, so no key is ever destroyed. This
is not crypto-shredding. A sealed blob stops being readable only when its row
is deleted, and six-month retention rests on the rollup's delete
(app/core/analytics_rollup.py), not on a key going away. The alternative the
maintainer was shown - an independent key per month, deleted with its rows -
was the one declined.

The secret is 32 random bytes that live in the maintainer's password
manager. `scripts/analytics_keys.py` makes it, publishes the public halves,
and opens rows; nothing in `app/` ever holds it.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from datetime import date

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

# The first byte of every sealed blob. A future change of scheme bumps it, so
# a blob says which scheme sealed it rather than leaving the opener to guess.
SEAL_VERSION = 1

# Domain separation: the same secret must never produce a user key, a month
# key and a row key that could be confused with one another.
_USER_KEY_LABEL = b"ourhike-analytics-user-key-v1\x00"
_MONTH_KEY_LABEL = b"ourhike-analytics-month-key-v1\x00"
_ROW_KEY_LABEL = b"ourhike-analytics-row-key-v1\x00"

_PUBLIC_KEY_BYTES = 32
_NONCE_BYTES = 12
_HEADER_BYTES = 1 + _PUBLIC_KEY_BYTES + _NONCE_BYTES

# 128 bits as 32 hex characters. A collision between two hikers would merge
# their User-table rows; at 2^-64 for a billion pairs it is not a number this
# app will reach.
USER_KEY_HEX_CHARS = 32


class SealError(ValueError):
    """A blob that does not open: wrong key, wrong month, wrong row, or tampered."""


def month_label(day: date) -> str:
    """`2026-10` for any day in October 2026 - the name the keys are derived from."""
    return f"{day.year:04d}-{day.month:02d}"


def user_key(secret: str, account_id: str) -> str:
    """The masked stand-in for an account, as every report sees it."""
    if not secret:
        raise ValueError("analytics_user_key_secret is empty; no row may be linked to an account")
    digest = hmac.new(secret.encode("utf-8"), _USER_KEY_LABEL + account_id.encode("utf-8"), hashlib.sha256)
    return digest.hexdigest()[:USER_KEY_HEX_CHARS]


def new_secret() -> bytes:
    """32 random bytes - the one secret every month's key is derived from."""
    return os.urandom(32)


def month_private_key(secret: bytes, month: str) -> X25519PrivateKey:
    """The month's private key: HKDF over the secret, with the month's name as info.

    Deterministic by design, so the secret alone is enough to open any month
    and nothing per month needs storing - which is exactly why it is not
    shredding (module docstring).
    """
    if len(secret) != 32:
        raise ValueError("the analytics secret is 32 bytes")
    raw = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=_MONTH_KEY_LABEL + month.encode("ascii")).derive(secret)
    return X25519PrivateKey.from_private_bytes(raw)


def month_public_key(secret: bytes, month: str) -> bytes:
    """The 32 raw bytes `analytics_seal_keys.public_key` holds for `month`."""
    return month_private_key(secret, month).public_key().public_bytes_raw()


def _row_key(shared: bytes, ephemeral_public: bytes, month_public: bytes, month: str) -> bytes:
    return HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=ephemeral_public + month_public,
        info=_ROW_KEY_LABEL + month.encode("ascii"),
    ).derive(shared)


def _associated_data(month: str, event_id: str) -> bytes:
    return month.encode("ascii") + b"\x00" + event_id.encode("ascii")


def seal(month_public: bytes, month: str, event_id: str, payload: dict) -> bytes:
    """Seal `payload` so only the holder of the month's private key can open it.

    Layout: version (1) | ephemeral public key (32) | nonce (12) | ciphertext+tag.
    """
    if len(month_public) != _PUBLIC_KEY_BYTES:
        raise ValueError("a month public key is 32 raw bytes")
    ephemeral = X25519PrivateKey.generate()
    ephemeral_public = ephemeral.public_key().public_bytes_raw()
    shared = ephemeral.exchange(X25519PublicKey.from_public_bytes(month_public))
    key = _row_key(shared, ephemeral_public, month_public, month)
    nonce = os.urandom(_NONCE_BYTES)
    plaintext = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, _associated_data(month, event_id))
    return bytes([SEAL_VERSION]) + ephemeral_public + nonce + ciphertext


def open_sealed(month_private: X25519PrivateKey, month: str, event_id: str, blob: bytes) -> dict:
    """The inverse of `seal`. Raises `SealError` on anything that does not open."""
    if len(blob) <= _HEADER_BYTES or blob[0] != SEAL_VERSION:
        raise SealError("not a sealed blob this version can open")
    ephemeral_public = blob[1 : 1 + _PUBLIC_KEY_BYTES]
    nonce = blob[1 + _PUBLIC_KEY_BYTES : _HEADER_BYTES]
    ciphertext = blob[_HEADER_BYTES:]
    month_public = month_private.public_key().public_bytes_raw()
    shared = month_private.exchange(X25519PublicKey.from_public_bytes(ephemeral_public))
    key = _row_key(shared, ephemeral_public, month_public, month)
    try:
        plaintext = AESGCM(key).decrypt(nonce, ciphertext, _associated_data(month, event_id))
    except Exception as exc:  # cryptography raises InvalidTag; anything else is the same answer
        raise SealError("the blob did not open with this month's key for this row") from exc
    return json.loads(plaintext)
