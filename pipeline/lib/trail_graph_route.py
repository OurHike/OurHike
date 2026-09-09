"""A Python twin of the phone's router over the junction graph, so a route
the pipeline measures is the route the phone will redo (#1290).

WHY A TWIN, AND WHY IT IS NOT A SECOND OPINION

`client/src/lib/trailGraph.ts` is where a day hike is routed: shortest path
over `trail_graph.json`'s edges by `length_m`, between points that carry an
edge and a fraction along it, with the partial first and last edges priced
by the fraction actually walked, the climb summed per edge and refused whole
when any edge was never measured, and the drawn line cut to the tapped
fractions. A published route (features/SUGGESTED_HIKES.md) stores ENDS and
nothing else - the phone re-routes between them when the card opens - so the
miles and climb the artifact prints beside a route are a claim about what the
phone will compute. This module is that arithmetic in Python, function for
function, so the pipeline can make the claim from the same rules rather than
from a guess.

WHAT IS TWINNED, and the file/line it is twinned from, so a change on one
side is findable from the other:

    nearest_point       nearestPointOnGraph / projectOntoEdge
    route_between       routeBetween / shortestPath / walkBack
    route_through       routeThrough (sections concatenated, legs merged)
    close_the_loop      closeTheLoop
    walked_metres       walkedMetresPerEdge
    entered_nodes       enteredNodes
    route_climb         routeClimb (pro-rated partial edges, direction swap)
    route_lines         routeLines / routeGeometry / cutPolyline
    same_trail          sameTrail (trail_id AND name)

WHAT IS DELIBERATELY NOT TWINNED, said so the difference is known rather
than discovered: `holdDesignation`, the client's swap of an edge for its
same-tread twin from another organization (#1115). It changes which
organization a leg WEARS and can move the total by the tracing noise between
two surveys of one path (`SAME_TREAD_MAX_LENGTH_DELTA_RATIO`, 5%); it does
not change where the walk goes. The miles this module reports can therefore
differ from the phone's by that noise on a leg two stewards both draw, and
`SAME_TREAD_NOTE` is carried on every measurement so the artifact can say
so rather than print the figure as exact.

THE CLIMB IS REFUSED WHEN THE SIDECAR DOES NOT FIT THE GRAPH. The per-edge
climb (`trail_graph_elevation.json`) is index-aligned with the edges by
construction (export_network_elevation.py), and a sidecar of a different
length is one built against a different graph: pairing them by index would
attribute edge 40's climb to whatever edge 40 is now. Measured on the
production bucket 2026-09-09 - 42,103 rows against 466,966 edges - so this
is not hypothetical. `load_graph` prices nothing from such a sidecar and
says why in `climb_note`; absent means unknown, never zero.

Pure module - no network. Loads three JSON files a caller names.
"""

from __future__ import annotations

import heapq
import json
import math
from dataclasses import dataclass, field
from pathlib import Path

METRES_PER_MILE = 1609.344
FEET_PER_METRE = 3.280839895
#: trailGraph.ts's `EARTH_RADIUS_M` - WGS84 equatorial, not the mean sphere
#: lib/nynjtc_long_path_guide.py uses. The phone's number, because the point
#: of this module is to reproduce the phone's arithmetic.
EARTH_RADIUS_M = 6_378_137

#: trailGraph.ts's `MAX_OFF_NETWORK_FEET` in metres: how far off a line a
#: stored end may sit and still resolve on the phone. A published end is
#: snapped ONTO the line here, so a hiker's phone finds it at zero offset -
#: but the check is kept at the phone's own radius so an end this module
#: would accept is one the phone would too.
MAX_OFF_NETWORK_M = 150 / FEET_PER_METRE

SAME_TREAD_NOTE = (
    "measured on the pipeline's copy of the trail lines without the phone's same-tread swap "
    "(trailGraph.ts holdDesignation), so a leg two organizations both draw can differ by up to 5% of its length"
)


@dataclass
class GraphPoint:
    """A place on the network: an edge and how far along it (trailGraph.ts's
    GraphPoint). `at` is the point pulled onto the line, `(lon, lat)`."""

    edge_index: int
    fraction: float
    at: tuple[float, float]
    off_metres: float


@dataclass
class Leg:
    name: str | None
    source: str | None
    blaze_color: str | None
    trail_id: str | None
    miles: float

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "source": self.source,
            "blaze_color": self.blaze_color,
            "trail_id": self.trail_id,
            "miles": self.miles,
        }


