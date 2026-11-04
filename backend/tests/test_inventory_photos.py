"""A survey record's photos: the report pipeline, keyed by record (#1986).

The checks are the report upload's, and so is the order they run in; what
this file holds is what is the survey's own. The key is the observation's,
so a later visit's photo never replaces an earlier one's. The set is dense.
A link reaches the person who took the photo and the people who review the
record, and refuses everybody else with the same 404.

S3 is doubled in-process with moto, test_poi_photos.py's convention.
"""

import uuid

import boto3
import pytest
from moto import mock_aws

from app.config import settings
from app.core.time import utc_now
from app.models.club import OrgState
from app.models.inventory import InventoryEnrollment, InventoryObservation, InventoryStructure
from tests.factories import make_admin, make_assignment, make_org, make_profile, make_role, make_section
from tests.tokens import auth_headers

_BUCKET = "ourhike-test"
_JPEG = b"\xff\xd8\xff\xe0" + b"pretend jpeg bytes" * 4


@pytest.fixture()
def r2(monkeypatch):
    """A configured, empty bucket with uploads on - test_poi_photos.py's."""
    with mock_aws():
        monkeypatch.setattr(settings, "r2_photo_endpoint_url", "https://s3.amazonaws.com")
        monkeypatch.setattr(settings, "r2_photo_bucket", _BUCKET)
        monkeypatch.setattr(settings, "r2_photo_access_key_id", "test-key")
        monkeypatch.setattr(settings, "r2_photo_secret_access_key", "test-secret")
        monkeypatch.setattr(settings, "r2_photo_write_enabled", True)
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket=_BUCKET)
        yield s3


def _stored(r2) -> list[str]:
    return sorted(entry["Key"] for entry in r2.list_objects_v2(Bucket=_BUCKET).get("Contents", []))


def _volunteer(db_session, org):
    person = make_profile(db_session)
    db_session.add(
        InventoryEnrollment(
            club_id=org.id, person_id=person.id, waiver_version="1", typed_name="Pat R.", training_completed_at=utc_now()
        )
    )
    db_session.commit()
    return person


@pytest.fixture
def survey(db_session):
    """A club, a chair over a crew, a volunteer, and an admin."""
    org = make_org(db_session, state=OrgState.claimed)
    chair_role = make_role(db_session, org, name="Trails chair")
    crew_role = make_role(db_session, org, name="Maintainer", reports_to_role_id=chair_role.id)
    section = make_section(db_session, org, name="Crew section")
    elsewhere = make_section(db_session, org, name="Nobody's section")
    supervisor, crew, admin = make_profile(db_session), make_profile(db_session), make_profile(db_session)
    make_assignment(db_session, org, supervisor, role=chair_role)
    make_assignment(db_session, org, crew, role=crew_role, section=section)
    make_admin(db_session, org, admin)
    db_session.commit()
    return {
        "org": org,
        "volunteer": _volunteer(db_session, org),
        "admin": admin,
        "supervisor": supervisor,
        "section": section,
        "elsewhere": elsewhere,
        "base": f"/clubs/{org.slug}/inventory/observations",
    }


def _record(client, survey, person=None, structure_id=None) -> str:
    person = person or survey["volunteer"]
    body = {
        "id": str(uuid.uuid4()),
        "structure_id": structure_id or str(uuid.uuid4()),
        "kind": "bridge",
        "captured_at": "2026-11-02T10:14:00Z",
        "lat": 41.43,
        "lon": -73.88,
        "accuracy_m": 4.3,
        "readings": [{"lat": 41.43, "lon": -73.88, "acc": 4.3, "t": 0}],
        "readings_seconds": 1,
        "condition": "poor",
        "repair": "major",
    }
    assert client.post(survey["base"], json=body, headers=auth_headers(person.id)).status_code == 201
    return body["id"]


def _put(client, survey, observation_id, index, *, person=None, body=_JPEG, content_type="image/jpeg"):
    headers = {**auth_headers((person or survey["volunteer"]).id), "Content-Type": content_type}
    return client.put(f"{survey['base']}/{observation_id}/photos/{index}", content=body, headers=headers)


