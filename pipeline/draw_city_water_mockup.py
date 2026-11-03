"""Draw features/mockups/city-water-density.html from the published artifact.

The mockup argues from six phone frames, and a frame drawn by hand is a
picture of a claim rather than the claim itself. This generates them, from
spike_city_poi_density.py's own window, placement and folds - so the picture
cannot disagree with the numbers printed beside it, and either can be re-run
when the release moves.

WHAT IT NEEDS, and neither is committed (CONTRIBUTING.md, "Data does not go in
commits"):

  1. A published `nearby_poi.geojson` - the same input the spike takes.
     curl -o nearby_poi.geojson \
       https://data.ourhike.org/releases/<release>/nearby_poi.geojson

  2. NYC Parks Properties as GeoJSON, for the ground under the frames. The
     layer is already registered as `nyc_park_polygons` in sources.json; this
     wants the raw portal copy rather than the clipped artifact.
     curl -o nyc_parks.geojson \
       'https://data.cityofnewyork.us/resource/enfh-gkve.geojson?$limit=2500'

Run:  python draw_city_water_mockup.py nearby_poi.geojson nyc_parks.geojson \
        ../features/mockups/city-water-density.html

IT WRITES THE PROSE TOO, and that is deliberate rather than convenient. The
page's prose quotes its own figures a dozen times - "63 pins", "30% of the
screen", "largest fold 12" - and a hand-written page beside a generated frame
is two copies of one measurement, which is the thing this repository keeps
finding out of date. So the numbers are interpolated from the same dicts the
frames are drawn from, and a re-run against a later release moves the
sentences with the pictures.

The page's own design is features/POI_VISIBILITY.md's residue, and the
stylesheet is lifted from features/mockups/corridor-view.html so the five
mockups read as one set.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

# The prose lives beside the drawing rather than inside it: this file knows
# about geometry and nothing about sentences.
from mockup_page import render
from spike_city_poi_density import (
    CITY_BBOX,
    PIN_SIZE_PX,
    Point,
    densest_window,
    fold_by_pixels,
    fold_by_place,
    fold_by_site,
    icon_scale,
    in_window,
    load,
    metres_per_pixel,
    place,
    screen_share,
    viewport_degrees,
    window_centre,
)

ZOOM = 12
VIEW_W, VIEW_H = 390, 700

# client/src/map/poiIcons.ts POI_COLORS, PIN_HALO_COLOR and PIN_EDGE_COLOR.
POI_COLORS = {"water": "#1c6ea4", "privy": "#7a2f66"}
PIN_HALO_COLOR = "#fffdf7"
PIN_EDGE_COLOR = "#2b2620"

# The `icon-padding` option 1 proposes. @unvalidated - see the constant's
# discussion on the page itself; it is the value that lands this screen near
# POI_VISIBILITY.md's ~16 and nothing more.
WIDE_PADDING_PX = 24.0

# How far a park boundary may sit outside the frame and still be drawn. A shape
# clipped exactly at the edge draws a straight line where a park continues, so
# the ground is cut wide and the SVG viewBox does the clipping.
GROUND_MARGIN_PX = 60.0

# Below this the ring is under one dot's ink, so dropping it loses nothing a
# reader could see and keeps 419 parks inside a few tens of kilobytes.
MIN_RING_PX = 2.0
MIN_VERTEX_GAP_PX = 1.2


def _arc(cx, cy, r, from_deg, to_deg, steps=14):
    """poiIcons.ts's own `arc`, at its own step count."""
    return [
        (
            cx + r * math.cos(math.radians(from_deg + (to_deg - from_deg) * i / steps)),
            cy + r * math.sin(math.radians(from_deg + (to_deg - from_deg) * i / steps)),
        )
        for i in range(steps + 1)
    ]


# poiIcons.ts's GLYPHS, ported vertex for vertex in its normalised 0..1 box:
# `water` is the droplet, `privy` the door with a keyhole cut even-odd.
GLYPHS = {
    "water": [[(0.5, 0.02), *_arc(0.5, 0.63, 0.33, -50, 230)]],
    "privy": [
        [
            (0.14, 0.16),
            (0.86, 0.16),
            (0.86, 0.30),
            (0.72, 0.30),
            (0.72, 0.96),
            (0.28, 0.96),
            (0.28, 0.30),
            (0.14, 0.30),
        ],
        [*_arc(0.485, 0.56, 0.12, 51.6, 308.4), *_arc(0.545, 0.56, 0.093, 278.8, 81.2)],
    ],
}


def glyph_path(kind: str, box: float, ox: float, oy: float) -> str:
    rings = []
    for ring in GLYPHS[kind]:
        points = [(ox + x * box, oy + y * box) for x, y in ring]
        rings.append("M" + "L".join(f"{x:.2f},{y:.2f}" for x, y in points) + "Z")
    return "".join(rings)