@dataclass
class Section:
    """One tap-to-tap piece of a walk, as walked (trailGraph.ts's RouteSection
    plus the per-edge pricing the client keeps beside it)."""

    edge_indices: list[int]
    start: GraphPoint
    end: GraphPoint
    walked_metres: list[float]
    entered: list[int]


@dataclass
class Route:
    sections: list[Section]
    legs: list[Leg]
    miles: float
    edge_indices: list[int]
    climb: tuple[float, float] | None
    climb_note: str | None = None

    @property
    def metres(self) -> float:
        return self.miles * METRES_PER_MILE


@dataclass
class Graph:
    nodes: list
    edges: list
    geometry: list | None = None
    climb: list | None = None
    climb_note: str | None = None
    adjacency: dict = field(default_factory=dict)
    _grid: dict = field(default_factory=dict)
    _cell_deg: float = 0.01

    def vertices(self, edge_index: int) -> list:
        """The edge's own polyline, or the chord between its nodes when no
        geometry was loaded - projectOntoEdge's fallback."""
        if self.geometry is not None and self.geometry[edge_index]:
            return self.geometry[edge_index]
        edge = self.edges[edge_index]
        return [self.nodes[edge["from"]], self.nodes[edge["to"]]]

    def has_geometry(self, edge_index: int) -> bool:
        return self.geometry is not None and len(self.geometry[edge_index] or []) >= 2


def local_metres(a: tuple[float, float], b: tuple[float, float]) -> tuple[float, float]:
    """trailGraph.ts's localMetres: an equirectangular offset from a to b."""
    mean_lat = ((a[1] + b[1]) / 2) * (math.pi / 180)
    return (
        (b[0] - a[0]) * (math.pi / 180) * EARTH_RADIUS_M * math.cos(mean_lat),
        (b[1] - a[1]) * (math.pi / 180) * EARTH_RADIUS_M,
    )


def metres_between(a: tuple[float, float], b: tuple[float, float]) -> float:
    x, y = local_metres(a, b)
    return math.hypot(x, y)


def metres_to_miles(metres: float) -> float:
    return metres / METRES_PER_MILE


def same_trail(a, b) -> bool:
    """trailGraph.ts's sameTrail: BOTH the id and the name."""
    return a.get("trail_id") == b.get("trail_id") and a.get("name") == b.get("name")


def load_graph(
    graph_path: Path,
    geometry_path: Path | None = None,
    elevation_path: Path | None = None,
    keep_near: list[tuple[float, float]] | None = None,
    keep_radius_m: float = 20_000,
) -> Graph:
    """The graph, with its geometry and climb sidecars where given.

    `keep_near` keeps geometry only for edges with a node within
    `keep_radius_m` of any of the points - the whole geometry file is 224 MB
    of JSON and a route review needs the ground around twenty trailheads,
    not New Hampshire. The parse still reads the whole file; what this saves
    is what stays resident.

    A geometry sidecar of the wrong length is refused outright (the
    pipeline's own rule, export_network_elevation.py: "refusing to guess the
    pairing"). A climb sidecar of the wrong length is not refused but is
    not USED: see the module docstring.
    """
    document = json.loads(Path(graph_path).read_text(encoding="utf-8"))
    nodes, edges = document["nodes"], document["edges"]
    graph = Graph(nodes=nodes, edges=edges)

    for index, edge in enumerate(edges):
        graph.adjacency.setdefault(edge["from"], []).append((edge["to"], index))
        graph.adjacency.setdefault(edge["to"], []).append((edge["from"], index))

    keep: set[int] | None = None
    if keep_near is not None:
        keep = set()
        for index, edge in enumerate(edges):
            for node in (nodes[edge["from"]], nodes[edge["to"]]):
                if any(metres_between(tuple(node), point) <= keep_radius_m for point in keep_near):
                    keep.add(index)
                    break

    if geometry_path is not None and Path(geometry_path).exists():
        geometry = json.loads(Path(geometry_path).read_text(encoding="utf-8"))
        if len(geometry) != len(edges):
            raise ValueError(f"geometry has {len(geometry)} entries against {len(edges)} edges - refusing to guess the pairing")
        if keep is not None:
            geometry = [vertices if index in keep else None for index, vertices in enumerate(geometry)]
        graph.geometry = geometry

    if elevation_path is not None and Path(elevation_path).exists():
        climb = json.loads(Path(elevation_path).read_text(encoding="utf-8"))
        if len(climb) == len(edges):
            graph.climb = climb
        else:
            graph.climb_note = (
                f"trail_graph_elevation.json has {len(climb)} rows against {len(edges)} edges - a sidecar built "
                "against a different graph, so no climb is priced from it (absent means unknown, never zero)"
            )
    else:
        graph.climb_note = "no trail_graph_elevation.json beside the graph, so no climb is priced"

    _index_nodes(graph, keep)
    return graph


