"""Tests for lib/spurs.py - what a blue-blazed spur actually leads to.

Why this exists
---------------
The lines are already fetched, already blue, already rendered. What was
missing is the relationship: spur LineStrings and shelter/water/viewpoint
Points with nothing connecting them, so the map draws a blue line and cannot
say "this goes to Rocky Run Shelter, 0.2 mi."

Three ways to get that link wrong, and they are what these tests are about:

- Pick the wrong end. `side_trails` coordinate order is not guaranteed to run
  away from the AT, so a naive "last coordinate is the destination" resolves
  half of all spurs against a point on the trail itself.
- Name a destination that is not one. A spur with nothing at its far end is
  the ordinary case for ~12% of them, and inventing a nearest-anything for
  those is worse than saying nothing.
- Drop a spur for being ugly. 60 side trails carry a misspelled literal where
  a domain code belongs; treating those as undecodable loses real shelter
  approaches.
"""

import pytest

from lib.spurs import (
    DESTINATION_MAX_M,
    JUNCTION_MAX_M,
    PointIndex,
    build_centerline_index,
    build_destination_index,
    decode_type,
    distance_m,
    is_spur,
    line_endpoints,
    orient,
    resolve_destination,
)

# A stretch of AT running north, and the real domain shape `Type` decodes
# against.
TRAIL_LAT, TRAIL_LON = 40.0, -75.0
TYPE_DOMAIN = {
    "0": "Access (eg Parking)",
    "1": "Alternate Route",
    "2": "Signficant Non-Blaze",
    "3": "Spur (eg View, Camp)",
    "4": "Other",
    "5": "Unknown",
}


def north(meters):
    """A latitude `meters` north of the trail."""
    return TRAIL_LAT + meters / 111_320.0


def centerline(points=None):
    """A stretch of AT running EAST-WEST, so a spur running north is a fixed
    distance from it no matter how long the spur is. A centerline parallel to
    the spurs would make "how far from the trail" depend on how far along the
    trail ran, which is a property of the fixture rather than of the code."""
    coords = points or [[TRAIL_LON + i * 0.0001, TRAIL_LAT] for i in range(20)]
    return build_centerline_index([{"geometry": {"type": "LineString", "coordinates": coords}}])


def destinations(pois):
    return build_destination_index(pois)


def spur_line(*lonlats):
    return list(lonlats)


# --- Distance --------------------------------------------------------------


def test_distance_is_symmetric():
    assert distance_m(40.0, -75.0, 40.001, -75.001) == pytest.approx(distance_m(40.001, -75.001, 40.0, -75.0))


def test_a_degree_of_latitude_is_about_111_km():
    assert distance_m(40.0, -75.0, 41.0, -75.0) == pytest.approx(111_320, rel=0.01)


def test_a_degree_of_longitude_shrinks_with_latitude():
    """The reason this is not flat Pythagoras on raw degrees. The AT spans 34
    to 46 degrees, across which a longitude degree loses ~15% of its length -
    against a 150 m threshold that is more than 20 m of error."""
    south = distance_m(34.0, -84.0, 34.0, -83.0)
    far_north = distance_m(46.0, -69.0, 46.0, -68.0)

    assert south > far_north


# --- Type decoding ---------------------------------------------------------


def test_a_plain_code_decodes():
    assert decode_type("3", TYPE_DOMAIN) == "3"


def test_an_integer_code_decodes():
    """A JSON round trip loses whether the code was written as 3 or "3", and
    the real downloaded file has been seen both ways."""
    assert decode_type(3, TYPE_DOMAIN) == "3"


def test_the_misspelled_literal_decodes_rather_than_being_dropped():
    """60 real features carry "Signficant Non-Blaze" - missing the second i -
    where the code "2" belongs. Exactly the mess `Blaze` already had. Sixty
    dropped side trails would be sixty missing approaches."""
    assert decode_type("Signficant Non-Blaze", TYPE_DOMAIN) == "2"


def test_the_correctly_spelled_literal_decodes_too():
    """If ATC ever fixes the typo, this must not become the new bug."""
    assert decode_type("Significant Non-Blaze", TYPE_DOMAIN) == "2"


def test_a_domain_name_in_place_of_a_code_decodes():
    assert decode_type("Spur (eg View, Camp)", TYPE_DOMAIN) == "3"


