"""Tests for the pure half of spike_day_planner.py.

The script's data half (read_points, and main()'s whole path) is hardcoded to
real fetched files and is verified by running it, the same way
spike_corridor.py's is - see TESTING.md's "what's intentionally manual-only".
What is tested here is everything that decides an ANSWER rather than reads a
file: the cost function's asymmetry, the shortest-path planner's behaviour
where a greedy pass would go wrong, and the linear referencing that turns a
site into a mile.

A spike's findings are only worth as much as its arithmetic, which is the
whole reason a throwaway script has tests at all.
"""

import math

import pytest
from shapely.geometry import LineString, Point

from spike_day_planner import (
    METERS_PER_MILE,
    Day,
    day_cost,
    day_summary,
    gain_between,
    locate_stops,
    naismith_minutes,
    plan_days,
    spacing_summary,
)

# One mile of flat walking, in Naismith minutes - the unit several tests
# below express a target in.
FLAT_MINUTES_PER_MILE = naismith_minutes(1, 0)


def test_overshooting_the_target_costs_more_than_undershooting_it():
    """The asymmetry is the safety property, not a tuning detail: a hiker who
    arrives early can walk on, and one still two miles out at dusk cannot."""
    assert day_cost(12, 10) > day_cost(8, 10)


def test_a_day_on_target_costs_nothing():
    assert day_cost(10, 10) == 0


def test_one_badly_wrong_day_costs_more_than_several_slightly_wrong_ones():
    """Why the cost is squared. Three days a mile short must be preferable to
    one day three miles short, or the planner has no reason to spread the
    error it cannot avoid."""
    assert day_cost(7, 10) > 3 * day_cost(9, 10)


def test_the_plan_starts_and_ends_where_the_route_does():
    days = plan_days([0.0, 8.0, 17.0, 24.0], target=8.0)

    assert days[0].start_mi == 0.0
    assert days[-1].end_mi == 24.0
    # Every day hands over to the next: a plan with a hole in it is not a plan.
    assert all(a.end_mi == b.start_mi for a, b in zip(days, days[1:]))


def test_evenly_spaced_stops_at_the_target_give_days_at_the_target():
    days = plan_days([0.0, 10.0, 20.0, 30.0], target=10.0)

    assert [day.length_mi for day in days] == [10.0, 10.0, 10.0]


def test_the_planner_spreads_error_rather_than_leaving_a_stub_last_day():
    """The reason this is a shortest path and not a greedy walk.

    Greedy takes the best-looking first day and pays for it at the far end:
    stopping at 9 and 18 leaves two miles of trail and a two-mile final day.
    Balancing into 9 and 11 is worse for one day and far better for the plan,
    which is the trade a hiker would make and a greedy pass cannot see.
    """
    days = plan_days([0.0, 9.0, 18.0, 20.0], target=10.0)

    assert [day.length_mi for day in days] == [9.0, 11.0]


def test_the_planner_stays_under_the_cap_when_the_trail_allows_it():
    """A 20-mile target with nothing legal above 12 miles: the plan gets
    shorter days rather than one long one."""
    days = plan_days([0.0, 5.0, 10.0, 15.0, 20.0], target=20.0, cap_mi=12.0)

    assert max(day.length_mi for day in days) <= 12.0


def test_a_stretch_with_nowhere_to_stop_produces_an_over_cap_day_rather_than_no_plan():
    """Real trail has stretches with no designated site inside any sane day.
    Refusing to plan there would be refusing to describe ground that exists -
    so the day is returned oversized, and day_summary counts it."""
    days = plan_days([0.0, 30.0, 35.0], target=15.0, cap_mi=25.0)

    assert [day.length_mi for day in days] == [30.0, 5.0]
    assert day_summary(days, target_mi=15.0, cap_mi=25.0)["over_cap"] == 1


def test_a_route_with_no_second_stop_has_no_plan():
    assert plan_days([4.2], target=10.0) == []
    assert plan_days([], target=10.0) == []


def test_planning_by_time_shortens_days_over_hard_ground():
    """HIKE_PLANNING.md's Finding 4, as a property rather than an assertion.

    The same stops and the same target, measured two ways: flat walking, and
    ground that costs twice as much per mile. If the time target is doing any
    work at all, the harder ground has to produce more, shorter days - which
    is the thing a distance target structurally cannot do.
    """
    stops = [float(m) for m in range(0, 22, 2)]
    target = naismith_minutes(10, 0)

    flat = plan_days(stops, target, effort=lambda a, b: naismith_minutes(b - a, 0))
    steep = plan_days(stops, target, effort=lambda a, b: 2 * naismith_minutes(b - a, 0))

    assert len(steep) > len(flat)


