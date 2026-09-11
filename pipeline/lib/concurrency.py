"""Where two trails share one stretch of ground, say so - as pairs of
features the map can draw side by side (#1384).

THE PROBLEM THIS SOLVES
-----------------------
Every line source draws its own trail on its own coordinates, so where the
Ramapo-Dunderberg runs on the A.T.'s treadway for a mile the map draws two
lines on the same pixels and whichever is painted last wins. The maintainer,
looking at Harriman on 2026-09-10: "If 2 trail lines overlap, could we show
both somehow?" - and, shown the options, chose the two-tone treatment: each
blaze on its own side of one line. That needs the data to say WHERE the two
lines share ground, which no source does; this module derives it.

WHAT IT PRODUCES
----------------
For every stretch where trail A's lines lie within `tolerance_m` of trail
B's for at least `min_length_m`, TWO features on the SAME geometry - the
stretch cut out of A's lines - one carrying A's properties and one carrying
B's, each naming the other in `concurrent_with` (and the other's source
key in `concurrent_source`, so the map can weigh the stretch at the heavier
of the two tiers) and each with a `concurrent_side` of +1 or -1. Same
coordinates, opposite signs: the client
offsets each feature by half a line width times its sign, and because both
features run the same way the two halves land on opposite sides whatever
direction either source digitised its line in. Direction-agreement logic
does not exist here because sharing the chord makes it unnecessary.

The A.T.'s centerline is always the geometry donor (side +1), so along the
whole trail the white half sits on the same side of ATC's line - the right,
facing the direction ATC's line runs. Between two other trails the donor is
the one whose name sorts first, which is arbitrary and deterministic.

THE TWO NUMBERS, MEASURED
-------------------------
Both measured 2026-09-10 against UA release 2026-09-10's published lines
(scratch scripts measure_concurrency.py / measure_pieces.py in the session
that built this; re-runnable against any release's trails.geojson and
nearby_trails.geojson). The Harriman box is (-74.25, 41.15)-(-73.85, 41.40):
1,205 network features against the 24 A.T. features it holds.

Shared length found between the network and the A.T. in that box, pieces of
30 m or more, as the tolerance widens:

    tolerance    2 m    3 m    5 m    8 m   10 m   15 m   20 m   30 m
    shared km    3.2    4.7    6.5    7.6    8.0    8.7    9.0   10.8

The curve flattens at 8-10 m (0.2 km per extra metre between 8 and 10,
0.14 between 10 and 15) and rises again past 20 m, which is parallel trails
that are not on the same ground starting to count. features/NEARBY_TRAILS.md
§5 measured the same two digitisations of one route agreeing at 1.8 m median
(OPRHP's A.T. copy against ATC's) and 3.3 m (the Long Path) - so 10 m is the
knee, and it is also under the width of the drawn line: at the tiles' z14
(7.2 m per pixel at 41°N) two lines 10 m apart already share their pixels.

The false-positive control is ATC's own layers, where there is nothing to
find: the side trails share NO ground with the centerline at 5 m or under
(0 pieces of 30 m or more, all 1,196 side trails), so everything found there
at 10 m is a junction approach running alongside before it joins. At 10 m
those pieces are 94% under 20 m long (868 of 931) - a crossing at angle θ
yields a piece of 2·tolerance/sin θ, 20 m square-on - and only two exceed
50 m on the whole trail. So the minimum is 50 m: it removes crossings and
approaches down to a 24° angle, and costs 0.4 km of the 8.1 km the network
genuinely shares with the A.T. in the box (pieces between 30 and 50 m),
which is the miss-rather-than-cry-wolf side of the trade.

WHICH LINES ARE PAIRED, AND WHICH DELIBERATELY NOT
--------------------------------------------------
Two records are the same trail when their names match, casefolded and
whitespace-collapsed, ACROSS sources: OPRHP's "Long Path" and NYNJTC's are
one trail and never a pair. A record with no name is skipped and counted -
a pair with an unnamed trail says less than a two-tone line looks like it
says. ATC's side-trails layer is not in the pool at all, by the caller's
choice (export_nearby_trails.load_at_centerline): measured above, it shares
no ground with the centerline, and it carries other organizations' trails
under ATC's own names ("Timp-Torne SideTrail" beside OPRHP's "Timp-Torne
Trail"), so pairing it would pair a trail with itself.

A STRETCH IS KEPT ONLY WHEN THE TWO HALVES CARRY TWO DIFFERENT REAL BLAZES,
and this rule is the one the first run over real data forced. The two-tone
treatment paints blazes: a half whose blaze is one of lib/blaze.py's
NEUTRAL_MEMBERS ("None", "Other", "Unknown") has no paint to show, and two
halves in the same paint draw as the one line they already were. Measured
2026-09-10 over UA release 2026-09-10's 112,439 network lines and 461
centerline chains, before this rule: 12,222 pair features, of which 7,930
were "Unknown", 1,562 "None" and 34 "Other" on one half - and the A.T.'s
most frequent partners were other organizations' copies of the A.T. itself
under their own names ("APPALACHIAN TRAIL" 505 stretches, "APPALACHIAN
TRAIL/LONG TRAIL" 208, "ANST - APPALACHIAN RD" 123, "APPALACHIAN" 111, then
New Hampshire's section names, "MOOSE MTN", "VELVET ROCKS", "HOLT'S LEDGE"),
every one of them blazed "Unknown" - and, in the Whites, "Garfield Ridge
Trail" and "Kinsman Ridge Trail" in White, which is the A.T.'s own paint on
the A.T.'s own ground. Between network sources the same shape: "KINSMAN
RIDGE" beside "Kinsman Ridge Trail", "IMP" beside "Imp Trail", the PCT and
CDT beside their own sections. None of those is two trails on one treadway;
all of them are one trail that two sources spell differently, and none of
them survives the rule, because a copy carries the same paint or none. What
does survive is what the treatment was asked for: the Long Path (Aqua) on
the Escarpment Trail (Blue), the Ramapo-Dunderberg (Red) on the A.T. (White).

KNOWN LIMITS, stated rather than hidden:
- The buffer overshoots each end of a shared stretch by up to `tolerance_m`.
- Three trails on one stretch produce three pairs on the same ground; the
  map draws them in tile order. Rare, and not handled.
- Two organizations publishing one trail under two names AND two different
  real blazes would pair as two trails. The blaze rule above is what stands
  between this and the map today; nothing in the measured run showed one.
"""

