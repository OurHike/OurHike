"""step_dem_sampling: the DEM's elevation at every elevation sample point, written to derived.dem_samples for dbt to read back.

    python step_dem_sampling.py [--warehouse data/warehouse.duckdb] [--index data/raw/elevation/tile_index.json]

pipeline/ELT.md, "Python steps, outside dbt", is the design, and EL06 of its
ledger the rule: DEM pixels never enter DuckDB. Sampling USGS 3DEP's rasters
stays Python because DuckDB has nothing fast and right for it - the `raster`
extension measured about 50x slower (200 s against 4.1 s for 1,000,000
points) and `raquet` wrong at 736 of 2,000 points, by up to 3.0 m
(pipeline/DBT.md:35-48, measured 2026-09-24). Everything else is SQL: where
the A.T.'s samples sit and their miles (int_elevation__sample_points), its
clip, seams and rounding (int_elevation__profile), and each junction-graph
edge's samples, climb and whole feet (int_elevation__edge_sample_points,
int_elevation__edge_climbs, int_elevation__edge_samples).

THE STEP, between two dbt invocations:
1. dbt builds int_elevation__dem_points (and everything not downstream of
   the `derived` source): the A.T.'s walk and every junction-graph edge's
   samples;
2. this reads every row of it, in its ask_order, and hands the points to
   export_elevation.ElevationSampler.for_index(index).
   sample_many - the sampler and the call export_elevation.build_profile makes
   today, reused rather than reimplemented: the same tile index, the same
   nearest-neighbour read in each tile's own grid, the same nodata and
   non-finite -> None rule, the same per-point cache beside the index;
3. it writes one row per sample point to derived.dem_samples, the point as
   GeoJSON text beside the elevation, so the models that read it can refuse
   an elevation that was not read at its own sample's point;
4. dbt builds everything downstream of the `derived` source.

THE SAME QUESTIONS IN THE SAME ORDER, which int_elevation__dem_points'
ask_order holds. For the A.T. that is the walk's order, every sample
included - also the ones int_elevation__profile drops where two pieces cover
the same miles - because build_profile reads the DEM at all of them in that
order, and the sampler's cache answers a second point within 0.11 m of a
first with the first's pixel ("whoever asked first",
export_elevation.CACHE_KEY_DECIMALS). Then each edge by its edge_index, its
samples from its start, as export_network_elevation.build asks in one call:
publish-vector-data.yml runs export_elevation.py before both network
exporters, so on a cold cache the A.T. profile is always read at its own
points, and an edge point keyed like an A.T. point takes the A.T.'s answer.
export_network_profile.py asks the same edge points again and is answered
from the cache, so one question serves both.

A value the sampler hands back is None or a finite float, and a value that is
neither stops the step rather than reaching the table: the sampler already
refuses NaN and infinity (#659 - a literal NaN in the profile artifact takes
the client down), and this is the same guard at the second door.

A RUN'S ANSWERS ARE A COLD CACHE'S, WHATEVER THE CACHE HOLDS. The cache file
outlives the run (the monthly build restores the last one), so "whoever asked
first" can be a point of an earlier run's graph that sat in another pixel.
Monthly run 30 (refresh-reference.yml 37772454847) answered all 22,000,918 of
its points from a cache earlier runs wrote ("0 read from tiles"), and its
parity, today's exporters on a cold cache, differed on 121 edges' profiles and
11 edges' climbs. Those edges' samples, placed by
export_network_elevation.edge_sample_points on the run's own
trail_graph_geometry.json and read cold on 2026-10-08, differ from what the
build published at 133 samples, and at every one the cache key's box crosses a
3DEP pixel edge and the published value is the other pixel's: up to 19 ft on
one sample and 15 ft on one edge's gain, in both directions (Measured). So
after the sampler answers, reread_where_the_cache_could_answer_another_point()
reads again, with no cache, every point whose key another point could have
answered from a different pixel, once per key at this run's first point under
it: the point a cold run reads that key at. Every other point has one answer
whoever asked first. On those 123 edges could_be_answered_for_another_point()
names 928 of 18,808 points, 4.9%, all 133 among them (Measured); a key reaches
2e-6 degrees across against a pixel of 1/10800, about 2% on each axis
(Reasoned).
"""

