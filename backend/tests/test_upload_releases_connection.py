"""A photo upload gives its database connection back before it waits for the bytes.

#1915 - A photo upload holds a pooled database connection inside an open
transaction while the phone sends the bytes, so fifteen slow uploads make every
other read 500. Each upload route looks its row up, then awaits the request
body. The lookups (and `get_current_user` before them) open a transaction, and
the session kept it open while a phone on one bar sent up to 2 MiB: the
connection sat `idle in transaction` for as long as the phone took. Measured
2026-10-27 against a local Postgres with the app's default pool: fifteen slow
uploads held all fifteen connections, and an anonymous `GET /closures` failed
with a 500 after 30.1 s.

Asserted at the one moment that matters: when a route starts reading the body,
the pool has nothing checked out. And because the row is no longer held across
the wait, the write that follows looks it up again; the last two tests are a
row that changed while the bytes were arriving.
"""

import uuid

import boto3
import pytest
from moto import mock_aws

from app.config import settings
from app.models.field_note import FieldNote
from app.models.profile import Role
from app.models.report import Report
from app.routers import field_notes as field_notes_router
from app.routers import poi_photos as poi_photos_router
from app.routers import reports as reports_router
from tests.factories import make_profile
from tests.tokens import auth_headers

_BUCKET = "ourhike-test"
_JPEG = b"\xff\xd8\xff\xe0" + b"pretend jpeg bytes" * 4
_POI = "atc_shelters:abc123"


@pytest.fixture()
def r2(monkeypatch):
    """A configured, empty bucket with uploads on - test_report_photos.py's double."""
    with mock_aws():
        monkeypatch.setattr(settings, "r2_photo_endpoint_url", "https://s3.amazonaws.com")
        monkeypatch.setattr(settings, "r2_photo_bucket", _BUCKET)
        monkeypatch.setattr(settings, "r2_photo_access_key_id", "test-key")
        monkeypatch.setattr(settings, "r2_photo_secret_access_key", "test-secret")
        monkeypatch.setattr(settings, "r2_photo_write_enabled", True)
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket=_BUCKET)
        yield s3


def _watch_the_body_read(monkeypatch, module, db_engine, while_waiting=None) -> list[int]:
    """Record how many pooled connections are checked out when `module` starts reading a body.

    `while_waiting`, if given, runs at that moment too: it is what a second
    request does while this one's bytes are still arriving.
    """
    seen: list[int] = []
    read = module.read_capped_body

    async def watched(request, limit):
        seen.append(db_engine.pool.checkedout())
        if while_waiting is not None:
            while_waiting()
        return await read(request, limit)

    monkeypatch.setattr(module, "read_capped_body", watched)
    return seen


def _jpeg(user_id: str) -> dict[str, str]:
    return {**auth_headers(user_id), "Content-Type": "image/jpeg"}


def _file_report(client, user_id: str) -> str:
    report_id = str(uuid.uuid4())
    payload = {"id": report_id, "type": "blowdown", "reporter_type": "thru", "mile": 10.0}
    assert client.post("/reports", json=payload, headers=auth_headers(user_id)).status_code == 201
    return report_id


def _file_note(client, user_id: str) -> str:
    note_id = str(uuid.uuid4())
    payload = {"id": note_id, "poi_id": _POI, "observation": "dry", "reporter_type": "thru"}
    assert client.post("/field-notes", json=payload, headers=auth_headers(user_id)).status_code == 201
    return note_id


def test_a_report_photo_holds_no_connection_while_its_bytes_arrive(client, db_engine, r2, monkeypatch):
    hiker = str(uuid.uuid4())
    report_id = _file_report(client, hiker)
    seen = _watch_the_body_read(monkeypatch, reports_router, db_engine)

    response = client.put(f"/reports/{report_id}/photos/1", content=_JPEG, headers=_jpeg(hiker))

    assert response.status_code == 200, response.text
    assert response.json()["photo_count"] == 1
    assert seen == [0], "a connection was checked out while the route waited for the photo"


def test_the_single_photo_route_holds_none_either(client, db_engine, r2, monkeypatch):
    hiker = str(uuid.uuid4())
    report_id = _file_report(client, hiker)
    seen = _watch_the_body_read(monkeypatch, reports_router, db_engine)

    response = client.put(f"/reports/{report_id}/photo", content=_JPEG, headers=_jpeg(hiker))

    assert response.status_code == 200, response.text
    assert seen == [0]


def test_a_field_note_photo_holds_no_connection_while_its_bytes_arrive(client, db_engine, r2, monkeypatch):
    hiker = str(uuid.uuid4())
    note_id = _file_note(client, hiker)
    seen = _watch_the_body_read(monkeypatch, field_notes_router, db_engine)

    response = client.put(f"/field-notes/{note_id}/photo", content=_JPEG, headers=_jpeg(hiker))

    assert response.status_code == 200, response.text
    assert seen == [0]


def test_a_waypoint_photo_holds_no_connection_while_its_bytes_arrive(client, db_engine, db_session, r2, monkeypatch):
    # A share needs a name to credit, so this hiker has one.
    hiker = make_profile(db_session, Role.hiker, display_name="Sawyer").id
    db_session.close()
    assert client.post(f"/waypoints/{_POI}/photos", json={}, headers=auth_headers(hiker)).status_code == 201
    seen = _watch_the_body_read(monkeypatch, poi_photos_router, db_engine)

    response = client.put(f"/waypoints/{_POI}/photos/mine", content=_JPEG, headers=_jpeg(hiker))

    assert response.status_code == 200, response.text
    assert seen == [0]


def test_a_report_deleted_while_its_photo_arrives_is_not_written_to(client, db_engine, db_session, r2, monkeypatch):
    """The account was deleted, or the report with it, between the check and the write."""
    hiker = str(uuid.uuid4())
    report_id = _file_report(client, hiker)

    def delete_it():
        db_session.query(Report).filter(Report.id == report_id).delete()
        db_session.commit()

    _watch_the_body_read(monkeypatch, reports_router, db_engine, while_waiting=delete_it)

    response = client.put(f"/reports/{report_id}/photos/1", content=_JPEG, headers=_jpeg(hiker))

    assert response.status_code == 404
    assert r2.list_objects_v2(Bucket=_BUCKET).get("KeyCount", 0) == 0


def test_a_note_deleted_while_its_photo_arrives_is_not_written_to(client, db_engine, db_session, r2, monkeypatch):
    hiker = str(uuid.uuid4())
    note_id = _file_note(client, hiker)

    def delete_it():
        db_session.query(FieldNote).filter(FieldNote.id == note_id).delete()
        db_session.commit()

    _watch_the_body_read(monkeypatch, field_notes_router, db_engine, while_waiting=delete_it)

    response = client.put(f"/field-notes/{note_id}/photo", content=_JPEG, headers=_jpeg(hiker))

    assert response.status_code == 404
    assert r2.list_objects_v2(Bucket=_BUCKET).get("KeyCount", 0) == 0
