"""The challenge map's geometry, ready to draw on a phone (#1965).

Usage: python export_challenge_map.py

Writes data/processed/challenge_map.json and its manifest, which publish.py
ships beside challenges.json. The phone projects and draws it with no tiles
and no MapLibre (client/src/lib/blazeMap.ts): the A.T. as a cased line, the
states and Canada as a paper map under it, and the places on a challenge
card as pins along it - on "Where your trail karma is" and on the share
poster. features/CHALLENGES_BLAZE_CARD.md, "The map: reuse, do not invent",
is the brief.

WHAT IT READS
  - trails.geojson's `centerline` features and trail_miles.json's mile for
    every vertex of each (export_trails.py writes both): the same line and
    the same mile axis every POI mile is placed on, so a pin at an item's
    published mile lands on the drawn line. The brief's mock maps used an
    OpenStreetMap line placed by proportion instead; this replaces it.
  - us-atlas's states and world-atlas's Canada, as fetch_atlas_outlines.py
    lands them (lib/atlas_sources.py, sources.json's `atlas_file` rows).

WHAT IT WRITES, and how much of it a reader can trust
  - `trail`: the centerline as runs in mile order, each vertex with its mile.
    Each published chain is turned to run north (its own miles decide), the
    chains are sorted by their first mile and joined where one ends within
    STITCH_MILES of the next, and each run is thinned with Douglas-Peucker
    at TRAIL_TOLERANCE_M, measured in EPSG:5070 metres. Every kept vertex is
    one of the published ones, with its published mile, so the phone can cut
    the walked stretch out of the line by mile without guessing.
  - `states`, `borders`, `canada`: outlines clipped to FRAME and thinned at
    OUTLINE_TOLERANCE_DEG. A picture's precision, not a survey's.
  - `state_runs`: which state each stretch of trail is in, by mile, from
    every published centerline vertex tested against us-atlas's state
    outlines before any thinning. MEASURED 2026-11-04 against UA's published
    trails.geojson and trail_miles.json (2,191.6 of the trail's miles covered
    by 465 chains, no gap between them wider than 0.45 mi): 206 runs, every
    vertex inside some state. Where the trail CROSSES a state line the run
    boundary is within a mile or so of it - the outline is 1:10m and
    cartographic. Where the trail FOLLOWS one it alternates: NC/TN from about
    mile 176 to 402, VA/WV near 652 and from 1009 to 1027, NJ/NY from 1346 to
    1371, 108 of the 206 runs shorter than half a mile. There the outline's
    simplification, not the ground, decides which side a vertex falls, and a
    place on those stretches can honestly be called either state. @unvalidated
    against the ATC's own state mileages, which would settle the crossings;
    nothing settles the alternation but a survey-grade boundary, and the
    phone only ever names a state, never counts miles in it.
  - `credits`: who each layer belongs to, read from sources.json, never typed.
  - `notices`: us-atlas's and world-atlas's ISC copyright and permission
    notice, which their licence asks to appear in every copy.

No `generated_at`, as challenges.json carries none: a run that changes
nothing writes the same bytes, and publish.py uploads nothing new.

A MISSING INPUT WRITES NOTHING, and takes away the manifest an earlier run in
the same workspace left, so publish.py never ships a map drawn from someone
else's run. The phone reads an absent artifact as "no map yet" and shows the
list alone, which is the honest fallback the brief asks for.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import shapely
from pyproj import Transformer
from shapely.geometry import box
from shapely.geometry.base import BaseGeometry

from lib import topojson
from lib.atlas_sources import ATLAS_FILES, US_ATLAS_KEY, WORLD_ATLAS_KEY
from lib.manifest_paths import to_manifest_path
from lib.source_registry import find_source, load_registry

ROOT = Path(__file__).parent
PROCESSED_DIR = ROOT / "data" / "processed"
TRAILS_PATH = PROCESSED_DIR / "trails.geojson"
TRAIL_MILES_PATH = PROCESSED_DIR / "trail_miles.json"
SOURCES_PATH = ROOT / "sources.json"
OUT_PATH = PROCESSED_DIR / "challenge_map.json"
MANIFEST_PATH = PROCESSED_DIR / "challenge_map_manifest.json"

FORMAT = 1
#: How trails.geojson marks the A.T. itself (export_challenges.py's constant).
CENTERLINE_SOURCE = "centerline"
CENTERLINE_KEY = "centerline"

#: The fourteen trail states, south to north, by us-atlas's FIPS ids.
TRAIL_STATES: tuple[tuple[str, str], ...] = (
    ("13", "GA"),
    ("37", "NC"),
    ("47", "TN"),
    ("51", "VA"),
    ("54", "WV"),
    ("24", "MD"),
    ("42", "PA"),
    ("34", "NJ"),
    ("36", "NY"),
    ("09", "CT"),
    ("25", "MA"),
    ("50", "VT"),
    ("33", "NH"),
    ("23", "ME"),
)
TRAIL_STATE_CODES = dict(TRAIL_STATES)

#: (west, south, east, north) in degrees: everything the phone may show
#: around the trail. Reasoned, not picked: the trail spans 84.2-68.9°W and
#: 34.6-45.9°N, and the narrowest frame the phone fits it into (the welcome
#: map, 358 by 330 px) shows about four degrees of longitude either side of it
#: under the conic projection; the brief's mock maps reach Lake Michigan's
#: shore at about 87.5°W. A margin past both, so no frame shows a cut edge.
FRAME = (-92.0, 30.5, -62.0, 49.5)

#: Outline thinning, in degrees. Reasoned: the share poster is the widest
#: drawing, about 1,100 px across the frame's 30 degrees of longitude at the
#: trail's latitude, so 0.01° is under half a pixel there.
OUTLINE_TOLERANCE_DEG = 0.01
#: Trail thinning, in metres. @unvalidated: picked to land near the brief's
#: "~1,000 points at phone scale" on the published line (the count is printed
#: on every run); 400 m is about a sixth of a poster pixel, so the thinned
#: line cannot be told from the full one there. A phone in a hand would settle
#: whether fewer points still read as the trail.
TRAIL_TOLERANCE_M = 400.0
#: Chains are joined into one run when the next starts within this many miles
#: of where the last ended. Reasoned: the widest gap between published chains
#: measured 0.45 mi (2026-11-04), and half a mile is under a pixel on any
#: drawing of the whole trail, so joining across it draws no false shortcut.
STITCH_MILES = 0.5

#: Decimals kept: about 11 m of longitude at this latitude for a vertex, a
#: hundredth of a mile for its mile.
COORD_DECIMALS = 4
MILE_DECIMALS = 2

#: The ISC notice us-atlas and world-atlas ship under, read from both
#: packages' LICENSE at the pinned versions on 2026-11-04. Their one
#: condition is that it appear in all copies.
ISC_NOTICE = (
    "us-atlas and world-atlas: Copyright 2013-2019 Michael Bostock. "
    "Permission to use, copy, modify, and/or distribute this software for any purpose with or without fee is hereby "
    "granted, provided that the above copyright notice and this permission notice appear in all copies. "
    'THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES WITH REGARD TO THIS SOFTWARE INCLUDING '
    "ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY SPECIAL, "
    "DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, "
    "WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE "
    "USE OR PERFORMANCE OF THIS SOFTWARE."
)

_TO_METRES = Transformer.from_crs("EPSG:4326", "EPSG:5070", always_xy=True)


# --- the trail -------------------------------------------------------------


def load_chains(trails: dict, miles: dict) -> list[tuple[np.ndarray, np.ndarray]]:
    """Every centerline chain as (lon/lat array, mile array), turned to run
    north by its own miles. A chain trail_miles.json has no miles for, or
    whose vertex count disagrees with its miles, is skipped and named."""
    chains: list[tuple[np.ndarray, np.ndarray]] = []
    for feature in trails.get("features") or []:
        properties = feature.get("properties") or {}
        if properties.get("source") != CENTERLINE_SOURCE:
            continue
        geometry = feature.get("geometry") or {}
        if geometry.get("type") != "LineString":
            continue
        chain_id = properties.get("id")
        chain_miles = miles.get(chain_id)
        coordinates = geometry.get("coordinates") or []
        if chain_miles is None or len(chain_miles) != len(coordinates) or len(coordinates) < 2:
            print(f"  skipped centerline chain {chain_id!r}: no per-vertex miles that match its vertices", file=sys.stderr)
            continue
        xy = np.array([(float(c[0]), float(c[1])) for c in coordinates])
        m = np.array(chain_miles, dtype=float)
        if m[0] > m[-1]:
            xy, m = xy[::-1], m[::-1]
        chains.append((xy, m))
    return chains


def stitch_runs(chains: list[tuple[np.ndarray, np.ndarray]]) -> list[tuple[np.ndarray, np.ndarray]]:
    """Chains in mile order, joined where one ends within STITCH_MILES of the
    next one's start (an overlap counts as within)."""
    runs: list[tuple[np.ndarray, np.ndarray]] = []
    for xy, m in sorted(chains, key=lambda chain: float(chain[1][0])):
        if runs and m[0] - runs[-1][1][-1] <= STITCH_MILES:
            last_xy, last_m = runs[-1]
            runs[-1] = (np.vstack([last_xy, xy]), np.concatenate([last_m, m]))
        else:
            runs.append((xy, m))
    return runs


