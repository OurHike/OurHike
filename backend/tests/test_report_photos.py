"""Report photos - `PUT` to store one, `GET` to fetch it back (#234).

S3 is doubled in-process with moto rather than reached over the network, the
project's established convention (pipeline/tests/test_publish.py does the same
for publish.py). What is under test is this app's decisions - who may upload,
what is accepted, and what ends up in the row - not boto3's ability to put an
object.

The three properties worth stating up front, because most cases below exist to
hold one of them:

  - **The key is derived from the report id**, never stored and looked up, so
    which objects belong to a report is answerable from the id alone and a
    retry overwrites rather than duplicates (app/core/photos.py).
  - **The row is the authoritative half.** `photo_url` is only written once
    the object is really there.
  - **A photo has the report's audience, not its own.** Everything the read
    path refuses, it refuses because `_visible_to` said so - the same function
    `GET /reports/{id}` uses - and it refuses uniformly with a 404.
"""

import uuid

import boto3
import pytest
import requests
from moto import mock_aws

from app.config import Settings, settings
from app.core.photos import PHOTO_URL_TTL_SECONDS, photo_key
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
        _configure(monkeypatch)
        monkeypatch.setattr(settings, "r2_photo_write_enabled", True)
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket=_BUCKET)
        yield s3


def _configure(monkeypatch) -> None:
    """Point the photo settings at the doubled bucket, uploads still off."""
    monkeypatch.setattr(settings, "r2_photo_endpoint_url", "https://s3.amazonaws.com")
    monkeypatch.setattr(settings, "r2_photo_bucket", _BUCKET)
    monkeypatch.setattr(settings, "r2_photo_access_key_id", "test-key")
    monkeypatch.setattr(settings, "r2_photo_secret_access_key", "test-secret")


def _reporter(db_session) -> Profile:
    profile = Profile(id=str(uuid.uuid4()), role=Role.hiker)
    db_session.add(profile)
    db_session.commit()
    return profile


def _report(
    db_session,
    reporter: Profile,
    *,
    type: ReportType = ReportType.blowdown,
    status: ReportStatus = ReportStatus.submitted,
    visibility: Visibility = Visibility.public,
    photo_url: str | None = None,
) -> Report:
    report = Report(
        id=str(uuid.uuid4()),
        reporter_id=reporter.id,
        type=type,
        reporter_type=ReporterType.thru,
        lat=35.6,
        lon=-83.5,
        status=status,
        visibility=visibility,
        photo_url=photo_url,
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
    _configure(monkeypatch)
    monkeypatch.setattr(settings, "r2_photo_write_enabled", False)

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


def test_the_published_bucket_variables_do_not_configure_report_photos(monkeypatch):
    """The settings this backend reads are NOT the ones publish.py reads.

    `R2_BUCKET` names the published bucket, which LAUNCH_CHECKLIST.md 1.5
    turns public read on for. A deployment carrying the publishing environment
    - one shared secret store, one platform injecting a set of variables for
    the whole project - must not thereby be configured to put report photos in
    it: a `bad_hikers` photo is a photo of a person, and that bucket answers
    anybody.

    Asserted against a freshly constructed `Settings` rather than the imported
    singleton, because what is under test is the env-var binding itself.
    """
    monkeypatch.setenv("R2_ENDPOINT_URL", "https://acct.r2.cloudflarestorage.com")
    monkeypatch.setenv("R2_BUCKET", "your-hike")
    monkeypatch.setenv("R2_ACCESS_KEY_ID", "publishing-key")
    monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "publishing-secret")
    monkeypatch.setenv("R2_WRITE_ENABLED", "true")

    fresh = Settings()

    assert fresh.r2_photo_bucket == ""
    assert fresh.r2_photo_endpoint_url == ""
    assert fresh.r2_photo_access_key_id == ""
    assert fresh.r2_photo_secret_access_key == ""
    assert fresh.r2_photo_write_enabled is False


# ---------------------------------------------------------------------------
# Reading one back - `GET /reports/{id}/photo`.
#
# Every case here is really one question asked in a different shape: does the
# photo inherit the report's audience? A public bucket URL would answer "no"
# to all of them at once, which is the design this endpoint exists to avoid.
# ---------------------------------------------------------------------------


def _stored(client, db_session, r2, **report_kwargs) -> tuple[Profile, Report]:
    """A report with its photo really in the bucket, uploaded the normal way.

    Through `PUT` rather than by writing the row and the object directly, so
    that what the read path is handed is what the write path actually produces
    - the two halves agreeing is most of what these cases are checking.
    Attributes that only matter after moderation are set afterwards, because
    the endpoint refuses an upload to somebody else's report and a moderated
    report is not something a reporter can file.
    """
    reporter = _reporter(db_session)
    report = _report(db_session, reporter)

    response = client.put(
        f"/reports/{report.id}/photo",
        content=_JPEG,
        headers={**auth_headers(reporter.id), "content-type": "image/jpeg"},
    )
    assert response.status_code == 200

    for field, value in report_kwargs.items():
        setattr(report, field, value)
    db_session.commit()
    db_session.refresh(report)
    return reporter, report


def _photo(client, report_id: str, viewer_id: str | None = None):
    """GET the photo without chasing the redirect - the redirect IS the answer."""
    headers = auth_headers(viewer_id) if viewer_id is not None else {}
    return client.get(f"/reports/{report_id}/photo", headers=headers, follow_redirects=False)


