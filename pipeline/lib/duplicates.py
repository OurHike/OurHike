"""One path recorded twice by two organizations, drawn once (#1459).

NOT THE SAME QUESTION AS lib/concurrency.py, AND THE DISTINCTION IS THE WHOLE
REASON THIS IS A SECOND MODULE. A CONCURRENCY is two trails sharing one
treadway - the Ramapo-Dunderberg on the A.T. - and the map draws BOTH, in two
tones, on purpose. A DUPLICATE is one path two sources each recorded, and the
map should draw it ONCE. That module's own docstring already separates them:
its blaze rule exists because "one trail that two sources spell differently"
kept arriving at its door, and it declines to pair them. Declining to pair is
not the same as removing one, so both lines still shipped and still drew on
top of each other.

THE MEASUREMENT THIS EXISTS FOR (#1453, spike_nyc_overlap.py, 2026-09-15).
New York City's two agencies catalogue the same paths: 23.6% of the length of
the greenway segments whose `gwyjuris` is DPR - NYC Parks' own ground - lies
within 25 m of an NYC Parks trail line, against 0.9% for every other
jurisdiction. Twenty-five times the floor, so it tracks land management and
not the city's density.

WHY PAIRING IS BY SOURCE AND NOT BY NAME. concurrency.py pairs trails whose
NAMES match, which is right for its question and finds nothing here: the two
agencies call the same path different things, and #1432's placeholder rule
leaves 3,777 of the parks rows with no name at all. What identifies a
duplicate here is that two DIFFERENT ORGANIZATIONS drew lines on the same
ground, so the pairing is declared in sources.json - a junior source names
the senior one it duplicates - and the geometry decides the rest.

THE THREE CHOICES, AND ALL THREE ROUND THE SAME WAY

Dropping a line a hiker needs is the `lost` path, so every number below is
set to MISS a duplicate rather than to remove a real second path.

- TEN METRES, not the 25 the overlap is quoted at. concurrency.py measured
  the knee of the same curve at 8-10 m against the same kind of data, and
  under the width of the line as drawn (7.2 m per pixel at z14, 41 deg). The
  25 m figure is the generous end of a sensitivity check and would take in
  a boulevard's two sides digitised apart, which are two paths.
- HALF THE FEATURE'S LENGTH. A record is a duplicate only when at least
  `min_share` of it lies near the senior source. A greenway that merely
  touches a park trail for fifty metres keeps both lines, because outside
  that fifty metres it is the only record of that path. At 10 m this is 269
  of the 1,828 DPR segments - about one in seven - where the whole-jurisdiction
  cut #1459 rejected would have taken all 1,828 and deleted the 76% of their
  length that overlaps nothing.
- WHOLE FEATURES, never split ones. Cutting a record at the boundary of its
  overlap would be more precise and would need a rule for what the offcut is
  called, whose status it carries, and what happens to a fifteen-metre orphan.
  Whole features are the conservative reading, and the offcut question is
  open rather than answered badly.

WHAT SURVIVES, FIELD BY FIELD. The senior record's geometry and name; the
junior's distinguishing columns where the senior has nothing. Neither agency
is uniformly better and this is a finding rather than a hedge - NYC Parks has
the park interiors and a trail vocabulary but leaves over half its rows
unnamed, while NYC DOT has the waterfront esplanades, a usually-real
`gwsystem` name, and the on-street and status columns the safety filter runs
on. So `merge` takes each field from whichever record has one, senior first,
and the loser's identity is kept on the survivor (`duplicate_of`) rather than
discarded: features/POI_DEDUPLICATION.md §3's "the merge is a line in the
identity ledger, not a new file", for lines, with no ledger yet to write it
in.

WHAT THIS DELIBERATELY IS NOT. It is not a general cross-source dedupe of
every organization's lines against every other's. The pairs are declared, one
at a time, by somebody who has looked at the measurement for that pair -
which is how #1453 arrived at this one. OPRHP's copy of the A.T. beside ATC's
is the obvious next candidate and is not claimed here.
"""

from __future__ import annotations

from pyproj import Transformer
from shapely import STRtree
from shapely import wkt as shapely_wkt
from shapely.ops import transform as shapely_transform
from shapely.ops import unary_union

from lib.corridor import GEOGRAPHIC_CRS, PROJECTED_CRS

# Both argued in the module docstring before changing either.
DUPLICATE_TOLERANCE_M = 10.0
DUPLICATE_MIN_SHARE = 0.5

_TO_METRIC = Transformer.from_crs(GEOGRAPHIC_CRS, PROJECTED_CRS, always_xy=True).transform

