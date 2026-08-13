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

import asyncio
import uuid

import boto3
import pytest
import requests
from fastapi import HTTPException, Request
from moto import mock_aws
from pydantic import ValidationError

from app.config import Settings, settings
from app.core.photos import MAX_PHOTO_BYTES, PHOTO_URL_TTL_SECONDS, photo_key
from app.models.profile import Profile, Role
from app.models.report import Report, ReporterType, ReportStatus, ReportType, Visibility
from app.routers.reports import read_capped_body
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


def _reading(chunks: list[bytes], headers: dict[str, str] | None = None) -> tuple[Request, list[int]]:
    """A `Request` whose body really arrives in pieces, and a record of which
    pieces were asked for.

    Direct rather than through `client`: starlette's sync `TestClient` calls
    `request.read()` on the way in, so a generator body is drained in the
    client and the app sees one chunk however it was offered. That makes the
    status code observable through the route (the tests below do check it) but
    not the reading, which is the half #379 is actually about. Under uvicorn
    `receive` delivers what has arrived off the socket, which is what this
    reproduces.
    """
    pulled: list[int] = []
    remaining = list(chunks)

    async def receive() -> dict:
        if not remaining:
            return {"type": "http.request", "body": b"", "more_body": False}
        chunk = remaining.pop(0)
        pulled.append(len(chunk))
        return {"type": "http.request", "body": chunk, "more_body": bool(remaining)}

    scope = {
        "type": "http",
        "method": "PUT",
        "path": "/reports/x/photo",
        "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()],
    }
    return Request(scope, receive), pulled


def test_an_oversized_body_is_cut_off_partway_rather_than_buffered():
    """No `Content-Length` at all, which is the case a header check misses.

    A chunked request declares nothing, so the only thing that can refuse it
    is the running total over the stream - and it has to refuse partway. The
    assertion that matters is the second one: a limit applied to the finished
    buffer would pull all 64 pieces and refuse afterwards, having already
    allocated the thing it was refusing.
    """
    # 4 MB offered in 64 KB pieces, against a 2 MB cap.
    request, pulled = _reading([b"x" * (64 * 1024)] * 64)

    with pytest.raises(HTTPException) as refused:
        asyncio.run(read_capped_body(request, MAX_PHOTO_BYTES))

    assert refused.value.status_code == 413
    assert len(pulled) < 64, "the whole body was read before the limit was applied"
    assert sum(pulled) <= MAX_PHOTO_BYTES + 64 * 1024, f"read {sum(pulled)} bytes of a 4 MB body"


def test_a_declared_oversize_is_refused_without_reading_the_body_at_all():
    """`Content-Length` is only an optimisation, but it is a real one: when the
    sender declares an oversized body there is no reason to read a byte of it."""
    request, pulled = _reading(
        [b"x" * 1024] * 4,
        headers={"content-length": str(8 * 1024 * 1024)},
    )

    with pytest.raises(HTTPException) as refused:
        asyncio.run(read_capped_body(request, MAX_PHOTO_BYTES))

    assert refused.value.status_code == 413
    assert pulled == [], f"read {sum(pulled)} bytes of a body that declared itself oversized"


def test_a_lying_content_length_does_not_get_the_body_through():
    """The header is a claim. A body that declares itself small and then keeps
    arriving is stopped by the running total, not by the claim."""
    request, pulled = _reading(
        [b"x" * (64 * 1024)] * 64,
        headers={"content-length": "12"},
    )

    with pytest.raises(HTTPException) as refused:
        asyncio.run(read_capped_body(request, MAX_PHOTO_BYTES))

    assert refused.value.status_code == 413
    assert sum(pulled) <= MAX_PHOTO_BYTES + 64 * 1024


def test_an_unparseable_content_length_decides_nothing_either_way():
    """A header this malformed is somebody else's bug, and it must neither
    refuse a body that fits nor wave through one that does not."""
    fits, _ = _reading([_JPEG], headers={"content-length": "not a number"})
    assert asyncio.run(read_capped_body(fits, MAX_PHOTO_BYTES)) == _JPEG

    does_not, _ = _reading(
        [b"x" * (64 * 1024)] * 64,
        headers={"content-length": "not a number"},
    )
    with pytest.raises(HTTPException) as refused:
        asyncio.run(read_capped_body(does_not, MAX_PHOTO_BYTES))
    assert refused.value.status_code == 413


def test_a_body_that_fits_is_returned_whole():
    """The reassembly is as much of the function as the refusing: a photo that
    arrives in four pieces has to come back out as the bytes that were sent."""
    request, pulled = _reading([_JPEG[:4], _JPEG[4:10], _JPEG[10:]])

    assert asyncio.run(read_capped_body(request, MAX_PHOTO_BYTES)) == _JPEG
    assert len(pulled) == 3, "the pieces were not all read"


