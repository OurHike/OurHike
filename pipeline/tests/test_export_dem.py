"""Tests for export_dem.py - packaging elevation as an offline archive.

The quantization tests are the load-bearing ones: a wrong bit here is a
silently wrong elevation under every contour and hillshade the client draws.
Synthetic terrarium tiles are built from known elevation grids so the
assertions can speak meters, not pixels."""

import argparse
import io
import json

import numpy as np
import pytest
from PIL import Image
from pmtiles.reader import MmapSource, all_tiles
from pmtiles.tile import Compression, TileType, deserialize_header
from requests_mock import ANY as ANY_URL
from shapely.geometry import box, mapping, shape

import export_dem
from export_dem import encode_tile, fetch_tile, quantize_unit
from extract_package import tiles_intersecting, to_mercator

NE_QUADRANT_BOX = box(30.0, 30.0, 80.0, 70.0)


def terrarium_png(elevations_m: np.ndarray) -> bytes:
    """A terrarium PNG for a grid of (possibly fractional) meter elevations:
    value = (R*256 + G + B/256) - 32768."""
    shifted = elevations_m + 32768.0
    r = np.floor(shifted / 256.0)
    g = np.floor(shifted - r * 256.0)
    b = np.round((shifted - np.floor(shifted)) * 256.0) % 256
    rgb = np.dstack([r, g, b]).astype("uint8")
    buf = io.BytesIO()
    Image.fromarray(rgb).save(buf, format="PNG")
    return buf.getvalue()


def decode_elevations(webp_bytes: bytes) -> np.ndarray:
    rgb = np.asarray(Image.open(io.BytesIO(webp_bytes)).convert("RGB")).astype(np.float64)
    return rgb[:, :, 0] * 256.0 + rgb[:, :, 1] + rgb[:, :, 2] / 256.0 - 32768.0


def test_quantize_unit_accepts_power_of_two_fractions_of_a_meter():
    assert quantize_unit(1.0) == 256
    assert quantize_unit(0.5) == 128
    assert quantize_unit(0.25) == 64


@pytest.mark.parametrize("step", [0.0, -1.0, 2.0, 0.3])
def test_quantize_unit_rejects_steps_that_would_need_channel_carries(step):
    with pytest.raises(ValueError, match="quantize step"):
        quantize_unit(step)


def test_encode_tile_floors_elevation_by_at_most_the_step():
    # Elevations chosen to exercise the fraction range, including values just
    # under a whole meter - the case where a careless ROUND would carry into
    # the green channel and corrupt the whole-meter part.
    grid = np.array([[100.0, 100.999], [1500.25, -12.75]])
    quantized = decode_elevations(encode_tile(terrarium_png(grid), quantize_unit(1.0)))

    error = grid - quantized
    assert np.all(error >= 0), "floor must never raise an elevation"
    assert np.all(error < 1.0), "floor must never drop more than one step"
    assert np.array_equal(quantized, np.floor(grid)), "1 m floor is exactly np.floor"


def test_encode_tile_half_meter_step_keeps_half_meters():
    grid = np.array([[100.0, 100.5], [100.49, 100.99]])
    quantized = decode_elevations(encode_tile(terrarium_png(grid), quantize_unit(0.5)))
    assert np.array_equal(quantized, np.array([[100.0, 100.5], [100.0, 100.5]]))


def test_encode_tile_is_lossless_after_quantization():
    # WebP must add zero error on top of the floor - lossless mode is the
    # entire reason the format swap is safe for elevation data.
    grid = np.arange(64, dtype=np.float64).reshape(8, 8) * 37.503 - 100
    once = encode_tile(terrarium_png(grid), quantize_unit(1.0))
    twice = encode_tile(once, quantize_unit(1.0))
    assert np.array_equal(decode_elevations(once), decode_elevations(twice))


