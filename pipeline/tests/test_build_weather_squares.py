"""Tests for build_weather_squares.py's pure pieces (#1056).

The network half (the release, URMA's terrain) is exercised by running the
script; what is pinned here is the arithmetic every published square rests
on - where points are laid, which cell a square is filed under, and which
water square borrows which land."""

import json

import numpy as np
import pytest

import build_weather_squares as squares_mod
from lib import hrrr_grid, nbm_grid


def test_densify_lays_points_no_further_apart_than_the_step():
    line = np.array([[-80.0, 40.0], [-79.9, 40.05]])

    points = squares_mod.densify(line, step_deg=0.004)

    gaps = np.abs(np.diff(points, axis=0)).max(axis=1)
    assert gaps.max() <= 0.004 + 1e-12
    assert points[0].tolist() == [-80.0, 40.0] and points[-1].tolist() == [-79.9, 40.05]


def test_densify_leaves_a_single_vertex_alone():
    assert squares_mod.densify(np.array([[-80.0, 40.0]])).tolist() == [[-80.0, 40.0]]


def test_a_line_through_a_square_is_found_even_when_no_vertex_is_in_it():
    # Two vertices ~11 km apart; the squares between them hold no vertex.
    line = np.array([[-71.40, 44.27], [-71.26, 44.27]])
    points = squares_mod.densify(line)

    cells, _ = squares_mod.squares_by_cell(points[:, 0], points[:, 1])

    found = {tuple(sq) for sq in cells["n44w072"]}
    ends = {(int(r), int(c)) for r, c in zip(*nbm_grid.squares(line[:, 0], line[:, 1]), strict=True)}
    assert ends <= found and len(found) >= 5


def test_a_square_is_filed_under_every_cell_a_trail_point_in_it_falls_in():
    # Straddling the 72nd meridian: one point each side.
    lons, lats = np.array([-72.001, -71.999]), np.array([44.5, 44.5])

    cells, _ = squares_mod.squares_by_cell(lons, lats)

    assert set(cells) == {"n44w073", "n44w072"}


def test_a_point_off_the_conus_grid_is_listed_rather_than_dropped():
    lons, lats = np.array([-149.9, -71.3033]), np.array([61.2, 44.2706])

    cells, outside = squares_mod.squares_by_cell(lons, lats)

    assert outside == ["n61w150"]
    assert cells == {"n44w072": [[562, 2074]]}


def test_geometry_lines_reads_both_line_types_and_ignores_the_rest():
    line = {"type": "LineString", "coordinates": [[0, 0], [1, 1]]}
    multi = {"type": "MultiLineString", "coordinates": [[[0, 0], [1, 1]], [[2, 2], [3, 3]]]}

    assert squares_mod.geometry_lines(line) == [[[0, 0], [1, 1]]]
    assert len(squares_mod.geometry_lines(multi)) == 2
    assert squares_mod.geometry_lines({"type": "Point", "coordinates": [0, 0]}) == []
    assert squares_mod.geometry_lines(None) == []


def terrain_with(values: dict[tuple[int, int], float], default: float = 100.0) -> np.ndarray:
    grid = np.full((20, 20), default)
    for square, height in values.items():
        grid[square] = height
    return grid


def test_a_water_square_borrows_its_nearest_land_square():
    # Bear Mountain, in miniature: the waypoint's square is river at 0 m and
    # the square north of it is land (measured: (711, 2007) at 41 m).
    terrain = terrain_with({(10, 10): 0.0, (10, 11): 0.0, (11, 10): 0.0, (11, 11): 0.0, (10, 9): 0.0})

    borrowed, kept = squares_mod.borrow_land({(10, 10)}, terrain <= squares_mod.WATER_MAX_M)

    assert borrowed == {(10, 10): (9, 10)}  # distance 1, and the smallest (row, col) of the ties
    assert kept == []


def test_a_land_square_reads_its_own_forecast():
    borrowed, kept = squares_mod.borrow_land({(5, 5)}, terrain_with({}) <= squares_mod.WATER_MAX_M)

    assert borrowed == {} and kept == []


