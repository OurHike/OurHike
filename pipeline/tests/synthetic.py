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