def test_fetch_tile_returns_none_on_404_and_retries_transient_errors(requests_mock, monkeypatch):
    import requests as requests_lib

    from lib import http_retry

    # The retry ladder must PAUSE between attempts (#659: the old loop here
    # slept zero seconds) - recorded here and skipped so the test doesn't
    # wait it out.
    slept: list[float] = []
    monkeypatch.setattr(http_retry.time, "sleep", slept.append)

    session = requests_lib.Session()
    url = export_dem.DEM_TILE_URL.format(z=1, x=0, y=0)
    requests_mock.get(url, status_code=404)
    assert fetch_tile(session, 1, 0, 0) is None
    assert slept == [], "a 404 is an answer, not a flake - no retry, no pause"

    url2 = export_dem.DEM_TILE_URL.format(z=1, x=1, y=0)
    requests_mock.get(url2, [{"status_code": 503}, {"content": b"png-bytes", "status_code": 200}])
    assert fetch_tile(session, 1, 1, 0) == b"png-bytes"
    assert slept == [export_dem.FETCH_BACKOFF_SECONDS[0]], "one 503 costs one pause from the ladder"


def make_args(tmp_path, region_path, **overrides):
    defaults = dict(
        region=region_path,
        out=tmp_path / "dem.pmtiles",
        min_zoom=0,
        max_zoom=2,
        quantize_step=1.0,
        workers=1,
        limit=0,
        name="test DEM",
        # None means export_dem's own CORRIDOR_TAPER_MILES, and these fixtures
        # all pass an explicit --region, which overrides the taper anyway.
        taper=None,
    )
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def region_file(tmp_path):
    path = tmp_path / "region.geojson"
    path.write_text(json.dumps(mapping(NE_QUADRANT_BOX)))
    return path


def test_main_packages_the_region_tiles(tmp_path, requests_mock, monkeypatch):
    monkeypatch.setattr(export_dem, "DEM_TILE_URL", "https://dem.test/{z}/{x}/{y}.png")
    png = terrarium_png(np.full((4, 4), 250.5))
    requests_mock.get(ANY_URL, content=png)

    args = make_args(tmp_path, region_file(tmp_path))
    export_dem.main(args)

    expected = tiles_intersecting(to_mercator(NE_QUADRANT_BOX), 0, 2)
    expected_zxy = {(z, x, y) for z, tiles in expected.items() for x, y in tiles}
    with open(args.out, "rb") as f:
        got = dict(all_tiles(MmapSource(f)))
    assert set(got) == expected_zxy
    for data in got.values():
        assert np.array_equal(decode_elevations(data), np.full((4, 4), 250.0))

    with open(args.out, "rb") as f:
        header = deserialize_header(f.read(127))
    assert header["tile_type"] == TileType.WEBP
    assert header["tile_compression"] == Compression.NONE


def test_main_counts_tiles_absent_from_the_source(tmp_path, requests_mock, monkeypatch, capsys):
    monkeypatch.setattr(export_dem, "DEM_TILE_URL", "https://dem.test/{z}/{x}/{y}.png")
    png = terrarium_png(np.full((4, 4), 10.0))
    requests_mock.get(ANY_URL, content=png)
    requests_mock.get("https://dem.test/0/0/0.png", status_code=404)

    export_dem.main(make_args(tmp_path, region_file(tmp_path)))

    out = capsys.readouterr().out
    assert "1 absent from source" in out


def test_main_refuses_to_exceed_the_tile_limit(tmp_path, requests_mock, monkeypatch):
    monkeypatch.setattr(export_dem, "DEM_TILE_URL", "https://dem.test/{z}/{x}/{y}.png")
    requests_mock.get(ANY_URL, content=b"unused")

    with pytest.raises(SystemExit, match="exceed --limit"):
        export_dem.main(make_args(tmp_path, region_file(tmp_path), limit=2))


# The corridor taper (#1088): the DEM's corridor narrows with depth, because a
# mile of buffer costs ~9x more at z13 than at z11.


def test_taper_reads_as_a_step_function_over_zoom():
    """Each entry holds from its own zoom until the next one - so the eleven
    shallow zooms that carry the pan-out context inherit the widest entry
    rather than needing eleven copies of it."""
    taper = {0: 30.0, 12: 15.0, 13: 6.0}

    assert [export_dem.taper_miles(z, taper) for z in range(14)] == [30.0] * 12 + [15.0, 6.0]


