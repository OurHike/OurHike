"""The server's mile, against the phone's, and the edges of placing a point (#1987).

#1987 — The server computes an observation's mile and distance to the line
from the club's own section geometry, and stores both beside the raw point.

`client/src/lib/trailAxis.golden.json` is one synthetic centerline with a
published mile per vertex, and four points. `client/src/lib/trailAxis.golden.test.ts`
records what the phone's `locateOnTrail` answers for each, and fails when that
answer changes. This half draws a section along the same line - from its first
published mile to its last, which is how a club's section and the published
axis are meant to relate - and requires `app/core/trail_axis.py` to agree:
the mile within `AGREEMENT_MILES`, the same refusal past the gate, and a
distance off the line no greater than the phone's.

The rest of the file is the cases the golden line does not reach: which
sections are searched, what a drawn line must be, and what the backfill
command fills and leaves alone.
"""

from __future__ import annotations

import datetime
import importlib.util
import json
import sys
from contextlib import contextmanager
from pathlib import Path

import pytest

from app.core.trail_axis import (
    FEET_PER_MILE,
    MAX_OFF_LINE_FT,
    place,
    place_observation,
    place_structure,
    project_onto_line,
    section_line,
)
from app.models.inventory import (
    Condition,
    InventoryObservation,
    InventoryStructure,
    Repair,
    ReviewState,
    StructureKind,
)
from tests.factories import make_org, make_profile, make_section

GOLDEN = Path(__file__).resolve().parents[2] / "client" / "src" / "lib" / "trailAxis.golden.json"
SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "inventory_place.py"

# Read by tests/test_ci_scope.py, which fails if backend-tests.yml's scope list
# stops naming this file - a client-only pull request is the one that changes it.
CLIENT_FILES_READ = (GOLDEN,)

#: How far the server's mile may sit from the phone's on the golden line.
#: @unvalidated: the handoff's pick (ISSUES.md issue 5). What settles it is
#: one real section's drawn line and the largest disagreement between the
#: two projections along it - see app/core/trail_axis.py.
AGREEMENT_MILES = 0.05

# A straight east-west line about 1.04 mi long at Harriman's latitude, for
# the cases where the exact answer should be readable off the geometry.
WEST, EAST, LAT = (-74.10, 41.24), (-74.08, 41.24), 41.24
FEET_PER_DEGREE_LAT = 20_902_231 * 3.141592653589793 / 180


def _golden() -> dict:
    assert GOLDEN.exists(), f"{GOLDEN} is missing, so nothing can be compared"
    return json.loads(GOLDEN.read_text(encoding="utf-8"))


def _line_text(coords) -> str:
    return json.dumps({"type": "LineString", "coordinates": [list(vertex) for vertex in coords]})


def _drawn(db_session, club, coords, *, start_mile=100.0, end_mile=101.0, name="Pine Meadow North"):
    return make_section(db_session, club, name=name, start_mile=start_mile, end_mile=end_mile, geometry=_line_text(coords))


@pytest.fixture()
def golden_section(db_session):
    golden = _golden()
    feature = golden["trails"]["features"][0]
    miles = golden["miles"][feature["properties"]["id"]]
    club = make_org(db_session)
    section = _drawn(db_session, club, feature["geometry"]["coordinates"], start_mile=miles[0], end_mile=miles[-1], name="Golden")
    return club, section, golden["points"]


# --- Against the phone -------------------------------------------------------


def test_the_servers_mile_is_within_a_twentieth_of_a_mile_of_the_phones_at_each_golden_point(db_session, golden_section):
    club, section, points = golden_section

    for point in points[:3]:
        placement = place(db_session, club.id, point["lat"], point["lon"])

        assert placement is not None, point["name"]
        assert placement.section_id == section.id
        assert abs(placement.mile - point["locateOnTrail"]["mile"]) <= AGREEMENT_MILES, point["name"]


def test_the_largest_disagreement_on_the_golden_line_is_the_one_the_module_docstring_quotes(db_session, golden_section):
    """app/core/trail_axis.py quotes 0.017 mi; this is where that number comes from."""
    club, _, points = golden_section

    largest = max(
        abs(place(db_session, club.id, point["lat"], point["lon"]).mile - point["locateOnTrail"]["mile"]) for point in points[:3]
    )

    assert round(largest, 3) == 0.017


def test_the_distance_off_the_line_is_never_more_than_the_phones_distance_to_its_nearest_vertex(db_session, golden_section):
    """The phone measures to a vertex, the server to the segment, which is never farther."""
    club, _, points = golden_section

    for point in points[:3]:
        placement = place(db_session, club.id, point["lat"], point["lon"])

        # One foot of slack, for the server rounding to whole feet.
        assert placement.off_line_ft <= point["locateOnTrail"]["offTrailFeet"] + 1, point["name"]