def simplify_indices(points: np.ndarray, tolerance: float) -> list[int]:
    """Douglas-Peucker over `points` (n by 2, metres), returning the indices
    kept, first and last always among them. Indices rather than coordinates,
    so each kept vertex keeps its own mile."""
    n = len(points)
    if n <= 2:
        return list(range(n))
    keep = np.zeros(n, dtype=bool)
    keep[0] = keep[-1] = True
    stack = [(0, n - 1)]
    while stack:
        start, end = stack.pop()
        if end - start < 2:
            continue
        a, b = points[start], points[end]
        segment = points[start + 1 : end]
        ab = b - a
        length = float(np.hypot(*ab))
        if length == 0.0:
            distances = np.hypot(*(segment - a).T)
        else:
            distances = np.abs(ab[0] * (segment[:, 1] - a[1]) - ab[1] * (segment[:, 0] - a[0])) / length
        worst = int(np.argmax(distances))
        if float(distances[worst]) > tolerance:
            middle = start + 1 + worst
            keep[middle] = True
            stack.append((start, middle))
            stack.append((middle, end))
    return [int(i) for i in np.flatnonzero(keep)]


def thin_run(xy: np.ndarray, m: np.ndarray, tolerance_m: float = TRAIL_TOLERANCE_M) -> dict:
    """One run as the phone reads it: coordinates and miles, thinned."""
    x, y = _TO_METRES.transform(xy[:, 0], xy[:, 1])
    kept = simplify_indices(np.column_stack([x, y]), tolerance_m)
    return {
        "coordinates": [[round(float(xy[i, 0]), COORD_DECIMALS), round(float(xy[i, 1]), COORD_DECIMALS)] for i in kept],
        "miles": [round(float(m[i]), MILE_DECIMALS) for i in kept],
    }


