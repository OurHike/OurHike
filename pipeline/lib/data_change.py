"""What changed between the artifact a phone holds and the one being published,
and how much a hiker should care (#919).

`publish.py` already knows *whether* an artifact changed - it compares sha256
against the live manifest and skips the ones that match. What nothing knew is
*what* changed, and that is the whole of what a phone needs to decide anything.
A sha256 says the bytes differ; it cannot tell "eleven new privies" from "the
spring you were walking to is gone".

So this classifies one artifact against the one it replaces, and `publish.py`
writes the result into `latest.json` beside the hash. The phone reads it and
asks the hiker in those terms.

WHY THE PUBLISHER AND NOT THE PHONE

The phone cannot do this. It holds the new artifact only after downloading it,
which is the decision the classification exists to inform - and it would have to
keep the old one to diff against, doubling what an offline-first app stores in
order to answer a question the publisher already had both sides of.

TWO GRADES, AND WHAT SEPARATES THEM

- **`ROUTINE`** - only additions and attribute edits. Nothing a hiker was
  relying on stopped being there or moved. A new privy, a corrected shelter
  name, a water point that gained a `seasonal` tag.
- **`CONSEQUENTIAL`** - a feature was removed, or its geometry moved. The
  removed case is the one this grade exists for: a hiker who planned around a
  water point is the person most affected by its deletion and least likely to
  notice it silently vanishing.

**A change this cannot read is CONSEQUENTIAL, not routine**, and that is the
load-bearing choice in this file. An artifact whose shape it does not
understand, or whose previous bytes could not be fetched, could be either - and
"an honest unknown outranks a confident answer" (CLAUDE.md) means the unknown
takes the grade that gets said out loud rather than the one that reads as
nothing much.

Both grades are offered to the hiker either way. **The maintainer's decision
(2026-08-21) is that nothing is applied without being asked**, so the grade
decides what the prompt SAYS, never whether it appears. Nothing here should be
read as a licence to apply a routine update silently; that would need a new
decision, not a new value.

WHAT A "MOVE" IS, AND WHY THERE IS NO THRESHOLD

Any coordinate change at all. There is deliberately no "moved by more than N
metres" tolerance, because the artifacts that would need one and the artifacts
this measures are different sets:

- `poi_*.geojson` are points, and nothing in the pipeline simplifies a point.
  A POI's coordinates change when the source moved it or when a fold changed
  which coordinate it inherits - both real, neither noise.
- `trails.geojson` is simplified (`export_trails.DEFAULT_SIMPLIFY_TOLERANCE_M`),
  so its vertices genuinely do shift by up to a metre for reasons no hiker
  cares about. This does not measure them: a line artifact is classified on its
  feature ids and on whether each feature's geometry is byte-identical, so a
  re-simplification reads as CONSEQUENTIAL. That is the cautious direction and
  it is honest - what it costs is an occasional prompt saying "the trail lines
  changed" when they moved by a metre, which is true.

Pure - no I/O, no network, no DuckDB. `publish.py` fetches the bytes.
"""

from __future__ import annotations

import json

#: Only additions and attribute edits: nothing a hiker had stopped being there.
ROUTINE = "routine"

#: Something was removed or moved, or this could not tell. See the docstring on
#: why the unreadable case lands here rather than in ROUTINE.
CONSEQUENTIAL = "consequential"

#: The property carrying a feature's published identity. `export_poi.py` writes
#: it into every feature (`POI_COLUMNS`), and since #671 it is the ledger id -
#: stable across an upstream re-key, which is what makes "the same feature,
#: moved" a thing this can see at all rather than a removal and an addition.
ID_PROPERTY = "id"


def _features(document: object) -> dict[str, dict] | None:
    """`{id: feature}` for a GeoJSON FeatureCollection whose features carry
    identities, or None where this cannot read the shape.

    None is the honest answer for `spurs.json`, `elevation_profile.json` and
    anything else that is not a FeatureCollection - and for a FeatureCollection
    whose features have no `id`, which would otherwise silently classify every
    feature as added and removed at once.
    """
    if not isinstance(document, dict) or document.get("type") != "FeatureCollection":
        return None
    features = document.get("features")
    if not isinstance(features, list):
        return None
    by_id: dict[str, dict] = {}
    for feature in features:
        if not isinstance(feature, dict):
            return None
        properties = feature.get("properties")
        identity = properties.get(ID_PROPERTY) if isinstance(properties, dict) else None
        if not isinstance(identity, str) or identity == "":
            return None
        by_id[identity] = feature
    return by_id


def _parse(raw: bytes) -> object | None:
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


def unreadable(reason: str) -> dict:
    """The verdict for an artifact this cannot diff, whatever the reason -
    binary, malformed, an unknown shape, or previous bytes that could not be
    fetched. Carries the reason so a reader is never left guessing why a
    release was graded this way."""
    return {"severity": CONSEQUENTIAL, "added": 0, "removed": 0, "moved": 0, "edited": 0, "unreadable": reason}


def first_publication() -> dict:
    """An artifact with no previous version. Not a change anybody needs warning
    about - there is nothing on a phone for it to disturb - and not
    CONSEQUENTIAL just because the old side is missing."""
    return {"severity": ROUTINE, "added": 0, "removed": 0, "moved": 0, "edited": 0, "first_publication": True}


def classify(previous: bytes | None, current: bytes) -> dict:
    """How one artifact changed, as
    `{"severity", "added", "removed", "moved", "edited"}`.

    `previous` is None for an artifact being published for the first time.
    Never raises: every way this can fail to understand its inputs comes back
    as `unreadable`, because a publish must not die over a description of a
    change it is otherwise ready to make.
    """
    if previous is None:
        return first_publication()

    old_document, new_document = _parse(previous), _parse(current)
    if old_document is None or new_document is None:
        return unreadable("not readable as JSON")

    old, new = _features(old_document), _features(new_document)
    if old is None or new is None:
        # Includes the two artifacts a hiker does download that are not
        # FeatureCollections - spurs.json and elevation_profile.json - so those
        # are always CONSEQUENTIAL today. That is a real cost of the shape rule
        # rather than a judgement about the data, and it is the direction to be
        # wrong in; a structural diff for them is worth adding when somebody
        # decides what "changed" means for an elevation profile.
        return unreadable("not a FeatureCollection with identified features")

    added = sorted(new.keys() - old.keys())
    removed = sorted(old.keys() - new.keys())
    moved, edited = 0, 0
    for identity in old.keys() & new.keys():
        before, after = old[identity], new[identity]
        if before.get("geometry") != after.get("geometry"):
            moved += 1
        elif before.get("properties") != after.get("properties"):
            edited += 1

    severity = CONSEQUENTIAL if (removed or moved) else ROUTINE
    return {"severity": severity, "added": len(added), "removed": len(removed), "moved": moved, "edited": edited}


def combine(changes: list[dict]) -> dict:
    """One verdict over several artifacts - what the phone shows for a whole
    release rather than per file.

    CONSEQUENTIAL wins: a release that added four privies and deleted one water
    point is a release that deleted a water point, and rolling that up as
    "mostly routine" would be the summary hiding the finding.
    """
    total = {"severity": ROUTINE, "added": 0, "removed": 0, "moved": 0, "edited": 0}
    for change in changes:
        for field in ("added", "removed", "moved", "edited"):
            total[field] += change.get(field, 0)
        if change.get("severity") == CONSEQUENTIAL:
            total["severity"] = CONSEQUENTIAL
    return total
