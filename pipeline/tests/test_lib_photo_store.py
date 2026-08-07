"""Tests for lib/photo_store.py - where a POI photo's bytes live.

The properties being pinned here are the reasons content-addressing was
chosen over keying on the POI id, so they are tested as properties rather
than as "does it return the string I typed".
"""

from pathlib import Path

import pytest

from lib.photo_store import local_photo_path, photo_digest, photo_key
from lib.r2_keys import validate_key

SHELTER_JPEG = b"\xff\xd8\xff\xe0 not really a jpeg, but these are the bytes we hash"


def test_the_key_a_digest_produces_is_legal_in_the_bucket():
    """The whole point of deriving keys here rather than by hand: publish()
    refuses an illegal key for the entire run, so a photo key that cannot
    pass the layout would fail a several-thousand-photo publish at the last
    step. `photos/` and `.jpg` both had to be declared for this to hold."""
    key = photo_key(photo_digest(SHELTER_JPEG))

    assert validate_key(key) is None


def test_identical_images_get_one_key_even_from_different_waypoints():
    """Two waypoints a hundred metres apart routinely match the same Commons
    file. Content-addressing dedupes them without anyone writing dedupe
    logic - the second POI simply points at an object that already exists."""
    assert photo_key(photo_digest(SHELTER_JPEG)) == photo_key(photo_digest(SHELTER_JPEG))


def test_different_bytes_never_collide_onto_one_key():
    """A corrected photo must not overwrite the one a phone already cached.
    Different bytes being a different key is what makes that structural
    rather than a rule somebody has to remember."""
    other = SHELTER_JPEG + b" rebuilt in 2026"

    assert photo_key(photo_digest(SHELTER_JPEG)) != photo_key(photo_digest(other))


def test_the_key_carries_the_checksum_so_a_download_is_self_verifying():
    digest = photo_digest(SHELTER_JPEG)
    key = photo_key(digest)

    # A client that asked for this key can hash what arrived and compare,
    # with no manifest lookup at all.
    assert key == f"photos/{digest}.jpg"
    assert photo_digest(SHELTER_JPEG) == digest


@pytest.mark.parametrize(
    "bad",
    [
        "atc_shelters:glob-1",  # a POI id - the obvious wrong choice
        "ABC123",  # capitals
        "abc123",  # too short
        "",
        "g" * 64,  # right length, not hex
    ],
)
def test_a_digest_that_is_not_a_digest_is_rejected_where_it_is_named(bad):
    """Failing here names the bad value; letting it through would surface
    thousands of photos later as an opaque layout violation on the whole
    publish."""
    with pytest.raises(ValueError, match="sha256"):
        photo_key(bad)


def test_local_path_sits_under_the_gitignored_raw_tree():
    digest = photo_digest(SHELTER_JPEG)

    path = local_photo_path(Path("/tmp/raw"), digest)

    assert path == Path("/tmp/raw") / "poi_photos" / f"{digest}.jpg"
