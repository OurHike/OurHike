"""The pure halves of spike_city_poi_density.py — the placement model, the two
folding rules, and the window datum that a floating-point slip had already
cost a waypoint.

The measurement half needs a published nearby_poi.geojson and is not re-run
here. What these hold is the part that makes the numbers on
features/mockups/city-water-density.html comparable: every option runs through
the same `place` and the same window, so a bug in either would move all six
rows together and none of them would look wrong.
"""

import math

from spike_city_poi_density import (
    ICON_PADDING_PX,
    PIN_SIZE_PX,
    Point,
    densest_window,
    fold_by_pixels,
    fold_by_place,
    fold_by_site,
    icon_scale,
    in_window,
    metres_per_pixel,
    place,
    screen_share,
    viewport_degrees,
    window_centre,
)


def _at(lon, lat, poi_type="water", named="Prospect Park"):
    return Point(lon=lon, lat=lat, poi_type=poi_type, place=named)


def test_the_icon_size_ramp_matches_the_expression_the_map_ships():
    """POI_ICON_SIZE_EXPRESSION: 0.8 at z9, 1.0 from z13, linear between.

    A scale read off the wrong end of that ramp changes the collision box, and
    a collision box is what every pin count on the mockup page rests on.
    """
    assert icon_scale(9) == 0.8
    assert icon_scale(13) == 1.0
    assert icon_scale(11) == 0.9
    assert icon_scale(8) == 0.8, "flat below the seam, as `interpolate` is"
    assert icon_scale(16) == 1.0, "and flat above its top stop"


def test_a_z12_phone_screen_is_the_ground_poi_visibility_says_it_is():
    """3.5 x 6.3 mi at 40.7°N, which is POI_VISIBILITY.md's table read at the
    latitude of New York City rather than at its 40°N round number."""
    lon_deg, lat_deg = viewport_degrees(40.7, 12)
    assert round(lat_deg * 111_320.0 / 1609.344, 1) == 6.3
    assert round(lon_deg * 111_320.0 * math.cos(math.radians(40.7)) / 1609.344, 1) == 3.5


def test_the_densest_window_is_selected_on_the_corner_it_was_counted_on():
    """The bug this file exists to have caught, and it cost a real waypoint.

    `densest_window` counts a box anchored at a point, so the anchor sits
    exactly on the west edge. Re-selecting from a CENTRE means recomputing
    that edge as `west + span/2 - span/2`, which in binary floating point is
    not always `west` — and the anchor drops out. Measured against the live
    Brooklyn window: 638 counted, 637 re-selected.

    These points are spaced so that dropping the westernmost changes the
    count, which a tolerance-free equality check would not notice.
    """
    lon_deg, lat_deg = viewport_degrees(40.7, 12)
    west, south = -73.97152618461452, 40.69322962606433
    points = [
        _at(west, south),
        _at(west + lon_deg / 3, south + lat_deg / 3),
        _at(west + lon_deg * 2 / 3, south + lat_deg * 2 / 3),
    ]
    total, corner = densest_window(points, lon_deg, lat_deg)
    assert total == 3
    assert corner == (west, south)
    assert len(in_window(points, corner, lon_deg, lat_deg)) == total

    centre = window_centre(corner, lon_deg, lat_deg)
    assert centre[0] > west and centre[1] > south


def test_a_pin_that_overlaps_one_already_placed_is_not_drawn():
    """MapLibre drops rather than nudges, which is why a loser becomes a dot
    instead of moving. Two fountains 10 m apart cannot both hold a 40 px box
    at z12, where a pixel is 14.4 m of ground."""
    centre = (-73.97, 40.69)
    metres = 10.0
    apart = metres / 111_320.0
    pinned = place([_at(-73.97, 40.69), _at(-73.97, 40.69 + apart)], centre, 12)
    assert len(pinned) == 1


def test_wider_padding_places_fewer_pins_and_never_more():
    """Option 1's entire mechanism. The relation has to be monotone, or the
    mockup's 'more air, fewer pins' claim is only true at the one value tried.
    """
    centre = (-73.97, 40.69)
    step = 260.0 / 111_320.0
    row = [_at(-73.97, 40.69 + i * step) for i in range(12)]
    counts = [len(place(row, centre, 12, padding)) for padding in (2, 8, 16, 24, 32)]
    assert counts == sorted(counts, reverse=True)
    assert counts[0] > counts[-1], "the sweep has to actually bind somewhere"