def test_serves_a_moderated_public_photo_to_anybody(client, db_session, r2):
    """Browsing needs no account, here as everywhere else in this router."""
    _, report = _stored(client, db_session, r2, status=ReportStatus.verified)

    response = _photo(client, report.id)

    assert response.status_code == 302
    location = response.headers["location"]
    # Path-style or virtual-hosted, the key is in it either way; asserting the
    # key rather than the whole URL is what keeps this about authorisation.
    assert photo_key(report.id) in location
    assert "X-Amz-Signature" in location
    assert f"X-Amz-Expires={PHOTO_URL_TTL_SECONDS}" in location


def test_the_signed_url_really_fetches_the_photo(client, db_session, r2):
    """The one case that follows the redirect all the way to the bytes.

    Everything else asserts the shape of the URL, which would keep passing if
    the signature were wrong or the key pointed somewhere empty. This one
    proves the hop actually resolves to the image that was uploaded.
    """
    _, report = _stored(client, db_session, r2, status=ReportStatus.verified)

    location = _photo(client, report.id).headers["location"]
    fetched = requests.get(location, timeout=10)

    assert fetched.status_code == 200
    assert fetched.content == _JPEG


def test_the_redirect_is_never_cached(client, db_session, r2):
    """Load-bearing, not hygiene.

    A cached 302 outlives the signature (a broken image once it expires) and,
    worse, outlives the visibility DECISION: a report dismissed afterwards
    would still be reachable through whatever kept the hop. The check has to
    run on every view for its answer to mean anything.
    """
    _, report = _stored(client, db_session, r2, status=ReportStatus.verified)

    response = _photo(client, report.id)

    assert "no-store" in response.headers["cache-control"]


def test_an_unmoderated_report_does_not_show_its_photo_to_a_stranger(client, db_session, r2):
    """#229's rule, one layer down.

    A photo is attached at create time, before anyone has looked at it. If the
    report is not publicly visible until it is verified, neither is the image
    - otherwise moderation is a label on something already published.
    """
    _, report = _stored(client, db_session, r2)  # left `submitted`
    stranger = _reporter(db_session)

    assert _photo(client, report.id).status_code == 404
    assert _photo(client, report.id, stranger.id).status_code == 404


def test_the_reporter_sees_their_own_photo_while_it_waits(client, db_session, r2):
    """The other half of the same rule: "Waiting" has to have something to
    appear on, and it is the reporter's own photo."""
    reporter, report = _stored(client, db_session, r2)  # left `submitted`

    assert _photo(client, report.id, reporter.id).status_code == 302


def test_a_bad_hikers_photo_is_not_served_to_a_stranger(client, db_session, r2):
    """The case the private bucket exists for.

    `bad_hikers` is `internal_only` and those are photos of people. Verified
    and resolved change nothing about who may see it - visibility does, and
    visibility is what this endpoint reads.
    """
    reporter, report = _stored(
        client,
        db_session,
        r2,
        type=ReportType.bad_hikers,
        visibility=Visibility.internal_only,
        status=ReportStatus.verified,
    )
    stranger = _reporter(db_session)

    assert _photo(client, report.id).status_code == 404
    assert _photo(client, report.id, stranger.id).status_code == 404
    # ...and still visible to the person who filed it, which is what makes the
    # 404 above a routing decision rather than the photo being missing.
    assert _photo(client, report.id, reporter.id).status_code == 302


def test_a_report_with_no_photo_is_a_404(client, db_session, r2):
    """Not a redirect to an object that is not there: a signed URL for a
    missing key would answer 403 or 404 from R2 with no explanation, from a
    hostname that is not ours."""
    reporter = _reporter(db_session)
    report = _report(db_session, reporter, status=ReportStatus.verified)

    assert _photo(client, report.id, reporter.id).status_code == 404


def test_an_unknown_report_is_a_404(client, db_session, r2):
    assert _photo(client, str(uuid.uuid4())).status_code == 404


def test_the_key_is_derived_from_the_report_not_read_out_of_the_row(client, db_session, r2):
    """`photo_url` is settable on `POST /reports`, so it is client-supplied
    text and cannot be dereferenced.

    A serving path that trusted it would let a report point at any object in
    the bucket - another report's photo among them - and the visibility check
    in front of it would have been checking the wrong report entirely. Deriving
    the key means the only object this endpoint can hand out is the one
    belonging to the report it just authorised.
    """
    _, victim = _stored(client, db_session, r2, status=ReportStatus.verified)
    reporter = _reporter(db_session)
    attacker = _report(
        db_session,
        reporter,
        status=ReportStatus.verified,
        photo_url=photo_key(victim.id),
    )

    location = _photo(client, attacker.id, reporter.id).headers["location"]

    assert photo_key(attacker.id) in location
    assert photo_key(victim.id) not in location


def test_serving_does_not_depend_on_the_write_gate(client, db_session, r2, monkeypatch):
    """Turning uploads off is a decision about what may be ADDED to the bucket.

    A deployment that has stopped accepting photos should still be able to show
    a moderator the photo attached to the report they are deciding on -
    otherwise closing the intake retroactively blinds the queue.
    """
    _, report = _stored(client, db_session, r2, status=ReportStatus.verified)
    monkeypatch.setattr(settings, "r2_photo_write_enabled", False)

    assert _photo(client, report.id).status_code == 302


def test_says_so_rather_than_404ing_when_no_bucket_is_configured(client, db_session):
    """503, and specifically not 404.

    No bucket on this deployment is not the same statement as "this report has
    no photo", and a client told "not found" would stop asking. Every developer
    machine and every CI run is this case - note the absent `r2` fixture.
    """
    reporter = _reporter(db_session)
    report = _report(db_session, reporter, status=ReportStatus.verified, photo_url="reports/x/1.jpg")

    assert _photo(client, report.id, reporter.id).status_code == 503
