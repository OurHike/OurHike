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

import json
import uuid
from datetime import datetime, timedelta, timezone

from app.models.closure import Closure, ClosureStatus, ModerationStatus
from app.models.profile import Profile, Role
from tests.factories import make_closure, make_profile
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
    reporter = make_profile(db_session, Role.hiker)

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


def test_public_closures_name_nobody(client, db_session):
    """#430: `reported_by`/`verified_by` are not on the wire.

    They are profile ids, which are Supabase auth user ids, and the test above
    is the reason this one matters - `GET /closures` needs no account, so
    every id it returned was readable by anybody. Joined across closures they
    say which maintainer covers which stretch and how often.

    Asserted against the response keys rather than a value, because a null
    would pass a value check on any closure nobody has verified yet - which is
    most of them, and would leave this green while the field was back for the
    verified ones.
    """
    reporter = Profile(id=str(uuid.uuid4()), role=Role.hiker)
    verifier = Profile(id=str(uuid.uuid4()), role=Role.maintainer)
    db_session.add_all([reporter, verifier])
    db_session.commit()
    db_session.add(
        Closure(
            reported_by=reporter.id,
            reason_type="storm_damage",
            start_mile_marker=300.0,
            end_mile_marker=301.0,
            moderation_status=ModerationStatus.verified,
            verified_by=verifier.id,
        )
    )
    db_session.commit()

    response = client.get("/closures")

    assert response.status_code == 200
    [closure] = [c for c in response.json() if c["start_mile_marker"] == 300.0]
    assert "reported_by" not in closure
    assert "verified_by" not in closure
    assert reporter.id not in response.text
    assert verifier.id not in response.text


def test_update_closure_status_rejected_for_a_plain_hiker_role_with_403(client, db_session):
    reporter = make_profile(db_session, Role.hiker)
    closure = make_closure(db_session, reporter.id)

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
    closure = make_closure(db_session, reporter.id)

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
    closure = make_closure(db_session, reporter.id)

    response = client.patch(
        f"/closures/{closure.id}",
        json={"status": "open"},
        headers=auth_headers(maintainer_id),
    )

    assert response.status_code == 200
    assert response.json()["status"] == ClosureStatus.open.value


# --- The three fields the sheet renders (#245) ----------------------------
#
# `ClosureDetail` extended the shared `Closure` shape with four fields that no
# backend could supply, so the component looked finished while being
# unfillable - every test fed them by hand. Three are facts about the closure
# and now have columns. The fourth, `marked_by`, is a fact about a person and
# was deleted from the client type instead.
#
# What these pin down is not that the columns exist - a schema test would say
# that - but that a maintainer can actually move them, that a reporter cannot,
# and that verifying does not wipe them.


def _closure_and_maintainer(db_session):
    """A submitted closure and a maintainer who can move it."""
    closure = make_closure(db_session, make_profile(db_session).id)
    return closure, make_profile(db_session, Role.maintainer).id


def test_a_new_closure_has_all_three_detail_fields_null(client):
    """Null is the honest start: nobody has said when the trail shut."""
    response = client.post("/closures", json=_VALID_PAYLOAD, headers=auth_headers(str(uuid.uuid4())))

    body = response.json()
    assert response.status_code == 201
    assert body["closed_since"] is None
    assert body["expected_reopen"] is None
    assert body["reroute_url"] is None


def test_a_maintainer_sets_the_three_detail_fields(client, db_session):
    closure, maintainer_id = _closure_and_maintainer(db_session)

    response = client.patch(
        f"/closures/{closure.id}",
        json={
            "closed_since": "2026-08-01T00:00:00Z",
            "expected_reopen": "2026-09-15T00:00:00Z",
            "reroute_url": "https://www.nynjtc.org/notice/storm-reroute",
        },
        headers=auth_headers(maintainer_id),
    )

    body = response.json()
    assert response.status_code == 200
    assert body["closed_since"] == "2026-08-01T00:00:00Z"
    assert body["expected_reopen"] == "2026-09-15T00:00:00Z"
    assert body["reroute_url"] == "https://www.nynjtc.org/notice/storm-reroute"


