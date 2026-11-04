"""A club's survey settings and a volunteer's enrolment (#1984).

Who may call each endpoint is test_org_permission_matrix.py's job. This file
holds what each one does: the waiver a signature names, the enrolment a
retry answers, and the field guide that cannot be un-finished.
"""

import pytest

from app.core.time import utc_now
from app.models.club import OrgState
from app.models.inventory import InventoryClubSettings, InventoryEnrollment
from tests.factories import make_admin, make_org, make_profile
from tests.tokens import auth_headers

WAIVER = {
    "waiver_text": "I walk at my own risk and will not repair anything I log.",
    "waiver_version": "2026-1",
    "claim_days_ahead": 14,
    "coverage_window_days": 90,
    "coverage_min_records": 3,
    "stale_days": 365,
}


@pytest.fixture
def club(db_session):
    org = make_org(db_session, state=OrgState.claimed)
    admin = make_profile(db_session)
    make_admin(db_session, org, admin)
    db_session.commit()
    return {"org": org, "admin": admin, "url": f"/clubs/{org.slug}/inventory"}


def _write_waiver(client, club, **changes):
    return client.put(f"{club['url']}/settings", json={**WAIVER, **changes}, headers=auth_headers(club["admin"].id))


def _enrol(client, club, person, **changes):
    body = {"typed_name": "Pat R.", "waiver_version": WAIVER["waiver_version"], **changes}
    return client.post(f"{club['url']}/enrollments", json=body, headers=auth_headers(person.id))


def test_a_club_with_no_settings_reads_as_the_defaults_with_enrolment_closed(client, club):
    body = client.get(f"{club['url']}/settings", headers=auth_headers(club["admin"].id)).json()

    assert body["enrolment_open"] is False
    assert body["waiver_text"] is None
    assert (body["claim_days_ahead"], body["coverage_window_days"], body["coverage_min_records"], body["stale_days"]) == (
        14,
        90,
        3,
        365,
    )
    assert body["publish_locations"] is False


def test_writing_a_waiver_opens_enrolment(client, club):
    assert _write_waiver(client, club).status_code == 200

    body = client.get(f"{club['url']}/settings", headers=auth_headers(club["admin"].id)).json()
    assert body["enrolment_open"] is True
    assert body["waiver_version"] == "2026-1"


def test_a_waiver_whose_words_change_needs_a_new_version(client, club):
    """A signature records the version, so the version has to pin the words."""
    _write_waiver(client, club)

    same_version = _write_waiver(client, club, waiver_text="Different words entirely.")
    new_version = _write_waiver(client, club, waiver_text="Different words entirely.", waiver_version="2026-2")

    assert same_version.status_code == 409
    assert new_version.status_code == 200


def test_a_waiver_needs_its_text_and_its_version_together(client, club):
    assert _write_waiver(client, club, waiver_version=None).status_code == 422
    assert _write_waiver(client, club, waiver_text=None).status_code == 422


@pytest.mark.parametrize(
    "field,value",
    [("claim_days_ahead", 0), ("coverage_window_days", 9000), ("coverage_min_records", 0), ("stale_days", 1)],
)
def test_a_threshold_outside_its_bounds_is_refused(client, club, field, value):
    assert _write_waiver(client, club, **{field: value}).status_code == 422


def test_the_settings_body_cannot_switch_publication_on(client, club, db_session):
    """Whether a club can publish locations in v1 is the design doc's open
    question 5, so the wire does not carry the switch yet."""
    _write_waiver(client, club, publish_locations=True)

    assert db_session.get(InventoryClubSettings, club["org"].id).publish_locations is False


def test_nobody_can_join_before_the_club_has_written_its_waiver(client, club, db_session):
    response = _enrol(client, club, make_profile(db_session))

    assert response.status_code == 409


def test_joining_signs_the_current_waiver_and_the_server_stamps_when(client, club, db_session):
    _write_waiver(client, club)
    volunteer = make_profile(db_session)
    before = utc_now()

    response = _enrol(client, club, volunteer, typed_name="  Pat R.  ")

    assert response.status_code == 201
    body = response.json()
    assert body["typed_name"] == "Pat R."
    assert body["waiver_version"] == "2026-1"
    assert body["can_survey"] is False
    row = db_session.query(InventoryEnrollment).filter_by(person_id=volunteer.id).one()
    assert row.waiver_signed_at >= before


def test_a_signature_against_a_waiver_that_has_since_changed_is_refused(client, club, db_session):
    _write_waiver(client, club)
    _write_waiver(client, club, waiver_text="A revised waiver.", waiver_version="2026-2")

    response = _enrol(client, club, make_profile(db_session), waiver_version="2026-1")

    assert response.status_code == 409


def test_joining_twice_answers_the_first_enrolment_with_200(client, club, db_session):
    _write_waiver(client, club)
    volunteer = make_profile(db_session)

    first = _enrol(client, club, volunteer)
    second = _enrol(client, club, volunteer, typed_name="Someone Else")

    assert (first.status_code, second.status_code) == (201, 200)
    assert second.json()["id"] == first.json()["id"]
    assert second.json()["typed_name"] == "Pat R."


def test_a_blank_typed_name_is_not_a_signature(client, club, db_session):
    _write_waiver(client, club)

    assert _enrol(client, club, make_profile(db_session), typed_name="   ").status_code == 422


def test_an_organization_waiting_for_its_domain_to_confirm_it_has_no_open_survey(client, db_session):
    org = make_org(db_session, slug="held-org", state=OrgState.pending)
    admin = make_profile(db_session)
    make_admin(db_session, org, admin)
    db_session.add(InventoryClubSettings(club_id=org.id, waiver_text="Words.", waiver_version="1"))
    db_session.commit()

    response = client.post(
        f"/clubs/{org.slug}/inventory/enrollments",
        json={"typed_name": "Pat R.", "waiver_version": "1"},
        headers=auth_headers(make_profile(db_session).id),
    )

    assert response.status_code == 409


def test_finishing_the_field_guide_is_what_lets_a_volunteer_survey(client, club, db_session):
    _write_waiver(client, club)
    volunteer = make_profile(db_session)
    _enrol(client, club, volunteer)

    response = client.patch(
        f"{club['url']}/enrollments/me", json={"training_completed": True}, headers=auth_headers(volunteer.id)
    )

    assert response.status_code == 200
    assert response.json()["can_survey"] is True
    assert response.json()["training_completed_at"] is not None


def test_finishing_the_field_guide_twice_keeps_the_first_time(client, club, db_session):
    _write_waiver(client, club)
    volunteer = make_profile(db_session)
    _enrol(client, club, volunteer)
    url, headers = f"{club['url']}/enrollments/me", auth_headers(volunteer.id)

    first = client.patch(url, json={"training_completed": True}, headers=headers).json()
    second = client.patch(url, json={"training_completed": True}, headers=headers).json()

    assert second["training_completed_at"] == first["training_completed_at"]


def test_the_field_guide_cannot_be_un_finished(client, club, db_session):
    _write_waiver(client, club)
    volunteer = make_profile(db_session)
    _enrol(client, club, volunteer)

    response = client.patch(
        f"{club['url']}/enrollments/me", json={"training_completed": False}, headers=auth_headers(volunteer.id)
    )

    assert response.status_code == 422


def test_reading_your_own_enrolment_before_joining_answers_null(client, club, db_session):
    response = client.get(f"{club['url']}/enrollments/me", headers=auth_headers(make_profile(db_session).id))

    assert response.status_code == 200
    assert response.json() is None
