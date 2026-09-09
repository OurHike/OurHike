"""The pure halves of spike_oprhp_poi_density.py (#936) — the z12 viewport
arithmetic and the densest-window search. The measurement half runs against
OPRHP's live layer and is not re-run here; these keep the arithmetic honest so
the numbers in the issue mean what they say.

The first test is the one that matters. #936's whole question is asked in
features/POI_VISIBILITY.md's units, and that table is the only calibration
either document offers — so a viewport computed in the other zoom convention
would describe a screen twice the size and disagree silently with the one page
the answer gets read against."""

import math

from spike_oprhp_poi_density import (
    AMENITIES,
    TOILETS,
    WATER,
    Point,
    densest_window,
    metres_per_pixel,
    viewport_degrees,
)


def test_matches_poi_visibility_density_table():
    """POI_VISIBILITY.md's own m/px at 40°N, row for row.

    Its table reads 117 / 14.6 / 7.3 / 3.7 at z9 / z12 / z13 / z14. Those are
    MapLibre zooms — 512 px tiles, so the exponent is z + 1 — and the 256-tile
    reading of the same numbers is exactly twice each of them, which is what
    makes getting this wrong quiet rather than obvious.
    """
    assert round(metres_per_pixel(40, 9)) == 117
    assert round(metres_per_pixel(40, 12), 1) == 14.6
    assert round(metres_per_pixel(40, 13), 1) == 7.3
    assert round(metres_per_pixel(40, 14), 1) == 3.7


def test_a_phone_map_at_z12_is_the_table_s_ground():
    """ "3.5 x 6.4 mi" at z12, from the same table."""
    m_per_px = metres_per_pixel(40, 12)
    miles = 1609.344
    assert round(390 * m_per_px / miles, 1) == 3.5
    assert round(700 * m_per_px / miles, 1) == 6.4


def test_ground_shrinks_with_latitude():
    # Web Mercator's cosine term. Harriman is 41.26°N, so its screen covers
    # slightly less ground than the table's 40° reference - which is why the
    # measurement uses the points' own mean latitude rather than 40.
    assert metres_per_pixel(41.26, 12) < metres_per_pixel(40, 12)
    assert metres_per_pixel(0, 12) > metres_per_pixel(40, 12)


def test_viewport_is_taller_than_it_is_wide():
    lon_deg, lat_deg = viewport_degrees(41.26, 12)
    # 700 px tall against 390 wide, but a degree of longitude is shorter than a
    # degree of latitude up here - so the DEGREE spans are closer together than
    # the pixel spans, and the height still wins.
    assert lat_deg > lon_deg > 0


def _at(lon, lat):
    return Point(lon=lon, lat=lat, sub_asset="Scenic View", park="Harriman State Park")


def test_densest_window_counts_a_cluster():
    points = [_at(0, 0), _at(0.001, 0.001), _at(0.002, 0.002), _at(5, 5)]

    best, where = densest_window(points, lon_deg=0.01, lat_deg=0.01)

    assert best == 3
    assert where is not None


def test_densest_window_is_exact_across_a_boundary():
    """The reason this is anchored on points rather than swept on a grid.

    These three sit within one window's span but straddle any grid line drawn
    through the middle of them, so a phase-dependent sweep can report 2.
    """
    points = [_at(0.0049, 0), _at(0.0050, 0), _at(0.0051, 0)]

    best, _ = densest_window(points, lon_deg=0.01, lat_deg=0.01)

    assert best == 3


def test_densest_window_of_nothing_is_nothing():
    # The water case in the real measurement: OPRHP's facilities layer holds no
    # drinking water in either park, so this subset is genuinely empty and must
    # not raise on the way to saying so.
    best, where = densest_window([], lon_deg=0.01, lat_deg=0.01)

    assert best == 0
    assert where is None


def test_the_three_classifications_do_not_overlap():
    """A row counted twice would inflate the very number this measures."""
    assert not WATER & TOILETS
    assert not WATER & AMENITIES
    assert not TOILETS & AMENITIES


def test_window_span_is_finite_everywhere_it_is_used():
    # viewport_degrees divides by cos(lat); at the latitudes this spike runs at
    # that is nowhere near zero, and the assertion is here so a future caller
    # reaching for a polar latitude finds out from a test rather than from an
    # infinity in a count.
    lon_deg, lat_deg = viewport_degrees(41.26, 12)
    assert math.isfinite(lon_deg) and math.isfinite(lat_deg)
