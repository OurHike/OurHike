"""`load_waypoint_miles.py`: the one writer of `waypoint_miles`.

#1917 - A maintainer's note settles a water dispute anywhere on the trail,
because the covering check reads the mile the note's author typed, not where
the waypoint is. `GET /disputes` now reads each waypoint's mile from this
table, so what the loader keeps, moves, drops and refuses decides which
maintainer's word counts where.
"""

import pytest

from app.models.waypoint_mile import WaypointMile
from load_waypoint_miles import InvalidFile, apply, parse


def _collection(*features: tuple[str, object]) -> dict:
    """A published waypoint GeoJSON, as export_poi.py writes it: `id` and `mile` among the properties."""
    return {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "geometry": None, "properties": {"id": poi_id, "mile": mile, "name": "x"}}
            for poi_id, mile in features
        ],
    }


def _table(db_session) -> dict[str, float]:
    return {row.poi_id: row.mile for row in db_session.query(WaypointMile).all()}


def test_it_reads_each_waypoints_mile_across_every_types_file():
    miles = parse(
        {
            "shelters.geojson": _collection(("atc_shelters:a", 12.5), ("atc_shelters:b", 1405.0)),
            "water.geojson": _collection(("atc_water:c", 800.25)),
        }
    )

    assert miles == {"atc_shelters:a": 12.5, "atc_shelters:b": 1405.0, "atc_water:c": 800.25}


def test_a_waypoint_whose_file_has_no_usable_mile_is_left_out():
    """export_poi.py withholds a mile from a waypoint on another
    organization's trail (`mark_off_trail_records`), and the GeoJSON writer
    puts that absent mile down as null. A mile that is not a finite number is
    not a position either."""
    miles = parse({"water.geojson": _collection(("on", 5.0), ("off", None), ("nan", float("nan")), ("text", "12"))})

    assert miles == {"on": 5.0}


@pytest.mark.parametrize(
    ("documents", "says"),
    [
        ({"x.geojson": {"type": "Feature"}}, "not a GeoJSON FeatureCollection"),
        ({"x.geojson": _collection(("", 5.0))}, "no `id`"),
        ({"a.geojson": _collection(("p", 5.0)), "b.geojson": _collection(("p", 6.0))}, "mile 5.0 in one file"),
        ({"x.geojson": _collection(("p", None))}, "would empty waypoint_miles"),
    ],
    ids=["not-geojson", "no-id", "two-miles-for-one-waypoint", "nothing-placed"],
)
def test_files_that_cannot_be_the_published_export_are_refused(documents, says):
    with pytest.raises(InvalidFile, match=says):
        parse(documents)


def test_the_table_ends_up_matching_the_files(db_session):
    apply(db_session, {"kept": 1.0, "moved": 2.0, "dropped": 3.0})
    db_session.commit()

    changes = apply(db_session, {"kept": 1.0, "moved": 2.5, "new": 4.0})
    db_session.commit()

    assert _table(db_session) == {"kept": 1.0, "moved": 2.5, "new": 4.0}
    assert changes == [
        "waypoint ~ moved moved from mile 2.0 to 2.5",
        "waypoint + new at mile 4.0",
        "waypoint - dropped, in no file given",
    ]


def test_an_unchanged_file_changes_nothing(db_session):
    apply(db_session, {"a": 1.0})
    db_session.commit()

    assert apply(db_session, {"a": 1.0}) == []


def test_a_run_rolled_back_writes_nothing(db_session):
    """What `main` does without --commit."""
    apply(db_session, {"a": 1.0})
    db_session.rollback()

    assert _table(db_session) == {}
