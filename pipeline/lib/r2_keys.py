"""The R2 key convention, as code rather than as prose alone.

[R2_LAYOUT.md](../R2_LAYOUT.md) is the document; this is the half of it a
test can run. It answers one question - "is this a legal key in our bucket?"
- and `publish.py` asks it about every name before it uploads anything.

Why enforce it at all, when the names are chosen by hand a few times a year:
a key in this bucket is not a filename, it is a URL that deployed clients
already request. `publish()`'s manifest merge is additive-only and app-store
builds cannot be forced forward, so a name that lands wrong cannot be
renamed later - only joined by a sibling and abandoned, with the mistake
served forever alongside it. The cheapest moment to catch `Trails_v2.geojson`
is before the first PutObject, not after a hiker's phone has cached it.

Checked before the first upload rather than per-object, so a bad name in a
set of twelve fails the run instead of leaving six uploaded and six not.
"""

from __future__ import annotations

import re

# One path segment that names an object: lowercase, digits, `_` between
# words, exactly one extension. `-` is deliberately absent - it is reserved
# for release ids (`2026-08-07`, `2026-08-07-2`), so a date can never appear
# in an object name by accident.
NAME_PATTERN = re.compile(r"^[a-z0-9]+(_[a-z0-9]+)*\.[a-z0-9]+$")

# A directory segment: the same, minus the extension.
DIR_PATTERN = re.compile(r"^[a-z0-9]+(_[a-z0-9]+)*$")

# A release id. Lexically sortable, and it answers "how old is the map on my
# phone" without a lookup table. The suffix is for a same-day rebuild.
RELEASE_ID_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}(-\d+)?$")

# The formats this bucket actually serves. A closed set on purpose: adding
# one is a single line here, reviewed alongside the artifact that needs it,
# rather than a `.tar.gz` appearing in a public bucket unremarked.
#
# `jpg` was added for POI photos (#362, features/POI_PHOTOS.md) - the one
# format here that is a payload rather than a dataset. It stays narrow
# deliberately: no `jpeg` alias, because two spellings of one format is two
# keys for one photo and the layout cannot rename either afterwards.
ALLOWED_EXTENSIONS = frozenset({"geojson", "fgb", "pmtiles", "json", "tif", "jpg"})

# Top-level prefixes anyone may write under. A new one is a design decision
# (see R2_LAYOUT.md), not something a script invents on its first upload -
# retention rules are written per prefix, so a prefix nobody declared is a
# prefix no prune job knows to spare.
#
# `photos` holds POI photos, content-addressed by the sha256 of the image
# bytes. Deliberately NOT under `releases/`: those folders are written once
# and never overwritten, so a photo published into one could never be taken
# down, and withdrawal is a promise made to the hiker who shared it
# (features/POI_PHOTOS.md). This prefix is mutable for exactly that reason.
#
# `conditions` holds the published safety data - verified closures, verified
# reports, and the ATC's own trail updates
# (features/CONDITIONS_DELIVERY.md, features/ATC_TRAIL_UPDATES.md). Mutable and
# overwritten in place, for the opposite reason to `photos`: a closure that
# has reopened must stop being served, and a release folder written once and
# never overwritten could only ever add a second answer beside the first.
#
# It is also deliberately not versioned the way trail data is. A release is a
# monthly-ish event about a large immutable dataset; this is a daily rewrite
# of a small one, and the freshness a hiker needs is inside the document
# (`generated_at`) rather than in which folder it came from.
#
# `originals/` is the preservation copy behind `photos/` - the full-resolution
# file each 640px rendering was reduced from, kept so that losing an upstream
# does not also lose the photograph (R2_LAYOUT.md, features/POI_PHOTOS.md).
# Declared here rather than when something first writes to it, because the
# declaration is what makes writing there legal: a script must never be able
# to invent a prefix on its first upload, which is the whole job of this set.
TOP_LEVEL_PREFIXES = frozenset({"releases", "_internal", "photos", "conditions", "originals"})

# Keys that mean something specific and are therefore spelled exactly one
# way. `latest.json` is the mutable pointer at the bucket root; the two under
# `releases/` are the release index and the do-not-prune list (DATA_RELEASES.md).
RESERVED_KEYS = frozenset({"latest.json", "releases/index.json", "releases/pinned.json"})

