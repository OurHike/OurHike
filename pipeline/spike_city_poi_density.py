"""How crowded one phone screen of New York City is, and what each declutter
option would do to it.

features/NEARBY_TRAILS.md §10 records the crowding and declines to resolve it:

    "The 233-pin window holds 190 fountains and 43 restrooms and nothing else.
     The maintainer's call of 2026-09-15, with these numbers in front of them,
     is that this is normal for New York City... Density travels separately,
     and POI_SITES.md's co-location clustering is the mechanism that would
     actually answer it."

This is that separate travel. It measures the densest screen the five boroughs
produce and runs four candidate fixes over it, so the options are compared on
one window by one placement rule rather than on four people's intuitions.

THIS IS A SPIKE, and the code is throwaway. What should survive is the shape of
the answer, drawn in features/mockups/city-water-density.html from this file's
own output. The pure helpers are kept honest by
tests/test_spike_city_poi_density.py; the measurement half needs the published
artifact.

THE FINDING, because it reorders the options and is not obvious:
FOLDING BARELY MOVES THE PIN COUNT. All three folds land between 53 and 61
pins against today's 63, because `icon-allow-overlap: false` packs pins until
nothing more fits and has no notion of enough. What folding moves is the DOTS.
Only spacing moves the pins - 63 to 22. The two levers are not alternatives.

NOTHING PUBLISHES and nothing is fetched from a portal: the input is the
release a hiker already downloaded, so what is measured is the map that exists.

Run:  python spike_city_poi_density.py path/to/nearby_poi.geojson
"""

from __future__ import annotations

import collections
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path

# The phone this map is designed for, as features/POI_VISIBILITY.md sizes it.
VIEWPORT_W_PX = 390
VIEWPORT_H_PX = 700
EQUATOR_M_PER_PX_Z0 = 156_543.03392

# client/src/map/poiIcons.ts POI_PIN_SIZE, and poiLayers.ts's `icon-padding`.
PIN_SIZE_PX = 38
ICON_PADDING_PX = 2

# client/src/map/poiLayers.ts POI_PIN_MIN_ZOOM and POI_PIN_MIN_SCALE, and the
# upper anchor of POI_ICON_SIZE_EXPRESSION.
PIN_MIN_ZOOM = 9
PIN_MIN_SCALE = 0.8
PIN_FULL_ZOOM = 13

# client/src/lib/waypointVisibility.ts DEFAULT_SHOWN_TYPES - what a fresh
# install opens to, which is the only visibility state a crowding claim can be
# made about without also claiming what the hiker turned on.
DEFAULT_SHOWN = frozenset({"shelter", "water", "campsite", "privy"})

# client/src/map/poiPriority.ts POI_PRIORITY, the layer's `symbol-sort-key`.
PRIORITY = (
    "water",
    "shelter",
    "campsite",
    "resupply",
    "parking",
    "trailhead",
    "privy",
    "crossing",
    "viewpoint",
)

# The five boroughs, as a box. It bounds the O(n^2) sweep below rather than
# deciding anything: the question is about New York City, and running the sweep
# over 7,626 default-visible waypoints from Maine to Georgia would answer a
# different one at sixty times the cost.
CITY_BBOX = (-74.30, 40.47, -73.65, 40.95)

# How far apart two fountains may be and still be called one place, for the
# option that ports features/POI_SITES.md's two gates to New York City.
#
# @unvalidated - PICKED, NOT MEASURED. POI_SITES.md's own PROXIMITY_RADIUS_M is
# 60 m, chosen against ATC's shelter geometry, where the thing being folded is a
# privy behind a lean-to. A bank of fountains along a playground fence is a
# different shape and nobody has measured it. What would settle it: the
# distribution of fountain-to-fountain distance inside one `gispropnum`, which
# is one query against the portal layer and was not run.
SITE_RADIUS_M = 80.0

# The screen-space clustering radius, for the option this repository already
# argues against (lib/poi_sites.py's header). @unvalidated and deliberately so -
# it is roughly one pin box, which is the value a reader would guess, and the
# option is on the page to be measured rather than tuned.
CLUSTER_RADIUS_PX = 44.0


@dataclass(frozen=True)
class Point:
    lon: float
    lat: float
    poi_type: str
    place: str
    members: int = 1


def metres_per_pixel(latitude: float, zoom: float) -> float:
    """Ground metres per CSS pixel at a latitude, in MapLibre's zoom."""
    return EQUATOR_M_PER_PX_Z0 * math.cos(math.radians(latitude)) / 2 ** (zoom + 1)


def viewport_degrees(latitude: float, zoom: float) -> tuple[float, float]:
    """The phone map's width and height at a latitude, in degrees lon/lat."""
    m_per_px = metres_per_pixel(latitude, zoom)
    lat_deg = VIEWPORT_H_PX * m_per_px / 111_320.0
    lon_deg = VIEWPORT_W_PX * m_per_px / (111_320.0 * math.cos(math.radians(latitude)))
    return lon_deg, lat_deg


