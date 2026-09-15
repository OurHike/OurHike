"""lib/hike_route_builder.py - forming a route from prose, and refusing to
(#1427).

The synthetic graph from test_lib_trail_graph_route.py: a chain along "Pine
Meadow Trail", a spur, and a loop on "Ridge Loop" - never the real graph
(TESTING.md).

What is pinned is the judgement, not the arithmetic. A route formed from a
description is an INFERENCE about where somebody walked, and every test here
is about the line between one this build may show a hiker and one it may not:
that disagreement with the publisher's own mileage is fatal rather than
cosmetic, that a "Circuit" which doubles back is not a loop, that a published
track is reported on rather than overruled, and that a refusal is a route of
None rather than a faint line.
"""

from __future__ import annotations

import pytest

from lib import trail_graph_route as router
from lib.hike_route_builder import (
    GENERATED,
    GRADE_FAIR,
    GRADE_REJECTED,
    GRADE_STRONG,
    PUBLISHED,
    Step,
    _route_score,
    form_route,
    itinerary,
    normalise_name,
    published_route,
    retrace_ratio,
    track_climb,
    trail_mentions,
    waypoints_from_itinerary,
)
from lib.hikefinder import Track, TrackPoint
from tests.test_lib_trail_graph_route import LAT, LON, STEP, graph_files


@pytest.fixture
def graph(tmp_path):
    root = graph_files(tmp_path)
    return router.load_graph(root / "trail_graph.json", root / "trail_graph_geometry.json", root / "trail_graph_elevation.json")


def hike(**overrides) -> dict:
    base = {
        "id": 7,
        "name": "Pine Meadow and Ridge Loop",
        "route_type": "Circuit",
        "stated_miles": 0.3,
        "start": {"lat": LAT, "lon": LON, "label": "Parking location"},
        "description": ["Follow the Pine Meadow Trail east, then turn onto the Ridge Loop."],
    }
    base.update(overrides)
    return base


def track(points, ele=True) -> Track:
    return Track(name="t", points=[TrackPoint(lat=lat, lon=lon, ele_m=100.0 if ele else None) for lat, lon in points])


def profile(elevations) -> Track:
    """A track carrying these metre elevations, on points that go somewhere.

    The coordinates are incidental - `track_climb` reads elevations alone -
    but they are spread rather than stacked so the fixture is not a shape the
    real corpus never takes.
    """
    return Track(
        name="t",
        points=[TrackPoint(lat=41.0 + index * 0.001, lon=-74.0, ele_m=value) for index, value in enumerate(elevations)],
    )


# --- reading the description ---------------------------------------------------


def test_trail_names_are_read_in_the_order_the_description_names_them():
    """Order is the only thing in a write-up that says which way round the
    walk goes."""
    assert trail_mentions(["Take the Blue Trail, then the Red Trail."]) == ["Blue Trail", "Red Trail"]


def test_a_trail_named_twice_is_one_name():
    assert trail_mentions(["The A.T. Trail climbs. The A.T. Trail descends."]) == ["A.T. Trail"]


def test_names_that_differ_only_in_what_carries_no_identity_are_one_trail():
    """The export writes "the Timp-Torne Trail" where a layer writes
    "Timp-Torne", and ATC writes "Appalachian National Scenic Trail" where a
    hiker writes "Appalachian Trail"."""
    assert normalise_name("the Timp-Torne Trail") == normalise_name("Timp-Torne")
    assert normalise_name("Appalachian National Scenic Trail") == normalise_name("Appalachian Trail")
    assert normalise_name("Pine Meadow Trail") != normalise_name("Ridge Loop")


def test_a_waypoint_is_taken_nearest_the_walk_s_current_position_not_the_car(graph):
    """The trick this module turns on: when a description says "turn onto the
    Ridge Loop", the nearest point on Ridge Loop to WHERE THE WALK IS is the
    junction that sentence means."""
    start = router.nearest_point(graph, LON, LAT, max_off_m=500)
    points, used = waypoints_from_itinerary(graph, start, [Step(name="Ridge Loop", blaze=None)])
    assert [step.name for step in used] == ["Ridge Loop"]
    # Node 2 is where Pine Meadow meets Ridge Loop - not either far end of it.
    assert points[0].at[0] == pytest.approx(LON + 2 * STEP, abs=1e-6)


