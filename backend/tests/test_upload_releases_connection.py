"""A photo upload holds no database connection while it waits: for the phone's bytes, or for R2.

#1915 - A photo upload holds a pooled database connection inside an open
transaction while the phone sends the bytes, so fifteen slow uploads make every
other read 500. Each upload route looked its row up, then awaited the request
body. The lookups (and `get_current_user` before them) open a transaction, and
the session kept it open while a phone on one bar sent up to 2 MiB: the
connection sat `idle in transaction` for as long as the phone took. Measured
2026-10-27 against a local Postgres with the app's default pool: fifteen slow
uploads held all fifteen connections, and an anonymous `GET /closures` failed
with a 500 after 30.1 s.

The review of #1925 - Hand the database connection back before a photo upload
waits for its bytes - found the same outage one step further on: the R2 put
ran inside the transaction the re-check had opened, so a slow R2 held the
connection where a slow phone had. Each route now checks, hands the connection
back, reads the body, puts the photo, and only then records it, in one short
transaction on a locked row. What is asserted here:

  - **No connection is checked out while the bytes arrive, or while R2 stores
    them**, on every route, at the moment each wait begins.
  - **The record step checks again, on the row as it is after the put.** A
    slow put cannot take the photo count back, and a waypoint share withdrawn
    mid-upload - a hard delete the API really can make while an upload is in
    flight - is a 404 that leaves nothing in the bucket, not a 500 that leaves
    the withdrawn photograph there.
  - **A refused upload deletes the object it put**, because nothing else
    would: no sweep exists (app/core/photos.py).
"""

import uuid

import boto3
import pytest
from botocore.exceptions import EndpointConnectionError
from moto import mock_aws

from app.config import settings
from app.core import photos as photos_core
from app.core.photos import poi_photo_key
from app.models.field_note import FieldNote
from app.models.poi_photo import PoiPhoto
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
_R2_ENDPOINT = "https://0123456789abcdef0123456789abcdef.r2.cloudflarestorage.com/ourhike-report-photos"


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


def _stored(r2) -> list[str]:
    """Every key in the bucket."""
    return [entry["Key"] for entry in r2.list_objects_v2(Bucket=_BUCKET).get("Contents", [])]


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


class _WatchedR2:
    """The moto client every upload talks to, with a hook in front of `put_object`.

    `deletes_fail` makes every delete fail the way an unreachable R2 does,
    with the endpoint in botocore's message, as test_report_photos.py's
    `_UnreachableR2` does for puts.
    """

    def __init__(self, real, before_put, deletes_fail):
        self._real = real
        self._before_put = before_put
        self._deletes_fail = deletes_fail

    def put_object(self, **kwargs):
        self._before_put()
        return self._real.put_object(**kwargs)

    def delete_object(self, **kwargs):
        if self._deletes_fail:
            raise EndpointConnectionError(endpoint_url=_R2_ENDPOINT)
        return self._real.delete_object(**kwargs)

    def __getattr__(self, name):
        return getattr(self._real, name)


def _watch_the_put(monkeypatch, db_engine, during_the_put=None, deletes_fail=False) -> list[int]:
    """Record how many pooled connections are checked out as each R2 put begins.

    `during_the_put`, if given, runs inside the first put, before its bytes
    land: what another request does while R2 is still storing this one's
    photo. Only the first, so the requests it makes can upload photos of
    their own.
    """
    seen: list[int] = []
    pending = [during_the_put] if during_the_put is not None else []
    real_client = photos_core._client

    def before_put():
        seen.append(db_engine.pool.checkedout())
        if pending:
            pending.pop()()

    monkeypatch.setattr(photos_core, "_client", lambda: _WatchedR2(real_client(), before_put, deletes_fail))
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


def _share(client, db_session) -> str:
    """A hiker with a share at `_POI` whose bytes have not been sent. They have
    a trail name, because a share needs one to credit."""
    hiker = make_profile(db_session, Role.hiker, display_name="Sawyer").id
    # Reading `.id` reloaded the committed row, which checked a connection out;
    # closing hands it back, so the pool counts below see only the request.
    db_session.close()
    assert client.post(f"/waypoints/{_POI}/photos", json={}, headers=auth_headers(hiker)).status_code == 201
    return hiker


