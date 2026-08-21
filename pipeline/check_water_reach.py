"""Ask of finished output the question `build_osm_water_reach.py` asks of
candidates: is every published OSM water point somewhere a hiker walks (#916)?

#749 put a gate between OSM's fourteen-state scan and a hiker's screen, and
`export_poi.py` refuses to run without its verdicts. That gate is real and it
works - but it can only ever check its own belief about its own run, which is
the same limitation `check_output_quality.py`'s docstring names as the reason
that module exists. Nothing looked at what actually landed, and nothing at all
looked at what the bucket was still serving.

That second gap is the one that bit. Measured 2026-08-21 against the live
`data.ourhike.org` (`latest.json` version `7c100329…`, release `2026-08-18`),
whose `poi_water.geojson` hashes to what that manifest promises:

    1,535 published osm_water points
      120 of them within the 100 ft gate
    1,343 further than 0.2 mi from anything a hiker walks
    1,159 further than five miles, the farthest 29.9 mi - drinking
          fountains in Manhattan, at the 30-mile corridor's edge

Production's root keys had not been rewritten since before the gate landed on
`main`, so the bucket was serving the pre-#749 layer while every check in this
repository stayed green. `check_output_quality.py` re-derives completeness,
corridor agreement and count drops and asks nothing about where a water point
is; `smoke_published.py` checks headers, ranges, sha256 and PMTiles structure,
and a pin thirty miles off the trail is byte-perfect.

WHAT THIS CHECKS, AND WHAT IT DELIBERATELY DOES NOT

The **distance** half of the gate only: every `osm_water` feature within
`MATCH_RADIUS_FT` of the nearest of the centerline, any side trail, any shelter
or any campsite - the union, on `fetch_trail_water.py`'s own constant, imported
rather than restated so a re-tune cannot move the gate without moving its
checker. A checker that disagreed with the gate would be a second opinion, not
a check.

The **grade** half is left out on purpose. Re-deriving it needs USGS EPQS
elevations for both ends of every walk, which is a network dependency neither a
pre-publish gate nor a weekly smoke run should take on, and its absence is
stated here rather than papered over: a point this check passes is a point that
cleared the distance gate, not a point proven reachable. The distance half is
the half that separates a spring from a fountain in Manhattan.

It is also **not** an independent re-implementation of the gate's geometry - it
is the same DuckDB `ST_Distance` in a different code path, run against output
rather than against in-memory state. What makes it worth running is the input,
not the arithmetic: it reads the file that was actually written, or the bytes
the bucket actually serves.

MEASURING AGAINST EXPORTED GEOMETRY COSTS UP TO ONE METRE, AND THAT IS WHY
`tolerance_m` EXISTS

Two callers, two shapes of input. `check_output_quality.py` measures against
`data/raw/`, the very layers the gate used, and passes no tolerance. A caller
measuring against the published `trails.geojson` is measuring against geometry
`export_trails.py` has simplified to `DEFAULT_SIMPLIFY_TOLERANCE_M`, and
Douglas-Peucker keeps the simplified line within that distance of the original
- so the same distance can read up to a metre differently there. `tolerance_m`
is that bound, imported from the module that decides it, and it is a property
of the simplification rather than slack anybody chose. At a 30.48 m gate it
moves nothing that is not already borderline, and a borderline flag prints its
own distance so a reader can see which it was.

Run it by hand against either shape:

    python check_water_reach.py                      # data/processed vs data/raw
    python check_water_reach.py --base https://data.ourhike.org
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

import duckdb

from export_trails import DEFAULT_SIMPLIFY_TOLERANCE_M
from fetch_trail_water import M_PER_FT, MATCH_RADIUS_FT
from lib.corridor import GEOGRAPHIC_CRS, PROJECTED_CRS

ROOT = Path(__file__).parent
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"

#: The gate, in metres. `fetch_trail_water.py`'s foot figure is the one home.
MATCH_RADIUS_M = MATCH_RADIUS_FT * M_PER_FT

#: What a caller measuring against the PUBLISHED trails layer passes as
#: `tolerance_m` - see this module's docstring.
#:
#: It lives here rather than at that call site because it is a fact about the
#: geometry, not a decision the caller gets to make: `export_trails.py`
#: simplifies to `DEFAULT_SIMPLIFY_TOLERANCE_M` and Douglas-Peucker keeps the
#: result within that distance of the original, so a distance measured against
#: the export can differ from the same distance against `data/raw/` by at most
#: that much. Imported from the module that decides it, so re-tuning the
#: simplification moves this with it.
SIMPLIFIED_TRAILS_TOLERANCE_M = DEFAULT_SIMPLIFY_TOLERANCE_M

#: The source whose points this checks. Every other water source on the map
#: arrives through a path with its own geography - opentrail's points are
#: trail-side by construction, `atc_csi`'s are synthesized at a site's own
#: coordinates, and `nhd_stream`'s already passed both of these gates in
#: `fetch_trail_water.py`. Only OSM's scan is corridor-wide.
OSM_WATER_SOURCE = "osm_water"

#: How far out a distance is measured before the answer is simply "far".
#:
#: NOT a second gate - a reporting ceiling, and the range join's prefilter, in
#: `build_osm_water_reach.py`'s shape and for its reason. The gate binds at
#: 30.48 m; a reader deciding whether a flagged point is a borderline
#: measurement or a fountain in a town park needs the exact figure near the
#: gate and needs nothing at all past a mile. One mile is ~53x the gate.
MEASURE_CEILING_M = 1609.344

TOO_FAR = "{poi_id}: {distance} from the nearest trail, side trail, shelter or campsite - the gate is {radius:.0f} ft"
BEYOND_CEILING = f"further than {MEASURE_CEILING_M / 1609.344:.0f} mi"

#: How many offenders a report spells out in full. The failure this exists to
#: catch produced 1,415 of them at once, and a list that long buries its own
#: finding; the count is always exact and the worst are always named.
MAX_NAMED = 10


def osm_water_points(water_path: Path) -> list[dict]:
    """Every `osm_water` feature in a published or processed water layer, as
    `{"id", "lon", "lat"}`.

    Read in Python rather than through `ST_Read` because the filter is on a
    property and the file is ~1.3 MB: doing it here keeps the check honest
    about which features it looked at even if the GeoJSON's property columns
    ever change shape, and a source name that stops matching shows up as "0
    points checked" rather than as a passing run.
    """
    document = json.loads(water_path.read_text(encoding="utf-8"))
    points = []
    for feature in document.get("features") or []:
        properties = feature.get("properties") or {}
        if properties.get("source") != OSM_WATER_SOURCE:
            continue
        geometry = feature.get("geometry") or {}
        coordinates = geometry.get("coordinates") or []
        if geometry.get("type") != "Point" or len(coordinates) < 2:
            # A water feature with no point is not this check's finding to
            # report - export_poi.py's own geometry guard counts those, and a
            # second voice saying it here would double-report one upstream row.
            continue
        points.append({"id": properties.get("id"), "lon": coordinates[0], "lat": coordinates[1]})
    return points


def _load_union(con: duckdb.DuckDBPyConnection, table: str, paths: Sequence[Path]) -> int:
    """One projected geometry table from several GeoJSON layers.

    Missing paths are skipped rather than raised on, and the returned count is
    what makes that safe to do: a caller that reads zero features from the
    layers it named gets a PROBLEM out of `check_reach`, not a pass measured
    against nothing.
    """
    present = [path for path in paths if path.exists()]
    if not present:
        con.execute(f"CREATE OR REPLACE TABLE {table} (g GEOMETRY)")
        return 0
    selects = [
        f"""
            SELECT ST_Transform(geom, '{GEOGRAPHIC_CRS}', '{PROJECTED_CRS}', always_xy := true) AS g
            FROM ST_Read('{path.as_posix()}')
        """
        for path in present
    ]
    con.execute(f"CREATE OR REPLACE TABLE {table} AS {' UNION ALL '.join(selects)}")
    return con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]


def measure(
    con: duckdb.DuckDBPyConnection,
    points: Sequence[dict],
    line_paths: Sequence[Path],
    site_paths: Sequence[Path],
) -> tuple[list[dict], int]:
    """Each point's distance in metres to the nearest of the union, capped at
    `MEASURE_CEILING_M`, plus how many features the union actually held.

    `nearest_m` is None for a point with nothing inside the ceiling. That is
    not a failure to measure - it is the answer, and the one the 1,159 points
    past five miles all give.
    """
    n_features = _load_union(con, "reach_lines", line_paths) + _load_union(con, "reach_sites", site_paths)
    if not points:
        return [], n_features

    con.execute("CREATE OR REPLACE TABLE water_points (poi_id VARCHAR, lon DOUBLE, lat DOUBLE)")
    con.executemany(
        "INSERT INTO water_points VALUES (?, ?, ?)",
        [(str(point["id"]), point["lon"], point["lat"]) for point in points],
    )
    con.execute(f"""
        CREATE OR REPLACE TABLE water_projected AS
        SELECT poi_id,
               ST_Transform(ST_Point(lon, lat), '{GEOGRAPHIC_CRS}', '{PROJECTED_CRS}', always_xy := true) AS g
        FROM water_points
    """)

    rows = con.execute(f"""
        WITH candidates AS (
            SELECT w.poi_id, ST_Distance(w.g, r.g) AS d
            FROM water_projected w, (SELECT g FROM reach_lines UNION ALL SELECT g FROM reach_sites) r
            WHERE ST_DWithin(w.g, r.g, {MEASURE_CEILING_M})
        )
        SELECT w.poi_id, MIN(c.d) AS nearest_m
        FROM water_projected w LEFT JOIN candidates c USING (poi_id)
        GROUP BY 1
    """).fetchall()

    nearest = {row[0]: row[1] for row in rows}
    return [{**point, "nearest_m": nearest.get(str(point["id"]))} for point in points], n_features


def describe(nearest_m: float | None) -> str:
    """A distance a reader can act on. Feet near the gate, where the argument
    is about the gate; miles once it is plainly not."""
    if nearest_m is None:
        return BEYOND_CEILING
    if nearest_m < 4 * MATCH_RADIUS_M:
        return f"{nearest_m / M_PER_FT:.0f} ft"
    return f"{nearest_m / 1609.344:.1f} mi"


def check_reach(
    water_path: Path,
    line_paths: Sequence[Path],
    site_paths: Sequence[Path],
    tolerance_m: float = 0.0,
    con: duckdb.DuckDBPyConnection | None = None,
) -> dict:
    """The whole check, as `{"problems", "checked", "past_gate", "worst"}`.

    `problems` is empty exactly when every `osm_water` point in `water_path`
    is inside `MATCH_RADIUS_M + tolerance_m` of the union. Raises nothing that
    a caller has to catch for correctness - both callers wrap it anyway,
    because a gate in front of publishing must never read as "nothing to
    report" because it crashed.
    """
    if not water_path.exists():
        return {"problems": [f"{water_path.name} is missing - nothing to check"], "checked": 0, "past_gate": [], "worst": None}

    points = osm_water_points(water_path)
    if not points:
        # Nothing to check, so nothing to measure against, so the empty-union
        # finding below would be an alarm about geometry this call never
        # needed. The normal state of every release before #529 added the
        # source, and of any run that did not fetch it.
        return {"problems": [], "checked": 0, "past_gate": [], "worst": None}

    owned = con is None
    con = con or duckdb.connect()
    try:
        if owned:
            con.execute("INSTALL spatial; LOAD spatial;")
        measured, n_features = measure(con, points, line_paths, site_paths)
    finally:
        if owned:
            con.close()

    if not n_features:
        # Measuring against an empty union would pass every point that is
        # already flagged and fail every point that is not - which is to say it
        # would report the opposite of the truth. The layers being absent is
        # the finding.
        named = ", ".join(path.name for path in [*line_paths, *site_paths])
        return {
            "problems": [f"no trail, shelter or campsite geometry loaded from {named} - the check measured against nothing"],
            "checked": len(points),
            "past_gate": [],
            "worst": None,
        }

    limit = MATCH_RADIUS_M + tolerance_m
    past_gate = [row for row in measured if row["nearest_m"] is None or row["nearest_m"] > limit]
    # None sorts last on purpose: a point with nothing inside the ceiling is
    # further than any point that has a number, so "worst first" puts it first.
    past_gate.sort(key=lambda row: (row["nearest_m"] is not None, -(row["nearest_m"] or 0.0)))

    problems = [
        TOO_FAR.format(poi_id=row["id"], distance=describe(row["nearest_m"]), radius=MATCH_RADIUS_FT)
        for row in past_gate[:MAX_NAMED]
    ]
    if len(past_gate) > MAX_NAMED:
        problems.append(f"... and {len(past_gate) - MAX_NAMED} more of {len(measured)} osm_water points past the gate")

    return {
        "problems": problems,
        "checked": len(measured),
        "past_gate": past_gate,
        # The first element after the sort above, described - so a caller with
        # room for one line says "29.9 mi" rather than "1,415 problems".
        "worst": describe(past_gate[0]["nearest_m"]) if past_gate else None,
    }


def processed_paths() -> tuple[Path, list[Path], list[Path]]:
    """What a pre-publish run measures: the water layer this run just wrote,
    against the raw layers the gate itself read. Not the exported trails -
    those are simplified, and there is no reason to accept a metre of slack
    when the originals are on the same disk."""
    return (
        PROCESSED_DIR / "poi" / "water.geojson",
        [RAW_DIR / "centerline.geojson", RAW_DIR / "side_trails.geojson"],
        [RAW_DIR / "shelters.geojson", RAW_DIR / "campsites.geojson"],
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--water", type=Path, help="water layer to check (default: this run's data/processed one)")
    args = parser.parse_args([] if argv is None else argv)

    water_path, line_paths, site_paths = processed_paths()
    if args.water is not None:
        water_path = args.water

    result = check_reach(water_path, line_paths, site_paths)
    print(f"{result['checked']} osm_water point(s) checked against the {MATCH_RADIUS_FT:.0f} ft union gate.")
    for problem in result["problems"]:
        print(f"  {problem}")
    if not result["problems"]:
        print("  every one of them is inside the gate.")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
