"""Build the corridor polygon that export_poi.py and export_trails.py both
clip their output against: the 30-mile buffer around the A.T., and since #1016
the ground under another organization's trail lines too, for the callers that
publish for it (see build_corridor's `network_path`).

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
METERS_PER_FOOT = 0.3048

# How far around ANOTHER organization's trail lines the corridor reaches, when
# a caller passes them (#1016). Deliberately not 30 miles, and the asymmetry is
# the decision rather than an oversight.
#
# The A.T.'s 30 miles are context: towns, resupply, parking, the things a
# thru-hiker leaves the trail for. features/NEARBY_TRAILS.md's decisions table
# (2026-08-18) says the network gets no such context - "Amenity POIs | Chosen
# trail only" - and only safety POIs are drawn for every trail on screen. So
# this buffer has exactly one job: be wide enough that the clip can never be
# the thing that decides whether a SAFETY POI reaches a hiker, leaving that to
# the gate that was designed to decide it.
#
# The widest such gate is build_osm_water_reach.py's 100 ft reach radius. 500 ft
# is five times it - slack for a future safety gate rather than a measurement,
# and `test_corridor_network.py` pins the relationship (this must stay larger
# than MATCH_RADIUS_FT) so a re-tune of that gate cannot quietly outgrow the
# clip that has to keep its passes.
#
# @unvalidated as a NUMBER: nobody has counted what a 500 ft ring around 3,663
# network lines admits from the other POI sources, because no fetched layers
# exist in the sandbox this was written in. It is bounded rather than unknown -
# every source but osm_water is A.T.-derived and sits on A.T. ground - and
# export_poi.py prints the per-source admitted counts on every run, so the real
# figure lands in the log rather than in this comment.
NETWORK_BUFFER_FEET = 500

# Same CRS choice as spike_corridor.py/export_poi.py/export_trails.py, for
# the same reason: EPSG:5070 (NAD83 / Conus Albers) is equal-area, meters,
# and appropriate for a CONUS-spanning buffer operation.
PROJECTED_CRS = "EPSG:5070"
GEOGRAPHIC_CRS = "EPSG:4326"


def count_features(con: duckdb.DuckDBPyConnection, path: Path) -> int:
    """How many features `path` holds, or 0 when it is absent.

    WHY EVERY READER OF THE NETWORK ARTIFACT HAS TO ASK THIS FIRST, and it is
    not defensiveness: `ST_Read` infers its columns from the features it finds,
    so an EMPTY FeatureCollection yields a table with no `source`, no `name`
    and no `geom` at all. A loader that names any of those against an empty
    file gets a BinderException - "Referenced column "source" not found" - and
    an empty artifact is an ordinary state, not a broken one: it is the licence
    gate having held every steward's lines back, the same reading
    `fetch_elevation.network_extent` gives it.

    Counting with no column named is the one query that survives both shapes.
    """
    if not path.exists():
        return 0
    return con.execute(f"SELECT count(*) FROM ST_Read('{path.as_posix()}')").fetchone()[0]


def _has_features(con: duckdb.DuckDBPyConnection, path: Path) -> bool:
    """Whether `path` is a network worth widening the corridor for, loading it
    into a `network_raw` table when it is."""
    if not count_features(con, path):
        return False
    con.execute(f"CREATE OR REPLACE TABLE network_raw AS SELECT * FROM ST_Read('{path.as_posix()}')")
    return True


def build_corridor(con: duckdb.DuckDBPyConnection, centerline_path: Path, network_path: Path | None = None) -> bool:
    """Build the 'corridor' table fresh from `centerline_path` - the
    ST_Buffer(30mi) + ST_Union_Agg pattern spike_corridor.py proved and
    export_poi.py/export_trails.py each duplicated verbatim before this
    extraction, including always_xy on both transform legs (see this
    module's docstring - without it ST_Transform silently swaps lat/lon and
    produces garbage geometry). Assumes `con` already has the spatial
    extension loaded (see this module's docstring).

    `network_path` widens it by NETWORK_BUFFER_FEET around another
    organization's published trail lines (#1016). Returns whether it did.

    WHY THIS IS A WIDENING AND NOT A SECOND CORRIDOR. Until #950 the A.T. was
    the only trail this app drew, so "the corridor" and "the ground this app
    publishes for" were the same sentence. They stopped being the same the day
    NYS OPRHP's, NYNJTC's and Mohonk Preserve's lines shipped, and the water
    build kept clipping to the older meaning - which is how four organizations'
    trails came to have no water source of either hydrography. One table with
    one meaning is what stops that recurring: a caller either publishes for the
    network's ground or it does not, and says so at the call.

    OMITTING network_path IS STILL CORRECT and is what export_trails.py does -
    its subject is ATC's own two layers, and clipping them to a wider world
    would keep nothing extra, because there is nothing of theirs out there.
    """
    centerline_posix = centerline_path.as_posix()
    con.execute(f"CREATE OR REPLACE TABLE centerline_raw AS SELECT * FROM ST_Read('{centerline_posix}')")

    def buffered(table: str, meters: float) -> str:
        return f"""
            SELECT ST_Buffer(
                ST_Transform(geom, '{GEOGRAPHIC_CRS}', '{PROJECTED_CRS}', always_xy := true),
                {meters}
            ) AS g
            FROM {table}
        """

    # One branch when there is no network, which is the same set of geometries
    # ST_Union_Agg saw before this parameter existed - so an A.T.-only call
    # produces the same corridor it always did.
    branches = [buffered("centerline_raw", BUFFER_MILES * METERS_PER_MILE)]
    widened = network_path is not None and _has_features(con, network_path)
    if widened:
        branches.append(buffered("network_raw", NETWORK_BUFFER_FEET * METERS_PER_FOOT))

    con.execute(f"""
        CREATE OR REPLACE TABLE corridor AS
        SELECT ST_Transform(
            ST_Union_Agg(g),
            '{PROJECTED_CRS}', '{GEOGRAPHIC_CRS}', always_xy := true
        ) AS geom
        FROM ({" UNION ALL ".join(branches)})
    """)
    return widened