def _cell(graph: Graph, lon: float, lat: float) -> tuple[int, int]:
    return (int(math.floor(lon / graph._cell_deg)), int(math.floor(lat / graph._cell_deg)))


def _index_nodes(graph: Graph, keep: set[int] | None) -> None:
    """Edges by the grid cells their end nodes fall in, for nearest_point's
    candidate search. An edge is indexed under both its ends' cells and the
    cells between them, so a long edge is found from anywhere along it."""
    for index, edge in enumerate(graph.edges):
        if keep is not None and index not in keep:
            continue
        a, b = graph.nodes[edge["from"]], graph.nodes[edge["to"]]
        ca, cb = _cell(graph, a[0], a[1]), _cell(graph, b[0], b[1])
        for cx in range(min(ca[0], cb[0]), max(ca[0], cb[0]) + 1):
            for cy in range(min(ca[1], cb[1]), max(ca[1], cb[1]) + 1):
                graph._grid.setdefault((cx, cy), []).append(index)


def edges_near(graph: Graph, lon: float, lat: float, radius_m: float) -> list[int]:
    """Every indexed edge whose end-node cells fall within the radius."""
    reach = int(math.ceil(radius_m / (graph._cell_deg * 111_000))) + 1
    cx, cy = _cell(graph, lon, lat)
    found: set[int] = set()
    for dx in range(-reach, reach + 1):
        for dy in range(-reach, reach + 1):
            found.update(graph._grid.get((cx + dx, cy + dy), ()))
    return sorted(found)


def project_onto_edge(graph: Graph, edge_index: int, at: tuple[float, float]) -> tuple[float, float, tuple[float, float]]:
    """trailGraph.ts's projectOntoEdge: `(fraction, off_metres, point)`."""
    vertices = graph.vertices(edge_index)
    best = None
    walked = 0.0
    total = 0.0
    for step in range(len(vertices) - 1):
        start = (vertices[step][0], vertices[step][1])
        end = (vertices[step + 1][0], vertices[step + 1][1])
        span = local_metres(start, end)
        span_length = math.hypot(*span)
        offset = local_metres(start, at)
        along = 0.0
        if span_length > 0:
            along = (offset[0] * span[0] + offset[1] * span[1]) / (span_length * span_length)
            along = min(1.0, max(0.0, along))
        off = math.hypot(offset[0] - span[0] * along, offset[1] - span[1] * along)
        if best is None or off < best[0]:
            best = (
                off,
                (start[0] + (end[0] - start[0]) * along, start[1] + (end[1] - start[1]) * along),
                walked + span_length * along,
            )
        walked += span_length
        total += span_length
    if best is None or total == 0:
        node = graph.nodes[graph.edges[edge_index]["from"]]
        return 0.0, math.inf, (node[0], node[1])
    return best[2] / total, best[0], best[1]


def nearest_point(
    graph: Graph, lon: float, lat: float, max_off_m: float = MAX_OFF_NETWORK_M, search_m: float = 2_000
) -> GraphPoint | None:
    """The nearest place on the network to a coordinate, or None when
    nothing is within `max_off_m` - trailGraph.ts's nearestPointOnGraph."""
    best: GraphPoint | None = None
    for edge_index in edges_near(graph, lon, lat, search_m):
        fraction, off, point = project_onto_edge(graph, edge_index, (lon, lat))
        if best is not None and off >= best.off_metres:
            continue
        best = GraphPoint(edge_index=edge_index, fraction=fraction, at=point, off_metres=off)
    if best is None or best.off_metres > max_off_m:
        return None
    return best


