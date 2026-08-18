"""Tests for export_elevation.py - dense along-the-trail elevation sampling
(ROADMAP.md's elevation line: the existing 4,395 half-mile markers average
just 2 points/mile, which under-counts real gain/loss on switchbacks and
steep pitches the same way other hiking apps' sparse sampling does). Small
synthetic fixtures throughout (a tiny DEM built in test code, a tiny
centerline), never the real ~14GB USGS 3DEP dataset or the full real
centerline.geojson - see TESTING.md.
"""

import json

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_bounds
from rasterio.warp import transform_bounds
from shapely.geometry import LineString, MultiLineString

import export_elevation


def _index_for_dir(dem_dir, tmp_path):
    """Turn a directory of local fixture DEM tiles into the tile-index JSON
    that index_elevation_tiles() now reads (see fetch_elevation.py - the real
    pipeline resolves remote COG URLs rather than downloading tiles)."""
    import json as _json

    import rasterio as _rio
    from rasterio.warp import transform_bounds as _tb

    entries = []
    for path in sorted(dem_dir.glob("*/*.tif")) + sorted(dem_dir.glob("*.tif")):
        with _rio.open(path) as src:
            b = _tb(src.crs, "EPSG:4326", *src.bounds)
        entries.append({"url": path.as_posix(), "bounds": list(b)})
    out = tmp_path / "tile_index.json"
    out.write_text(_json.dumps(entries))
    return out


# Real approximate trailhead coordinates (also used by export_elevation.py
# itself - see its module docstring) - kept independent here rather than
# imported, so a typo in the module's own constants wouldn't silently make
# this test vacuous.
SPRINGER = (-84.1942, 34.6272)
KATAHDIN = (-68.9214, 45.9044)


def _write_centerline(path, coord_groups):
    """coord_groups: a list of coordinate lists - each becomes its own
    LineString Feature, mirroring the real centerline.geojson's shape (many
    separate segment features, not one feature for the whole trail)."""
    if coord_groups and isinstance(coord_groups[0], tuple):
        coord_groups = [coord_groups]  # allow passing a single flat coord list
    features = [
        {
            "type": "Feature",
            "properties": {},
            "geometry": {"type": "LineString", "coordinates": [[lon, lat] for lon, lat in coords]},
        }
        for coords in coord_groups
    ]
    path.write_text(json.dumps({"type": "FeatureCollection", "features": features}))


def _write_dem_tile(path, bounds, size=20, elevation=500.0, crs="EPSG:4326", nodata=-9999.0):
    """A tiny real single-band GeoTIFF covering `bounds` (west, south, east,
    north) filled with a constant elevation value - written to real bytes on
    disk via rasterio, not committed as an opaque binary (see TESTING.md)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    transform = from_bounds(*bounds, size, size)
    profile = {
        "driver": "GTiff",
        "height": size,
        "width": size,
        "count": 1,
        "dtype": "float32",
        "crs": crs,
        "transform": transform,
        "nodata": nodata,
    }
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(np.full((1, size, size), elevation, dtype="float32"))


def _write_markers(path, coord_groups, interval_mi=0.5):
    """ATC-shaped half-mile markers for a synthetic centerline: walked along
    coord_groups in their GIVEN order - the fixture author's intended trail
    order - with `Measure` set to the true cumulative mile, mirroring the
    real half_mile_points_from_springer.geojson (#652). The first marker
    lands at Measure 0.5, like ATC's does."""
    from rasterio.warp import transform as _warp_transform

    if coord_groups and isinstance(coord_groups[0], tuple):
        coord_groups = [coord_groups]
    interval_m = interval_mi * 1609.344
    features = []
    pending = interval_m
    next_measure = interval_mi
    for coords in coord_groups:
        xs, ys = _warp_transform("EPSG:4326", "EPSG:5070", [lon for lon, _ in coords], [lat for _, lat in coords])
        line_m = LineString(list(zip(xs, ys)))
        d = pending
        while d <= line_m.length:
            pt = line_m.interpolate(d)
            lon, lat = _warp_transform("EPSG:5070", "EPSG:4326", [pt.x], [pt.y])
            features.append(
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [lon[0], lat[0]]},
                    "properties": {"Measure": next_measure},
                }
            )
            next_measure += interval_mi
            d += interval_m
        pending = d - line_m.length
    path.write_text(json.dumps({"type": "FeatureCollection", "features": features}))