from __future__ import annotations

from collections import defaultdict

from pyproj import Transformer
from shapely import STRtree
from shapely import wkt as shapely_wkt
from shapely.geometry import LineString, MultiLineString
from shapely.ops import linemerge, unary_union
from shapely.ops import transform as shapely_transform

from lib.blaze import NEUTRAL_MEMBERS
from lib.corridor import GEOGRAPHIC_CRS, PROJECTED_CRS

# Both measured - see the module docstring before changing either.
SHARED_GROUND_TOLERANCE_M = 10.0
SHARED_GROUND_MIN_LENGTH_M = 50.0

# The source key export_trails.py gives ATC's centerline. Its records are the
# geometry donor of every pair they are in, for the reason in the docstring.
AT_CENTERLINE_SOURCE = "centerline"

_TO_METRIC = Transformer.from_crs(GEOGRAPHIC_CRS, PROJECTED_CRS, always_xy=True).transform
_TO_GEOGRAPHIC = Transformer.from_crs(PROJECTED_CRS, GEOGRAPHIC_CRS, always_xy=True).transform

# The properties a pair feature carries over from its record. `wkt` is
# replaced by the shared stretch; anything else on the record (closure text,
# for one) stays with the record it belongs to rather than riding onto a
# stretch it may not describe.
_CARRIED = ("source", "name", "blaze_color", "trail_status")


def trail_key(record: dict) -> str | None:
    """The identity two records must differ in to be two trails: the name,
    casefolded and whitespace-collapsed, or None for a nameless record."""
    name = record.get("name")
    if name is None:
        return None
    key = " ".join(str(name).split()).casefold()
    return key or None


def _rank(record: dict, key: str) -> tuple[int, str]:
    return (0 if record.get("source") == AT_CENTERLINE_SOURCE else 1, key)


def _line_parts(geometry) -> list[LineString]:
    """Every LineString inside `geometry`, flattening collections and
    dropping the points a buffer intersection leaves where lines touch."""
    if geometry.is_empty:
        return []
    if isinstance(geometry, LineString):
        return [geometry]
    if hasattr(geometry, "geoms"):
        parts: list[LineString] = []
        for part in geometry.geoms:
            parts.extend(_line_parts(part))
        return parts
    return []


def _merged(geometry):
    """The union of a trail's nearby lines with contiguous pieces re-joined,
    so a stretch is one part rather than one per source segment. linemerge
    refuses a bare LineString, which needs no merging."""
    return linemerge(geometry) if isinstance(geometry, MultiLineString) else geometry


def _painted(record: dict) -> bool:
    """Whether a half has a blaze the two-tone treatment can paint: a real
    palette member, not lib/blaze.py's neutral trio and not nothing."""
    blaze = record.get("blaze_color")
    return bool(blaze) and blaze not in NEUTRAL_MEMBERS


def _carried(record: dict) -> dict:
    return {field: record[field] for field in _CARRIED if record.get(field) is not None}


