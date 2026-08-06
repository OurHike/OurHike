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

from app.models.closure import Closure, ModerationStatus
from app.models.profile import Profile, Role
from app.models.report import Report, ReportStatus, ReportType, Severity, Visibility
from tests.tokens import auth_headers


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

    response = client.post(f"/reports/{report.id}/verify", json={}, headers=auth_headers(hiker_id))

    assert response.status_code == 403


def test_verify_report_can_set_severity_serious_in_the_same_action(client, db_session):
    _reporter, report = _make_reporter_and_report(db_session, report_type=ReportType.bad_hikers)
    maintainer_id = _make_maintainer(db_session)

    response = client.post(
        f"/reports/{report.id}/verify",
        json={"severity": "serious"},
        headers=auth_headers(maintainer_id),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "verified"
    assert body["severity"] == "serious"


def test_verify_report_defaults_severity_to_normal_when_omitted(client, db_session):
    _reporter, report = _make_reporter_and_report(db_session)
    maintainer_id = _make_maintainer(db_session)

    response = client.post(f"/reports/{report.id}/verify", json={}, headers=auth_headers(maintainer_id))

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

    denied = client.post(f"/reports/{report.id}/dismiss", headers=auth_headers(hiker_id))
    allowed = client.post(f"/reports/{report.id}/dismiss", headers=auth_headers(maintainer_id))

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

    response = client.post(f"/closures/{closure.id}/verify", headers=auth_headers(maintainer_id))

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

    denied = client.post(f"/closures/{closure.id}/dismiss", headers=auth_headers(hiker_id))
    allowed = client.post(f"/closures/{closure.id}/dismiss", headers=auth_headers(maintainer_id))

    assert denied.status_code == 403
    assert allowed.status_code == 200
    assert allowed.json()["moderation_status"] == ModerationStatus.dismissed.value


def test_verify_report_that_does_not_exist_returns_404(client, db_session):
    maintainer_id = _make_maintainer(db_session)

    response = client.post(f"/reports/{uuid.uuid4()}/verify", json={}, headers=auth_headers(maintainer_id))

    assert response.status_code == 404


def test_severity_data_default_is_normal(db_session):
    reporter = Profile(id=str(uuid.uuid4()), role=Role.hiker)
    db_session.add(reporter)
    db_session.commit()
    report = Report(reporter_id=reporter.id, type=ReportType.trash, reporter_type="day", visibility=Visibility.public)
    db_session.add(report)
    db_session.commit()

    assert report.severity == Severity.normal


# --- Reading the queue ---------------------------------------------------
#
# Everything above acts on an id. Nothing above returns one. Until
# GET /moderation/queue existed, the two list endpoints were both scoped to
# the public - /reports to what had already been moderated, /closures to
# `moderation_status == verified`, i.e. exactly the items already dealt with
# - so the queue could be acted on but not read.


def _make_closure(db_session, reporter_id, moderation_status=ModerationStatus.submitted):
    closure = Closure(
        reported_by=reporter_id,
        reason_type="storm_damage",
        start_mile_marker=1.0,
        end_mile_marker=2.0,
        moderation_status=moderation_status,
    )
    db_session.add(closure)
    db_session.commit()
    return closure


def test_moderation_queue_requires_a_moderator_role(client, db_session):
    _reporter, _report = _make_reporter_and_report(db_session)

    anonymous = client.get("/moderation/queue")
    hiker = client.get("/moderation/queue", headers=auth_headers(str(uuid.uuid4())))

    assert anonymous.status_code == 401
    assert hiker.status_code == 403


def test_moderation_queue_lists_submitted_reports_and_closures(client, db_session):
    reporter, report = _make_reporter_and_report(db_session)
    closure = _make_closure(db_session, reporter.id)
    maintainer_id = _make_maintainer(db_session)

    body = client.get("/moderation/queue", headers=auth_headers(maintainer_id)).json()

    assert [r["id"] for r in body["reports"]] == [report.id]
    assert [c["id"] for c in body["closures"]] == [closure.id]


def test_moderation_queue_shows_a_bad_hikers_report(client, db_session):
    """The whole point. `internal_only` appeared in exactly one query before
    this endpoint - the public list, which excludes it - so a report about
    being followed on trail could be filed and then read by nobody but its
    own author. REPORT_A_PROBLEM.md chose that visibility to mean "route it
    privately to club maintainers/moderators", and this is the route."""
    _reporter, report = _make_reporter_and_report(db_session, report_type=ReportType.bad_hikers)
    maintainer_id = _make_maintainer(db_session)

    body = client.get("/moderation/queue", headers=auth_headers(maintainer_id)).json()

    assert report.visibility == Visibility.internal_only
    assert [r["id"] for r in body["reports"]] == [report.id]


def test_moderation_queue_omits_a_thanks(client, db_session):
    """verify_report refuses a thanks with a 409 - gratitude has nothing to
    verify - so listing one here would put an item in the queue whose only
    available action is an error, in the queue closures and serious warnings
    share."""
    _reporter, thanks = _make_reporter_and_report(db_session, report_type=ReportType.thanks)
    maintainer_id = _make_maintainer(db_session)

    body = client.get("/moderation/queue", headers=auth_headers(maintainer_id)).json()

    assert thanks.id not in [r["id"] for r in body["reports"]]


def test_moderation_queue_drops_an_item_once_it_is_actioned(client, db_session):
    """A queue that still lists what was just verified is a queue nobody can
    work through."""
    _reporter, report = _make_reporter_and_report(db_session)
    closure = _make_closure(db_session, _reporter.id)
    maintainer_id = _make_maintainer(db_session)
    headers = auth_headers(maintainer_id)

    assert len(client.get("/moderation/queue", headers=headers).json()["reports"]) == 1

    client.post(f"/reports/{report.id}/verify", json={}, headers=headers)
    client.post(f"/closures/{closure.id}/dismiss", headers=headers)

    body = client.get("/moderation/queue", headers=headers).json()
    assert body["reports"] == []
    assert body["closures"] == []