def _shortest_path(graph: Graph, seeds: list[tuple[int, float]], targets: dict[int, float]):
    """trailGraph.ts's shortestPath: Dijkstra over `length_m` from several
    seeds to the cheapest target, each target carrying its own tail."""
    reached: dict[int, tuple[float, int, int]] = {}
    settled: set[int] = set()
    frontier: list[tuple[float, int]] = []
    for node, distance in seeds:
        known = reached.get(node)
        if known is None or distance < known[0]:
            reached[node] = (distance, -1, -1)
            heapq.heappush(frontier, (distance, node))
    best = None
    while frontier:
        distance, current = heapq.heappop(frontier)
        if current in settled:
            continue
        known = reached.get(current)
        if known is not None and known[0] < distance:
            continue
        settled.add(current)
        tail = targets.get(current)
        if tail is not None:
            total = distance + tail
            if best is None or total < best[1]:
                best = (current, total)
        if best is not None and distance >= best[1]:
            break
        for to, edge_index in graph.adjacency.get(current, ()):
            if to in settled:
                continue
            next_distance = distance + graph.edges[edge_index]["length_m"]
            known_to = reached.get(to)
            if known_to is not None and known_to[0] <= next_distance:
                continue
            reached[to] = (next_distance, edge_index, current)
            heapq.heappush(frontier, (next_distance, to))
    if best is None:
        return None
    return best[0], best[1], reached


def _walk_back(reached: dict, node: int) -> list[int]:
    edges = []
    current = node
    while True:
        _, via_edge, from_node = reached[current]
        if via_edge == -1:
            break
        edges.append(via_edge)
        current = from_node
    edges.reverse()
    return edges


def entered_nodes(
    graph: Graph, edge_indices: list[int], start: GraphPoint | None = None, end: GraphPoint | None = None
) -> list[int]:
    """trailGraph.ts's enteredNodes: which node each edge is entered FROM,
    chained by node id."""
    entered: list[int] = []
    if len(edge_indices) == 1:
        only = graph.edges[edge_indices[0]]
        forward = start is None or end is None or start.fraction <= end.fraction
        entered.append(only["from"] if forward else only["to"])
        return entered
    for step, edge_index in enumerate(edge_indices):
        edge = graph.edges[edge_index]
        if step == 0:
            nxt = graph.edges[edge_indices[1]]
            from_shared = edge["from"] in (nxt["from"], nxt["to"])
            entered.append(edge["to"] if from_shared else edge["from"])
        else:
            previous = graph.edges[edge_indices[step - 1]]
            came_from = edge["from"] if edge["from"] in (previous["from"], previous["to"]) else edge["to"]
            entered.append(came_from)
    return entered


def walked_metres(graph: Graph, edge_indices: list[int], start: GraphPoint, end: GraphPoint) -> list[float]:
    """trailGraph.ts's walkedMetresPerEdge."""
    entered = entered_nodes(graph, edge_indices, start, end)
    out = []
    last = len(edge_indices) - 1
    for at, edge_index in enumerate(edge_indices):
        edge = graph.edges[edge_index]
        if len(edge_indices) == 1:
            out.append(abs(end.fraction - start.fraction) * edge["length_m"])
            continue
        forward = entered[at] == edge["from"]
        if at == 0:
            out.append((1 - start.fraction if forward else start.fraction) * edge["length_m"])
        elif at == last:
            out.append((end.fraction if forward else 1 - end.fraction) * edge["length_m"])
        else:
            out.append(edge["length_m"])
    return out


def route_climb(graph: Graph, edge_indices: list[int], walked: list[float], entered: list[int]) -> tuple[float, float] | None:
    """trailGraph.ts's routeClimb: `(gain_ft, loss_ft)`, or None when any
    edge of the walk was never measured. Partial edges are pro-rated by the
    share walked; an edge walked against its stored direction swaps its
    ascent for its descent (#1034)."""
    if not edge_indices or graph.climb is None:
        return None
    gain = loss = 0.0
    for at, edge_index in enumerate(edge_indices):
        edge = graph.edges[edge_index]
        climb = graph.climb[edge_index]
        if climb is None:
            return None
        share = min(max(walked[at] / edge["length_m"], 0.0), 1.0) if edge["length_m"] > 0 else 0.0
        forward = entered[at] == edge["from"]
        gain += (climb[0] if forward else climb[1]) * share
        loss += (climb[1] if forward else climb[0]) * share
    return gain, loss


def _legs_from_walk(graph: Graph, edge_indices: list[int], walked: list[float]) -> list[Leg]:
    legs: list[Leg] = []
    for at, edge_index in enumerate(edge_indices):
        edge = graph.edges[edge_index]
        if legs and same_trail({"trail_id": legs[-1].trail_id, "name": legs[-1].name}, edge):
            legs[-1].miles += metres_to_miles(walked[at])
            continue
        legs.append(
            Leg(
                name=edge.get("name"),
                source=edge.get("source"),
                blaze_color=edge.get("blaze_color"),
                trail_id=edge.get("trail_id"),
                miles=metres_to_miles(walked[at]),
            )
        )
    return legs


