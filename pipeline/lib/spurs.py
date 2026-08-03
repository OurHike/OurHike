"""What a blue-blazed spur actually leads to.

The lines are already fetched, already blue, already rendered. What was
missing is the *relationship*: we hold spur LineStrings and shelter/water/
viewpoint Points and nothing connecting them, so the map draws a blue line
and cannot say "this goes to Rocky Run Shelter, 0.2 mi."

That is the decision a thru-hiker makes a dozen times a day - is it worth
walking down there, and how far back up - and the map currently declines to
help with it.

HOW THE LINK IS MADE. Each spur has two ends. The one nearer the AT is where
it joins; the other is where it goes. The nearest destination-type POI to that
far end is the spur's destination. Measured on real data (features/
SPUR_TRAILS.md, n=300): half of all spurs end within a metre of their
destination, 231 of 300 within 50 m, 265 of 300 within 150 m. This is not a
heuristic that might work - it demonstrably resolves ~88% of spurs.

WHY THE MATCH DISTANCE IS PUBLISHED RATHER THAN THRESHOLDED AWAY. 150 m
captures 88% of spurs; 50 m captures 77% with far higher confidence. Which to
believe is a judgement about real mismatches, not a percentile, and it is not
settled. So the export resolves out to the loose bound and publishes how far
the match actually was. The client can then present a 1 m match differently
from a 140 m one, and tightening the rule later costs a client release rather
than a 25-minute re-export.

NO DUCKDB HERE, DELIBERATELY. The join is 784 spurs against 2,532 POIs, which
is nothing, and export_trails.py's spatial work is already the part of this
pipeline that cannot be exercised without a spatial extension. Keeping the
rule in plain Python means the thing most likely to be wrong - which end is
the junction, what counts as a destination, when to give up - is unit-tested
directly instead of inferred from a query plan.
"""

from __future__ import annotations

from math import cos, hypot, radians

# One degree of latitude, in metres. Constant enough for these distances:
# it varies by ~1% pole to equator, against thresholds of 50-150 m.
METERS_PER_DEGREE = 111_320.0

# `side_trails.Type` is a real ArcGIS coded-value domain (features/
# SPUR_TRAILS.md has the full table). 3 is "Spur (eg View, Camp)" - 784 of
# the 1,200 side trails.
SPUR_TYPE_CODE = "3"

# 60 features carry the literal string "Signficant Non-Blaze" in `Type`
# instead of the code "2" - including the misspelling, missing the second
# `i`. Exactly the mess `Blaze` already had, and handled the same way: it
# decodes to a known value rather than falling through as unrecognised.
# Sixty side trails treated as undecodable would be sixty loud warnings about
# data that is merely ugly.
TYPE_LITERAL_ALIASES = {
    "signficant non-blaze": "2",
    "significant non-blaze": "2",
}

# How close an endpoint must sit to the AT to be called a junction.
#
# Generous on purpose. Its job is not to decide whether a spur is real - the
# `Type` field already did that - only to tell the two ends apart, and being
# wrong about which end is which turns a destination lookup into a lookup at
# the wrong end of the trail.
JUNCTION_MAX_M = 100.0

# How far from a spur's far end a POI may sit and still be recorded as its
# destination.
#
# The LOOSE bound, and the client narrows it. See the module docstring: this
# number is deliberately not the display threshold, so that changing the
# display threshold does not mean re-exporting.
DESTINATION_MAX_M = 150.0


def distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Equirectangular distance in metres.

    Not haversine, and not a projection. At the distances that matter here -
    under a kilometre - the flat approximation is accurate to well under 1%,
    while cos() at the midpoint latitude is what keeps a longitude degree
    honest across the trail's 34-46 degree span. Against a 150 m threshold
    that error is centimetres.
    """
    mean_lat = radians((lat1 + lat2) / 2)
    dy = (lat2 - lat1) * METERS_PER_DEGREE
    dx = (lon2 - lon1) * METERS_PER_DEGREE * cos(mean_lat)
    return hypot(dx, dy)


class PointIndex:
    """Nearest-point lookup over a fixed set of lat/lon points.

    A flat grid, sized so that the eight cells around a query's own always
    cover the search radius. Nothing clever is needed: the biggest set here is
    the AT centerline's vertices, and the alternative - comparing every spur
    endpoint against every vertex - is the only version slow enough to notice.

    Cell width in longitude is computed at the NORTHERNMOST point in the set,
    where a degree of longitude is shortest. That makes the cells at least as
    wide in metres everywhere else, so the 3x3 search can never miss a point
    inside the radius by being too narrow further south.
    """

    def __init__(self, points: list[tuple[float, float, object]], radius_m: float):
        self.radius_m = radius_m
        self.cells: dict[tuple[int, int], list[tuple[float, float, object]]] = {}

        max_abs_lat = max((abs(lat) for lat, _, _ in points), default=0.0)
        self.cell_lat = radius_m / METERS_PER_DEGREE
        self.cell_lon = radius_m / (METERS_PER_DEGREE * max(cos(radians(max_abs_lat)), 1e-6))

        for lat, lon, payload in points:
            self.cells.setdefault(self._cell(lat, lon), []).append((lat, lon, payload))

    def _cell(self, lat: float, lon: float) -> tuple[int, int]:
        return (int(lat // self.cell_lat), int(lon // self.cell_lon))

    def nearest(self, lat: float, lon: float) -> tuple[object | None, float | None]:
        """The closest indexed point within the radius, and how far it was.

        `(None, None)` when nothing is in range - which is an answer, not a
        failure. ~12% of spurs genuinely lead somewhere unmapped.
        """
        row, col = self._cell(lat, lon)
        best: object | None = None
        best_distance: float | None = None

        for d_row in (-1, 0, 1):
            for d_col in (-1, 0, 1):
                for cand_lat, cand_lon, payload in self.cells.get((row + d_row, col + d_col), ()):
                    distance = distance_m(lat, lon, cand_lat, cand_lon)
                    if distance <= self.radius_m and (best_distance is None or distance < best_distance):
                        best, best_distance = payload, distance

        return best, best_distance


def decode_type(raw: object, coded_domain: dict | None) -> str | None:
    """A side trail's `Type` as a domain code, or None if it does not decode.

    Handles the three shapes the real data actually contains: the code as a
    string ("3"), the code as an int (3, since a JSON round trip loses which
    it was), and the literal domain *name* in place of the code - including
    the misspelled one.
    """
    if raw is None:
        return None

    text = str(raw).strip()
    if not text:
        return None

    domain = coded_domain or {}
    if text in domain:
        return text

    lowered = text.lower()
    if lowered in TYPE_LITERAL_ALIASES:
        return TYPE_LITERAL_ALIASES[lowered]

    # The domain read the other way round: a feature carrying the name where
    # the code was expected. Matched case-insensitively because the misspelled
    # values prove nobody is normalising these on the way in.
    for code, name in domain.items():
        if isinstance(name, str) and name.strip().lower() == lowered:
            return code

    # No domain to check against (the FeatureServer lookup can fail and is
    # tolerated elsewhere in this pipeline) - a bare numeric code is still
    # usable, and refusing it would drop every spur on a bad metadata day.
    if not domain and text.isdigit():
        return text

    return None


def is_spur(raw_type: object, coded_domain: dict | None) -> bool:
    return decode_type(raw_type, coded_domain) == SPUR_TYPE_CODE


def line_endpoints(coordinates: list) -> tuple[tuple[float, float], tuple[float, float]] | None:
    """A line's two ends as (lat, lon), from GeoJSON LineString or
    MultiLineString coordinates.

    A MultiLineString's ends are the first part's first point and the last
    part's last point. That is right for a spur, whose parts are one path
    broken by a digitising seam rather than separate trails - and where it is
    wrong, both candidate ends still sit on the same spur, so the worst case
    is a destination lookup a few metres off rather than at the wrong end.
    """
    if not coordinates:
        return None

    flat = coordinates
    if isinstance(coordinates[0][0], (list, tuple)):  # MultiLineString
        parts = [part for part in coordinates if part]
        if not parts:
            return None
        first, last = parts[0][0], parts[-1][-1]
    else:
        if len(flat) < 2:
            return None
        first, last = flat[0], flat[-1]

    return (first[1], first[0]), (last[1], last[0])


def orient(
    ends: tuple[tuple[float, float], tuple[float, float]],
    centerline: PointIndex,
) -> tuple[tuple[float, float], tuple[float, float]] | None:
    """(junction, destination_end), or None if the ends cannot be told apart.

    The junction is whichever end is nearer the AT. Coordinate order does not
    settle this: `side_trails` is not guaranteed to run away from the trail,
    the same thing `export_elevation.py`'s ordered_oriented_parts() exists to
    handle for the centerline.

    Returns None in two cases, both of which must not be guessed at:

    - BOTH ends sit on the AT. That is an alternate route, not a spur, and ATC
      already codes those as Type=1 - but if one appears under Type=3 anyway,
      picking whichever end won by a metre would name a destination that is
      just a different bit of the AT.
    - NEITHER end is near the AT. Then this line's relationship to the trail is
      not what the code assumed, and the "far end" is not meaningfully far
      from anything.
    """
    first, last = ends
    _, first_distance = centerline.nearest(*first)
    _, last_distance = centerline.nearest(*last)

    first_on_trail = first_distance is not None
    last_on_trail = last_distance is not None

    if first_on_trail and last_on_trail:
        return None
    if first_on_trail:
        return first, last
    if last_on_trail:
        return last, first
    return None


def resolve_destination(
    coordinates: list,
    centerline: PointIndex,
    destinations: PointIndex,
) -> dict:
    """One spur's destination link.

    Always returns a dict with the same keys, so a caller never has to
    distinguish "no destination" from "this spur was not processed":

        destination_poi_id      the POI's id, or None
        destination_distance_m  how far it was, or None

    A null destination is the ordinary situation for ~12% of spurs - some lead
    somewhere genuinely unmapped, some to a viewpoint ATC has not digitised -
    and is reported as absence rather than as an error.
    """
    empty = {"destination_poi_id": None, "destination_distance_m": None}

    ends = line_endpoints(coordinates)
    if ends is None:
        return empty

    oriented = orient(ends, centerline)
    if oriented is None:
        return empty

    _junction, far_end = oriented
    poi_id, distance = destinations.nearest(*far_end)
    if poi_id is None or distance is None:
        return empty

    return {
        "destination_poi_id": poi_id,
        # Rounded to the metre. Publishing more precision than an equirect-
        # angular distance between two GPS-surveyed points can support would
        # be inviting a reader to trust digits that are not there.
        "destination_distance_m": round(distance),
    }


def build_centerline_index(features: list[dict]) -> PointIndex:
    """An index over every centerline vertex, for the junction test.

    Vertices rather than segments, which is an approximation: a point beside
    the middle of a long segment reads as further from the trail than it is.
    The error is bounded by the centerline's own vertex spacing, which in
    ATC's data is metres - against a 100 m junction threshold, that changes no
    answer. Point-to-segment distance would remove it and would need segment
    indexing to stay fast, which is a real cost for no change in behaviour.
    """
    points: list[tuple[float, float, object]] = []
    for feature in features:
        geometry = feature.get("geometry") or {}
        for lon, lat in _iter_coordinates(geometry):
            points.append((lat, lon, None))
    return PointIndex(points, JUNCTION_MAX_M)


def build_destination_index(pois: list[dict]) -> PointIndex:
    """An index over candidate destination POIs, keyed by their published id.

    `pois` are export_poi.py's unified records, so whichever types the caller
    passes in are the types that can be named as a destination. That choice is
    the caller's rather than this module's - features/SPUR_TRAILS.md leaves it
    open, noting that a privy is a real destination but a strange thing to
    name as one.
    """
    points: list[tuple[float, float, object]] = []
    for poi in pois:
        lat, lon = poi.get("lat"), poi.get("lon")
        if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
            points.append((float(lat), float(lon), poi.get("id")))
    return PointIndex(points, DESTINATION_MAX_M)


def _iter_coordinates(geometry: dict):
    coordinates = geometry.get("coordinates") or []
    if not coordinates:
        return
    if geometry.get("type") == "MultiLineString":
        for part in coordinates:
            yield from part
    else:
        yield from coordinates
