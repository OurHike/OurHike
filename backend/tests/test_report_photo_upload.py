"""Tests for `PUT /reports/{report_id}/photo` - part 1 of #234.

moto rather than a mocked `put_object`, matching what pipeline/ already does
(pipeline/tests/test_publish.py): a real boto3 client against an in-process
S3 means a key that would not survive a real PutObject fails here, and the
object can be read back and compared rather than inferred from a call
assertion.

The two rules worth stating before the tests, because both are security
properties rather than behaviour:

  - A report that is not yours is a 404, not a 403. Telling those apart turns
    a guessed UUID into a way to confirm one, and for `bad_hikers` into a way
    to confirm an incident note about a named individual exists.
  - Nothing here grants public read. The bucket is private and the Worker
    that checks the owning report before streaming is part 2, so a photo
    uploaded today is written and unreachable. That is the point.
"""

import os
import uuid

import boto3
import pytest
from moto import mock_aws

from app.core.photo_storage import (
    JPEG_MAGIC,
    MAX_PHOTO_BYTES,
    WRITE_ENABLED_ENV_VAR,
    PhotoStorageUnavailable,
    photo_key,
    photo_rejection,
    store_photo,
)
from app.models.profile import Profile, Role
from app.models.report import Report, ReportType, Visibility
from tests.tokens import auth_headers

BUCKET = "ourhike-test-photos"

# The smallest thing that is legitimately a JPEG as far as this endpoint is
# concerned: the SOI marker it checks, plus a byte of payload. Decoding is
# not this endpoint's job - part 3 downscales client-side, and a server that
# re-encoded would be undoing that work.
A_PHOTO = JPEG_MAGIC + b"\xe0 and then some bytes"


@pytest.fixture
def r2():
    """A private bucket, and the write gate open - both, because either one
    missing is a different 503 and both have their own tests below."""
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket=BUCKET)
        previous = os.environ.get(WRITE_ENABLED_ENV_VAR)
        os.environ[WRITE_ENABLED_ENV_VAR] = "true"
        for name, value in {
            # An AWS-shaped endpoint rather than R2's real
            # `*.r2.cloudflarestorage.com`, because moto intercepts botocore
            # by endpoint and would let a Cloudflare host through to the
            # network. Substituting it costs nothing that matters: R2 is
            # S3-compatible, which is the entire reason boto3 talks to it,
            # so the client built here is the client production builds.
            "R2_ENDPOINT_URL": "https://s3.us-east-1.amazonaws.com",
            "R2_BUCKET": BUCKET,
            "R2_ACCESS_KEY_ID": "test-key",
            "R2_SECRET_ACCESS_KEY": "test-secret",
        }.items():
            os.environ.setdefault(name, value)
        os.environ["R2_BUCKET"] = BUCKET
        os.environ["R2_ENDPOINT_URL"] = "https://s3.us-east-1.amazonaws.com"
        try:
            yield client
        finally:
            if previous is None:
                os.environ.pop(WRITE_ENABLED_ENV_VAR, None)
            else:
                os.environ[WRITE_ENABLED_ENV_VAR] = previous


def _reporter_with_report(db_session, report_type=ReportType.blowdown):
    reporter_id = str(uuid.uuid4())
    db_session.add(Profile(id=reporter_id, role=Role.hiker))
    db_session.commit()
    visibility = Visibility.internal_only if report_type == ReportType.bad_hikers else Visibility.public
    report = Report(
        reporter_id=reporter_id,
        type=report_type,
        reporter_type="thru",
        visibility=visibility,
    )
    db_session.add(report)
    db_session.commit()
    return reporter_id, report


def _put(client, report_id, reporter_id, data=A_PHOTO):
    return client.put(
        f"/reports/{report_id}/photo",
        content=data,
        headers={**auth_headers(reporter_id), "Content-Type": "image/jpeg"},
    )


# --- The key, which is the design decision the rest hangs off -------------


def test_the_key_is_derived_from_the_report_id():
    """Derived, never random and stored. That is what makes "which photos
    belong to this report" answerable from the id alone, and a retry an
    overwrite rather than a duplicate (#234)."""
    report_id = str(uuid.uuid4())

    assert photo_key(report_id) == f"reports/{report_id}/1.jpg"


