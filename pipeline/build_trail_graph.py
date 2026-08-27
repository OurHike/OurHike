"""Turn the network's trail lines into a junction graph the phone can route on
(#974, features/HIKE_PLANNING.md "The day hike on a network").

export_nearby_trails.py publishes the LINES other organizations maintain.
Nothing publishes their TOPOLOGY, and topology is the whole of what a day-hike
builder needs: #928's "tap a trail to walk it, tap again further along to turn"
is a shortest path between two points on a graph nobody has built.

This module builds it. Input is that module's own artifact, so the two cannot
disagree about which lines exist; output is nodes and edges, one JSON file.

WHAT IS AN EDGE, AND WHAT IS DELIBERATELY NOT

An edge is a piece of a maintained trail line between two junctions. Every edge
carries the parent line's `id`, `source`, `name` and `blaze_color`, because the
client reads all four off it: frame `1j` tallies legs per organization WHILE
the hiker builds ("NYNJTC - 2 legs, ATC - 1 leg"), and frame `1l`'s turn list
is spoken in trail names and blazes ("Right onto Seven Hills (blue)").
Re-deriving attribution at the end from geometry would be a second source of
truth for something the edge already knows.

Three things are not edges:

  CLOSED TRAILS. `trail_status == "closed"` is what lib/closureStyle.ts already
  draws the barred band from - 125 statewide long-term closures plus the
  polygon-derived ones (#964). A router that happily paths down a trail NYS
  OPRHP marks closed is FEATURES.md's confidently-wrong answer, arriving on the
  one screen a hiker uses to decide where to walk. They stay drawn and are
  never routable.

  ROADS AND CONNECTORS. #931 is a LATER row on the wireframe, not an omission.
  Only lines an organization maintains become edges, which is what makes
  frame `1j`'s refusal honest: "OurHike only builds routes on trails an
  organization maintains."

  ANYTHING PROPOSED OR UNKNOWN. Those never reach the input artifact at all
  (NEARBY_TRAILS.md section 3), so this module inherits the omission for free
  and should not re-implement it.

THE TWO WAYS TWO TRAILS MEET, AND WHY THEY ARE HANDLED SEPARATELY

This is the design decision in this file, and it exists because a single
blanket "snap anything within N metres" tolerance is unsafe on this ground.
The #771 spike measured why: through Harriman-Bear Mountain, 48% of sampled
A.T. points sit within 150 m of a DIFFERENT marked trail (NEARBY_TRAILS.md).
A blanket tolerance loose enough to be useful would weld parallel trails to
each other along half that corridor, inventing junctions that are not there.

So the two cases are split:

  1. LINES THAT ACTUALLY CROSS OR TOUCH are noded exactly, with no tolerance
     at all. Both lines are split at the intersection and share a node. This is
     every junction inside a single source's own layer, where the publisher
     already snapped their geometry together, and it is the large majority.

  2. A LINE'S ENDPOINT that stops just short of another line is joined, within
     ENDPOINT_SNAP_M. This is the cross-source case: NYNJTC's trail and OPRHP's
     trail are different surveys of ground that meets, and their geometries
     miss each other by a few metres. build_water_distance.py measured the
     comparable figure for point data - "the median offset from an ATC shelter
     to its nearest CSI shelter row is 21 m" - so the offset is real and is not
     zero.

WHAT A JOIN DOES TO THE GEOMETRY, WHICH IS NOTHING A HIKER SEES

A join unifies the two ends into one graph NODE. It does not edit anybody's
published line. The map still draws nearby_trails.geojson exactly as each
steward published it - this module never writes back to it - so the 5 m
disagreement between two surveys stays visible on the map and is resolved only
in the routing graph, where it has to be resolved for a path to exist at all.

Restricting the tolerance to ENDPOINTS is what makes it safe. A parallel trail
running 30 m away for two miles has no endpoint in that corridor, so no
tolerance short of absurd can weld it on. Only a line that STOPS near another
line gets joined, which is the shape of a real trail junction and not the shape
of two trails running alongside each other.

WHICH WAY THIS ROUNDS, AND WHY

Toward disconnection. A tolerance too small loses a real junction and the
router says it cannot find a way - an honest refusal a hiker can act on. A
tolerance too large invents a junction, and the router hands somebody a route
across ground with no trail on it. Those failures are not symmetrical and the
default reflects it.

ENDPOINT_SNAP_M IS @unvalidated AND THIS SCRIPT IS THE INSTRUMENT THAT WOULD
SETTLE IT. Run `--sweep` against real fetched layers: it reports, per candidate
tolerance, how many endpoint joins are made and how many connected components
the graph falls into. The right value is the knee - where components stop
collapsing and joins keep climbing, which is where it has started welding
things that do not meet. Nobody has run it against real data yet, so the
default below is a starting point and not a finding.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

from pyproj import Transformer
from shapely.geometry import LineString, MultiLineString, Point, shape
from shapely.ops import substring, transform
from shapely.strtree import STRtree

from lib.hashing import sha256_file

ROOT = Path(__file__).resolve().parent
IN_DIR = ROOT / "data" / "processed"
OUT_DIR = ROOT / "data" / "processed"
INPUT_NAME = "nearby_trails.geojson"
# The A.T.'s own lines (export_trails.py), which join the graph clipped to the
# ring - see load_at_lines for why they are CUT where the network artifact's
# lines never are.
TRAILS_NAME = "trails.geojson"
NEARBY_MANIFEST_NAME = "nearby_trails_manifest.json"
ARTIFACT_NAME = "trail_graph.json"
GEOMETRY_NAME = "trail_graph_geometry.json"
MANIFEST_NAME = "trail_graph_manifest.json"

# Which of trails.geojson's sources become graph edges. The centerline and the
# blue-blazed side trails are both maintained, walkable ground; road approaches
# and anything else stay out for #931's reasons.
AT_GRAPH_SOURCES = ("centerline", "side_trails")

# EPSG:5070 (NAD83 / Conus Albers) is equal-area and in metres, and is already
# this pipeline's projected CRS for length work - export_elevation.py measures
# the whole A.T. profile in it. Using the same one means a metre here and a
# metre there are the same metre, which HIKE_PLANNING.md Finding 1 exists
# because this codebase has got wrong before.
GEOGRAPHIC_CRS = "EPSG:4326"
PROJECTED_CRS = "EPSG:5070"

# @unvalidated - see the header. A trail line whose END lies within this many
# metres of another line is joined to it. Applies to endpoints only, never to
# a line's interior. Nobody has measured the right value; `--sweep` is how it
# gets measured, against real fetched layers.
#
# 8 m is chosen to be smaller than build_water_distance.py's measured 21 m
# median cross-source offset for POINTS, on the reasoning that a trail END is
# surveyed more carefully than a shelter's pin and that under-connecting fails
# safe. It is a starting point for the sweep, not a finding.
ENDPOINT_SNAP_M = 8.0

# The grid coincident endpoints are quantised onto before they become one node.
# Two vertices closer together than this are the same place; this is geometric
# housekeeping for float noise, not the junction tolerance above.
NODE_QUANT_M = 0.5

# What `--sweep` tries. Spans "float noise only" to "well past anything
# defensible", so the knee is visible rather than assumed.
SWEEP_TOLERANCES_M = (0.0, 2.0, 5.0, 8.0, 12.0, 20.0, 35.0, 60.0, 100.0)

CLOSED_STATUS = "closed"


def _transformers() -> tuple[Transformer, Transformer]:
    """to-projected and back. always_xy because every coordinate in this
    pipeline is (lon, lat) and pyproj's authority-order default would swap
    them - the same note compare_shards.py carries."""
    return (
        Transformer.from_crs(GEOGRAPHIC_CRS, PROJECTED_CRS, always_xy=True),
        Transformer.from_crs(PROJECTED_CRS, GEOGRAPHIC_CRS, always_xy=True),
    )


def load_at_lines(path: Path) -> dict | None:
    """trails.geojson's A.T. lines - centerline and side trails, WHOLE.

    WITHOUT THIS THE GRAPH TELLS A HIKER A FALSE SENTENCE. export_nearby_trails
    deliberately suppresses every other organization's copy of a route ATC owns
    (`suppressed_by_owner`), so the A.T. is absent from the network artifact BY
    DESIGN - and a graph built from that artifact alone would refuse a tap on
    the widest line on the map with "that tap isn't on a marked hiking route",
    which in that one case is untrue. Frame `1l`'s own worked example walks an
    A.T. leg ("Appalachian Trail - 0.9 mi - ATC").

    NOT CLIPPED TO THE RING - the maintainer's call, 2026-08-25: the graph
    holds all trails from the three organizations this app ships, the whole
    A.T. included. Which geographies a phone downloads is a future, hiker-made
    choice (the same decision space as OFFLINE_COVERAGE's unit question), not a
    build-time cut. The routing artifact stays small because geometry ships
    separately - see write_artifact.

    None when the file is absent, which main() reports loudly: a graph without
    the A.T. still routes the other trails, but every refusal on the A.T. is
    the false sentence above, so absence has to be visible in the stats rather
    than discovered on a phone.
    """
    if not path.exists():
        return None
    return at_lines_of(json.loads(path.read_text(encoding="utf-8")))


def at_lines_of(collection: dict) -> dict:
    """The A.T. features that may route, separated so a test can hand it a
    collection."""
    kept = []
    for feature in collection.get("features", []):
        properties = feature.get("properties") or {}
        if properties.get("source") not in AT_GRAPH_SOURCES:
            continue
        geometry_json = feature.get("geometry")
        if not geometry_json:
            continue
        kept.append({"type": "Feature", "properties": properties, "geometry": geometry_json})
    return {"type": "FeatureCollection", "features": kept}


def routable_lines(collection: dict) -> tuple[list[dict], dict]:
    """The features that may carry a route, and a count of what was refused.

    Refusals are counted rather than silently dropped, because "the graph has
    fewer edges than the map has lines" is a thing a reviewer should be able to
    account for exactly.
    """
    kept: list[dict] = []
    refused = {"closed": 0, "not_a_line": 0, "empty": 0}

    for feature in collection.get("features", []):
        properties = feature.get("properties") or {}
        if (properties.get("trail_status") or "").strip().lower() == CLOSED_STATUS:
            refused["closed"] += 1
            continue

        geometry_json = feature.get("geometry")
        if not geometry_json:
            refused["empty"] += 1
            continue

        geometry = shape(geometry_json)
        if geometry.is_empty:
            refused["empty"] += 1
            continue
        if not isinstance(geometry, (LineString, MultiLineString)):
            refused["not_a_line"] += 1
            continue

        parts = list(geometry.geoms) if isinstance(geometry, MultiLineString) else [geometry]
        for part in parts:
            if part.is_empty or len(part.coords) < 2:
                refused["empty"] += 1
                continue
            kept.append({"properties": properties, "line": part})

    return kept, refused


def _split_at(line: LineString, points: list[Point]) -> list[LineString]:
    """`line` cut at every point that genuinely lies on it.

    Cuts are made by DISTANCE ALONG THE LINE rather than by handing shapely's
    `split` a Point. That is not a style preference: `split` requires the
    splitter to lie exactly on the line, and a point computed from an
    intersection is off it by float noise often enough that it silently returns
    the line uncut. This module got that wrong once and the graph came back
    with every crossing detected and nothing actually split.

    A cut at the very start or end makes a zero-length piece and no new
    junction - the endpoint is already a node - so those are dropped.
    """
    if not points:
        return [line]

    cuts = []
    for point in points:
        distance = line.project(point)
        if distance <= NODE_QUANT_M or distance >= line.length - NODE_QUANT_M:
            continue
        cuts.append(distance)

    if not cuts:
        return [line]

    bounds = [0.0] + sorted(cuts) + [line.length]
    pieces = []
    for start, end in zip(bounds, bounds[1:]):
        if end - start <= NODE_QUANT_M:
            continue
        piece = substring(line, start, end)
        if isinstance(piece, LineString) and piece.length > 0:
            pieces.append(piece)
    return pieces or [line]


def node_lines(lines: list[dict], endpoint_snap_m: float) -> tuple[list[dict], dict]:
    """Split every line where it meets another, and join ends that stop short.

    Returns the split pieces (each still carrying its parent's properties), a
    stats dict naming how much of each mechanism fired, and the endpoint pairs
    that must end up sharing a node.
    """
    geometries = [entry["line"] for entry in lines]
    tree = STRtree(geometries)

    cut_points: list[list[Point]] = [[] for _ in lines]
    welds: list[tuple[tuple[float, float], tuple[float, float]]] = []
    stats = {"crossings": 0, "endpoint_joins": 0}

    for index, line in enumerate(geometries):
        for other_index in tree.query(line):
            other_index = int(other_index)
            if other_index <= index:
                continue
            other = geometries[other_index]

            # 1. Exact crossings and touches - no tolerance.
            if line.intersects(other):
                intersection = line.intersection(other)
                points = _intersection_points(intersection)
                if points:
                    stats["crossings"] += len(points)
                    cut_points[index].extend(points)
                    cut_points[other_index].extend(points)
                continue

            # 2. An endpoint stopping just short of the other line.
            if endpoint_snap_m <= 0:
                continue
            for end_index, other_line_index in ((index, other_index), (other_index, index)):
                end_line = geometries[end_index]
                target = geometries[other_line_index]
                for coordinate in (end_line.coords[0], end_line.coords[-1]):
                    endpoint = Point(coordinate)
                    if endpoint.distance(target) <= endpoint_snap_m:
                        stats["endpoint_joins"] += 1
                        # Cut the TARGET where the endpoint comes closest, then
                        # record the pair so the two become one node below.
                        # Quantisation alone cannot do this: the whole point of
                        # the tolerance is that the two coordinates are metres
                        # apart, which is far outside the node grid.
                        landing = target.interpolate(target.project(endpoint))
                        cut_points[other_line_index].append(landing)
                        welds.append(((endpoint.x, endpoint.y), (landing.x, landing.y)))

    pieces: list[dict] = []
    for index, entry in enumerate(lines):
        for piece in _split_at(entry["line"], cut_points[index]):
            pieces.append({"properties": entry["properties"], "line": piece})

    return pieces, stats, welds


def _intersection_points(geometry) -> list[Point]:
    """Every discrete point where two lines meet.

    A shared SEGMENT (two layers publishing the same stretch of ground) yields
    a LineString rather than a point; its two ends are the junctions, and the
    overlap itself is not one.
    """
    if geometry.is_empty:
        return []
    kind = geometry.geom_type
    if kind == "Point":
        return [geometry]
    if kind == "MultiPoint":
        return list(geometry.geoms)
    if kind in ("LineString", "MultiLineString"):
        points = []
        parts = list(geometry.geoms) if kind == "MultiLineString" else [geometry]
        for part in parts:
            if part.is_empty:
                continue
            points.append(Point(part.coords[0]))
            points.append(Point(part.coords[-1]))
        return points
    if kind == "GeometryCollection":
        points = []
        for part in geometry.geoms:
            points.extend(_intersection_points(part))
        return points
    return []


def _node_id(x: float, y: float, quant_m: float, buckets: dict, points: list) -> int:
    """The node at this coordinate, creating it if this is the first line to
    reach it.

    Coordinates are bucketed on a grid and then checked against the real
    distance, rather than trusted to a rounded key alone. Two vertices that are
    the same place but land either side of a grid boundary would otherwise
    become two nodes and quietly break the graph at exactly the junctions that
    matter - which is the failure that is hardest to see in an artifact and
    most expensive on a trail.
    """
    cell_x = int(math.floor(x / quant_m))
    cell_y = int(math.floor(y / quant_m))
    for delta_x in (-1, 0, 1):
        for delta_y in (-1, 0, 1):
            for node_id in buckets.get((cell_x + delta_x, cell_y + delta_y), ()):
                near_x, near_y = points[node_id]
                if (near_x - x) ** 2 + (near_y - y) ** 2 <= quant_m * quant_m:
                    return node_id
    node_id = len(points)
    points.append((x, y))
    buckets.setdefault((cell_x, cell_y), []).append(node_id)
    return node_id


def build_graph(
    pieces: list[dict],
    welds: list[tuple[tuple[float, float], tuple[float, float]]],
    to_geographic: Transformer,
    quant_m: float = NODE_QUANT_M,
) -> dict:
    """Nodes and edges, in the shape the client loads."""
    buckets: dict[tuple[int, int], list[int]] = {}
    node_points: list[tuple[float, float]] = []
    raw_edges: list[dict] = []

    for piece in pieces:
        line = piece["line"]
        properties = piece["properties"]
        ends = [
            _node_id(coordinate[0], coordinate[1], quant_m, buckets, node_points)
            for coordinate in (line.coords[0], line.coords[-1])
        ]

        # A piece whose ends land on one node is a loop shorter than the grid -
        # float noise, not a walkable circuit.
        if ends[0] == ends[1] and line.length <= quant_m:
            continue

        # The piece's own vertices, back in WGS84 - the client draws the
        # highlight from these and projects taps onto them. Without them an
        # edge is a straight chord between its junctions, and a chord across a
        # switchback is a picture of a trail that does not exist.
        edge_geometry = [[round(lon, 6), round(lat, 6)] for lon, lat in (to_geographic.transform(x, y) for x, y in line.coords)]
        raw_edges.append(
            {
                "from": ends[0],
                "to": ends[1],
                "length_m": round(line.length, 2),
                "trail_id": properties.get("id"),
                "source": properties.get("source"),
                "name": properties.get("name"),
                "blaze_color": properties.get("blaze_color"),
                "geometry": edge_geometry,
            }
        )

    parent = list(range(len(node_points)))

    def find(node_id: int) -> int:
        while parent[node_id] != node_id:
            parent[node_id] = parent[parent[node_id]]
            node_id = parent[node_id]
        return node_id

    # The welds. Each pair is two coordinates the endpoint tolerance decided are
    # one place; both already exist as nodes, so this only merges identity.
    for left, right in welds:
        left_id = _node_id(left[0], left[1], quant_m, buckets, node_points)
        right_id = _node_id(right[0], right[1], quant_m, buckets, node_points)
        while len(parent) < len(node_points):
            parent.append(len(parent))
        left_root, right_root = find(left_id), find(right_id)
        if left_root != right_root:
            # Keep the lower id so output ordering stays stable across runs.
            parent[max(left_root, right_root)] = min(left_root, right_root)

    while len(parent) < len(node_points):
        parent.append(len(parent))

    # Compact: only nodes an edge actually touches reach the artifact.
    renumbered: dict[int, int] = {}
    nodes: list[list[float]] = []
    edges: list[dict] = []
    for edge in raw_edges:
        ends = []
        for side in ("from", "to"):
            root = find(edge[side])
            if root not in renumbered:
                renumbered[root] = len(nodes)
                x, y = node_points[root]
                lon, lat = to_geographic.transform(x, y)
                nodes.append([round(lon, 6), round(lat, 6)])
            ends.append(renumbered[root])
        if ends[0] == ends[1] and edge["length_m"] <= quant_m:
            continue
        edges.append({**edge, "from": ends[0], "to": ends[1]})

    return {"nodes": nodes, "edges": edges}


def connected_components(graph: dict) -> int:
    """How many disconnected islands the graph falls into.

    The number `--sweep` is really about: a graph in many pieces is one where
    junctions the ground has are missing from the data, and a hiker's route
    across one of them will be refused.
    """
    adjacency: dict[int, list[int]] = defaultdict(list)
    for edge in graph["edges"]:
        adjacency[edge["from"]].append(edge["to"])
        adjacency[edge["to"]].append(edge["from"])

    seen: set[int] = set()
    components = 0
    for start in range(len(graph["nodes"])):
        if start in seen:
            continue
        components += 1
        stack = [start]
        seen.add(start)
        while stack:
            current = stack.pop()
            for neighbour in adjacency[current]:
                if neighbour not in seen:
                    seen.add(neighbour)
                    stack.append(neighbour)
    return components


def junction_count(graph: dict) -> int:
    """Nodes where three or more edge-ends meet - junctions in the sense a
    hiker means, as opposed to the nodes that merely end a line."""
    degree: dict[int, int] = defaultdict(int)
    for edge in graph["edges"]:
        degree[edge["from"]] += 1
        degree[edge["to"]] += 1
    return sum(1 for count in degree.values() if count >= 3)


def load_input(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(
            f"{path} is missing - run export_nearby_trails.py first. "
            "This module's subject is that artifact's topology, so it has nothing to build without it."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def build(
    collection: dict,
    at_collection: dict | None = None,
    endpoint_snap_m: float = ENDPOINT_SNAP_M,
) -> tuple[dict, dict]:
    """The whole pipeline, from FeatureCollection(s) to graph plus stats."""
    to_projected, to_geographic = _transformers()

    merged = dict(collection)
    at_count = 0
    if at_collection is not None:
        at_features = at_collection.get("features", [])
        at_count = len(at_features)
        merged = {
            "type": "FeatureCollection",
            "features": [*collection.get("features", []), *at_features],
        }

    lines, refused = routable_lines(merged)
    for entry in lines:
        entry["line"] = transform(to_projected.transform, entry["line"])

    pieces, node_stats, welds = node_lines(lines, endpoint_snap_m)
    graph = build_graph(pieces, welds, to_geographic)

    stats = {
        "lines_in": len(merged.get("features", [])),
        "at_lines": at_count,
        "at_included": at_collection is not None,
        "lines_routable": len(lines),
        "refused": refused,
        "endpoint_snap_m": endpoint_snap_m,
        "nodes": len(graph["nodes"]),
        "edges": len(graph["edges"]),
        "junctions": junction_count(graph),
        "components": connected_components(graph),
        **node_stats,
    }
    return graph, stats


def sweep(collection: dict, at_collection: dict | None = None, tolerances=SWEEP_TOLERANCES_M) -> list[dict]:
    """What ENDPOINT_SNAP_M should be, measured rather than argued.

    Reports each candidate's endpoint joins and component count. The value to
    take is the knee: past it, components stop falling while joins keep rising,
    which is the signature of welding together ends that do not meet.
    """
    rows = []
    for tolerance in tolerances:
        _, stats = build(collection, at_collection, endpoint_snap_m=tolerance)
        rows.append(
            {
                "endpoint_snap_m": tolerance,
                "endpoint_joins": stats["endpoint_joins"],
                "nodes": stats["nodes"],
                "edges": stats["edges"],
                "junctions": stats["junctions"],
                "components": stats["components"],
            }
        )
    return rows


def write_artifact(graph: dict, stats: dict, sources: dict | None = None) -> dict:
    """Write the routing artifact, the geometry artifact, and one manifest.

    TWO ARTIFACTS, SPLIT ON WHEN A PHONE NEEDS THEM - the maintainer's call,
    2026-08-25. The routing half (nodes, edges, lengths, attribution) is what
    PlanKindSheet needs at launch to say whether a day hike is even on offer;
    the geometry half (each edge's vertices, index-aligned with `edges`) is
    only needed once the builder opens, and with the whole A.T. in the graph it
    is by far the heavier half. Splitting keeps "can I plan a day hike" cheap
    on every launch that never opens the door.

    INDEX-ALIGNED, AND THE MANIFEST BINDS THE PAIR. trail_graph_geometry.json
    is one coordinate list per edge, in edge order. The alignment invariant is
    real and silent when broken - edge 40's highlight drawn from edge 41's
    vertices is a route on the wrong trail - so both files' hashes live in ONE
    manifest and the client refuses a geometry whose edge count disagrees.

    `sources` is copied from the nearby-trails manifest so THE LICENCE GATE
    TRAVELS WITH THE DERIVATION: this graph is those lines' topology, and
    publish.py must be able to hold both halves back on exactly the
    `reaches_hikers` check it applies to the lines themselves.
    """
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    geometry = [edge.pop("geometry") for edge in graph["edges"]]
    path = OUT_DIR / ARTIFACT_NAME
    path.write_text(json.dumps(graph, separators=(",", ":")), encoding="utf-8")
    geometry_path = OUT_DIR / GEOMETRY_NAME
    geometry_path.write_text(json.dumps(geometry, separators=(",", ":")), encoding="utf-8")

    manifest = {
        "path": str(path),
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
        "geometry_path": str(geometry_path),
        "geometry_sha256": sha256_file(geometry_path),
        "geometry_bytes": geometry_path.stat().st_size,
        "sources": sources or {},
        **stats,
    }
    (OUT_DIR / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main() -> dict:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--snap-m",
        type=float,
        default=ENDPOINT_SNAP_M,
        help=f"endpoint join tolerance in metres (default {ENDPOINT_SNAP_M}, @unvalidated)",
    )
    parser.add_argument(
        "--sweep",
        action="store_true",
        help="report joins and components across candidate tolerances instead of writing an artifact",
    )
    arguments = parser.parse_args()

    collection = load_input(IN_DIR / INPUT_NAME)
    at_collection = load_at_lines(IN_DIR / TRAILS_NAME)
    if at_collection is None:
        # Loud, because a graph without the A.T. refuses taps on the widest
        # line on the map with a sentence that is false in that one case.
        print(f"WARNING: {TRAILS_NAME} not found - the A.T. is NOT in this graph.")

    if arguments.sweep:
        print(f"{'snap_m':>8}  {'joins':>7}  {'nodes':>7}  {'edges':>7}  {'junctions':>10}  {'components':>11}")
        for row in sweep(collection, at_collection):
            print(
                f"{row['endpoint_snap_m']:>8.1f}  {row['endpoint_joins']:>7}  {row['nodes']:>7}  "
                f"{row['edges']:>7}  {row['junctions']:>10}  {row['components']:>11}"
            )
        print("\nTake the knee: where components stop falling and joins keep climbing.")
        return {}

    graph, stats = build(collection, at_collection, endpoint_snap_m=arguments.snap_m)

    # The licence gate travels with the derivation - see write_artifact.
    nearby_manifest_path = IN_DIR / NEARBY_MANIFEST_NAME
    sources = {}
    if nearby_manifest_path.exists():
        sources = json.loads(nearby_manifest_path.read_text(encoding="utf-8")).get("sources", {})
    manifest = write_artifact(graph, stats, sources)

    print(f"  lines in:        {stats['lines_in']} (A.T.: {stats['at_lines']})")
    print(f"  routable:        {stats['lines_routable']} (refused: {stats['refused']})")
    print(f"  nodes:           {stats['nodes']}")
    print(f"  edges:           {stats['edges']}")
    print(f"  junctions (>=3): {stats['junctions']}")
    print(f"  components:      {stats['components']}")
    print(f"  artifact:        {manifest['bytes']} bytes at {manifest['path']}")
    print(f"  geometry:        {manifest['geometry_bytes']} bytes at {manifest['geometry_path']}")
    # #757 put the phone's budget at ~3,000 edges and this warning used to
    # fire above it, pointing at lib/trailGraph.ts's plain-scan shortestPath.
    # #1020 acted on that and found the scan was the smaller half: the search
    # is now a binary heap, and the tap that precedes it reads a spatial grid
    # instead of every edge. Measured against this artifact at 40,596 edges
    # (2026-08-27), one tap went from 85.5 ms to 0.021 ms and one Harriman-
    # sized route from 0.057 ms to 0.041 ms.
    #
    # So the number below is no longer a warning about the search. What it is
    # still worth watching is the DOWNLOAD and the parse - the client fetches
    # every edge in the state, and pipeline-side cuts per coverage unit are
    # #552's to decide.
    print(
        f"\n{stats['edges']} edges. The client indexes these spatially (#1020), so the cost "
        "that scales here is the artifact's size on a phone, not the search over it."
    )
    return manifest


if __name__ == "__main__":
    main()