class Camera:
    """Web Mercator at one zoom, into the 390 x 700 box the spike measures."""

    def __init__(self, centre: tuple[float, float], zoom: float):
        self.centre = centre
        self.zoom = zoom
        self.m_per_px = metres_per_pixel(centre[1], zoom)

    def to_px(self, lon: float, lat: float) -> tuple[float, float]:
        east = (lon - self.centre[0]) * 111_320.0 * math.cos(math.radians(self.centre[1]))
        north = (lat - self.centre[1]) * 111_320.0
        return east / self.m_per_px + VIEW_W / 2, -north / self.m_per_px + VIEW_H / 2


def ground_paths(parks_geojson: Path, camera: Camera) -> list[str]:
    """NYC Parks' boundaries, clipped to the frame and thinned to the pixel.

    Radial-distance thinning rather than Douglas-Peucker, because these are
    CLOSED rings: a ring's first and last vertex are the same point, so the
    line RDP measures perpendicular distance from has zero length and every
    vertex collapses onto it. Measured: an RDP pass dropped all 419 parks.
    """
    payload = json.loads(parks_geojson.read_text())
    out = []
    for feature in payload["features"]:
        geometry = feature.get("geometry")
        if not geometry:
            continue
        polygons = geometry["coordinates"] if geometry["type"] == "MultiPolygon" else [geometry["coordinates"]]
        rings, touches = [], False
        for polygon in polygons:
            for ring in polygon:
                points = [camera.to_px(x, y) for x, y in ring]
                if not any(
                    -GROUND_MARGIN_PX <= x <= VIEW_W + GROUND_MARGIN_PX and -GROUND_MARGIN_PX <= y <= VIEW_H + GROUND_MARGIN_PX
                    for x, y in points
                ):
                    continue
                touches = True
                xs = [p[0] for p in points]
                ys = [p[1] for p in points]
                if max(xs) - min(xs) < MIN_RING_PX and max(ys) - min(ys) < MIN_RING_PX:
                    continue
                kept = [points[0]]
                for point in points[1:]:
                    if math.dist(point, kept[-1]) >= MIN_VERTEX_GAP_PX:
                        kept.append(point)
                if len(kept) > 3 and math.dist(kept[-1], kept[0]) < MIN_VERTEX_GAP_PX:
                    kept.pop()
                if len(kept) < 3:
                    continue
                rings.append("M" + "L".join(f"{x:.0f},{y:.0f}" for x, y in kept) + "Z")
        if touches and rings:
            out.append("".join(rings))
    return out


def pin_svg(x: float, y: float, kind: str, members: int, zoom: float) -> str:
    """poiIcons.ts's pinGeometry at this zoom's icon size: disc, halo, hairline
    edge, and the member badge when several waypoints ride one pin."""
    radius = PIN_SIZE_PX * icon_scale(zoom) / 2
    edge = radius / 15
    halo = radius / 6
    disc = radius - edge - halo
    box = disc * math.sqrt(2) * 0.86
    colour = POI_COLORS.get(kind, "#5a5346")
    parts = [
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius - edge / 2:.2f}" fill="{PIN_HALO_COLOR}"'
        f' stroke="{PIN_EDGE_COLOR}" stroke-width="{edge:.2f}"/>',
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{disc:.2f}" fill="{colour}"/>',
        f'<path d="{glyph_path(kind, box, x - box / 2, y - box / 2)}" fill="{PIN_HALO_COLOR}" fill-rule="evenodd"/>',
    ]
    if members > 1:
        # poiIcons.ts: the badge radius is 0.555 of the pin's, and its ring is
        # DERIVED from the disc so it clears the silhouette at any size.
        badge = radius * 0.555
        ring = disc + badge + edge / 3
        bx, by = x + ring * 0.707, y - ring * 0.707
        parts += [
            f'<circle cx="{bx:.1f}" cy="{by:.1f}" r="{badge:.2f}" fill="{PIN_HALO_COLOR}"'
            f' stroke="{PIN_EDGE_COLOR}" stroke-width="{edge * 0.8:.2f}"/>',
            f'<circle cx="{bx:.1f}" cy="{by:.1f}" r="{badge * 0.8:.2f}" fill="{colour}"/>',
            f'<text x="{bx:.1f}" y="{by + badge * 0.33:.1f}" text-anchor="middle"'
            f' font-size="{badge * 1.02:.1f}" font-weight="700" fill="{PIN_HALO_COLOR}"'
            f' font-family="Public Sans, sans-serif">{members}</text>',
        ]
    return "".join(parts)