def icon_scale(zoom: float) -> float:
    """POI_ICON_SIZE_EXPRESSION, evaluated rather than approximated.

    A linear interpolation from PIN_MIN_SCALE at PIN_MIN_ZOOM to 1.0 at
    PIN_FULL_ZOOM, flat outside that band - which is what `interpolate` does
    past its end stops.
    """
    if zoom <= PIN_MIN_ZOOM:
        return PIN_MIN_SCALE
    if zoom >= PIN_FULL_ZOOM:
        return 1.0
    span = PIN_FULL_ZOOM - PIN_MIN_ZOOM
    return PIN_MIN_SCALE + (1.0 - PIN_MIN_SCALE) * (zoom - PIN_MIN_ZOOM) / span


def distance_m(a: Point, b: Point) -> float:
    """Flat-earth metres. Over the 6 mi this file ever measures across, the
    error against a great circle is under a metre."""
    dx = (a.lon - b.lon) * 111_320.0 * math.cos(math.radians(a.lat))
    dy = (a.lat - b.lat) * 111_320.0
    return math.hypot(dx, dy)


def densest_window(points: list[Point], lon_deg: float, lat_deg: float) -> tuple[int, tuple[float, float] | None]:
    """The most points any one viewport-sized window can hold, and its corner.

    Anchored on the points themselves rather than swept on a grid - a window
    whose south-west corner is not on a point can always be slid until it is
    without losing anything, so the maximum over point-anchored windows IS the
    maximum. The method is spike_oprhp_poi_density.py's, so the two
    measurements are comparable by construction.

    IT RETURNS THE CORNER, NOT THE CENTRE, and that is not tidiness. Handing
    back a centre means the caller re-derives the edges as `centre -/+ span/2`,
    and `west + span/2 - span/2` is not always `west` in binary floating point
    - so a point sitting exactly on the west edge, which the anchor point
    always is, falls inside the count and outside the re-selection. Measured:
    the window below reported 638 and re-selected 637. The corner is the datum
    both the count and the selection can share.
    """
    best = 0
    corner: tuple[float, float] | None = None
    for anchor in points:
        west, south = anchor.lon, anchor.lat
        count = sum(1 for p in points if west <= p.lon <= west + lon_deg and south <= p.lat <= south + lat_deg)
        if count > best:
            best = count
            corner = (west, south)
    return best, corner


def in_window(points: list[Point], corner: tuple[float, float], lon_deg: float, lat_deg: float) -> list[Point]:
    """The points inside the window with this south-west corner - the same
    comparison {@link densest_window} counted with, on the same datum."""
    west, south = corner
    return [p for p in points if west <= p.lon <= west + lon_deg and south <= p.lat <= south + lat_deg]


def window_centre(corner: tuple[float, float], lon_deg: float, lat_deg: float) -> tuple[float, float]:
    """Where the camera sits for a window with this corner. Used for placement
    and for drawing, never for selection - see {@link densest_window}."""
    return corner[0] + lon_deg / 2, corner[1] + lat_deg / 2


def place(
    points: list[Point],
    centre: tuple[float, float],
    zoom: float,
    padding_px: float = ICON_PADDING_PX,
) -> list[Point]:
    """MapLibre's collision pass, and the pins it would draw.

    Symbols are considered in `symbol-sort-key` order and a box is skipped when
    it overlaps one already placed. The box is square because MapLibre's
    collision box for a centred icon is - the pin artwork is a circle inside it.
    """
    m_per_px = metres_per_pixel(centre[1], zoom)
    box = (PIN_SIZE_PX + 2 * padding_px) * icon_scale(zoom)

    def to_px(p: Point) -> tuple[float, float]:
        x = (p.lon - centre[0]) * 111_320.0 * math.cos(math.radians(centre[1])) / m_per_px
        y = -(p.lat - centre[1]) * 111_320.0 / m_per_px
        return x, y

    def rank(p: Point) -> int:
        return PRIORITY.index(p.poi_type) if p.poi_type in PRIORITY else len(PRIORITY)

    taken: list[tuple[float, float]] = []
    pinned: list[Point] = []
    for point in sorted(points, key=rank):
        x, y = to_px(point)
        if any(abs(x - tx) < box and abs(y - ty) < box for tx, ty in taken):
            continue
        taken.append((x, y))
        pinned.append(point)
    return pinned


def fold_by_place(points: list[Point]) -> list[Point]:
    """One mark per (place, type). The park name the artifact already carries."""
    groups: dict[tuple[str, str], list[Point]] = collections.defaultdict(list)
    for p in points:
        groups[(p.place, p.poi_type)].append(p)
    return [_centroid(members) for members in groups.values()]


