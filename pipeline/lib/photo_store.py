"""Where a POI photo's bytes live, locally and in the bucket.

Photos are **content-addressed**: the sha256 of the image bytes is both the
local filename and the object key. Three things fall out of that, and they
are the reason it is worth doing rather than keying on the POI id:

- **A key never needs renaming**, which is the one thing R2_LAYOUT.md says
  the bucket cannot do. Different bytes are a different key by construction,
  so a corrected photo is an upload plus a pointer change, never an
  overwrite of something a phone already cached.
- **Identical images dedupe.** Two waypoints a hundred metres apart
  routinely match the same Commons file; content-addressing stores it once
  without anyone writing dedupe logic.
- **The key is the checksum.** A client that fetched `photos/<digest>.jpg`
  can verify the bytes by hashing them, with no manifest lookup - the same
  integrity property trailData.ts gets from `latest.json` for everything
  else, for free.

A POI id would have given none of those: it is not stable against a photo
being replaced, it cannot dedupe, and `atc_shelters:glob-1` is not even a
legal object name (see lib/r2_keys.py - no colons, no capitals).

Pure module - no I/O, no network. fetch_poi_images.py writes the files and
publish.py uploads them.
"""

import hashlib
import re
from pathlib import Path

# Where downloaded photo bytes are cached locally, under the pipeline's
# gitignored data/ tree. `raw`, not `processed`: these are bytes fetched from
# upstream unchanged, which is exactly what TECHNICAL_ARCHITECTURE.md's
# "generated data never enters git" rule covers.
PHOTOS_DIRNAME = "poi_photos"

# The bucket prefix, declared in lib/r2_keys.py's TOP_LEVEL_PREFIXES and
# documented in R2_LAYOUT.md. Spelled once, here.
PHOTO_PREFIX = "photos"

PHOTO_EXTENSION = "jpg"

_DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def photo_digest(image_bytes: bytes) -> str:
    """The sha256 hex digest that names this image everywhere."""
    return hashlib.sha256(image_bytes).hexdigest()


def photo_key(digest: str) -> str:
    """The bucket key for an image with this digest.

    Validates rather than trusts: every caller of this builds a key that
    `publish()` will refuse if it is malformed, and failing here names the
    bad digest instead of surfacing as an opaque layout violation over a run
    of several thousand.
    """
    if not _DIGEST_PATTERN.match(digest):
        raise ValueError(f"{digest!r} is not a sha256 hex digest, so it cannot name a photo object")
    return f"{PHOTO_PREFIX}/{digest}.{PHOTO_EXTENSION}"


def local_photo_path(raw_dir: Path, digest: str) -> Path:
    """Where this image is cached on disk. Flat rather than sharded into
    `ab/cd/` subdirectories: a corridor holds thousands of photos, not
    millions, and a flat directory of a few thousand files is something every
    filesystem and every `ls` handles without help."""
    return raw_dir / PHOTOS_DIRNAME / f"{digest}.{PHOTO_EXTENSION}"
