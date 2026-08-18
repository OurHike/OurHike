"""The moderation trail answers all three questions, not one (#658).

Who first escalated (preserved across re-verification), who removed
(recorded at all - it never was), and who declared a hazard fixed (a state
the vocabulary held open and no endpoint could reach). Plus the audience
fix: the audit trail exists FOR moderators, and closures withheld it from
them too.
"""

import uuid

from app.models.closure import ModerationStatus
from app.models.profile import Role
from app.models.report import Report, ReportStatus, ReportType, Visibility
from tests.factories import make_closure, make_profile
from tests.tokens import auth_headers


def _moderator(db_session):
    return make_profile(db_session, Role.maintainer).id


def _report(db_session, **fields):
    reporter = make_profile(db_session, Role.hiker)
    report = Report(
        reporter_id=reporter.id,
        type=ReportType.blowdown,
        reporter_type="day",
        visibility=Visibility.public,
        **fields,
    )
    db_session.add(report)
    db_session.commit()
    return report


def test_dismissal_finally_records_who_and_when(client, db_session):
    report = _report(db_session)
    moderator = _moderator(db_session)

    response = client.post(f"/reports/{report.id}/dismiss", headers=auth_headers(moderator))

    assert response.status_code == 200
    db_session.refresh(report)
    assert report.dismissed_by == moderator
    assert report.dismissed_at is not None


def test_reverification_never_overwrites_the_first_escalator(client, db_session):
    """Who FIRST marked a dangerous-person report serious is the fact an
    audit needs, and a re-verify used to replace it with whoever touched
    the row last."""
    report = _report(db_session)
    first = _moderator(db_session)
    second = _moderator(db_session)

    client.post(f"/reports/{report.id}/verify", json={}, headers=auth_headers(first))
    db_session.refresh(report)
    first_stamp = report.verified_at

    client.post(f"/reports/{report.id}/verify", json={}, headers=auth_headers(second))
    db_session.refresh(report)

    assert report.verified_by == first
    assert report.verified_at == first_stamp


def test_a_closure_reverification_preserves_the_first_verifier_too(client, db_session):
    closure = make_closure(db_session, make_profile(db_session).id)
    first = _moderator(db_session)
    second = _moderator(db_session)

    client.post(f"/closures/{closure.id}/verify", headers=auth_headers(first))
    client.post(f"/closures/{closure.id}/verify", headers=auth_headers(second))

    db_session.refresh(closure)
    assert closure.verified_by == first


def test_a_verified_report_can_be_resolved_and_the_resolver_is_recorded(client, db_session):
    report = _report(db_session)
    verifier = _moderator(db_session)
    resolver = _moderator(db_session)
    client.post(f"/reports/{report.id}/verify", json={}, headers=auth_headers(verifier))

    response = client.post(f"/reports/{report.id}/resolve", headers=auth_headers(resolver))

    assert response.status_code == 200
    assert response.json()["status"] == ReportStatus.resolved.value
    db_session.refresh(report)
    assert report.resolved_by == resolver
    assert report.resolved_at is not None
    assert report.verified_by == verifier, "resolving must not disturb the escalation record"


def test_a_resolved_report_still_reads_as_fixed_to_the_public(client, db_session):
    """The whole point of resolved over dismissed: it was real, and someone
    fixed it - so it stays in the public list where dismissal removes."""
    report = _report(db_session)
    moderator = _moderator(db_session)
    client.post(f"/reports/{report.id}/verify", json={}, headers=auth_headers(moderator))
    client.post(f"/reports/{report.id}/resolve", headers=auth_headers(moderator))

    anonymous = client.get("/reports")

    listed = {r["id"]: r for r in anonymous.json()}
    assert report.id in listed
    assert listed[report.id]["status"] == ReportStatus.resolved.value


def test_resolving_an_unverified_report_is_refused(client, db_session):
    """"Fixed" implies "was real", and only verify says that - resolving a
    submitted report would skip the moderation gate."""
    report = _report(db_session)
    moderator = _moderator(db_session)

    response = client.post(f"/reports/{report.id}/resolve", headers=auth_headers(moderator))

    assert response.status_code == 409


def test_resolving_a_dismissed_report_is_refused(client, db_session):
    report = _report(db_session)
    moderator = _moderator(db_session)
    client.post(f"/reports/{report.id}/dismiss", headers=auth_headers(moderator))

    response = client.post(f"/reports/{report.id}/resolve", headers=auth_headers(moderator))

    assert response.status_code == 409


def test_resolving_twice_is_a_no_op_200_not_an_error(client, db_session):
    report = _report(db_session)
    first = _moderator(db_session)
    second = _moderator(db_session)
    client.post(f"/reports/{report.id}/verify", json={}, headers=auth_headers(first))
    client.post(f"/reports/{report.id}/resolve", headers=auth_headers(first))

    again = client.post(f"/reports/{report.id}/resolve", headers=auth_headers(second))

    assert again.status_code == 200
    db_session.refresh(report)
    assert report.resolved_by == first, "a retry records nothing new"


def test_verifying_a_resolved_report_is_refused(client, db_session):
    """Re-verifying would quietly re-open a hazard the record says is
    cleared; a recurrence is a new report."""
    report = _report(db_session)
    moderator = _moderator(db_session)
    client.post(f"/reports/{report.id}/verify", json={}, headers=auth_headers(moderator))
    client.post(f"/reports/{report.id}/resolve", headers=auth_headers(moderator))

    response = client.post(f"/reports/{report.id}/verify", json={}, headers=auth_headers(moderator))

    assert response.status_code == 409


def test_moderators_see_the_closure_audit_trail_the_public_does_not(client, db_session):
    """ClosureOut's docstring promised the identity fields "only stop being
    handed to anonymous HTTP callers"; until #658 the moderation surface was
    refused them too."""
    reporter = make_profile(db_session)
    closure = make_closure(db_session, reporter.id)
    moderator = _moderator(db_session)

    verified = client.post(f"/closures/{closure.id}/verify", headers=auth_headers(moderator))
    assert verified.status_code == 200
    body = verified.json()
    assert body["reported_by"] == reporter.id
    assert body["verified_by"] == moderator

    public = client.get("/closures")
    assert public.status_code == 200
    for row in public.json():
        assert "reported_by" not in row
        assert "verified_by" not in row


def test_the_dismissing_moderator_shows_in_the_closure_answer(client, db_session):
    closure = make_closure(db_session, make_profile(db_session).id)
    moderator = _moderator(db_session)

    response = client.post(f"/closures/{closure.id}/dismiss", headers=auth_headers(moderator))

    assert response.status_code == 200
    assert response.json()["dismissed_by"] == moderator
    db_session.refresh(closure)
    assert closure.moderation_status is ModerationStatus.dismissed


def test_resolve_requires_a_moderator_role(client, db_session):
    report = _report(db_session)
    hiker = str(uuid.uuid4())

    response = client.post(f"/reports/{report.id}/resolve", headers=auth_headers(hiker))

    assert response.status_code == 403