from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import NamedTuple

import duckdb
import numpy as np
import rasterio
from pyproj import Transformer

import export_elevation

ROOT = Path(__file__).parent
WAREHOUSE_PATH = ROOT / "data" / "warehouse.duckdb"
SAMPLE_POINTS = "intermediate.int_elevation__dem_points"
SCHEMA = "derived"
TABLE = "dem_samples"

#: How far apart, on each axis, two points can be and still share a sample cache key: export_elevation._cache_key
#: writes each coordinate at CACHE_KEY_DECIMALS, so two points under one key are under one unit of the last decimal
#: apart. A nanodegree more, so that the last bit of a double cannot carry one past it.
KEY_REACH_DEG = 10.0**-export_elevation.CACHE_KEY_DECIMALS + 1e-9

#: How many tile headers are read at once to learn each tile's grid. A header is a range read or two; this is
#: export_elevation.DEFAULT_TILE_WORKERS's reasoning (waiting, not arithmetic) at its value.
GRID_WORKERS = export_elevation.DEFAULT_TILE_WORKERS


class SamplePoint(NamedTuple):
    line_id: str
    sample_index: int
    lon: float
    lat: float


def _tile_grid(source) -> tuple:
    """A tile's CRS, transform, width and height, read from its header as the sampler opens it."""
    with rasterio.Env(**export_elevation.GDAL_READ_OPTIONS):
        with rasterio.open(source) as tile:
            return tile.crs, tile.transform, tile.width, tile.height


def _tile_grids(sources: list) -> list[tuple]:
    """Each tile's grid, GRID_WORKERS headers at a time, and any header whose read failed read again on its own.

    WHY THE SECOND TRY. From this sandbox's proxy, 2 to 4 of 8 real 3DEP headers opened side by side failed as
    "not recognized as being in a supported file format", one of them on an S3 404 for a tile that exists, and all 8
    opened one at a time (measured 2026-10-08). Whether a runner does that is unmeasured. A header that fails alone
    as well raises, as the sampler's own read of that tile would."""

    def first_try(source):
        try:
            return _tile_grid(source)
        except rasterio.errors.RasterioIOError:
            return None

    with ThreadPoolExecutor(max_workers=max(1, min(GRID_WORKERS, len(sources)))) as pool:
        grids = list(pool.map(first_try, sources))
    return [grid if grid is not None else _tile_grid(source) for source, grid in zip(sources, grids)]


def _one_pixel(lons: np.ndarray, lats: np.ndarray, grid: tuple) -> np.ndarray:
    """Whether the square of half-side KEY_REACH_DEG around each point lies in one pixel of this grid.

    Its four corners are placed as ElevationSampler._read_tile places a point: into the tile's CRS, through the
    inverse of its transform, floored and held to the raster. A corner with no finite place is not in one pixel."""
    crs, transform, width, height = grid
    reach = KEY_REACH_DEG
    corner_lons = np.concatenate((lons - reach, lons + reach, lons - reach, lons + reach))
    corner_lats = np.concatenate((lats - reach, lats - reach, lats + reach, lats + reach))
    xs, ys = Transformer.from_crs(export_elevation.GEOGRAPHIC_CRS, crs.to_wkt(), always_xy=True).transform(
        corner_lons, corner_lats
    )
    cols_f, rows_f = ~transform * (np.asarray(xs, dtype=float), np.asarray(ys, dtype=float))
    placed = (np.isfinite(cols_f) & np.isfinite(rows_f)).reshape(4, -1).all(axis=0)
    cols = np.clip(np.floor(np.where(np.isfinite(cols_f), cols_f, 0.0)), 0, width - 1).reshape(4, -1)
    rows = np.clip(np.floor(np.where(np.isfinite(rows_f), rows_f, 0.0)), 0, height - 1).reshape(4, -1)
    return placed & (cols == cols[0]).all(axis=0) & (rows == rows[0]).all(axis=0)


