"""step_dem_sampling: the DEM's elevation at every elevation sample point, written to derived.dem_samples for dbt to read back.

    python step_dem_sampling.py [--warehouse data/warehouse.duckdb] [--index data/raw/elevation/tile_index.json]

pipeline/ELT.md, "Python steps, outside dbt", is the design, and EL06 of its
ledger the rule: DEM pixels never enter DuckDB. Sampling USGS 3DEP's rasters
stays Python because DuckDB has nothing fast and right for it - the `raster`
extension measured about 50x slower (200 s against 4.1 s for 1,000,000
points) and `raquet` wrong at 736 of 2,000 points, by up to 3.0 m
(pipeline/DBT.md:35-48, measured 2026-09-24). Everything else about the
profile is SQL: where the samples sit and their miles
(int_elevation__sample_points), the clip, the seams and the rounding
(int_elevation__profile).

THE STEP, between two dbt invocations:
1. dbt builds int_elevation__sample_points (and everything not downstream of
   the `derived` source);
2. this reads every row of it, in (line_id, sample_index) order, and hands
   the points to export_elevation.ElevationSampler.for_index(index).
   sample_many - the sampler and the call export_elevation.build_profile makes
   today, reused rather than reimplemented: the same tile index, the same
   nearest-neighbour read in each tile's own grid, the same nodata and
   non-finite -> None rule, the same per-point cache beside the index;
3. it writes one row per sample point to derived.dem_samples, the point as
   GeoJSON text beside the elevation, so int_elevation__profile can refuse an
   elevation that was not read at its own sample's point;
4. dbt builds everything downstream of the `derived` source.

THE SAME QUESTIONS IN THE SAME ORDER. For the A.T. that is the walk's order,
every sample included - also the ones int_elevation__profile drops where two
pieces cover the same miles - because build_profile reads the DEM at all of
them in that order, and the sampler's cache answers a second point within
0.11 m of a first with the first's pixel ("whoever asked first",
export_elevation.CACHE_KEY_DECIMALS). A line added to
int_elevation__sample_points later (the trail network's edges) sorts after or
before 'AT' by its line_id, which decides who asks first between lines;
today's exporters run the A.T. first.

A value the sampler hands back is None or a finite float, and a value that is
neither stops the step rather than reaching the table: the sampler already
refuses NaN and infinity (#659 - a literal NaN in the profile artifact takes
the client down), and this is the same guard at the second door.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import NamedTuple

import duckdb
import numpy as np

import export_elevation

ROOT = Path(__file__).parent
WAREHOUSE_PATH = ROOT / "data" / "warehouse.duckdb"
SAMPLE_POINTS = "intermediate.int_elevation__sample_points"
SCHEMA = "derived"
TABLE = "dem_samples"


class SamplePoint(NamedTuple):
    line_id: str
    sample_index: int
    lon: float
    lat: float


def read_sample_points(con: duckdb.DuckDBPyConnection, relation: str = SAMPLE_POINTS) -> list[SamplePoint]:
    """Every row of the sample-point intermediate, in the order the DEM is asked about them."""
    try:
        rows = con.execute(f"select line_id, sample_index, lon, lat from {relation} order by line_id, sample_index").fetchall()
    except duckdb.CatalogException as missing:
        raise SystemExit(
            f"{relation} is not in the warehouse: build it with dbt first (everything but "
            f"`source:derived+`), then run this step, then build `source:derived+`. ({missing})"
        ) from missing
    return [SamplePoint(*row) for row in rows]


def sample_elevations(points: list[SamplePoint], index_path: Path) -> list[float | None]:
    """The DEM's answer at each point, from the sampler export_elevation.build_profile reads the DEM with."""
    sampler = export_elevation.ElevationSampler.for_index(index_path)
    try:
        elevations = sampler.sample_many([(point.lon, point.lat) for point in points])
    finally:
        sampler.close()
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
