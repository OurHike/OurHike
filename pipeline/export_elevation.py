"""Export a dense along-the-trail elevation profile from USGS 3DEP 1/3
arc-second (~10m) DEM tiles, read REMOTELY (see fetch_elevation.py - nothing
is downloaded; the tiles are Cloud-Optimized GeoTIFFs and only the blocks the
trail crosses are fetched), sampled every
SAMPLE_INTERVAL_METERS along the REAL centerline geometry - not just at the
existing 4,395 half-mile markers (data/raw/half_mile_points_from_springer.
geojson, README.md: ~2 points/mile). ROADMAP.md's elevation line names the
exact reason this exists: sparse half-mile-marker sampling under-counts real
gain/loss, the same failure mode other hiking apps' sparse sampling has.

Pipeline, mirroring patterns already established elsewhere in this repo:
1. Merge the real centerline.geojson's 3,025 raw segments via
   ST_LineMerge(ST_Union_Agg(...)) - the same DuckDB spatial primitives
   spike_corridor.py/export_poi.py/export_trails.py already use. Real-data
   gotcha (confirmed 2026-07-28): this does NOT collapse to one connected
   LineString - it merges into 558 separate pieces (114 of them under ~10m
   long), because real segment endpoints don't always touch exactly.
2. Since centerline.geojson carries no explicit trail-sequence field,
   ordered_oriented_parts() first puts those disconnected pieces into a
   rough south-to-north order using a straight Springer->Katahdin axis, and
   then - because #652 measured that approximation misplacing 18 stretches
   by more than ten miles - calibrate_parts_to_markers() re-orders,
   re-orients and re-scales every piece against ATC's own
   half_mile_points_from_springer `Measure` field, the one trail-sequence
   field the source data has. distance_mi is therefore ATC's own NOBO mile
   scale, held to it by a held-out accuracy gate (require_marker_agreement)
   on every run. See ORDERING.md for the measurements behind both halves.
3. Each ordered piece is reprojected to EPSG:5070 (NAD83 / Conus Albers -
   meters, the same CONUS-wide equal-distance choice spike_corridor.py/
   export_poi.py/export_trails.py already use) so shapely's .interpolate()
   walks real distance, not degrees - and so always_xy := true is needed on
   both transform legs (see README.md's "Gotcha hit and fixed" note:
   without it ST_Transform silently swaps lat/lon instead of erroring).
4. sample_points_along_parts() walks the ordered, reprojected pieces end to
   end, placing one sample point every SAMPLE_INTERVAL_METERS of cumulative
   distance. Known limitation: where two pieces are genuinely disconnected,
   the interval carries straight across that gap as if the pieces touched,
   rather than adding the real (unmeasured) gap distance - a bounded
   approximation worth naming plainly, not a crash risk.
   measure_cross_part_gaps() quantifies (never corrects) that same gap
   distance - main() logs the total and largest single gap so the size of
   the approximation is visible run-over-run, not just described in prose
   here.

   **Every sample records the piece it came from, and the first sample of
   each piece is written with `part_start: true` (#559).** Naming the seam
   is not decoration: because the distance axis carries straight across it,
   the step from the last sample of one piece into the first of the next
   looks exactly like terrain to anything reading elevations alone, and
   summing those steps put ~36,800 ft of climbing that nobody did into the
   published total - the largest a single +2,588 ft "step" across 25 m of
   ground. lib/elevation_gain.py and client/src/lib/elevationGain.ts both
   break their runs on it. A profile written before this existed carries no
   markers and is measured as it always was, which is the only honest
   reading of a file that does not say where its seams are.

   The ORDERING of the pieces was a separate, open problem (#652) until the
   marker calibration above closed it - ORDERING.md records what the source
   geometry actually looks like, why the graph-walking fixes failed, and
   why calibrating to ATC's markers is the one that worked. Marking the
   seams is independent of it and stays correct regardless.
5. Each sample point is reprojected back to lon/lat and looked up against
   the indexed DEM tiles via ElevationSampler, which reprojects each
   tile (see fetch_elevation.py's
   docstring) to EPSG:4326 via a WarpedVRT, mirroring spike_raster_mosaic.py's
   per-quad WarpedVRT reprojection but "mosaic"-ing at the scale of a single
   point lookup rather than materializing a merged raster array (see that
   class's docstring for why that's the right "lighter scale" here). A point
   no indexed tile covers - a real DEM coverage gap - gets a null
   elevation, not a crash; it's kept in the output (not dropped) so the
   distance axis a client-side chart draws from stays continuous. main()
   counts what fraction of a run's points land null so a coverage
   regression is visible in elevation_manifest.json, not just noticed by
   eye.

Output: a compact JSON array of {distance_mi, elevation_ft} records, sorted
by distance (guaranteed by construction), to data/processed/
elevation_profile.json, with a SHA256 content hash and DEM-null-coverage
counts (null_elevation_count, null_elevation_pct) in data/processed/
elevation_manifest.json - matching export_trails.py's flat single-artifact
manifest shape (this module has exactly one output artifact, unlike
export_poi.py's per-poi_type or export_trails.py's geojson+fgb pair).

Intentionally manual-only (see TESTING.md): a full corridor run streams from
110 remote DEM tiles and takes roughly 25 minutes, mirroring
fetch_topo_quads.py + spike_raster_mosaic.py's own real-data verification
being a documented manual procedure, not a pytest case.
"""

import hashlib
import json
import math
from pathlib import Path
from typing import NamedTuple

