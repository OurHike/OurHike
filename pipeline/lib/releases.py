"""The `releases/` tree: one immutable folder per dated release, and the index
that lists them.

R2_LAYOUT.md declared this prefix and lib/r2_keys.py has enforced its shape
since it was written - `RELEASE_ID_PATTERN`, `releases/index.json` reserved,
the segment limit. What did not exist was anything that WROTE it (#500).
Measured against the live bucket on 2026-08-09: `releases/index.json` 404,
`latest.json` 206. So the layout was a description of somewhere nobody had
been.

WHAT A RELEASE FOLDER IS FOR, which is not versioning for its own sake. Flat
mutable keys have no previous state, so there is nothing for a rollback to go
back TO (RELEASING.md section 11b), nothing for a release-over-release
regression check to compare against, and nothing for a phone pinned to an
older release to keep reading. All three are properties of *the old bytes
still being somewhere*, and one prefix provides all three.

EVERY FOLDER IS COMPLETE, never a delta. A hiker's client resolves exactly one
folder and must find everything there; a folder holding only what changed that
week would make correctness depend on chasing a chain backwards, and one gap in
that chain is a 404 on a mountain (DATA_RELEASES.md section 2). Storage is the
price and it is the right one to pay - which is affordable because the copies
are server-side and no bytes leave the machine twice.

`conditions/` IS DELIBERATELY NOT IN HERE, and it is the one exclusion worth
understanding rather than remembering. A closure that has reopened must stop
being served, and an immutable folder cannot express that - it could only add a
second answer beside the first. Safety data is mutable, rewritten in place, on
a daily clock against a release cadence measured in months. R2_LAYOUT.md says
so; `is_release_artifact` is that sentence made mechanical.
"""

from __future__ import annotations

from datetime import date
from typing import Iterable

# The index and the release folders. Both spelled here rather than built at
# call sites, because `releases/index.json` is a RESERVED_KEY in
# lib/r2_keys.py - one meaning, one spelling.
RELEASES_PREFIX = "releases/"
RELEASE_INDEX_KEY = "releases/index.json"

# The manifest that travels INSIDE a release folder, naming what the folder
# holds. Same shape as `latest.json`'s, and deliberately the same name a
# reader would guess: the folder is meant to be self-describing, so that
# resolving a release needs one fetch rather than a lookup in the index plus a
# fetch of the pointer that used to describe it.
RELEASE_MANIFEST_NAME = "manifest.json"

# The prefix whose artifacts never enter a release folder. See the module
# docstring - this is a rule about mutability, not about size or importance.
CONDITIONS_PREFIX = "conditions/"


def is_release_artifact(name: str) -> bool:
    """Whether an artifact belongs in a release folder.

    Everything except `conditions/`. Written as an exclusion of one prefix
    rather than an allow-list of the rest, so an artifact added later is in a
    release by default - the safe direction, since the failure of wrongly
    including something is a duplicate copy and the failure of wrongly
    excluding it is a release folder that is not complete.
    """
    return not name.startswith(CONDITIONS_PREFIX)


def release_key(release_id: str, name: str) -> str:
    """Where an artifact lives inside its release folder."""
    return f"{RELEASES_PREFIX}{release_id}/{name}"


def next_release_id(taken: Iterable[str], today: date | None = None) -> str:
    """Today's release id, avoiding any already used.

    `2026-08-13`, and `2026-08-13-2` for a second release on the same day -
    exactly what RELEASE_ID_PATTERN allows and R2_LAYOUT.md describes. Lexically
    sortable, and it answers "how old is the map on my phone" without a lookup
    table.

    The suffix starts at 2 rather than 1 because the unsuffixed id IS the
    first: `2026-08-13` and `2026-08-13-1` naming different folders on one day
    would be two spellings of "the first one today", and the layout cannot
    rename either afterwards.

    `today` is injected rather than read here so a test can assert the
    same-day case without waiting a day for it.
    """
    stamp = (today or date.today()).isoformat()
    used = set(taken)
    if stamp not in used:
        return stamp
    suffix = 2
    while f"{stamp}-{suffix}" in used:
        suffix += 1
    return f"{stamp}-{suffix}"


def index_ids(index: dict | None) -> list[str]:
    """Every release id the index lists, oldest first.

    A missing or malformed index reads as empty rather than raising. That is
    the first-publish case - there is no index until something writes one - and
    it is indistinguishable from a corrupt one at this level. Both mean "no
    release ids are taken", and the wrong answer costs a colliding id that
    r2_keys would then reject, rather than silent damage.
    """
    if not isinstance(index, dict):
        return []
    releases = index.get("releases")
    if not isinstance(releases, list):
        return []
    return [entry["id"] for entry in releases if isinstance(entry, dict) and isinstance(entry.get("id"), str)]


def append_release(index: dict | None, *, release_id: str, version: str, created_at: str) -> dict:
    """The index with one more release on the end.

    An object with a `releases` list rather than a bare list, so the file can
    gain a field later without every reader of it changing shape. DATA_RELEASES.md
    section 2's staging flow will want `status` here - `candidate` until the
    verification battery passes, then `verified` - and that arrives with the
    flow that can honestly set it.

    `created_at` is what the retention rule reads, and the rule is
    DATA_RELEASES.md's "Retention" section rather than restated here: **90
    days after a release is SUPERSEDED, with a floor of the three most recent**,
    plus two exemptions no age can override - the folder `latest.json` currently
    names, and anything listed in `releases/pinned.json`.

    Superseded rather than published is the load-bearing word, and it is why an
    entry needs no `superseded_at` of its own: releases are appended in order,
    so a release is superseded exactly when the NEXT entry was created. The
    clock is therefore derivable from this list alone, which is what lets a
    prune job read one file and decide.

    (#500's own comment reads the rule as `max(3 releases, 90 days)` from the
    build date. That agrees on the floor and the window and differs on when the
    clock starts; DATA_RELEASES.md's is the stricter and the older, and a
    release that stays current for months not ageing out from under the build
    pinned to it is the property the difference protects.)

    Either way, neither half is expressible without a date - an entry carrying
    only an id would be an index a prune job could not use, and a prefix whose
    prune rule cannot be evaluated is the one R2_LAYOUT.md warns a prune job
    may delete.

    Appended rather than sorted: the id is lexically sortable and publishes
    happen in order, so append and sort agree - and if they ever disagree, the
    order things actually happened is the more honest record.
    """
    existing = index.get("releases") if isinstance(index, dict) else None
    releases = list(existing) if isinstance(existing, list) else []
    releases.append(
        {
            "id": release_id,
            "created_at": created_at,
            # Which `latest.json` version these bytes were published as, so a
            # release folder and the pointer that described it can be matched
            # up after the fact. The two ids answer different questions - one
            # names a folder, the other names a manifest - and neither can be
            # derived from the other.
            "version": version,
        }
    )
    return {"releases": releases}