@pytest.mark.parametrize("raw", [None, "", "   ", "not a type"])
def test_an_undecodable_value_returns_none_rather_than_guessing(raw):
    assert decode_type(raw, TYPE_DOMAIN) is None


def test_a_numeric_code_still_decodes_when_the_domain_lookup_failed():
    """The FeatureServer metadata call is tolerated as failable elsewhere in
    this pipeline. Refusing every code on a bad metadata day would drop every
    spur at once."""
    assert decode_type("3", None) == "3"


def test_only_type_three_is_a_spur():
    assert is_spur("3", TYPE_DOMAIN)
    assert not is_spur("0", TYPE_DOMAIN)
    assert not is_spur("1", TYPE_DOMAIN)


# --- Endpoints -------------------------------------------------------------


def test_a_linestring_gives_its_two_ends_as_lat_lon():
    ends = line_endpoints(spur_line([-75.0, 40.0], [-75.0, 40.001], [-75.0, 40.002]))

    assert ends == ((40.0, -75.0), (40.002, -75.0))


def test_a_multilinestring_spans_from_the_first_part_to_the_last():
    """Real side_trails features are MultiLineString - a digitising seam in
    one path, not two trails."""
    ends = line_endpoints([[[-75.0, 40.0], [-75.0, 40.001]], [[-75.0, 40.002], [-75.0, 40.003]]])

    assert ends == ((40.0, -75.0), (40.003, -75.0))


@pytest.mark.parametrize("coordinates", [[], [[-75.0, 40.0]]])
def test_a_line_with_no_two_ends_has_none(coordinates):
    assert line_endpoints(coordinates) is None


# --- Orientation -----------------------------------------------------------


def test_the_end_nearer_the_trail_is_the_junction():
    ends = ((TRAIL_LAT, TRAIL_LON), (north(500), TRAIL_LON))

    junction, far = orient(ends, centerline())

    assert junction == (TRAIL_LAT, TRAIL_LON)
    assert far == (north(500), TRAIL_LON)


def test_orientation_does_not_depend_on_coordinate_order():
    """The failure this function exists for. side_trails is not guaranteed to
    run away from the trail, so trusting the last coordinate resolves half of
    all spurs against a point on the AT itself."""
    forwards = ((TRAIL_LAT, TRAIL_LON), (north(500), TRAIL_LON))
    backwards = ((north(500), TRAIL_LON), (TRAIL_LAT, TRAIL_LON))

    assert orient(forwards, centerline()) == orient(backwards, centerline())


def test_a_line_touching_the_trail_at_both_ends_has_no_destination():
    """That is an alternate route, and ATC codes those as Type=1. If one
    appears under Type=3 anyway, picking whichever end won by a metre would
    name a destination that is just a different bit of the AT."""
    both_ends_on_trail = ((TRAIL_LAT, TRAIL_LON), (TRAIL_LAT, TRAIL_LON + 0.0019))

    assert orient(both_ends_on_trail, centerline()) is None


def test_a_line_touching_the_trail_at_neither_end_has_no_destination():
    """Then its relationship to the trail is not the one this code assumes,
    and neither end is meaningfully the far one."""
    detached = ((north(5000), TRAIL_LON), (north(6000), TRAIL_LON))

    assert orient(detached, centerline()) is None


def test_a_spur_shorter_than_the_junction_radius_still_orients():
    """The regression that motivated ON_TRAIL_M. A spur shorter than
    JUNCTION_MAX_M has both ends within the junction radius by construction
    - at the p50 length of 385 ft both ends clear 100 m - so treating "both
    ends within the radius" as the alternate-route signature refused the
    most common spurs there are. Every fixture spur used to be 300 m, which
    is how this survived: nothing at or below the median length was tested."""
    ends = ((TRAIL_LAT, TRAIL_LON), (north(80), TRAIL_LON))

    junction, far = orient(ends, centerline())

    assert junction == (TRAIL_LAT, TRAIL_LON)
    assert far == (north(80), TRAIL_LON)


