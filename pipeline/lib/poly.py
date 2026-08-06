"""Osmosis .poly serialization, for the clip shape handed to osmium and
Planetiler by export_basemap.py.

Both tools take the same plain-text polygon format (one section per outer
ring, holes as !-prefixed sections) and clip raw OSM data to it. The format
is trivial, stable since Osmosis, and ~30 lines to emit - the same reasoning
that keeps tiling.py hand-rolled instead of adding a dependency.

The clip shape is deliberately NOT the corridor itself. The corridor polygon
is built from ~3,000 buffered segments and carries far more vertices than a
clip test should pay for on every OSM object - and a clip boundary that hugs
the corridor exactly would also be wrong, because Planetiler and osmium clip
to *tiles/objects intersecting the shape*, and a basemap feature crossing the
boundary should arrive whole. clip_shape() therefore simplifies and then
buffers OUTWARD by the same tolerance: Douglas-Peucker moves a boundary by at
most the tolerance, so buffering by that same tolerance restores a guaranteed
superset of the original shape. The package a hiker downloads is still cut
against the real corridor (extract_package.py) - the padded shape only
bounds what the build considers, never what ships.
"""

from shapely.geometry import MultiPolygon, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union


def clip_shape(geom: BaseGeometry, tolerance_deg: float = 0.01) -> BaseGeometry:
    """A cheap, guaranteed superset of `geom` for clipping raw OSM data.

    `tolerance_deg` is in degrees (the corridor is EPSG:4326); 0.01 is ~1.1 km
    N-S - noise against a 30-mile corridor buffer, decisive against paying
    full corridor vertex count per clipped OSM object."""
    return geom.simplify(tolerance_deg).buffer(tolerance_deg)


def from_poly(text: str) -> BaseGeometry:
    """Parse Osmosis .poly text back into a Polygon or MultiPolygon.

    The inverse of to_poly(), and here because Geofabrik publishes a .poly
    beside every extract - the exact shape it cut that extract with. Reading
    it is how a shard's own boundary becomes a geometry we can intersect
    against its neighbour's to get the seam between them, which is the line
    compare_shards.py measures differences against.

    Sections are rings; a leading `!` marks a hole, matching to_poly()'s
    spelling. Ring names are otherwise ignored - the format allows any label
    and only the `!` carries meaning."""
    outers: list[list[tuple[float, float]]] = []
    holes: list[list[tuple[float, float]]] = []
    ring: list[tuple[float, float]] | None = None
    is_hole = False

    # The first line is the polygon's name, never a section header.
    for line in text.splitlines()[1:]:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped == "END":
            if ring is None:
                break  # The file-level END, after the last section.
            (holes if is_hole else outers).append(ring)
            ring = None
            continue
        if ring is None:
            is_hole = stripped.startswith("!")
            ring = []
            continue
        x, y = stripped.split()[:2]
        ring.append((float(x), float(y)))

    if not outers:
        raise ValueError("No rings in .poly text")
    # Holes are matched to whichever outer ring contains them rather than by
    # file order: the format does not promise a hole follows its own outer,
    # and difference() over the union is indifferent to which one it was.
    return (
        unary_union([Polygon(r) for r in outers]).difference(unary_union([Polygon(r) for r in holes]))
        if holes
        else unary_union([Polygon(r) for r in outers])
    )


def to_poly(geom: BaseGeometry, name: str = "area") -> str:
    """Serialize a Polygon or MultiPolygon as Osmosis .poly text.

    Sections are numbered outer rings; holes are the same with a `!` prefix,
    which is how the format spells subtraction. Coordinates are lon lat -
    the axis order every geometry in this pipeline already carries (see
    lib/corridor.py's always_xy note)."""
    if isinstance(geom, Polygon):
        polygons = [geom]
    elif isinstance(geom, MultiPolygon):
        polygons = list(geom.geoms)
    else:
        raise ValueError(f"to_poly needs a Polygon or MultiPolygon, got {geom.geom_type}")

    lines = [name]
    section = 0
    for polygon in polygons:
        section += 1
        lines.append(str(section))
        lines.extend(f"   {x:.7f}   {y:.7f}" for x, y in polygon.exterior.coords)
        lines.append("END")
        for hole in polygon.interiors:
            section += 1
            lines.append(f"!{section}")
            lines.extend(f"   {x:.7f}   {y:.7f}" for x, y in hole.coords)
            lines.append("END")
    lines.append("END")
    return "\n".join(lines) + "\n"
