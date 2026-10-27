"""Tests for `POST /usage-events` (#1902, app/routers/analytics.py).

The endpoint makes four promises, and each test below is one of them failing
if it is broken:

  - **A token alone links nothing.** A row carries a `user_key` only when the
    batch says the hiker agreed AND the token is valid.
  - **The account and the fix are only ever sealed.** No plain column holds
    either, and without a published key both are thrown away.
  - **Anything outside the registry is refused**, whole, with a 422.
  - **The User table counts each stored row once**, however often a phone
    resends it.
"""

import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import inspect

from app.config import settings
from app.core.analytics_rollup import add_months, month_start, retention_start
from app.core.analytics_seal import month_label, month_private_key, month_public_key, new_secret, open_sealed, user_key
from app.core.time import utc_now
from app.models.analytics import AnalyticsEvent, AnalyticsSealKey, AnalyticsUser
from tests.factories import make_profile
from tests.tokens import auth_headers

SERVER_SECRET = "test-only-user-key-secret"


@pytest.fixture(autouse=True)
def _user_key_secret(monkeypatch):
    monkeypatch.setattr(settings, "analytics_user_key_secret", SERVER_SECRET)


@pytest.fixture()
def today():
    return utc_now().date()


@pytest.fixture()
def seal_secret(db_session, today):
    """A secret with this month's and last month's public keys published."""
    secret = new_secret()
    for month in (month_start(today), add_months(month_start(today), -1)):
        db_session.add(AnalyticsSealKey(month=month, public_key=month_public_key(secret, month_label(month))))
    db_session.commit()
    return secret


def _event(today, **fields):
    return {
        "id": str(uuid.uuid4()),
        "event": "map_screen_viewed",
        "local_date": today.isoformat(),
        "platform": "android",
        **fields,
    }


def _post(client, events, *, identified=False, headers=None):
    return client.post("/usage-events", json={"identified": identified, "events": events}, headers=headers or {})


# --- what is stored ---------------------------------------------------------


def test_a_signed_out_batch_is_stored_with_no_key(client, db_session, today):
    event = _event(today, month_first=True)

    response = _post(client, [event])

    assert response.status_code == 202
    assert response.json() == {"accepted": 1, "duplicates": 0}
    stored = db_session.get(AnalyticsEvent, event["id"])
    assert stored.user_key is None and stored.month_first is True


def test_resending_a_batch_stores_nothing_twice(client, db_session, today):
    events = [_event(today), _event(today)]
    _post(client, events)

    response = _post(client, events)

    assert response.json() == {"accepted": 0, "duplicates": 2}
    assert db_session.query(AnalyticsEvent).count() == 2


# --- a token alone links nothing ---------------------------------------------


def test_a_hiker_who_said_yes_is_linked_by_their_key(client, db_session, today):
    hiker = make_profile(db_session)
    event = _event(today)

    _post(client, [event], identified=True, headers=auth_headers(hiker.id))

    assert db_session.get(AnalyticsEvent, event["id"]).user_key == user_key(SERVER_SECRET, hiker.id)


def test_a_token_without_a_yes_links_nothing(client, db_session, today):
    hiker = make_profile(db_session)
    event = _event(today)

    _post(client, [event], identified=False, headers=auth_headers(hiker.id))

    assert db_session.get(AnalyticsEvent, event["id"]).user_key is None


def test_a_yes_without_a_token_links_nothing(client, db_session, today):
    event = _event(today)

    _post(client, [event], identified=True)

    assert db_session.get(AnalyticsEvent, event["id"]).user_key is None


def test_a_yes_with_an_unusable_token_links_nothing(client, db_session, today):
    event = _event(today)

    response = _post(client, [event], identified=True, headers={"Authorization": "Bearer not-a-real-token"})

    assert response.status_code == 202
    assert db_session.get(AnalyticsEvent, event["id"]).user_key is None


def test_with_no_server_secret_nothing_is_ever_linked(client, db_session, today, monkeypatch):
    monkeypatch.setattr(settings, "analytics_user_key_secret", "")
    hiker = make_profile(db_session)
    event = _event(today)

    _post(client, [event], identified=True, headers=auth_headers(hiker.id))

    assert db_session.get(AnalyticsEvent, event["id"]).user_key is None
    assert db_session.query(AnalyticsUser).count() == 0