def _assemble(
    graph: Graph, edge_indices: list[int], walked: list[float], entered: list[int], start: GraphPoint, end: GraphPoint
) -> Route:
    climb = route_climb(graph, edge_indices, walked, entered)
    return Route(
        sections=[Section(edge_indices=list(edge_indices), start=start, end=end, walked_metres=walked, entered=entered)],
        legs=_legs_from_walk(graph, edge_indices, walked),
        miles=metres_to_miles(sum(walked)),
        edge_indices=list(edge_indices),
        climb=climb,
        climb_note=None if climb is not None else (graph.climb_note or "an edge on this walk has no measured climb"),
    )


def route_between(graph: Graph, start: GraphPoint, end: GraphPoint) -> Route | None:
    """trailGraph.ts's routeBetween: the shortest walk between two points on
    the network, or None when the graph holds no path between them."""
    if start.edge_index == end.edge_index:
        edge = graph.edges[start.edge_index]
        metres = abs(end.fraction - start.fraction) * edge["length_m"]
        indices = [start.edge_index]
        return _assemble(graph, indices, [metres], entered_nodes(graph, indices, start, end), start, end)
    from_edge = graph.edges[start.edge_index]
    to_edge = graph.edges[end.edge_index]
    seeds = [
        (from_edge["from"], start.fraction * from_edge["length_m"]),
        (from_edge["to"], (1 - start.fraction) * from_edge["length_m"]),
    ]
    targets = {to_edge["from"]: end.fraction * to_edge["length_m"]}
    # The far end may be the same node when an edge is a loop; the cheaper
    # tail wins, as a JS Map's second set() would overwrite the first.
    targets[to_edge["to"]] = (1 - end.fraction) * to_edge["length_m"]
    found = _shortest_path(graph, seeds, targets)
    if found is None:
        return None
    node, _, reached = found
    middle = _walk_back(reached, node)
    indices = [start.edge_index, *middle, end.edge_index]
    walked = walked_metres(graph, indices, start, end)
    return _assemble(graph, indices, walked, entered_nodes(graph, indices, start, end), start, end)


def route_through(graph: Graph, points: list[GraphPoint]) -> Route | None:
    """trailGraph.ts's routeThrough: every point in order, or None if ANY
    leg cannot be routed - a partial route with a hole in it is a hiker told
    something false about the missing leg."""
    if len(points) < 2:
        return None
    sections: list[Section] = []
    legs: list[Leg] = []
    edge_indices: list[int] = []
    climbs: list[tuple[float, float] | None] = []
    notes: list[str] = []
    metres = 0.0
    for step in range(len(points) - 1):
        section = route_between(graph, points[step], points[step + 1])
        if section is None:
            return None
        metres += section.metres
        climbs.append(section.climb)
        if section.climb_note:
            notes.append(section.climb_note)
        sections.extend(section.sections)
        for edge_index in section.edge_indices:
            if edge_indices and edge_indices[-1] == edge_index:
                continue
            edge_indices.append(edge_index)
        for leg in section.legs:
            if legs and same_trail(
                {"trail_id": legs[-1].trail_id, "name": legs[-1].name}, {"trail_id": leg.trail_id, "name": leg.name}
            ):
                legs[-1].miles += leg.miles
                continue
            legs.append(Leg(**leg.to_dict()))
    climb: tuple[float, float] | None = (0.0, 0.0)
    for part in climbs:
        if part is None:
            climb = None
            break
        climb = (climb[0] + part[0], climb[1] + part[1])
    return Route(
        sections=sections,
        legs=legs,
        miles=metres_to_miles(metres),
        edge_indices=edge_indices,
        climb=climb,
        climb_note=None if climb is not None else (notes[0] if notes else None),
    )


def close_the_loop(graph: Graph, points: list[GraphPoint]) -> Route | None:
    """trailGraph.ts's closeTheLoop: through every point and back to the first."""
    if len(points) < 2:
        return None
    return route_through(graph, [*points, points[0]])