def test_open_water_with_no_land_in_reach_keeps_its_own_and_is_listed():
    terrain = terrain_with({}, default=0.0)
    terrain[0, 0] = 50.0  # far outside two squares of (10, 10)

    borrowed, kept = squares_mod.borrow_land({(10, 10)}, terrain <= squares_mod.WATER_MAX_M)

    assert borrowed == {} and kept == [(10, 10)]


def test_a_mountain_where_mount_washington_is_passes_the_terrain_check():
    terrain = np.zeros((nbm_grid.HEIGHT, nbm_grid.WIDTH), dtype=np.float32)
    terrain[562, 2074] = 1702.0

    squares_mod.check_terrain(terrain)


def test_a_mirrored_terrain_grid_is_refused():
    # The first trap in WEATHER.md §6: rows reversed, and the mountain lands
    # somewhere else entirely.
    terrain = np.zeros((nbm_grid.HEIGHT, nbm_grid.WIDTH), dtype=np.float32)
    terrain[562, 2074] = 1702.0

    with pytest.raises(RuntimeError, match="Mount Washington"):
        squares_mod.check_terrain(terrain[::-1, :])


def test_a_cached_index_is_reused_only_for_its_own_release_and_schema(tmp_path, monkeypatch):
    path = tmp_path / "squares.json"
    monkeypatch.setattr(squares_mod, "SQUARES_PATH", path)

    assert squares_mod.cached_release() is None

    path.write_text(json.dumps({"schema": squares_mod.SCHEMA, "release": "2026-09-24-4"}))
    assert squares_mod.cached_release() == "2026-09-24-4"

    path.write_text(json.dumps({"schema": squares_mod.SCHEMA - 1, "release": "2026-09-24-4"}))
    assert squares_mod.cached_release() is None


# --------------------------------------------------------------------------
# Each square's NWS zones (the warnings slice).

WHITES = [[562, 2074], [563, 2076], [563, 2073]]  # Mount Washington, Pinkham Notch, Lakes of the Clouds


def lonlat_box(west, south, east, north):
    import shapely

    return shapely.box(west, south, east, north)


def test_a_square_lists_every_zone_whose_outline_reaches_it():
    # Two made-up zones split at 71.27 W, which runs between Mount Washington's
    # and Pinkham Notch's squares; a county covering all three.
    layers = {
        "forecast": (["NHZ901", "NHZ902"], [lonlat_box(-71.6, 44.0, -71.27, 44.5), lonlat_box(-71.27, 44.0, -71.0, 44.5)]),
        "county": (["NHC007"], [lonlat_box(-71.6, 44.0, -71.0, 44.5)]),
    }

    zones = squares_mod.zones_by_square(WHITES, layers)

    assert zones["county/NHC007"] == sorted(WHITES)
    assert [562, 2074] in zones["forecast/NHZ901"] and [562, 2074] not in zones["forecast/NHZ902"]
    assert [563, 2076] in zones["forecast/NHZ902"]


def test_a_forecast_zone_and_a_fire_zone_with_one_id_stay_apart():
    # NWS reuses ids across kinds: forecast zone NHZ010 and fire weather zone
    # NHZ010 can be different outlines, and a Red Flag Warning names the fire one.
    layers = {
        "forecast": (["NHZ010"], [lonlat_box(-71.6, 44.0, -71.27, 44.5)]),
        "fire": (["NHZ010"], [lonlat_box(-71.27, 44.0, -71.0, 44.5)]),
    }

    zones = squares_mod.zones_by_square(WHITES, layers)

    assert set(zones) == {"forecast/NHZ010", "fire/NHZ010"}
    assert zones["forecast/NHZ010"] != zones["fire/NHZ010"]