import duckdb
import numpy as np
import rasterio
from rasterio.vrt import WarpedVRT
from rasterio.windows import Window
from shapely import wkt as shapely_wkt
from shapely.geometry import LineString, MultiLineString, Point
from shapely.strtree import STRtree

from lib.elevation_gain import (
    DEFAULT_THRESHOLD_FT,
    DEFAULT_THRESHOLD_M,
    cumulative_gain_over_gaps,
    raw_cumulative_gain,
)

ROOT = Path(__file__).parent
CENTERLINE_PATH = ROOT / "data" / "raw" / "centerline.geojson"
MARKERS_PATH = ROOT / "data" / "raw" / "half_mile_points_from_springer.geojson"
ELEVATION_INDEX_PATH = ROOT / "data" / "raw" / "elevation" / "tile_index.json"
OUT_PATH = ROOT / "data" / "processed" / "elevation_profile.json"
MANIFEST_PATH = ROOT / "data" / "processed" / "elevation_manifest.json"

# Same CRS choice as spike_corridor.py/export_poi.py/export_trails.py, for
# the same reason: EPSG:5070 (NAD83 / Conus Albers) is equal-area, meters,
# and appropriate for a CONUS-spanning distance calculation.
GEOGRAPHIC_CRS = "EPSG:4326"
PROJECTED_CRS = "EPSG:5070"

METERS_PER_MILE = 1609.344
METERS_PER_FOOT = 0.3048

# 50m intervals -> ~32.2 points/mile, vs. the real half-mile markers' ~2
# points/mile (README.md: 4,395 markers / 2,190 miles) - a >15x density
# increase. Chosen at 25m (tightened from 50m on 2026-07-29) - roughly
# 2.5x the source DEM's ~10m posting, which is about as dense as sampling
# can usefully get.
#
# There is a real ceiling here, and it is worth stating because "more
# samples" sounds strictly better and is not. Cumulative ascent sums every
# |delta elevation| along the line, so it accumulates EVERYTHING: DEM noise,
# vegetation artifacts, and the fact that the centerline sits a few metres
# from the real tread. Sample far below the DEM's own resolution and those
# errors compound into fake climbing - which is why hiking apps disagree so
# wildly on "total gain" for the same trail. Since that figure feeds the
# Naismith time estimate directly, an inflated one is not a cosmetic
# problem.
#
# 25m is dense enough to catch switchbacks and steep pitches the old 50m
# spacing smoothed over (the under-counting ROADMAP.md's elevation line
# exists to fix), while staying above the noise floor. Going finer would
# need a finer DEM, and see fetch_elevation.py's DATASET note for why 1m is
# the wrong answer there - not least that it has no coverage at all at the
# northern terminus.
#
# Cost: ~140,000 records for the full 2,190 miles, ~6MB of compact JSON and
# ~1MB gzipped - still trivial next to the 314MB background archive.
SAMPLE_INTERVAL_METERS = 25

# data/raw/half_mile_points_from_springer.geojson's real feature count
# (README.md's source table) - the sparse baseline this module exists to
# beat, referenced here (not just in comments) so main()'s own log output
# and the test suite can't silently drift apart from that real number.
HALF_MILE_MARKER_COUNT = 4395

# Real approximate trailhead coordinates (Springer Mountain, GA - the AT's
# southern terminus; Katahdin/Baxter Peak, ME - the northern terminus), used
# only as a rough south-to-north "trail axis" to order/orient the
# centerline's real disconnected segments (see ordered_oriented_parts) - not
# for anything requiring geodetic precision.
SPRINGER_LONLAT = (-84.1942, 34.6272)
KATAHDIN_LONLAT = (-68.9214, 45.9044)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_merged_trail_line(con: duckdb.DuckDBPyConnection, centerline_path: Path):
    """Read every real centerline.geojson feature (3,025 segments, one per
    maintaining-club-edited stretch - see README.md's source table) and
    merge touching segments into as few connected pieces as possible via
    ST_LineMerge(ST_Union_Agg(...)) - the same DuckDB spatial primitives
    spike_corridor.py/export_poi.py/export_trails.py already use elsewhere
    in this pipeline. See module docstring for the real gotcha this doesn't
    fully collapse to one LineString (558 pieces on the real data) - not a
    bug here, a real property of the raw source geometry."""
    con.execute(f"CREATE OR REPLACE TABLE _centerline AS SELECT * FROM ST_Read('{centerline_path.as_posix()}')")
    wkt = con.execute("SELECT ST_AsText(ST_LineMerge(ST_Union_Agg(geom))) FROM _centerline").fetchone()[0]
    return shapely_wkt.loads(wkt)


def _trail_axis_projection(lon: float, lat: float) -> float:
    """A rough scalar 'position along a straight Springer->Katahdin axis'
    for a (lon, lat) point - used only to order/orient centerline pieces
    south-to-north (see ordered_oriented_parts), never as a real distance
    measurement (the actual trail isn't straight - real cumulative distance
    comes from sample_points_along_parts' EPSG:5070 interpolation)."""
    dx = KATAHDIN_LONLAT[0] - SPRINGER_LONLAT[0]
    dy = KATAHDIN_LONLAT[1] - SPRINGER_LONLAT[1]
    return (lon - SPRINGER_LONLAT[0]) * dx + (lat - SPRINGER_LONLAT[1]) * dy


