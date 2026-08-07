"""Report photo upload - `PUT /reports/{id}/photo` (#234).

S3 is doubled in-process with moto rather than reached over the network, the
project's established convention (pipeline/tests/test_publish.py does the same
for publish.py). What is under test is this app's decisions - who may upload,
what is accepted, and what ends up in the row - not boto3's ability to put an
object.

The two properties worth stating up front, because most cases below exist to
hold one of them:

  - **The key is derived from the report id**, never stored and looked up, so
    which objects belong to a report is answerable from the id alone and a
    retry overwrites rather than duplicates (app/core/photos.py).
  - **The row is the authoritative half.** `photo_url` is only written once
    the object is really there.
"""

import uuid

import boto3
import pytest
from moto import mock_aws

from app.config import settings
from app.core.photos import photo_key
from app.models.profile import Profile, Role
from app.models.report import Report, ReporterType, ReportStatus, ReportType, Visibility
from tests.tokens import auth_headers

_BUCKET = "ourhike-test"
_JPEG = b"\xff\xd8\xff\xe0" + b"pretend jpeg bytes" * 4


@pytest.fixture()
def r2(monkeypatch):
    """A configured, empty bucket, with uploads switched on.

    Sets the write gate explicitly rather than letting the credentials imply
    it: the gate is a separate decision in app/config.py, and a test that
    turned it on by accident would stop being able to prove it works.

    The endpoint is an AWS-shaped one rather than an `r2.cloudflarestorage.com`
    address, and that is a constraint of the double rather than a claim about
    production: moto intercepts botocore's AWS endpoints, and a custom host it
    does not recognise is attempted for real - which in this sandbox fails
    against the proxy and would have every case below passing for the wrong
    reason (a 503 that means "could not connect" reads exactly like a 503 that
    means "not configured"). R2 speaks the same S3 API either way; what is
    under test here is this app's decisions, not Cloudflare's DNS.
    """
    with mock_aws():
        monkeypatch.setattr(settings, "r2_endpoint_url", "https://s3.amazonaws.com")
        monkeypatch.setattr(settings, "r2_bucket", _BUCKET)
        monkeypatch.setattr(settings, "r2_access_key_id", "test-key")
        monkeypatch.setattr(settings, "r2_secret_access_key", "test-secret")
        monkeypatch.setattr(settings, "r2_write_enabled", True)
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket=_BUCKET)
        yield s3


def _reporter(db_session) -> Profile:
    profile = Profile(id=str(uuid.uuid4()), role=Role.hiker)
    db_session.add(profile)
    db_session.commit()
    return profile


def _report(db_session, reporter: Profile) -> Report:
    report = Report(
        id=str(uuid.uuid4()),
        reporter_id=reporter.id,
        type=ReportType.blowdown,
        reporter_type=ReporterType.thru,
        lat=35.6,
        lon=-83.5,
        status=ReportStatus.submitted,
        visibility=Visibility.public,
    )
    db_session.add(report)
    db_session.commit()
    return report


def test_stores_the_photo_and_records_its_key(client, db_session, r2):
    reporter = _reporter(db_session)
    report = _report(db_session, reporter)

    response = client.put(
        f"/reports/{report.id}/photo",
        content=_JPEG,
        headers={**auth_headers(reporter.id), "content-type": "image/jpeg"},
    )

    assert response.status_code == 200
    # The KEY, not a URL: a full URL bakes today's bucket domain into every
    # row permanently, and that domain is a documented stopgap.
    assert response.json()["photo_url"] == f"reports/{report.id}/1.jpg"
    assert "http" not in response.json()["photo_url"]

    stored = r2.get_object(Bucket=_BUCKET, Key=photo_key(report.id))
    assert stored["Body"].read() == _JPEG
    assert stored["ContentType"] == "image/jpeg"


def test_a_retry_overwrites_rather_than_duplicating(client, db_session, r2):
    """The offline case, which on this trail is the normal one.

    A derived key means the second attempt lands on the first one's object.
    A random key would leave two, with the row naming one of them and nothing
    naming the other.
    """
    reporter = _reporter(db_session)
    report = _report(db_session, reporter)
    headers = {**auth_headers(reporter.id), "content-type": "image/jpeg"}

    client.put(f"/reports/{report.id}/photo", content=_JPEG, headers=headers)
    client.put(f"/reports/{report.id}/photo", content=_JPEG + b"second try", headers=headers)

    listing = r2.list_objects_v2(Bucket=_BUCKET, Prefix=f"reports/{report.id}/")
    assert listing["KeyCount"] == 1
    assert r2.get_object(Bucket=_BUCKET, Key=photo_key(report.id))["Body"].read().endswith(b"second try")


