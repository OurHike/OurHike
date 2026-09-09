"""Build the corridor polygon that export_poi.py and export_trails.py both
clip their output against: the 30-mile buffer around the A.T., and since #1016
the ground under another organization's trail lines too, for the callers that
publish for it (see build_corridor's `network_path`).

THE NETWORK IS A JOIN, NOT A POLYGON (#1311). Between #1016 and 2026-09-09 the
widening was literal: every network line was buffered to NETWORK_BUFFER_FEET
and ST_Union_Agg'd into the corridor polygon with the A.T.'s thirty miles.
That was fine for 3,663 New York lines and stopped being fine on 2026-09-02,
when the Forest Service's nationwide layer took the network to 112,439 lines:
MEASURED on run #88 of publish-vector-data.yml (2026-09-08), the same unify-
and-clip that runs in 14.66 s against the A.T.-only corridor took 20:07
widened - and it is paid twice per build, once in reconcile_poi_identity.py
and once in export_poi.py. So the polygon is the A.T.'s alone again, exactly
as before #1016, and the network lives beside it as an R-tree-indexed line
table; `keep_within_corridor` asks both. A point is kept when it intersects
the polygon OR sits within NETWORK_BUFFER_FEET of some line, which is the
same set the union answered - a point inside ST_Union(ST_Buffer(line, r))
is a point within r of some line - reached without building the union.
export_nearby_poi.py had answered its own ring question this way since
#1097 (and measured 35 s for the whole step on the same nationwide file in
the same run); it shares the SQL now rather than carrying a second copy.

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


#: The line table `build_corridor` loads beside the polygon, and the name the
#: R-tree index over it takes. One home for both spellings: `near_network_sql`
#: reads the table, and a caller that builds its own connection
#: (export_nearby_poi.py) loads it through `load_network_lines` rather than
#: knowing the name.
NETWORK_TABLE = "network_lines"
NETWORK_INDEX = "network_lines_rtree"


def load_network_lines(con: duckdb.DuckDBPyConnection, path: Path | None) -> int:
    """Load `path`'s lines into NETWORK_TABLE, projected to metres and
    R-tree-indexed, and return how many. Always leaves the table in place -
    empty for a missing, empty or unpassed artifact - so `near_network_sql`
    can be joined unconditionally and an absent network reads as "nothing is
    near a line" rather than as a missing table.

    Empty is an ordinary state, not an error: it is the licence gate having
    held every steward's lines back, the reading `count_features` already
    gives it, and it is why the A.T.-only callers can pass nothing at all.
    """
    con.execute(f"DROP INDEX IF EXISTS {NETWORK_INDEX}")
    if path is None or not count_features(con, path):
        con.execute(f"CREATE OR REPLACE TABLE {NETWORK_TABLE} (g GEOMETRY)")
        return 0
    con.execute(f"""
        CREATE OR REPLACE TABLE {NETWORK_TABLE} AS
        SELECT ST_Transform(geom, '{GEOGRAPHIC_CRS}', '{PROJECTED_CRS}', always_xy := true) AS g
        FROM ST_Read('{path.as_posix()}')
    """)
    con.execute(f"CREATE INDEX {NETWORK_INDEX} ON {NETWORK_TABLE} USING RTREE (g)")
    return con.execute(f"SELECT count(*) FROM {NETWORK_TABLE}").fetchone()[0]


def build_corridor(
    con: duckdb.DuckDBPyConnection,
    centerline_path: Path,
    network_path: Path | None = None,
    buffer_miles: float = BUFFER_MILES,
) -> bool:
    """Build the 'corridor' table fresh from `centerline_path` - the
    ST_Buffer(30mi) + ST_Union_Agg pattern spike_corridor.py proved and
    export_poi.py/export_trails.py each duplicated verbatim before this
    extraction, including always_xy on both transform legs (see this
    module's docstring - without it ST_Transform silently swaps lat/lon and
    produces garbage geometry). Assumes `con` already has the spatial
    extension loaded (see this module's docstring).

    `network_path` loads another organization's published trail lines
    beside the polygon (#1016, #1311 - see the module docstring for why
    beside and not into). Returns whether any were loaded. Callers that clip
    then ask `keep_within_corridor`, which reaches both; a caller that reads
    the `corridor` table directly gets the A.T.'s ground and nothing else,
    which is what every such caller wants (fetch_elevation.py loads the
    network on its own terms for its own reason).

    WHY THIS IS A WIDENING AND NOT A SECOND CORRIDOR. Until #950 the A.T. was
    the only trail this app drew, so "the corridor" and "the ground this app
    publishes for" were the same sentence. They stopped being the same the day
    NYS OPRHP's, NYNJTC's and Mohonk Preserve's lines shipped, and the water
    build kept clipping to the older meaning - which is how four organizations'
    trails came to have no water source of either hydrography. One question
    with one answer is what stops that recurring: a caller either publishes for
    the network's ground or it does not, and says so at the call.

    OMITTING network_path IS STILL CORRECT and is what export_trails.py does -
    its subject is ATC's own two layers, and clipping them to a wider world
    would keep nothing extra, because there is nothing of theirs out there.

    `buffer_miles` OVERRIDES THE 30, and exists for one caller: export_dem.py,
    which needs a NARROWER shape than the POI corridor and a different one per
    zoom (#1088). BUFFER_MILES stays the default, so every existing caller
    builds the corridor it always did. See export_dem.CORRIDOR_TAPER_MILES for
    why terrain wants its own width - the 30 above is argued from resupply
    POIs, which is not an argument about hillshade.
    """
    centerline_posix = centerline_path.as_posix()
    con.execute(f"CREATE OR REPLACE TABLE centerline_raw AS SELECT * FROM ST_Read('{centerline_posix}')")
    con.execute(f"""
        CREATE OR REPLACE TABLE corridor AS
        SELECT ST_Transform(
            ST_Union_Agg(g),
            '{PROJECTED_CRS}', '{GEOGRAPHIC_CRS}', always_xy := true
        ) AS geom
        FROM (
            SELECT ST_Buffer(
                ST_Transform(geom, '{GEOGRAPHIC_CRS}', '{PROJECTED_CRS}', always_xy := true),
                {buffer_miles * METERS_PER_MILE}
            ) AS g
            FROM centerline_raw
        )
    """)
    return load_network_lines(con, network_path) > 0


def near_network_sql(table: str, id_col: str, lon_col: str, lat_col: str) -> str:
    """One SELECT of `table`'s `id_col` for every row within NETWORK_BUFFER_FEET
    of a NETWORK_TABLE line - the ring, as a query both clips share.

    Buffers the POINT and asks which lines the disc intersects, never the
    other way round, because that is the shape the R-tree answers: one
    candidate disc probes the index, where buffering 112,439 lines would be
    the union this module stopped building. `ST_Buffer(point, r)` intersects
    a line exactly when the point is within r of it, so the set is the one
    the old polygon answered. GROUP BY so a point near two lines is one row.
    """
    radius_m = NETWORK_BUFFER_FEET * METERS_PER_FOOT
    return f"""
        SELECT t.{id_col} AS id
        FROM {table} t
        JOIN {NETWORK_TABLE} n
          ON ST_Intersects(
               n.g,
               ST_Buffer(
                 ST_Transform(ST_Point(t.{lon_col}, t.{lat_col}), '{GEOGRAPHIC_CRS}', '{PROJECTED_CRS}', always_xy := true),
                 {radius_m}
               )
             )
        GROUP BY t.{id_col}
    """


def keep_within_corridor(con: duckdb.DuckDBPyConnection, table: str, id_col: str, lon_col: str, lat_col: str) -> int:
    """Write `corridor_hits(id)`: the ids of `table`'s rows the corridor
    reaches - inside the A.T. polygon `build_corridor` built, or within
    NETWORK_BUFFER_FEET of a line it loaded - and return how many.

    A table rather than a returned set so the id keeps its own type: a
    caller joins `corridor_hits` back to its rows (build_osm_water_reach.py)
    or reads the ids out (export_poi.py), and neither has to say what an id
    is. `build_corridor` must have run on `con` first.
    """
    con.execute(f"""
        CREATE OR REPLACE TABLE corridor_hits AS
        SELECT DISTINCT id FROM (
            SELECT t.{id_col} AS id
            FROM {table} t, corridor
            WHERE ST_Intersects(ST_Point(t.{lon_col}, t.{lat_col}), corridor.geom)
            UNION ALL
            {near_network_sql(table, id_col, lon_col, lat_col)}
        )
    """)
    return con.execute("SELECT count(*) FROM corridor_hits").fetchone()[0]