def ordered_oriented_parts(merged_geom) -> list[LineString]:
    """Turn load_merged_trail_line's output (a LineString, or - for the real
    data - a MultiLineString of disconnected pieces) into an ordered list of
    LineStrings running south-to-north: each piece is reversed if its own
    raw coordinates run north-to-south, then all pieces are sorted by their
    (now-consistent) starting point's _trail_axis_projection.

    This is only the pre-calibration pass now: #652 measured this
    approximation misplacing 18 stretches by more than ten miles (the AT's
    real north-south switchbacks are exactly what a straight-axis sort
    cannot see), so calibrate_parts_to_markers() re-orders, re-orients and
    re-scales its output against ATC's half-mile `Measure` field before
    anything downstream reads a mile. It is kept because pieces the markers
    cannot orient (fewer than two markers snapped) keep the orientation
    this gives them."""
    if isinstance(merged_geom, LineString):
        parts = [merged_geom]
    elif isinstance(merged_geom, MultiLineString):
        parts = list(merged_geom.geoms)
    else:
        raise TypeError(f"expected a (Multi)LineString from ST_LineMerge, got {type(merged_geom).__name__}")

    oriented = []
    for part in parts:
        coords = list(part.coords)
        if _trail_axis_projection(*coords[0]) > _trail_axis_projection(*coords[-1]):
            coords = coords[::-1]
        oriented.append(LineString(coords))
    oriented.sort(key=lambda line: _trail_axis_projection(*line.coords[0]))
    return oriented


def reproject_lines_to_meters(con: duckdb.DuckDBPyConnection, lines: list[LineString]) -> list[LineString]:
    """Bulk-reproject every ordered/oriented WGS84 piece to EPSG:5070 in one
    round trip rather than one query per piece. always_xy := true on both
    transform legs - see README.md's "Gotcha hit and fixed" note: without it
    ST_Transform silently swaps lat/lon instead of erroring.

    Loads via con.register() on a dict of numpy arrays, not con.executemany()
    - a real gotcha found while building this module (2026-07-28):
    executemany() measured ~13s for ~10,000 rows in this environment (~1.3ms/
    row of pure per-statement overhead), while registering the same data as
    a queryable relation and reading it back in one query measured ~0.01s -
    a >1000x difference that matters once a run means tens of thousands of
    rows, not the few hundred/thousand export_poi.py's/export_trails.py's
    own executemany() calls handle."""
    idx = np.arange(len(lines))
    wkts = np.array([line.wkt for line in lines], dtype=object)
    con.register("_parts_src", {"idx": idx, "wkt": wkts})
    try:
        rows = con.execute(f"""
            SELECT idx, ST_AsText(ST_Transform(ST_GeomFromText(wkt), '{GEOGRAPHIC_CRS}', '{PROJECTED_CRS}', always_xy := true))
            FROM _parts_src ORDER BY idx
        """).fetchall()
    finally:
        con.unregister("_parts_src")
    return [shapely_wkt.loads(wkt) for _, wkt in rows]


# --- Marker calibration of the mile axis (#652) --------------------------
#
# The centerline carries no trail-sequence field, but ATC publishes one in
# the only form the source data has: half_mile_points_from_springer's
# `Measure` - 4,395 points, each stamped with ATC's own NOBO mile. Measured
# 2026-08-18 against the live layers, the markers sit ON the centerline
# (p99 marker->nearest-piece distance 0.0 m, max 3.4 m), so snapping each
# marker to its piece is unambiguous, and 100 m is ~30x the worst real
# offset - wide enough to survive upstream jitter, narrow enough that a
# marker cannot land on the wrong piece except where two pieces genuinely
# overlap, where either is as good.
MARKER_SNAP_MAX_M = 100.0


class CalibratedPart(NamedTuple):
    """One centerline piece, oriented so ATC's mile increases along it, plus
    the marker control points that map distance-along to ATC's mile scale.

    `alongs_mi`/`miles` are parallel arrays: along-distance (miles) of each
    snapped marker on `line`, and ATC's `Measure` there. mile_at() linearly
    interpolates between them and extrapolates past the ends at unit slope -
    so between markers the piece's own geometric spacing is preserved (the
    warp is bounded by the geometry-vs-wheel disagreement over one half-mile
    gap), and a piece's already-correct interior is shifted, never
    reshaped."""

    line: LineString
    alongs_mi: np.ndarray
    miles: np.ndarray

    def mile_at(self, along_m):
        along_mi = np.asarray(along_m, dtype=float) / METERS_PER_MILE
        if len(self.alongs_mi) == 1:
            out = self.miles[0] + (along_mi - self.alongs_mi[0])
        else:
            out = np.interp(along_mi, self.alongs_mi, self.miles)
            lo, hi = self.alongs_mi[0], self.alongs_mi[-1]
            out = np.where(along_mi < lo, self.miles[0] + (along_mi - lo), out)
            out = np.where(along_mi > hi, self.miles[-1] + (along_mi - hi), out)
        return float(out) if np.isscalar(along_m) or np.ndim(along_m) == 0 else out

    @property
    def start_mile(self) -> float:
        return self.mile_at(0.0)