def test_a_plain_hiker_cannot_set_the_detail_fields(client, db_session):
    """Same gate as every other PATCH field - judging a reopening date is a
    maintainer's job, and `reroute_url` renders as a link a hiker taps."""
    closure, _ = _closure_and_maintainer(db_session)
    hiker_id = str(uuid.uuid4())
    db_session.add(Profile(id=hiker_id, role=Role.hiker))
    db_session.commit()

    response = client.patch(
        f"/closures/{closure.id}",
        json={"reroute_url": "https://example.com/anything"},
        headers=auth_headers(hiker_id),
    )

    assert response.status_code == 403


def test_the_detail_fields_are_not_settable_on_create(client):
    """They are absent from `ClosureCreate`, so a reporter sending them
    changes nothing - the same posture `moderation_status` takes."""
    payload = dict(
        _VALID_PAYLOAD,
        closed_since="2020-01-01T00:00:00Z",
        reroute_url="https://example.com/not-reviewed",
    )

    response = client.post("/closures", json=payload, headers=auth_headers(str(uuid.uuid4())))

    body = response.json()
    assert response.status_code == 201
    assert body["closed_since"] is None
    assert body["reroute_url"] is None


def test_an_omitted_detail_field_is_left_alone(client, db_session):
    """A PATCH that only changes `status` must not clear the dates."""
    closure, maintainer_id = _closure_and_maintainer(db_session)
    client.patch(
        f"/closures/{closure.id}",
        json={"closed_since": "2026-08-01T00:00:00Z"},
        headers=auth_headers(maintainer_id),
    )

    response = client.patch(
        f"/closures/{closure.id}",
        json={"status": "open"},
        headers=auth_headers(maintainer_id),
    )

    assert response.status_code == 200
    assert response.json()["closed_since"] == "2026-08-01T00:00:00Z"


def test_an_explicit_null_clears_a_detail_field(client, db_session):
    """The distinction `model_fields_set` exists for: a reopening date that
    slips or is withdrawn has to be removable, or a stale promise outlives
    the promise."""
    closure, maintainer_id = _closure_and_maintainer(db_session)
    client.patch(
        f"/closures/{closure.id}",
        json={"expected_reopen": "2026-09-15T00:00:00Z"},
        headers=auth_headers(maintainer_id),
    )

    response = client.patch(
        f"/closures/{closure.id}",
        json={"expected_reopen": None},
        headers=auth_headers(maintainer_id),
    )

    assert response.status_code == 200
    assert response.json()["expected_reopen"] is None


def test_verifying_a_closure_preserves_the_detail_fields(client, db_session):
    """ "Survives moderation" from #245, walked rather than asserted about:
    the fields are set, the closure goes through the real verify action, and
    the public list is what gets checked."""
    closure, maintainer_id = _closure_and_maintainer(db_session)
    client.patch(
        f"/closures/{closure.id}",
        json={
            "closed_since": "2026-08-01T00:00:00Z",
            "reroute_url": "https://www.nynjtc.org/notice/storm-reroute",
        },
        headers=auth_headers(maintainer_id),
    )

    verify = client.post(f"/closures/{closure.id}/verify", headers=auth_headers(maintainer_id))
    assert verify.status_code == 200

    listed = client.get("/closures").json()
    served = next(c for c in listed if c["id"] == closure.id)
    assert served["closed_since"] == "2026-08-01T00:00:00Z"
    assert served["reroute_url"] == "https://www.nynjtc.org/notice/storm-reroute"


def test_a_reroute_url_must_be_http_or_https(client, db_session):
    """A `javascript:` URL on a safety sheet is the reason this is validated
    at all - the sheet renders the value as an anchor a hiker taps."""
    closure, maintainer_id = _closure_and_maintainer(db_session)

    response = client.patch(
        f"/closures/{closure.id}",
        json={"reroute_url": "javascript:alert(document.cookie)"},
        headers=auth_headers(maintainer_id),
    )

    assert response.status_code == 422