def could_be_answered_for_another_point(points: list[SamplePoint], tile_index: list) -> np.ndarray:
    """Whether another point under the same cache key could have been answered with a different value: True where
    the square of half-side KEY_REACH_DEG around the point crosses an edge of any indexed tile's bounds, or spans
    more than one pixel of a tile that holds it.

    Every point under one key lies in that square around each of them, so a point this calls False has one answer
    whoever asked its key first: every tile that covers the square covers all of it, in one pixel, and the sampler's
    fall-through visits the same tiles in the same order for each of them (Reasoned from _read_points and
    _read_tile). True is conservative and costs one read: a key whose points all read one pixel reads it again."""
    flagged = np.zeros(len(points), dtype=bool)
    if not points or not tile_index:
        return flagged
    lons = np.fromiter((point.lon for point in points), dtype=float, count=len(points))
    lats = np.fromiter((point.lat for point in points), dtype=float, count=len(points))
    by_lon = np.argsort(lons, kind="stable")
    sorted_lons = lons[by_lon]
    reach = KEY_REACH_DEG
    reached = []
    for source, (xmin, ymin, xmax, ymax) in tile_index:
        near = by_lon[np.searchsorted(sorted_lons, xmin - reach, "left") : np.searchsorted(sorted_lons, xmax + reach, "right")]
        near = near[(lats[near] + reach >= ymin) & (lats[near] - reach <= ymax)]
        if len(near):
            reached.append((source, (xmin, ymin, xmax, ymax), near))
    grids = _tile_grids([source for source, _bounds, _near in reached])
    for (_source, (xmin, ymin, xmax, ymax), near), grid in zip(reached, grids):
        inside = (lons[near] - reach >= xmin) & (lons[near] + reach <= xmax)
        inside &= (lats[near] - reach >= ymin) & (lats[near] + reach <= ymax)
        flagged[near[~inside]] = True
        held = near[inside]
        flagged[held[~_one_pixel(lons[held], lats[held], grid)]] = True
    return flagged


def reread_where_the_cache_could_answer_another_point(
    points: list[SamplePoint], elevations: list[float | None], index_path: Path
) -> tuple[list[float | None], int, int]:
    """`elevations` with every point could_be_answered_for_another_point() names read again from the tiles, with no
    cache, at the first point in ask order under its key, which is the point a cold cache reads that key at. Returns
    the answers, how many points were read again and under how many keys."""
    tile_index = export_elevation.index_elevation_tiles(index_path)
    flagged = np.flatnonzero(could_be_answered_for_another_point(points, tile_index)).tolist()
    if not flagged:
        return elevations, 0, 0
    keys = [export_elevation._cache_key(points[i].lon, points[i].lat) for i in flagged]
    first: dict[str, int] = {}
    for i, key in zip(flagged, keys):
        first.setdefault(key, i)
    sampler = export_elevation.ElevationSampler(tile_index, cache_path=None)
    try:
        values = sampler.sample_many([(points[i].lon, points[i].lat) for i in first.values()])
    finally:
        sampler.close()
    answers = dict(zip(first, values))
    reread = list(elevations)
    for i, key in zip(flagged, keys):
        reread[i] = answers[key]
    return reread, len(flagged), len(first)


def read_sample_points(con: duckdb.DuckDBPyConnection, relation: str = SAMPLE_POINTS) -> list[SamplePoint]:
    """Every row of the DEM-point intermediate, in the order the DEM is asked about them: the A.T. first."""
    try:
        rows = con.execute(f"select line_id, sample_index, lon, lat from {relation} order by ask_order").fetchall()
    except duckdb.CatalogException as missing:
        raise SystemExit(
            f"{relation} is not in the warehouse: build it with dbt first (everything but "
            f"`source:derived+`), then run this step, then build `source:derived+`. ({missing})"
        ) from missing
    return [SamplePoint(*row) for row in rows]