def load_half_mile_markers(con: duckdb.DuckDBPyConnection, markers_path: Path) -> tuple[list[Point], np.ndarray]:
    """ATC's half-mile markers as EPSG:5070 points plus their `Measure`
    miles. Loud when the file is missing or empty rather than degrading to
    the uncalibrated axis: an axis that silently loses its calibration is
    #652 coming back with nothing logging that it did."""
    if not markers_path.exists():
        raise FileNotFoundError(
            f"{markers_path} is missing - the mile axis is calibrated against ATC's "
            "half-mile markers (#652) and cannot be built without them. "
            "fetch_all.py fetches the layer."
        )
    features = json.loads(markers_path.read_text())["features"]
    if not features:
        raise ValueError(f"{markers_path} has no features - refusing to build an uncalibrated mile axis (#652).")
    idx = np.arange(len(features))
    xs = np.array([f["geometry"]["coordinates"][0] for f in features])
    ys = np.array([f["geometry"]["coordinates"][1] for f in features])
    miles = np.array([f["properties"]["Measure"] for f in features], dtype=float)
    con.register("_markers_src", {"idx": idx, "x": xs, "y": ys})
    try:
        rows = con.execute(f"""
            SELECT idx, ST_X(g), ST_Y(g) FROM (
                SELECT idx, ST_Transform(ST_Point(x, y), '{GEOGRAPHIC_CRS}', '{PROJECTED_CRS}', always_xy := true) AS g
                FROM _markers_src
            ) ORDER BY idx
        """).fetchall()
    finally:
        con.unregister("_markers_src")
    return [Point(x, y) for _, x, y in rows], miles


def _snap_markers_to_parts(
    parts_meters: list[LineString], marker_points: list[Point], marker_miles: np.ndarray
) -> dict[int, list[tuple[float, float]]]:
    """part index -> [(along_m, mile)] for every marker within
    MARKER_SNAP_MAX_M of that part, along-sorted."""
    tree = STRtree(parts_meters)
    snapped: dict[int, list[tuple[float, float]]] = {}
    for point, mile in zip(marker_points, marker_miles):
        index = int(tree.nearest(point))
        part = parts_meters[index]
        if part.distance(point) <= MARKER_SNAP_MAX_M:
            snapped.setdefault(index, []).append((part.project(point), mile))
    for pairs in snapped.values():
        pairs.sort()
    return snapped


def _calibrated_part(line: LineString, pairs: list[tuple[float, float]]) -> tuple[CalibratedPart, bool]:
    """Calibrate one piece from its along-sorted (along_m, mile) pairs.
    Returns the calibrated part and whether the line was reversed.

    With two or more markers the piece is oriented by them - reversed when
    mile falls as along grows - which is what catches the 33 real switchback
    pieces the straight-axis heuristic mis-orients (measured 2026-08-18).
    With one marker the incoming orientation is kept: one point carries no
    direction. Marker miles are made monotone with a running max before
    interpolation; the jitter this absorbs is small (anchor-spread p95
    median 60 m per piece, same measurement)."""
    alongs = np.array([a for a, _ in pairs], dtype=float)
    miles = np.array([m for _, m in pairs], dtype=float)
    reversed_ = len(pairs) >= 2 and np.polyfit(alongs, miles, 1)[0] < 0
    if reversed_:
        line = LineString(list(line.coords)[::-1])
        alongs = line.length - alongs
        order = np.argsort(alongs)
        alongs, miles = alongs[order], miles[order]
    miles = np.maximum.accumulate(miles)
    return CalibratedPart(line, alongs / METERS_PER_MILE, miles), reversed_


def calibrate_parts_to_markers(
    parts_meters: list[LineString], marker_points: list[Point], marker_miles: np.ndarray
) -> list[CalibratedPart]:
    """Order, orient, and scale every piece by ATC's own mile field (#652).

    This replaces the straight Springer->Katahdin projection as the thing
    that decides trail order. What it changes and what it leaves alone,
    which is the shape the fix was asked for in: pieces already in the right
    relative order keep that order and keep their internal geometric
    spacing - a correct piece's miles change only by the offset that brings
    them onto ATC's scale. The 18 stretches the projection had more than ten
    miles out of place land where ATC says they are.

    Pieces no marker snapped to - 182 of 558 on the real data, 7.5 mi in
    total, none longer than 0.43 mi - are anchored from the nearest marker
    outright: mile error there is bounded by the marker spacing plus the
    piece's own length, a fraction of a mile on a fraction of a percent of
    the trail, against the median 7.7 mi the uncalibrated axis measured."""
    snapped = _snap_markers_to_parts(parts_meters, marker_points, marker_miles)
    marker_tree = STRtree(marker_points)
    calibrated = []
    for index, line in enumerate(parts_meters):
        pairs = snapped.get(index)
        if not pairs:
            nearest = int(marker_tree.nearest(line))
            pairs = [(line.project(marker_points[nearest]), float(marker_miles[nearest]))]
        calibrated.append(_calibrated_part(line, pairs)[0])
    calibrated.sort(key=lambda cal: cal.start_mile)
    return calibrated


def measure_marker_agreement(parts_meters: list[LineString], marker_points: list[Point], marker_miles: np.ndarray) -> dict:
    """How accurately the calibrated axis reproduces ATC's miles, measured
    honestly: each piece is calibrated from its even-indexed markers only
    and scored on the odd-indexed ones it never saw. Scoring the fit on its
    own control points would measure nothing - interpolation passes through
    them by construction.

    Returns holdout count and median/p95/max absolute error in miles.
    Reference figures from the real data (2026-08-18): median 0.003 mi,
    p95 0.055 mi, max 0.497 mi over 2,022 held-out markers - against the
    uncalibrated axis's median 7.7 mi and max 101.8 mi (#652)."""
    snapped = _snap_markers_to_parts(parts_meters, marker_points, marker_miles)
    errors = []
    for index, pairs in snapped.items():
        if len(pairs) < 4:
            continue
        fitted, reversed_ = _calibrated_part(parts_meters[index], pairs[::2])
        for along_m, mile in pairs[1::2]:
            oriented_along = fitted.line.length - along_m if reversed_ else along_m
            errors.append(abs(fitted.mile_at(oriented_along) - mile))
    errors = np.array(errors) if errors else np.array([0.0])
    return {
        "holdout_marker_count": int(len(errors)),
        "holdout_median_mi": float(np.median(errors)),
        "holdout_p95_mi": float(np.percentile(errors, 95)),
        "holdout_max_mi": float(errors.max()),
    }