def _link(client, survey, observation_id, index, person):
    return client.get(f"{survey['base']}/{observation_id}/photos/{index}/link", headers=auth_headers(person.id))


def test_a_photo_lands_under_its_record_and_the_count_is_all_the_row_learns(client, survey, r2, db_session):
    record = _record(client, survey)

    response = _put(client, survey, record, 1)

    assert response.status_code == 200, response.text
    assert response.json() == {"observation_id": record, "photo_count": 1}
    assert _stored(r2) == [f"inventory/{record}/1.jpg"]


def test_a_later_visits_photo_never_replaces_an_earlier_ones(client, survey, r2):
    """Keyed by the record, not the structure: last year's scoured abutment
    stays beside this week's sound bridge."""
    structure_id = str(uuid.uuid4())
    first = _record(client, survey, structure_id=structure_id)
    second = _record(client, survey, structure_id=structure_id)

    _put(client, survey, first, 1)
    _put(client, survey, second, 1)

    assert _stored(r2) == sorted([f"inventory/{first}/1.jpg", f"inventory/{second}/1.jpg"])


def test_a_retry_of_photo_one_does_not_claim_a_second(client, survey, r2):
    record = _record(client, survey)

    _put(client, survey, record, 1)
    again = _put(client, survey, record, 1)

    assert again.json()["photo_count"] == 1


def test_the_set_is_dense_and_capped(client, survey, r2):
    record = _record(client, survey)
    _put(client, survey, record, 1)

    assert _put(client, survey, record, 3).status_code == 409
    assert _put(client, survey, record, 0).status_code == 409
    assert _put(client, survey, record, 7).status_code == 409
    assert _put(client, survey, record, 2).json()["photo_count"] == 2


def test_a_photo_is_a_jpeg_by_its_header_and_by_its_bytes(client, survey, r2):
    record = _record(client, survey)

    assert _put(client, survey, record, 1, content_type="image/png").status_code == 415
    assert _put(client, survey, record, 1, body=b"\x89PNG not a jpeg").status_code == 415
    assert _stored(r2) == []


def test_somebody_elses_record_is_not_found_and_nothing_is_stored(client, survey, r2, db_session):
    record = _record(client, survey)
    somebody_else = _volunteer(db_session, survey["org"])

    assert _put(client, survey, record, 1, person=somebody_else).status_code == 404
    assert _stored(r2) == []


def test_a_server_with_no_bucket_says_so(client, survey):
    record = _record(client, survey)

    assert _put(client, survey, record, 1).status_code == 503


def test_the_volunteer_and_the_clubs_admin_get_a_link(client, survey, r2):
    record = _record(client, survey)
    _put(client, survey, record, 1)

    for person in (survey["volunteer"], survey["admin"]):
        response = _link(client, survey, record, 1, person)
        assert response.status_code == 200, response.text
        assert f"inventory/{record}/1.jpg" in response.json()["url"]
        assert response.headers["Cache-Control"] == "private, no-store, max-age=0"


def test_a_supervisor_sees_a_records_photo_only_in_a_section_under_their_role(client, survey, r2, db_session):
    under, outside = _record(client, survey), _record(client, survey)
    for record, section in ((under, survey["section"]), (outside, survey["elsewhere"])):
        _put(client, survey, record, 1)
        observation = db_session.get(InventoryObservation, record)
        db_session.get(InventoryStructure, observation.structure_id).section_id = section.id
    db_session.commit()

    assert _link(client, survey, under, 1, survey["supervisor"]).status_code == 200
    assert _link(client, survey, outside, 1, survey["supervisor"]).status_code == 404


def test_everybody_else_and_every_missing_photo_get_the_same_404(client, survey, r2, db_session):
    record = _record(client, survey)
    _put(client, survey, record, 1)
    somebody_else = _volunteer(db_session, survey["org"])

    assert _link(client, survey, record, 1, somebody_else).status_code == 404
    assert _link(client, survey, record, 2, survey["volunteer"]).status_code == 404
    assert _link(client, survey, str(uuid.uuid4()), 1, survey["volunteer"]).status_code == 404
