"""Tests for spike_dem_banding.py's pure pieces (#186).

The spike's conclusions came from fetching real tiles, which a test must not
do - but its arithmetic is what those conclusions rest on, so the decode,
the shading, the terrace metric and the tile math are each pinned against
hand-computable cases. The quantization itself is export_dem.floor_blue,
tested in test_export_dem.py; here we only prove the spike really calls it."""

import numpy as np

import spike_dem_banding as spike


def rgb_for(elevations_m: np.ndarray) -> np.ndarray:
    shifted = elevations_m + 32768.0
    r = np.floor(shifted / 256.0)
    g = np.floor(shifted - r * 256.0)
    b = np.round((shifted - np.floor(shifted)) * 256.0) % 256
    return np.dstack([r, g, b]).astype("uint8")


def test_elevation_decodes_terrarium_exactly():
    grid = np.array([[0.0, 100.5], [-12.25, 4000.0]])

    assert np.array_equal(spike.elevation(rgb_for(grid)), grid)


def test_quantized_uses_the_exporters_floor():
    grid = np.array([[100.0, 100.5], [100.49, 100.99]])

    half = spike.elevation(spike.quantized(rgb_for(grid), 0.5))
    whole = spike.elevation(spike.quantized(rgb_for(grid), 1.0))

    assert np.array_equal(half, np.array([[100.0, 100.5], [100.0, 100.5]]))
    assert np.array_equal(whole, np.array([[100.0, 100.0], [100.0, 100.0]]))


def test_quantized_leaves_the_input_untouched():
    rgb = rgb_for(np.full((2, 2), 10.75))
    before = rgb.copy()

    spike.quantized(rgb, 1.0)

    assert np.array_equal(rgb, before)


def test_hillshade_is_uniform_on_flat_ground():
    flat = spike.hillshade(np.full((16, 16), 500.0), m_per_px=10.0)

    assert len(np.unique(flat)) == 1


def test_hillshade_shows_a_quantized_ramp_as_bands_where_the_raw_ramp_is_smooth():
    """The phenomenon the spike measures, in miniature: a gentle smooth ramp
    shades as one value, and the same ramp floored to 1 m breaks into treads
    and risers - alternating shading values where there was one."""
    gentle = np.tile(np.linspace(100.0, 104.0, 64), (16, 1))  # ~6 cm per 10 m px

    smooth = spike.hillshade(gentle, m_per_px=10.0)
    stepped = spike.hillshade(np.floor(gentle), m_per_px=10.0)

    assert len(np.unique(smooth[:, 2:-2])) == 1
    assert len(np.unique(stepped[:, 2:-2])) >= 2


def test_mean_terrace_run_grows_under_flooring():
    gentle = np.tile(np.linspace(100.0, 104.0, 64), (4, 1))

    assert spike.mean_terrace_run(np.floor(gentle)) > spike.mean_terrace_run(gentle)


def test_tile_xy_matches_the_slippy_map_convention():
    # Greenwich at the equator is the exact center of the grid.
    assert spike.tile_xy(0.0, 0.0, 1) == (1, 1)
    # Boiling Springs PA at z13, cross-checked against the standard formula.
    assert spike.tile_xy(40.185, -77.08, 13) == (2342, 3095)


def test_meters_per_pixel_halves_per_zoom():
    at_12 = spike.meters_per_pixel(40.0, 12)
    at_13 = spike.meters_per_pixel(40.0, 13)

    assert at_12 / at_13 == 2.0


def test_flattest_window_finds_the_flat_corner():
    elev = np.random.default_rng(7).normal(0, 5.0, (256, 256))
    elev[:192, :192] = 0.0  # a dead-flat block in the north-west

    assert spike.flattest_window(elev) == (0, 0)


def test_compare_reports_rms_and_share_of_big_shifts():
    a = np.zeros((10, 10), dtype=np.uint8)
    b = np.zeros((10, 10), dtype=np.uint8)
    b[0, 0] = 90  # one pixel, 90 levels off

    rms, big = spike.compare(a, b)

    assert rms == 9.0
    assert big == 1.0


def test_bilinear_upsample_scales_the_grid_without_moving_flat_values():
    up = spike.bilinear_upsample(np.full((4, 4), 250.0), 4)

    assert up.shape == (16, 16)
    assert np.allclose(up, 250.0)