def _withdraw(client, hiker: str):
    """The hiker's own withdrawal, through the route their phone uses."""

    def withdraw():
        assert client.delete(f"/waypoints/{_POI}/photos/mine", headers=auth_headers(hiker)).status_code == 204

    return withdraw


# --- No connection while the bytes arrive ------------------------------------


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
    hiker = _share(client, db_session)
    seen = _watch_the_body_read(monkeypatch, poi_photos_router, db_engine)

    response = client.put(f"/waypoints/{_POI}/photos/mine", content=_JPEG, headers=_jpeg(hiker))

    assert response.status_code == 200, response.text
    assert seen == [0]


# --- No connection while R2 stores them ---------------------------------------
#
# The review found the put inside the re-check's transaction on all three
# routes: `pool.checkedout()` 1 and the connection `idle in transaction` for
# as long as R2 took.


def test_a_report_photo_holds_no_connection_while_r2_stores_it(client, db_engine, r2, monkeypatch):
    hiker = str(uuid.uuid4())
    report_id = _file_report(client, hiker)
    seen = _watch_the_put(monkeypatch, db_engine)

    response = client.put(f"/reports/{report_id}/photos/1", content=_JPEG, headers=_jpeg(hiker))

    assert response.status_code == 200, response.text
    assert seen == [0], "a connection was checked out while R2 stored the photo"


def test_a_field_note_photo_holds_no_connection_while_r2_stores_it(client, db_engine, r2, monkeypatch):
    hiker = str(uuid.uuid4())
    note_id = _file_note(client, hiker)
    seen = _watch_the_put(monkeypatch, db_engine)

    response = client.put(f"/field-notes/{note_id}/photo", content=_JPEG, headers=_jpeg(hiker))

    assert response.status_code == 200, response.text
    assert seen == [0]


def test_a_waypoint_photo_holds_no_connection_while_r2_stores_it(client, db_engine, db_session, r2, monkeypatch):
    hiker = _share(client, db_session)
    seen = _watch_the_put(monkeypatch, db_engine)

    response = client.put(f"/waypoints/{_POI}/photos/mine", content=_JPEG, headers=_jpeg(hiker))

    assert response.status_code == 200, response.text
    assert seen == [0]


# --- The record step, on the row as it is after the put ----------------------


def test_a_slow_put_does_not_take_the_photo_count_back(client, db_engine, r2, monkeypatch):
    """Photo 2's first put is slow, and its retry and then photo 3 both land
    while R2 still has it. Recording from the copy of the row it read before
    the put, the slow one wrote `max(1, 2)` over the 3 already there, and
    photo 3 - in the bucket - stopped being shown. The record step now reads
    the count under a row lock, after the put."""
    hiker = str(uuid.uuid4())
    report_id = _file_report(client, hiker)
    assert client.put(f"/reports/{report_id}/photos/1", content=_JPEG, headers=_jpeg(hiker)).status_code == 200

    def the_retry_and_photo_3_land():
        for index in (2, 3):
            response = client.put(f"/reports/{report_id}/photos/{index}", content=_JPEG, headers=_jpeg(hiker))
            assert response.status_code == 200, response.text

    _watch_the_put(monkeypatch, db_engine, during_the_put=the_retry_and_photo_3_land)

    response = client.put(f"/reports/{report_id}/photos/2", content=_JPEG, headers=_jpeg(hiker))

    assert response.status_code == 200, response.text
    assert response.json()["photo_count"] == 3


def test_a_waypoint_photo_withdrawn_while_its_bytes_arrive_is_not_stored(client, db_engine, db_session, r2, monkeypatch):
    """The row change the API really can make mid-upload: `DELETE .../photos/mine`
    is a hard delete. On `main` this was a 500 - the write was an UPDATE of
    the deleted row - and the photograph its hiker had just withdrawn stayed
    in the bucket."""
    hiker = _share(client, db_session)
    _watch_the_body_read(monkeypatch, poi_photos_router, db_engine, while_waiting=_withdraw(client, hiker))

    response = client.put(f"/waypoints/{_POI}/photos/mine", content=_JPEG, headers=_jpeg(hiker))

    assert response.status_code == 404
    assert _stored(r2) == []
    assert db_session.query(PoiPhoto).count() == 0