def test_a_name_no_line_nearby_carries_is_skipped_rather_than_failing_the_hike(graph):
    """Descriptions name road crossings, viewpoint spurs and trails in parks
    whose layer nobody has registered. None of those should cost the route
    its other legs."""
    start = router.nearest_point(graph, LON, LAT, max_off_m=500)
    steps = [Step(name="Nonexistent Trail", blaze=None), Step(name="Ridge Loop", blaze=None)]
    points, used = waypoints_from_itinerary(graph, start, steps)
    assert [step.name for step in used] == ["Ridge Loop"]
    assert len(points) == 1


# --- what stops a route being formed at all ------------------------------------


def test_a_hike_with_no_coordinate_forms_nothing_and_says_why(graph):
    result = form_route(graph, hike(start=None))
    assert result.grade == GRADE_REJECTED
    assert result.route is None
    assert "nowhere to start from" in " ".join(result.problems)


def test_a_trailhead_far_off_every_line_forms_nothing(graph):
    """31 of the export's 385 sit here, and they are mostly New Jersey's state
    and county parks - a missing layer, not a bad coordinate."""
    result = form_route(graph, hike(start={"lat": LAT + 1.0, "lon": LON + 1.0, "label": "Parking location"}))
    assert result.grade == GRADE_REJECTED
    assert "not in the layers registered here" in " ".join(result.problems)


def test_a_description_naming_no_trail_this_build_draws_forms_nothing(graph):
    result = form_route(graph, hike(description=["Walk uphill on the Nonexistent Trail for a while."]))
    assert result.grade == GRADE_REJECTED
    assert "match a line within" in " ".join(result.problems)


# --- the checks that decide whether a formed route may be shown ----------------


def test_a_formed_route_is_marked_generated_and_carries_its_ends_snapped(graph):
    result = form_route(graph, hike())
    assert result.provenance == GENERATED
    if result.ships:
        for lon, lat in result.ends:
            assert router.nearest_point(graph, lon, lat, max_off_m=1.0) is not None


def test_a_length_that_disagrees_with_the_publisher_by_half_is_fatal(graph):
    """Not a caution. There is no reading under which a walk measuring a
    fifth of what its own page states is the walk that page describes, and no
    way to tell which half is wrong."""
    result = form_route(graph, hike(stated_miles=40.0))
    assert result.grade == GRADE_REJECTED
    assert result.route is None and result.ends == []
    assert "too far apart to be the same walk" in " ".join(result.problems)


def test_a_length_that_disagrees_mildly_is_kept_but_capped_at_fair(graph):
    formed = form_route(graph, hike(stated_miles=0.3))
    if formed.miles is None:
        pytest.skip("this synthetic graph formed no route to grade")
    result = form_route(graph, hike(stated_miles=formed.miles * 1.3))
    assert result.grade == GRADE_FAIR
    assert result.ships


def test_a_circuit_that_doubles_back_on_itself_is_not_a_loop(graph):
    """The single most likely way this module goes wrong: the waypoints leave
    the walk short of halfway round, so the only way home is the way it came.
    That is an out-and-back, whatever the page calls it."""
    formed = form_route(graph, hike(route_type="Circuit", description=["Take the Spur Trail."]))
    if formed.retrace_ratio is None:
        pytest.skip("no route formed on this synthetic graph")
    assert formed.retrace_ratio > 0.4
    assert formed.grade == GRADE_REJECTED


def test_retrace_is_priced_in_metres_walked_rather_than_edges_counted(graph):
    """An edge is whatever length the survey made it; counting them would let
    fifty short edges outvote one long one."""
    start = router.nearest_point(graph, LON, LAT, max_off_m=500)
    far = router.nearest_point(graph, LON + 3 * STEP, LAT, max_off_m=500)
    there_and_back = router.close_the_loop(graph, [start, far])
    assert retrace_ratio(there_and_back) == pytest.approx(0.5, abs=0.01)
    assert retrace_ratio(router.route_between(graph, start, far)) == pytest.approx(0.0, abs=1e-9)


def test_a_rejected_route_carries_no_line_at_all(graph):
    """FEATURES.md's rule on the paths that can hurt somebody: a route this
    module cannot stand behind must be absent, not faint."""
    result = form_route(graph, hike(stated_miles=40.0))
    assert result.ships is False
    assert result.to_dict()["ends"] == []


# --- the published track is checked, never overruled ---------------------------


def test_a_published_track_is_marked_published_and_measured_on_its_own_points():
    result = published_route({"id": 1, "stated_miles": 1.38, "route_type": "Shuttle"}, track([(41.0, -74.0), (41.02, -74.0)]))
    assert result.provenance == PUBLISHED
    assert result.grade == GRADE_STRONG
    assert result.ships
    assert result.miles == pytest.approx(1.38, abs=0.05)