# --- the account and the fix are only ever sealed -----------------------------


def test_a_fix_is_sealed_and_opens_to_exactly_what_the_phone_sent(client, db_session, today, seal_secret):
    hiker = make_profile(db_session)
    event = _event(today, fix={"lat": 41.29871, "lon": -74.18810, "accuracy_m": 12.0})

    _post(client, [event], identified=True, headers=auth_headers(hiker.id))

    stored = db_session.get(AnalyticsEvent, event["id"])
    label = month_label(today)
    opened = open_sealed(month_private_key(seal_secret, label), label, event["id"], bytes(stored.sealed))
    assert opened == {"account": hiker.id, "lat": 41.29871, "lon": -74.1881, "accuracy_m": 12.0}
    assert stored.seal == "sealed" and stored.has_fix is True


def test_the_plain_square_is_the_fixs_south_west_corner(client, db_session, today, seal_secret):
    event = _event(today, fix={"lat": 41.29871, "lon": -74.18810})

    _post(client, [event])

    stored = db_session.get(AnalyticsEvent, event["id"])
    assert (stored.area_lat, stored.area_lon) == (Decimal("41.2"), Decimal("-74.2"))


def test_no_plain_column_holds_the_account_or_the_exact_fix(client, db_session, today, seal_secret):
    hiker = make_profile(db_session)
    event = _event(today, fix={"lat": 41.29871, "lon": -74.18810})

    _post(client, [event], identified=True, headers=auth_headers(hiker.id))

    stored = db_session.get(AnalyticsEvent, event["id"])
    plain = [str(getattr(stored, column.key)) for column in inspect(AnalyticsEvent).mapper.columns if column.key != "sealed"]
    assert not any(hiker.id in value for value in plain)
    assert not any("41.29871" in value or "74.1881" in value for value in plain)


def test_without_a_published_key_the_fix_and_account_are_thrown_away(client, db_session, today):
    """Never kept in the clear to be sealed later: the row says `no_key` and
    holds neither, not even the square."""
    hiker = make_profile(db_session)
    event = _event(today, fix={"lat": 41.29871, "lon": -74.18810})

    _post(client, [event], identified=True, headers=auth_headers(hiker.id))

    stored = db_session.get(AnalyticsEvent, event["id"])
    assert stored.seal == "no_key" and stored.sealed is None
    assert stored.area_lat is None and stored.area_lon is None
    assert stored.user_key == user_key(SERVER_SECRET, hiker.id), "the masked key is not sealed, so it survives"


def test_a_row_with_nothing_to_seal_says_so(client, db_session, today, seal_secret):
    event = _event(today)

    _post(client, [event])

    stored = db_session.get(AnalyticsEvent, event["id"])
    assert stored.seal == "none" and stored.sealed is None and stored.has_fix is False


def test_no_column_could_hold_an_ip_address():
    """EVENTING.md §8: the IP is never written. The cheapest proof is that
    there is nowhere to write it."""
    columns = {column.key for column in inspect(AnalyticsEvent).mapper.columns}

    assert not columns & {"ip", "ip_address", "remote_addr", "client_host", "user_agent"}


# --- anything outside the registry is refused -----------------------------------


@pytest.mark.parametrize(
    "fields",
    [
        {"event": "trail_searched"},
        {"platform": "blackberry"},
        {"trail_name": "Bear Mountain Loop"},
        {"clubs": {"NY NJ Trail Conference": 1.0}},
        {"clubs": {"NYNJTC": 0.5}},
        {"clubs": {}},
        {"club_firsts": ["NYNJTC", "NYNJTC"]},
        {"pageviews": 3},
        {"miles": 4.2},
        {"fix": {"lat": 91, "lon": 0}},
        {"fix": {"lat": 41.3, "lon": -74.2, "label": "home"}},
        {"app_version": "1.2.3 (beta; Pixel 8)"},
    ],
    ids=[
        "an-unregistered-event",
        "an-unknown-platform",
        "a-field-the-registry-lacks",
        "a-club-as-free-text",
        "club-shares-short-of-one-event",
        "an-empty-club-map",
        "a-club-first-twice",
        "pageviews-on-a-map-view",
        "miles-on-a-map-view",
        "a-latitude-off-the-planet",
        "a-labelled-fix",
        "a-version-string-with-spaces",
    ],
)
def test_a_batch_outside_the_registry_is_refused_whole(client, db_session, today, fields):
    good = _event(today)

    response = _post(client, [good, _event(today, **fields)])

    assert response.status_code == 422
    assert db_session.query(AnalyticsEvent).count() == 0, "nothing from a refused batch is stored"


