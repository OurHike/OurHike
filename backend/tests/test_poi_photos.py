"""Community waypoint photos - share, upload, list, withdraw (#576).

S3 is doubled in-process with moto, the same convention as
test_report_photos.py, and what is under test is the same kind of thing:
this app's decisions, not boto3's. The properties most cases below exist to
hold:

  - **The row's identity is the rule.** One photo per person per POI is the
    unique constraint; a re-share replaces rather than refuses, and the
    replacement clears the club's pin because it is a different photograph.
  - **The gallery serves only what is really there.** A share whose bytes
    have not landed is invisible; a dismissed photo is invisible; an
    unconfigured deployment serves an empty gallery, never unsignable URLs.
  - **The caps are the design's, and the twelve roll.** Pins first and
    exempt; beyond the newest twelve unpinned photos, the oldest are
    deleted - row and object - because "at most 15" is a claim about the
    store, not just the screen.
  - **Withdrawal really withdraws.** Row and object both gone, idempotent,
    because the outbox retries and a promise kept twice is still kept.
  - **Masking is a stored fact.** The anonymity window is computed at share
    time and the public credit honours it, per POI_PHOTOS.md's licence
    reasoning.
"""

from datetime import date, timedelta

import boto3
import pytest
from moto import mock_aws

from app.config import settings
from app.core.photos import poi_photo_key
from app.core.time import utc_now
from app.models.poi_photo import PoiPhoto, PoiPhotoStatus
from app.models.preferences import UserPreferences
from app.models.profile import Role
from tests.factories import make_profile
from tests.tokens import auth_headers

_BUCKET = "ourhike-test"
_JPEG = b"\xff\xd8\xff\xe0" + b"pretend jpeg bytes" * 4
_POI = "atc_shelters:abc123"


@pytest.fixture()
def r2(monkeypatch):
    """A configured, empty bucket, with uploads switched on. Same double and
    same reasoning as test_report_photos.py's fixture."""
    with mock_aws():
        monkeypatch.setattr(settings, "r2_photo_endpoint_url", "https://s3.amazonaws.com")
        monkeypatch.setattr(settings, "r2_photo_bucket", _BUCKET)
        monkeypatch.setattr(settings, "r2_photo_access_key_id", "test-key")
        monkeypatch.setattr(settings, "r2_photo_secret_access_key", "test-secret")
        monkeypatch.setattr(settings, "r2_photo_write_enabled", True)
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket=_BUCKET)
        yield s3


def _hiker(db_session, name="Sawyer"):
    return make_profile(db_session, Role.hiker, display_name=name)


def _share(client, profile, poi=_POI, taken=None):
    payload = {} if taken is None else {"taken": taken}
    return client.post(f"/waypoints/{poi}/photos", json=payload, headers=auth_headers(profile.id))


def _upload(client, profile, poi=_POI, body=_JPEG, content_type="image/jpeg"):
    return client.put(
        f"/waypoints/{poi}/photos/mine",
        content=body,
        headers={**auth_headers(profile.id), "Content-Type": content_type},
    )


def _gallery(client, poi=_POI):
    response = client.get(f"/waypoints/{poi}/photos")
    assert response.status_code == 200
    return response.json()


# --- sharing ---------------------------------------------------------------


def test_share_needs_a_trail_name_to_credit(client, db_session, r2):
    anonymous = make_profile(db_session, Role.hiker)  # no display_name

    response = _share(client, anonymous)

    assert response.status_code == 409
    assert "trail name" in response.json()["detail"]


def test_share_records_attribution_licence_and_capture_month(client, db_session, r2):
    hiker = _hiker(db_session)

    response = _share(client, hiker, taken="2026-06-18")

    assert response.status_code == 201
    body = response.json()
    assert body["attribution"] == "Sawyer"
    assert body["license"] == "CC BY-SA 4.0"
    assert body["taken_month"] == "2026-06"
    assert body["pinned"] is False


def test_a_share_without_bytes_is_not_in_the_gallery(client, db_session, r2):
    hiker = _hiker(db_session)
    _share(client, hiker)

    assert _gallery(client) == []