def test_a_blank_reroute_url_is_read_as_a_clear(client, db_session):
    """The shape a form sends for an emptied box. Storing it would give the
    client a truthy value that renders an anchor pointing nowhere."""
    closure, maintainer_id = _closure_and_maintainer(db_session)
    client.patch(
        f"/closures/{closure.id}",
        json={"reroute_url": "https://www.nynjtc.org/notice/storm-reroute"},
        headers=auth_headers(maintainer_id),
    )

    response = client.patch(
        f"/closures/{closure.id}",
        json={"reroute_url": "   "},
        headers=auth_headers(maintainer_id),
    )

    assert response.status_code == 200
    assert response.json()["reroute_url"] is None


def test_a_reopening_date_before_the_closing_date_is_refused(client, db_session):
    closure, maintainer_id = _closure_and_maintainer(db_session)

    response = client.patch(
        f"/closures/{closure.id}",
        json={
            "closed_since": "2026-08-01T00:00:00Z",
            "expected_reopen": "2026-07-01T00:00:00Z",
        },
        headers=auth_headers(maintainer_id),
    )

    assert response.status_code == 422
    # Nothing from the refused request survives. The check runs before the
    # assignment for this reason: values left on a live ORM instance can be
    # written out by the next autoflush, behind the 422.
    stored = db_session.get(Closure, closure.id)
    db_session.refresh(stored)
    assert stored.closed_since is None
    assert stored.expected_reopen is None


def test_the_ordering_check_reads_the_stored_value_not_just_the_payload(client, db_session):
    """The two dates arrive in whichever order a maintainer sends them,
    possibly days apart. A payload-only check passes on every second half of
    an inconsistent pair."""
    closure, maintainer_id = _closure_and_maintainer(db_session)
    client.patch(
        f"/closures/{closure.id}",
        json={"closed_since": "2026-08-01T00:00:00Z"},
        headers=auth_headers(maintainer_id),
    )

    response = client.patch(
        f"/closures/{closure.id}",
        json={"expected_reopen": "2026-07-01T00:00:00Z"},
        headers=auth_headers(maintainer_id),
    )

    assert response.status_code == 422


def test_an_offset_bearing_date_is_converted_rather_than_truncated(client, db_session):
    """Storage is naive-UTC, so a phone's `-04:00` has to be applied. Dropping
    the offset instead would move the date by four hours - across midnight for
    exactly the evening values a hiker reads as "yesterday"."""
    closure, maintainer_id = _closure_and_maintainer(db_session)

    response = client.patch(
        f"/closures/{closure.id}",
        json={"closed_since": "2026-08-01T22:30:00-04:00"},
        headers=auth_headers(maintainer_id),
    )

    assert response.status_code == 200
    assert response.json()["closed_since"] == "2026-08-02T02:30:00Z"


def test_an_explicit_null_clears_the_note(client, db_session):
    """The edit #255 found foreclosed: a stale note could only be overwritten
    with more text, never removed. Under the shared PATCH convention
    (app/schemas/partial.py) `{"note": null}` is a deliberate clear."""
    closure, maintainer_id = _closure_and_maintainer(db_session)
    client.patch(
        f"/closures/{closure.id}",
        json={"note": "bridge out at the crossing"},
        headers=auth_headers(maintainer_id),
    )

    response = client.patch(
        f"/closures/{closure.id}",
        json={"note": None},
        headers=auth_headers(maintainer_id),
    )

    assert response.status_code == 200
    assert response.json()["note"] is None