def test_an_oversized_upload_is_refused_by_the_endpoint(client, db_session, r2):
    """The same limit, through the route, so the status a client sees is
    pinned as well as the reading behaviour above."""
    reporter = _reporter(db_session)
    report = _report(db_session, reporter)

    response = client.put(
        f"/reports/{report.id}/photo",
        content=b"\xff\xd8\xff" + b"x" * (2 * 1024 * 1024),
        headers={**auth_headers(reporter.id), "content-type": "image/jpeg"},
    )

    assert response.status_code == 413
    assert r2.list_objects_v2(Bucket=_BUCKET).get("KeyCount", 0) == 0


def test_refuses_bytes_that_are_not_a_jpeg_however_they_are_labelled(client, db_session, r2):
    """The `Content-Type` header is the sender describing their own bytes.

    We store the object as `.jpg` with `ContentType: image/jpeg` set by us and
    hand that back to a browser through a signed URL, so the label has to be
    true rather than merely claimed (#379).
    """
    reporter = _reporter(db_session)
    report = _report(db_session, reporter)

    response = client.put(
        f"/reports/{report.id}/photo",
        content=b'<svg onload="alert(1)"/>',
        headers={**auth_headers(reporter.id), "content-type": "image/jpeg"},
    )

    assert response.status_code == 415
    assert r2.list_objects_v2(Bucket=_BUCKET).get("KeyCount", 0) == 0

    db_session.refresh(report)
    assert report.photo_url is None


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


# --- The photo a MODERATOR is deciding on (#385) ---------------------------
#
# Everything above this line is about a hiker and their own report. The queue
# is the other audience, and it was the one `GET /photo` refused: `_visible_to`
# knew the reporter and the public and nobody else, so a maintainer looking at
# an `internal_only` `bad_hikers` report - the case the private bucket, the
# private routing and the queue's own separate section all exist for - got the
# same 404 as a report with no photo.


def _moderator(db_session, role: Role = Role.maintainer) -> Profile:
    profile = Profile(id=str(uuid.uuid4()), role=role)
    db_session.add(profile)
    db_session.commit()
    return profile


def _link(client, report_id: str, viewer_id: str | None = None):
    """GET the JSON form - the one an `<img>` can be pointed at."""
    headers = auth_headers(viewer_id) if viewer_id is not None else {}
    return client.get(f"/reports/{report_id}/photo/link", headers=headers)


@pytest.mark.parametrize("role", [Role.maintainer, Role.club_admin])
def test_a_moderator_sees_the_bad_hikers_photo_they_are_deciding_on(client, db_session, r2, role):
    """The case #385 exists for, and the one that was broken.

    `/moderation/queue` has handed this report's whole record - note,
    `photo_url`, `reporter_id` - to exactly these two roles since #235. The
    photo behind it answered 404. Both roles, because `MODERATOR_ROLES` is the
    pair and a check that only knew one of them would pass a single-role test.
    """
    _, report = _stored(
        client,
        db_session,
        r2,
        type=ReportType.bad_hikers,
        visibility=Visibility.internal_only,
    )
    moderator = _moderator(db_session, role)

    assert _photo(client, report.id, moderator.id).status_code == 302
    assert _link(client, report.id, moderator.id).status_code == 200


def test_a_plain_hiker_is_still_refused_the_same_photo(client, db_session, r2):
    """The moderator clause is a role, not a token.

    Every signed-in account would be an authorisation check that had stopped
    checking anything - and this is the report type where that is a photo of a
    person handed to whoever asked.
    """
    _, report = _stored(
        client,
        db_session,
        r2,
        type=ReportType.bad_hikers,
        visibility=Visibility.internal_only,
    )
    stranger = _reporter(db_session)  # role=hiker

    assert _photo(client, report.id, stranger.id).status_code == 404
    assert _link(client, report.id, stranger.id).status_code == 404


def test_a_moderator_can_look_again_after_deciding(client, db_session, r2):
    """A verified report leaves the queue; the photo does not leave with it.

    This is the widening `_visible_to`'s docstring names deliberately: a
    decision nobody can look at again after it is made is a decision nobody
    can review.
    """
    _, report = _stored(
        client,
        db_session,
        r2,
        type=ReportType.bad_hikers,
        visibility=Visibility.internal_only,
        status=ReportStatus.verified,
    )
    moderator = _moderator(db_session)

    assert _link(client, report.id, moderator.id).status_code == 200


