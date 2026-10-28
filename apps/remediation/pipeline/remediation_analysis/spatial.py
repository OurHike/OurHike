"""Distances, complexes, nearest parking and land units.

Plain numpy and shapely rather than DuckDB's spatial extension. Neither join
needs more than a few thousand points, and the extension would bring
pipeline-tests.yml's seeding step (#321) into a suite that otherwise installs
in seconds.
"""

from __future__ import annotations

import math
from collections import defaultdict

import numpy as np
from shapely.geometry import Point, shape
from shapely.strtree import STRtree

from remediation_analysis.rules import DESIGNATION_ORDER

EARTH_RADIUS_M = 6_371_008.8
FEET_PER_METRE = 1 / 0.3048
FEET_PER_MILE = 5280


def feet_between(lat1, lon1, lat2, lon2):
    """Great-circle distance in feet. Takes scalars or numpy arrays that broadcast."""
    lat1, lon1, lat2, lon2 = (np.radians(np.asarray(v, dtype=float)) for v in (lat1, lon1, lat2, lon2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS_M * np.arcsin(np.sqrt(a)) * FEET_PER_METRE


def complexes(lats, lons, join_ft: float) -> list[int]:
    """Single-linkage groups: two sites closer than `join_ft` share a complex, and so does a chain of them.

    Returns a complex id per site, numbered from 0 in the order the complexes
    are first met. Sites are bucketed into a grid of cells at least `join_ft`
    on a side, so each site is compared only with the nine cells around it
    rather than with every other site.
    """
    lats = np.asarray(lats, dtype=float)
    lons = np.asarray(lons, dtype=float)
    n = len(lats)
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    # A cell's height in degrees of latitude is join_ft; its width in degrees
    # of longitude is the same distance at the highest latitude present, where
    # a degree of longitude is shortest, so no neighbour can be two cells away.
    deg_lat = join_ft / FEET_PER_METRE / (EARTH_RADIUS_M * math.pi / 180)
    widest = max(math.cos(math.radians(float(np.max(np.abs(lats))))), 1e-6) if n else 1.0
    deg_lon = deg_lat / widest
    cells: dict[tuple[int, int], list[int]] = defaultdict(list)
    for i in range(n):
        cells[(math.floor(lats[i] / deg_lat), math.floor(lons[i] / deg_lon))].append(i)

    for (cy, cx), members in cells.items():
        neighbours = [j for dy in (-1, 0, 1) for dx in (-1, 0, 1) for j in cells.get((cy + dy, cx + dx), ())]
        cand = np.array(neighbours)
        for i in members:
            d = feet_between(lats[i], lons[i], lats[cand], lons[cand])
            for j in cand[(d < join_ft) & (cand > i)]:
                a, b = find(i), find(int(j))
                if a != b:
                    parent[a] = b

    roots: dict[int, int] = {}
    return [roots.setdefault(find(i), len(roots)) for i in range(n)]


def nearest(lats, lons, other_lats, other_lons, block: int = 500) -> tuple[np.ndarray, np.ndarray]:
    """For each point, the index of the nearest `other` point and the distance to it in feet.

    In blocks, so 3,442 sites against 483 parking points never holds more than
    `block` rows of the distance matrix at once.
    """
    lats = np.asarray(lats, dtype=float)
    lons = np.asarray(lons, dtype=float)
    other_lats = np.asarray(other_lats, dtype=float)
    other_lons = np.asarray(other_lons, dtype=float)
    index = np.empty(len(lats), dtype=int)
    dist = np.empty(len(lats), dtype=float)
    for start in range(0, len(lats), block):
        stop = start + block
        d = feet_between(lats[start:stop, None], lons[start:stop, None], other_lats[None, :], other_lons[None, :])
        index[start:stop] = d.argmin(axis=1)
        dist[start:stop] = d.min(axis=1)
    return index, dist


def land_units(lats, lons, polygons: list[dict]) -> list[list[dict]]:
    """For each point, the properties of every PAD-US polygon containing it (zero, one or several)."""
    usable = [f for f in polygons if f.get("geometry")]
    geoms = [shape(f["geometry"]) for f in usable]
    tree = STRtree(geoms)
    found = []
    for lat, lon in zip(lats, lons):
        hits = tree.query(Point(float(lon), float(lat)), predicate="intersects")
        found.append([usable[int(h)]["properties"] for h in hits])
    return found


def most_specific(units: list[dict]) -> dict | None:
    """The unit whose designation is earliest in DESIGNATION_ORDER: a wilderness over the forest around it."""
    if not units:
        return None
    rank = {des: i for i, des in enumerate(DESIGNATION_ORDER)}
    return min(units, key=lambda u: rank.get(u.get("Des_Tp"), len(rank)))


#: How far around a site to look for trail, in degrees (about 4 miles of
#: latitude). The farthest CSI site from the A.T. was 15,661 ft, about 3 miles,
#: on 2026-10-24; a site with no trail inside this box falls back to the
#: nearest line anywhere.
TRAIL_SEARCH_DEG = 0.06

#: Eight compass points, clockwise from north, for "walk 40 ft west".
COMPASS = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")


def bearing_deg(from_lat, from_lon, to_lat, to_lon) -> float:
    """The initial great-circle bearing from one point to another, 0-360 clockwise from north."""
    p1, p2 = math.radians(from_lat), math.radians(to_lat)
    dl = math.radians(to_lon - from_lon)
    x = math.sin(dl) * math.cos(p2)
    y = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def compass(bearing: float) -> str:
    return COMPASS[int((bearing + 22.5) // 45) % 8]


def _segments(geometry) -> list[np.ndarray]:
    """Each part of a LineString or MultiLineString as an (n, 2) array of lon, lat."""
    parts = geometry.geoms if hasattr(geometry, "geoms") else [geometry]
    return [np.asarray(part.coords)[:, :2] for part in parts if len(part.coords) >= 2]


def from_trail(lats, lons, trail_features: list[dict]) -> list[dict | None]:
    """For each site, the nearest point on the trail, how far it is in feet, and the bearing from it to the site.

    The nearest point is found in a flat frame centred on each site (longitude
    scaled by the cosine of the site's latitude), which is exact enough over the
    few thousand feet involved and needs no projection library. The distance and
    bearing are then measured on the sphere. None for every site when there is
    no trail to measure from.
    """
    geoms = [shape(f["geometry"]) for f in trail_features if f.get("geometry")]
    if not geoms:
        return [None] * len(lats)
    tree = STRtree(geoms)
    out: list[dict | None] = []
    for lat, lon in zip(lats, lons):
        lat, lon = float(lat), float(lon)
        site = Point(lon, lat)
        candidates = tree.query(site.buffer(TRAIL_SEARCH_DEG))
        if len(candidates) == 0:
            candidates = [tree.nearest(site)]
        scale = math.cos(math.radians(lat))
        best = None
        for index in candidates:
            for coords in _segments(geoms[int(index)]):
                # Local frame: the site at the origin, units of degrees of latitude.
                xy = np.column_stack(((coords[:, 0] - lon) * scale, coords[:, 1] - lat))
                a, b = xy[:-1], xy[1:]
                d = b - a
                length2 = (d**2).sum(axis=1)
                t = np.clip(np.where(length2 > 0, -(a * d).sum(axis=1) / np.where(length2 > 0, length2, 1), 0), 0, 1)
                closest = a + d * t[:, None]
                dist2 = (closest**2).sum(axis=1)
                i = int(dist2.argmin())
                if best is None or dist2[i] < best[0]:
                    best = (dist2[i], closest[i])
        x, y = best[1]
        trail_lat, trail_lon = lat + y, lon + x / scale
        feet = float(feet_between(trail_lat, trail_lon, lat, lon))
        bearing = bearing_deg(trail_lat, trail_lon, lat, lon)
        out.append({"lat": trail_lat, "lon": trail_lon, "ft": feet, "bearing_deg": bearing, "toward": compass(bearing)})
    return out