def test_the_point_the_phone_refuses_past_its_three_mile_gate_the_server_refuses_too(db_session, golden_section):
    club, _, points = golden_section
    beyond = points[3]

    assert beyond["locateOnTrail"] is None
    assert place(db_session, club.id, beyond["lat"], beyond["lon"]) is None


# --- The geometry, where the answer can be read off it -----------------------


def test_a_point_a_hundred_feet_north_of_the_middle_of_a_line_reads_the_middle_mile_and_a_hundred_feet(
    db_session,
):
    club = make_org(db_session)
    _drawn(db_session, club, [WEST, EAST], start_mile=100.0, end_mile=101.0)

    placement = place(db_session, club.id, LAT + 100 / FEET_PER_DEGREE_LAT, -74.09)

    assert placement.mile == pytest.approx(100.5, abs=0.001)
    assert placement.off_line_ft == pytest.approx(100, abs=1)


def test_a_line_is_read_from_its_first_coordinate_at_the_start_mile(db_session):
    """The assumption the module docstring tags @unvalidated: nothing on the row
    says which way a line was drawn, so the first coordinate is the start."""
    club = make_org(db_session)
    _drawn(db_session, club, [EAST, WEST], start_mile=100.0, end_mile=101.0)

    near_the_east_end = place(db_session, club.id, LAT, -74.0801)

    assert near_the_east_end.mile == pytest.approx(100.0, abs=0.01)


def test_a_point_past_the_end_of_a_line_is_measured_to_the_end_and_reads_the_end_mile(db_session):
    club = make_org(db_session)
    _drawn(db_session, club, [WEST, EAST], start_mile=100.0, end_mile=101.0)

    half_a_mile_east = place(db_session, club.id, LAT, -74.08 + 0.5 * FEET_PER_MILE / (FEET_PER_DEGREE_LAT * 0.752))

    assert half_a_mile_east.mile == 101.0
    assert half_a_mile_east.off_line_ft == pytest.approx(0.5 * FEET_PER_MILE, rel=0.01)


def test_a_point_just_inside_the_gate_is_placed_and_one_just_outside_is_not(db_session):
    club = make_org(db_session)
    _drawn(db_session, club, [WEST, EAST])
    inside = (MAX_OFF_LINE_FT - 50) / FEET_PER_DEGREE_LAT
    outside = (MAX_OFF_LINE_FT + 50) / FEET_PER_DEGREE_LAT

    assert place(db_session, club.id, LAT + inside, -74.09) is not None
    assert place(db_session, club.id, LAT + outside, -74.09) is None


def test_the_fraction_along_a_line_is_measured_by_length_not_by_vertex_count():
    """Three vertices bunched at the west end must not pull the middle west."""
    line = [WEST, (-74.0999, LAT), (-74.0998, LAT), EAST]

    fraction, feet = project_onto_line(line, -74.09, LAT)

    assert fraction == pytest.approx(0.5, abs=0.001)
    assert feet == pytest.approx(0, abs=0.5)


# --- Which sections are searched ----------------------------------------------


def test_a_club_that_has_drawn_no_section_gets_no_placement(db_session):
    """The maintainer's choice by poll, 2026-11-04: no published fallback, so no mile."""
    club = make_org(db_session)
    make_section(db_session, club, geometry=None)

    assert place(db_session, club.id, LAT, -74.09) is None


def test_another_clubs_line_is_never_used_however_close_the_point_is(db_session):
    ours = make_org(db_session)
    theirs = make_org(db_session, slug="other-trail-club", domain="other.example.org")
    _drawn(db_session, theirs, [WEST, EAST])

    assert place(db_session, ours.id, LAT, -74.09) is None


def test_the_nearest_of_two_drawn_sections_places_the_point(db_session):
    club = make_org(db_session)
    _drawn(db_session, club, [WEST, EAST], start_mile=100.0, end_mile=101.0, name="South")
    north = _drawn(
        db_session,
        club,
        [(-74.10, 41.25), (-74.08, 41.25)],
        start_mile=101.0,
        end_mile=102.0,
        name="North",
    )

    placement = place(db_session, club.id, 41.249, -74.09)

    assert placement.section_id == north.id
    assert placement.mile == pytest.approx(101.5, abs=0.001)