def _setup(tmp_path, monkeypatch, centerline_coord_groups, dem_tiles, markers_coord_groups=None):
    """dem_tiles: list of (relative_path_under_elevation_dir, bounds, elevation)
    tuples - written under <elevation_dir>/<relative_path> mirroring
    fetch_elevation.py's real OUT_DIR/<state>/<file>.tif layout.

    Half-mile markers are generated along the centerline's own coordinate
    order (the axis is calibrated to them since #652); pass
    markers_coord_groups to walk the markers along different geometry than
    the centerline carries - e.g. to leave duplicated geometry out of the
    mile scale the way ATC's real markers do."""
    centerline_path = tmp_path / "centerline.geojson"
    _write_centerline(centerline_path, centerline_coord_groups)

    markers_path = tmp_path / "half_mile_points.geojson"
    _write_markers(markers_path, markers_coord_groups or centerline_coord_groups)

    elevation_dir = tmp_path / "elevation"
    for rel_path, bounds, elevation in dem_tiles:
        _write_dem_tile(elevation_dir / rel_path, bounds, elevation=elevation)

    out_path = tmp_path / "elevation_profile.json"
    manifest_path = tmp_path / "elevation_manifest.json"

    monkeypatch.setattr(export_elevation, "CENTERLINE_PATH", centerline_path)
    monkeypatch.setattr(export_elevation, "MARKERS_PATH", markers_path)
    monkeypatch.setattr(export_elevation, "ELEVATION_INDEX_PATH", _index_for_dir(elevation_dir, tmp_path))
    monkeypatch.setattr(export_elevation, "OUT_PATH", out_path)
    monkeypatch.setattr(export_elevation, "MANIFEST_PATH", manifest_path)

    return out_path, manifest_path


# --- the core density claim ---------------------------------------------


def test_export_elevation_produces_denser_points_than_the_half_mile_markers_alone(tmp_path, monkeypatch):
    """This is the entire point of the module. A full-corridor-scale
    synthetic line (spanning a real chunk of the actual Springer->Katahdin
    geographic extent, ~323 real miles) sampled at the module's real default
    interval must produce far more than the real half_mile_points_from_
    springer.geojson's 4,395 markers (README.md: 2 points/mile) - not just
    barely more, but meaningfully denser."""
    frac = 0.28  # ~323 real miles from Springer along the real Katahdin bearing
    end = (
        SPRINGER[0] + (KATAHDIN[0] - SPRINGER[0]) * frac,
        SPRINGER[1] + (KATAHDIN[1] - SPRINGER[1]) * frac,
    )
    out_path, _ = _setup(
        tmp_path,
        monkeypatch,
        [SPRINGER, end],
        [("XX/corridor.tif", (-86.0, 33.0, -78.0, 39.0), 1000.0)],
    )

    manifest = export_elevation.main()

    profile = json.loads(out_path.read_text())
    assert len(profile) > export_elevation.HALF_MILE_MARKER_COUNT * 2, (
        "a corridor-scale synthetic line should produce far more sample points "
        "than the sparse half-mile markers, not just barely clear the bar"
    )
    assert manifest["point_count"] == len(profile)


# --- ordering ------------------------------------------------------------


def test_export_elevation_points_are_ordered_by_distance_along_trail(tmp_path, monkeypatch):
    out_path, _ = _setup(
        tmp_path,
        monkeypatch,
        [(-74.0, 41.0), (-73.9, 41.05), (-73.8, 41.1)],
        [("XX/tile.tif", (-74.2, 40.9, -73.6, 41.3), 800.0)],
    )

    export_elevation.main()

    profile = json.loads(out_path.read_text())
    distances = [p["distance_mi"] for p in profile]
    assert len(distances) > 1
    assert distances == sorted(distances)
    assert len(distances) == len(set(distances)), "sample points should be strictly increasing, not repeat a distance"


