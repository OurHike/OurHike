"""Several photos on one report, and a place named in words (#1439).

A blowdown is three trunks and one photo rarely shows it, so a report holds a
set rather than a photo. What is under test here is the three properties that
set has to keep, all of which the single-photo endpoint got for free and none
of which survive being extended carelessly:

  - **The keys stay derived.** `reports/{id}/{n}.jpg`, so which objects belong
    to a report is still answerable from the id alone (app/core/photos.py), and
    the only thing the row supplies is how far the numbering runs.
  - **The sequence is dense.** A `photo_count` of four with nothing at index 3
    would be the row describing a set the bucket does not hold, in the one
    direction this design refuses.
  - **A retry is not an append.** The outbox re-sends photo 2 as photo 2, on a
    trail where a request that commits and whose response never arrives is the
    normal case rather than the edge one.

And the location half: a report with no fix and no waypoint carries the
hiker's own words for where it was, with `lat`, `lon` and `mile` still
omitted. Nothing geocodes it, here or anywhere - a typed name turned into
coordinates is a confident wrong dot on every phone that downloads it.

The S3 double and the fixtures are tests/test_report_photos.py's, imported
rather than copied so the two files cannot come to configure different buckets.
"""

import uuid

import pytest

from app.core.photos import MAX_REPORT_PHOTOS, photo_key
from app.models.report import Report, ReporterType, ReportStatus, ReportType, Visibility
from tests.factories import make_profile
from tests.test_report_photos import _BUCKET, _JPEG, r2  # noqa: F401 - fixture
from tests.tokens import auth_headers


def _reporter(db_session):
    return make_profile(db_session)


def _report(db_session, reporter, **kwargs) -> Report:
    report = Report(
        id=str(uuid.uuid4()),
        reporter_id=reporter.id,
        type=kwargs.pop("type", ReportType.blowdown),
        reporter_type=ReporterType.thru,
        lat=35.6,
        lon=-83.5,
        status=kwargs.pop("status", ReportStatus.submitted),
        visibility=kwargs.pop("visibility", Visibility.public),
        **kwargs,
    )
    db_session.add(report)
    db_session.commit()
    return report


def _put(client, report_id: str, index: int, reporter_id: str, body: bytes = _JPEG):
    return client.put(
        f"/reports/{report_id}/photos/{index}",
        content=body,
        headers={**auth_headers(reporter_id), "content-type": "image/jpeg"},
    )


# --- The set ---------------------------------------------------------------


def test_a_second_photo_lands_beside_the_first(client, db_session, r2):  # noqa: F811
    reporter = _reporter(db_session)
    report = _report(db_session, reporter)

    _put(client, report.id, 1, reporter.id)
    response = _put(client, report.id, 2, reporter.id, _JPEG + b"the second trunk")

    assert response.status_code == 200
    assert response.json()["photo_count"] == 2
    keys = sorted(o["Key"] for o in r2.list_objects_v2(Bucket=_BUCKET)["Contents"])
    assert keys == [photo_key(report.id, 1), photo_key(report.id, 2)]
    assert r2.get_object(Bucket=_BUCKET, Key=photo_key(report.id, 2))["Body"].read().endswith(b"the second trunk")


def test_photo_url_keeps_naming_the_first_of_the_set(client, db_session, r2):  # noqa: F811
    """The invariant `_record_photo` holds while both columns exist.

    RELEASING.md §8c: a column dropped in the same release that stops being
    written breaks the previous release, which is still running during the
    rollout. So `photo_url` is photo 1's key exactly when the count is at
    least 1, and a later revision contracts.
    """
    reporter = _reporter(db_session)
    report = _report(db_session, reporter)

    _put(client, report.id, 1, reporter.id)
    body = _put(client, report.id, 2, reporter.id).json()

    assert body["photo_url"] == photo_key(report.id, 1)
    assert body["photo_count"] == 2


def test_resending_a_photo_replaces_it_rather_than_appending(client, db_session, r2):  # noqa: F811
    """The offline case, which out here is the normal one."""
    reporter = _reporter(db_session)
    report = _report(db_session, reporter)

    _put(client, report.id, 1, reporter.id)
    _put(client, report.id, 2, reporter.id)
    response = _put(client, report.id, 2, reporter.id, _JPEG + b"sent again")

    assert response.json()["photo_count"] == 2
    assert r2.list_objects_v2(Bucket=_BUCKET, Prefix=f"reports/{report.id}/")["KeyCount"] == 2
    assert r2.get_object(Bucket=_BUCKET, Key=photo_key(report.id, 2))["Body"].read().endswith(b"sent again")


def test_refuses_an_index_that_would_leave_a_hole(client, db_session, r2):  # noqa: F811
    """A count of three with nothing at index 2 is the row describing a set
    the bucket does not hold - and the count is the only thing that says how
    far to read."""
    reporter = _reporter(db_session)
    report = _report(db_session, reporter)
    _put(client, report.id, 1, reporter.id)

    response = _put(client, report.id, 3, reporter.id)

    assert response.status_code == 409
    db_session.refresh(report)
    assert report.photo_count == 1
    assert r2.list_objects_v2(Bucket=_BUCKET, Prefix=f"reports/{report.id}/")["KeyCount"] == 1


def test_refuses_more_than_the_cap(client, db_session, r2):  # noqa: F811
    reporter = _reporter(db_session)
    report = _report(db_session, reporter)
    for index in range(1, MAX_REPORT_PHOTOS + 1):
        assert _put(client, report.id, index, reporter.id).status_code == 200

    response = _put(client, report.id, MAX_REPORT_PHOTOS + 1, reporter.id)

    assert response.status_code == 409
    # The refusal says what the limit is rather than only that one was hit -
    # the form draws a sentence from this rather than greying its `+` tile.
    assert str(MAX_REPORT_PHOTOS) in response.json()["detail"]


