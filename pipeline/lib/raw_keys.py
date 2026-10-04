"""The private raw store's key rule, which is not the public bucket's.

pipeline/INCREMENTAL.md, "The private bucket needs its own key validator, not
`lib/r2_keys.py`", is the design: every rule in r2_keys.py exists because a
key in the public bucket is a permanent URL (at most four segments, no
`latest`, a closed set of extensions), and none of that is true of a private
key. A raw store holds `.pbf`, `.parquet`, `.zip` and whatever an upstream
sends next, under paths that mirror pipeline/data/raw/, and Geofabrik's own
file names say `latest`. So this rule set is aimed at the two things that do
still matter in a private store: a key that cannot escape the prefix it is
written under, and one that cannot be two keys at once (a `.`/`..` segment,
an empty segment, a backslash, or a character a filesystem or a URL reads
as something else).

First used by extract/_geofabrik.py's `current/` copies (#1652 — Download
OSM's Geofabrik extracts at most once a month, into a private raw bucket
that outlives the 7-day Actions cache). INCREMENTAL.md means it to serve the
step cache's keys too; extract/_warehouse.py's `_step_key()` still checks
its own three cases and has not moved onto it.
"""

from __future__ import annotations

import re

#: One segment: letters, digits, `.`, `_` and `-`. No space, `%`, `?`, `#`,
#: `:` or `\`, each of which some reader of a key (a shell, a URL, fsspec,
#: Windows) reads as something other than a name.
SEGMENT_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")
#: S3's own ceiling on a key, in bytes, and R2's (both documented at 1,024).
MAX_KEY_BYTES = 1024


def raw_key_problems(key: str) -> list[str]:
    """Why `key` is not a legal path under a raw-store prefix, or [] when it is."""
    if not isinstance(key, str) or not key:
        return ["a key is a non-empty string"]
    problems = []
    if key.startswith("/"):
        problems.append("a key is relative to its prefix, so it may not start with /")
    if key.endswith("/"):
        problems.append("a key names an object, so it may not end with /")
    if len(key.encode("utf-8")) > MAX_KEY_BYTES:
        problems.append(f"a key is at most {MAX_KEY_BYTES} bytes")
    for segment in key.strip("/").split("/"):
        if segment in ("", ".", ".."):
            problems.append(f"segment {segment!r} could resolve outside its prefix or onto another key")
        elif not SEGMENT_PATTERN.match(segment):
            problems.append(f"segment {segment!r} holds a character outside A-Z a-z 0-9 . _ -")
    return problems


def validate_raw_key(key: str) -> str:
    """`key`, or ValueError naming every problem raw_key_problems() found."""
    if problems := raw_key_problems(key):
        raise ValueError(f"{key!r} is not a raw-store key: {'; '.join(problems)}")
    return key