def test_export_elevation_orders_disconnected_centerline_segments_by_trail_direction_even_when_reversed():
    """Real-data gotcha confirmed against the actual centerline.geojson
    (2026-07-28): merging the real 3,025 segments does NOT collapse into one
    connected LineString - it merges into 558 disconnected pieces (114 of
    them under ~10m long), since real segment endpoints don't always touch
    exactly, and there's no explicit trail-sequence field to order pieces by.
    ordered_oriented_parts must (a) put disconnected pieces into south-to-
    north order and (b) flip around any piece whose own raw coordinate order
    happens to run north-to-south - not just trust MultiLineString.geoms'
    arbitrary order or a piece's original digitizing direction."""
    southern_piece = LineString([(-84.0, 35.0), (-83.9, 35.1)])
    northern_piece_reversed = LineString([(-80.0, 40.1), (-80.1, 40.0)])  # coords run north -> south
    merged = MultiLineString([northern_piece_reversed, southern_piece])  # supplied out of trail order too

    ordered = export_elevation.ordered_oriented_parts(merged)

    assert len(ordered) == 2
    assert ordered[0].coords[0] == pytest.approx((-84.0, 35.0))  # southern piece comes first
    # the northern piece must be reoriented to start at its own southern end
    assert ordered[1].coords[0] == pytest.approx((-80.1, 40.0))
    assert ordered[1].coords[-1] == pytest.approx((-80.0, 40.1))


# --- cross-part gap diagnostic (logging only - does not affect sampling) ---


def test_measure_cross_part_gaps_sums_and_maxes_known_synthetic_gaps():
    """Pure-function test (no DuckDB/rasterio/filesystem involved) against a
    hand-computable answer: three already-in-meters parts with a 30m gap
    between the first pair (part_a ends at x=100, part_b starts at x=130)
    and a 40m gap between the second pair (part_b ends at x=200, part_c
    starts at x=240). sample_points_along_parts() never adds this real gap
    distance to distance_mi (see its docstring) - this asserts exactly what
    that leaves out: a 70m total across both gaps, and a 40m max single
    gap, not the two conflated into one number."""
    part_a = LineString([(0, 0), (100, 0)])
    part_b = LineString([(130, 0), (200, 0)])
    part_c = LineString([(240, 0), (300, 0)])

    total_gap_m, max_gap_m = export_elevation.measure_cross_part_gaps([part_a, part_b, part_c])

    assert total_gap_m == pytest.approx(70.0)
    assert max_gap_m == pytest.approx(40.0)


# --- DEM coverage gaps -----------------------------------------------------


def test_export_elevation_handles_a_gap_in_dem_coverage_without_crashing(tmp_path, monkeypatch):
    """The line runs well past the synthetic DEM tile's extent - points out
    there must come back with a null elevation (kept, not dropped, so the
    distance axis a client-side chart draws from stays continuous), and the
    run must not crash."""
    out_path, _ = _setup(
        tmp_path,
        monkeypatch,
        [(-74.0, 41.0), (-73.0, 41.5)],
        [("XX/tile.tif", (-74.1, 40.9, -73.6, 41.3), 900.0)],  # only covers the western half of the line
    )

    manifest = export_elevation.main()  # should not raise

    profile = json.loads(out_path.read_text())
    elevations = [p["elevation_ft"] for p in profile]
    assert any(e is None for e in elevations), "points past the DEM tile's extent should be null, not crash the run"
    assert any(e is not None for e in elevations), "points within DEM coverage should still get a real value"
    assert manifest["point_count"] == len(profile)


def test_export_elevation_manifest_reports_null_elevation_count_and_percentage(tmp_path, monkeypatch):
    """LAUNCH_CHECKLIST.md currently claims '0% DEM gaps', but nothing was
    counting that fraction run-over-run, so a regression from 0% could pass
    unnoticed. The manifest (not just a transient print line, so it's
    diffable run-over-run) must carry both how many and what percentage of
    points came back with a null elevation_ft for this real, correctly-
    handled DEM coverage gap - reusing the same partial-coverage fixture as
    test_export_elevation_handles_a_gap_in_dem_coverage_without_crashing,
    which already confirms it produces some null points."""
    out_path, manifest_path = _setup(
        tmp_path,
        monkeypatch,
        [(-74.0, 41.0), (-73.0, 41.5)],
        [("XX/tile.tif", (-74.1, 40.9, -73.6, 41.3), 900.0)],  # only covers the western half of the line
    )

    manifest = export_elevation.main()

    profile = json.loads(out_path.read_text())
    expected_count = sum(1 for p in profile if p["elevation_ft"] is None)
    assert expected_count > 0, "fixture must actually produce some null points, or this test proves nothing"
    expected_pct = expected_count / len(profile) * 100

    assert manifest["null_elevation_count"] == expected_count
    assert manifest["null_elevation_pct"] == pytest.approx(expected_pct, abs=0.01)

    on_disk_manifest = json.loads(manifest_path.read_text())
    assert on_disk_manifest["null_elevation_count"] == expected_count
    assert on_disk_manifest["null_elevation_pct"] == pytest.approx(expected_pct, abs=0.01)


