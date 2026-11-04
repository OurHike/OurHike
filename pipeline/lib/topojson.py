"""Read a TopoJSON topology into shapely geometries (#1965).

WHY A READER OF OUR OWN RATHER THAN A PACKAGE. The two files this reads are
Mike Bostock's `us-atlas` and `world-atlas` (lib/atlas_sources.py), and
export_challenge_map.py needs three things from them: each state's or
country's polygon, each polygon's label point, and the lines two states
share - the borders a map draws once, which a TopoJSON carries for free
because a shared edge is one arc referenced by both polygons. The format is
small (topojson-specification §2, read 2026-11-04): a transform, a list of
delta-encoded arcs, and objects whose rings are lists of arc indexes. The
Python packages that read it (`topojson`, `pytopojson`) exist to WRITE it,
pull in geopandas or networkx to do so, and would be a dependency for forty
lines of decoding. The forty lines are here, and tests/test_lib_topojson.py
holds them to the specification's own examples.

WHAT IS AND IS NOT HANDLED. Quantized (`transform`) and unquantized arcs;
LineString, MultiLineString, Polygon, MultiPolygon and GeometryCollection
objects; the `~index` reversal. Not handled, because neither atlas carries
one: a Point or MultiPoint object, and a `bbox`'s meaning for projected
topologies (us-atlas's `-albers` files are projected and are not read here).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import shapely
from shapely.geometry import LineString, MultiLineString, MultiPolygon, Polygon
from shapely.geometry.base import BaseGeometry

Position = tuple[float, float]


@dataclass(frozen=True)
class Feature:
    """One geometry of a topology object, with the arcs it was built from -
    the arc indexes are what `shared_arcs` reads borders off."""

    id: str | None
    properties: dict
    geometry: BaseGeometry
    arc_indexes: frozenset[int] = field(default_factory=frozenset)


def decode_arcs(topology: dict) -> list[list[Position]]:
    """Every arc as absolute (x, y) positions.

    With a `transform`, each arc's positions are quantized integers and every
    position after the first is a delta from the one before
    (topojson-specification §2.1.2); without one, they are absolute floats.
    """
    transform = topology.get("transform")
    arcs: list[list[Position]] = []
    for raw in topology["arcs"]:
        if transform is None:
            arcs.append([(float(p[0]), float(p[1])) for p in raw])
            continue
        sx, sy = transform["scale"]
        tx, ty = transform["translate"]
        x = y = 0
        decoded: list[Position] = []
        for dx, dy in raw:
            x += dx
            y += dy
            decoded.append((x * sx + tx, y * sy + ty))
        arcs.append(decoded)
    return arcs


def arc_index(index: int) -> int:
    """The arc an index refers to: itself, or `~index` for a reversed one."""
    return index if index >= 0 else ~index


def stitch(indexes: list[int], arcs: list[list[Position]]) -> list[Position]:
    """A line or ring from a list of arc indexes.

    Consecutive arcs share their junction point - the last of one is the
    first of the next - so every arc after the first contributes from its
    second point. A reversed arc (`~index`) is walked backwards.
    """
    line: list[Position] = []
    for index in indexes:
        arc = arcs[arc_index(index)]
        points = arc[::-1] if index < 0 else arc
        line.extend(points[1:] if line else points)
    return line


def _polygon(rings: list[list[int]], arcs: list[list[Position]]) -> Polygon:
    shells = [stitch(ring, arcs) for ring in rings]
    polygon = Polygon(shells[0], shells[1:])
    # A quantized ring can touch itself at a point, which shapely reads as
    # invalid and refuses to measure; make_valid keeps the area it encloses.
    return polygon if polygon.is_valid else shapely.make_valid(polygon)


def _geometry(obj: dict, arcs: list[list[Position]]) -> BaseGeometry | None:
    kind = obj["type"]
    if kind == "LineString":
        return LineString(stitch(obj["arcs"], arcs))
    if kind == "MultiLineString":
        return MultiLineString([stitch(part, arcs) for part in obj["arcs"]])
    if kind == "Polygon":
        return _polygon(obj["arcs"], arcs)
    if kind == "MultiPolygon":
        return shapely.union_all([_polygon(rings, arcs) for rings in obj["arcs"]])
    if kind == "GeometryCollection":
        parts = [g for g in (_geometry(member, arcs) for member in obj["geometries"]) if g is not None]
        return shapely.union_all(parts) if parts else None
    return None


def _arc_indexes(obj: dict) -> frozenset[int]:
    if obj["type"] == "GeometryCollection":
        return frozenset().union(*(_arc_indexes(member) for member in obj["geometries"]))
    found: set[int] = set()

    def walk(value) -> None:
        if isinstance(value, int):
            found.add(arc_index(value))
        else:
            for member in value:
                walk(member)

    walk(obj.get("arcs", []))
    return frozenset(found)


def features(topology: dict, object_name: str, arcs: list[list[Position]] | None = None) -> list[Feature]:
    """The geometries of one named object, in the file's order.

    A GeometryCollection object (which both atlases use) yields one Feature
    per member; any other object yields one. Members with no geometry (a
    null geometry, or a type this does not read) are skipped.
    """
    arcs = decode_arcs(topology) if arcs is None else arcs
    obj = topology["objects"][object_name]
    members = obj["geometries"] if obj["type"] == "GeometryCollection" else [obj]
    out: list[Feature] = []
    for member in members:
        geometry = _geometry(member, arcs)
        if geometry is None or geometry.is_empty:
            continue
        raw_id = member.get("id")
        out.append(
            Feature(
                id=None if raw_id is None else str(raw_id),
                properties=dict(member.get("properties") or {}),
                geometry=geometry,
                arc_indexes=_arc_indexes(member),
            )
        )
    return out


def shared_arcs(members: list[Feature], arcs: list[list[Position]]) -> list[list[Position]]:
    """The arcs two or more of `members` share, as lines - the borders between
    them, each once. topojson-client's `mesh(topology, object, (a, b) => a !== b)`.

    An arc used by exactly one member is an outer edge (a coastline, or a
    border with something outside the object) and is left out, which is what
    lets a map draw state borders over state fills without re-stroking every
    coast.
    """
    uses: dict[int, int] = {}
    for member in members:
        for index in member.arc_indexes:
            uses[index] = uses.get(index, 0) + 1
    return [list(arcs[index]) for index in sorted(uses) if uses[index] >= 2]