def test_a_track_whose_length_disagrees_with_the_page_is_reported_not_rejected():
    """THE ASYMMETRY THAT MATTERS. A generated route disagreeing with the
    stated mileage is rejected, because the inference is the weaker claim. A
    published track disagreeing is not: what is established is that one of the
    publisher's own two figures is wrong, and the line the publisher drew is
    not the likelier candidate."""
    result = published_route({"id": 1, "stated_miles": 9.0, "route_type": "Shuttle"}, track([(41.0, -74.0), (41.02, -74.0)]))
    assert result.grade == GRADE_FAIR
    assert result.ships
    assert "the publisher's own two figures disagree" in " ".join(result.problems)


def test_a_track_of_fewer_than_two_points_is_not_a_route():
    result = published_route({"id": 1, "stated_miles": 2.0}, track([(41.0, -74.0)]))
    assert result.grade == GRADE_REJECTED
    assert result.ships is False


def test_a_missing_track_file_is_a_rejection_with_a_reason_rather_than_a_crash():
    result = published_route({"id": 1, "stated_miles": 2.0}, None)
    assert result.grade == GRADE_REJECTED
    assert "fewer than two points" in " ".join(result.problems)


def test_a_page_calling_itself_a_circuit_whose_track_does_not_close_is_flagged():
    result = published_route({"id": 1, "stated_miles": 1.38, "route_type": "Circuit"}, track([(41.0, -74.0), (41.02, -74.0)]))
    assert result.grade == GRADE_FAIR
    assert "ends sit" in " ".join(result.problems)


def test_a_closed_track_is_recognised_as_closed():
    loop = track([(41.0, -74.0), (41.01, -74.0), (41.01, -74.01), (41.0, -74.0)])
    result = published_route({"id": 1, "stated_miles": 2.3, "route_type": "Circuit"}, loop)
    assert result.closed is True


def test_a_published_track_ships_on_its_ends_although_it_has_no_graph_route():
    """The two roads fill different fields: a generated route carries a
    `route` measured over the graph, a published one only the track's own
    points. Testing `route` graded every published track as not shipping."""
    result = published_route({"id": 1, "stated_miles": 1.38, "route_type": "Shuttle"}, track([(41.0, -74.0), (41.02, -74.0)]))
    assert result.route is None
    assert result.ships is True


# --- the climb along a published track (#1451) ---------------------------------
#
# THESE TRACKS WERE DRAWN, NOT WALKED, so their elevations are DEM samples and
# do not wobble: 110 of the 113 are gpx.studio files, 2 of 113 carry any
# timestamp, and consecutive `<ele>` values land on exact 0.25 m multiples with
# a median step of 0.75-1.75 m. A `TRACK_CLIMB_STEP_M = 3.0` stood in front of
# this function until 2026-09-15 to remove a wobble that is not there, and cost
# a measured 15.2% of the median track's gain. Understating climb is the
# direction that gets a hiker caught by the dark, so these are on a safety path
# and the fixtures below are shaped like the real data rather than like a unit.


def test_a_rolling_profile_keeps_every_rise_although_no_single_step_is_large():
    """THE DEFECT #1451 NAMES, at its sharpest. A trail that rolls - up two
    metres, down two, up two - gains real height a hiker really climbs. Under
    the old 3 m threshold not one of those steps counted, so this same profile
    reported a flat zero. The fixture's steps are all well inside the 0.75-1.75 m
    median the real corpus carries, which is why the loss was 15% and not 1%."""
    gain, loss = track_climb(profile([100.0, 102.0, 100.0, 102.0, 100.0, 102.0]))
    assert gain == pytest.approx(6.0 * 3.280839895)
    assert loss == pytest.approx(4.0 * 3.280839895)


def test_a_quantised_climb_is_reported_at_the_height_its_own_points_state():
    """A monotone climb sampled off a raster, in the 0.25 m multiples the real
    files carry. The answer is arithmetic over the points and nothing is
    withheld: 3.5 m gained, no loss."""
    gain, loss = track_climb(profile([10.0, 10.75, 11.75, 12.0, 13.5]))
    assert gain == pytest.approx(3.5 * 3.280839895)
    assert loss == 0.0


def test_the_figure_never_reads_lower_than_the_points_themselves_state():
    """The invariant the threshold broke, pinned so a future smoothing step
    cannot quietly reintroduce it. A threshold can only ever REMOVE gain, and
    removing gain is the unsafe direction - so whatever this function grows
    later, it may not report less climb than the elevations it was handed."""
    elevations = [100.0, 100.5, 101.75, 101.0, 104.25, 103.0, 106.5]
    rises = sum(b - a for a, b in zip(elevations, elevations[1:]) if b > a)
    gain, _ = track_climb(profile(elevations))
    assert gain == pytest.approx(rises * 3.280839895)
    assert gain >= rises * 3.280839895


