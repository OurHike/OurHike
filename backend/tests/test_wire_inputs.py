"""Wire-level input hardening (#658).

The audit's pattern: every hardened path in app/ cites an incident number,
and the unhardened ones were the paths without a war story yet. These are
the war stories being written before the incident:

- NaN/Infinity floats were accepted by every float field except
  ReportCreate.mile, on the strength of a comment claiming JSON cannot
  deliver them. It can - Python's json module emits and accepts the bare
  NaN token - and what a NaN does downstream is never loud (a NaN mile is
  absent from every banner; a NaN hike reference makes derive_direction
  return SOBO unconditionally).
- Unbounded notes on unpaginated public lists compound: one valid 50 MB
  note, once verified, ships to every anonymous GET caller on every sync.
- A thanks naming a nonexistent maintainer/club was a 500; a maintainer
  named without a club was credited to whichever club covered the mile.
- Two check-then-insert seams (profile provisioning, preferences upsert)
  raced their own parallel first requests and the loser 500ed - the #265
  shape, unhandled where every authenticated request crosses.
"""

import uuid
from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError

from app.core import auth as core_auth
from app.models.club import Club
from app.models.maintainer_assignment import MaintainerAssignment
from app.models.profile import Profile, Role
from app.schemas.common import NOTE_MAX_CHARS
from tests.tokens import auth_headers

# Raw bodies carrying the bare NaN/Infinity tokens - the exact bytes a
# loose JSON emitter produces. httpx's own json= encoder refuses them
# client-side (allow_nan=False), which is precisely why the old comment
# believed the wire was safe: the well-behaved client it tested with could
# not send what a hostile or sloppy one can.
def _post_raw(client, url, body, user_id=None):
    return client.post(
        url,
        content=body,
        headers={"Content-Type": "application/json", **auth_headers(user_id or str(uuid.uuid4()))},
    )


def test_a_nan_hike_reference_is_a_422_not_a_stored_sobo_generator(client):
    response = _post_raw(client, "/hikes", '{"overall_start_reference": NaN, "overall_end_reference": 2189.0}')

    assert response.status_code == 422


def test_an_infinite_closure_mile_is_a_422(client):
    response = _post_raw(
        client,
        "/closures",
        '{"reason_type": "storm_damage", "start_mile_marker": Infinity, "end_mile_marker": 12.0}',
    )

    assert response.status_code == 422


def test_a_nan_report_latitude_is_a_422(client):
    response = _post_raw(
        client,
        "/reports",
        '{"type": "blowdown", "reporter_type": "day", "lat": NaN, "lon": -83.5}',
    )

    assert response.status_code == 422


def test_a_note_past_the_cap_is_a_422_not_a_stored_megabyte(client):
    oversized = "x" * (NOTE_MAX_CHARS + 1)

    report = client.post(
        "/reports",
        json={"type": "blowdown", "reporter_type": "day", "note": oversized},
        headers=auth_headers(str(uuid.uuid4())),
    )
    closure = client.post(
        "/closures",
        json={"reason_type": "storm_damage", "start_mile_marker": 1.0, "end_mile_marker": 2.0, "note": oversized},
        headers=auth_headers(str(uuid.uuid4())),
    )

    assert report.status_code == 422
    assert closure.status_code == 422


def test_a_note_at_the_cap_still_files(client):
    response = client.post(
        "/reports",
        json={"type": "blowdown", "reporter_type": "day", "note": "x" * NOTE_MAX_CHARS},
        headers=auth_headers(str(uuid.uuid4())),
    )

    assert response.status_code == 201


# --- The thanks credit paths -------------------------------------------------


def _club(db, name="Mountain Club"):
    club = Club(id=str(uuid.uuid4()), name=name, region="Central Virginia")
    db.add(club)
    db.commit()
    return club


def _maintainer(db, name="Pat"):
    profile = Profile(id=str(uuid.uuid4()), role=Role.maintainer, display_name=name)
    db.add(profile)
    db.commit()
    return profile


def _assign(db, *, maintainer, club, start, end):
    assignment = MaintainerAssignment(
        id=str(uuid.uuid4()),
        maintainer_id=maintainer.id,
        club_id=club.id,
        start_mile=start,
        end_mile=end,
        effective_from=date(2026, 1, 1),
        publicly_creditable=True,
    )
    db.add(assignment)
    db.commit()
    return assignment


def test_a_thanks_naming_a_nonexistent_maintainer_is_a_422_naming_the_field(client):
    response = client.post(
        "/reports",
        json={
            "type": "thanks",
            "reporter_type": "day",
            "maintainer_id": str(uuid.uuid4()),
        },
        headers=auth_headers(str(uuid.uuid4())),
    )

    assert response.status_code == 422, "a bad foreign key is the caller's error, not a 500"
    assert "maintainer_id" in response.json()["detail"]


