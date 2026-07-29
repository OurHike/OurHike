"""Tests for the `/reports` router - community condition reports.

See ../../features/REPORT_A_PROBLEM.md for the feature this mirrors. The
two server-controlled fields (`visibility`, `severity`) and the
server-authored `timestamp` are the load-bearing behaviors here - none of
them can be set or overridden by whatever a client sends in the request
body, only derived/assigned server-side.
"""

import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.config import settings
from app.models.profile import Profile, Role
from app.models.report import Report, ReporterType, ReportStatus, ReportType, Visibility

TEST_SECRET = settings.supabase_jwt_secret


def _make_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    return jwt.encode(payload, TEST_SECRET, algorithm="HS256")


def _auth_headers(user_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {_make_token(user_id)}"}


_VALID_PAYLOAD = {
    "type": "blowdown",
    "reporter_type": "thru",
    "lat": 35.6,
    "lon": -83.5,
    "note": "Large tree across the trail near the gap.",
}


def test_create_report_requires_authentication(client):
    response = client.post("/reports", json=_VALID_PAYLOAD)

    assert response.status_code == 401


def test_create_report_persists_the_authoring_timestamp_not_the_request_time(client):
    user_id = str(uuid.uuid4())
    # A client-supplied timestamp is not a field ReportCreate declares, so
    # it should be silently dropped, not applied - assert the server's own
    # clock won regardless.
    payload = dict(_VALID_PAYLOAD, timestamp="1999-01-01T00:00:00Z")

    before = datetime.now(timezone.utc)
    response = client.post("/reports", json=payload, headers=_auth_headers(user_id))
    after = datetime.now(timezone.utc)

    assert response.status_code == 201
    body = response.json()
    stored_timestamp = datetime.fromisoformat(body["timestamp"]).replace(tzinfo=timezone.utc)

    assert stored_timestamp.year != 1999
    assert before - timedelta(seconds=5) <= stored_timestamp <= after + timedelta(seconds=5)


def test_create_report_defaults_bad_hikers_type_to_internal_only_visibility(client):
    user_id = str(uuid.uuid4())
    payload = dict(_VALID_PAYLOAD, type="bad_hikers")

    response = client.post("/reports", json=payload, headers=_auth_headers(user_id))

    assert response.status_code == 201
    assert response.json()["visibility"] == "internal_only"


@pytest.mark.parametrize("report_type", ["blowdown", "trash", "flooding", "shelter_repair", "animals"])
def test_create_report_defaults_the_other_five_types_to_public_visibility(client, report_type):
    user_id = str(uuid.uuid4())
    payload = dict(_VALID_PAYLOAD, type=report_type)

    response = client.post("/reports", json=payload, headers=_auth_headers(user_id))

    assert response.status_code == 201
    assert response.json()["visibility"] == "public"


def test_create_report_ignores_a_client_supplied_severity_field(client):
    user_id = str(uuid.uuid4())
    payload = dict(_VALID_PAYLOAD, severity="serious")

    response = client.post("/reports", json=payload, headers=_auth_headers(user_id))

    assert response.status_code == 201
    assert response.json()["severity"] == "normal"


def test_public_list_reports_excludes_internal_only_reports(client, db_session):
    reporter = Profile(id=str(uuid.uuid4()), role=Role.hiker)
    db_session.add(reporter)
    db_session.commit()

    public_report = Report(
        reporter_id=reporter.id,
        type=ReportType.trash,
        reporter_type=ReporterType.day,
        visibility=Visibility.public,
    )
    internal_report = Report(
        reporter_id=reporter.id,
        type=ReportType.bad_hikers,
        reporter_type=ReporterType.day,
        visibility=Visibility.internal_only,
    )
    db_session.add_all([public_report, internal_report])
    db_session.commit()

    response = client.get("/reports")

    assert response.status_code == 200
    ids = [r["id"] for r in response.json()]
    assert public_report.id in ids
    assert internal_report.id not in ids


def test_public_list_reports_excludes_dismissed_reports(client, db_session):
    reporter = Profile(id=str(uuid.uuid4()), role=Role.hiker)
    db_session.add(reporter)
    db_session.commit()

    active_report = Report(
        reporter_id=reporter.id,
        type=ReportType.flooding,
        reporter_type=ReporterType.section,
        visibility=Visibility.public,
        status=ReportStatus.submitted,
    )
    dismissed_report = Report(
        reporter_id=reporter.id,
        type=ReportType.flooding,
        reporter_type=ReporterType.section,
        visibility=Visibility.public,
        status=ReportStatus.dismissed,
    )
    db_session.add_all([active_report, dismissed_report])
    db_session.commit()

    response = client.get("/reports")

    assert response.status_code == 200
    ids = [r["id"] for r in response.json()]
    assert active_report.id in ids
    assert dismissed_report.id not in ids


def test_reporter_can_view_their_own_internal_only_report(client, db_session):
    user_id = str(uuid.uuid4())
    reporter = Profile(id=user_id, role=Role.hiker)
    db_session.add(reporter)
    db_session.commit()

    internal_report = Report(
        reporter_id=reporter.id,
        type=ReportType.bad_hikers,
        reporter_type=ReporterType.thru,
        visibility=Visibility.internal_only,
    )
    db_session.add(internal_report)
    db_session.commit()

    anonymous_response = client.get(f"/reports/{internal_report.id}")
    owner_response = client.get(f"/reports/{internal_report.id}", headers=_auth_headers(user_id))

    assert anonymous_response.status_code == 404
    assert owner_response.status_code == 200
    assert owner_response.json()["id"] == internal_report.id


def test_list_reports_requires_no_authentication(client):
    response = client.get("/reports")

    assert response.status_code == 200
