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

from app.models.closure import Closure, ClosureStatus, ModerationStatus
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


def test_verify_report_leaves_severity_alone_when_omitted(client, db_session):
    """A moderator saying nothing about severity is not a de-escalation.

    This test used to assert the opposite - `severity` defaulted to `normal`
    and was assigned unconditionally - which pinned the bug in place while
    the schema's own docstring described the correct behaviour (#251).
    """
    _reporter, report = _make_reporter_and_report(db_session)
    maintainer_id = _make_maintainer(db_session)

    response = client.post(f"/reports/{report.id}/verify", json={}, headers=auth_headers(maintainer_id))

    assert response.status_code == 200
    assert response.json()["severity"] == "normal"


def test_re_verifying_does_not_silently_un_escalate_a_serious_warning(client, db_session):
    """The bug, walked end to end.

    A `bad_hikers` report escalated to `serious` is what makes the 44px
    warning pin exist on every phone (features/HIKER_SAFETY.md §1,
    client/src/map/warningPin.ts). A second moderator re-verifying it with an
    empty body used to take that pin off the map, with no error and no
    record - and from a hiker's side, a warning vanishing looks exactly like
    a warning withdrawn on purpose.

    Two calls rather than one, because one call could never see it: the
    field only resets on a verify that follows a verify.
    """
    _reporter, report = _make_reporter_and_report(db_session, report_type=ReportType.bad_hikers)
    maintainer_id = _make_maintainer(db_session)

    escalated = client.post(
        f"/reports/{report.id}/verify",
        json={"severity": "serious"},
        headers=auth_headers(maintainer_id),
    )
    assert escalated.json()["severity"] == "serious"

    again = client.post(f"/reports/{report.id}/verify", json={}, headers=auth_headers(maintainer_id))

    assert again.status_code == 200
    assert again.json()["severity"] == "serious"


def test_a_moderator_can_still_de_escalate_by_saying_so(client, db_session):
    """`normal` sent explicitly is a decision, and it has to keep working.

    The fix distinguishes "omitted" from "explicitly normal"; it must not
    turn the second into a no-op, or a warning escalated in error would have
    no way back down.
    """
    _reporter, report = _make_reporter_and_report(db_session, report_type=ReportType.bad_hikers)
    maintainer_id = _make_maintainer(db_session)

    client.post(
        f"/reports/{report.id}/verify",
        json={"severity": "serious"},
        headers=auth_headers(maintainer_id),
    )
    response = client.post(
        f"/reports/{report.id}/verify",
        json={"severity": "normal"},
        headers=auth_headers(maintainer_id),
    )

    assert response.status_code == 200
    assert response.json()["severity"] == "normal"


def test_verify_report_records_who_did_it_and_when(client, db_session):
    """The audit trail closures have had all along.

    Read off the row rather than the response body: these are deliberately
    not on the public `ReportOut`, because a moderator's profile id has no
    business in the anonymous `GET /reports` payload (#252). Surfacing them
    to a moderator is the moderation surface's job (#235).
    """
    _reporter, report = _make_reporter_and_report(db_session, report_type=ReportType.bad_hikers)
    maintainer_id = _make_maintainer(db_session)

    response = client.post(
        f"/reports/{report.id}/verify",
        json={"severity": "serious"},
        headers=auth_headers(maintainer_id),
    )
    assert response.status_code == 200

    db_session.expire_all()
    stored = db_session.get(Report, report.id)
    assert stored.verified_by == maintainer_id
    assert stored.verified_at is not None


def test_an_unmoderated_report_has_no_verifier(client, db_session):
    """Null means nobody has looked at it - which is what `status` already
    says. These two answer WHO and WHEN, never WHETHER."""
    _reporter, report = _make_reporter_and_report(db_session)

    assert report.verified_by is None
    assert report.verified_at is None


def test_a_moderator_who_dismisses_a_report_is_not_recorded_as_verifying_it(client, db_session):
    """Dismissal is a different action and must not forge a verification.

    Worth asserting because the two sit next to each other in the same file
    and take the same role gate - copying the two lines across would be an
    easy and completely silent mistake.
    """
    _reporter, report = _make_reporter_and_report(db_session)
    maintainer_id = _make_maintainer(db_session)

    client.post(f"/reports/{report.id}/dismiss", headers=auth_headers(maintainer_id))

    db_session.expire_all()
    stored = db_session.get(Report, report.id)
    assert stored.status == ReportStatus.dismissed
    assert stored.verified_by is None


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


def _submitted_closure(db_session):
    """An unmoderated closure and a maintainer who can act on it."""
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
    return closure, _make_maintainer(db_session)


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
    assert body["verified_at"] is not None

    # Who verified it is stamped on the ROW, and read back from the row - it
    # left the response with #430. Asserting it here rather than on `body` is
    # the point: the audit trail has to survive the field being taken off the
    # wire, and this is what would notice if it stopped being written at all.
    db_session.expire_all()
    stored = db_session.get(Closure, closure.id)
    assert stored.verified_by == maintainer_id
    assert stored.verified_at is not None