# Words that describe a *build* rather than a *thing*. Every one of them is a
# name that was accurate on the day it was uploaded and misleading a month
# later: `background_new.pmtiles` is not new, `trails_final.geojson` was not
# final. What version an object is belongs in its release folder, which is
# the one place that stays true.
BANNED_WORDS = frozenset(
    {
        "backup",
        "bak",
        "copy",
        "draft",
        "final",
        "latest",
        "new",
        "old",
        "temp",
        "tmp",
        "test",
    }
)

# `_v2`, `_2026_08_07` - the same mistake as BANNED_WORDS, spelled with
# digits. A release is a folder, never a suffix.
VERSIONISH_PATTERN = re.compile(r"_(v\d+|\d{4}_\d{2}_\d{2})(_|$)")

MAX_SEGMENTS = 4


def validate_name(name: str) -> str | None:
    """Check one object-name segment. Returns None if it is fine, or the
    reason it is not - a sentence meant to be read by whoever typed it."""
    if not NAME_PATTERN.match(name):
        return (
            f"'{name}' is not a legal object name: lowercase letters, digits and `_` between words, "
            "then one extension (no spaces, no capitals, no `-`, no double extension)"
        )

    stem, _, extension = name.rpartition(".")
    if extension not in ALLOWED_EXTENSIONS:
        return f"'{name}' has extension '.{extension}', which is not one this bucket serves: {_listing(ALLOWED_EXTENSIONS)}"

    if VERSIONISH_PATTERN.search(f"_{stem}_"):
        return f"'{name}' carries a version or date in its name - that belongs in the release folder, not the object name"

    banned = sorted(set(stem.split("_")) & BANNED_WORDS)
    if banned:
        return (
            f"'{name}' contains {_listing(banned)}, which describes a build rather than a thing - "
            "name the artifact for what it is and let the release folder say which build it came from"
        )
    return None


def validate_key(key: str) -> str | None:
    """Check a whole key, prefix and all. Returns None if it is fine, or the
    reason it is not.

    A bare name (no `/`) is a root key - what everything published today is,
    and what stays frozen when the release layout lands."""
    if key in RESERVED_KEYS:
        return None

    if key != key.strip() or not key:
        return "A key may not be empty or have leading/trailing whitespace"
    if key.startswith("/") or key.endswith("/") or "//" in key:
        return f"'{key}' has an empty path segment"

    segments = key.split("/")
    if len(segments) > MAX_SEGMENTS:
        return (
            f"'{key}' nests {len(segments)} levels deep; the layout goes at most {MAX_SEGMENTS} "
            "(see R2_LAYOUT.md). Deeper usually means the prefix is doing a manifest's job"
        )

    if len(segments) > 1 and segments[0] not in TOP_LEVEL_PREFIXES:
        return (
            f"'{segments[0]}/' is not a declared top-level prefix ({_listing(TOP_LEVEL_PREFIXES)}). "
            "Adding one is a design decision, not a side effect of an upload - see R2_LAYOUT.md"
        )

    # segments[0] is a declared prefix and is spelled however it was
    # declared - `_internal` leads with the underscore that DIR_PATTERN
    # forbids everywhere else, deliberately, so that the one prefix hikers
    # never fetch sorts and reads differently from the ones they do.
    for segment in segments[1:-1]:
        if RELEASE_ID_PATTERN.match(segment) or DIR_PATTERN.match(segment):
            continue
        return f"'{segment}/' in '{key}' is neither a legal directory name nor a release id (YYYY-MM-DD)"

    return validate_name(segments[-1])


def assert_valid_keys(keys) -> None:
    """Raise on the first illegal key, naming every one of them. Called by
    publish.py before it opens a connection, so a bad name costs nothing."""
    problems = [reason for key in keys if (reason := validate_key(key)) is not None]
    if problems:
        joined = "\n  - ".join(problems)
        raise ValueError(f"These object keys do not follow the R2 layout (pipeline/R2_LAYOUT.md):\n  - {joined}")


def _listing(items) -> str:
    return ", ".join(sorted(items))