def test_a_waypoint_photo_withdrawn_while_r2_stores_it_leaves_nothing_behind(client, db_engine, db_session, r2, monkeypatch):
    """The same withdrawal, landing during the put. The review had it answer
    500, with no row and the withdrawn photograph still in the bucket: the
    copy the withdrawal promised not to keep."""
    hiker = _share(client, db_session)
    _watch_the_put(monkeypatch, db_engine, during_the_put=_withdraw(client, hiker))

    response = client.put(f"/waypoints/{_POI}/photos/mine", content=_JPEG, headers=_jpeg(hiker))

    assert response.status_code == 404
    assert _stored(r2) == []
    assert db_session.query(PoiPhoto).count() == 0


def test_a_cleanup_delete_that_fails_is_logged_and_the_refusal_stands(client, db_engine, db_session, r2, monkeypatch):
    """When R2 will not delete the refused object, the hiker still hears the
    refusal - a 503 would say the photo did not land, when the trouble is
    that it did - and the orphan's key reaches the log, which is the only way
    anybody finds it again. That line carries the key and nothing of the
    endpoint botocore names in its error (app/core/logs.py)."""
    # The module's own logger rather than caplog, for the reason
    # test_report_photos.py gives: Alembic's `fileConfig` disables it.
    errors: list[str] = []
    monkeypatch.setattr(photos_core.logger, "error", lambda message, *args: errors.append(message % args))
    hiker = _share(client, db_session)
    _watch_the_put(monkeypatch, db_engine, during_the_put=_withdraw(client, hiker), deletes_fail=True)

    response = client.put(f"/waypoints/{_POI}/photos/mine", content=_JPEG, headers=_jpeg(hiker))

    assert response.status_code == 404
    key = poi_photo_key(_POI, hiker)
    assert _stored(r2) == [key]
    assert [line for line in errors if key in line], errors
    assert not [line for line in errors if "cloudflarestorage" in line], errors


# --- Rows no route deletes ----------------------------------------------------
#
# Nothing in this backend deletes a report or a field note: no route, no
# cascade, no job (account deletion keeps both - app/core/account_deletion.py).
# So the two tests below delete one by SQL, and are kept for what they hold:
# a row gone by any means is a 404 with nothing left in the bucket, not the
# StaleDataError and stored object it used to be.


def test_a_report_deleted_while_its_photo_arrives_is_not_written_to(client, db_engine, db_session, r2, monkeypatch):
    """A state no route produces - see above - made by SQL. It once claimed
    to cover an account deleted mid-upload as well; account deletion keeps
    the report, so that is not this state."""
    hiker = str(uuid.uuid4())
    report_id = _file_report(client, hiker)

    def delete_it():
        db_session.query(Report).filter(Report.id == report_id).delete()
        db_session.commit()

    _watch_the_body_read(monkeypatch, reports_router, db_engine, while_waiting=delete_it)

    response = client.put(f"/reports/{report_id}/photos/1", content=_JPEG, headers=_jpeg(hiker))

    assert response.status_code == 404
    assert _stored(r2) == []


def test_a_note_deleted_while_its_photo_arrives_is_not_written_to(client, db_engine, db_session, r2, monkeypatch):
    """A state no route produces either, made by SQL."""
    hiker = str(uuid.uuid4())
    note_id = _file_note(client, hiker)

    def delete_it():
        db_session.query(FieldNote).filter(FieldNote.id == note_id).delete()
        db_session.commit()

    _watch_the_body_read(monkeypatch, field_notes_router, db_engine, while_waiting=delete_it)

    response = client.put(f"/field-notes/{note_id}/photo", content=_JPEG, headers=_jpeg(hiker))

    assert response.status_code == 404
    assert _stored(r2) == []
