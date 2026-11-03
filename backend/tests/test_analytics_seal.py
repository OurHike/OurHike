"""Sealing and masking for usage events (#1902, app/core/analytics_seal.py).

What these hold is the maintainer's two choices of 2026-10-27: write-only
encryption, and the month's name in the key. A blob opens with its own month's
key, for its own row, and for nothing else.
"""

import pytest

from app.core.analytics_seal import (
    SEAL_VERSION,
    USER_KEY_HEX_CHARS,
    SealError,
    month_label,
    month_private_key,
    month_public_key,
    new_secret,
    open_sealed,
    seal,
    user_key,
)

FIX = {"account": "a1b2", "lat": 41.29871, "lon": -74.1881, "accuracy_m": 9.0}


@pytest.fixture()
def secret():
    return new_secret()


def test_a_sealed_fix_opens_with_its_months_key_to_exactly_what_was_sealed(secret):
    blob = seal(month_public_key(secret, "2026-10"), "2026-10", "event-1", FIX)

    assert open_sealed(month_private_key(secret, "2026-10"), "2026-10", "event-1", blob) == FIX


def test_a_sealed_fix_does_not_open_with_the_next_months_key(secret):
    blob = seal(month_public_key(secret, "2026-10"), "2026-10", "event-1", FIX)

    with pytest.raises(SealError):
        open_sealed(month_private_key(secret, "2026-11"), "2026-11", "event-1", blob)


def test_a_blob_copied_onto_another_row_does_not_open_there(secret):
    """The event id is associated data, so a blob moved between rows fails
    rather than opening as the other row's fix."""
    blob = seal(month_public_key(secret, "2026-10"), "2026-10", "event-1", FIX)

    with pytest.raises(SealError):
        open_sealed(month_private_key(secret, "2026-10"), "2026-10", "event-2", blob)


def test_a_tampered_blob_does_not_open(secret):
    blob = bytearray(seal(month_public_key(secret, "2026-10"), "2026-10", "event-1", FIX))
    blob[-1] ^= 0x01

    with pytest.raises(SealError):
        open_sealed(month_private_key(secret, "2026-10"), "2026-10", "event-1", bytes(blob))


def test_a_different_secret_cannot_open_it(secret):
    blob = seal(month_public_key(secret, "2026-10"), "2026-10", "event-1", FIX)

    with pytest.raises(SealError):
        open_sealed(month_private_key(new_secret(), "2026-10"), "2026-10", "event-1", blob)


def test_each_month_has_its_own_key_derived_from_the_one_secret(secret):
    october, november = month_public_key(secret, "2026-10"), month_public_key(secret, "2026-11")

    assert october != november
    assert month_public_key(secret, "2026-10") == october, "the same month must derive the same key every time"


def test_sealing_the_same_fix_twice_gives_two_different_blobs(secret):
    """A fresh ephemeral key per row: two hikers at the same spot do not
    produce matching ciphertext a reader could group by."""
    public = month_public_key(secret, "2026-10")

    assert seal(public, "2026-10", "event-1", FIX) != seal(public, "2026-10", "event-1", FIX)


def test_a_blob_says_which_scheme_sealed_it(secret):
    assert seal(month_public_key(secret, "2026-10"), "2026-10", "event-1", FIX)[0] == SEAL_VERSION


def test_the_plaintext_appears_nowhere_in_the_blob(secret):
    blob = seal(month_public_key(secret, "2026-10"), "2026-10", "event-1", FIX)

    assert b"41.29871" not in blob and b"a1b2" not in blob


def test_the_month_label_is_the_calendar_month():
    from datetime import date

    assert month_label(date(2026, 10, 31)) == "2026-10"
    assert month_label(date(2027, 1, 1)) == "2027-01"


def test_a_user_key_is_stable_for_one_account_and_differs_between_accounts():
    assert user_key("server-secret", "account-1") == user_key("server-secret", "account-1")
    assert user_key("server-secret", "account-1") != user_key("server-secret", "account-2")
    assert len(user_key("server-secret", "account-1")) == USER_KEY_HEX_CHARS


def test_a_user_key_depends_on_the_servers_secret():
    """Without the secret, an account id cannot be turned into its key, so a
    report holding keys cannot be joined back to accounts by anyone else."""
    assert user_key("one-secret", "account-1") != user_key("another-secret", "account-1")


def test_no_user_key_is_made_without_a_secret():
    with pytest.raises(ValueError):
        user_key("", "account-1")