def test_export_elevation_samples_correctly_from_a_dem_tile_in_a_non_wgs84_projection(tmp_path):
    """Real DEM tiles are delivered in their own native per-LiDAR-project UTM
    zone (fetch_elevation.py's docstring: tile filenames like
    USGS_1M_17_x54y410_... even encode the zone digit) - the same real-world
    fact spike_raster_mosaic.py already had to handle for the topo quads via
    a WarpedVRT. ElevationSampler must reproject before sampling, not assume
    every downloaded tile is already in EPSG:4326."""
    wgs84_bounds = (-84.3, 34.5, -84.0, 34.8)
    utm_crs = "EPSG:32617"
    utm_bounds = transform_bounds("EPSG:4326", utm_crs, *wgs84_bounds)

    tile_path = tmp_path / "GA" / "utm_tile.tif"
    tile_path.parent.mkdir(parents=True)
    transform = from_bounds(*utm_bounds, 40, 40)
    profile = {
        "driver": "GTiff",
        "height": 40,
        "width": 40,
        "count": 1,
        "dtype": "float32",
        "crs": utm_crs,
        "transform": transform,
        "nodata": -9999.0,
    }
    with rasterio.open(tile_path, "w", **profile) as dst:
        dst.write(np.full((1, 40, 40), 1234.5, dtype="float32"))

    tile_index = export_elevation.index_elevation_tiles(_index_for_dir(tmp_path, tmp_path))
    sampler = export_elevation.ElevationSampler(tile_index)
    try:
        value = sampler.sample(-84.15, 34.65)  # well inside wgs84_bounds
    finally:
        sampler.close()

    assert value == pytest.approx(1234.5, abs=1.0)


# --- manifest / hashing ----------------------------------------------------


def test_export_elevation_writes_a_sha256_hash_for_the_profile_artifact(tmp_path, monkeypatch):
    import hashlib

    out_path, manifest_path = _setup(
        tmp_path,
        monkeypatch,
        [(-74.0, 41.0), (-73.9, 41.05)],
        [("XX/tile.tif", (-74.1, 40.9, -73.6, 41.3), 700.0)],
    )

    manifest = export_elevation.main()

    on_disk = out_path.read_bytes()
    expected_hash = hashlib.sha256(on_disk).hexdigest()
    assert manifest["sha256"] == expected_hash
    assert len(manifest["sha256"]) == 64

    on_disk_manifest = json.loads(manifest_path.read_text())
    assert on_disk_manifest["sha256"] == expected_hash
    assert on_disk_manifest["path"] == str(out_path)


# --- part boundaries in the artifact (#559) ---------------------------------


def test_a_sample_carries_the_piece_it_came_from():
    """The walk is the only place that knows where the seams are, so it is the
    only place that can say. Everything downstream reads the artifact."""
    from shapely.geometry import LineString

    parts = [LineString([(0, 0), (100, 0)]), LineString([(500, 0), (600, 0)])]

    samples = export_elevation.sample_points_along_parts(parts, 25.0)

    assert [part for _d, _pt, part in samples] == [0, 0, 0, 0, 0, 1, 1, 1, 1]


def test_only_the_first_sample_of_a_piece_is_marked(tmp_path, monkeypatch):
    """558 markers rather than 139,218 `part` indices: the same information at
    a fraction of the bytes on a file hikers download over trailhead signal."""
    from shapely.geometry import LineString

    parts = [LineString([(0, 0), (50, 0)]), LineString([(500, 0), (550, 0)])]
    samples = export_elevation.sample_points_along_parts(parts, 25.0)

    records = []
    previous = None
    for _d, _pt, part in samples:
        record = {}
        if part != previous:
            record["part_start"] = True
            previous = part
        records.append(record)

    # Three samples on the first 50 m piece (0, 25, 50), then `pending` carries
    # 25 m into the second, which therefore yields two (25, 50) rather than
    # three - the interval is continuous across the seam even though the trail
    # is not, which is the whole reason the marker has to be explicit.
    assert [bool(r.get("part_start")) for r in records] == [True, False, False, True, False]