def test_a_session_may_carry_pageviews_and_a_plan_may_carry_miles(client, db_session, today):
    response = _post(
        client,
        [
            _event(today, event="session", pageviews=7, session_length="m1_to_5"),
            _event(today, event="hike_plan_made", miles=12.4, clubs={"NYNJTC": 0.6667, "AMC-DV": 0.3333}),
        ],
    )

    assert response.status_code == 202


def test_a_date_more_than_a_day_ahead_is_refused(client, today):
    response = _post(client, [_event(today + timedelta(days=2))])

    assert response.status_code == 422


def test_a_date_older_than_retention_is_refused(client, today):
    """It would land in a month the rollup has already deleted."""
    response = _post(client, [_event(retention_start(today) - timedelta(days=1))])

    assert response.status_code == 422


def test_a_batch_over_the_cap_is_refused(client, today):
    response = _post(client, [_event(today) for _ in range(201)])

    assert response.status_code == 422


def test_the_same_id_twice_in_one_batch_is_refused(client, today):
    event = _event(today)

    assert _post(client, [event, event]).status_code == 422


# --- the User table ------------------------------------------------------------


def test_the_user_table_sums_a_hikers_events_once(client, db_session, today):
    hiker = make_profile(db_session)
    headers = auth_headers(hiker.id)
    last_month = add_months(month_start(today), -1)
    batch = [
        _event(last_month, event="user_login", platform="ios"),
        _event(today, event="hike_plan_made", miles=10.0),
        _event(today, event="session", pageviews=5),
    ]
    _post(client, batch, identified=True, headers=headers)
    _post(client, batch, identified=True, headers=headers)  # a resend
    _post(client, [_event(today, event="hike_plan_completed", miles=10.0)], identified=True, headers=headers)

    row = db_session.get(AnalyticsUser, user_key(SERVER_SECRET, hiker.id))
    assert (row.logins, row.plans_made, row.plans_completed, row.sessions, row.pageviews) == (1, 1, 1, 1, 5)
    assert (row.plan_miles, row.completed_miles) == (10.0, 10.0)
    assert row.first_seen_on == last_month and row.last_seen_on == today
    assert row.first_platform == "ios" and row.last_platform == "android"
    assert row.first_login_on == last_month and row.first_plan_on == today and row.first_completion_on == today
    yyyymm = [last_month.year * 100 + last_month.month, today.year * 100 + today.month]
    assert row.active_months == yyyymm


def test_a_late_arrival_moves_a_milestone_earlier_but_never_later(client, db_session, today):
    hiker = make_profile(db_session)
    headers = auth_headers(hiker.id)
    _post(client, [_event(today, event="hike_plan_made", miles=3.0)], identified=True, headers=headers)
    earlier = today - timedelta(days=3)
    if earlier < retention_start(today):
        pytest.skip("three days back crosses the retention line today")

    _post(client, [_event(earlier, event="hike_plan_made", miles=3.0)], identified=True, headers=headers)

    row = db_session.get(AnalyticsUser, user_key(SERVER_SECRET, hiker.id))
    assert row.first_plan_on == earlier and row.first_seen_on == earlier and row.last_seen_on == today


def test_signed_out_rows_never_reach_the_user_table(client, db_session, today):
    _post(client, [_event(today), _event(today, event="session", pageviews=2)])

    assert db_session.query(AnalyticsUser).count() == 0


def test_there_is_no_way_to_read_events_back(client):
    assert client.get("/usage-events").status_code == 405


def test_a_second_batch_in_the_same_month_adds_no_second_month(client, db_session, today):
    """`active_months` is a set, kept sorted."""
    hiker = make_profile(db_session)
    headers = auth_headers(hiker.id)

    _post(client, [_event(today)], identified=True, headers=headers)
    _post(client, [_event(today)], identified=True, headers=headers)

    row = db_session.get(AnalyticsUser, user_key(SERVER_SECRET, hiker.id))
    assert row.active_months == [today.year * 100 + today.month]