def test_the_key_refuses_an_id_that_is_not_a_uuid():
    """A key is a path, and a path assembled from unvalidated input is how
    traversal happens. Every report id IS a UUID - this is the belt to that
    braces."""
    with pytest.raises(ValueError):
        photo_key("../../etc/passwd")


# --- What may be stored ---------------------------------------------------


def test_an_empty_body_is_refused():
    assert photo_rejection(b"") is not None


def test_something_that_is_not_a_jpeg_is_refused():
    """The key ends `.jpg` and part 2's Worker will serve it as image/jpeg
    from that name, so anything else would be mislabelled at the moment it is
    read, by a component with no way to notice."""
    assert photo_rejection(b"%PDF-1.7 not a photo") is not None


def test_a_photo_larger_than_the_ceiling_is_refused():
    assert photo_rejection(JPEG_MAGIC + b"x" * MAX_PHOTO_BYTES) is not None


def test_a_real_jpeg_within_the_ceiling_is_accepted():
    assert photo_rejection(A_PHOTO) is None


def test_the_rejection_reads_as_a_sentence_a_hiker_could_be_shown():
    """The client surfaces these on the More screen next to a stuck report
    (lib/api.ts), so they have to explain rather than classify."""
    reason = photo_rejection(b"%PDF-1.7")

    assert reason is not None
    assert reason.endswith(".")
    assert reason[0].isupper()


# --- The endpoint ---------------------------------------------------------


def test_uploading_stores_the_object_and_records_the_key(client, db_session, r2):
    reporter_id, report = _reporter_with_report(db_session)

    response = _put(client, report.id, reporter_id)

    assert response.status_code == 200
    assert response.json()["photo_url"] == photo_key(report.id)

    stored = r2.get_object(Bucket=BUCKET, Key=photo_key(report.id))
    assert stored["Body"].read() == A_PHOTO
    assert stored["ContentType"] == "image/jpeg"


def test_the_row_records_a_key_rather_than_a_url(client, db_session, r2):
    """A full URL would bake today's bucket domain into every row
    permanently (#234)."""
    reporter_id, report = _reporter_with_report(db_session)

    _put(client, report.id, reporter_id)

    db_session.expire_all()
    stored = db_session.get(Report, report.id)
    assert not stored.photo_url.startswith("http")
    assert stored.photo_url == f"reports/{report.id}/1.jpg"


def test_uploading_twice_overwrites_rather_than_duplicating(client, db_session, r2):
    """The offline case #234 names as the one that will actually bite: the
    outbox retries, and a random key would leave two objects for one report."""
    reporter_id, report = _reporter_with_report(db_session)
    second = JPEG_MAGIC + b"\xe0 a different photo entirely"

    _put(client, report.id, reporter_id)
    _put(client, report.id, reporter_id, data=second)

    listing = r2.list_objects_v2(Bucket=BUCKET, Prefix=f"reports/{report.id}/")
    assert listing["KeyCount"] == 1
    assert r2.get_object(Bucket=BUCKET, Key=photo_key(report.id))["Body"].read() == second


def test_uploading_needs_an_account(client, db_session, r2):
    _reporter_id, report = _reporter_with_report(db_session)

    response = client.put(f"/reports/{report.id}/photo", content=A_PHOTO)

    assert response.status_code == 401


def test_somebody_elses_report_is_a_404_not_a_403(client, db_session, r2):
    """The rule stated in #363, and the reason it is a rule: a 403 confirms
    the id names a real report, which for `bad_hikers` confirms an incident
    note about a named individual exists. A guessed UUID must learn nothing.
    """
    _reporter_id, report = _reporter_with_report(db_session, report_type=ReportType.bad_hikers)
    stranger_id = str(uuid.uuid4())
    db_session.add(Profile(id=stranger_id, role=Role.hiker))
    db_session.commit()

    response = _put(client, report.id, stranger_id)

    assert response.status_code == 404


