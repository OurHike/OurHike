import numpy as np
import pytest
from conftest import FEET_PER_DEG, square

from remediation_analysis import spatial


def test_feet_between_measures_a_degree_of_latitude_at_about_364000_feet():
    assert spatial.feet_between(0, 0, 1, 0) == pytest.approx(FEET_PER_DEG, rel=0.005)


def test_a_chain_of_close_sites_is_one_complex_even_where_its_ends_are_far_apart():
    # A-B 150 ft, B-C 150 ft, so A and C (300 ft apart) are joined through B. D stands alone.
    feet = [0, 150, 300, 2000]
    ids = spatial.complexes([f / FEET_PER_DEG for f in feet], [0.0] * 4, join_ft=200)
    assert ids[0] == ids[1] == ids[2] != ids[3]


def test_sites_join_only_when_closer_than_the_joining_distance():
    close = spatial.complexes([0.0, 195 / FEET_PER_DEG], [0.0, 0.0], join_ft=200)
    apart = spatial.complexes([0.0, 205 / FEET_PER_DEG], [0.0, 0.0], join_ft=200)
    assert close[0] == close[1]
    assert apart[0] != apart[1]


def brute_force(lats, lons, join_ft):
    n = len(lats)
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            i = parent[i]
        return i

    d = spatial.feet_between(lats[:, None], lons[:, None], lats[None, :], lons[None, :])
    for i in range(n):
        for j in range(i + 1, n):
            if d[i, j] < join_ft:
                parent[find(i)] = find(j)
    roots = {}
    return [roots.setdefault(find(i), len(roots)) for i in range(n)]


@pytest.mark.parametrize("latitude", [0.0, 44.0])
def test_the_grid_finds_exactly_the_complexes_comparing_every_pair_would(latitude):
    # The grid only compares neighbouring cells; this checks it never misses a
    # pair that straddles a cell edge, including where degrees of longitude are short.
    rng = np.random.default_rng(7)
    lats = latitude + rng.uniform(0, 3000, 400) / FEET_PER_DEG
    lons = rng.uniform(0, 3000, 400) / FEET_PER_DEG
    grid = spatial.complexes(lats, lons, join_ft=200)
    expected = brute_force(lats, lons, 200)
    # Same partition, whatever the numbering.
    assert len({(g, e) for g, e in zip(grid, expected)}) == len(set(grid)) == len(set(expected))


def test_nearest_names_the_closest_point_and_its_distance():
    idx, feet = spatial.nearest([0.0], [0.0], [1000 / FEET_PER_DEG, 300 / FEET_PER_DEG], [0.0, 0.0])
    assert idx[0] == 1
    assert feet[0] == pytest.approx(300, rel=0.01)


def test_land_units_finds_every_polygon_around_a_site_and_most_specific_prefers_the_wilderness():
    forest = square(0, 0, 5000, Mang_Name="USFS", Des_Tp="NF", Unit_Nm="Example National Forest")
    wilderness = square(0, 0, 1000, Mang_Name="USFS", Des_Tp="WA", Unit_Nm="Example Wilderness")
    elsewhere = square(50_000, 0, 1000, Mang_Name="NPS", Des_Tp="NP", Unit_Nm="Example Park")
    found = spatial.land_units([0.0, 3000 / FEET_PER_DEG, 1.0], [0.0, 0.0, 1.0], [forest, wilderness, elsewhere])
    assert sorted(u["Des_Tp"] for u in found[0]) == ["NF", "WA"]
    assert spatial.most_specific(found[0])["Unit_Nm"] == "Example Wilderness"
    assert [u["Des_Tp"] for u in found[1]] == ["NF"]
    assert found[2] == [] and spatial.most_specific(found[2]) is None


@pytest.mark.parametrize(
    ("to_lat", "to_lon", "expected", "word"),
    [(1, 0, 0, "N"), (0, 1, 90, "E"), (-1, 0, 180, "S"), (0, -1, 270, "W"), (1, 1, 45, "NE")],
)
def test_bearing_and_compass_point(to_lat, to_lon, expected, word):
    bearing = spatial.bearing_deg(0, 0, to_lat / 1000, to_lon / 1000)
    assert bearing == pytest.approx(expected, abs=0.5)
    assert spatial.compass(bearing) == word


def north_south_trail(east_ft: float, from_ft: float = -5000, to_ft: float = 5000) -> dict:
    return {
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": [[east_ft / FEET_PER_DEG, from_ft / FEET_PER_DEG], [east_ft / FEET_PER_DEG, to_ft / FEET_PER_DEG]],
        },
        "properties": {},
    }


def test_from_trail_finds_where_to_leave_the_trail_and_which_way_to_walk():
    # The trail runs north-south 300 ft west of the site, so the walk is 300 ft due east.
    found = spatial.from_trail([1000 / FEET_PER_DEG], [0.0], [north_south_trail(-300)])[0]
    assert found["toward"] == "E"
    assert found["bearing_deg"] == pytest.approx(90, abs=1)
    assert found["ft"] == pytest.approx(300, rel=0.01)
    assert found["lat"] == pytest.approx(1000 / FEET_PER_DEG, abs=1e-7)


def test_from_trail_takes_the_end_of_a_segment_when_the_site_is_past_it():
    # The trail stops 500 ft south of the site, so the nearest point is its end and the walk is north.
    found = spatial.from_trail([0.0], [0.0], [north_south_trail(0, -5000, -500)])[0]
    assert found["toward"] == "N"
    assert found["ft"] == pytest.approx(500, rel=0.01)


def test_from_trail_reads_every_part_of_a_multilinestring():
    near = north_south_trail(200)["geometry"]["coordinates"]
    far = north_south_trail(-3000)["geometry"]["coordinates"]
    multi = {"type": "Feature", "geometry": {"type": "MultiLineString", "coordinates": [far, near]}, "properties": {}}
    found = spatial.from_trail([0.0], [0.0], [multi])[0]
    assert found["toward"] == "W" and found["ft"] == pytest.approx(200, rel=0.01)


def test_from_trail_is_none_without_a_trail():
    assert spatial.from_trail([0.0, 1.0], [0.0, 1.0], []) == [None, None]