def test_water_survives_a_collision_a_privy_loses():
    """POI_PRIORITY, applied. In a city the two categories are the whole map,
    and a rule that let a restroom take a fountain's pin would invert the one
    ordering poiPriority.ts calls a safety ordering rather than a visual one.
    """
    centre = (-73.97, 40.69)
    apart = 10.0 / 111_320.0
    pinned = place(
        [_at(-73.97, 40.69 + apart, poi_type="privy"), _at(-73.97, 40.69, poi_type="water")],
        centre,
        12,
    )
    assert [p.poi_type for p in pinned] == ["water"]


def test_a_site_needs_both_gates_and_not_either_one():
    """features/POI_SITES.md's rule, ported. Two fountains 20 m apart in
    DIFFERENT parks are two places; two fountains 3 km apart in the same park
    are also two places. Only the pair that agrees on both folds.
    """
    near = 20.0 / 111_320.0
    far = 3000.0 / 111_320.0
    points = [
        _at(-73.97, 40.69, named="Prospect Park"),
        _at(-73.97, 40.69 + near, named="Fort Greene Park"),
        _at(-73.97, 40.69 + far, named="Prospect Park"),
    ]
    assert len(fold_by_site(points)) == 3

    points.append(_at(-73.97, 40.69 + near / 2, named="Prospect Park"))
    folded = fold_by_site(points)
    assert len(folded) == 3
    assert max(f.members for f in folded) == 2


def test_a_line_of_fountains_folds_as_one_site_rather_than_a_chain_of_pairs():
    """Single-link, which is the boardwalk case: Coney Island's fountains run
    in a line where no two ends are within the radius of each other. A
    pairwise rule would leave a chain of overlapping two-member sites."""
    step = 60.0 / 111_320.0
    line = [_at(-73.97, 40.69 + i * step) for i in range(6)]
    folded = fold_by_site(line, radius_m=80.0)
    assert len(folded) == 1
    assert folded[0].members == 6


def test_folding_to_a_place_keeps_a_type_apart_from_another_type():
    """A park's fountains and its restrooms are two marks, not one. The pin
    carries a category and a fold across categories would have to invent one.
    """
    points = [
        _at(-73.97, 40.69, poi_type="water"),
        _at(-73.971, 40.691, poi_type="water"),
        _at(-73.972, 40.692, poi_type="privy"),
    ]
    folded = fold_by_place(points)
    assert sorted((f.poi_type, f.members) for f in folded) == [("privy", 1), ("water", 2)]


def test_a_screen_space_cluster_sits_on_a_member_and_a_site_sits_between_them():
    """The difference the mockup's option 4 turns on. A library's cluster keeps
    its head's coordinate, so the mark is a real place for one member and wrong
    for the rest; a site is a centroid, which is honest about being neither."""
    centre = (-73.97, 40.69)
    step = 30.0 / 111_320.0
    pair = [_at(-73.97, 40.69), _at(-73.97, 40.69 + step)]

    clustered = fold_by_pixels(pair, centre, 12)
    assert len(clustered) == 1
    assert clustered[0].lat in (pair[0].lat, pair[1].lat)

    sited = fold_by_site(pair)
    assert len(sited) == 1
    assert pair[0].lat < sited[0].lat < pair[1].lat


def test_screen_share_counts_the_disc_the_hiker_sees_not_the_box_reserved():
    """30% for the 63 pins the live window draws. The collision box is 40 px
    at `icon-padding: 2` and the pin is 38 — using the box would report 33%
    and describe ink nobody can see."""
    assert round(screen_share(63, 12), 2) == 0.30
    drawn = PIN_SIZE_PX * icon_scale(12)
    assert screen_share(1, 12) == drawn * drawn / (390 * 700)
    assert drawn < (PIN_SIZE_PX + 2 * ICON_PADDING_PX) * icon_scale(12)


def test_metres_per_pixel_is_maplibre_s_zoom_and_not_the_256_tile_reading():
    """The same calibration spike_oprhp_poi_density.py's first test makes, for
    the same reason: the other convention is exactly twice these and would
    disagree silently with every table on the mockup page."""
    assert round(metres_per_pixel(40, 12), 1) == 14.6
    assert round(metres_per_pixel(40, 14), 1) == 3.7