def test_an_explicit_null_on_a_non_nullable_field_is_a_422(client, db_session):
    """`status` and `reason_type` have no null state for a null to mean, so
    the answer is a validation error naming the field - not the silent drop
    that used to read as success (#255)."""
    closure, maintainer_id = _closure_and_maintainer(db_session)

    for field in ("status", "reason_type"):
        response = client.patch(
            f"/closures/{closure.id}",
            json={field: None},
            headers=auth_headers(maintainer_id),
        )

        assert response.status_code == 422, field
        assert field in response.text


def test_a_reversed_mile_pair_is_normalised_on_create(client):
    """#257: warningsOnRoute normalises ordering and closureBanner assumes
    start <= end, so a reversed pair made the inside-the-closure check
    unsatisfiable. Normalised at the source, as a swap rather than a 422 -
    "closed between these two miles" means the same thing in either order."""
    payload = dict(_VALID_PAYLOAD, start_mile_marker=120.5, end_mile_marker=118.0)

    response = client.post("/closures", json=payload, headers=auth_headers(str(uuid.uuid4())))

    body = response.json()
    assert response.status_code == 201
    assert body["start_mile_marker"] == 118.0
    assert body["end_mile_marker"] == 120.5


# --- Endpoint geometry: the anchor a re-measure cannot move (#674) ----------
#
# features/POI_IDENTITY.md, "Miles are a projection, not an anchor". A mile is
# a reading against one measurement of the centerline; the ATC re-measures, and
# a closure stored only as two miles quietly comes to name a different stretch.
# The fix is the geometry, captured by the author's client at write time.

_GEOMETRY = {"start_lat": 40.9, "start_lon": -73.9, "end_lat": 41.1, "end_lon": -73.7}


def test_a_closure_can_carry_the_position_of_both_its_ends(client):
    response = client.post("/closures", json=dict(_VALID_PAYLOAD, **_GEOMETRY), headers=auth_headers(str(uuid.uuid4())))

    body = response.json()
    assert response.status_code == 201
    assert {key: body[key] for key in _GEOMETRY} == _GEOMETRY


def test_a_closure_without_geometry_is_still_accepted_and_reads_as_null(client):
    """The ordinary state, not a gap: every row filed before the columns
    existed has none, and so does every row filed until this app grows a
    closure form. The client falls back to the stored mile."""
    response = client.post("/closures", json=_VALID_PAYLOAD, headers=auth_headers(str(uuid.uuid4())))

    body = response.json()
    assert response.status_code == 201
    assert [body["start_lat"], body["start_lon"], body["end_lat"], body["end_lon"]] == [None] * 4


def test_half_a_point_is_refused_rather_than_half_stored(client):
    """A latitude with no longitude is not a position. Storing it would put a
    row in the table that looks anchored and is not - which is the failure a
    null pair exists to make visible, wearing a disguise."""
    for field in ("start_lat", "start_lon", "end_lat", "end_lon"):
        payload = dict(_VALID_PAYLOAD, **{field: 41.0})

        response = client.post("/closures", json=payload, headers=auth_headers(str(uuid.uuid4())))

        assert response.status_code == 422, field
        assert field.split("_")[0] in response.text


def test_normalising_a_reversed_pair_carries_the_geometry_with_it(client):
    """The subtle half of #257 meeting #674. Each point is the position OF
    its mile, so swapping the miles without the points would pair the
    southern end's coordinates with the northern end's mile - a closure whose
    two ends are each other's. Worse than the reversed pair the normalisation
    exists to fix, and invisible in a way that one was not."""
    payload = dict(
        _VALID_PAYLOAD,
        start_mile_marker=120.5,
        end_mile_marker=118.0,
        start_lat=41.1,
        start_lon=-73.7,
        end_lat=40.9,
        end_lon=-73.9,
    )

    response = client.post("/closures", json=payload, headers=auth_headers(str(uuid.uuid4())))

    body = response.json()
    assert response.status_code == 201
    assert (body["start_mile_marker"], body["end_mile_marker"]) == (118.0, 120.5)
    # The point that travelled with mile 118.0, not the one sent as "start".
    assert (body["start_lat"], body["start_lon"]) == (40.9, -73.9)
    assert (body["end_lat"], body["end_lon"]) == (41.1, -73.7)