def fold_by_site(points: list[Point], radius_m: float = SITE_RADIUS_M) -> list[Point]:
    """features/POI_SITES.md's two gates: a NAME match AND proximity.

    Single-link within each name group, so a line of fountains down a boardwalk
    folds as one site rather than as a chain of pairs. Neither gate stands
    alone, for the reason lib/poi_sites.py gives: name-only ships a 903 km
    match, proximity-only merges two overlooks into one place.
    """
    groups: dict[tuple[str, str], list[Point]] = collections.defaultdict(list)
    for p in points:
        groups[(p.place, p.poi_type)].append(p)

    folded: list[Point] = []
    for members in groups.values():
        parent = list(range(len(members)))

        def find(i: int, parent: list[int] = parent) -> int:
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                if distance_m(members[i], members[j]) <= radius_m:
                    a, b = find(i), find(j)
                    if a != b:
                        parent[a] = b
        sites: dict[int, list[Point]] = collections.defaultdict(list)
        for i, member in enumerate(members):
            sites[find(i)].append(member)
        folded.extend(_centroid(site) for site in sites.values())
    return folded


def fold_by_pixels(
    points: list[Point],
    centre: tuple[float, float],
    zoom: float,
    radius_px: float = CLUSTER_RADIUS_PX,
) -> list[Point]:
    """Screen-space greedy clustering: the generic map-library answer.

    Kept at the cluster HEAD's coordinate rather than a centroid, which is what
    a library does and what makes the mark a real place for exactly one of its
    members. It re-clusters at every zoom by construction - that is the cost,
    not a limitation of this implementation.
    """
    m_per_px = metres_per_pixel(centre[1], zoom)

    def rank(p: Point) -> int:
        return PRIORITY.index(p.poi_type) if p.poi_type in PRIORITY else len(PRIORITY)

    heads: list[tuple[Point, int]] = []
    for point in sorted(points, key=rank):
        for index, (head, count) in enumerate(heads):
            if head.poi_type == point.poi_type and distance_m(point, head) / m_per_px <= radius_px:
                heads[index] = (head, count + 1)
                break
        else:
            heads.append((point, 1))
    return [Point(head.lon, head.lat, head.poi_type, head.place, count) for head, count in heads]


def _centroid(members: list[Point]) -> Point:
    return Point(
        lon=sum(m.lon for m in members) / len(members),
        lat=sum(m.lat for m in members) / len(members),
        poi_type=members[0].poi_type,
        place=members[0].place,
        members=sum(m.members for m in members),
    )


def screen_share(pin_count: int, zoom: float) -> float:
    """How much of the phone the pins cover, as a fraction.

    The pin's own disc rather than its collision box: the box is what the
    engine reserves, the disc is what a hiker sees ink on.
    """
    drawn = PIN_SIZE_PX * icon_scale(zoom)
    return pin_count * drawn * drawn / (VIEWPORT_W_PX * VIEWPORT_H_PX)


def load(path: Path) -> list[Point]:
    """Default-visible waypoints from a published nearby_poi.geojson."""
    payload = json.loads(path.read_text())
    return [
        Point(
            lon=props["lon"],
            lat=props["lat"],
            poi_type=props["poi_type"],
            place=props.get("name", ""),
        )
        for props in (f["properties"] for f in payload["features"])
        if props["poi_type"] in DEFAULT_SHOWN
    ]


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__.strip().splitlines()[-1], file=sys.stderr)
        return 2
    points = load(Path(argv[1]))
    west, south, east, north = CITY_BBOX
    city = [p for p in points if west < p.lon < east and south < p.lat < north]
    print(f"{len(points)} default-visible waypoints published, {len(city)} in the five boroughs\n")

    for zoom in (12, 13, 14, 15):
        lon_deg, lat_deg = viewport_degrees(40.7, zoom)
        total, corner = densest_window(city, lon_deg, lat_deg)
        if corner is None:
            continue
        window = in_window(city, corner, lon_deg, lat_deg)
        centre = window_centre(corner, lon_deg, lat_deg)
        by_type = collections.Counter(p.poi_type for p in window)
        span_w = VIEWPORT_W_PX * metres_per_pixel(40.7, zoom) / 1609.344
        span_h = VIEWPORT_H_PX * metres_per_pixel(40.7, zoom) / 1609.344
        print(
            f"z{zoom}  worst window {centre[0]:.4f},{centre[1]:.4f}  "
            f"{span_w:.2f} x {span_h:.2f} mi  {total} waypoints  {dict(by_type)}"
        )
        if zoom != 12:
            continue

        options = [
            ("today", window),
            ("1 - air (icon-padding 24)", window),
            ("2 - sites (place + proximity)", fold_by_site(window)),
            ("1 + 2", fold_by_site(window)),
            ("3 - fold to the place", fold_by_place(window)),
            ("4 - screen-space clusters", fold_by_pixels(window, centre, zoom)),
        ]
        print(f"\n      {'option':<32} {'marks':>6} {'pins':>6} {'ink':>6} {'dots':>6} {'fold':>6}")
        for label, marks in options:
            padding = 24.0 if label.startswith(("1 -", "1 +")) else ICON_PADDING_PX
            pinned = place(marks, centre, zoom, padding)
            print(
                f"      {label:<32} {len(marks):>6} {len(pinned):>6} "
                f"{screen_share(len(pinned), zoom):>5.0%} {len(marks) - len(pinned):>6} "
                f"{max(m.members for m in marks):>6}"
            )
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
