"""Tests for the `/closures` router.

See ../../features/MAP_OPTIONS.md's closures/reroutes section. Closures
mirror Report a Problem's create-vs-verify permission split (any
authenticated user can report one; only a maintainer/club_admin can modify
its real-world status). `moderation_status` is a real gap MAP_OPTIONS.md
never specifies - it has no moderation-state field at all, only the
closure's physical `status` (open/closed/reroute_available) - added here so
public queries have something to filter unverified closures out on, the same
way Report's `status`/`visibility` split already works.
"""

import uuid

from app.models.closure import Closure, ClosureStatus, ModerationStatus
from app.models.profile import Profile, Role
from tests.tokens import auth_headers

_VALID_PAYLOAD = {
    "reason_type": "storm_damage",
    "note": "Large blowdown blocking the trail after the storm.",
    "start_mile_marker": 1408.6,
    "end_mile_marker": 1411.0,
}


def test_create_closure_requires_authentication(client):
    response = client.post("/closures", json=_VALID_PAYLOAD)

    assert response.status_code == 401


def test_create_closure_always_starts_at_moderation_status_submitted(client):
    user_id = str(uuid.uuid4())
    # A client trying to self-verify should have no effect - moderation_status
    # isn't even a field ReportCreate-equivalent accepts.
    payload = dict(_VALID_PAYLOAD, moderation_status="verified")

    response = client.post("/closures", json=payload, headers=auth_headers(user_id))

    assert response.status_code == 201
    assert response.json()["moderation_status"] == "submitted"


def test_public_list_closures_excludes_moderation_status_submitted(client, db_session):
    reporter = Profile(id=str(uuid.uuid4()), role=Role.hiker)
    db_session.add(reporter)
    db_session.commit()

    verified = Closure(
        reported_by=reporter.id,
        reason_type="storm_damage",
        start_mile_marker=100.0,
        end_mile_marker=102.0,
        moderation_status=ModerationStatus.verified,
    )
    submitted = Closure(
        reported_by=reporter.id,
        reason_type="flooding",
        start_mile_marker=200.0,
        end_mile_marker=201.0,
        moderation_status=ModerationStatus.submitted,
    )
    db_session.add_all([verified, submitted])
    db_session.commit()

    response = client.get("/closures")

    assert response.status_code == 200
    ids = [c["id"] for c in response.json()]
    assert verified.id in ids
    assert submitted.id not in ids


def test_list_closures_requires_no_authentication(client):
    response = client.get("/closures")

    assert response.status_code == 200


def test_update_closure_status_rejected_for_a_plain_hiker_role_with_403(client, db_session):
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
    response = client.patch(
        f"/closures/{closure.id}",
        json={"status": "closed"},
        headers=auth_headers(hiker_id),
    )

    assert response.status_code == 403


def test_update_closure_status_allowed_for_maintainer_role(client, db_session):
    reporter = Profile(id=str(uuid.uuid4()), role=Role.hiker)
    maintainer_id = str(uuid.uuid4())
    maintainer = Profile(id=maintainer_id, role=Role.maintainer)
    db_session.add_all([reporter, maintainer])
    db_session.commit()
    closure = Closure(
        reported_by=reporter.id,
        reason_type="storm_damage",
        start_mile_marker=1.0,
        end_mile_marker=2.0,
    )
    db_session.add(closure)
    db_session.commit()

    response = client.patch(
        f"/closures/{closure.id}",
        json={"status": "closed"},
        headers=auth_headers(maintainer_id),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "closed"


# --- The status a closure is born with (#246) -----------------------------
#
# `open` in this enum means REOPENED, and the client renders it as such: the
# banner stays silent and the sheet says "Open again". While it was also the
# column's birth default, the designed happy path - report, verify, publish -
# produced a verified closure that every reader was obliged to present as
# reopened trail.
#
# What makes that worth a block of tests rather than a one-line assertion is
# that nothing failed while it was broken. Both halves were individually
# correct; only the sequence was wrong, and no test walked the sequence.


def test_a_reported_closure_is_born_closed(client):
    """Somebody filing this is telling us the trail is shut."""
    response = client.post("/closures", json=_VALID_PAYLOAD, headers=auth_headers(str(uuid.uuid4())))

    assert response.status_code == 201
    assert response.json()["status"] == ClosureStatus.closed.value


def test_a_reporter_cannot_declare_a_trail_open(client):
    """`status` is server-controlled on create, like `moderation_status`.

    Reopening a trail is a maintainer's judgment - PATCH, or the verify call.
    A reporter who could set this could publish "the trail is fine" over
    somebody else's closure by filing a second one.
    """
    payload = dict(_VALID_PAYLOAD, status="open")

    response = client.post("/closures", json=payload, headers=auth_headers(str(uuid.uuid4())))

    assert response.status_code == 201
    assert response.json()["status"] == ClosureStatus.closed.value


def test_report_then_verify_then_list_serves_a_closure_that_says_closed(client, db_session):
    """The whole flow, in order, which is the thing that was broken.

    Every step of this passed on its own. Walked end to end, the closure the
    public list served said `open`, so client/src/lib/closureBanner.ts
    returned null and client/src/map/closureLayers.ts drew no band - a
    verified closure rendered as an open trail.
    """
    reporter_id = str(uuid.uuid4())
    created = client.post("/closures", json=_VALID_PAYLOAD, headers=auth_headers(reporter_id))
    assert created.status_code == 201
    closure_id = created.json()["id"]

    maintainer_id = str(uuid.uuid4())
    db_session.add(Profile(id=maintainer_id, role=Role.maintainer))
    db_session.commit()

    verified = client.post(f"/closures/{closure_id}/verify", headers=auth_headers(maintainer_id))
    assert verified.status_code == 200

    listed = client.get("/closures").json()
    served = next(c for c in listed if c["id"] == closure_id)

    assert served["moderation_status"] == ModerationStatus.verified.value
    assert served["status"] == ClosureStatus.closed.value


def test_a_maintainer_can_still_reopen_a_trail(client, db_session):
    """The `open` state has not gone anywhere - it has only stopped being the
    state a closure starts in."""
    reporter = Profile(id=str(uuid.uuid4()), role=Role.hiker)
    maintainer_id = str(uuid.uuid4())
    db_session.add_all([reporter, Profile(id=maintainer_id, role=Role.maintainer)])
    db_session.commit()
    closure = Closure(
        reported_by=reporter.id,
        reason_type="storm_damage",
        start_mile_marker=1.0,
        end_mile_marker=2.0,
    )
    db_session.add(closure)
    db_session.commit()

    response = client.patch(
        f"/closures/{closure.id}",
        json={"status": "open"},
        headers=auth_headers(maintainer_id),
    )

    assert response.status_code == 200
    assert response.json()["status"] == ClosureStatus.open.value