# The gate on measure_marker_agreement's holdout error. Reasoned from the
# 2026-08-18 real-data measurement above, with 4-15x headroom over what was
# observed so upstream data drift does not flap the build - while staying
# 15x under the smallest error the uncalibrated fault produced at median,
# so a return of #652 cannot pass.
MARKER_HOLDOUT_MAX_MEDIAN_MI = 0.05
MARKER_HOLDOUT_MAX_P95_MI = 0.25
MARKER_HOLDOUT_MAX_MI = 1.0


def require_marker_agreement(agreement: dict) -> None:
    """The accuracy gate: refuse to publish an axis that stopped agreeing
    with ATC's own miles. A quietly-degraded calibration is the one failure
    mode worse than the fault it fixed, because this time the code would
    claim to be calibrated."""
    breaches = []
    if agreement["holdout_median_mi"] > MARKER_HOLDOUT_MAX_MEDIAN_MI:
        breaches.append(f"median {agreement['holdout_median_mi']:.3f} mi > {MARKER_HOLDOUT_MAX_MEDIAN_MI}")
    if agreement["holdout_p95_mi"] > MARKER_HOLDOUT_MAX_P95_MI:
        breaches.append(f"p95 {agreement['holdout_p95_mi']:.3f} mi > {MARKER_HOLDOUT_MAX_P95_MI}")
    if agreement["holdout_max_mi"] > MARKER_HOLDOUT_MAX_MI:
        breaches.append(f"max {agreement['holdout_max_mi']:.3f} mi > {MARKER_HOLDOUT_MAX_MI}")
    if breaches:
        raise SystemExit(
            "Mile axis no longer agrees with ATC's half-mile markers on held-out points: "
            + "; ".join(breaches)
            + ". Refusing to publish a mis-calibrated axis (#652). Inspect the fetched "
            "centerline and half_mile_points_from_springer layers for upstream changes."
        )


def calibrated_trail_axis(con: duckdb.DuckDBPyConnection, centerline_path: Path, markers_path: Path) -> list[CalibratedPart]:
    """The one mile axis everything shares (#652, #753): merge the
    centerline, orient/order/scale it by ATC's half-mile markers. Both the
    elevation profile's distance_mi and export_poi's published POI mile come
    off this function, which is what makes them one measurement."""
    merged = load_merged_trail_line(con, centerline_path)
    parts_meters = reproject_lines_to_meters(con, ordered_oriented_parts(merged))
    marker_points, marker_miles = load_half_mile_markers(con, markers_path)
    return calibrate_parts_to_markers(parts_meters, marker_points, marker_miles)


def sample_points_along_parts(parts_meters: list[LineString], interval_m: float) -> list[tuple[float, Point, int]]:
    """Walk every ordered piece (already reprojected to meters) end to end,
    placing one sample point every interval_m of cumulative distance via
    shapely's .interpolate() - the actual dense along-the-line sampling this
    module exists for, in place of the existing 4,395 sparse half-mile
    markers. See module docstring for the known cross-gap limitation. Robust
    to a degenerate (zero-length) piece - it just contributes no points and
    no distance, rather than looping forever or crashing.

    Each sample carries the index of the piece it came from, and that is the
    whole of #559's fix. The distance axis carries straight across the gap
    between two pieces as though they touched, so the step between the last
    sample of one and the first of the next looks exactly like terrain to
    anything reading elevations alone - which is how ~36,800 ft of phantom
    climb ended up in the published gain. The walk is the only place that
    knows where the seams are, so it is the only place that can say.
    """
    samples: list[tuple[float, Point, int]] = []
    cumulative_before = 0.0
    pending = 0.0
    for index, part in enumerate(parts_meters):
        length = part.length
        d = pending
        while d <= length:
            samples.append((cumulative_before + d, part.interpolate(d), index))
            d += interval_m
        pending = d - length
        cumulative_before += length
    return samples


def reproject_points_to_wgs84(
    con: duckdb.DuckDBPyConnection, samples_meters: list[tuple[float, Point]]
) -> list[tuple[float, float]]:
    """Bulk-reproject every sampled point back to lon/lat (EPSG:4326) - the
    CRS the downloaded DEM tiles get reprojected into via WarpedVRT (see
    ElevationSampler) - in one round trip rather than one query per point.
    See reproject_lines_to_meters' docstring for why this registers a dict
    of numpy arrays instead of using con.executemany() - the same >1000x
    real performance gap applies here, and matters more: a full corridor run
    means tens of thousands of points, not hundreds of trail pieces."""
    idx = np.arange(len(samples_meters))
    xs = np.array([pt.x for _, pt, _part in samples_meters])
    ys = np.array([pt.y for _, pt, _part in samples_meters])
    con.register("_sample_points_src", {"idx": idx, "x": xs, "y": ys})
    try:
        rows = con.execute(f"""
            SELECT idx, ST_X(geom), ST_Y(geom) FROM (
                SELECT idx, ST_Transform(ST_Point(x, y), '{PROJECTED_CRS}', '{GEOGRAPHIC_CRS}', always_xy := true) AS geom
                FROM _sample_points_src
            ) ORDER BY idx
        """).fetchall()
    finally:
        con.unregister("_sample_points_src")
    return [(lon, lat) for _, lon, lat in rows]


