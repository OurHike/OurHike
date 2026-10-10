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

EVERY POINT IS ANSWERED AT ITS OWN POINT, whatever the cache beside the index
holds and whoever asked first. Since decision 115 the sampler keys its cache
on each point's exact coordinates (export_elevation.SAMPLE_CACHE_KEYS), the
same rule today's three exporters read under, so a cached answer is the DEM's
at the point asked, and a run's answers are a cold run's. The questions go in
int_elevation__dem_points' ask_order, today's exporters' order (the A.T.'s
walk, every sample included, then each edge by its edge_index from its
start), which decides no answer now; export_network_profile.py asks the edge
points again and is answered from the cache, so one question serves both.

UNTIL DECISION 115 IT WAS NOT. The cache keyed a point to 6 decimals and gave
every point under a key the pixel of the first one asked, and the file
outlives the run (the monthly build restores the last one). Monthly run 30
(refresh-reference.yml 37772454847) answered all 22,000,918 of its points from
a cache earlier runs wrote ("0 read from tiles"), and its parity, today's
exporters on a cold cache, differed on 121 edges' profiles and 11 edges'
climbs: 133 samples carried the neighbouring 3DEP pixel's value, up to 19 ft
on one sample and 15 ft on one edge's gain, in both directions (Measured
2026-10-08, by reading those samples cold). Commit 38467bc7 made this step
read again, with no cache, every point whose 6-decimal key could hold another
pixel (928 of those edges' 18,808 points). Under an exact key no point can be
answered for another, so that re-read had nothing left to catch and is gone:
both lanes now keep one rule, in one place.

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
SAMPLE_POINTS = "intermediate.int_elevation__dem_points"
SCHEMA = "derived"
TABLE = "dem_samples"


class SamplePoint(NamedTuple):
    line_id: str
    sample_index: int
    lon: float
    lat: float


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
    """The DEM's answer at each point, from the sampler export_elevation.build_profile reads the DEM with: through
    the cache beside the index, which answers a point only with what was read at that same point (the header's
    "EVERY POINT IS ANSWERED AT ITS OWN POINT")."""
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
