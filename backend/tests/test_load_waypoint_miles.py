"""`load_waypoint_miles.py`: the one writer of `waypoint_miles`.

#1917 - A maintainer's note settles a water dispute anywhere on the trail,
because the covering check reads the mile the note's author typed, not where
the waypoint is. `GET /disputes` now reads each waypoint's mile from this
table, so what the loader keeps, moves, drops and refuses decides which
maintainer's word counts where.
"""

import json

import pytest
from sqlalchemy.orm import sessionmaker

import load_waypoint_miles
from app.models.waypoint_mile import WaypointMile
from load_waypoint_miles import InvalidFile, apply, main, parse


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
        ({"x.geojson": {"type": "FeatureCollection", "features": ["not a feature"]}}, "not a GeoJSON Feature"),
        ({"x.geojson": {"type": "FeatureCollection", "features": [{"properties": []}]}}, "not a GeoJSON Feature"),
        ({"x.geojson": _collection(("p", -500.0))}, "no position on a trail"),
        ({"x.geojson": _collection(("p", 1e9))}, "no position on a trail"),
    ],
    ids=[
        "not-geojson",
        "no-id",
        "two-miles-for-one-waypoint",
        "nothing-placed",
        "feature-not-an-object",
        "properties-not-an-object",
        "mile-before-springer",
        "mile-past-any-trail",
    ],
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


def test_a_load_that_would_delete_most_of_the_table_is_refused(db_session):
    """One type's file standing in for every type's: measured against release
    2026-10-10-2, `poi_water.geojson` alone would have deleted 2,592 of 3,024
    rows. Refused before anything is written, unless the release really did
    retire them."""
    apply(db_session, {f"w:{index}": float(index) for index in range(40)})
    db_session.commit()

    with pytest.raises(InvalidFile, match="would delete 35 of the 40 waypoints"):
        apply(db_session, {f"w:{index}": float(index) for index in range(5)})
    db_session.rollback()
    assert len(_table(db_session)) == 40

    apply(db_session, {f"w:{index}": float(index) for index in range(5)}, allow_shrink=True)
    db_session.commit()
    assert len(_table(db_session)) == 5


def test_every_kept_row_is_stamped_with_the_run(db_session):
    """So `max(loaded_at)` says when the table last matched a release, even
    when the release moved nothing."""
    apply(db_session, {"a": 1.0})
    db_session.commit()
    first = db_session.query(WaypointMile).one().loaded_at

    assert apply(db_session, {"a": 1.0}) == []
    db_session.commit()
    db_session.expire_all()

    assert db_session.query(WaypointMile).one().loaded_at > first


@pytest.fixture()
def run(db_engine, monkeypatch, tmp_path):
    """`main` as an operator runs it, against this test's database, with
    files written where it reads them."""
    monkeypatch.setattr(load_waypoint_miles, "SessionLocal", sessionmaker(bind=db_engine))

    def write(relative: str, *features: tuple[str, object]) -> str:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(_collection(*features)), encoding="utf-8")
        return str(path)

    return write


def test_main_without_commit_writes_nothing(run, db_session, capsys):
    assert main([run("poi_water.geojson", ("w:1", 10.0))]) == 0

    assert _table(db_session) == {}
    assert "NOT written" in capsys.readouterr().out


def test_main_with_commit_writes(run, db_session):
    assert main([run("poi_water.geojson", ("w:1", 10.0)), "--commit"]) == 0

    assert _table(db_session) == {"w:1": 10.0}


def test_main_refuses_a_file_name_given_twice(run, db_session, capsys):
    """Two `poi_water.geojson` from two downloads: keyed by name, the second
    silently replaced the first, so `w:2` was lost and the two files'
    disagreement about `w:1` was never seen."""
    first = run("a/poi_water.geojson", ("w:1", 10.0), ("w:2", 20.0))
    second = run("b/poi_water.geojson", ("w:1", 99.0))

    assert main([first, second, "--commit"]) == 2

    assert _table(db_session) == {}
    assert "given twice" in capsys.readouterr().err
