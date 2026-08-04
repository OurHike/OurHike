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


def clip_shape(geom: BaseGeometry, tolerance_deg: float = 0.01) -> BaseGeometry:
    """A cheap, guaranteed superset of `geom` for clipping raw OSM data.

    `tolerance_deg` is in degrees (the corridor is EPSG:4326); 0.01 is ~1.1 km
    N-S - noise against a 30-mile corridor buffer, decisive against paying
    full corridor vertex count per clipped OSM object."""
    return geom.simplify(tolerance_deg).buffer(tolerance_deg)


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