def test_refuses_a_photo_for_somebody_elses_report(client, db_session, r2):
    """404 rather than 403, and deliberately.

    A report that is not yours is one you have no business knowing exists -
    distinguishing "wrong owner" from "no such id" turns a guessed UUID into a
    way to confirm one, and for `bad_hikers` into a way to confirm an incident
    note about a named individual.
    """
    reporter = _reporter(db_session)
    intruder = _reporter(db_session)
    report = _report(db_session, reporter)

    response = client.put(
        f"/reports/{report.id}/photo",
        content=_JPEG,
        headers={**auth_headers(intruder.id), "content-type": "image/jpeg"},
    )

    assert response.status_code == 404
    assert r2.list_objects_v2(Bucket=_BUCKET).get("KeyCount", 0) == 0
    db_session.refresh(report)
    assert report.photo_url is None


def test_requires_authentication(client, db_session, r2):
    reporter = _reporter(db_session)
    report = _report(db_session, reporter)

    response = client.put(f"/reports/{report.id}/photo", content=_JPEG, headers={"content-type": "image/jpeg"})

    assert response.status_code in (401, 403)


def test_unknown_report_is_not_an_upload_target(client, db_session, r2):
    """No row, no object. The report is what gives an object a reason to
    exist, which is the whole of the orphan story in app/core/photos.py."""
    reporter = _reporter(db_session)

    response = client.put(
        f"/reports/{uuid.uuid4()}/photo",
        content=_JPEG,
        headers={**auth_headers(reporter.id), "content-type": "image/jpeg"},
    )

    assert response.status_code == 404
    assert r2.list_objects_v2(Bucket=_BUCKET).get("KeyCount", 0) == 0


def test_refuses_anything_that_is_not_a_jpeg(client, db_session, r2):
    reporter = _reporter(db_session)
    report = _report(db_session, reporter)

    response = client.put(
        f"/reports/{report.id}/photo",
        content=b"<svg/>",
        headers={**auth_headers(reporter.id), "content-type": "image/svg+xml"},
    )

    assert response.status_code == 415
    assert r2.list_objects_v2(Bucket=_BUCKET).get("KeyCount", 0) == 0


def test_refuses_a_photo_that_was_never_downscaled(client, db_session, r2):
    """The client resizes before uploading; this is the guard for one that
    did not. Egress is the cost R2 was chosen to keep flat, and an untouched
    phone photo is several megabytes of it."""
    reporter = _reporter(db_session)
    report = _report(db_session, reporter)

    response = client.put(
        f"/reports/{report.id}/photo",
        content=b"x" * (2 * 1024 * 1024 + 1),
        headers={**auth_headers(reporter.id), "content-type": "image/jpeg"},
    )

    assert response.status_code == 413
    assert r2.list_objects_v2(Bucket=_BUCKET).get("KeyCount", 0) == 0


def test_says_so_rather_than_failing_when_no_bucket_is_configured(client, db_session):
    """Every developer machine and every CI run is this case.

    503 rather than 500, so the client keeps the photo queued instead of
    treating it as rejected - and no `r2` fixture here, which is the point:
    the gate is off by default.
    """
    reporter = _reporter(db_session)
    report = _report(db_session, reporter)

    response = client.put(
        f"/reports/{report.id}/photo",
        content=_JPEG,
        headers={**auth_headers(reporter.id), "content-type": "image/jpeg"},
    )

    assert response.status_code == 503
    db_session.refresh(report)
    assert report.photo_url is None


def test_credentials_alone_do_not_enable_uploads(client, db_session, monkeypatch):
    """The write gate is a separate decision from having credentials.

    Credentials can be present for a reason that is not this one - a shared
    environment, a platform-injected secret - and a process that should not
    upload should be unable to rather than merely unlikely to. Same rule
    pipeline/publish.py's R2_WRITE_ENABLED encodes.
    """
    monkeypatch.setattr(settings, "r2_endpoint_url", "https://s3.amazonaws.com")
    monkeypatch.setattr(settings, "r2_bucket", _BUCKET)
    monkeypatch.setattr(settings, "r2_access_key_id", "test-key")
    monkeypatch.setattr(settings, "r2_secret_access_key", "test-secret")
    monkeypatch.setattr(settings, "r2_write_enabled", False)

    reporter = _reporter(db_session)
    report = _report(db_session, reporter)

    response = client.put(
        f"/reports/{report.id}/photo",
        content=_JPEG,
        headers={**auth_headers(reporter.id), "content-type": "image/jpeg"},
    )

    assert response.status_code == 503


def test_photo_key_is_the_only_spelling_of_the_key():
    """Pure, and asserted directly because two spellings is how the uploader
    and a future sweeper come to disagree about what belongs to a report."""
    assert photo_key("abc-123") == "reports/abc-123/1.jpg"
    assert photo_key("abc-123", 2) == "reports/abc-123/2.jpg"
