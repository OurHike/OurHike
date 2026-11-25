"""Priority areas and claims: how a section is scored, and what a claim shows.

#1988 — Priority areas are sections scored by the records in them, and a
claim is a day a volunteer means to walk one.

Who may call either endpoint is test_org_permission_matrix.py's job. This
file holds what they answer: the three `need` values on three sections of one
trail (the issue's "done when"), which records count, the club's own
thresholds, and that a claim carries a first name and nothing more.
"""

import uuid
from datetime import timedelta

import pytest

from app.core.time import utc_now
from app.models.club import OrgState
from app.models.inventory import (
    Condition,
    InventoryClaim,
    InventoryClubSettings,
    InventoryEnrollment,
    InventoryObservation,
    InventoryStructure,
    Repair,
    ReviewState,
    StructureKind,
)
from app.models.org_registry import OrgSection
from app.routers import inventory_areas
from tests.factories import make_org, make_profile, make_section
from tests.tokens import auth_headers


def _volunteer(db_session, org, typed_name="Pat Rivera"):
    person = make_profile(db_session)
    db_session.add(
        InventoryEnrollment(
            club_id=org.id,
            person_id=person.id,
            waiver_version="2026-1",
            typed_name=typed_name,
            training_completed_at=utc_now(),
        )
    )
    db_session.commit()
    return person


@pytest.fixture
def trail(db_session):
    """One club, one trail, and three sections on it in trail order.

    The first is made by `make_section`, which builds the park and trail; the
    other two sit on the same trail."""
    org = make_org(db_session, state=OrgState.claimed)
    db_session.add(InventoryClubSettings(club_id=org.id, waiver_text="Words.", waiver_version="2026-1"))
    first = make_section(db_session, org, name="NY 301 to Dennytown Rd", start_mile=1.0, end_mile=4.4, miles=3.4)
    second = OrgSection(trail_id=first.trail_id, name="Dennytown Rd to Canopus Hill Rd", start_mile=4.4, end_mile=8.6, miles=4.2)
    third = OrgSection(
        trail_id=first.trail_id, name="Canopus Hill Rd to Bear Mtn Bridge", start_mile=8.6, end_mile=12.5, miles=3.9
    )
    db_session.add_all([second, third])
    db_session.commit()
    return {
        "org": org,
        "trail_id": first.trail_id,
        "sections": [first, second, third],
        "volunteer": _volunteer(db_session, org),
    }


def _record(db_session, world, section, *, days_ago, state=ReviewState.submitted):
    """One visit to a new structure in `section`, `days_ago` days back."""
    structure = InventoryStructure(
        club_id=world["org"].id,
        section_id=section.id,
        kind=StructureKind.bridge,
        lat=41.43,
        lon=-73.87,
        created_by=world["volunteer"].id,
    )
    db_session.add(structure)
    db_session.flush()
    db_session.add(
        InventoryObservation(
            id=str(uuid.uuid4()),
            structure_id=structure.id,
            club_id=world["org"].id,
            volunteer_id=world["volunteer"].id,
            captured_at=utc_now() - timedelta(days=days_ago),
            lat=41.43,
            lon=-73.87,
            accuracy_m=4.0,
            readings_count=1,
            readings_seconds=1,
            readings=[{"lat": 41.43, "lon": -73.87, "acc": 4.0, "t": 0}],
            condition=Condition.good,
            repair=Repair.leave,
            review_state=state,
        )
    )
    db_session.commit()


def _areas(client, world, person=None):
    response = client.get(
        f"/clubs/{world['org'].slug}/inventory/areas?trail={world['trail_id']}",
        headers=auth_headers((person or world["volunteer"]).id),
    )
    assert response.status_code == 200, response.text
    return response.json()


def _claim(client, world, section, walk_on, person=None):
    return client.post(
        f"/clubs/{world['org'].slug}/inventory/claims",
        json={"section_id": section.id, "walk_on": walk_on.isoformat()},
        headers=auth_headers((person or world["volunteer"]).id),
    )


def test_the_three_sample_sections_come_back_as_the_three_needs(client, db_session, trail):
    """The issue's "done when": nothing in a year, under 3 in 90 days, covered."""
    first, second, third = trail["sections"]
    _record(db_session, trail, first, days_ago=400)
    _record(db_session, trail, second, days_ago=10)
    _record(db_session, trail, second, days_ago=100)
    for days_ago in (1, 20, 80):
        _record(db_session, trail, third, days_ago=days_ago)

    areas = _areas(client, trail)

    assert [(area["name"], area["records_90d"], area["need"]) for area in areas] == [
        ("NY 301 to Dennytown Rd", 0, "none_in_a_year"),
        ("Dennytown Rd to Canopus Hill Rd", 1, "under_3_in_90"),
        ("Canopus Hill Rd to Bear Mtn Bridge", 3, "covered"),
    ]
    assert areas[0]["last_record_at"] is not None


def test_a_section_with_no_record_at_all_needs_a_walk_most(client, trail):
    areas = _areas(client, trail)

    assert {area["need"] for area in areas} == {"none_in_a_year"}
    assert {area["last_record_at"] for area in areas} == {None}


@pytest.mark.parametrize(
    ("state", "counts"),
    [
        (ReviewState.submitted, True),
        (ReviewState.accepted, True),
        (ReviewState.returned, True),
        (ReviewState.merged, True),
        (ReviewState.not_ours, False),
    ],
)
def test_every_record_counts_but_one_the_chair_marked_not_ours(client, db_session, trail, state, counts):
    """The design doc's open question 11, answered provisionally by
    `inventory_areas.COUNTED_REVIEW_STATES`."""
    section = trail["sections"][0]
    _record(db_session, trail, section, days_ago=5, state=state)

    area = _areas(client, trail)[0]

    assert area["records_90d"] == (1 if counts else 0)
    assert (area["last_record_at"] is not None) is counts