def test_moderator_visibility_does_not_leak_into_the_public_list(client, db_session, r2):
    """`list_reports` deliberately did not gain the clause.

    A maintainer browsing the map is a hiker, and every unmoderated report on
    the trail appearing as a pin for them is a different feature from the
    queue. The check is on the list, not on the photo, because the list is
    where the widening would have been silent.
    """
    _, report = _stored(
        client,
        db_session,
        r2,
        type=ReportType.bad_hikers,
        visibility=Visibility.internal_only,
    )
    moderator = _moderator(db_session)

    listed = client.get("/reports", headers=auth_headers(moderator.id))

    assert listed.status_code == 200
    assert report.id not in {row["id"] for row in listed.json()}


# --- `GET /{id}/photo/link`: the same photo, as a URL ----------------------


def test_the_link_is_the_same_signed_url_the_redirect_would_have_sent(client, db_session, r2):
    """Two spellings, one capability - not a second way of authorising.

    Asserting the key and the signature rather than string equality, because
    two presigns a second apart differ in `X-Amz-Date` and comparing them
    whole would be testing the clock.
    """
    _, report = _stored(client, db_session, r2, status=ReportStatus.verified)

    body = _link(client, report.id).json()

    assert photo_key(report.id) in body["url"]
    assert "X-Amz-Signature" in body["url"]
    assert f"X-Amz-Expires={PHOTO_URL_TTL_SECONDS}" in body["url"]


def test_the_link_really_fetches_the_photo(client, db_session, r2):
    """The one case that follows the URL all the way to the bytes.

    Everything else asserts its shape, which would keep passing if the
    signature were wrong. An `<img src>` pointed at a URL that does not
    resolve is the broken image #385 is about.
    """
    _, report = _stored(client, db_session, r2, status=ReportStatus.verified)

    fetched = requests.get(_link(client, report.id).json()["url"], timeout=10)

    assert fetched.status_code == 200
    assert fetched.content == _JPEG


def test_the_link_says_how_long_it_is_good_for(client, db_session, r2):
    """So a screen holding one open re-asks on the server's number.

    The alternative to re-asking is a longer TTL, which app/core/photos.py
    records as a decision rather than a knob.
    """
    _, report = _stored(client, db_session, r2, status=ReportStatus.verified)

    assert _link(client, report.id).json()["expires_in"] == PHOTO_URL_TTL_SECONDS


def test_the_link_is_never_cached(client, db_session, r2):
    """It matters more here than on the redirect: this response BODY is the
    bearer token, where the redirect at least kept it in a header. A cache
    holding it outlives the signature and the visibility decision both."""
    _, report = _stored(client, db_session, r2, status=ReportStatus.verified)

    assert "no-store" in _link(client, report.id).headers["cache-control"]


def test_the_link_does_not_hand_back_the_stored_key(client, db_session, r2):
    """`photo_url` is client-supplied text on `POST /reports`.

    Repeating it in this body would invite a client to build its own URL from
    it, and the signed URL is the only spelling that was authorised. The
    queue already carries the key for anything that needs to know a photo
    exists.
    """
    _, report = _stored(client, db_session, r2, status=ReportStatus.verified)

    assert set(_link(client, report.id).json()) == {"url", "expires_in"}


def test_the_link_refuses_exactly_what_the_redirect_refuses(client, db_session, r2):
    """One check behind both, so they cannot answer differently.

    A link endpoint with its own copy of `_visible_to` is the drift
    app/core/photos.py refused a Cloudflare Worker over, one layer in.
    """
    _, unmoderated = _stored(client, db_session, r2)  # left `submitted`
    stranger = _reporter(db_session)
    no_photo = _report(db_session, stranger, status=ReportStatus.verified)

    assert _link(client, unmoderated.id).status_code == 404
    assert _link(client, unmoderated.id, stranger.id).status_code == 404
    assert _link(client, no_photo.id, stranger.id).status_code == 404
    assert _link(client, str(uuid.uuid4())).status_code == 404


def test_the_link_needs_no_account_for_a_public_photo(client, db_session, r2):
    """Browsing needs no account here either. The link form exists because an
    `<img>` cannot authenticate - not because it always must."""
    _, report = _stored(client, db_session, r2, status=ReportStatus.verified)

    assert _link(client, report.id).status_code == 200


def test_the_link_says_so_rather_than_404ing_when_no_bucket_is_configured(client, db_session):
    """503, and specifically not 404 - the same distinction the redirect
    makes. Note the absent `r2` fixture: this is every developer machine."""
    reporter = _reporter(db_session)
    report = _report(db_session, reporter, status=ReportStatus.verified, photo_url="reports/x/1.jpg")

    assert _link(client, report.id, reporter.id).status_code == 503


