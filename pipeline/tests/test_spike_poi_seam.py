"""Tests for the arithmetic half of spike_poi_seam.py.

The data half - load_records, and main()'s whole path - reads real fetched
files and is verified by running it, the same way spike_photo_scope.py's and
spike_day_planner.py's are (TESTING.md, "what's intentionally manual-only").

What is tested here is everything that decides an ANSWER: the projection, the
collision test, what site-folding makes reachable, the viewport window, and
the seam rule itself. A spike's findings are worth exactly what its arithmetic
is worth, and this one's arithmetic chooses a constant that decides what the
first map a hiker sees is for.

The load-bearing test in this file is
`test_collision_distance_matches_the_measured_table`. Every number in
features/POI_SITES.md and features/POI_VISIBILITY.md is downstream of the
claim that two pins collide within 615 m at z12, and a projection that
silently used 256 px tiles would be a whole zoom level out while still looking
entirely plausible.
"""

import math

import pytest

from lib.spurs import distance_m
from spike_poi_seam import (
    DAY_MILES,
    ICON_PADDING_PX,
    PIN_FULL_SCALE_ZOOM,
    PIN_MIN_SCALE,
    PLANNING_WINDOW_MILES,
    POI_PIN_SIZE_PX,
    VIEWPORT_H_PX,
    VIEWPORT_W_PX,
    pin_box_px,
    pin_room,
    place,
    reachable,
    screen_miles,
    seam,
    sort_key,
    to_pixels,
    viewport_loads,
)

# The seam every call below is measured at, so a test never depends on the
# constant the spike is computing.
SEAM = 9


def poi(poi_id: str, poi_type: str, lat: float, lon: float, name: str | None = None) -> dict:
    return {"id": poi_id, "poi_type": poi_type, "lat": lat, "lon": lon, "name": name}


# --- the projection -------------------------------------------------------


def test_world_is_512px_at_zoom_zero_not_256():
    """MapLibre's tile grid, which is the one this whole spike is pinned to."""
    x, y = to_pixels(0.0, 0.0, 0)
    assert x == pytest.approx(256.0)
    assert y == pytest.approx(256.0)


def test_the_antimeridian_and_the_prime_meridian_are_a_world_apart():
    left, _ = to_pixels(0.0, -180.0, 3)
    right, _ = to_pixels(0.0, 180.0, 3)
    assert right - left == pytest.approx(512.0 * 2**3)


def test_north_is_up():
    _, north = to_pixels(45.0, 0.0, 10)
    _, south = to_pixels(35.0, 0.0, 10)
    assert north < south


@pytest.mark.parametrize(
    ("zoom", "expected_m"),
    # features/POI_SITES.md §2's measured table, at latitude 40.
    [(12, 615), (13, 307), (14, 154), (15, 77), (16, 38), (17, 19)],
)
def test_collision_distance_matches_the_measured_table(zoom, expected_m):
    """42 px of pin box, converted to ground metres through this projection,
    reproduces the table both design docs reason from.

    Derived rather than asserted: the pixel span comes from to_pixels and the
    ground span from lib/spurs.py's own distance_m, so this fails if either
    the projection or the pin box drifts - which is exactly the pair that
    would otherwise produce a confident, wrong seam.

    AT FULL SIZE, not at the ramped box. That doc's table is a statement about
    a 42 px pin, and feeding it the seam-zoom box would silently compare two
    different things and read 392 m where the doc says 615.
    """
    full_box = POI_PIN_SIZE_PX + ICON_PADDING_PX * 2
    assert full_box == pin_box_px(PIN_FULL_SCALE_ZOOM, SEAM)

    lat, lon = 40.0, -75.0
    one_degree_px = to_pixels(lat, lon + 1.0, zoom)[0] - to_pixels(lat, lon, zoom)[0]
    metres_per_px = distance_m(lat, lon, lat, lon + 1.0) / one_degree_px
    # Rounded to the metre, which reproduces the doc's table exactly rather
    # than approximately - all six rows agree on the nose.
    assert round(metres_per_px * full_box) == expected_m


# --- the collision test ---------------------------------------------------


def test_pins_closer_than_the_box_collide_and_one_is_dropped():
    lat, lon = 40.0, -75.0
    world = 512.0 * 2**14
    # Half a box east: inside the collision distance in both axes.
    nudge = (pin_box_px(14, SEAM) / 2) * 360.0 / world
    drawn = place([poi("a", "shelter", lat, lon), poi("b", "shelter", lat, lon + nudge)], 14, SEAM)
    assert len(drawn) == 1


