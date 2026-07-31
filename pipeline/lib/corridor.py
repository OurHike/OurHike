"""Build the 30-mile AT corridor polygon that export_poi.py and
export_trails.py both clip their output against.

Until this extraction, `build_corridor()` was an identical, verbatim-
duplicated function living in both export_poi.py and export_trails.py - each
module independently re-deriving the same 30-mile buffer around
data/raw/centerline.geojson via the ST_Buffer(30mi) + ST_Union_Agg pattern
spike_corridor.py first proved. It lives here instead now, following
lib/corridor_grid.py's own precedent for the identical reason: kept in
exactly one place so export_poi.py, export_trails.py, and any future
consumer can never silently drift into computing two different corridor
boundaries from what should be the same source data.

Built fresh from whatever centerline path the caller passes in (in practice,
always data/raw/centerline.geojson) on every call - deliberately never from
data/spike/corridor.geojson. That file is stale proof-of-concept output from
spike_corridor.py (dated 2026-07-24); centerline.geojson was re-fetched
2026-07-25, *after* it, and nothing has regenerated
data/spike/corridor.geojson since. Reading the stale file here would
silently clip every export against out-of-date trail geometry.

always_xy: EPSG:4326's authority-defined axis order is (lat, lon), but every
geometry source this pipeline actually reads (GeoJSON, GeoPandas, etc.) is
(lon, lat). Without `always_xy := true` on *both* the forward and inverse
ST_Transform, DuckDB's spatial extension silently swaps the axes instead of
erroring - the buffer/union still "succeeds" but produces geometry
transformed as if every point were on the wrong side of the globe, which the
first time this bit us only surfaced as `ST_Area` returning `nan` on the
reprojected-back result (see README.md's "Gotcha hit and fixed" note and
test_spike_corridor.py's regression tests for the full story). Both
transform legs below keep `always_xy := true` exactly as both original
copies had it - this must not regress.

Caller's responsibility, not this function's: open the DuckDB connection and
run `INSTALL spatial; LOAD spatial;` on it before calling build_corridor().
export_poi.py's and export_trails.py's own main() already does this once,
up front, before doing anything corridor-related, so nothing changes there -
this just stops the (harmless but redundant) second copy of that same setup
call that used to also live inside build_corridor() itself.
"""

from pathlib import Path

import duckdb

BUFFER_MILES = 30
METERS_PER_MILE = 1609.344

# Same CRS choice as spike_corridor.py/export_poi.py/export_trails.py, for
# the same reason: EPSG:5070 (NAD83 / Conus Albers) is equal-area, meters,
# and appropriate for a CONUS-spanning buffer operation.
PROJECTED_CRS = "EPSG:5070"
GEOGRAPHIC_CRS = "EPSG:4326"


def build_corridor(con: duckdb.DuckDBPyConnection, centerline_path: Path) -> None:
    """Build the 'corridor' table fresh from `centerline_path` - the
    ST_Buffer(30mi) + ST_Union_Agg pattern spike_corridor.py proved and
    export_poi.py/export_trails.py each duplicated verbatim before this
    extraction, including always_xy on both transform legs (see this
    module's docstring - without it ST_Transform silently swaps lat/lon and
    produces garbage geometry). Assumes `con` already has the spatial
    extension loaded (see this module's docstring)."""
    centerline_posix = centerline_path.as_posix()
    con.execute(f"CREATE OR REPLACE TABLE centerline_raw AS SELECT * FROM ST_Read('{centerline_posix}')")

    buffer_meters = BUFFER_MILES * METERS_PER_MILE
    con.execute(f"""
        CREATE OR REPLACE TABLE corridor AS
        SELECT ST_Transform(
            ST_Union_Agg(
                ST_Buffer(
                    ST_Transform(geom, '{GEOGRAPHIC_CRS}', '{PROJECTED_CRS}', always_xy := true),
                    {buffer_meters}
                )
            ),
            '{PROJECTED_CRS}', '{GEOGRAPHIC_CRS}', always_xy := true
        ) AS geom
        FROM centerline_raw
    """)
