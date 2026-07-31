"""Corridor cell-grid logic shared between the raster mosaic step
(spike_raster_mosaic.py) and the per-cell fetch+mosaic path
(fetch_and_mosaic_cell.py) - kept in exactly one place so the two can never
silently compute different cell boundaries or quad-to-cell assignments,
which would otherwise be an easy way to introduce a coverage gap that only
surfaces downstream, in the exported background map.

The 1-degree grid here is the same one spike_raster_mosaic.py has always
tiled its output by (see that script's docstring for why: a mosaic sized to
the corridor's full bounding rectangle would be enormous, since the actual
corridor is a thin ~60-mile-wide winding band, not a filled rectangle).
"""

import json
from pathlib import Path

import duckdb

CELL_DEGREES = 1.0


def compute_cells(corridor_path: Path) -> list[tuple]:
    """The corridor-intersecting 1-degree grid cells, as (west, south, east,
    north) bbox tuples."""
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    con.execute(f"CREATE TABLE corridor AS SELECT * FROM ST_Read('{corridor_path.as_posix()}')")
    bbox = con.execute("SELECT ST_XMin(geom), ST_YMin(geom), ST_XMax(geom), ST_YMax(geom) FROM corridor").fetchone()

    xmin, ymin, xmax, ymax = bbox
    cells = []
    x = xmin
    while x < xmax:
        y = ymin
        while y < ymax:
            cx0, cy0 = x, y
            cx1, cy1 = min(x + CELL_DEGREES, xmax), min(y + CELL_DEGREES, ymax)
            hit = con.execute(f"""
                SELECT EXISTS (SELECT 1 FROM corridor WHERE ST_Intersects(geom, ST_MakeEnvelope({cx0}, {cy0}, {cx1}, {cy1})))
            """).fetchone()[0]
            if hit:
                cells.append((cx0, cy0, cx1, cy1))
            y += CELL_DEGREES
        x += CELL_DEGREES
    return cells


def load_corridor_geom(corridor_path: Path) -> dict:
    """The corridor polygon as GeoJSON geometry, for the final corridor-clip
    (rasterio.mask.mask) step - loaded independently of compute_cells() (a
    second small query against the same small file) so the two stay
    separately callable/testable rather than bundled into one do-everything
    function."""
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    con.execute(f"CREATE TABLE corridor AS SELECT * FROM ST_Read('{corridor_path.as_posix()}')")
    return json.loads(con.execute("SELECT ST_AsGeoJSON(geom) FROM corridor").fetchone()[0])


def bounds_intersect(a: tuple, b: tuple) -> bool:
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    return ax0 < bx1 and ax1 > bx0 and ay0 < by1 and ay1 > by0


def load_quad_bounds(corridor_path: Path, metadata_csv_path: Path) -> dict[str, tuple]:
    """product_filename -> (west, south, east, north) for every quad whose
    bbox intersects the AT corridor. Deliberately independent of
    fetch_topo_quads.corridor_intersecting_quads()'s own, near-identical
    query rather than sharing it - that function's contract (a bare list of
    filenames, no bbox) is relied on as-is by fetch_topo_quads.py's
    existing, already-tested whole-corridor path, and this module's own
    cell-assignment use case needs the bbox columns too."""
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    con.execute(f"CREATE TABLE corridor AS SELECT * FROM ST_Read('{corridor_path.as_posix()}')")
    con.execute(f"CREATE TABLE quads AS SELECT * FROM read_csv_auto('{metadata_csv_path.as_posix()}')")
    rows = con.execute("""
        SELECT q.product_filename, q.westbc, q.southbc, q.eastbc, q.northbc
        FROM quads q, corridor c
        WHERE ST_Intersects(
            ST_MakeEnvelope(q.westbc, q.southbc, q.eastbc, q.northbc),
            c.geom
        )
    """).fetchall()
    return {pf: (west, south, east, north) for pf, west, south, east, north in rows}


def assign_quads_to_cells(quad_bounds: dict[str, tuple], cells: list[tuple]) -> dict[int, list[str]]:
    """Every cell a quad's bbox overlaps, not just the first - ~23% of
    corridor quads bbox-overlap more than one 1-degree cell (measured
    directly against the real AT corridor/quad data: 378 of 1,654), so a
    quad near a cell boundary genuinely belongs to more than one cell's
    fetch list. Accepting the resulting duplicate fetches (a quad gets
    pulled once per owning cell, ~3.6GB total across the whole corridor) is
    a deliberate tradeoff - the alternative is a shared quad cache across
    independent, parallel per-cell jobs, which reintroduces the
    disk/coordination problem this per-cell split exists to avoid."""
    assignment: dict[int, list[str]] = {i: [] for i in range(len(cells))}
    for product_filename, bounds in quad_bounds.items():
        for i, cell in enumerate(cells):
            if bounds_intersect(bounds, cell):
                assignment[i].append(product_filename)
    return assignment


def build_cells_manifest(corridor_path: Path, metadata_csv_path: Path) -> dict:
    """{"cells": [{"index": 0, "bbox": [...], "quads": [...]}, ...]} - the
    one artifact every downstream per-cell fetch+mosaic job (and CI's
    matrix step) needs, computed once from small vector data (no rasters
    touched at all)."""
    cells = compute_cells(corridor_path)
    quad_bounds = load_quad_bounds(corridor_path, metadata_csv_path)
    assignment = assign_quads_to_cells(quad_bounds, cells)
    return {"cells": [{"index": i, "bbox": list(cell), "quads": assignment[i]} for i, cell in enumerate(cells)]}