def test_pins_further_apart_than_the_box_both_place():
    lat, lon = 40.0, -75.0
    world = 512.0 * 2**14
    gap = (pin_box_px(14, SEAM) + 1) * 360.0 / world
    drawn = place([poi("a", "shelter", lat, lon), poi("b", "shelter", lat, lon + gap)], 14, SEAM)
    assert drawn == {"a", "b"}


def test_priority_decides_the_survivor_not_input_order():
    """POI_PRIORITY is a safety ordering. A viewpoint listed first must not
    take the slot a water source wanted, and an id that sorts earlier must not
    either."""
    lat, lon = 40.0, -75.0
    contested = [poi("a_viewpoint", "viewpoint", lat, lon), poi("z_water", "water", lat, lon)]
    assert place(contested, 14, SEAM) == {"z_water"}
    assert place(list(reversed(contested)), 14, SEAM) == {"z_water"}


def test_an_unknown_type_sorts_last_rather_than_crashing():
    assert sort_key({"poi_type": "something_new"}) > sort_key({"poi_type": "viewpoint"})


def test_placement_is_deterministic_across_runs():
    """Ties inside one priority break by id. Without that the whole table
    wobbles between runs, which is very hard to notice and impossible to
    review."""
    points = [poi(f"p{i}", "viewpoint", 40.0, -75.0 + i * 1e-5) for i in range(40)]
    assert place(points, 13, SEAM) == place(list(reversed(points)), 13, SEAM)


# --- what site-folding makes reachable ------------------------------------


def test_a_member_rides_its_anchors_pin():
    """The whole claim of features/POI_SITES.md. The privy is 40 m from its
    shelter, so at z14 (154 m collision) it could never place its own pin -
    and it is still reachable, because the shelter's pin stands for it."""
    shelter = poi("s", "shelter", 40.0, -75.0, "Mt. Algo Shelter")
    privy = poi("p", "privy", 40.00036, -75.0, "Mt. Algo Shelter Privy")
    reach = reachable([shelter, privy], 14, SEAM)
    assert reach == {"s", "p"}
    # ...and the privy is genuinely un-placeable on its own terms.
    assert place([shelter, privy], 14, SEAM) == {"s"}


def test_a_member_whose_anchor_lost_is_not_reachable():
    """A site pin is still a pin and can still lose a collision. When it does
    it takes its members with it, and the spike must not credit them.

    The water sits 100 m off - beyond lib/poi_sites.py's 60 m proximity gate,
    so it stays a competitor rather than becoming a fourth member of the site,
    and inside z14's 154 m collision distance, so it is a competitor that
    wins. Putting it on top of the shelter would have folded it in and quietly
    tested nothing.
    """
    lat, lon = 40.0, -75.0
    water = poi("w", "water", lat + 0.0009, lon)
    shelter = poi("s", "shelter", lat, lon, "Mt. Algo Shelter")
    privy = poi("p", "privy", lat + 0.00036, lon, "Mt. Algo Shelter Privy")
    assert 60 < distance_m(lat + 0.0009, lon, lat, lon) < 154
    assert reachable([water, shelter, privy], 14, SEAM) == {"w"}


def test_folding_never_reports_more_than_exists():
    points = [poi(f"p{i}", "viewpoint", 40.0 + i * 0.5, -75.0) for i in range(6)]
    assert reachable(points, 12, SEAM) <= {p["id"] for p in points}


# --- the viewport window --------------------------------------------------


def test_a_load_counts_the_centre_waypoint_itself():
    """A lone waypoint is a screen with one waypoint on it, not an empty one."""
    assert viewport_loads([poi("a", "shelter", 40.0, -75.0)], 12) == [1]


def test_the_window_excludes_what_is_off_screen():
    """Two waypoints a degree of latitude apart at z12 are nowhere near one
    screen, so neither sees the other."""
    far = [poi("a", "shelter", 40.0, -75.0), poi("b", "shelter", 41.0, -75.0)]
    assert viewport_loads(far, 12) == [1, 1]


