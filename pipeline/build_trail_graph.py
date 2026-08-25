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

ROOT = Path(__file__).resolve().parent
IN_DIR = ROOT / "data" / "processed"
OUT_DIR = ROOT / "data" / "processed"
INPUT_NAME = "nearby_trails.geojson"
ARTIFACT_NAME = "trail_graph.json"

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

        raw_edges.append(
            {
                "from": ends[0],
                "to": ends[1],
                "length_m": round(line.length, 2),
                "trail_id": properties.get("id"),
                "source": properties.get("source"),
                "name": properties.get("name"),
                "blaze_color": properties.get("blaze_color"),
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


def build(collection: dict, endpoint_snap_m: float = ENDPOINT_SNAP_M) -> tuple[dict, dict]:
    """The whole pipeline, from FeatureCollection to graph plus stats."""
    to_projected, to_geographic = _transformers()

    lines, refused = routable_lines(collection)
    for entry in lines:
        entry["line"] = transform(to_projected.transform, entry["line"])

    pieces, node_stats, welds = node_lines(lines, endpoint_snap_m)
    graph = build_graph(pieces, welds, to_geographic)

    stats = {
        "lines_in": len(collection.get("features", [])),
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


def sweep(collection: dict, tolerances=SWEEP_TOLERANCES_M) -> list[dict]:
    """What ENDPOINT_SNAP_M should be, measured rather than argued.

    Reports each candidate's endpoint joins and component count. The value to
    take is the knee: past it, components stop falling while joins keep rising,
    which is the signature of welding together ends that do not meet.
    """
    rows = []
    for tolerance in tolerances:
        _, stats = build(collection, endpoint_snap_m=tolerance)
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


def write_artifact(graph: dict, stats: dict) -> dict:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / ARTIFACT_NAME
    path.write_text(json.dumps(graph, separators=(",", ":")), encoding="utf-8")
    return {"path": str(path), "bytes": path.stat().st_size, **stats}


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

    if arguments.sweep:
        print(f"{'snap_m':>8}  {'joins':>7}  {'nodes':>7}  {'edges':>7}  {'junctions':>10}  {'components':>11}")
        for row in sweep(collection):
            print(
                f"{row['endpoint_snap_m']:>8.1f}  {row['endpoint_joins']:>7}  {row['nodes']:>7}  "
                f"{row['edges']:>7}  {row['junctions']:>10}  {row['components']:>11}"
            )
        print("\nTake the knee: where components stop falling and joins keep climbing.")
        return {}

    graph, stats = build(collection, endpoint_snap_m=arguments.snap_m)
    manifest = write_artifact(graph, stats)

    print(f"  lines in:        {stats['lines_in']}")
    print(f"  routable:        {stats['lines_routable']} (refused: {stats['refused']})")
    print(f"  nodes:           {stats['nodes']}")
    print(f"  edges:           {stats['edges']}")
    print(f"  junctions (>=3): {stats['junctions']}")
    print(f"  components:      {stats['components']}")
    print(f"  artifact:        {manifest['bytes']} bytes at {manifest['path']}")
    print(
        "\n#757 established that ~3,000 edges routes acceptably on a phone. "
        f"This graph has {stats['edges']}; if that is well past 3,000 the client approach needs revisiting "
        "before lib/trailGraph.ts is written, not after."
    )
    return manifest


if __name__ == "__main__":
    main()