def index_elevation_tiles(index_path: Path) -> list[tuple[str, tuple[float, float, float, float]]]:
    """Read fetch_elevation.py's tile index and return (source, bounds) pairs
    ready for ElevationSampler.

    The "source" is a `/vsicurl/` URL, not a local file. Nothing is
    downloaded: 3DEP tiles are Cloud-Optimized GeoTIFFs, so rasterio reads
    them in place over HTTP and pulls only the 512x512 blocks the trail
    actually crosses. Measured on real centerline points, that is ~10 ms per
    sample - roughly 25 minutes for the whole corridor, against ~24 GB and a
    lot longer to fetch whole 1-degree tiles and read a thin line through
    them. See fetch_elevation.py's module docstring for the full reasoning,
    including why 1m DEM was rejected.

    Bounds come from the index rather than by opening each tile: opening 110
    remote rasters just to read their headers would cost a round trip each,
    and TNM already gave us the footprint.
    """
    entries = json.loads(index_path.read_text())
    return [(_gdal_source(entry["url"]), tuple(entry["bounds"])) for entry in entries]


def _gdal_source(url: str) -> str | Path:
    """`/vsicurl/`-prefix a remote URL so GDAL range-reads it; hand a local
    entry back as a real Path.

    The Path matters on Windows: given the string "C:/tmp/x.tif" GDAL parses
    "C:" as a URL scheme and fails with a port-number error. A Path object is
    never URL-parsed. Keeping this conditional rather than always prefixing is
    also what lets tests point the sampler at local fixture rasters.
    """
    return f"/vsicurl/{url}" if url.startswith(("http://", "https://")) else Path(url)


def _bounds_contains_point(bounds: tuple[float, float, float, float], lon: float, lat: float) -> bool:
    xmin, ymin, xmax, ymax = bounds
    return xmin <= lon <= xmax and ymin <= lat <= ymax


class ElevationSampler:
    """Samples elevation at arbitrary (lon, lat) points from the indexed
    DEM tiles (local paths or remote /vsicurl/ URLs - see
    index_elevation_tiles), lazily opening + caching one WarpedVRT (reprojected
    to EPSG:4326) per tile actually touched, reused across nearby sample
    points instead of reopening per point - a densely-sampled 2,190-mile
    trail means tens of thousands of point queries.

    "Mosaics" tiles only when more than one covers the same point (a rare
    overlap at a LiDAR-project boundary): takes the first covering tile's
    reading unless it's nodata, in which case it falls through to the next
    covering tile - the same "first" strategy rasterio.merge() uses by
    default, just resolved per point instead of materializing a merged
    array. spike_raster_mosaic.py's full-array merge() would be wasted work
    here, since this only ever reads isolated sample points, never a raster
    image - the "lighter scale" mosaic this module's docstring promises.

    Returns None for a point no indexed tile covers - a real DEM coverage
    gap (e.g. a stretch of trail with no 1m LiDAR project flown yet) -
    instead of raising, so a gap in source coverage degrades the profile
    gracefully rather than crashing the whole export."""

    def __init__(self, tile_index: list[tuple[str | Path, tuple[float, float, float, float]]]):
        self._tile_index = tile_index
        self._vrt_cache: dict[str | Path, WarpedVRT] = {}

    def _vrt_for(self, path: str | Path) -> WarpedVRT:
        if path not in self._vrt_cache:
            src = rasterio.open(path)
            self._vrt_cache[path] = WarpedVRT(src, crs=GEOGRAPHIC_CRS)
        return self._vrt_cache[path]

    def _covering_tiles(self, lon: float, lat: float):
        for path, bounds in self._tile_index:
            if _bounds_contains_point(bounds, lon, lat):
                yield path

    def sample(self, lon: float, lat: float) -> float | None:
        """Single-point convenience wrapper around sample_many() - same
        first-valid-tile precedence, just for one point at a time."""
        return self.sample_many([(lon, lat)])[0]

    def sample_many(self, points: list[tuple[float, float]]) -> list[float | None]:
        """Batched point sampling: groups points by whichever tile covers
        them, then does one windowed array read per tile - scoped to the
        bounding box of just that tile's own touched points, not the whole
        tile (real 1m DEM tiles can be large; a full-tile read per tile
        risks real memory pressure across hundreds of them) - instead of one
        WarpedVRT.sample() Python call per point. Measured ~100x faster than
        the naive per-point .sample() loop on synthetic test-scale data,
        real enough to matter for a full ~70,000-point corridor run. Falls
        through to the next covering tile (if any) when the first candidate
        is nodata at that exact point - see class docstring's "mosaic if
        needed" note."""
        results: list[float | None] = [None] * len(points)
        by_tile: dict[Path, list[int]] = {}
        remaining_candidates: dict[int, list[Path]] = {}
        for i, (lon, lat) in enumerate(points):
            candidates = list(self._covering_tiles(lon, lat))
            if not candidates:
                continue  # real DEM coverage gap - stays None
            remaining_candidates[i] = candidates[1:]
            by_tile.setdefault(candidates[0], []).append(i)

        while by_tile:
            tile_path, indices = by_tile.popitem()
            vrt = self._vrt_for(tile_path)
            inv_transform = ~vrt.transform
            cols = np.empty(len(indices), dtype=np.int64)
            rows = np.empty(len(indices), dtype=np.int64)
            for j, i in enumerate(indices):
                lon, lat = points[i]
                col_f, row_f = inv_transform * (lon, lat)
                cols[j] = min(max(int(col_f), 0), vrt.width - 1)
                rows[j] = min(max(int(row_f), 0), vrt.height - 1)

            row_off, col_off = int(rows.min()), int(cols.min())
            window = Window(col_off, row_off, int(cols.max()) - col_off + 1, int(rows.max()) - row_off + 1)
            data = vrt.read(1, window=window)
            nodata = vrt.nodata

            for j, i in enumerate(indices):
                value = float(data[rows[j] - row_off, cols[j] - col_off])
                # NaN is checked unconditionally, not just when it is the
                # declared nodata: `value == nodata` is always False for
                # NaN, so a NaN-nodata tile used to pass its NaNs through
                # as "real" elevations - and json.dumps then emits a
                # literal NaN that JSON.parse rejects, taking the whole
                # profile down client-side on one upstream re-encode
                # (#659). A NaN sample is never a real elevation, whatever
                # the tile's metadata says.
                if math.isnan(value) or (nodata is not None and value == nodata):
                    # This tile covers the point but has no real data there
                    # - fall through to the next covering tile, if any (the
                    # "mosaic if needed" case), instead of leaving it None.
                    next_candidates = remaining_candidates.get(i, [])
                    if next_candidates:
                        by_tile.setdefault(next_candidates[0], []).append(i)
                        remaining_candidates[i] = next_candidates[1:]
                    continue
                results[i] = value

        return results

    def close(self) -> None:
        for vrt in self._vrt_cache.values():
            vrt.close()
            vrt.src_dataset.close()


