"""An observation's upload: idempotent on its id, every reading kept.

#1985 — An observation uploads once, idempotent on its id, creates its structure when the structure is new, and keeps every GPS reading it was given.

Who may upload is test_org_permission_matrix.py's job. This file holds the
outbox's contract - a second send of a record answers the first and changes
nothing - and the rules a record carries in: a new structure needs its kind,
a size is a bucket or a measurement and never both, and nothing a volunteer
sends sets a mile.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.core.time import utc_now
from app.models.club import OrgState
from app.models.inventory import (
    Condition,
    InventoryClubSettings,
    InventoryEnrollment,
    InventoryObservation,
    InventoryPass,
    InventoryStructure,
    ReviewState,
    StructureKind,
    StructureStatus,
)
from tests.factories import make_org, make_profile, make_section
from tests.tokens import auth_headers

READINGS = [{"lat": 41.4321 + i * 1e-6, "lon": -73.8765, "acc": 4.0 + i / 10, "t": 1_000 + i} for i in range(23)]


def _volunteer(db_session, org, *, trained=True):
    person = make_profile(db_session)
    db_session.add(
        InventoryEnrollment(
            club_id=org.id,
            person_id=person.id,
            waiver_version="2026-1",
            typed_name="Pat R.",
            training_completed_at=utc_now() if trained else None,
        )
    )
    db_session.commit()
    return person


@pytest.fixture
def survey(db_session):
    org = make_org(db_session, state=OrgState.claimed)
    db_session.add(InventoryClubSettings(club_id=org.id, waiver_text="Words.", waiver_version="2026-1"))
    db_session.commit()
    return {"org": org, "volunteer": _volunteer(db_session, org), "url": f"/clubs/{org.slug}/inventory/observations"}


def _record(**changes):
    body = {
        "id": str(uuid.uuid4()),
        "structure_id": str(uuid.uuid4()),
        "kind": "bridge",
        "captured_at": "2026-11-02T10:14:00-05:00",
        "offline": True,
        "readings": READINGS,
        "readings_seconds": 38,
        "condition": "poor",
        "problems": ["abutment_eroded", "spongy_decking"],
        "repair": "major",
        "timing": "this_season",
        "size_method": "bucket",
        "size_bucket": "10_to_25_ft",
        "railings": False,
        "notes": "Two deck boards rotted through near the west end.",
    }
    return {**body, **changes}


def _send(client, survey, body, person=None):
    return client.post(survey["url"], json=body, headers=auth_headers((person or survey["volunteer"]).id))


def test_the_first_record_of_a_new_structure_creates_both_and_starts_submitted(client, survey, db_session):
    body = _record()

    response = _send(client, survey, body)

    assert response.status_code == 201
    receipt = response.json()
    assert receipt == {
        "observation_id": body["id"],
        "structure_id": body["structure_id"],
        "review_state": "submitted",
        "mile": None,
        "off_line_ft": None,
    }
    structure = db_session.get(InventoryStructure, body["structure_id"])
    assert structure.kind is StructureKind.bridge
    assert structure.created_by == survey["volunteer"].id
    # The median of the 23 readings, derived by the server: the twelfth.
    assert (structure.lat, structure.lon) == (pytest.approx(41.4321 + 11e-6), pytest.approx(-73.8765))


def test_every_reading_is_kept_whole_and_the_server_counts_them(client, survey, db_session):
    body = _record()
    _send(client, survey, body)

    row = db_session.get(InventoryObservation, body["id"])
    assert row.readings == READINGS
    assert row.readings_count == 23
    assert row.readings_seconds == 38


def test_the_phones_local_time_is_stored_as_utc(client, survey, db_session):
    body = _record(captured_at="2026-11-02T10:14:00-05:00")
    _send(client, survey, body)

    assert db_session.get(InventoryObservation, body["id"]).captured_at == datetime(2026, 11, 2, 15, 14)


def test_a_second_send_of_one_record_answers_the_first_and_changes_nothing(client, survey, db_session):
    """The outbox retries until it hears back. A retry that rewrote the row
    would let a stale copy on the phone overwrite what a reviewer acted on."""
    body = _record()
    first = _send(client, survey, body)
    row = db_session.get(InventoryObservation, body["id"])
    row.review_state = ReviewState.accepted
    db_session.commit()

    second = _send(client, survey, {**body, "condition": "unsafe", "notes": "Changed my mind."})

    assert (first.status_code, second.status_code) == (201, 200)
    assert second.json()["review_state"] == "accepted"
    db_session.expire_all()
    stored = db_session.get(InventoryObservation, body["id"])
    assert stored.condition is Condition.poor
    assert stored.notes == "Two deck boards rotted through near the west end."
    assert db_session.query(InventoryObservation).count() == 1


def test_two_visits_to_one_structure_are_two_records_on_one_structure(client, survey, db_session):
    first = _record()
    second = _record(structure_id=first["structure_id"], kind=None, condition="fair")

    assert _send(client, survey, first).status_code == 201
    assert _send(client, survey, second).status_code == 201

    assert db_session.query(InventoryStructure).count() == 1
    assert db_session.query(InventoryObservation).filter_by(structure_id=first["structure_id"]).count() == 2


def test_a_structure_nobody_has_logged_needs_its_kind(client, survey):
    assert _send(client, survey, _record(kind=None)).status_code == 422


def test_a_record_that_calls_a_logged_bridge_a_privy_is_refused(client, survey):
    first = _record()
    _send(client, survey, first)

    response = _send(client, survey, _record(structure_id=first["structure_id"], kind="privy"))

    assert response.status_code == 409


def test_another_volunteers_record_id_is_refused_and_theirs_is_untouched(client, survey, db_session):
    body = _record()
    _send(client, survey, body)
    somebody_else = _volunteer(db_session, survey["org"])

    response = _send(client, survey, {**body, "condition": "unsafe"}, person=somebody_else)

    assert response.status_code == 409
    db_session.expire_all()
    assert db_session.get(InventoryObservation, body["id"]).volunteer_id == survey["volunteer"].id


def test_a_structure_id_from_another_club_is_refused(client, survey, db_session):
    other_org = make_org(db_session, slug="another-club", state=OrgState.claimed)
    stranger = make_profile(db_session)
    db_session.add(
        InventoryStructure(
            id=str(uuid.uuid4()), club_id=other_org.id, kind=StructureKind.bridge, lat=1.0, lon=1.0, created_by=stranger.id
        )
    )
    db_session.commit()
    theirs = db_session.query(InventoryStructure).filter_by(club_id=other_org.id).one()

    assert _send(client, survey, _record(structure_id=theirs.id, kind=None)).status_code == 409


def test_a_visit_to_a_structure_since_merged_lands_on_the_one_it_turned_out_to_be(client, survey, db_session):
    kept, duplicate = _record(), _record()
    _send(client, survey, kept)
    _send(client, survey, duplicate)
    row = db_session.get(InventoryStructure, duplicate["structure_id"])
    row.status = StructureStatus.merged
    row.merged_into_id = kept["structure_id"]
    db_session.commit()

    response = _send(client, survey, _record(structure_id=duplicate["structure_id"], kind=None))

    assert response.status_code == 201
    assert response.json()["structure_id"] == kept["structure_id"]


@pytest.mark.parametrize(
    "size",
    [
        {"size_method": "bucket", "size_bucket": "10_to_25_ft", "size_measured": 18.0, "size_unit": "ft"},
        {"size_method": "bucket", "size_bucket": None},
        {"size_method": "tape", "size_bucket": None, "size_measured": 18.0},
        {"size_method": None, "size_bucket": "10_to_25_ft"},
    ],
    ids=["a bucket with a number", "a bucket with no bucket", "a tape with no unit", "a bucket with no method"],
)
def test_a_size_is_a_bucket_or_a_measurement_and_says_which(client, survey, size):
    """Rule 3: nothing a volunteer estimated is stored as a measurement."""
    assert _send(client, survey, _record(**size)).status_code == 422


def test_a_measured_size_keeps_its_number_and_unit_and_a_skipped_one_keeps_nothing(client, survey, db_session):
    tape = _record(size_method="tape", size_bucket=None, size_measured=18.5, size_unit="ft")
    skipped = _record(size_method=None, size_bucket=None)
    _send(client, survey, tape)
    _send(client, survey, skipped)

    measured = db_session.get(InventoryObservation, tape["id"])
    nothing = db_session.get(InventoryObservation, skipped["id"])
    assert (measured.size_method.value, measured.size_measured, measured.size_unit) == ("tape", 18.5, "ft")
    assert (nothing.size_method, nothing.size_bucket, nothing.size_measured) == (None, None, None)


def test_leaving_it_has_no_how_soon(client, survey):
    assert _send(client, survey, _record(repair="leave", timing="this_season")).status_code == 422
    assert _send(client, survey, _record(repair="leave", timing=None)).status_code == 201


def test_a_capture_time_in_the_future_is_refused(client, survey):
    tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()

    assert _send(client, survey, _record(captured_at=tomorrow)).status_code == 422


@pytest.mark.parametrize("readings", [[], READINGS * 27], ids=["none", "more than six hundred"])
def test_a_record_carries_at_least_one_reading_and_not_a_flood(client, survey, readings):
    assert _send(client, survey, _record(readings=readings)).status_code == 422


def test_a_problem_tag_is_a_key_and_never_a_sentence(client, survey):
    assert _send(client, survey, _record(problems=["The abutment is eroding badly"])).status_code == 422


def test_a_walk_that_is_not_the_volunteers_own_is_refused(client, survey, db_session):
    section = make_section(db_session, survey["org"])
    somebody_else = _volunteer(db_session, survey["org"])
    walk = InventoryPass(club_id=survey["org"].id, volunteer_id=somebody_else.id, trail_id=section.trail_id)
    db_session.add(walk)
    db_session.commit()

    assert _send(client, survey, _record(pass_id=walk.id)).status_code == 422


def test_an_unsafe_record_sets_nothing_special_on_the_row(client, survey, db_session):
    body = _record(condition="unsafe", repair="replace", timing="now")

    _send(client, survey, body)

    row = db_session.get(InventoryObservation, body["id"])
    assert row.condition is Condition.unsafe
    assert row.review_state is ReviewState.submitted
    assert row.report_id is None


def test_a_volunteer_who_has_not_finished_the_field_guide_cannot_upload(client, survey, db_session):
    untrained = _volunteer(db_session, survey["org"], trained=False)

    assert _send(client, survey, _record(), person=untrained).status_code == 403


def test_a_point_the_phone_sends_is_ignored_and_the_readings_decide_where_it_is(client, survey, db_session):
    """Rule 2, from the adversarial review: the saved point is the middle of
    the readings, so a client cannot store a point its readings do not
    support. A location field on the wire is ignored, not trusted."""
    body = _record(lat=10.0, lon=10.0, accuracy_m=0.1)
    _send(client, survey, body)

    row = db_session.get(InventoryObservation, body["id"])
    assert row.lat == pytest.approx(41.4321 + 11e-6)
    assert row.lon == pytest.approx(-73.8765)
    # The median of the readings' own accuracies, 4.0 + 11/10.
    assert row.accuracy_m == pytest.approx(5.1)


def test_one_stray_reading_does_not_drag_the_saved_point(client, survey, db_session):
    """A median, not a mean: a reading thrown a kilometre by a canopy
    reflection moves the saved point not at all."""
    stray = [*READINGS[:-1], {"lat": 41.4421, "lon": -73.8665, "acc": 300.0, "t": 2_000}]
    body = _record(readings=stray)
    _send(client, survey, body)

    row = db_session.get(InventoryObservation, body["id"])
    assert row.lat == pytest.approx(41.4321 + 11e-6)
    assert row.lon == pytest.approx(-73.8765)


def test_a_number_cannot_pose_as_a_bucket(client, survey):
    """Rule 3: only the screen's four buckets are buckets."""
    assert _send(client, survey, _record(size_bucket="18.5 ft")).status_code == 422
    for bucket in ("under_10_ft", "10_to_25_ft", "25_to_50_ft", "over_50_ft"):
        assert _send(client, survey, _record(size_bucket=bucket)).status_code == 201