# --- the states ------------------------------------------------------------


def state_runs(chains: list[tuple[np.ndarray, np.ndarray]], states: dict[str, BaseGeometry]) -> list[list]:
    """[code, from_mile, to_mile] in mile order: every vertex of every chain
    tested against the state outlines, runs of one state merged. A run ends
    where the next begins, so the runs leave no gap a mile could fall into;
    a vertex inside no outline (none, measured) is passed over."""
    if not chains:
        return []
    xy = np.vstack([chain[0] for chain in chains])
    m = np.concatenate([chain[1] for chain in chains])
    codes = list(states)
    tree = shapely.STRtree([states[code] for code in codes])
    point_index, state_index = tree.query(shapely.points(xy), predicate="within")
    found = np.full(len(xy), -1)
    found[point_index] = state_index
    order = np.argsort(m, kind="stable")
    runs: list[list] = []
    for i in order:
        if found[i] < 0:
            continue
        code, mile = codes[found[i]], round(float(m[i]), MILE_DECIMALS)
        if runs and runs[-1][0] == code:
            runs[-1][2] = mile
            continue
        if runs:
            runs[-1][2] = mile
        runs.append([code, mile, mile])
    return runs


def _rings(geometry: BaseGeometry) -> list[list[list[list[float]]]]:
    """A (Multi)Polygon as a list of polygons, each a list of rings, each a
    list of [lon, lat] - GeoJSON's MultiPolygon coordinates."""
    if geometry.is_empty:
        return []
    polygons = list(geometry.geoms) if hasattr(geometry, "geoms") else [geometry]
    out = []
    for polygon in polygons:
        if polygon.geom_type != "Polygon" or polygon.is_empty:
            continue
        rings = [polygon.exterior, *polygon.interiors]
        out.append([[[round(x, COORD_DECIMALS), round(y, COORD_DECIMALS)] for x, y in ring.coords] for ring in rings])
    return out


def _outline(geometry: BaseGeometry) -> BaseGeometry:
    clipped = shapely.clip_by_rect(geometry, *FRAME)
    return shapely.simplify(clipped, OUTLINE_TOLERANCE_DEG, preserve_topology=True)


def _label(geometry: BaseGeometry) -> list[float]:
    """Where a state's code is written: its largest piece's centroid, or a
    point surely inside it when the centroid falls outside (a crescent)."""
    pieces = list(geometry.geoms) if hasattr(geometry, "geoms") else [geometry]
    largest = max(pieces, key=lambda piece: piece.area)
    point = largest.centroid if largest.contains(largest.centroid) else largest.representative_point()
    return [round(point.x, 2), round(point.y, 2)]