def test_a_spur_at_the_first_quartile_length_orients():
    """49 m is the p25 spur (features/SPUR_TRAILS.md): above the ON_TRAIL_M
    bound, so it must resolve - a quarter of all spurs are at or below it."""
    ends = ((TRAIL_LAT, TRAIL_LON), (north(49), TRAIL_LON))

    junction, far = orient(ends, centerline())

    assert junction == (TRAIL_LAT, TRAIL_LON)
    assert far == (north(49), TRAIL_LON)


def test_a_stub_shorter_than_the_on_trail_bound_refuses_rather_than_guesses():
    """Below ON_TRAIL_M, "rejoins the trail" and "ends beside it" are inside
    digitisation noise of each other, so refusing is the honest answer - the
    accepted residual of keeping alternate routes out."""
    ends = ((TRAIL_LAT, TRAIL_LON), (north(20), TRAIL_LON))

    assert orient(ends, centerline()) is None


def test_two_ends_at_the_same_distance_refuse_rather_than_coin_flip():
    ends = ((north(60), TRAIL_LON), (north(60), TRAIL_LON + 0.0019))

    assert orient(ends, centerline()) is None


def test_a_short_spur_ending_on_a_shelter_names_it():
    """The reproduced end-to-end case: an 80 m spur ending exactly on a
    shelter used to publish destination_poi_id: None."""
    line = spur_line([TRAIL_LON, TRAIL_LAT], [TRAIL_LON, north(80)])
    pois = destinations([{"id": "shelter:close", "lat": north(80), "lon": TRAIL_LON}])

    result = resolve_destination(line, centerline(), pois)

    assert result["destination_poi_id"] == "shelter:close"
    assert result["destination_distance_m"] == 0


# --- Destination resolution ------------------------------------------------


def test_a_spur_ending_on_a_shelter_names_it():
    """Half of all real spurs end within a metre of their destination."""
    line = spur_line([TRAIL_LON, TRAIL_LAT], [TRAIL_LON, north(300)])
    pois = destinations([{"id": "shelter:rocky-run", "lat": north(300), "lon": TRAIL_LON}])

    result = resolve_destination(line, centerline(), pois)

    assert result["destination_poi_id"] == "shelter:rocky-run"
    assert result["destination_distance_m"] == 0


def test_the_match_distance_is_published_not_thresholded_away():
    """150 m captures 88% of spurs; 50 m captures 77% with far higher
    confidence, and which to believe is not settled. Publishing the distance
    lets the client present a 1 m match differently from a 140 m one, and lets
    the rule tighten without a 25-minute re-export."""
    line = spur_line([TRAIL_LON, TRAIL_LAT], [TRAIL_LON, north(300)])
    pois = destinations([{"id": "shelter:far", "lat": north(400), "lon": TRAIL_LON}])

    result = resolve_destination(line, centerline(), pois)

    assert result["destination_poi_id"] == "shelter:far"
    assert result["destination_distance_m"] == pytest.approx(100, abs=2)


def test_the_nearest_of_several_candidates_wins():
    line = spur_line([TRAIL_LON, TRAIL_LAT], [TRAIL_LON, north(300)])
    pois = destinations(
        [
            {"id": "shelter:near", "lat": north(310), "lon": TRAIL_LON},
            {"id": "campsite:nearer", "lat": north(302), "lon": TRAIL_LON},
        ]
    )

    assert resolve_destination(line, centerline(), pois)["destination_poi_id"] == "campsite:nearer"


def test_a_spur_leading_nowhere_mapped_says_nothing():
    """~12% of spurs have no POI near their far end - some lead somewhere
    genuinely unmapped, some to a viewpoint ATC has not digitised. Naming a
    nearest-anything for those would be worse than absence."""
    line = spur_line([TRAIL_LON, TRAIL_LAT], [TRAIL_LON, north(300)])
    pois = destinations([{"id": "shelter:elsewhere", "lat": north(3000), "lon": TRAIL_LON}])

    result = resolve_destination(line, centerline(), pois)

    assert result["destination_poi_id"] is None
    assert result["destination_distance_m"] is None


def test_a_long_spur_resolves_as_readily_as_a_short_one():
    """Match quality is unrelated to spur length - a 4.53 mi spur can end a
    metre from its shelter - so nothing here may gate on how far it ran."""
    far = north(7_300)  # ~4.53 miles
    line = spur_line([TRAIL_LON, TRAIL_LAT], [TRAIL_LON, far])
    pois = destinations([{"id": "shelter:remote", "lat": far, "lon": TRAIL_LON}])

    assert resolve_destination(line, centerline(), pois)["destination_poi_id"] == "shelter:remote"