def test_a_zone_drawn_as_two_rows_is_one_entry_and_far_zones_are_absent():
    # c_16ap26 draws a county split between two forecast offices as two rows.
    layers = {
        "county": (
            ["NHC007", "NHC007", "GAC111"],
            [lonlat_box(-71.6, 44.0, -71.27, 44.5), lonlat_box(-71.27, 44.0, -71.0, 44.5), lonlat_box(-84.4, 34.5, -84.0, 34.8)],
        )
    }

    assert squares_mod.zones_by_square(WHITES, layers) == {"county/NHC007": sorted(WHITES)}


def test_a_zone_file_whose_md5_is_not_the_pinned_one_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(squares_mod, "ZONES_DIR", tmp_path)
    url, _, id_sql = squares_mod.ZONE_FILES["county"]
    monkeypatch.setitem(squares_mod.ZONE_FILES, "county", (url, "0" * 32, id_sql))
    monkeypatch.setattr(squares_mod, "download_with_retry", lambda url, dest, **kw: dest.write_bytes(b"a different file"))

    with pytest.raises(RuntimeError, match="MD5"):
        squares_mod.fetch_zone_file("county")
    assert not (tmp_path / url.rsplit("/", 1)[-1]).exists()


def test_a_zone_file_already_on_disk_with_the_pinned_md5_is_not_downloaded_again(tmp_path, monkeypatch):
    import hashlib

    body = b"shapefile bytes"
    url, _, id_sql = squares_mod.ZONE_FILES["fire"]
    monkeypatch.setattr(squares_mod, "ZONES_DIR", tmp_path)
    monkeypatch.setitem(squares_mod.ZONE_FILES, "fire", (url, hashlib.md5(body).hexdigest(), id_sql))
    (tmp_path / url.rsplit("/", 1)[-1]).write_bytes(body)
    monkeypatch.setattr(squares_mod, "download_with_retry", lambda *a, **kw: pytest.fail("downloaded a file it had"))

    assert squares_mod.fetch_zone_file("fire").read_bytes() == body


def test_a_county_id_is_spelled_the_way_nws_alerts_spell_it(tmp_path):
    # A real round trip through the zip reader, on a one-row shapefile shaped
    # like c_16ap26's: FIPS 24031 must come back as MDC031, the id in
    # api.weather.gov/zones/county/MDC031.
    import zipfile

    import duckdb

    folder = tmp_path / "c_test"
    folder.mkdir()
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    con.execute(
        "COPY (SELECT 'MD' AS STATE, '24031' AS FIPS, ST_GeomFromText('POLYGON((-77.5 39.0, -77.0 39.0, -77.0 39.3, -77.5 39.3, -77.5 39.0))') AS geom) "
        f"TO '{folder / 'c_test.shp'}' WITH (FORMAT GDAL, DRIVER 'ESRI Shapefile')"
    )
    con.close()
    archive = tmp_path / "c_test.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        for part in folder.iterdir():
            zf.write(part, part.name)

    ids, geometries = squares_mod.read_zone_file(archive, squares_mod.ZONE_FILES["county"][2])

    assert ids == ["MDC031"]
    assert geometries[0].bounds == pytest.approx((-77.5, 39.0, -77.0, 39.3))


# --------------------------------------------------------------------------
# HRRR's land mask (the HRRR slice): the lake-aware water rule.


def test_a_lake_square_is_water_when_hrrr_says_so_though_its_terrain_is_above_zero():
    # Lake Champlain, in miniature: URMA puts the surface at ~30 m, HRRR's
    # LAND is 0 there. Either test calling it water is enough.
    terrain = terrain_with({(10, 10): 30.0, (3, 3): 0.0})
    land = np.ones((5, 5))
    land[2, 2] = 0
    hrows = np.full(terrain.shape, 1)
    hcols = np.full(terrain.shape, 1)
    hrows[10, 10], hcols[10, 10] = 2, 2  # square (10, 10)'s centre is in HRRR's water cell

    water = squares_mod.water_mask(terrain, land, hrows, hcols)

    assert water[10, 10]  # HRRR water, terrain says land
    assert water[3, 3]  # terrain water, HRRR says land (the Hudson at Bear Mountain)
    assert not water[5, 5]


