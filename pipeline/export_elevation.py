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
   ordered_oriented_parts() puts those disconnected pieces into a sensible
   south-to-north order using a rough Springer->Katahdin axis, reorienting
   any piece whose own raw coordinate order runs the "wrong" way. This is a
   real, honestly-documented approximation, not a guaranteed-correct
   trail-order reconstruction - see that function's docstring.
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
from pathlib import Path

import duckdb
import numpy as np
import rasterio
from rasterio.vrt import WarpedVRT
from rasterio.windows import Window
from shapely import wkt as shapely_wkt
from shapely.geometry import LineString, MultiLineString, Point

ROOT = Path(__file__).parent
CENTERLINE_PATH = ROOT / "data" / "raw" / "centerline.geojson"
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

    Real, worth-being-upfront-about limitation: centerline.geojson carries
    no explicit trail-sequence field, so this is a geographic approximation,
    not a guaranteed-correct trail-order reconstruction - good enough for
    the AT's overall SW-to-NE run, but a piece that runs opposite to that
    axis at a large scale (the AT does have some real north-south
    switchbacks, e.g. around the Smokies) could still land slightly out of
    true hiking order. That's a limitation of the source data having no
    sequence field, not something a smarter heuristic here fully solves."""
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


def sample_points_along_parts(parts_meters: list[LineString], interval_m: float) -> list[tuple[float, Point]]:
    """Walk every ordered piece (already reprojected to meters) end to end,
    placing one sample point every interval_m of cumulative distance via
    shapely's .interpolate() - the actual dense along-the-line sampling this
    module exists for, in place of the existing 4,395 sparse half-mile
    markers. See module docstring for the known cross-gap limitation. Robust
    to a degenerate (zero-length) piece - it just contributes no points and
    no distance, rather than looping forever or crashing."""
    samples: list[tuple[float, Point]] = []
    cumulative_before = 0.0
    pending = 0.0
    for part in parts_meters:
        length = part.length
        d = pending
        while d <= length:
            samples.append((cumulative_before + d, part.interpolate(d)))
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
    xs = np.array([pt.x for _, pt in samples_meters])
    ys = np.array([pt.y for _, pt in samples_meters])
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
                value = data[rows[j] - row_off, cols[j] - col_off]
                if nodata is not None and value == nodata:
                    # This tile covers the point but has no real data there
                    # - fall through to the next covering tile, if any (the
                    # "mosaic if needed" case), instead of leaving it None.
                    next_candidates = remaining_candidates.get(i, [])
                    if next_candidates:
                        by_tile.setdefault(next_candidates[0], []).append(i)
                        remaining_candidates[i] = next_candidates[1:]
                    continue
                results[i] = float(value)

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


def build_profile(centerline_path: Path, elevation_index_path: Path, interval_m: float) -> tuple[list[dict], tuple[float, float]]:
    """Orchestrate the full merge -> order -> sample -> DEM-lookup pipeline
    (see module docstring for the step-by-step rationale). Returns
    (records, cross_part_gaps):
    - records: sorted by distance_mi (guaranteed by construction - see
      sample_points_along_parts), each with a null elevation_ft for any
      point outside every downloaded DEM tile's coverage.
    - cross_part_gaps: the (total_gap_m, max_gap_m) tuple from
      measure_cross_part_gaps() - a diagnostic main() logs, not a value
      reflected in any record's distance_mi."""
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")

    merged = load_merged_trail_line(con, centerline_path)
    parts_wgs84 = ordered_oriented_parts(merged)
    parts_meters = reproject_lines_to_meters(con, parts_wgs84)
    cross_part_gaps = measure_cross_part_gaps(parts_meters)
    samples_meters = sample_points_along_parts(parts_meters, interval_m)
    lonlats = reproject_points_to_wgs84(con, samples_meters)

    tile_index = index_elevation_tiles(elevation_index_path)
    sampler = ElevationSampler(tile_index)
    try:
        elevations_m = sampler.sample_many(lonlats)
    finally:
        sampler.close()

    records = [
        {
            "distance_mi": round(distance_m / METERS_PER_MILE, 3),
            "elevation_ft": round(elevation_m / METERS_PER_FOOT, 1) if elevation_m is not None else None,
        }
        for (distance_m, _pt), elevation_m in zip(samples_meters, elevations_m)
    ]
    return records, cross_part_gaps


def main() -> dict:
    print("Merging + ordering the real centerline...")
    records, (total_gap_m, max_gap_m) = build_profile(CENTERLINE_PATH, ELEVATION_INDEX_PATH, SAMPLE_INTERVAL_METERS)
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

    null_elevation_count = sum(1 for r in records if r["elevation_ft"] is None)
    null_elevation_pct = (null_elevation_count / len(records) * 100) if records else 0.0
    print(f"  {null_elevation_count} points with no DEM coverage ({null_elevation_pct:.2f}% of {len(records)}).")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(records))

    manifest = {
        "path": str(OUT_PATH),
        "sha256": sha256_file(OUT_PATH),
        "point_count": len(records),
        "null_elevation_count": null_elevation_count,
        "null_elevation_pct": round(null_elevation_pct, 2),
    }
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2))
    print(f"Profile -> {OUT_PATH}\nManifest -> {MANIFEST_PATH}")

    return manifest


if __name__ == "__main__":
    main()