def test_a_nan_coordinate_is_refused_like_every_other_float_on_the_wire(client):
    """schemas/common.FiniteFloat's whole point: a NaN compares False against
    everything, so it would be silently absent from every projection rather
    than loudly wrong."""
    payload = dict(_VALID_PAYLOAD, **{**_GEOMETRY, "start_lat": float("nan")})

    response = client.post(
        "/closures", data=json.dumps(payload), headers={**auth_headers(str(uuid.uuid4())), "Content-Type": "application/json"}
    )

    assert response.status_code == 422


# ---------------------------------------------------------------------------
# The outbox contract (#832): a closure is authored at the washout, where
# there is no signal, so it queues on a phone and flushes days later. Two
# things follow, and both are what these tests pin.
# ---------------------------------------------------------------------------


def test_resending_a_closure_returns_the_stored_one_rather_than_filing_a_second(client, db_session):
    """The one-bar failure, which for this endpoint is the ordinary case: the
    request commits here and its response never arrives, so the outbox sends
    it again. Reports' contract (#243), now the closure's."""
    user_id = str(uuid.uuid4())
    closure_id = str(uuid.uuid4())
    payload = dict(_VALID_PAYLOAD, id=closure_id)

    first = client.post("/closures", json=payload, headers=auth_headers(user_id))
    second = client.post("/closures", json=payload, headers=auth_headers(user_id))

    assert first.status_code == 201
    # 200 rather than 201: the same closure, not a new one. A client only
    # needs to see a 2xx either way.
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"] == closure_id
    assert db_session.query(Closure).count() == 1


def test_a_closure_id_belonging_to_somebody_else_is_refused_not_returned(client):
    """Handing back another person's row would turn a guessed UUID into a way
    to read an unmoderated report about a stretch of trail."""
    closure_id = str(uuid.uuid4())
    payload = dict(_VALID_PAYLOAD, id=closure_id)

    client.post("/closures", json=payload, headers=auth_headers(str(uuid.uuid4())))
    response = client.post("/closures", json=payload, headers=auth_headers(str(uuid.uuid4())))

    assert response.status_code == 409


def test_the_day_it_was_written_survives_the_days_it_waited_in_an_outbox(client):
    """`reported_at` is what the closure sheet ages a closure by. A queued
    closure that reads as filed on the day its phone found signal makes that
    number wrong in the safe-looking direction - fresher than it is."""
    wrote_it = datetime.now(timezone.utc) - timedelta(days=3)
    payload = dict(_VALID_PAYLOAD, reported_at=wrote_it.isoformat())

    response = client.post("/closures", json=payload, headers=auth_headers(str(uuid.uuid4())))

    assert response.status_code == 201
    stored = datetime.fromisoformat(response.json()["reported_at"].replace("Z", "+00:00"))
    assert abs((stored - wrote_it).total_seconds()) < 1


def test_a_closure_dated_in_the_future_is_refused(client):
    """Five minutes of lead is a drifting phone clock; a day is not. The same
    bound `ReportCreate.authored_at` keeps, and deliberately the same number."""
    payload = dict(
        _VALID_PAYLOAD,
        reported_at=(datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
    )

    response = client.post("/closures", json=payload, headers=auth_headers(str(uuid.uuid4())))

    assert response.status_code == 422
    assert "reported_at" in response.text


def test_a_closure_with_no_date_is_stamped_by_the_server(client):
    """Every client that predates the form sends nothing, and a maintainer
    with curl still files closures. Absent means now, as it always did."""
    before = datetime.now(timezone.utc) - timedelta(seconds=5)

    response = client.post("/closures", json=_VALID_PAYLOAD, headers=auth_headers(str(uuid.uuid4())))

    assert response.status_code == 201
    stored = datetime.fromisoformat(response.json()["reported_at"].replace("Z", "+00:00"))
    assert stored >= before