def test_a_track_with_no_elevation_at_all_is_absent_rather_than_flat():
    """Absent has to stay distinguishable from flat: a hiker deciding whether
    they beat the dark is better served by no figure than by a zero nobody
    stands behind."""
    assert track_climb(Track(name="t", points=[TrackPoint(lat=41.0, lon=-74.0, ele_m=None)] * 4)) is None
    assert track_climb(None) is None


def test_one_measured_point_is_not_enough_to_state_a_climb():
    assert track_climb(profile([100.0])) is None


# --- reading a description as an itinerary (#1427 follow-up) -------------------


def test_a_step_carries_a_name_a_colour_or_both():
    steps = itinerary(
        [
            "From the parking area, follow the red-blazed Butler Trail into the woods.",
            "Head into the woods on a blue-blazed trail, then follow the white blazes of the Appalachian Trail.",
            "Turn onto the Timp-Torne Trail.",
        ],
        nameless=True,
    )
    assert [(s.name, s.blaze) for s in steps] == [
        ("Butler Trail", "Red"),
        (None, "Blue"),
        ("Appalachian Trail", "White"),
        ("Timp-Torne Trail", None),
    ]


def test_a_nameless_blaze_step_is_the_case_nothing_else_could_place():
    """ "head into the woods on a blue-blazed trail" names no trail at all, and
    before the blaze patterns landed this module saw nothing here."""
    steps = itinerary(["Head into the woods on a blue-blazed trail."], nameless=True)
    assert len(steps) == 1
    assert steps[0].name is None and steps[0].blaze == "Blue"


def test_a_trail_named_twice_with_and_without_its_colour_is_one_step():
    """Keying a step on the name AND the colour made "the white-blazed
    Appalachian Trail" and a later bare "Appalachian Trail" into two steps,
    which put a second waypoint on a trail the walk was already on."""
    steps = itinerary(["Follow the white-blazed Appalachian Trail north.", "The Appalachian Trail then descends."])
    assert len(steps) == 1


def test_a_colour_this_build_cannot_place_yields_no_step():
    """A blaze word narrows the candidates or it is not worth having; silver
    is not in the graph's vocabulary, so it narrows nothing."""
    assert itinerary(["Follow the silver-blazed trail."], nameless=True) == []


def test_a_blaze_only_matches_a_line_of_that_colour_and_a_name_does_not_have_to(graph):
    """A named step is matched on its name and the colour only breaks ties,
    because 398,882 of the graph's 631,915 edges carry `Unknown` - demanding
    the colour agree would throw away the right trail whenever its surveyor
    recorded none."""
    start = router.nearest_point(graph, LON, LAT, max_off_m=500)
    points, used = waypoints_from_itinerary(graph, start, [Step(name=None, blaze="Yellow")])
    assert [(s.name, s.blaze) for s in used] == [(None, "Yellow")]
    assert graph.edges[points[0].edge_index]["blaze_color"] == "Yellow"


def test_the_search_may_drop_a_step_the_description_only_mentions(graph):
    """THE REASON THE SEARCH EXISTS. Measured over the 113 ground-truth hikes,
    a published track walks a median of 3 distinct trails while the parser finds
    6 steps in the same description - a write-up names the trails you cross and
    decline as readily as the ones you walk. A greedy walk has to take all six;
    this one may take the subset that fits the publisher's own mileage."""
    walk = hike(route_type="Shuttle", stated_miles=0.05, description=["Take the Spur Trail, then the Ridge Loop."])
    result = form_route(graph, walk)
    if result.route is None:
        pytest.skip("no route formed on this synthetic graph")
    assert result.checks["steps_kept"] <= result.checks["steps_proposed"]


def test_the_score_prefers_the_walk_that_matches_the_publishers_mileage(graph):
    start = router.nearest_point(graph, LON, LAT, max_off_m=500)
    near = router.nearest_point(graph, LON + STEP, LAT, max_off_m=500)
    far = router.nearest_point(graph, LON + 3 * STEP, LAT, max_off_m=500)
    short, long = router.route_between(graph, start, near), router.route_between(graph, start, far)
    stated = long.miles
    assert _route_score(long, stated, 1, False, 1.0) > _route_score(short, stated, 1, False, 1.0)
