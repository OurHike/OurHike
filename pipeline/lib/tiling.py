"""Web Mercator slippy-map (XYZ) tile math.

Hand-rolled rather than adding morecantile as a dependency - this is ~10
lines of standard formulas, and this project already keeps small custom
helpers in lib/ instead of pulling in a framework for something this size
(see arcgis.py).
"""

WEB_MERCATOR_HALF_WORLD = 20037508.342789244  # meters; half the EPSG:3857 world extent


def tile_bounds_merc(z: int, x: int, y: int) -> tuple[float, float, float, float]:
    """EPSG:3857 (minx, miny, maxx, maxy) bounds of XYZ tile (z, x, y)."""
    n = 2**z
    tile_size = 2 * WEB_MERCATOR_HALF_WORLD / n
    minx = -WEB_MERCATOR_HALF_WORLD + x * tile_size
    maxx = minx + tile_size
    maxy = WEB_MERCATOR_HALF_WORLD - y * tile_size
    miny = maxy - tile_size
    return minx, miny, maxx, maxy


def tile_range_for_bounds(bounds_merc: tuple[float, float, float, float], z: int) -> tuple[int, int, int, int]:
    """Candidate (x0, x1, y0, y1) inclusive XYZ tile index range at zoom z
    that could intersect the given EPSG:3857 bounds.

    This is a cheap bounding-box filter, not a real intersection test - the
    caller is expected to follow up with an actual polygon-intersection
    check (e.g. against the real corridor shape) since this range is a
    superset of the tiles that actually matter."""
    minx, miny, maxx, maxy = bounds_merc
    n = 2**z
    tile_size = 2 * WEB_MERCATOR_HALF_WORLD / n
    x0 = max(0, int((minx + WEB_MERCATOR_HALF_WORLD) // tile_size))
    x1 = min(n - 1, int((maxx + WEB_MERCATOR_HALF_WORLD) // tile_size))
    y0 = max(0, int((WEB_MERCATOR_HALF_WORLD - maxy) // tile_size))
    y1 = min(n - 1, int((WEB_MERCATOR_HALF_WORLD - miny) // tile_size))
    return x0, x1, y0, y1