def test_second_share_replaces_the_first_and_clears_the_pin(client, db_session, r2):
    hiker = _hiker(db_session)
    moderator = make_profile(db_session, Role.club_admin, display_name="Ridge")
    _share(client, hiker, taken="2020-01-10")
    _upload(client, hiker)

    # The club pins it (directly on the row - the pin ACTION is #579's).
    row = db_session.query(PoiPhoto).filter_by(poi_id=_POI, contributor_id=hiker.id).one()
    row.pinned_at = utc_now()
    row.pinned_by = moderator.id
    db_session.commit()

    response = _share(client, hiker, taken="2026-02-20")

    assert response.status_code == 201
    rows = db_session.query(PoiPhoto).filter_by(poi_id=_POI, contributor_id=hiker.id).all()
    assert len(rows) == 1
    db_session.refresh(rows[0])
    assert rows[0].taken == date(2026, 2, 20)
    assert rows[0].pinned_at is None
    # And the replacement is invisible until ITS bytes land.
    assert _gallery(client) == []


# --- uploading -------------------------------------------------------------


def test_upload_before_share_is_refused(client, db_session, r2):
    hiker = _hiker(db_session)

    response = _upload(client, hiker)

    assert response.status_code == 404


def test_upload_checks_the_bytes_not_the_header(client, db_session, r2):
    hiker = _hiker(db_session)
    _share(client, hiker)

    mislabelled = _upload(client, hiker, body=b"not a jpeg at all")
    assert mislabelled.status_code == 415

    wrong_header = _upload(client, hiker, content_type="image/png")
    assert wrong_header.status_code == 415


def test_shared_and_uploaded_photo_is_served_with_a_signed_url(client, db_session, r2):
    hiker = _hiker(db_session)
    _share(client, hiker, taken="2026-06-18")
    response = _upload(client, hiker)
    assert response.status_code == 200

    gallery = _gallery(client)
    assert len(gallery) == 1
    entry = gallery[0]
    assert entry["attribution"] == "Sawyer"
    assert entry["taken_month"] == "2026-06"
    assert entry["url"].startswith("http")
    # The object really is under the derived key, byte for byte.
    stored = r2.get_object(Bucket=_BUCKET, Key=poi_photo_key(_POI, hiker.id))
    assert stored["Body"].read() == _JPEG


def test_gallery_is_empty_where_storage_is_not_configured(client, db_session, r2, monkeypatch):
    hiker = _hiker(db_session)
    _share(client, hiker)
    _upload(client, hiker)

    monkeypatch.setattr(settings, "r2_photo_endpoint_url", None)

    assert _gallery(client) == []


def test_a_dismissed_photo_is_not_served(client, db_session, r2):
    hiker = _hiker(db_session)
    _share(client, hiker)
    _upload(client, hiker)

    row = db_session.query(PoiPhoto).filter_by(poi_id=_POI, contributor_id=hiker.id).one()
    row.status = PoiPhotoStatus.dismissed
    db_session.commit()

    assert _gallery(client) == []


def test_poi_id_that_could_escape_the_key_is_refused(client, db_session, r2):
    hiker = _hiker(db_session)

    response = client.post("/waypoints/..%2Freports/photos", json={}, headers=auth_headers(hiker.id))

    assert response.status_code == 404


# --- the caps --------------------------------------------------------------


def test_the_rolling_window_evicts_the_oldest_beyond_twelve(client, db_session, r2):
    # Thirteen hikers photograph one shelter, oldest capture date first.
    hikers = [_hiker(db_session, name=f"Hiker {n}") for n in range(13)]
    for n, hiker in enumerate(hikers):
        _share(client, hiker, taken=(date(2026, 1, 1) + timedelta(days=n)).isoformat())
        assert _upload(client, hiker).status_code == 200

    gallery = _gallery(client)
    assert len(gallery) == 12
    months = {entry["attribution"] for entry in gallery}
    assert "Hiker 0" not in months  # the oldest rolled out

    # Rolled out of the STORE, not just the screen: row and object both gone.
    assert db_session.query(PoiPhoto).filter_by(poi_id=_POI, contributor_id=hikers[0].id).one_or_none() is None
    listed = r2.list_objects_v2(Bucket=_BUCKET, Prefix=f"poi-photos/{_POI}/")
    keys = {obj["Key"] for obj in listed.get("Contents", [])}
    assert poi_photo_key(_POI, hikers[0].id) not in keys
    assert len(keys) == 12


