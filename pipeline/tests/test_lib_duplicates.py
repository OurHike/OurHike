"""One path recorded twice, drawn once (#1459).

Every test here is about the DIRECTION the errors run. Removing a line a
hiker needs is the `lost` path, so the rule is built to miss a duplicate
rather than to delete a real second path - and most of what follows asserts
that something was KEPT.
"""

import pytest
from shapely.geometry import LineString

from lib.duplicates import (
    DUPLICATE_MIN_SHARE,
    DUPLICATE_TOLERANCE_M,
    apply_duplicates,
    find_duplicates,
    merge,
)

# Brooklyn, where the greenway and the park trail genuinely run together.
ORIGIN = (-73.970, 40.660)
_M_PER_DEG_LAT = 110_570.0
_M_PER_DEG_LON = 84_500.0  # at 40.66 deg


def _north(metres: float) -> float:
    return ORIGIN[1] + metres / _M_PER_DEG_LAT


def _east(metres: float) -> float:
    return ORIGIN[0] + metres / _M_PER_DEG_LON


def _line(points, key="x", source="nyc_dot_greenways", **extra):
    return {"id": key, "source": source, "wkt": LineString(points).wkt, **extra}


def _run(length_m: float, offset_m: float = 0.0, start_m: float = 0.0, **kw):
    """A north-south line `length_m` long, `offset_m` east of the origin."""
    return _line([(_east(offset_m), _north(start_m)), (_east(offset_m), _north(start_m + length_m))], **kw)


PARKS = [_line([(ORIGIN[0], ORIGIN[1]), (ORIGIN[0], _north(400))], key="p1", source="nyc_parks_trails", name="Park Loop")]


def test_a_greenway_laid_along_a_parks_trail_is_a_duplicate():
    """The case the whole module exists for: two agencies digitised one path,
    so the map should draw it once."""
    alongside = _run(400.0, offset_m=4.0, key="g1")

    duplicates, stats = find_duplicates(PARKS, [alongside])

    assert duplicates == {"g1": "p1"}
    assert stats["duplicates"] == 1


def test_a_greenway_that_only_touches_is_kept():
    """The conservative half of the rule, and the reason it is a SHARE rather
    than a hit: outside the stretch they share, this record is the only one
    of that path. Measured on the real layers, 86 greenway records land
    here - they would all have gone under a whole-jurisdiction cut."""
    # 2 km long, running beside the 400 m parks trail for its first fifth.
    touching = _run(2000.0, offset_m=4.0, key="g2")

    duplicates, stats = find_duplicates(PARKS, [touching])

    assert duplicates == {}
    assert stats["touched_but_kept"] == 1


def test_a_parallel_path_a_street_away_is_kept():
    """Two sides of a boulevard digitised apart are two paths. 10 m is under
    the width of the drawn line at z14 and 25 m is not, which is why the
    tolerance here is the tighter of the two figures #1453 reports."""
    a_street_away = _run(400.0, offset_m=22.0, key="g3")

    duplicates, _stats = find_duplicates(PARKS, [a_street_away])

    assert duplicates == {}
    # And it WOULD be taken at the generous radius - so the constant is doing
    # the work, not the geometry happening to miss.
    wide, _ = find_duplicates(PARKS, [a_street_away], tolerance_m=25.0)
    assert wide == {"g3": "p1"}


def test_a_crossing_greenway_is_kept():
    """A path crossing a trail shares a few metres of ground with it. In a
    city that is every junction, and counting them would empty the map."""
    crossing = _line(
        [(_east(-500.0), _north(200.0)), (_east(500.0), _north(200.0))],
        key="g4",
    )

    duplicates, _stats = find_duplicates(PARKS, [crossing])

    assert duplicates == {}


def test_no_senior_records_removes_nothing():
    """A source that failed to fetch, or is held back by `reaches_hikers`,
    must not silently delete the other one's lines."""
    duplicates, stats = find_duplicates([], [_run(400.0, offset_m=4.0, key="g5")])

    assert duplicates == {}
    assert stats["duplicates"] == 0


def test_the_survivor_inherits_a_name_the_senior_does_not_have():
    """#1432's placeholder rule leaves 3,777 NYC Parks rows nameless, so the
    senior frequently has no name at all - and a path carrying the junior's
    name is more use to somebody standing on it than a path with none."""
    senior = {"id": "p1", "source": "nyc_parks_trails", "name": None, "wkt": "LINESTRING (0 0, 0 1)"}
    junior = {"id": "g1", "source": "nyc_dot_greenways", "name": "Bronx River Greenway", "wkt": "LINESTRING (0 0, 0 1)"}

    survivor = merge(senior, junior)

    assert survivor["name"] == "Bronx River Greenway"
    assert survivor["duplicate_of"] == "nyc_dot_greenways"


def test_the_senior_keeps_a_field_it_has():
    """Per-field and senior-first. Neither agency is uniformly better, but on
    a field both filled the land manager's own record wins."""
    senior = {"id": "p1", "source": "nyc_parks_trails", "name": "Park Loop", "wkt": "LINESTRING (0 0, 0 1)"}
    junior = {"id": "g1", "source": "nyc_dot_greenways", "name": "Some Greenway", "wkt": "LINESTRING (0 0, 0 1)"}

    assert merge(senior, junior)["name"] == "Park Loop"


def test_the_survivor_never_takes_the_losers_geometry():
    senior = {"id": "p1", "source": "nyc_parks_trails", "wkt": "LINESTRING (0 0, 0 1)"}
    junior = {"id": "g1", "source": "nyc_dot_greenways", "wkt": "LINESTRING (9 9, 9 8)"}

    assert merge(senior, junior)["wkt"] == "LINESTRING (0 0, 0 1)"


def test_applying_removes_the_junior_and_keeps_the_order():
    """Feature order must not shuffle when a pair is found or lost, or every
    reader of the artifact sees a diff that is not a change."""
    records = [
        {"id": "a", "source": "nyc_parks_trails"},
        {"id": "g1", "source": "nyc_dot_greenways"},
        {"id": "p1", "source": "nyc_parks_trails"},
        {"id": "b", "source": "nyc_dot_greenways"},
    ]

    kept = apply_duplicates(records, {"g1": "p1"})

    assert [r["id"] for r in kept] == ["a", "p1", "b"]
    assert next(r for r in kept if r["id"] == "p1")["duplicate_of"] == "nyc_dot_greenways"


def test_a_duplicate_whose_survivor_is_gone_keeps_the_junior():
    """A senior dropped by a closure after the pairing was computed. Losing
    both would leave a hiker with no line where two organizations hold one -
    the direction that costs somebody something."""
    records = [{"id": "g1", "source": "nyc_dot_greenways"}]

    assert [r["id"] for r in apply_duplicates(records, {"g1": "p1"})] == ["g1"]


@pytest.mark.parametrize("share", [0.0, 1.5, -0.1])
def test_an_impossible_share_is_refused(share):
    with pytest.raises(ValueError):
        find_duplicates(PARKS, [], min_share=share)


def test_the_constants_are_the_conservative_end():
    """Pinned because loosening either silently removes more of somebody's
    map, and the argument for both is in the module docstring rather than in
    whoever edits them next."""
    assert DUPLICATE_TOLERANCE_M == 10.0
    assert DUPLICATE_MIN_SHARE == 0.5