def measure_cross_part_gaps(parts_meters: list[LineString]) -> tuple[float, float]:
    """Diagnostic-only: measures the real, straight-line distance between
    each ordered/reprojected (EPSG:5070 meters) part's end and the next
    part's start - exactly the gap sample_points_along_parts() intentionally
    does NOT add to its cumulative distance (see module docstring point 4
    and that function's own docstring). Does not affect sampling or output
    records at all; purely quantifies how big that already-documented
    approximation is on a given run.

    Returns (total_gap_m, max_gap_m) summed/maxed across every consecutive
    pair of parts - (0.0, 0.0) for 0 or 1 parts, where there's no gap to
    measure."""
    total_gap_m = 0.0
    max_gap_m = 0.0
    for prev_part, next_part in zip(parts_meters, parts_meters[1:]):
        gap = Point(prev_part.coords[-1]).distance(Point(next_part.coords[0]))
        total_gap_m += gap
        max_gap_m = max(max_gap_m, gap)
    return total_gap_m, max_gap_m


def build_profile(
    centerline_path: Path, markers_path: Path, elevation_index_path: Path, interval_m: float
) -> tuple[list[dict], dict]:
    """Orchestrate the full merge -> calibrate -> sample -> DEM-lookup
    pipeline (see module docstring for the step-by-step rationale). Returns
    (records, diagnostics):
    - records: sorted by distance_mi (guaranteed by construction: each
      piece's mile_at is monotone, pieces are emitted in calibrated order,
      and any sample that would step the axis backwards - overlapping
      duplicate source geometry, ~5 mi of the real trail - is dropped and
      counted rather than published twice). Null elevation_ft for any point
      outside every downloaded DEM tile's coverage.
    - diagnostics: cross-part gap totals (measure_cross_part_gaps),
      marker-agreement holdout stats (measure_marker_agreement, already
      gated by require_marker_agreement before this returns), and the
      overlap-clip counts."""
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")

    merged = load_merged_trail_line(con, centerline_path)
    parts_meters = reproject_lines_to_meters(con, ordered_oriented_parts(merged))
    marker_points, marker_miles = load_half_mile_markers(con, markers_path)

    agreement = measure_marker_agreement(parts_meters, marker_points, marker_miles)
    require_marker_agreement(agreement)

    calibrated = calibrate_parts_to_markers(parts_meters, marker_points, marker_miles)
    lines = [cal.line for cal in calibrated]
    cross_part_gaps = measure_cross_part_gaps(lines)

    offsets = []
    cumulative = 0.0
    for line in lines:
        offsets.append(cumulative)
        cumulative += line.length

    samples_meters = sample_points_along_parts(lines, interval_m)
    lonlats = reproject_points_to_wgs84(con, samples_meters)

    tile_index = index_elevation_tiles(elevation_index_path)
    sampler = ElevationSampler(tile_index)
    try:
        elevations_m = sampler.sample_many(lonlats)
    finally:
        sampler.close()

    records = []
    previous_part = None
    high_water = float("-inf")
    clipped_count = 0
    for (distance_m, _pt, part), elevation_m in zip(samples_meters, elevations_m):
        # Clipped on the ROUNDED mile - the value the artifact actually
        # publishes - not the raw one. Two samples from different pieces can
        # sit closer than the 3-decimal precision at a seam (the real run
        # that found this had exactly two such pairs in 138,710 samples),
        # and clipping the raw value would let them through as equal
        # published neighbours, breaking the strictly-increasing contract by
        # a rounding artifact.
        mile = round(calibrated[part].mile_at(distance_m - offsets[part]), 3)
        # Where two pieces cover the same stretch of trail - duplicate
        # geometry surviving the merge, see ORDERING.md's degree-6 nodes -
        # their calibrated mile ranges overlap, and publishing both would
        # put the same miles on the axis twice (and their phantom gain in
        # the total, twice). The first piece to reach a mile keeps it.
        if mile <= high_water:
            clipped_count += 1
            continue
        high_water = mile
        record = {
            "distance_mi": mile,
            "elevation_ft": round(elevation_m / METERS_PER_FOOT, 1) if elevation_m is not None else None,
        }
        # Only on the first emitted sample of a piece, and absent everywhere
        # else (#559). A `part` index on all ~139,000 records would say the
        # same thing and cost about a megabyte on an artifact hikers download
        # over a trailhead's signal; the seams are 558 of them. A reader that
        # does not know the key ignores it, which is what makes this additive.
        #
        # Including the very first sample, where breaking a run is a no-op.
        # Uniform is worth more than clever here: a consumer should be able to
        # write "start a new run at every part_start" without special-casing
        # index 0.
        if part != previous_part:
            record["part_start"] = True
            previous_part = part
        records.append(record)

    diagnostics = {
        "cross_part_gaps": cross_part_gaps,
        "marker_agreement": agreement,
        "clipped_sample_count": clipped_count,
        "clipped_mi": round(clipped_count * interval_m / METERS_PER_MILE, 2),
    }
    return records, diagnostics


