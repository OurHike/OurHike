"""The synthetic geometry the suites share, so they share it once.

Not a conftest fixture, deliberately. Some callers are test functions, which
could take a fixture, and some are module-level helpers like
test_export_poi.py's `_write_fixture_sources` - which has forty-odd callers
and would have to grow a parameter threaded through every one of them to
reach a fixture. A plain import reaches both.

Everything here is built in code rather than checked in, per ../../TESTING.md,
and none of it is anywhere near real data.
"""

import json

# A short line in the Hudson Highlands, far from the real centerline.
#
# One definition rather than six. Six suites had declared this identical pair,
# and each one carried a comment naming the others it was matching -
# test_lib_corridor.py's cited three by filename. That comment was doing a
# module import's job by hand: the point of the shared coordinates is that a
# corridor built from them has a known buffered bbox (-76 < lon < -72,
# 39 < lat < 43) and a known area, which several suites assert against.
CENTERLINE_COORDS = [(-74.0, 41.0), (-73.9, 41.1)]


def write_centerline(path, coords=CENTERLINE_COORDS):
    """Write a one-feature centerline.geojson, in the shape the fetchers read.

    Defaults to CENTERLINE_COORDS, so a suite that needs only "a centerline
    exists at this path" says one thing, and a suite testing geometry passes
    its own line.

    One LineString feature, where the real centerline.geojson has thousands.
    Suites that care about the many-features shape - test_export_elevation.py,
    which is about what happens BETWEEN the pieces - build their own rather
    than take a flag here, because that difference is their subject.
    """
    path.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {},
                        "geometry": {
                            "type": "LineString",
                            "coordinates": [[lon, lat] for lon, lat in coords],
                        },
                    }
                ],
            }
        )
    )


def write_half_mile_markers(path, coords=CENTERLINE_COORDS, scale=1.0, interval_mi=0.5):
    """ATC-shaped half-mile markers along a lon/lat line, in the shape of the
    real half_mile_points_from_springer.geojson: Point features whose
    `Measure` is the cumulative mile. The mile axis is calibrated to these
    since #652, so any fixture whose export reaches attach_miles or
    build_profile needs them next to its centerline.

    scale=1 makes ATC's scale agree with the line's geometry; another value
    makes them disagree, which is what the calibration exists to resolve in
    ATC's favour - a suite proving that passes its own scale."""
    from rasterio.warp import transform as _warp_transform
    from shapely.geometry import LineString as _LineString

    meters_per_mile = 1609.344
    xs, ys = _warp_transform("EPSG:4326", "EPSG:5070", [lon for lon, _ in coords], [lat for _, lat in coords])
    line_m = _LineString(list(zip(xs, ys)))
    features = []
    distance = interval_mi * meters_per_mile
    measure = interval_mi
    while distance <= line_m.length:
        pt = line_m.interpolate(distance)
        lon, lat = _warp_transform("EPSG:5070", "EPSG:4326", [pt.x], [pt.y])
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon[0], lat[0]]},
                "properties": {"Measure": round(measure * scale, 3)},
            }
        )
        distance += interval_mi * meters_per_mile
        measure += interval_mi
    path.write_text(json.dumps({"type": "FeatureCollection", "features": features}))