def find_shared_ground(
    records: list[dict],
    *,
    tolerance_m: float = SHARED_GROUND_TOLERANCE_M,
    min_length_m: float = SHARED_GROUND_MIN_LENGTH_M,
) -> tuple[list[dict], dict]:
    """The pair features for every shared stretch among `records`, plus a
    stats dict.

    `records` are export_trails.py-shaped rows (id, source, name, blaze_color,
    wkt in EPSG:4326, and trail_status where the source has one) from any
    mix of exports. Returns records of the same shape: `wkt` is the shared
    stretch, `concurrent_with` the other trail's name as its own record
    spells it, `concurrent_source` the other's source key, `concurrent_side`
    +1 on the donor's feature and -1 on the
    partner's. Each half's other properties come from the record of that
    trail nearest the stretch's midpoint. Output order is deterministic for
    a given input set.

    Works trail against trail, never record against record: a trail one
    organization publishes in 40 m segments shares its ground in one piece,
    and the minimum length is judged on the piece. Only the records of each
    trail near the other trail are merged for that, so a 500 km route is
    never buffered whole.
    """
    if tolerance_m <= 0:
        raise ValueError(f"tolerance_m must be > 0, got {tolerance_m}")
    if min_length_m < 0:
        raise ValueError(f"min_length_m must be >= 0, got {min_length_m}")

    keyed: list[tuple[dict, str]] = []
    nameless = 0
    for record in records:
        key = trail_key(record)
        if key is None:
            nameless += 1
            continue
        keyed.append((record, key))
    # Sorted so the donor of a pair, the record picked for each half's
    # properties and the feature order all follow from the records rather
    # than from the order two exports happened to be concatenated in.
    keyed.sort(key=lambda item: (_rank(item[0], item[1]), str(item[0].get("id"))))

    geoms = [shapely_transform(_TO_METRIC, shapely_wkt.loads(record["wkt"])) for record, _ in keyed]
    tree = STRtree(geoms)

    # (donor trail, partner trail) -> the records of each that come within
    # the tolerance of the other. The donor is the lower-ranked trail: the
    # A.T.'s centerline, else the name that sorts first.
    near: dict[tuple[str, str], tuple[set[int], set[int]]] = defaultdict(lambda: (set(), set()))
    for i, (record, key) in enumerate(keyed):
        rank = _rank(record, key)
        for j in tree.query(geoms[i], predicate="dwithin", distance=tolerance_m):
            other, other_key = keyed[j]
            if other_key == key:
                continue
            if rank < _rank(other, other_key):
                donors, partners = near[(key, other_key)]
                donors.add(i)
                partners.add(int(j))
            else:
                donors, partners = near[(other_key, key)]
                donors.add(int(j))
                partners.add(i)

    pairs: list[dict] = []
    stretches = 0
    dropped_short = 0
    dropped_unpainted = 0
    dropped_same_blaze = 0
    shared_m = 0.0

    for donor_key, partner_key in sorted(near):
        donor_indices, partner_indices = near[(donor_key, partner_key)]
        donor_geom = _merged(unary_union([geoms[i] for i in sorted(donor_indices)]))
        partner_geom = unary_union([geoms[j] for j in sorted(partner_indices)])
        piece = donor_geom.intersection(partner_geom.buffer(tolerance_m))
        for n, part in enumerate(_line_parts(piece)):
            if part.length < min_length_m:
                dropped_short += 1
                continue
            midpoint = part.interpolate(0.5, normalized=True)
            donor = keyed[min(sorted(donor_indices), key=lambda i: (geoms[i].distance(midpoint), i))][0]
            partner = keyed[min(sorted(partner_indices), key=lambda j: (geoms[j].distance(midpoint), j))][0]
            # The blaze rule - see the docstring: no paint on one half, or
            # the same paint on both, is one line spelled twice.
            if not (_painted(donor) and _painted(partner)):
                dropped_unpainted += 1
                continue
            if donor["blaze_color"] == partner["blaze_color"]:
                dropped_same_blaze += 1
                continue
            stretch_wkt = shapely_transform(_TO_GEOGRAPHIC, part).wkt
            pairs.append(
                {
                    "id": f"{donor['id']}~shared~{partner['id']}~{n}",
                    **_carried(donor),
                    "concurrent_with": partner.get("name"),
                    "concurrent_source": partner.get("source"),
                    "concurrent_side": 1,
                    "wkt": stretch_wkt,
                }
            )
            pairs.append(
                {
                    "id": f"{partner['id']}~shared~{donor['id']}~{n}",
                    **_carried(partner),
                    "concurrent_with": donor.get("name"),
                    "concurrent_source": donor.get("source"),
                    "concurrent_side": -1,
                    "wkt": stretch_wkt,
                }
            )
            stretches += 1
            shared_m += part.length

    stats = {
        "trails": len({key for _, key in keyed}),
        "nameless_skipped": nameless,
        "stretches": stretches,
        "features": len(pairs),
        "shared_m": round(shared_m, 1),
        "dropped_short": dropped_short,
        "dropped_unpainted": dropped_unpainted,
        "dropped_same_blaze": dropped_same_blaze,
        "tolerance_m": tolerance_m,
        "min_length_m": min_length_m,
    }
    return pairs, stats
