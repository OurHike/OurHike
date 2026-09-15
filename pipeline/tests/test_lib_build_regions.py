"""The build's shape, as named regions (#1458).

What is under test is the part that decides how much ground the offline
basemap build considers - so every test here is about the direction the
errors run. A region that comes back SMALLER than the lines it was built
from is a hiker in a city with no map and nothing failing; a region that
comes back EMPTY is the same thing, silently, which is why two of these
assert on a refusal rather than on a shape.
"""

import json
import math

import pytest
from shapely.geometry import LineString, Point, box, shape

from lib.build_regions import (
    REGION_BUFFER_KM,
    buffer_km,
    combined,
    lines_of,
    region_from_layers,
)

# A short line through Prospect Park, Brooklyn - inside neither the A.T.
# corridor nor any cell the basemap build covered before this change.
BROOKLYN = [[-73.9700, 40.6600], [-73.9650, 40.6650]]


def _layer(path, coordinates_list):
    features = [
        {"type": "Feature", "properties": {}, "geometry": None if c is None else {"type": "LineString", "coordinates": c}}
        for c in coordinates_list
    ]
    path.write_text(json.dumps({"type": "FeatureCollection", "features": features}))
    return path


def test_the_buffer_is_measured_in_metres_not_degrees():
    """A degree of longitude is 111 km at the equator and about 85 km at New
    York, so a buffer stated in degrees promises different ground at each end
    of the country. The round trip through EPSG:5070 is what makes 3 km mean
    3 km, and lib/corridor.py makes the same trip for the same reason."""
    ring = buffer_km(Point(-73.97, 40.78), 3.0)
    north = shape(ring).bounds[3] - 40.78
    east = shape(ring).bounds[2] - (-73.97)

    # 3 km north is ~0.027 deg of latitude; 3 km east is ~0.036 deg of
    # longitude at this latitude. A degree-buffer would make them equal.
    assert north == pytest.approx(3000 / 110_570, rel=0.02)
    assert east == pytest.approx(3000 / (111_320 * math.cos(math.radians(40.78))), rel=0.05)
    assert east > north


def test_a_region_contains_every_line_it_was_built_from():
    """The one property the build turns on. A clip shape that does not contain
    its own lines is a build that omits the ground it exists to cover."""
    line = LineString(BROOKLYN)
    assert buffer_km(line, REGION_BUFFER_KM).contains(line)


def test_a_feature_with_no_geometry_is_skipped_rather_than_fatal(tmp_path):
    """Nine of the greenway rows carry a geometry object with no coordinates
    and the export already drops them as `no geometry`. A build that fell
    over on them would be the only thing in the pipeline that did."""
    path = _layer(tmp_path / "greenways.geojson", [BROOKLYN, None, []])

    assert lines_of(path) is not None


def test_a_layer_with_nothing_in_it_reads_as_nothing(tmp_path):
    assert lines_of(_layer(tmp_path / "empty.geojson", [])) is None


def test_two_layers_make_one_region(tmp_path):
    parks = _layer(tmp_path / "nyc_parks_trails.geojson", [BROOKLYN])
    greenways = _layer(tmp_path / "nyc_dot_greenways.geojson", [[[-73.99, 40.70], [-73.98, 40.71]]])

    region = region_from_layers([parks, greenways])

    assert region.contains(LineString(BROOKLYN))
    assert region.contains(LineString([[-73.99, 40.70], [-73.98, 40.71]]))


def test_a_missing_layer_refuses_the_build_and_says_which(tmp_path):
    """The failure this refusal exists for is silent, not loud: a region built
    from a layer that was never fetched comes back smaller, the clip shrinks,
    Planetiler succeeds, and the first anybody knows is blank paper in a
    city. Naming the file is the difference between that and a one-line fix."""
    present = _layer(tmp_path / "nyc_parks_trails.geojson", [BROOKLYN])

    with pytest.raises(SystemExit) as caught:
        region_from_layers([present, tmp_path / "nyc_dot_greenways.geojson"])

    assert "nyc_dot_greenways.geojson" in str(caught.value)
    assert "fetch_external_layers" in str(caught.value)


def test_layers_that_are_all_empty_refuse_rather_than_return_nothing(tmp_path):
    """An empty region would union into the clip as nothing at all, which is
    indistinguishable from not having asked for it."""
    with pytest.raises(SystemExit):
        region_from_layers([_layer(tmp_path / "nyc_parks_trails.geojson", [])])


def test_regions_union_into_one_clip_shape():
    """Two regions 40 miles apart today, and a third between them should cost
    nothing extra rather than being refused."""
    whole = combined([box(-75, 40, -74, 41), box(-74, 41, -73, 42)])

    assert whole.contains(Point(-74.5, 40.5))
    assert whole.contains(Point(-73.5, 41.5))


def test_no_regions_is_a_refusal_rather_than_an_empty_clip():
    """An empty clip shape passed to osmium keeps nothing, so a build with no
    region would produce an empty archive and report success."""
    with pytest.raises(SystemExit):
        combined([])