def test_the_clubs_own_thresholds_decide_the_need(client, db_session, trail):
    db_session.get(InventoryClubSettings, trail["org"].id).coverage_min_records = 1
    db_session.commit()
    _record(db_session, trail, trail["sections"][0], days_ago=5)

    assert _areas(client, trail)[0]["need"] == "covered"


def test_another_clubs_trail_is_not_found(client, db_session, trail):
    other = make_org(db_session, slug="another-club", state=OrgState.claimed)
    elsewhere = make_section(db_session, other)

    response = client.get(
        f"/clubs/{trail['org'].slug}/inventory/areas?trail={elsewhere.trail_id}",
        headers=auth_headers(trail["volunteer"].id),
    )

    assert response.status_code == 404


def test_a_claim_shows_its_volunteers_first_name_and_only_its_owner_gets_its_id(client, db_session, trail):
    section = trail["sections"][1]
    other = _volunteer(db_session, trail["org"], typed_name="Sam O'Neill")
    today = utc_now().date()
    made = _claim(client, trail, section, today + timedelta(days=3))
    assert made.status_code == 201
    _claim(client, trail, section, today + timedelta(days=1), person=other)

    claims = _areas(client, trail)[1]["claims"]

    assert claims == [
        {"walk_on": (today + timedelta(days=1)).isoformat(), "first_name": "Sam", "mine": False, "id": None},
        {"walk_on": (today + timedelta(days=3)).isoformat(), "first_name": "Pat", "mine": True, "id": made.json()["id"]},
    ]


def test_the_same_claim_twice_answers_the_first(client, trail):
    section = trail["sections"][0]
    day = utc_now().date() + timedelta(days=2)

    first = _claim(client, trail, section, day)
    again = _claim(client, trail, section, day)

    assert (first.status_code, again.status_code) == (201, 200)
    assert again.json()["id"] == first.json()["id"]


def test_a_claim_can_be_up_to_the_clubs_days_ahead_and_no_further(client, trail):
    section = trail["sections"][0]
    today = utc_now().date()

    assert _claim(client, trail, section, today + timedelta(days=14)).status_code == 201
    too_far = _claim(client, trail, section, today + timedelta(days=15))
    assert too_far.status_code == 422
    assert "at most 14 days ahead" in too_far.json()["detail"]


def test_a_claim_for_a_day_already_past_is_refused_but_a_volunteers_yesterday_in_utc_is_not(client, trail):
    """`CLAIM_DAY_SLACK`: the UTC date can be a day ahead of the volunteer's own."""
    section = trail["sections"][0]
    today = utc_now().date()

    assert _claim(client, trail, section, today - timedelta(days=inventory_areas.CLAIM_DAY_SLACK)).status_code == 201
    past = _claim(client, trail, section, today - timedelta(days=inventory_areas.CLAIM_DAY_SLACK + 1))
    assert past.status_code == 422


def test_a_claim_on_another_clubs_section_is_not_found(client, db_session, trail):
    other = make_org(db_session, slug="another-club", state=OrgState.claimed)
    elsewhere = make_section(db_session, other)

    assert _claim(client, trail, elsewhere, utc_now().date()).status_code == 404


def test_a_released_claim_and_a_lapsed_one_leave_the_map_but_keep_their_rows(client, db_session, trail):
    section = trail["sections"][0]
    today = utc_now().date()
    made = _claim(client, trail, section, today + timedelta(days=2)).json()
    lapsed = InventoryClaim(
        club_id=trail["org"].id,
        volunteer_id=trail["volunteer"].id,
        section_id=section.id,
        walk_on=today - timedelta(days=inventory_areas.CLAIM_DAY_SLACK + 1),
    )
    db_session.add(lapsed)
    db_session.commit()

    released = client.delete(
        f"/clubs/{trail['org'].slug}/inventory/claims/{made['id']}", headers=auth_headers(trail["volunteer"].id)
    )

    assert released.status_code == 204
    assert _areas(client, trail)[0]["claims"] == []
    db_session.expire_all()
    assert db_session.get(InventoryClaim, made["id"]).released_at is not None
    assert db_session.get(InventoryClaim, lapsed.id) is not None


def test_releasing_twice_is_not_an_error(client, trail):
    made = _claim(client, trail, trail["sections"][0], utc_now().date()).json()
    url = f"/clubs/{trail['org'].slug}/inventory/claims/{made['id']}"

    first = client.delete(url, headers=auth_headers(trail["volunteer"].id))
    second = client.delete(url, headers=auth_headers(trail["volunteer"].id))

    assert (first.status_code, second.status_code) == (204, 204)


def test_nobody_can_release_somebody_elses_claim(client, db_session, trail):
    """Answered with the same 404 as a claim that does not exist."""
    made = _claim(client, trail, trail["sections"][0], utc_now().date()).json()
    other = _volunteer(db_session, trail["org"], typed_name="Sam")

    response = client.delete(f"/clubs/{trail['org'].slug}/inventory/claims/{made['id']}", headers=auth_headers(other.id))

    assert response.status_code == 404
    db_session.expire_all()
    assert db_session.get(InventoryClaim, made["id"]).released_at is None


def test_a_blank_typed_name_gives_no_first_name(client, db_session, trail):
    enrollment = db_session.query(InventoryEnrollment).filter_by(person_id=trail["volunteer"].id).one()
    enrollment.typed_name = "   "
    db_session.commit()
    _claim(client, trail, trail["sections"][0], utc_now().date())

    assert _areas(client, trail)[0]["claims"][0]["first_name"] is None
