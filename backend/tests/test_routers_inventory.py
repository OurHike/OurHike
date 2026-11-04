"""A club's survey settings and a volunteer's enrolment.

#1984 — A club's enrolment, settings and waiver have endpoints, and an
enrolled volunteer is a person `org_access` did not know about.

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


def _held_org(db_session):
    org = make_org(db_session, slug="held-org", state=OrgState.pending)
    admin = make_profile(db_session)
    make_admin(db_session, org, admin)
    db_session.add(InventoryClubSettings(club_id=org.id, waiver_text="Words.", waiver_version="1"))
    db_session.commit()
    return org, admin


def test_a_held_registration_is_the_same_404_as_no_organization_to_a_stranger(client, db_session):
    """A held (`pending`) registration has published nothing, so a stranger
    who tries to join its survey learns nothing either: the response is the
    one a slug nobody registered gets. #2018 — Harden the release review's
    security findings: one domain normaliser, held registrations off public
    reads, strict Stripe ids and choices, hash-pinned rollup installs, made
    `org_access` answer it that way."""
    org, _ = _held_org(db_session)
    stranger = auth_headers(make_profile(db_session).id)
    body = {"typed_name": "Pat R.", "waiver_version": "1"}

    held = client.post(f"/clubs/{org.slug}/inventory/enrollments", json=body, headers=stranger)
    unknown = client.post("/clubs/nobody-registered-this/inventory/enrollments", json=body, headers=stranger)

    assert held.status_code == unknown.status_code == 404
    assert held.json() == unknown.json()


def test_a_held_registrations_own_admin_is_told_its_survey_is_not_open_yet(client, db_session):
    """The one person who can see a held registration exists gets the reason,
    not a 404 about their own organization."""
    org, admin = _held_org(db_session)

    response = client.post(
        f"/clubs/{org.slug}/inventory/enrollments",
        json={"typed_name": "Pat R.", "waiver_version": "1"},
        headers=auth_headers(admin.id),
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


def _signed_by_somebody(client, club, db_session):
    _enrol(client, club, make_profile(db_session))


def test_clearing_the_waiver_does_not_free_a_signed_version_for_new_words(client, club, db_session):
    """The way round the same-version rule that the adversarial review found:
    clear the waiver, then save different words under the version people
    already signed. The cleared row keeps nothing to compare against, so a
    signed version cannot come back with any words at all."""
    _write_waiver(client, club)
    _signed_by_somebody(client, club, db_session)

    assert _write_waiver(client, club, waiver_text=None, waiver_version=None).status_code == 200
    reused = _write_waiver(client, club, waiver_text="Different words entirely.")

    assert reused.status_code == 409
    assert db_session.get(InventoryClubSettings, club["org"].id).waiver_version is None


def test_a_signed_version_cannot_come_back_after_it_was_replaced(client, club, db_session):
    _write_waiver(client, club)
    _signed_by_somebody(client, club, db_session)
    _write_waiver(client, club, waiver_text="A revised waiver.", waiver_version="2026-2")

    assert _write_waiver(client, club).status_code == 409


def test_the_current_signed_version_can_be_saved_again_with_its_own_words(client, club, db_session):
    """Changing a threshold re-sends the waiver as it stands; that is not a
    new waiver and must not be refused."""
    _write_waiver(client, club)
    _signed_by_somebody(client, club, db_session)

    assert _write_waiver(client, club, stale_days=400).status_code == 200


def test_a_version_nobody_signed_can_be_reused_after_clearing(client, club, db_session):
    _write_waiver(client, club)
    _write_waiver(client, club, waiver_text=None, waiver_version=None)

    assert _write_waiver(client, club, waiver_text="Better words, never signed.").status_code == 200


def test_two_first_saves_at_once_answer_the_second_instead_of_failing(client, club, db_session, monkeypatch):
    """Both find no row and both insert; the loser is run again against the
    row the winner made. Simulated by making the router miss an existing row
    once, which is exactly what the loser saw."""
    from app.routers import inventory as inventory_router

    db_session.add(InventoryClubSettings(club_id=club["org"].id, waiver_text="Words.", waiver_version="1"))
    db_session.commit()
    real = inventory_router._settings_row
    misses = [True]

    def first_read_misses(db, club_id):
        if misses:
            misses.pop()
            return None
        return real(db, club_id)

    monkeypatch.setattr(inventory_router, "_settings_row", first_read_misses)

    response = _write_waiver(client, club, waiver_text="Words.", waiver_version="1", stale_days=500)

    assert response.status_code == 200
    assert response.json()["stale_days"] == 500