def test_a_square_off_hrrrs_grid_is_judged_by_terrain_alone():
    terrain = terrain_with({(4, 4): 0.0})
    hrows = np.full(terrain.shape, -1)
    hcols = np.full(terrain.shape, -1)

    water = squares_mod.water_mask(terrain, np.zeros((5, 5)), hrows, hcols)

    assert water[4, 4] and not water[5, 5]  # HRRR's all-water grid is never consulted


def test_a_lake_square_borrows_its_nearest_land_square():
    water = np.zeros((20, 20), dtype=bool)
    water[8:13, 8:12] = True  # rows 8-12, columns 8-11; column 12 is the east shore

    borrowed, kept = squares_mod.borrow_land({(10, 10)}, water)

    assert borrowed == {(10, 10): (10, 12)}  # two squares east; every nearer square is lake
    assert kept == []


def test_a_mountain_on_land_where_mount_washington_is_passes_the_hrrr_check():
    height = np.zeros((hrrr_grid.HEIGHT, hrrr_grid.WIDTH))
    land = np.ones_like(height)
    height[216, 1589] = 1306.0

    squares_mod.check_hrrr_terrain(height, land)


@pytest.mark.parametrize("flip", ["rows", "land"])
def test_a_mirrored_hrrr_grid_or_a_summit_in_the_sea_is_refused(flip):
    height = np.zeros((hrrr_grid.HEIGHT, hrrr_grid.WIDTH))
    land = np.ones_like(height)
    height[216, 1589] = 1306.0
    if flip == "rows":
        height = height[::-1, :]
    else:
        land[216, 1589] = 0

    with pytest.raises(RuntimeError, match="Mount Washington"):
        squares_mod.check_hrrr_terrain(height, land)


def test_a_grib_message_range_ends_where_the_next_message_starts():
    index = [
        "63:39354229:d=2026092912:HGT:surface:anl:",
        "64:41507924:d=2026092912:TMP:surface:anl:",
        "165:148726362:d=2026092912:LAND:surface:anl:",
        "166:148776838:d=2026092912:ICEC:surface:anl:",
    ]

    assert squares_mod.grib_message_range(index, "HGT", "surface") == (39354229, 41507923)
    assert squares_mod.grib_message_range(index, "LAND", "surface") == (148726362, 148776837)
    with pytest.raises(RuntimeError, match="no TMP:2 m above ground"):
        squares_mod.grib_message_range(index, "TMP", "2 m above ground")
    with pytest.raises(RuntimeError, match="last message"):
        squares_mod.grib_message_range(index, "ICEC", "surface")


def test_mount_washingtons_nbm_square_centre_is_in_the_hrrr_cell_beside_the_summits():
    # The measurement that moved HRRR onto its own cells: this square's centre
    # is in HRRR cell (215, 1589), while the summit itself is in (216, 1589).
    hrows, hcols = squares_mod.nbm_centres_on_hrrr()

    assert (int(hrows[562, 2074]), int(hcols[562, 2074])) == (215, 1589)
    assert hrows.shape == (nbm_grid.HEIGHT, nbm_grid.WIDTH)


class FakeHead:
    def __init__(self, present):
        self.present, self.asked = present, []

    def head(self, url, timeout):
        self.asked.append(url)
        return type("R", (), {"status_code": 200 if any(url.endswith(p) for p in self.present) else 404})()


def test_the_newest_hrrr_hour_zero_file_is_found_by_asking_each_hour():
    from datetime import UTC, datetime

    session = FakeHead(["hrrr.t11z.wrfsfcf00.grib2.idx"])

    key = squares_mod.newest_hrrr_analysis(session, now=datetime(2026, 9, 29, 13, 40, tzinfo=UTC))

    assert key == "hrrr.20260929/conus/hrrr.t11z.wrfsfcf00.grib2"
    assert len(session.asked) == 3  # 13Z and 12Z were not there yet