def test_the_very_first_sample_is_marked_too():
    """Breaking a run before the first sample is a no-op, so this is about
    uniformity: a consumer writes "new run at every part_start" without
    special-casing index 0."""
    from shapely.geometry import LineString

    samples = export_elevation.sample_points_along_parts([LineString([(0, 0), (50, 0)])], 25.0)

    assert samples[0][2] == 0


# --- marker calibration of the mile axis (#652) ------------------------------


def test_marker_calibration_orders_pieces_by_atc_measure_not_geography():
    """The straight-axis sort put 18 stretches more than ten miles out of
    place because geography is not trail order (#652). ATC's `Measure` field
    is trail order, so a piece the markers put earlier comes earlier - even
    when it sits further along any straight geographic axis."""
    import numpy as np
    from shapely.geometry import Point

    far_north = LineString([(0, 100000), (0, 110000)])
    near_springer = LineString([(0, 0), (0, 10000)])
    marker_points = [Point(0, 105000), Point(0, 5000)]
    marker_miles = np.array([1.0, 50.0])  # ATC: the northern piece is mile ~1

    calibrated = export_elevation.calibrate_parts_to_markers([near_springer, far_north], marker_points, marker_miles)

    assert calibrated[0].line.equals(far_north), "the piece ATC marks as mile 1 must come first"
    assert calibrated[1].line.equals(near_springer)


def test_marker_calibration_flips_a_piece_whose_coords_run_against_the_miles():
    """33 real pieces are mis-oriented by the straight-axis heuristic
    (measured 2026-08-18) - the AT's genuine north-south switchbacks. Two
    markers whose Measure falls as the coords advance mean the piece is
    digitized against trail direction, and the calibration must walk it the
    way the miles run."""
    import numpy as np
    from shapely.geometry import Point

    mile_m = 1609.344
    line = LineString([(0, 0), (10 * mile_m, 0)])
    marker_points = [Point(1 * mile_m, 0), Point(9 * mile_m, 0)]
    marker_miles = np.array([9.0, 1.0])  # measure falls as x grows -> reversed piece

    (calibrated,) = export_elevation.calibrate_parts_to_markers([line], marker_points, marker_miles)

    assert calibrated.line.coords[0] == (10 * mile_m, 0.0)
    assert calibrated.mile_at(0.0) == pytest.approx(0.0)
    assert calibrated.mile_at(calibrated.line.length) == pytest.approx(10.0)


def test_mile_at_interpolates_between_markers_and_extrapolates_at_unit_slope():
    """Between markers, linear interpolation through ATC's own values - so
    where geometry and wheel measure disagree, the published mile agrees
    with the scale closures and ATC updates quote. Past the end markers
    there is nothing to interpolate toward, so the piece's own geometric
    distance carries on at unit slope rather than trusting a fitted slope
    beyond its data."""
    import numpy as np

    mile_m = 1609.344
    part = export_elevation.CalibratedPart(
        LineString([(0, 0), (20 * mile_m, 0)]),
        alongs_mi=np.array([1.0, 3.0]),
        miles=np.array([10.0, 14.0]),  # ATC's scale runs 2x this piece's geometry here
    )

    assert part.mile_at(2.0 * mile_m) == pytest.approx(12.0)  # midway between the markers
    assert part.mile_at(0.5 * mile_m) == pytest.approx(9.5)  # 0.5 mi before the first marker
    assert part.mile_at(4.0 * mile_m) == pytest.approx(15.0)  # 1 mi past the last marker


def test_a_marker_less_piece_is_anchored_from_the_nearest_marker():
    """182 real pieces (7.5 mi in total, none over 0.43 mi) have no marker of
    their own. Anchoring them to the nearest marker bounds their error by the
    marker spacing plus their own length - against the median 7.7 mi the
    uncalibrated axis measured."""
    import numpy as np
    from shapely.geometry import Point

    mile_m = 1609.344
    marked = LineString([(0, 0), (10 * mile_m, 0)])
    tiny = LineString([(10.05 * mile_m, 0), (10.10 * mile_m, 0)])
    marker_points = [Point(1 * mile_m, 0), Point(9 * mile_m, 0)]
    marker_miles = np.array([101.0, 109.0])

    calibrated = export_elevation.calibrate_parts_to_markers([marked, tiny], marker_points, marker_miles)

    assert calibrated[0].line.equals(marked)
    tiny_start = calibrated[1].start_mile
    assert tiny_start == pytest.approx(109.0, abs=1.5), (
        "a marker-less piece must land near its nearest marker's measure, not at a geographic guess"
    )