def frame_svg(marks: list[Point], pinned: set[int], camera: Camera, label: str) -> str:
    """One phone screen. Dots first - style.ts draws the circle layer under the
    pins - then the pins that won placement."""
    dots, pins = [], []
    for index, mark in enumerate(marks):
        x, y = camera.to_px(mark.lon, mark.lat)
        colour = POI_COLORS.get(mark.poi_type, "#5a5346")
        dots.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.9" fill="{colour}" stroke="{PIN_HALO_COLOR}" stroke-width="1"/>')
        if index in pinned:
            pins.append(pin_svg(x, y, mark.poi_type, mark.members, camera.zoom))
    share = screen_share(len(pinned), camera.zoom)
    return (
        f'<svg class="screen" viewBox="0 0 {VIEW_W} {VIEW_H}" role="img"'
        f' aria-label="{label}: {len(marks)} waypoints, {len(pinned)} pins,'
        f' {share:.0%} of the screen under pin">'
        f'<rect width="{VIEW_W}" height="{VIEW_H}" fill="var(--map-paper)"/>'
        f'<use href="#nyc-ground" fill="var(--map-park)" stroke="var(--map-park-edge)"'
        f' stroke-width="0.6"/>'
        f"{''.join(dots)}{''.join(pins)}</svg>"
    )


def build_frames(window: list[Point], camera: Camera) -> dict[str, dict]:
    """Every option over the same window, through the same placement code."""
    sites = fold_by_site(window)
    places = fold_by_place(window)
    clusters = fold_by_pixels(window, camera.centre, camera.zoom)
    recipes = {
        "today": (window, 2.0),
        "air": (window, WIDE_PADDING_PX),
        "sites": (sites, 2.0),
        "both": (sites, WIDE_PADDING_PX),
        "places": (places, 2.0),
        "clusters": (clusters, 2.0),
    }
    labels = {
        "today": "Today",
        "air": "Option 1 · Air",
        "sites": "Option 2 · Sites",
        "both": "Options 1 + 2",
        "places": "Option 3 · Parks",
        "clusters": "Option 4 · Screen clusters",
    }
    built = {}
    for slug, (marks, padding) in recipes.items():
        drawn = place(marks, camera.centre, camera.zoom, padding)
        # `place` returns the same objects it was given, so identity recovers
        # which marks won without re-deriving them from coordinates - where
        # two folded centroids can legitimately coincide.
        won = {i for i, m in enumerate(marks) if any(m is d for d in drawn)}
        built[slug] = {
            "svg": frame_svg(marks, won, camera, labels[slug]),
            "label": labels[slug],
            "marks": len(marks),
            "pins": len(drawn),
            "dots": len(marks) - len(drawn),
            "ink": screen_share(len(drawn), camera.zoom),
            "fold": max(m.members for m in marks),
            "padding": padding,
        }
    return built


def zoom_rows(city: list[Point]) -> list[dict]:
    """One row per zoom for the page's second table, each on its OWN densest
    window - so the four rows are four pieces of the city rather than one place
    zoomed, which the table says outright.

    `pins_without_water` is the deferred-pin idea the page rules out: the same
    window with every water pin withheld, which is how the finding that the
    restrooms simply take the space is stated as a number rather than asserted.
    """
    rows = []
    for zoom in (12, 13, 14, 15):
        lon_deg, lat_deg = viewport_degrees(40.7, zoom)
        _, corner = densest_window(city, lon_deg, lat_deg)
        if corner is None:
            continue
        window = in_window(city, corner, lon_deg, lat_deg)
        centre = window_centre(corner, lon_deg, lat_deg)
        dry = [p for p in window if p.poi_type != "water"]
        m_per_px = metres_per_pixel(40.7, zoom)
        rows.append(
            {
                "zoom": zoom,
                "span_w": VIEW_W * m_per_px / 1609.344,
                "span_h": VIEW_H * m_per_px / 1609.344,
                "waypoints": len(window),
                "pins": len(place(window, centre, zoom)),
                "pins_without_water": len(place(dry, centre, zoom)),
            }
        )
    return rows


def main(argv: list[str]) -> int:
    if len(argv) != 4:
        print("usage: draw_city_water_mockup.py POI.geojson PARKS.geojson OUT.html", file=sys.stderr)
        return 2
    poi_path, parks_path, out_path = (Path(a) for a in argv[1:])

    points = load(poi_path)
    west, south, east, north = CITY_BBOX
    city = [p for p in points if west < p.lon < east and south < p.lat < north]
    lon_deg, lat_deg = viewport_degrees(40.7, ZOOM)
    total, corner = densest_window(city, lon_deg, lat_deg)
    if corner is None:
        print("no waypoints in the city box", file=sys.stderr)
        return 1
    window = in_window(city, corner, lon_deg, lat_deg)
    camera = Camera(window_centre(corner, lon_deg, lat_deg), ZOOM)
    assert len(window) == total, "the window selected has to be the window counted"

    ground = ground_paths(parks_path, camera)
    frames = build_frames(window, camera)
    page = render(frames, ground, camera, window, zoom_rows(city))
    out_path.write_text(page)
    print(f"{out_path} - {len(page) / 1024:.0f} KB, {len(ground)} park boundaries")
    for slug, frame in frames.items():
        print(
            f"  {slug:<10} {frame['marks']:>4} marks {frame['pins']:>3} pins "
            f"{frame['ink']:>4.0%} ink {frame['dots']:>4} dots fold {frame['fold']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