def test_a_section_drawn_without_its_miles_places_the_point_with_a_distance_and_no_mile(db_session):
    club = make_org(db_session)
    section = _drawn(db_session, club, [WEST, EAST], start_mile=None, end_mile=None)

    placement = place(db_session, club.id, LAT + 100 / FEET_PER_DEGREE_LAT, -74.09)

    assert placement.section_id == section.id
    assert placement.mile is None
    assert placement.off_line_ft == pytest.approx(100, abs=1)


def test_a_section_whose_line_cannot_be_read_is_skipped_and_the_readable_one_is_used(db_session):
    club = make_org(db_session)
    make_section(db_session, club, name="Broken", geometry="not json")
    readable = _drawn(db_session, club, [WEST, EAST], name="Readable")

    assert place(db_session, club.id, LAT, -74.09).section_id == readable.id


# --- What a drawn line must be ---------------------------------------------------


@pytest.mark.parametrize(
    "geometry",
    [
        None,
        "",
        "not json",
        json.dumps({"type": "Point", "coordinates": [-74.09, 41.24]}),
        json.dumps({"type": "MultiLineString", "coordinates": [[list(WEST), list(EAST)]]}),
        json.dumps({"type": "LineString", "coordinates": [list(WEST)]}),
        json.dumps({"type": "LineString", "coordinates": [list(WEST), list(WEST)]}),
        json.dumps({"type": "LineString", "coordinates": [list(WEST), [-74.08, 91.0]]}),
        json.dumps({"type": "LineString", "coordinates": [list(WEST), ["-74.08", "41.24"]]}),
        json.dumps({"type": "LineString", "coordinates": [list(WEST), [True, False]]}),
        json.dumps({"type": "LineString", "coordinates": "nope"}),
        json.dumps({"type": "Feature", "geometry": None}),
    ],
    ids=[
        "none",
        "empty",
        "not-json",
        "point",
        "multilinestring",
        "one-vertex",
        "no-length",
        "latitude-out-of-range",
        "strings",
        "booleans",
        "coordinates-not-a-list",
        "feature-with-no-geometry",
    ],
)
def test_a_line_that_is_not_one_readable_linestring_is_refused(geometry):
    assert section_line(geometry) is None


def test_a_feature_wrapping_a_linestring_with_heights_is_read_as_its_line():
    text = json.dumps(
        {"type": "Feature", "properties": {}, "geometry": {"type": "LineString", "coordinates": [[*WEST, 300], [*EAST, 320]]}}
    )

    assert section_line(text) == [WEST, EAST]


# --- Writing the placement beside the point ------------------------------------


def _structure(db_session, club, volunteer, **fields):
    structure = InventoryStructure(
        **{"club_id": club.id, "kind": StructureKind.bridge, "lat": LAT, "lon": -74.09, "created_by": volunteer.id, **fields}
    )
    db_session.add(structure)
    db_session.commit()
    return structure


def _observation(db_session, structure, volunteer, **fields):
    observation = InventoryObservation(
        **{
            "structure_id": structure.id,
            "club_id": structure.club_id,
            "volunteer_id": volunteer.id,
            "captured_at": datetime.datetime(2026, 11, 2, 10, 14),
            "lat": structure.lat,
            "lon": structure.lon,
            "accuracy_m": 4.3,
            "readings_count": 1,
            "readings_seconds": 0,
            "readings": [{"lat": structure.lat, "lon": structure.lon, "acc": 4.3, "t": 0}],
            "condition": Condition.poor,
            "repair": Repair.major,
            **fields,
        }
    )
    db_session.add(observation)
    db_session.commit()
    return observation


def test_placing_an_observation_stores_the_mile_beside_the_point_and_leaves_the_point_alone(db_session):
    club = make_org(db_session)
    _drawn(db_session, club, [WEST, EAST], start_mile=100.0, end_mile=101.0)
    volunteer = make_profile(db_session)
    observation = _observation(db_session, _structure(db_session, club, volunteer), volunteer)

    place_observation(db_session, observation)

    assert (observation.mile, observation.off_line_ft) == (pytest.approx(100.5, abs=0.001), 0)
    assert (observation.lat, observation.lon) == (LAT, -74.09)


def test_an_observation_that_cannot_be_placed_keeps_its_blank_mile(db_session):
    club = make_org(db_session)
    volunteer = make_profile(db_session)
    observation = _observation(db_session, _structure(db_session, club, volunteer), volunteer)

    assert place_observation(db_session, observation) is None
    assert (observation.mile, observation.off_line_ft) == (None, None)