def test_an_unusable_geometry_resolves_to_nothing_rather_than_raising():
    """One real side_trails feature has null geometry. The export must survive
    it the way it already survives it for rendering."""
    result = resolve_destination([], centerline(), destinations([]))

    assert result == {"destination_poi_id": None, "destination_distance_m": None}


def test_the_result_always_has_the_same_keys():
    """So a caller never has to tell "no destination" apart from "this spur
    was never processed"."""
    resolved = resolve_destination(
        spur_line([TRAIL_LON, TRAIL_LAT], [TRAIL_LON, north(300)]),
        centerline(),
        destinations([{"id": "x", "lat": north(300), "lon": TRAIL_LON}]),
    )
    unresolved = resolve_destination([], centerline(), destinations([]))

    assert set(resolved) == set(unresolved)


# --- The index -------------------------------------------------------------


def test_the_index_finds_a_point_just_inside_the_radius():
    index = PointIndex([(north(90), TRAIL_LON, "found")], JUNCTION_MAX_M)

    payload, distance = index.nearest(TRAIL_LAT, TRAIL_LON)

    assert payload == "found"
    assert distance == pytest.approx(90, abs=2)


def test_the_index_rejects_a_point_just_outside_the_radius():
    index = PointIndex([(north(110), TRAIL_LON, "too far")], JUNCTION_MAX_M)

    assert index.nearest(TRAIL_LAT, TRAIL_LON) == (None, None)


def test_the_index_finds_points_across_a_cell_boundary():
    """The bug a grid index exists to have: a candidate one cell over is still
    within the radius, and searching only the query's own cell silently misses
    it. Points are placed to straddle a boundary deliberately."""
    index = PointIndex([(lat, TRAIL_LON, lat) for lat in (north(-40), north(40))], JUNCTION_MAX_M)

    for offset in range(-100, 101, 7):
        payload, _ = index.nearest(north(offset), TRAIL_LON)
        assert payload is not None, f"missed a point {offset} m along"


def test_the_index_stays_correct_at_the_northern_end_of_the_trail():
    """Cell width in longitude is computed where a degree is shortest. Get
    that backwards and the 3x3 search covers less ground than the radius in
    exactly one half of the trail - which would look like Maine's spurs
    quietly resolving worse than Georgia's."""
    katahdin_lat = 45.9044
    index = PointIndex([(katahdin_lat, -68.9214, "baxter")], DESTINATION_MAX_M)

    east = -68.9214 + 100 / (111_320.0 * 0.696)
    payload, distance = index.nearest(katahdin_lat, east)

    assert payload == "baxter"
    assert distance == pytest.approx(100, abs=5)


def test_an_empty_index_finds_nothing_rather_than_raising():
    assert PointIndex([], DESTINATION_MAX_M).nearest(40.0, -75.0) == (None, None)


def test_a_poi_without_coordinates_is_left_out_of_the_index():
    """export_poi.py's records can carry a null lat/lon, and a POI with no
    position cannot be anything's destination."""
    index = build_destination_index(
        [
            {"id": "no-position", "lat": None, "lon": None},
            {"id": "positioned", "lat": TRAIL_LAT, "lon": TRAIL_LON},
        ]
    )

    assert index.nearest(TRAIL_LAT, TRAIL_LON)[0] == "positioned"


def test_the_centerline_index_reads_multilinestring_parts():
    """Both real centerline features named "Appalachian National Scenic Trail"
    are MultiLineString. Reading only LineStrings would index almost none of
    the trail, and then no spur would have a junction at all."""
    index = build_centerline_index(
        [
            {
                "geometry": {
                    "type": "MultiLineString",
                    "coordinates": [[[TRAIL_LON, TRAIL_LAT]], [[TRAIL_LON, north(1000)]]],
                }
            }
        ]
    )

    # Both parts indexed, not just the first.
    assert index.nearest(TRAIL_LAT, TRAIL_LON)[1] == pytest.approx(0, abs=1)
    assert index.nearest(north(1000), TRAIL_LON)[1] == pytest.approx(0, abs=1)