def cut_polyline(coords: list, from_fraction: float, to_fraction: float) -> list:
    """trailGraph.ts's cutPolyline: the piece between two fractions of arc length."""
    lengths = []
    total = 0.0
    for step in range(len(coords) - 1):
        length = metres_between((coords[step][0], coords[step][1]), (coords[step + 1][0], coords[step + 1][1]))
        lengths.append(length)
        total += length
    if total == 0:
        return list(coords)
    start_at = max(0.0, min(1.0, from_fraction)) * total
    end_at = max(0.0, min(1.0, to_fraction)) * total
    if end_at <= start_at:
        return []
    out = []
    walked = 0.0
    for step, length in enumerate(lengths):
        segment_start, segment_end = walked, walked + length
        a, b = coords[step], coords[step + 1]

        def point_at(distance, a=a, b=b, length=length, segment_start=segment_start):
            t = 0.0 if length == 0 else (distance - segment_start) / length
            return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t]

        if segment_end > start_at and segment_start < end_at:
            if not out:
                out.append(point_at(max(start_at, segment_start)))
            if segment_end <= end_at:
                out.append([b[0], b[1]])
            else:
                out.append(point_at(end_at))
                break
        walked = segment_end
    return out


def section_lines(graph: Graph, section: Section) -> list[list] | None:
    """trailGraph.ts's routeGeometry for one section: one line per edge in
    walking order, the partial ends trimmed; None when any edge has no
    geometry, rather than a chord across a switchback."""
    for edge_index in section.edge_indices:
        if not graph.has_geometry(edge_index):
            return None
    entered = entered_nodes(graph, section.edge_indices, section.start, section.end)
    lines = []
    last = len(section.edge_indices) - 1
    for step, edge_index in enumerate(section.edge_indices):
        edge = graph.edges[edge_index]
        forward = entered[step] == edge["from"]
        coords = list(graph.geometry[edge_index]) if forward else list(reversed(graph.geometry[edge_index]))
        from_fraction, to_fraction = 0.0, 1.0
        if step == 0 and section.start.edge_index == edge_index:
            from_fraction = section.start.fraction if forward else 1 - section.start.fraction
        if step == last and section.end.edge_index == edge_index:
            to_fraction = section.end.fraction if forward else 1 - section.end.fraction
        if step == 0 and step == last and from_fraction > to_fraction:
            from_fraction, to_fraction = to_fraction, from_fraction
        if from_fraction > 0 or to_fraction < 1:
            coords = cut_polyline(coords, from_fraction, to_fraction)
        if len(coords) >= 2:
            lines.append(coords)
    return lines


def route_lines(graph: Graph, route: Route) -> list[list] | None:
    """trailGraph.ts's routeLines: the whole walk, leg by leg, a re-walked
    leg drawn again over itself; None if any section cannot be drawn."""
    lines = []
    for section in route.sections:
        drawn = section_lines(graph, section)
        if drawn is None:
            return None
        lines.extend(drawn)
    return lines or None


def junctions_of(
    graph: Graph, name_a: str, name_b: str, near: tuple[float, float], radius_m: float = 5_000
) -> list[tuple[int, tuple[float, float]]]:
    """Nodes where an edge named `name_a` meets one named `name_b`, within
    the radius - the review script's way of turning "where the Halifax Trail
    leaves the Vista Loop Trail" into a point. Names compare case-folded and
    by containment, because a steward's name for a trail ("Vista Loop Trail
    (yellow)") is rarely the guide's exact spelling."""
    a, b = name_a.casefold(), name_b.casefold()
    by_node: dict[int, set[str]] = {}
    for edge_index in edges_near(graph, near[0], near[1], radius_m):
        edge = graph.edges[edge_index]
        name = (edge.get("name") or "").casefold()
        if not name:
            continue
        for node in (edge["from"], edge["to"]):
            if metres_between(tuple(graph.nodes[node]), near) > radius_m:
                continue
            tags = by_node.setdefault(node, set())
            if a in name:
                tags.add("a")
            if b in name:
                tags.add("b")
    found = [(node, tuple(graph.nodes[node])) for node, tags in by_node.items() if tags == {"a", "b"}]
    return sorted(found, key=lambda pair: metres_between(pair[1], near))


def point_at_node(graph: Graph, node: int) -> GraphPoint:
    """A GraphPoint sitting exactly on a node, via the first edge that
    touches it - the routing does not care which."""
    to, edge_index = graph.adjacency[node][0]
    edge = graph.edges[edge_index]
    fraction = 0.0 if edge["from"] == node else 1.0
    coords = graph.nodes[node]
    return GraphPoint(edge_index=edge_index, fraction=fraction, at=(coords[0], coords[1]), off_metres=0.0)
