"""Tests for the moderation-queue actions: verify/dismiss for both Report
and Closure.

See ../../features/HIKER_SAFETY.md §1. Escalating a report to
`severity=serious` happens *during the same verification action* already in
Report a Problem's flow ("the same review step, not a second one" -
HIKER_SAFETY.md's own text) - there is no separate corroboration-count
mechanism to build; a moderator's own judgment, exercised through this one
action, is the entire mechanism.
"""

import uuid
from datetime import datetime, timedelta, timezone

import jwt

from app.config import settings
from app.models.closure import Closure, ModerationStatus
from app.models.profile import Profile, Role
from app.models.report import Report, ReportStatus, ReportType, Severity, Visibility

TEST_SECRET = settings.supabase_jwt_secret


def _make_token(user_id: str) -> str:
    payload = {"sub": user_id, "exp": datetime.now(timezone.utc) + timedelta(hours=1)}
    return jwt.encode(payload, TEST_SECRET, algorithm="HS256")


def _auth_headers(user_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {_make_token(user_id)}"}


def _make_reporter_and_report(db_session, report_type=ReportType.blowdown):
    reporter = Profile(id=str(uuid.uuid4()), role=Role.hiker)
    db_session.add(reporter)
    db_session.commit()
    # visibility has no column default by design (app/models/report.py: "the
    # router always computes and sets this explicitly") - set it explicitly
    # here too, the same way create_report does, rather than relying on one.
    visibility = Visibility.internal_only if report_type == ReportType.bad_hikers else Visibility.public
    report = Report(reporter_id=reporter.id, type=report_type, reporter_type="thru", visibility=visibility)
    db_session.add(report)
    db_session.commit()
    return reporter, report


def _make_maintainer(db_session):
    maintainer_id = str(uuid.uuid4())
    maintainer = Profile(id=maintainer_id, role=Role.maintainer)
    db_session.add(maintainer)
    db_session.commit()
    return maintainer_id


def test_verify_report_rejects_a_plain_hiker_role_with_403(client, db_session):
    _reporter, report = _make_reporter_and_report(db_session)
    hiker_id = str(uuid.uuid4())

    response = client.post(f"/reports/{report.id}/verify", json={}, headers=_auth_headers(hiker_id))

    assert response.status_code == 403


def test_verify_report_can_set_severity_serious_in_the_same_action(client, db_session):
    _reporter, report = _make_reporter_and_report(db_session, report_type=ReportType.bad_hikers)
    maintainer_id = _make_maintainer(db_session)

    response = client.post(
        f"/reports/{report.id}/verify",
        json={"severity": "serious"},
        headers=_auth_headers(maintainer_id),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "verified"
    assert body["severity"] == "serious"


def test_verify_report_defaults_severity_to_normal_when_omitted(client, db_session):
    _reporter, report = _make_reporter_and_report(db_session)
    maintainer_id = _make_maintainer(db_session)

    response = client.post(f"/reports/{report.id}/verify", json={}, headers=_auth_headers(maintainer_id))

    assert response.status_code == 200
    assert response.json()["severity"] == "normal"


def test_a_reporter_cannot_self_declare_their_own_report_serious(client):
    # Confirmed at the schema level, not just the router: ReportCreate has
    # no severity field at all, so a client sending one has zero effect -
    # cross-checked against test_create_report_ignores_a_client_supplied_severity_field
    # in test_routers_reports.py, which asserts the same invariant through
    # the create endpoint directly.
    from app.schemas.report import ReportCreate

    assert "severity" not in ReportCreate.model_fields


def test_dismiss_report_requires_maintainer_or_club_admin_role(client, db_session):
    _reporter, report = _make_reporter_and_report(db_session)
    hiker_id = str(uuid.uuid4())
    maintainer_id = _make_maintainer(db_session)

    denied = client.post(f"/reports/{report.id}/dismiss", headers=_auth_headers(hiker_id))
    allowed = client.post(f"/reports/{report.id}/dismiss", headers=_auth_headers(maintainer_id))

    assert denied.status_code == 403
    assert allowed.status_code == 200
    assert allowed.json()["status"] == ReportStatus.dismissed.value


def test_verify_closure_sets_verified_by_and_verified_at(client, db_session):
    reporter = Profile(id=str(uuid.uuid4()), role=Role.hiker)
    db_session.add(reporter)
    db_session.commit()
    closure = Closure(
        reported_by=reporter.id,
        reason_type="storm_damage",
        start_mile_marker=1.0,
        end_mile_marker=2.0,
    )
    db_session.add(closure)
    db_session.commit()
    maintainer_id = _make_maintainer(db_session)

    response = client.post(f"/closures/{closure.id}/verify", headers=_auth_headers(maintainer_id))

    assert response.status_code == 200
    body = response.json()
    assert body["moderation_status"] == ModerationStatus.verified.value
    assert body["verified_by"] == maintainer_id
    assert body["verified_at"] is not None


def test_dismiss_closure_requires_maintainer_or_club_admin_role(client, db_session):
    reporter = Profile(id=str(uuid.uuid4()), role=Role.hiker)
    db_session.add(reporter)
    db_session.commit()
    closure = Closure(
        reported_by=reporter.id,
        reason_type="storm_damage",
        start_mile_marker=1.0,
        end_mile_marker=2.0,
    )
    db_session.add(closure)
    db_session.commit()
    hiker_id = str(uuid.uuid4())
    maintainer_id = _make_maintainer(db_session)

    denied = client.post(f"/closures/{closure.id}/dismiss", headers=_auth_headers(hiker_id))
    allowed = client.post(f"/closures/{closure.id}/dismiss", headers=_auth_headers(maintainer_id))

    assert denied.status_code == 403
    assert allowed.status_code == 200
    assert allowed.json()["moderation_status"] == ModerationStatus.dismissed.value


def test_verify_report_that_does_not_exist_returns_404(client, db_session):
    maintainer_id = _make_maintainer(db_session)

    response = client.post(f"/reports/{uuid.uuid4()}/verify", json={}, headers=_auth_headers(maintainer_id))

    assert response.status_code == 404


def test_severity_data_default_is_normal(db_session):
    reporter = Profile(id=str(uuid.uuid4()), role=Role.hiker)
    db_session.add(reporter)
    db_session.commit()
    report = Report(reporter_id=reporter.id, type=ReportType.trash, reporter_type="day", visibility=Visibility.public)
    db_session.add(report)
    db_session.commit()

    assert report.severity == Severity.normal