def test_verify_closure_leaves_the_status_alone_when_no_body_is_sent(client, db_session):
    """The ordinary case, and the one that has to need no thought.

    A closure is born `closed` (#246), so "yes, this is real" is the whole of
    verifying one. The band and the banner appear because the record was
    already true - not because this call repaired it.
    """
    closure, maintainer_id = _submitted_closure(db_session)

    response = client.post(f"/closures/{closure.id}/verify", headers=auth_headers(maintainer_id))

    assert response.status_code == 200
    assert response.json()["status"] == ClosureStatus.closed.value


def test_verify_closure_can_settle_a_reroute_in_the_same_call(client, db_session):
    """The one judgment that genuinely belongs at the moment of verifying.

    Without this a moderator who has confirmed both that the trail is shut
    and that there is a marked way round has to follow up with a separate
    `PATCH /closures/{id}` that nothing in the flow tells them about - which
    is the same trap #246 was, one size smaller.
    """
    closure, maintainer_id = _submitted_closure(db_session)

    response = client.post(
        f"/closures/{closure.id}/verify",
        json={"status": "reroute_available"},
        headers=auth_headers(maintainer_id),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == ClosureStatus.reroute_available.value
    assert body["moderation_status"] == ModerationStatus.verified.value


def test_verify_closure_ignores_a_body_that_names_no_status(client, db_session):
    """`{}` is not "set the status to nothing" - there is nothing to set."""
    closure, maintainer_id = _submitted_closure(db_session)

    response = client.post(f"/closures/{closure.id}/verify", json={}, headers=auth_headers(maintainer_id))

    assert response.status_code == 200
    assert response.json()["status"] == ClosureStatus.closed.value


def test_verify_closure_still_refuses_a_plain_hiker_with_a_status_in_hand(client, db_session):
    """The body must not become a way past the role gate."""
    closure, _ = _submitted_closure(db_session)

    response = client.post(
        f"/closures/{closure.id}/verify",
        json={"status": "open"},
        headers=auth_headers(str(uuid.uuid4())),
    )

    assert response.status_code == 403


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


# --- when a moderator confirmed it, on the wire (#292) ------------------------


def test_an_unverified_report_has_no_confirmation_time(client, db_session):
    """Null means "nobody has confirmed this", and the sheet renders the
    badge off it - so a report that only reached the queue must not read as
    one a moderator stood behind.

    Read as its own author, because an unverified report is not publicly
    readable at all - which is itself the reason the anonymous test below
    has to verify first."""
    reporter, report = _make_reporter_and_report(db_session)

    body = client.get(f"/reports/{report.id}", headers=auth_headers(reporter.id)).json()

    assert body["verified_at"] is None


def test_verifying_a_report_stamps_a_confirmation_time_on_the_wire(client, db_session):
    """`verified_at` has been on the model since #251 and was not on
    `ReportOut`, so the database knew when a moderator confirmed a report and
    the API could not say it. SeriousWarningSheet renders "Confirmed by club
    moderators - <date>" off exactly this."""
    _reporter, report = _make_reporter_and_report(db_session)
    maintainer_id = _make_maintainer(db_session)

    body = client.post(f"/reports/{report.id}/verify", json={}, headers=auth_headers(maintainer_id)).json()

    assert body["verified_at"] is not None


def test_the_confirmation_time_reaches_an_anonymous_reader(client, db_session):
    """The property the sheet depends on, and the one worth pinning: this is
    PUBLIC, unlike `received_at` beside it.

    A hiker weighing a strong claim is entitled to check when somebody stood
    behind it, and they are reading the map without an account. The privacy
    argument that withholds `received_at` does not reach this: that one
    narrows "when was this person there", because a report arrives when its
    author next has signal. This is a fact about a moderator at a desk.
    """
    _reporter, report = _make_reporter_and_report(db_session)
    maintainer_id = _make_maintainer(db_session)
    client.post(f"/reports/{report.id}/verify", json={}, headers=auth_headers(maintainer_id))

    body = client.get(f"/reports/{report.id}").json()

    assert body["verified_at"] is not None
    assert body["received_at"] is None


def test_who_confirmed_it_stays_behind(client, db_session):
    """The same split `ClosureOut` has always made: `verified_at` goes out,
    `verified_by` does not. It is a profile id, and #252 closed by taking
    reporter identity off the public read path - a moderator's is no more
    publishable than a reporter's."""
    _reporter, report = _make_reporter_and_report(db_session)
    maintainer_id = _make_maintainer(db_session)
    client.post(f"/reports/{report.id}/verify", json={}, headers=auth_headers(maintainer_id))

    body = client.get(f"/reports/{report.id}").json()

    assert "verified_by" not in body
    assert maintainer_id not in str(body)
