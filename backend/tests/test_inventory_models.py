"""The structure inventory's tables hold the rules the design rests on.

#1983 — The structure inventory's five tables land in one revision, locked by
RLS, with every enum as VARCHAR + CHECK.

features/STRUCTURE_INVENTORY.md's first rule is that nothing is overwritten:
a visit is a new row, never an edit to the last one. The migration tests
prove the tables exist and are locked; these prove the rows behave the way
the routers built on them will assume.
"""

import datetime

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.inventory import (
    COVERAGE_MIN_RECORDS,
    COVERAGE_WINDOW_DAYS,
    MAX_CLAIM_DAYS_AHEAD,
    STALE_DAYS,
    Condition,
    Connection,
    FixSource,
    InventoryClaim,
    InventoryClubSettings,
    InventoryEnrollment,
    InventoryObservation,
    InventoryPass,
    InventoryStructure,
    PassState,
    Repair,
    ReviewState,
    StructureKind,
    StructureStatus,
)
from tests.factories import make_org, make_profile, make_section

# 23 readings over 38 seconds, the Location screen's own sample (2c), with
# accuracies that are not round numbers so a float that came back rounded
# would show.
READINGS = [
    {"lat": 41.4321 + i * 1e-6, "lon": -73.8765 - i * 1e-6, "acc": 4.27 + i / 10, "t": 1000 + i * 1.65} for i in range(23)
]


def _structure(db_session, club, volunteer, **fields):
    structure = InventoryStructure(
        club_id=club.id,
        kind=StructureKind.bridge,
        lat=41.4321,
        lon=-73.8765,
        created_by=volunteer.id,
        **fields,
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
            "lat": 41.4321,
            "lon": -73.8765,
            "accuracy_m": 4.3,
            "readings_count": len(READINGS),
            "readings_seconds": 38,
            "readings": READINGS,
            "condition": Condition.poor,
            "repair": Repair.major,
            **fields,
        }
    )
    db_session.add(observation)
    db_session.commit()
    return observation


def test_two_volunteers_logging_one_bridge_on_one_day_are_two_observation_rows_on_one_structure(db_session):
    club = make_org(db_session)
    first, second = make_profile(db_session), make_profile(db_session)
    bridge = _structure(db_session, club, first)

    _observation(db_session, bridge, first, condition=Condition.poor)
    _observation(db_session, bridge, second, condition=Condition.fair)

    rows = db_session.query(InventoryObservation).filter_by(structure_id=bridge.id).all()
    assert sorted(row.condition for row in rows) == [Condition.fair, Condition.poor]
    assert db_session.query(InventoryStructure).count() == 1


def test_every_gps_reading_the_phone_sent_comes_back_whole_and_in_order(db_session):
    club = make_org(db_session)
    volunteer = make_profile(db_session)
    observation = _observation(db_session, _structure(db_session, club, volunteer), volunteer)

    db_session.expire_all()
    assert db_session.get(InventoryObservation, observation.id).readings == READINGS


def test_a_new_observation_starts_submitted_with_no_photos_an_unknown_connection_and_a_sampled_fix(db_session):
    club = make_org(db_session)
    volunteer = make_profile(db_session)
    observation = _observation(db_session, _structure(db_session, club, volunteer), volunteer)

    assert observation.review_state is ReviewState.submitted
    assert observation.photo_count == 0
    assert observation.connection is Connection.unknown
    assert observation.fix_source is FixSource.sampled
    assert observation.problems == []
    # Null is "the platform did not say", never false or zero.
    assert observation.gps_lock is None
    assert observation.satellites is None
    assert observation.size_measured is None


def test_a_person_enrols_once_per_club_and_may_enrol_at_another(db_session):
    club, other_club = make_org(db_session), make_org(db_session, slug="another-trail-club")
    volunteer = make_profile(db_session)

    def enrol(at):
        db_session.add(InventoryEnrollment(club_id=at.id, person_id=volunteer.id, waiver_version="2026-1", typed_name="Pat R."))
        db_session.commit()

    enrol(club)
    enrol(other_club)
    with pytest.raises(IntegrityError):
        enrol(club)


def test_a_structure_code_is_unique_per_club_and_any_number_of_new_structures_wait_without_one(db_session):
    club, other_club = make_org(db_session), make_org(db_session, slug="another-trail-club")
    volunteer = make_profile(db_session)

    # Codes are assigned on a structure's first accepted observation, so
    # every structure still in review has none at the same time.
    _structure(db_session, club, volunteer)
    _structure(db_session, club, volunteer)
    _structure(db_session, club, volunteer, code="AT-NY-BR-014")
    _structure(db_session, other_club, volunteer, code="AT-NY-BR-014")

    with pytest.raises(IntegrityError):
        _structure(db_session, club, volunteer, code="AT-NY-BR-014")


def test_a_merged_structure_keeps_its_row_and_names_the_one_it_turned_out_to_be(db_session):
    club = make_org(db_session)
    volunteer = make_profile(db_session)
    kept = _structure(db_session, club, volunteer)
    duplicate = _structure(db_session, club, volunteer)
    _observation(db_session, duplicate, volunteer)

    duplicate.status = StructureStatus.merged
    duplicate.merged_into_id = kept.id
    db_session.commit()

    assert kept.status is StructureStatus.active
    assert db_session.query(InventoryObservation).filter_by(structure_id=duplicate.id).count() == 1


def test_a_club_settings_row_starts_from_the_unvalidated_thresholds_and_publishes_nothing(db_session):
    club = make_org(db_session)
    settings_row = InventoryClubSettings(club_id=club.id)
    db_session.add(settings_row)
    db_session.commit()

    assert (
        (
            settings_row.claim_days_ahead,
            settings_row.coverage_window_days,
            settings_row.coverage_min_records,
            settings_row.stale_days,
        )
        == (MAX_CLAIM_DAYS_AHEAD, COVERAGE_WINDOW_DAYS, COVERAGE_MIN_RECORDS, STALE_DAYS)
        == (14, 90, 3, 365)
    )
    assert settings_row.publish_locations is False
    # Enrolment stays closed until the club has written its waiver.
    assert settings_row.waiver_text is None


def test_a_pass_and_a_claim_hang_off_the_club_s_own_trail_and_section(db_session):
    club = make_org(db_session)
    volunteer = make_profile(db_session)
    section = make_section(db_session, club)

    walk = InventoryPass(club_id=club.id, volunteer_id=volunteer.id, trail_id=section.trail_id)
    claim = InventoryClaim(club_id=club.id, volunteer_id=volunteer.id, section_id=section.id, walk_on=datetime.date(2026, 11, 14))
    db_session.add_all([walk, claim])
    db_session.commit()

    assert walk.state is PassState.in_progress
    assert walk.ended_early is False
    # Unknown until the phone says, never a made-up point.
    assert (walk.to_lat, walk.to_lon) == (None, None)
    assert claim.released_at is None