def test_placing_a_structure_puts_it_in_the_section_its_point_is_nearest(db_session):
    club = make_org(db_session)
    section = _drawn(db_session, club, [WEST, EAST])
    structure = _structure(db_session, club, make_profile(db_session))

    place_structure(db_session, structure)

    assert structure.section_id == section.id
    assert structure.mile == pytest.approx(100.5, abs=0.001)


def test_a_structure_that_cannot_be_placed_keeps_the_section_it_had(db_session):
    """Losing a placement because a line was deleted is not evidence the structure moved."""
    club = make_org(db_session)
    undrawn = make_section(db_session, club, geometry=None)
    structure = _structure(db_session, club, make_profile(db_session), section_id=undrawn.id)

    assert place_structure(db_session, structure) is None
    assert structure.section_id == undrawn.id


# --- The backfill command ---------------------------------------------------------


@pytest.fixture()
def script(db_session, monkeypatch):
    spec = importlib.util.spec_from_file_location("inventory_place_script", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    # Registered before it runs: the script's dataclass looks its own module
    # up by name, which a module loaded from a path is not until it is added.
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)

    @contextmanager
    def session():
        yield db_session

    monkeypatch.setattr(module, "SessionLocal", session)
    return module


def test_the_command_fills_accepted_records_and_leaves_submitted_ones_for_accept(db_session, script, capsys):
    club = make_org(db_session)
    _drawn(db_session, club, [WEST, EAST])
    volunteer = make_profile(db_session)
    structure = _structure(db_session, club, volunteer)
    accepted = _observation(db_session, structure, volunteer, review_state=ReviewState.accepted)
    submitted = _observation(db_session, structure, volunteer)

    assert script.main([]) == 0

    db_session.refresh(accepted)
    db_session.refresh(submitted)
    db_session.refresh(structure)
    assert accepted.mile == pytest.approx(100.5, abs=0.001)
    assert submitted.mile is None
    assert structure.mile == pytest.approx(100.5, abs=0.001)
    out = capsys.readouterr().out
    assert "Accepted observations with no mile: 1. Placed 1; 0 have no drawn section" in out
    assert "Structures with an accepted observation with no mile: 1. Placed 1" in out


def test_the_command_never_overwrites_a_mile_already_stored(db_session, script):
    club = make_org(db_session)
    _drawn(db_session, club, [WEST, EAST])
    volunteer = make_profile(db_session)
    structure = _structure(db_session, club, volunteer, mile=7.0)
    observation = _observation(db_session, structure, volunteer, review_state=ReviewState.accepted, mile=7.0)

    assert script.main([]) == 0

    db_session.refresh(observation)
    db_session.refresh(structure)
    assert (observation.mile, structure.mile) == (7.0, 7.0)


def test_the_command_leaves_a_structure_nobody_has_accepted_for_accept(db_session, script):
    club = make_org(db_session)
    _drawn(db_session, club, [WEST, EAST])
    volunteer = make_profile(db_session)
    structure = _structure(db_session, club, volunteer)
    _observation(db_session, structure, volunteer)

    assert script.main([]) == 0

    db_session.refresh(structure)
    assert structure.mile is None


def test_the_command_counts_what_it_could_not_place_and_says_so_the_same_way_twice(db_session, script, capsys):
    club = make_org(db_session)
    volunteer = make_profile(db_session)
    _observation(db_session, _structure(db_session, club, volunteer), volunteer, review_state=ReviewState.accepted)

    assert script.main([]) == 0
    first = capsys.readouterr().out
    assert script.main([]) == 0

    assert "Accepted observations with no mile: 1. Placed 0; 1 have no drawn section within 3 mi" in first
    assert capsys.readouterr().out == first


def test_the_command_places_one_organization_when_asked(db_session, script):
    ours = make_org(db_session)
    theirs = make_org(db_session, slug="other-trail-club", domain="other.example.org")
    volunteer = make_profile(db_session)
    for club in (ours, theirs):
        _drawn(db_session, club, [WEST, EAST], name=f"{club.slug} line")
    our_record = _observation(db_session, _structure(db_session, ours, volunteer), volunteer, review_state=ReviewState.accepted)
    their_record = _observation(
        db_session, _structure(db_session, theirs, volunteer), volunteer, review_state=ReviewState.accepted
    )

    assert script.main(["--club", ours.slug]) == 0

    db_session.refresh(our_record)
    db_session.refresh(their_record)
    assert our_record.mile is not None
    assert their_record.mile is None


def test_the_command_refuses_a_slug_no_organization_has(db_session, script, capsys):
    assert script.main(["--club", "no-such-club"]) == 2
    assert "No organization has the slug 'no-such-club'" in capsys.readouterr().err