def _structure_row(db_session, survey, **fields):
    row = InventoryStructure(
        id=str(uuid.uuid4()),
        club_id=survey["org"].id,
        kind=StructureKind.bridge,
        lat=41.43,
        lon=-73.88,
        created_by=survey["volunteer"].id,
        **fields,
    )
    db_session.add(row)
    db_session.flush()
    return row


def test_a_merge_chain_longer_than_eight_is_followed_to_its_end(client, survey, db_session):
    """The old walk stopped after eight hops and called a real chain a loop."""
    chain = [_structure_row(db_session, survey)]
    for _ in range(10):
        chain.append(_structure_row(db_session, survey, status=StructureStatus.merged, merged_into_id=chain[-1].id))
    db_session.commit()

    response = _send(client, survey, _record(structure_id=chain[-1].id, kind=None))

    assert response.status_code == 201
    assert response.json()["structure_id"] == chain[0].id


def test_merges_that_loop_back_on_themselves_are_refused_not_followed(client, survey, db_session):
    first = _structure_row(db_session, survey)
    second = _structure_row(db_session, survey, status=StructureStatus.merged, merged_into_id=first.id)
    first.status, first.merged_into_id = StructureStatus.merged, second.id
    db_session.commit()

    assert _send(client, survey, _record(structure_id=first.id, kind=None)).status_code == 409