def test_taper_narrows_monotonically_with_depth():
    """Not an arbitrary preference: a corridor that widened at a deeper zoom
    would buy width at exactly the price this taper exists to avoid paying."""
    widths = [export_dem.taper_miles(z) for z in range(export_dem.MIN_ZOOM, export_dem.MAX_ZOOM + 1)]

    assert widths == sorted(widths, reverse=True), f"taper widens somewhere: {widths}"
    assert widths[-1] < widths[0], "a taper whose deepest zoom is as wide as its shallowest is not a taper"


def test_taper_covers_every_zoom_the_exporter_builds():
    """taper_miles() must be total over MIN_ZOOM..MAX_ZOOM. A zoom with no
    entry is not a narrower corridor, it is a KeyError mid-build - or, if it
    were made to default, a silent hole in the map."""
    for zoom in range(export_dem.MIN_ZOOM, export_dem.MAX_ZOOM + 1):
        assert export_dem.taper_miles(zoom) > 0


def test_parse_taper_reads_a_command_line_schedule():
    assert export_dem.parse_taper("0:30,12:15,13:6") == {0: 30.0, 12: 15.0, 13: 6.0}
    assert export_dem.parse_taper(" 0:30 , 13:6.5 ") == {0: 30.0, 13: 6.5}


@pytest.mark.parametrize(
    "spec, why",
    [
        ("0:30,13", "an entry that is not zoom:miles"),
        ("12:15,13:6", "no zoom-0 entry, so the shallow zooms have no width"),
        ("0:30,13:0", "a zero width is an empty corridor, not a narrow one"),
        ("0:30,13:-6", "a negative width"),
        ("-1:30,0:30", "a negative zoom"),
    ],
)
def test_parse_taper_refuses_a_schedule_that_would_ship_a_hole(spec, why):
    """A typo here is a map with nothing in it at some zoom, found by a hiker
    with no signal. Every one of these fails loudly at parse time instead."""
    with pytest.raises(ValueError):
        export_dem.parse_taper(spec)


def test_the_shallow_zooms_escape_the_corridor_entirely():
    """z0-9 keep the corridor's whole bounding box, not the corridor - the
    boundary extract_package.DEFAULT_CONTEXT_ZOOM already draws for the vector
    sheet. Before this the hillshade stopped at a 60-mile ribbon while the
    basemap under it showed the whole region, and panned out with no signal the
    two disagreed on screen."""
    assert export_dem.CONTEXT_ZOOM == 9

    calls = []

    def fake_corridor(buffer_miles=None):
        calls.append(buffer_miles)
        return box(-84.2, 34.6, -68.9, 45.9)

    import unittest.mock as mock

    with mock.patch.object(export_dem, "load_corridor_4326", fake_corridor):
        tiles, widest = export_dem.tapered_tiles(0, 11, {0: 30.0, 11: 6.0})

    by_zoom = {}
    for z, x, y in tiles:
        by_zoom.setdefault(z, []).append((x, y))
    # z9 is context (whole bbox); z10-11 are corridor-clipped. With a box
    # standing in for the corridor the two coincide in extent, so what this
    # pins is that every zoom is populated and none was dropped by the split.
    assert set(by_zoom) == set(range(12))
    assert widest is not None


def test_a_region_argument_still_overrides_the_taper(tmp_path):
    """--region has always meant "this exact shape", and it keeps meaning it:
    one shape at every zoom, no corridor build, no taper."""
    region = shape(json.loads(region_file(tmp_path).read_text()))

    tiles, widest = export_dem.tapered_tiles(0, 2, export_dem.CORRIDOR_TAPER_MILES, region)

    assert widest is region
    assert tiles == sorted(tiles), "tiles must reach the writer in (z, x, y) order"
    assert {z for z, _, _ in tiles} == {0, 1, 2}
