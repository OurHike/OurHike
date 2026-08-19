"""The identity ledger, read rather than written (#673).

`reconcile_poi_identity.py` OWNS the ledger - it is the only thing that
writes `reference/poi_identity.json`. This module is the other half: the
questions everything downstream asks of that file, in one place because
features/POI_IDENTITY.md's step 3 asks for "one resolver ... used by the
backend's serialisers and the client's lookup rather than implemented
twice", and two copies of `resolve` that disagree is the failure that
sentence exists to prevent.

Three callers today, all in the pipeline: `export_retired_poi.py` (which
turns retired rows into the published tombstones), `verify_release.py`
(which holds the artifact and the ledger to each other), and
`reconcile_poi_identity.py` itself for `live_rows`.

WHAT IS NOT HERE, AND WHY IT MATTERS

The backend and the client are the two consumers the design names, and
neither can call this today: nothing under `backend/` reads a pipeline
reference file or a published artifact (grepped 2026-08-19 - `backend/app/`
touches R2 only for its own private photo bucket, and `load_assignments.py`
is the sole precedent for reviewed pipeline-shaped data reaching Postgres,
via a script and a table). `retired_poi.geojson` exists so that those
halves have something to resolve AGAINST when they are built; until then
this is the reference implementation they should be ported from rather
than a shared dependency they import. Said out loud because a resolver
that only the pipeline calls is a third of #673, not all of it.
"""

from __future__ import annotations

# The properties a tombstone publishes, in the order the design lists them
# (features/POI_IDENTITY.md section 4): "id, name, type, last position,
# retired release, `superseded_by`". Position rides in the geometry rather
# than the properties, which is what makes the artifact a FeatureCollection
# a map can draw rather than a JSON table.
TOMBSTONE_PROPERTIES = ("id", "name", "poi_type", "retired", "superseded_by")


def live_rows(pois: dict) -> dict:
    """The rows a release may publish: everything not retired.

    Retirement is the only thing that takes a row out of circulation - the
    contract forbids deleting one - so "live" is the absence of a
    `retired` stamp rather than a state field with three spellings.
    """
    return {poi_id: row for poi_id, row in pois.items() if "retired" not in row}


def retired_rows(pois: dict) -> dict:
    """The tombstones: every row that has been retired, whenever it was.

    Deliberately not filtered by age. features/POI_IDENTITY.md's open
    question - how long a tombstone publishes - is answered `forever` here,
    on a measurement rather than the doc's estimate: the ledger holds 4,251
    rows of which 21 are already retired, and `export_retired_poi.py` turns
    those 21 into a 5,235-byte artifact (measured 2026-08-19, against
    reference/poi_identity.json as reconciled that morning). That is 249
    bytes a tombstone, so a refresh year that retires fifty places adds
    ~12 KB to a first fetch that is already 5.3 MB gzipped - four
    thousandths of a percent.

    Pruning would cost more than that in machinery alone: it needs the
    pipeline to know which tombstones still have a hiker's photo or note
    anchored to them, which is a Postgres read from a build that
    deliberately has none. Forever until measured cost says otherwise, per
    the doc's own recommendation - and the number to re-measure against is
    the one above.
    """
    return {poi_id: row for poi_id, row in pois.items() if "retired" in row}


def resolve(pois: dict, poi_id: str) -> str | None:
    """Follow `superseded_by` from any id ever published to the id that
    stands for that place today. Returns None when nothing does.

    This is what re-anchors a hiker's photos, notes and plans after upstream
    folds two places into one. Three answers, and the third is the one worth
    stating:

      - a LIVE row resolves to itself;
      - a retired row with `superseded_by` resolves to whatever that points
        at, transitively - a place merged twice over two refreshes still
        arrives somewhere;
      - a retired row WITHOUT `superseded_by` resolves to None, which is the
        honest answer and not a failure. It means "this place is gone and
        nothing took its place", which is exactly what a tombstone card
        says. Returning a nearby id instead would be the confident wrong
        merge features/POI_IDENTITY.md tunes every threshold away from.

    An unknown id also returns None: an id this ledger has never held is a
    reference from somewhere this project cannot vouch for, and inventing a
    target for it would be worse than saying so.

    Cycles cannot arise from `reconcile_poi_identity.py` - it only ever
    points a newly retired row at a row that is live in the same run - but
    a hand-written `merged_into` override is a file a person edits, and
    "the resolver hung" is a bad way to learn that two rows point at each
    other. The seen-set makes that a None instead.
    """
    seen: set[str] = set()
    current = poi_id
    while True:
        row = pois.get(current)
        if row is None:
            return None
        if "retired" not in row:
            return current
        successor = row.get("superseded_by")
        if successor is None or successor in seen:
            return None
        seen.add(current)
        current = successor
