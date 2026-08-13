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
import statistics

import pytest

from lib.spurs import distance_m
from spike_poi_seam import (
    PIN_BOX_PX,
    VIEWPORT_H_PX,
    VIEWPORT_W_PX,
    ZoomResult,
    pin_room,
    place,
    reachable,
    seam,
    sort_key,
    to_pixels,
    viewport_loads,
)


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
    """
    lat, lon = 40.0, -75.0
    one_degree_px = to_pixels(lat, lon + 1.0, zoom)[0] - to_pixels(lat, lon, zoom)[0]
    metres_per_px = distance_m(lat, lon, lat, lon + 1.0) / one_degree_px
    # Rounded to the metre, which reproduces the doc's table exactly rather
    # than approximately - all six rows agree on the nose.
    assert round(metres_per_px * PIN_BOX_PX) == expected_m


# --- the collision test ---------------------------------------------------


def test_pins_closer_than_the_box_collide_and_one_is_dropped():
    lat, lon = 40.0, -75.0
    world = 512.0 * 2**14
    # Half a box east: inside the collision distance in both axes.
    nudge = (PIN_BOX_PX / 2) * 360.0 / world
    drawn = place([poi("a", "shelter", lat, lon), poi("b", "shelter", lat, lon + nudge)], 14)
    assert len(drawn) == 1


def test_pins_further_apart_than_the_box_both_place():
    lat, lon = 40.0, -75.0
    world = 512.0 * 2**14
    gap = (PIN_BOX_PX + 1) * 360.0 / world
    drawn = place([poi("a", "shelter", lat, lon), poi("b", "shelter", lat, lon + gap)], 14)
    assert drawn == {"a", "b"}


def test_priority_decides_the_survivor_not_input_order():
    """POI_PRIORITY is a safety ordering. A viewpoint listed first must not
    take the slot a water source wanted, and an id that sorts earlier must not
    either."""
    lat, lon = 40.0, -75.0
    contested = [poi("a_viewpoint", "viewpoint", lat, lon), poi("z_water", "water", lat, lon)]
    assert place(contested, 14) == {"z_water"}
    assert place(list(reversed(contested)), 14) == {"z_water"}


def test_an_unknown_type_sorts_last_rather_than_crashing():
    assert sort_key({"poi_type": "something_new"}) > sort_key({"poi_type": "viewpoint"})


def test_placement_is_deterministic_across_runs():
    """Ties inside one priority break by id. Without that the whole table
    wobbles between runs, which is very hard to notice and impossible to
    review."""
    points = [poi(f"p{i}", "viewpoint", 40.0, -75.0 + i * 1e-5) for i in range(40)]
    assert place(points, 13) == place(list(reversed(points)), 13)


# --- what site-folding makes reachable ------------------------------------


def test_a_member_rides_its_anchors_pin():
    """The whole claim of features/POI_SITES.md. The privy is 40 m from its
    shelter, so at z14 (154 m collision) it could never place its own pin -
    and it is still reachable, because the shelter's pin stands for it."""
    shelter = poi("s", "shelter", 40.0, -75.0, "Mt. Algo Shelter")
    privy = poi("p", "privy", 40.00036, -75.0, "Mt. Algo Shelter Privy")
    reach = reachable([shelter, privy], 14)
    assert reach == {"s", "p"}
    # ...and the privy is genuinely un-placeable on its own terms.
    assert place([shelter, privy], 14) == {"s"}


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
    assert reachable([water, shelter, privy], 14) == {"w"}


def test_folding_never_reports_more_than_exists():
    points = [poi(f"p{i}", "viewpoint", 40.0 + i * 0.5, -75.0) for i in range(6)]
    assert reachable(points, 12) <= {p["id"] for p in points}


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


# --- the seam rule --------------------------------------------------------


def test_pin_room_is_the_column_not_the_area():
    assert pin_room() == int(VIEWPORT_H_PX / PIN_BOX_PX)


def result(zoom: int, median_load: int) -> ZoomResult:
    return ZoomResult(zoom=zoom, drawn_share={}, loads=[median_load] * 5)


def test_the_seam_is_the_lowest_zoom_whose_median_fits():
    room = pin_room()
    results = [result(10, room * 3), result(11, room + 1), result(12, room - 1), result(13, 2)]
    assert seam(results) == 12


def test_the_seam_is_chosen_on_the_median_not_the_worst_case():
    """Above the seam an oversubscribed screen costs dots, not deletions, so
    the criterion is 'is this a better screen than the corridor view' rather
    than 'is every screen guaranteed to fit'. A p90 rule would push the seam a
    level deeper to protect against something that is no longer a failure."""
    room = pin_room()
    crowded_tail = ZoomResult(zoom=12, drawn_share={}, loads=[1, 1, 1, room * 10, room * 10])
    assert statistics.median(crowded_tail.loads) <= room
    assert seam([crowded_tail]) == 12


def test_no_zoom_fitting_is_reported_rather_than_guessed():
    assert seam([result(10, pin_room() * 2)]) is None