def sample_elevations(points: list[SamplePoint], index_path: Path) -> list[float | None]:
    """The DEM's answer at each point, from the sampler export_elevation.build_profile reads the DEM with, and at
    every point the cache could have answered from another point's pixel, the answer a cold cache gives (the header's
    "A RUN'S ANSWERS ARE A COLD CACHE'S")."""
    sampler = export_elevation.ElevationSampler.for_index(index_path)
    try:
        elevations = sampler.sample_many([(point.lon, point.lat) for point in points])
    finally:
        sampler.close()
    # The cache it holds is one entry per key of every run before (16,824,060 in monthly run 30), and nothing below
    # reads it.
    del sampler
    elevations, reread, keys = reread_where_the_cache_could_answer_another_point(points, elevations, index_path)
    print(
        f"  Read again with no cache: {reread:,} point(s) under {keys:,} key(s) whose cached answer could be another "
        "point's pixel."
    )
    for point, value in zip(points, elevations):
        # The cache's own test of a stored value: None, or a finite number that is not a bool.
        if not export_elevation._is_a_stored_sample(value):
            raise SystemExit(f"the sampler answered {value!r} at {point}: an elevation is a finite number or None")
    return elevations


def point_geojson(point: SamplePoint) -> str:
    """The point as GeoJSON text. json.dumps writes each double at the shortest length that reads back to it."""
    return json.dumps({"type": "Point", "coordinates": [point.lon, point.lat]})


def write_dem_samples(
    con: duckdb.DuckDBPyConnection, points: list[SamplePoint], elevations: list[float | None], loaded_at: datetime
) -> int:
    """Replace derived.dem_samples with one row per point. Returns the row count.

    A null elevation goes in as NULL through its own mask, never as a NaN
    placeholder: DuckDB stores a NaN as a double, and a double is an
    elevation to everything that reads the table."""
    if len(points) != len(elevations):
        raise ValueError(f"{len(points)} points and {len(elevations)} elevations")
    con.register(
        "_dem_samples_src",
        {
            "line_id": np.array([point.line_id for point in points], dtype=object),
            "sample_index": np.array([point.sample_index for point in points], dtype=np.int64),
            "geometry": np.array([point_geojson(point) for point in points], dtype=object),
            "elevation_m": np.array([0.0 if value is None else value for value in elevations], dtype=np.float64),
            "has_elevation": np.array([value is not None for value in elevations], dtype=bool),
        },
    )
    try:
        con.execute(f"create schema if not exists {SCHEMA}")
        con.execute(f"""
            create or replace table {SCHEMA}.{TABLE} as
            select
                cast(line_id as varchar) as line_id,
                cast(sample_index as integer) as sample_index,
                cast(geometry as varchar) as geometry,
                case when has_elevation then elevation_m end as elevation_m,
                cast('{loaded_at.isoformat()}' as timestamptz) as _loaded_at
            from _dem_samples_src
        """)
    finally:
        con.unregister("_dem_samples_src")
    return con.execute(f"select count(*) from {SCHEMA}.{TABLE}").fetchone()[0]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--warehouse", type=Path, default=WAREHOUSE_PATH)
    parser.add_argument(
        "--index", type=Path, default=export_elevation.ELEVATION_INDEX_PATH, help="fetch_elevation.py's tile index"
    )
    args = parser.parse_args(argv)

    with duckdb.connect(str(args.warehouse)) as con:
        points = read_sample_points(con)
        elevations = sample_elevations(points, args.index)
        written = write_dem_samples(con, points, elevations, datetime.now(UTC))
    gaps = sum(1 for value in elevations if value is None)
    print(f"{SCHEMA}.{TABLE}: {written:,} sample points, {gaps:,} with no DEM answer, from {args.index}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