def test_a_named_maintainers_thanks_never_borrows_another_clubs_credit(client, db_session):
    """Two clubs' assignments overlap the mile. The hiker named Pat, so the
    club is Pat's club - not "whichever club covers the mile", which is what
    resolving the two fields independently used to produce (#658)."""
    pats_club = _club(db_session, "Pat's Club")
    other_club = _club(db_session, "The Other Club")
    pat = _maintainer(db_session, "Pat")
    stranger = _maintainer(db_session, "Stranger")
    _assign(db_session, maintainer=pat, club=pats_club, start=100, end=110)
    _assign(db_session, maintainer=stranger, club=other_club, start=100, end=110)

    response = client.post(
        "/reports",
        json={"type": "thanks", "reporter_type": "day", "mile": 105.0, "maintainer_id": pat.id},
        headers=auth_headers(str(uuid.uuid4())),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["maintainer_id"] == pat.id
    assert body["club_id"] == pats_club.id, "the named maintainer's own club, never the overlap's"


def test_a_named_maintainer_with_no_covering_assignment_falls_back_to_the_stretch(client, db_session):
    """Pat is real but nothing covers this mile for Pat, while one club does
    cover it. The stretch's club still resolves - the reviewed #249 decision
    ("the half they left blank is still resolved") that
    test_a_hiker_who_knows_the_name_is_not_overruled_by_the_lookup pins:
    the #658 fix bites only where the named person has covering assignments
    of their own to prefer."""
    other_club = _club(db_session, "The Other Club")
    pat = _maintainer(db_session, "Pat")
    stranger = _maintainer(db_session, "Stranger")
    _assign(db_session, maintainer=stranger, club=other_club, start=100, end=110)

    response = client.post(
        "/reports",
        json={"type": "thanks", "reporter_type": "day", "mile": 105.0, "maintainer_id": pat.id},
        headers=auth_headers(str(uuid.uuid4())),
    )

    assert response.status_code == 201
    assert response.json()["club_id"] == other_club.id


# --- The two check-then-insert races (#265's shape) ---------------------------


def test_losing_the_profile_provisioning_race_returns_the_winners_row(db_session, monkeypatch):
    """Simulated race: the commit fails as it would when a parallel request
    inserted first, and the winner's row is already there to be found."""
    user_id = str(uuid.uuid4())

    real_commit = core_auth.commit_and_refresh

    def lose_the_race(db, row):
        db.rollback()
        winner = Profile(id=user_id, role=Role.hiker)
        db.add(winner)
        db.commit()
        raise IntegrityError("duplicate key", params=None, orig=Exception("profiles_pkey"))

    monkeypatch.setattr(core_auth, "commit_and_refresh", lose_the_race)
    profile = core_auth._get_or_create_profile(db_session, user_id)

    assert profile.id == user_id
    monkeypatch.setattr(core_auth, "commit_and_refresh", real_commit)


def test_losing_the_preferences_first_sync_race_still_stores_this_requests_data(client, db_session, monkeypatch):
    """The loser's PUT must land its own blob on the winner's row - a sync
    is a full overwrite by design, so that is what a retry would have done.
    Simulated by having the winner's row appear (via a second session, as a
    parallel request would) at the moment the loser's insert fails."""
    from app.core.time import utc_now
    from app.models.preferences import UserPreferences
    from app.routers import preferences as preferences_router

    user_id = str(uuid.uuid4())
    db_session.add(Profile(id=user_id, role=Role.hiker))
    db_session.commit()
    real_commit = preferences_router.commit_and_refresh
    calls = {"n": 0}

    def lose_the_first_race(db, row):
        calls["n"] += 1
        if calls["n"] == 1 and isinstance(row, UserPreferences):
            db.rollback()
            winner = UserPreferences(profile_id=user_id, data={"theme": "light"}, updated_at=utc_now())
            db_session.add(winner)
            db_session.commit()
            raise IntegrityError("duplicate key", params=None, orig=Exception("user_preferences_pkey"))
        return real_commit(db, row)

    monkeypatch.setattr(preferences_router, "commit_and_refresh", lose_the_first_race)

    payload = _valid_preferences_payload()
    put = client.put("/preferences/me", json=payload, headers=auth_headers(user_id))

    assert put.status_code == 200, "losing the race must recover, never 500"
    got = client.get("/preferences/me", headers=auth_headers(user_id))
    assert got.status_code == 200
    assert got.json()["unit_system"] == payload["unit_system"], "the loser's own blob wins the overwrite"


def _valid_preferences_payload() -> dict:
    """The full PreferencesIn shape - mirrored from the preferences suite's
    own fixture rather than imported, so this file stands alone."""
    return {
        "trail_name": "Switchback",
        "theme": "dark",
        "unit_system": "metric",
        "background_source": "usgs_topo_offline",
        "max_background_zoom": 12,
        "hiking_detail_level": "fine",
        "map_style": "field",
        "red_light_enabled": False,
        "show_roads": False,
        "layer_detail_level": "standard",
        "anonymity_window_days": 14,
    }