def outlines(us_topology: dict, world_topology: dict) -> dict:
    """The states inside FRAME (trail states flagged), the borders between
    them, and Canada."""
    frame = box(*FRAME)
    arcs = topojson.decode_arcs(us_topology)
    members = [f for f in topojson.features(us_topology, "states", arcs) if f.geometry.intersects(frame)]
    states = []
    for member in members:
        drawn = _outline(member.geometry)
        if drawn.is_empty:
            continue
        code = TRAIL_STATE_CODES.get(member.id or "")
        states.append(
            {
                "id": member.id,
                "name": member.properties.get("name"),
                "code": code,
                "trail": code is not None,
                "label": _label(drawn),
                "polygons": _rings(drawn),
            }
        )
    borders = []
    for line in topojson.shared_arcs(members, arcs):
        drawn = shapely.simplify(shapely.clip_by_rect(shapely.LineString(line), *FRAME), OUTLINE_TOLERANCE_DEG)
        for part in getattr(drawn, "geoms", [drawn]):
            if part.geom_type == "LineString" and not part.is_empty and len(part.coords) >= 2:
                borders.append([[round(x, COORD_DECIMALS), round(y, COORD_DECIMALS)] for x, y in part.coords])
    canada = [f for f in topojson.features(world_topology, "countries") if (f.properties.get("name") == "Canada")]
    return {
        "states": states,
        "borders": borders,
        "canada": _rings(_outline(canada[0].geometry)) if canada else [],
    }


# --- provenance --------------------------------------------------------------


def credits(registry: dict) -> list[dict]:
    """Who each layer belongs to, from each source's own registry row: its
    `attribution` where it states one, else its organization's name."""
    names = {org.get("provider"): org.get("name") for org in (registry.get("organizations") or {}).get("orgs", {}).values()}
    out = []
    for role, key in (("trail", CENTERLINE_KEY), ("states", US_ATLAS_KEY), ("canada", WORLD_ATLAS_KEY)):
        row = find_source(registry, key)
        if row is None:
            raise SystemExit(f"sources.json has no {key!r} row, so the map cannot say whose {role} it draws")
        out.append(
            {"layer": role, "source": key, "credit": row.get("attribution") or names.get(row["provider"]) or row["provider"]}
        )
    return out


# --- the file -----------------------------------------------------------------


def build_output(trails: dict, miles: dict, us_topology: dict, world_topology: dict, registry: dict) -> dict:
    chains = load_chains(trails, miles)
    runs = stitch_runs(chains)
    drawn = outlines(us_topology, world_topology)
    trail_states = {
        code: shapely.make_valid(feature.geometry)
        for feature in topojson.features(us_topology, "states")
        if (code := TRAIL_STATE_CODES.get(feature.id or "")) is not None
    }
    return {
        "format": FORMAT,
        "frame": list(FRAME),
        "trail": [thin_run(xy, m) for xy, m in runs],
        "state_runs": state_runs(chains, trail_states),
        **drawn,
        "credits": credits(registry),
        "notices": [ISC_NOTICE],
    }


def _forget_manifest(why: str) -> None:
    print(f"::warning::challenge_map.json not written - {why}.")
    MANIFEST_PATH.unlink(missing_ok=True)


def main() -> dict | None:
    missing = [path for path in (TRAILS_PATH, TRAIL_MILES_PATH) if not path.exists()]
    missing += [path for path, _ in ATLAS_FILES.values() if not path.exists()]
    if missing:
        _forget_manifest(
            f"missing {', '.join(path.name for path in missing)} (run export_trails.py and fetch_atlas_outlines.py first)"
        )
        return None
    output = build_output(
        json.loads(TRAILS_PATH.read_text()),
        json.loads(TRAIL_MILES_PATH.read_text()).get("miles") or {},
        json.loads(ATLAS_FILES[US_ATLAS_KEY][0].read_text()),
        json.loads(ATLAS_FILES[WORLD_ATLAS_KEY][0].read_text()),
        load_registry(SOURCES_PATH),
    )
    if not output["trail"]:
        _forget_manifest(f"{TRAILS_PATH.name} has no centerline chain with miles")
        return None
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(output, separators=(",", ":"), ensure_ascii=False))
    digest = hashlib.sha256(OUT_PATH.read_bytes()).hexdigest()
    MANIFEST_PATH.write_text(json.dumps({"path": to_manifest_path(OUT_PATH), "sha256": digest}, indent=2) + "\n")
    points = sum(len(run["coordinates"]) for run in output["trail"])
    print(
        f"challenge_map.json: {points:,} trail points in {len(output['trail'])} runs, {len(output['states'])} states, "
        f"{len(output['state_runs'])} state runs, {OUT_PATH.stat().st_size:,} bytes"
    )
    return output


if __name__ == "__main__":
    main()