#: Fields a survivor may inherit from the record it swallows. `name` is in the
#: list because the senior source frequently has none - #1432's placeholder
#: rule leaves 3,777 NYC Parks rows nameless - and a path with the junior's
#: name is more use to somebody standing on it than a path with none.
#: Geometry is NOT in it: the survivor's line is the survivor's.
INHERITABLE = ("name", "trail_status", "blaze_color")


def merge(senior: dict, junior: dict) -> dict:
    """The surviving record: the senior's, plus what only the junior knows.

    Field by field rather than record by record, because neither source is
    uniformly better - see the module docstring. The senior always wins a
    field it actually has; the junior fills the holes.
    """
    survivor = dict(senior)
    for field in INHERITABLE:
        if survivor.get(field) in (None, "") and junior.get(field) not in (None, ""):
            survivor[field] = junior[field]
    # The loser is named rather than forgotten. A hiker who taps this line
    # gets one record where two organizations hold one, and the least this
    # can do is say whose the other was.
    survivor["duplicate_of"] = junior.get("source")
    return survivor


def find_duplicates(
    senior: list[dict],
    junior: list[dict],
    *,
    tolerance_m: float = DUPLICATE_TOLERANCE_M,
    min_share: float = DUPLICATE_MIN_SHARE,
) -> tuple[dict[str, str], dict]:
    """Which junior records are the senior's paths drawn again.

    Returns `{junior id: the senior id it duplicates}` plus a stats dict.
    Both lists are export_nearby_trails-shaped rows carrying `id` and `wkt`
    in EPSG:4326. A junior record qualifies when at least `min_share` of its
    length lies within `tolerance_m` of any senior record; the senior it is
    reported against is the one covering most of it, which is the one a
    merge should inherit into.

    An empty senior list yields no duplicates rather than raising: a source
    that failed to fetch must not silently delete the other one's lines.
    """
    if not (0.0 < min_share <= 1.0):
        raise ValueError(f"min_share must be in (0, 1], got {min_share}")
    if tolerance_m <= 0:
        raise ValueError(f"tolerance_m must be > 0, got {tolerance_m}")

    stats = {
        "tolerance_m": tolerance_m,
        "min_share": min_share,
        # `senior_records` rather than `senior`, because export_nearby_trails
        # merges this dict under keys naming the two SOURCES and a collision
        # there silently replaced the source key with a count. Caught by a
        # test; renamed so it cannot happen again rather than reordered so it
        # happens to not.
        "senior_records": len(senior),
        "junior_records": len(junior),
        "duplicates": 0,
        "junior_miles_removed": 0.0,
        "touched_but_kept": 0,
    }
    if not senior or not junior:
        return {}, stats

    senior_geoms = [shapely_transform(_TO_METRIC, shapely_wkt.loads(r["wkt"])) for r in senior]
    tree = STRtree(senior_geoms)

    duplicates: dict[str, str] = {}
    for record in junior:
        geom = shapely_transform(_TO_METRIC, shapely_wkt.loads(record["wkt"]))
        if geom.length <= 0:
            continue
        hits = [int(i) for i in tree.query(geom, predicate="dwithin", distance=tolerance_m)]
        if not hits:
            continue
        near = geom.intersection(unary_union([senior_geoms[i] for i in hits]).buffer(tolerance_m))
        share = near.length / geom.length
        if share < min_share:
            stats["touched_but_kept"] += 1
            continue
        # Reported against the senior record covering most of it - the one a
        # merge should inherit into, and deterministic where two tie.
        best = min(hits, key=lambda i: (-geom.intersection(senior_geoms[i].buffer(tolerance_m)).length, str(senior[i]["id"])))
        duplicates[record["id"]] = senior[best]["id"]
        stats["duplicates"] += 1
        stats["junior_miles_removed"] += geom.length / 1609.344

    stats["junior_miles_removed"] = round(stats["junior_miles_removed"], 2)
    return duplicates, stats


def apply_duplicates(records: list[dict], duplicates: dict[str, str]) -> list[dict]:
    """`records` with each duplicate removed and its survivor merged.

    Order is preserved, so the artifact's feature order does not shuffle when
    a pair is found or lost. A duplicate whose survivor is not in `records` -
    a senior dropped by a closure after the pairing was computed - keeps the
    junior rather than losing both, which is the direction that costs a
    hiker nothing.
    """
    by_id = {record["id"]: record for record in records}
    resolved = {jid: sid for jid, sid in duplicates.items() if sid in by_id and jid in by_id}
    for jid, sid in resolved.items():
        by_id[sid] = merge(by_id[sid], by_id[jid])
    return [by_id[record["id"]] for record in records if record["id"] not in resolved]