def test_an_id_that_names_no_report_gets_the_same_404(client, db_session, r2):
    """Same status AND same body as the wrong-owner case above - a difference
    in either is the oracle the 404 exists to remove."""
    stranger_id = str(uuid.uuid4())
    db_session.add(Profile(id=stranger_id, role=Role.hiker))
    db_session.commit()
    _reporter_id, real = _reporter_with_report(db_session, report_type=ReportType.bad_hikers)

    missing = _put(client, str(uuid.uuid4()), stranger_id)
    wrong_owner = _put(client, real.id, stranger_id)

    assert missing.status_code == wrong_owner.status_code == 404
    assert missing.json() == wrong_owner.json()


def test_a_moderator_cannot_upload_to_a_report_they_did_not_file(client, db_session, r2):
    """Reading a photo is part 2's business and goes through the Worker.
    Writing is only ever the author's - a role that could overwrite somebody
    else's evidence is not a moderation power anybody asked for."""
    _reporter_id, report = _reporter_with_report(db_session)
    maintainer_id = str(uuid.uuid4())
    db_session.add(Profile(id=maintainer_id, role=Role.maintainer))
    db_session.commit()

    assert _put(client, report.id, maintainer_id).status_code == 404


def test_a_body_that_is_not_a_jpeg_is_refused_with_422(client, db_session, r2):
    reporter_id, report = _reporter_with_report(db_session)

    response = _put(client, report.id, reporter_id, data=b"%PDF-1.7 not a photo")

    assert response.status_code == 422
    assert r2.list_objects_v2(Bucket=BUCKET).get("KeyCount", 0) == 0


def test_an_oversized_body_is_refused_with_413(client, db_session, r2):
    reporter_id, report = _reporter_with_report(db_session)

    response = _put(client, report.id, reporter_id, data=JPEG_MAGIC + b"x" * MAX_PHOTO_BYTES)

    assert response.status_code == 413
    assert r2.list_objects_v2(Bucket=BUCKET).get("KeyCount", 0) == 0


def test_a_refused_photo_leaves_the_row_alone(client, db_session, r2):
    """The report is authoritative and the object derived - so a rejected
    upload must not leave `photo_url` pointing at something that was never
    written."""
    reporter_id, report = _reporter_with_report(db_session)

    _put(client, report.id, reporter_id, data=b"not a photo at all")

    db_session.expire_all()
    assert db_session.get(Report, report.id).photo_url is None


# --- When this deployment cannot store photos at all ----------------------


def test_the_write_gate_is_closed_by_default(client, db_session):
    """`pipeline/publish.py`'s gate, reused rather than reinvented: an
    environment that should not write to the bucket cannot, and finds out
    loudly."""
    reporter_id, report = _reporter_with_report(db_session)
    previous = os.environ.pop(WRITE_ENABLED_ENV_VAR, None)
    try:
        response = _put(client, report.id, reporter_id)
    finally:
        if previous is not None:
            os.environ[WRITE_ENABLED_ENV_VAR] = previous

    assert response.status_code == 503
    assert WRITE_ENABLED_ENV_VAR in response.json()["detail"]


def test_an_unconfigured_deployment_says_which_half_is_missing():
    """ "R2 is not configured" without saying which variable is a support
    ticket rather than a fix."""
    previous = {name: os.environ.pop(name, None) for name in ("R2_BUCKET",)}
    os.environ[WRITE_ENABLED_ENV_VAR] = "true"
    try:
        with pytest.raises(PhotoStorageUnavailable) as raised:
            store_photo(str(uuid.uuid4()), A_PHOTO)
    finally:
        for name, value in previous.items():
            if value is not None:
                os.environ[name] = value
        os.environ.pop(WRITE_ENABLED_ENV_VAR, None)

    assert "R2_BUCKET" in str(raised.value)


def test_unavailable_is_a_503_so_the_outbox_keeps_the_photo(client, db_session):
    """503 rather than 422, and the distinction is load-bearing: lib/api.ts's
    `permanentFailureReason` allow-lists only 409 and 422 as permanent, so a
    422 here would make a client discard a photo over a server
    misconfiguration."""
    reporter_id, report = _reporter_with_report(db_session)
    os.environ.pop(WRITE_ENABLED_ENV_VAR, None)

    assert _put(client, report.id, reporter_id).status_code == 503