def main() -> dict:
    print("Merging the real centerline + calibrating to ATC's half-mile markers...")
    records, diagnostics = build_profile(CENTERLINE_PATH, MARKERS_PATH, ELEVATION_INDEX_PATH, SAMPLE_INTERVAL_METERS)
    total_gap_m, max_gap_m = diagnostics["cross_part_gaps"]
    agreement = diagnostics["marker_agreement"]
    density = len(records) / (records[-1]["distance_mi"] or 1) if records else 0
    print(
        f"  {len(records)} sample points at {SAMPLE_INTERVAL_METERS}m intervals "
        f"(~{density:.1f}/mile, vs. {HALF_MILE_MARKER_COUNT} half-mile markers at ~2/mile)."
    )
    print(
        f"  Cross-part gaps not counted in distance_mi (real, unmeasured space "
        f"between disconnected centerline pieces - see module docstring point 4): "
        f"total {total_gap_m:.1f}m ({total_gap_m / METERS_PER_MILE:.3f}mi), "
        f"max single gap {max_gap_m:.1f}m ({max_gap_m / METERS_PER_MILE:.3f}mi)."
    )
    print(
        f"  Marker agreement (held-out): median {agreement['holdout_median_mi']:.3f} mi, "
        f"p95 {agreement['holdout_p95_mi']:.3f} mi, max {agreement['holdout_max_mi']:.3f} mi "
        f"over {agreement['holdout_marker_count']} markers (#652)."
    )
    print(
        f"  {diagnostics['clipped_sample_count']} samples on overlapping duplicate geometry "
        f"clipped (~{diagnostics['clipped_mi']} mi published once instead of twice)."
    )

    null_elevation_count = sum(1 for r in records if r["elevation_ft"] is None)
    null_elevation_pct = (null_elevation_count / len(records) * 100) if records else 0.0
    print(f"  {null_elevation_count} points with no DEM coverage ({null_elevation_pct:.2f}% of {len(records)}).")

    # Both numbers, not just the good one. The raw sum is what this profile
    # gives anyone who adds up its rises without thinking about it - 17% too
    # high, because summing is the operation that turns DEM error into signal
    # (lib/elevation_gain.py). Recording them side by side means the next
    # person to reach for a total finds the corrected one *and* finds out why
    # it is not the obvious one, rather than rederiving the bug.
    elevations = [r["elevation_ft"] for r in records]
    raw_gain_ft = raw_cumulative_gain(elevations)
    gain_ft = cumulative_gain_over_gaps(elevations, DEFAULT_THRESHOLD_FT)
    print(f"  Cumulative ascent {gain_ft:,.0f} ft at a {DEFAULT_THRESHOLD_M} m dead band; {raw_gain_ft:,.0f} ft raw.")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(records))

    manifest = {
        "path": str(OUT_PATH),
        "sha256": sha256_file(OUT_PATH),
        "point_count": len(records),
        "null_elevation_count": null_elevation_count,
        "null_elevation_pct": round(null_elevation_pct, 2),
        "cumulative_gain_ft": round(gain_ft),
        "cumulative_gain_raw_ft": round(raw_gain_ft),
        "cumulative_gain_threshold_m": DEFAULT_THRESHOLD_M,
        # The axis's own accuracy, run-over-run (#652): held-out agreement
        # with ATC's half-mile markers, plus how much duplicate geometry was
        # clipped. In the manifest so a calibration regression shows up in a
        # diff of published metadata, not only in a log nobody reads.
        "marker_holdout_median_mi": round(agreement["holdout_median_mi"], 4),
        "marker_holdout_p95_mi": round(agreement["holdout_p95_mi"], 4),
        "marker_holdout_max_mi": round(agreement["holdout_max_mi"], 4),
        "marker_holdout_count": agreement["holdout_marker_count"],
        "clipped_sample_count": diagnostics["clipped_sample_count"],
    }
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2))
    print(f"Profile -> {OUT_PATH}\nManifest -> {MANIFEST_PATH}")

    return manifest


if __name__ == "__main__":
    main()