def test_the_window_is_390_by_700_and_not_square():
    """A tall window is the phone, and a square one would report a different
    number for the same trail.

    300 px is the gap that tells them apart: inside the 350 px half-height, so
    two waypoints that far apart north-south share a screen; outside the 195 px
    half-width, so the same gap east-west does not.
    """
    lat, lon = 40.0, -75.0
    zoom = 13
    world = 512.0 * 2**zoom
    gap_px = 300.0
    assert VIEWPORT_W_PX / 2 < gap_px < VIEWPORT_H_PX / 2

    lon_apart = lon + gap_px * 360.0 / world
    # The inverse of to_pixels' y, so the gap is exact rather than walked to.
    y_apart = to_pixels(lat, lon, zoom)[1] - gap_px
    lat_apart = math.degrees(math.atan(math.sinh(math.pi * (1.0 - 2.0 * y_apart / world))))

    north_south = viewport_loads([poi("a", "shelter", lat, lon), poi("b", "shelter", lat_apart, lon)], zoom)
    east_west = viewport_loads([poi("a", "shelter", lat, lon), poi("b", "shelter", lat, lon_apart)], zoom)
    assert north_south == [2, 2]
    assert east_west == [1, 1]


# --- the seam rule ---------------------------------------------------------


def test_a_pin_is_smaller_at_the_seam_than_at_walking_zoom():
    """POI_ICON_SIZE_EXPRESSION's ramp, which the first cut of this spike
    ignored entirely - it used the full-size 42 px box at every zoom. That
    understates what fits by a lot exactly where it matters: 27 px at the seam
    against 42, so a column holds 26 pins rather than 16."""
    assert pin_box_px(SEAM, SEAM) < pin_box_px(PIN_FULL_SCALE_ZOOM, SEAM)
    assert pin_box_px(SEAM, SEAM) == pytest.approx(POI_PIN_SIZE_PX * PIN_MIN_SCALE + ICON_PADDING_PX * 2)


def test_a_pin_is_full_size_from_z13_up_and_stays_there():
    assert pin_box_px(PIN_FULL_SCALE_ZOOM, SEAM) == pytest.approx(POI_PIN_SIZE_PX + ICON_PADDING_PX * 2)
    assert pin_box_px(20, SEAM) == pin_box_px(PIN_FULL_SCALE_ZOOM, SEAM)


def test_more_pins_fit_a_column_at_the_seam_than_at_walking_zoom():
    assert pin_room(SEAM, SEAM) > pin_room(PIN_FULL_SCALE_ZOOM, SEAM)


def test_the_screen_halves_in_each_direction_per_zoom_level():
    wide, tall = screen_miles(10)
    closer_wide, closer_tall = screen_miles(11)
    assert closer_wide == pytest.approx(wide / 2)
    assert closer_tall == pytest.approx(tall / 2)


def test_the_seam_is_the_tightest_zoom_that_still_shows_the_planning_window():
    """THE criterion, and the one this spike has now got wrong twice.

    A day on the A.T. is 16-24 miles, and the window is twice that so the day
    has ground around it rather than filling the screen edge to edge. The seam
    is the HIGHEST zoom whose screen still fits that window.
    """
    answer = seam()
    assert answer is not None
    assert screen_miles(answer)[1] >= PLANNING_WINDOW_MILES
    assert screen_miles(answer + 1)[1] < PLANNING_WINDOW_MILES


def test_the_window_is_a_day_with_room_around_it_rather_than_exactly_a_day():
    """The second correction. Sizing the screen to exactly one day put a
    24-mile day edge to edge with no context, so every question that starts
    "and then what" cost a pan. Doubling it is deliberate, not slack."""
    assert PLANNING_WINDOW_MILES == pytest.approx(DAY_MILES * 2)

    exactly_a_day = seam(window_miles=DAY_MILES)
    assert seam() < exactly_a_day, "the wider window must sit further out"
    assert screen_miles(seam())[1] >= DAY_MILES * 2


def test_taking_the_lowest_fitting_zoom_would_report_the_whole_corridor():
    """The bug this replaced, kept as a test because it produced a plausible
    number rather than an error: every wider view also fits the window,
    trivially, so a `min` walks out to the bottom of the range and calls the
    whole 2,197-mile corridor the seam."""
    fitting = [z for z in range(4, 18) if screen_miles(z)[1] >= PLANNING_WINDOW_MILES]
    assert min(fitting) == 4
    assert seam() == max(fitting)


def test_a_smaller_window_pushes_the_seam_in_rather_than_out():
    """Sanity on the direction, since the inequality is easy to flip: asking
    for less ground on screen means zooming further in."""
    assert seam(window_miles=PLANNING_WINDOW_MILES / 4) > seam()


def test_no_zoom_fitting_is_reported_rather_than_guessed():
    assert seam(zooms=range(18, 20)) is None