def test_overlapping_duplicate_geometry_is_published_once(tmp_path, monkeypatch):
    """ORDERING.md's degree-6 nodes: duplicate geometry survives the merge,
    so two pieces can cover the same stretch of trail. Publishing both would
    put the same miles on the axis twice - and their phantom climbing in the
    total twice. The axis keeps the first piece to reach a mile and counts
    what it clipped."""
    true_line = [(-74.0, 41.0), (-73.9, 41.0), (-73.8, 41.0)]
    duplicate_of_east_half = [(-73.9, 41.0003), (-73.8, 41.0003)]  # ~33 m north of the real tread
    out_path, manifest_path = _setup(
        tmp_path,
        monkeypatch,
        [true_line, duplicate_of_east_half],
        [("XX/tile.tif", (-74.2, 40.9, -73.6, 41.3), 800.0)],
        markers_coord_groups=[true_line],  # ATC's markers walk the trail once
    )

    manifest = export_elevation.main()

    profile = json.loads(out_path.read_text())
    distances = [p["distance_mi"] for p in profile]
    assert distances == sorted(distances)
    assert len(distances) == len(set(distances))
    assert manifest["clipped_sample_count"] > 100, "the duplicated ~5 mi must be clipped, not published twice"
    assert distances[-1] < 11.0, "the axis must span the trail once, not the trail plus its duplicate"


def test_the_run_refuses_a_missing_markers_file(tmp_path, monkeypatch):
    """No markers, no axis: silently falling back to the uncalibrated
    projection would be #652 coming back with nothing logging that it did."""
    _setup(
        tmp_path,
        monkeypatch,
        [(-74.0, 41.0), (-73.9, 41.05)],
        [("XX/tile.tif", (-74.1, 40.9, -73.6, 41.3), 700.0)],
    )
    monkeypatch.setattr(export_elevation, "MARKERS_PATH", tmp_path / "not_fetched.geojson")

    with pytest.raises(FileNotFoundError, match="half-mile markers"):
        export_elevation.main()


def test_the_accuracy_gate_refuses_a_drifted_axis():
    """require_marker_agreement is what keeps the calibration honest
    run-over-run: a quietly-degraded axis is worse than the fault it fixed,
    because this time the code claims to be calibrated."""
    good = {
        "holdout_marker_count": 2000,
        "holdout_median_mi": 0.003,
        "holdout_p95_mi": 0.055,
        "holdout_max_mi": 0.497,
    }
    export_elevation.require_marker_agreement(good)  # the real 2026-08-18 figures pass

    drifted = dict(good, holdout_median_mi=7.7)  # the uncalibrated fault's median
    with pytest.raises(SystemExit, match="mis-calibrated"):
        export_elevation.require_marker_agreement(drifted)


def test_the_manifest_carries_the_marker_agreement(tmp_path, monkeypatch):
    """A calibration regression must show in a diff of published metadata,
    not only in a log nobody reads. On a clean synthetic fixture - markers
    generated from the same geometry - the held-out error is essentially
    zero, which also pins that the holdout wiring measures the axis that
    ships rather than some other quantity."""
    _, manifest_path = _setup(
        tmp_path,
        monkeypatch,
        [(-74.0, 41.0), (-73.8, 41.1)],
        [("XX/tile.tif", (-74.2, 40.9, -73.6, 41.3), 900.0)],
    )

    manifest = export_elevation.main()

    assert manifest["marker_holdout_count"] > 0
    assert manifest["marker_holdout_median_mi"] <= 0.01
    assert manifest["marker_holdout_max_mi"] <= export_elevation.MARKER_HOLDOUT_MAX_MI
    on_disk = json.loads(manifest_path.read_text())
    assert on_disk["marker_holdout_median_mi"] == manifest["marker_holdout_median_mi"]