def test_the_spikes_naismith_copy_agrees_with_the_clients_published_example():
    """WIREFRAMES.md's load-bearing value, and client/src/lib/naismith.ts's
    own test case: 2.6 mi with 640 ft of ascent is 1h 10m once rounded to
    five-minute steps. Pinned here because this file keeps a second copy of
    the formula to measure with, and a spike whose pace model has drifted
    from the app's would be measuring a different trail."""
    minutes = naismith_minutes(2.6, 640)

    assert round(minutes / 5) * 5 == 70


def test_naismith_charges_for_ascent_on_top_of_distance():
    assert naismith_minutes(5, 1000) > naismith_minutes(5, 0)


def test_a_stop_on_a_later_piece_carries_the_earlier_pieces_length():
    """The centerline is 558 disconnected pieces, so a mile is cumulative
    across them in order. A stop on the second piece that ignored the first
    piece's length would land 700 miles south of where it is."""
    parts = [
        LineString([(0, 0), (METERS_PER_MILE, 0)]),
        LineString([(2 * METERS_PER_MILE, 0), (3 * METERS_PER_MILE, 0)]),
    ]

    located = locate_stops(parts, [("Second piece", Point(2.5 * METERS_PER_MILE, 0))], "shelter")

    # One mile of first piece, then half a mile along the second.
    assert located[0].mile == pytest.approx(1.5)
    assert located[0].off_trail_mi == pytest.approx(0)


def test_a_stop_beside_the_trail_reports_how_far_off_it_is():
    """What MAX_OFF_TRAIL_MI is applied to. A site half a mile down a blue
    blaze is a side trip, and counting its spur mileage as trail mileage
    would inflate every day that ended there."""
    parts = [LineString([(0, 0), (METERS_PER_MILE, 0)])]

    located = locate_stops(parts, [("Off to one side", Point(METERS_PER_MILE / 2, 0.25 * METERS_PER_MILE))], "shelter")

    assert located[0].mile == pytest.approx(0.5)
    assert located[0].off_trail_mi == pytest.approx(0.25)


def test_located_stops_come_back_in_trail_order():
    parts = [LineString([(0, 0), (10 * METERS_PER_MILE, 0)])]
    points = [
        ("North", Point(8 * METERS_PER_MILE, 0)),
        ("South", Point(2 * METERS_PER_MILE, 0)),
    ]

    located = locate_stops(parts, points, "campsite")

    assert [stop.name for stop in located] == ["South", "North"]


def test_spacing_reports_the_distribution_not_just_the_mean():
    """An 8-mile average made of 3s and 20s plans very differently from one
    made of 7s and 9s. The spike exists to tell those apart."""
    summary = spacing_summary([0.0, 3.0, 6.0, 26.0])

    assert summary["count"] == 4
    assert summary["gaps"] == 3
    assert summary["mean_mi"] == pytest.approx(26 / 3)
    assert summary["median_mi"] == pytest.approx(3.0)
    assert summary["max_mi"] == pytest.approx(20.0)


def test_spacing_of_a_single_stop_has_no_gaps_to_describe():
    assert spacing_summary([12.0]) == {"count": 1, "gaps": 0}


def test_day_summary_counts_only_days_within_a_fifth_of_the_target():
    days = [Day(0, 10), Day(10, 20), Day(20, 34)]

    summary = day_summary(days, target_mi=10.0)

    assert summary["days"] == 3
    assert summary["within_20pct"] == pytest.approx(2 / 3)
    assert summary["longest_mi"] == 14


def test_day_summary_of_an_empty_plan_says_so_rather_than_dividing_by_zero():
    assert day_summary([], target_mi=10.0) == {"days": 0}


def test_gain_between_counts_only_the_window_asked_for():
    """Inclusive bounds, matching lib/elevation_gain.py's own gain_between -
    a day's ascent has to be measured over exactly the stretch that day
    covers, or the number describes someone else's day."""
    profile = ([0.0, 1.0, 2.0, 3.0], [1000.0, 1500.0, 1500.0, 2000.0])

    assert gain_between(profile, 0.0, 1.0) == pytest.approx(500)
    assert gain_between(profile, 1.0, 3.0) == pytest.approx(500)
    assert gain_between(profile, 0.0, 3.0) == pytest.approx(1000)


def test_gain_between_treats_a_dem_gap_as_a_break_rather_than_a_climb():
    """A null elevation is real missing coverage. Joining across it would
    count a step nobody walked as a climb - the gotcha lib/elevation_gain.py
    exists to hold, asserted here because a day's ascent feeds a day's
    estimated time."""
    profile = ([0.0, 1.0, 2.0], [1000.0, None, 5000.0])

    assert gain_between(profile, 0.0, 2.0) == 0


def test_a_flat_mile_is_about_twelve_minutes():
    """Sanity anchor for the unit the time-target tests are written in:
    5 km/h is 19.3 minutes per mile of horizontal distance."""
    assert math.isclose(FLAT_MINUTES_PER_MILE, 19.31, rel_tol=1e-3)