def test_refuses_index_zero(client, db_session, r2):  # noqa: F811
    """Numbering starts at 1 (FIRST_PHOTO_INDEX), and `reports/{id}/0.jpg` is
    an object no reader would ever ask for."""
    reporter = _reporter(db_session)
    report = _report(db_session, reporter)

    assert _put(client, report.id, 0, reporter.id).status_code == 409
    assert r2.list_objects_v2(Bucket=_BUCKET).get("KeyCount", 0) == 0


def test_refuses_a_photo_for_somebody_elses_report(client, db_session, r2):  # noqa: F811
    reporter = _reporter(db_session)
    intruder = _reporter(db_session)
    report = _report(db_session, reporter)

    response = _put(client, report.id, 1, intruder.id)

    assert response.status_code == 404
    assert r2.list_objects_v2(Bucket=_BUCKET).get("KeyCount", 0) == 0


def test_the_single_photo_endpoint_still_writes_the_first(client, db_session, r2):  # noqa: F811
    """The previous release is still running during a rollout, and it PUTs
    `/photo`. That call has to keep meaning photo 1."""
    reporter = _reporter(db_session)
    report = _report(db_session, reporter)

    body = client.put(
        f"/reports/{report.id}/photo",
        content=_JPEG,
        headers={**auth_headers(reporter.id), "content-type": "image/jpeg"},
    ).json()

    assert body["photo_url"] == photo_key(report.id, 1)
    assert body["photo_count"] == 1


# --- Reading one back ------------------------------------------------------


def test_serves_each_photo_of_the_set(client, db_session, r2):  # noqa: F811
    reporter = _reporter(db_session)
    report = _report(db_session, reporter, status=ReportStatus.verified)
    _put(client, report.id, 1, reporter.id)
    _put(client, report.id, 2, reporter.id)

    for index in (1, 2):
        redirect = client.get(f"/reports/{report.id}/photos/{index}", follow_redirects=False)
        assert redirect.status_code == 302
        assert f"/{index}.jpg" in redirect.headers["location"]

        link = client.get(f"/reports/{report.id}/photos/{index}/link")
        assert link.status_code == 200
        assert f"/{index}.jpg" in link.json()["url"]
        # The body is a bearer capability, so it is never cached - the same
        # reasoning the single-photo link endpoint carries.
        assert "no-store" in link.headers["cache-control"]


def test_an_index_past_the_end_is_not_found(client, db_session, r2):  # noqa: F811
    reporter = _reporter(db_session)
    report = _report(db_session, reporter, status=ReportStatus.verified)
    _put(client, report.id, 1, reporter.id)

    assert client.get(f"/reports/{report.id}/photos/2", follow_redirects=False).status_code == 404
    assert client.get(f"/reports/{report.id}/photos/2/link").status_code == 404


def test_every_photo_of_a_report_has_the_reports_audience(client, db_session, r2):  # noqa: F811
    """The fourth photo on a `bad_hikers` report is as much a photo of a
    person as the first, and 404 uniformly - a distinct 403 would confirm to a
    stranger that an incident note about a named individual exists."""
    reporter = _reporter(db_session)
    report = _report(
        db_session,
        reporter,
        type=ReportType.bad_hikers,
        visibility=Visibility.internal_only,
        status=ReportStatus.verified,
    )
    _put(client, report.id, 1, reporter.id)
    _put(client, report.id, 2, reporter.id)

    for index in (1, 2):
        assert client.get(f"/reports/{report.id}/photos/{index}", follow_redirects=False).status_code == 404
        assert client.get(f"/reports/{report.id}/photos/{index}/link").status_code == 404
        # …and the owner still sees their own.
        owned = client.get(
            f"/reports/{report.id}/photos/{index}/link",
            headers=auth_headers(reporter.id),
        )
        assert owned.status_code == 200


# --- A place in words ------------------------------------------------------


@pytest.mark.parametrize("reading", ["create", "read back"])
def test_a_report_with_no_fix_carries_the_hikers_own_words(client, db_session, reading):
    """D16's third state: no GPS fix and no waypoint, so the only thing that
    can say where this was is the hiker.

    The assertion that matters is the pair - the words are stored AND the
    coordinates stay absent. A backend that helpfully resolved the string
    would put a confident wrong dot on every phone that downloads the report,
    which is exactly what the omitted-not-zeroed rule exists to prevent.
    """
    reporter = _reporter(db_session)
    words = "The brook crossing about half a mile north of Fitzgerald Falls"

    created = client.post(
        "/reports",
        json={
            "type": "blowdown",
            "reporter_type": "thru",
            "note": "Three big pines down.",
            "place_words": words,
        },
        headers=auth_headers(reporter.id),
    )
    assert created.status_code == 201, created.text
    body = created.json()
    if reading == "read back":
        body = client.get(f"/reports/{body['id']}", headers=auth_headers(reporter.id)).json()

    assert body["place_words"] == words
    assert body["lat"] is None
    assert body["lon"] is None
    assert body["mile"] is None


def test_a_report_with_no_words_says_nothing_rather_than_empty(client, db_session):
    """Absent, never "Unknown" and never a blank string standing in for one -
    the same rule every other omitted field on this row keeps."""
    reporter = _reporter(db_session)

    body = client.post(
        "/reports",
        json={"type": "trash", "reporter_type": "day", "lat": 41.2, "lon": -74.1},
        headers=auth_headers(reporter.id),
    ).json()

    assert body["place_words"] is None
    assert body["photo_count"] == 0