def test_a_photo_bucket_pointed_at_the_published_one_refuses_to_start(monkeypatch):
    """The half the separate names cannot cover: a deliberate wrong paste.

    `R2_PHOTO_` stops the publishing variables from configuring this backend by
    accident. It cannot stop somebody typing the published bucket's name into
    `R2_PHOTO_BUCKET`, and the outcome is identical - a `bad_hikers` photo is a
    photo of a person, and that bucket answers anybody.

    #395 names misconfiguration as the largest realistic risk in the system and
    asks for an alarm on it. Refusing to construct is the loudest one available:
    the process that should not be able to do this cannot, rather than merely
    being unlikely to.
    """
    monkeypatch.setenv("R2_BUCKET", "your-hike")
    monkeypatch.setenv("R2_PHOTO_BUCKET", "your-hike")

    with pytest.raises(ValidationError) as caught:
        Settings()

    message = str(caught.value)
    assert "published" in message
    assert "LAUNCH_CHECKLIST.md 1.7" in message


def test_the_collision_is_refused_when_it_arrives_through_a_dot_env_file(monkeypatch, tmp_path):
    """The bypass #649 demonstrated. pydantic-settings loads `backend/.env` -
    the gitignored channel the config module's own header sanctions - WITHOUT
    exporting it to os.environ, and the guard used to ask os.environ alone. So
    a developer keeping both variable sets in `.env`, with the photo bucket
    pasted wrong, started cleanly into the exact state the guard exists to
    refuse. The guard now reads the publishing names from every channel its
    own fields arrive by."""
    monkeypatch.delenv("R2_BUCKET", raising=False)
    monkeypatch.delenv("R2_PHOTO_BUCKET", raising=False)
    (tmp_path / ".env").write_text("R2_BUCKET=your-hike\nR2_PHOTO_BUCKET=your-hike\n")
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ValidationError) as caught:
        Settings()

    assert "LAUNCH_CHECKLIST.md 1.7" in str(caught.value)


def test_a_photo_token_that_is_the_publishing_token_refuses_to_start(monkeypatch):
    """A token scoped to the published bucket is wrong here whichever way it
    fails. Either it cannot write to the photo bucket - so every upload 503s
    for a reason nobody can see from the outside - or it is broader than
    LAUNCH_CHECKLIST.md 1.2 says and can write to the public one."""
    monkeypatch.setenv("R2_ACCESS_KEY_ID", "publishing-key")
    monkeypatch.setenv("R2_PHOTO_BUCKET", "your-hike-photos")
    monkeypatch.setenv("R2_PHOTO_ACCESS_KEY_ID", "publishing-key")

    with pytest.raises(ValidationError):
        Settings()


def test_a_correctly_separated_deployment_is_silent(monkeypatch):
    """The guard must not fire on the arrangement LAUNCH_CHECKLIST.md 1.7
    actually asks for - two buckets, two tokens, both sets present because one
    host happens to carry both."""
    monkeypatch.setenv("R2_BUCKET", "your-hike")
    monkeypatch.setenv("R2_ACCESS_KEY_ID", "publishing-key")
    monkeypatch.setenv("R2_PHOTO_BUCKET", "your-hike-photos")
    monkeypatch.setenv("R2_PHOTO_ACCESS_KEY_ID", "photo-key")

    fresh = Settings()

    assert fresh.r2_photo_bucket == "your-hike-photos"


def test_the_guard_stays_quiet_where_there_is_nothing_to_collide_with(monkeypatch, tmp_path):
    """Every developer machine and every CI run: photo variables set, no
    publishing variables in the environment or in a `.env`. Nothing to compare
    against, so nothing to say.

    Quiet is not a safety proof, and this test's name should not be read as
    one (#649): a backend-only host where someone pastes the published
    bucket's NAME with no publishing variables anywhere looks exactly like
    this from inside the process. That case has no in-process check - it is
    what LAUNCH_CHECKLIST.md 1.7's separate bucket and scoped token exist to
    prevent. What this asserts is only that the guard does not cry wolf on
    the correct arrangement."""
    monkeypatch.delenv("R2_BUCKET", raising=False)
    monkeypatch.delenv("R2_ACCESS_KEY_ID", raising=False)
    monkeypatch.setenv("R2_PHOTO_BUCKET", "your-hike-photos")
    # An empty directory, so a stray developer .env cannot decide this test.
    monkeypatch.chdir(tmp_path)

    assert Settings().r2_photo_bucket == "your-hike-photos"