def test_pins_are_exempt_from_the_window_and_served_first(client, db_session, r2):
    moderator = make_profile(db_session, Role.club_admin, display_name="Ridge")
    pinned_hiker = _hiker(db_session, name="Pinned")
    _share(client, pinned_hiker, taken="2019-05-05")  # older than everything below
    _upload(client, pinned_hiker)
    row = db_session.query(PoiPhoto).filter_by(poi_id=_POI, contributor_id=pinned_hiker.id).one()
    row.pinned_at = utc_now()
    row.pinned_by = moderator.id
    db_session.commit()

    hikers = [_hiker(db_session, name=f"Hiker {n}") for n in range(13)]
    for n, hiker in enumerate(hikers):
        _share(client, hiker, taken=(date(2026, 1, 1) + timedelta(days=n)).isoformat())
        _upload(client, hiker)

    gallery = _gallery(client)
    # The pin survives thirteen fresher photos and leads the gallery.
    assert gallery[0]["attribution"] == "Pinned"
    assert gallery[0]["pinned"] is True
    assert len(gallery) == 13  # 1 pinned + the rolling 12


# --- the anonymity window --------------------------------------------------


def test_the_window_masks_the_credit_and_is_stored_with_the_photo(client, db_session, r2):
    hiker = _hiker(db_session)
    db_session.add(UserPreferences(profile_id=hiker.id, data={"anonymity_window_days": 7}))
    db_session.commit()

    _share(client, hiker)
    _upload(client, hiker)

    gallery = _gallery(client)
    assert gallery[0]["attribution"] is None
    # The request is recorded with the photo - the licence-compliance fact
    # POI_PHOTOS.md requires - not evaluated against live preferences.
    row = db_session.query(PoiPhoto).filter_by(poi_id=_POI, contributor_id=hiker.id).one()
    assert row.masked_until is not None
    assert row.attribution_name == "Sawyer"


def test_no_window_means_the_credit_shows(client, db_session, r2):
    hiker = _hiker(db_session)
    _share(client, hiker)
    _upload(client, hiker)

    assert _gallery(client)[0]["attribution"] == "Sawyer"


# --- withdrawal ------------------------------------------------------------


def test_withdrawal_removes_the_row_and_the_object_and_is_idempotent(client, db_session, r2):
    hiker = _hiker(db_session)
    _share(client, hiker)
    _upload(client, hiker)
    assert len(_gallery(client)) == 1

    first = client.delete(f"/waypoints/{_POI}/photos/mine", headers=auth_headers(hiker.id))
    assert first.status_code == 204

    assert _gallery(client) == []
    assert db_session.query(PoiPhoto).filter_by(poi_id=_POI, contributor_id=hiker.id).one_or_none() is None
    listed = r2.list_objects_v2(Bucket=_BUCKET, Prefix=f"poi-photos/{_POI}/")
    assert listed.get("KeyCount", 0) == 0

    # The outbox retries; a wish already granted is granted again quietly.
    second = client.delete(f"/waypoints/{_POI}/photos/mine", headers=auth_headers(hiker.id))
    assert second.status_code == 204


def test_withdrawing_someone_elses_photo_is_impossible_by_construction(client, db_session, r2):
    owner = _hiker(db_session, name="Owner")
    other = _hiker(db_session, name="Other")
    _share(client, owner)
    _upload(client, owner)

    # `/mine` scopes the delete to the CALLER's row; the other hiker's
    # "withdrawal" deletes their own (absent) photo and touches nothing.
    response = client.delete(f"/waypoints/{_POI}/photos/mine", headers=auth_headers(other.id))
    assert response.status_code == 204
    assert len(_gallery(client)) == 1
