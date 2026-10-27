"""Tests for `POST /usage-events` (#1902, app/routers/analytics.py).

The endpoint makes these promises, and each test below is one of them failing
if it is broken:

  - **A token alone links nothing.** A row carries a `user_key` only when the
    batch says the hiker agreed AND the token is valid.
  - **The account and the fix are only ever sealed.** No plain column holds
    either, and without a published key both are thrown away.
  - **Anything outside the registry is refused, one row at a time**, and the
    refusal is counted in `analytics_intake` - the phone keeps no copy, so
    that count is the only trace.
  - **The User table counts each stored row once**, however often a phone
    resends it.
  - **It stores no more than its bounds allow** (app/config.py), and a batch
    past them is turned away whole with a 503 the phone answers by keeping it.
  - **It collects nothing while the six-month delete is not running** - the
    same 503, read from the nightly rollup's heartbeat.
"""

import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import inspect

from app.config import settings
from app.core import analytics_quality as quality
from app.core import analytics_storage
from app.core.analytics_rollup import add_months, month_start, retention_start, run
from app.core.analytics_seal import month_label, month_private_key, month_public_key, new_secret, open_sealed, user_key
from app.core.time import utc_now
from app.models.analytics import (
    AnalyticsEvent,
    AnalyticsIntake,
    AnalyticsMonth,
    AnalyticsMonthly,
    AnalyticsSealKey,
    AnalyticsUser,
)
from tests.factories import make_profile, make_rollup_heartbeat, make_usage_consent
from tests.tokens import auth_headers

SERVER_SECRET = "test-only-user-key-secret"


@pytest.fixture(autouse=True)
def _user_key_secret(monkeypatch):
    monkeypatch.setattr(settings, "analytics_user_key_secret", SERVER_SECRET)


@pytest.fixture(autouse=True)
def _rollup_has_run(db_session):
    """The route collects nothing while the six-month delete is not running;
    every test but the ones about that needs it to look alive."""
    make_rollup_heartbeat(db_session)


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


def _hiker_who_said_yes(db_session):
    """An account whose synced preferences agree to linking - the third thing,
    beside the batch's yes and a valid token, that a linked row needs."""
    hiker = make_profile(db_session)
    make_usage_consent(db_session, hiker, enabled=True, linked=True)
    return hiker


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


def _intake(db_session) -> dict[tuple[str, str], int]:
    """{(app_version, outcome): rows} across every day."""
    counts: dict[tuple[str, str], int] = {}
    for row in db_session.query(AnalyticsIntake).all():
        outcome = row.outcome.value if hasattr(row.outcome, "value") else row.outcome
        counts[(row.app_version, outcome)] = counts.get((row.app_version, outcome), 0) + row.rows
    return counts


# --- what is stored ---------------------------------------------------------


def test_a_signed_out_batch_is_stored_with_no_key(client, db_session, today):
    event = _event(today, month_first=True)

    response = _post(client, [event])

    assert response.status_code == 202
    assert response.json() == {"accepted": 1, "duplicates": 0, "refused": 0}
    stored = db_session.get(AnalyticsEvent, event["id"])
    assert stored.user_key is None and stored.month_first is True


def test_resending_a_batch_stores_nothing_twice(client, db_session, today):
    events = [_event(today), _event(today)]
    _post(client, events)

    response = _post(client, events)

    assert response.json() == {"accepted": 0, "duplicates": 2, "refused": 0}
    assert db_session.query(AnalyticsEvent).count() == 2
    assert _intake(db_session) == {("", "stored"): 2, ("", "duplicate"): 2}


# --- a token alone links nothing ---------------------------------------------


def test_a_hiker_who_said_yes_is_linked_by_their_key(client, db_session, today):
    hiker = _hiker_who_said_yes(db_session)
    event = _event(today)

    _post(client, [event], identified=True, headers=auth_headers(hiker.id))

    assert db_session.get(AnalyticsEvent, event["id"]).user_key == user_key(SERVER_SECRET, hiker.id)


def test_a_token_without_a_yes_links_nothing(client, db_session, today):
    hiker = _hiker_who_said_yes(db_session)
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


def test_an_account_that_never_synced_a_yes_is_stored_unlinked_whatever_the_phone_says(client, db_session, today):
    """The phone's `identified` is one phone's word; the account's synced
    `measurement_linked` is the hiker's, and it reads as no until it is a yes."""
    hiker = make_profile(db_session)
    event = _event(today)

    _post(client, [event], identified=True, headers=auth_headers(hiker.id))

    assert db_session.get(AnalyticsEvent, event["id"]).user_key is None


def test_an_account_that_synced_no_is_stored_unlinked_whatever_the_phone_says(client, db_session, today):
    hiker = make_profile(db_session)
    make_usage_consent(db_session, hiker, enabled=True, linked=False)
    event = _event(today)

    _post(client, [event], identified=True, headers=auth_headers(hiker.id))

    assert db_session.get(AnalyticsEvent, event["id"]).user_key is None
    assert db_session.query(AnalyticsUser).count() == 0


@pytest.mark.parametrize("identified", [True, False])
def test_a_batch_from_an_account_that_turned_measurement_off_stores_nothing(client, db_session, today, identified):
    """A second phone that never heard the hiker turn measurement off does
    not get to measure them: the batch is counted as declined and dropped."""
    hiker = make_profile(db_session)
    make_usage_consent(db_session, hiker, enabled=False, linked=True)

    response = _post(client, [_event(today), _event(today)], identified=identified, headers=auth_headers(hiker.id))

    assert response.status_code == 202
    assert response.json() == {"accepted": 0, "duplicates": 0, "refused": 2}, "refused, so the phone drops the rows"
    assert db_session.query(AnalyticsEvent).count() == 0
    assert _intake(db_session) == {("", "declined"): 2}


def test_with_no_server_secret_nothing_is_ever_linked(client, db_session, today, monkeypatch):
    monkeypatch.setattr(settings, "analytics_user_key_secret", "")
    hiker = _hiker_who_said_yes(db_session)
    event = _event(today)

    _post(client, [event], identified=True, headers=auth_headers(hiker.id))

    assert db_session.get(AnalyticsEvent, event["id"]).user_key is None
    assert db_session.query(AnalyticsUser).count() == 0


# --- the account and the fix are only ever sealed -----------------------------


def test_a_fix_is_sealed_and_opens_to_exactly_what_the_phone_sent(client, db_session, today, seal_secret):
    hiker = _hiker_who_said_yes(db_session)
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
    hiker = _hiker_who_said_yes(db_session)
    event = _event(today, fix={"lat": 41.29871, "lon": -74.18810})

    _post(client, [event], identified=True, headers=auth_headers(hiker.id))

    stored = db_session.get(AnalyticsEvent, event["id"])
    plain = [str(getattr(stored, column.key)) for column in inspect(AnalyticsEvent).mapper.columns if column.key != "sealed"]
    assert not any(hiker.id in value for value in plain)
    assert not any("41.29871" in value or "74.1881" in value for value in plain)


def test_without_a_published_key_the_fix_and_account_are_thrown_away(client, db_session, today):
    """Never kept in the clear to be sealed later: the row says `no_key` and
    holds neither, not even the square."""
    hiker = _hiker_who_said_yes(db_session)
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


# --- anything outside the registry is refused, row by row ------------------------


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
        {"app_version": "1.4.0\n"},
        {"app_version": "1.5.0+build.7"},
        {"app_version": "1.5"},
        {"clubs": {"ABCDEFGHIJKLMNOPQ": 1.0}},
        {"club_firsts": ["ABCDEFGHIJKLMNOPQ"]},
        {"event": "session", "pageviews": 3},
        {"ever_first": True},
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
        "a-version-with-a-trailing-newline",
        "a-version-with-build-metadata",
        "a-version-of-two-parts",
        "a-17-character-club-in-clubs",
        "a-17-character-club-in-club-firsts",
        "a-session-without-its-length",
        "first-ever-off-the-months-first-row",
    ],
)
def test_a_row_outside_the_registry_is_refused_alone(client, db_session, today, fields):
    good = _event(today, app_version="1.4.0")
    bad = _event(today, **{"app_version": "1.5.0", **fields})

    response = _post(client, [good, bad])

    assert response.status_code == 202
    assert response.json() == {"accepted": 1, "duplicates": 0, "refused": 1}
    assert db_session.get(AnalyticsEvent, good["id"]) is not None
    assert db_session.get(AnalyticsEvent, bad["id"]) is None, "the refused row is not stored"
    version = "" if fields.get("app_version") else "1.5.0"
    assert _intake(db_session) == {("1.4.0", "stored"): 1, (version, "invalid"): 1}


def test_a_16_character_club_and_a_pre_release_version_are_stored(client, db_session, today):
    """The longest club id and the pre-release shape the patterns allow, so
    the refusals above are the cap and not something stricter."""
    event = _event(today, app_version="1.5.0-beta.2", clubs={"ABCDEFGHIJKLMNOP": 1.0}, club_firsts=["ABCDEFGHIJKLMNOP"])

    assert _post(client, [event]).json() == {"accepted": 1, "duplicates": 0, "refused": 0}
    assert db_session.get(AnalyticsEvent, event["id"]).app_version == "1.5.0-beta.2"


def test_club_shares_are_stored_as_exactly_one_event(client, db_session, today):
    """0.509 + 0.509 is inside the schema's tolerance and is 1.018 of a plan;
    stored as sent, one such row put the clubs' plans above the app's own."""
    event = _event(today, event="hike_plan_made", miles=8.0, clubs={"GATC": 0.509, "SMHC": 0.509})

    _post(client, [event])

    assert db_session.get(AnalyticsEvent, event["id"]).clubs == {"GATC": 0.5, "SMHC": 0.5}


def test_shares_that_already_add_up_are_stored_unchanged(client, db_session, today):
    event = _event(today, event="hike_plan_made", miles=30.0, clubs={"NYNJTC": 0.6667, "AMC-NY": 0.2667, "_unrecorded": 0.0666})

    _post(client, [event])

    assert db_session.get(AnalyticsEvent, event["id"]).clubs == event["clubs"]


def test_a_month_of_rounded_shares_keeps_the_clubs_plans_within_the_apps(client, db_session, today):
    """The reproduction: one plan at 0.509 + 0.509 was enough for the nightly
    `club_plans_within_total` check to call the month broken, for good."""
    _post(client, [_event(today, event="hike_plan_made", miles=8.0, clubs={"GATC": 0.509, "SMHC": 0.509})])

    run(db_session, today=today)

    assert [f.check_name for f in quality.invariant_findings(db_session) if f.check_name == "club_plans_within_total"] == []


# --- what it will store at all --------------------------------------------------------


def test_a_batch_past_the_days_row_budget_is_turned_away_whole_and_counted(client, db_session, today, monkeypatch):
    monkeypatch.setattr(settings, "analytics_daily_row_budget", 2)
    _post(client, [_event(today), _event(today)])
    late = [_event(today), _event(today), _event(today)]

    response = _post(client, late)

    assert response.status_code == 503
    assert response.headers["Retry-After"] == "3600"
    assert db_session.query(AnalyticsEvent).count() == 2, "nothing past the budget is stored"
    assert _intake(db_session) == {("", "stored"): 2, ("", "over_budget"): 3}


def test_a_table_past_its_storage_ceiling_turns_every_batch_away(client, db_session, today, monkeypatch):
    monkeypatch.setattr(settings, "analytics_storage_ceiling_mb", 0)

    response = _post(client, [_event(today)])

    assert response.status_code == 503 and response.headers["Retry-After"] == "3600"
    assert db_session.query(AnalyticsEvent).count() == 0
    assert _intake(db_session) == {("", "over_budget"): 1}


def test_the_storage_ceiling_counts_rows_held_so_a_deleted_month_lets_batches_in_again(client, db_session, today, monkeypatch):
    """The first ceiling read the table's size on disk, and a Postgres table's
    file does not shrink when rows are deleted (app/core/analytics_storage.py
    has the measurement) - so once met, it would have turned every batch away
    for good. Rows held come down when the rollup deletes a month."""
    monkeypatch.setattr(settings, "analytics_storage_ceiling_mb", 1)
    monkeypatch.setattr(analytics_storage, "STORED_ROW_BYTES", 1024 * 1024 // 2)
    assert _post(client, [_event(today), _event(today)]).status_code == 202

    assert _post(client, [_event(today)]).status_code == 503, "two rows held fill a two-row ceiling"

    run(db_session, today=add_months(today, 7))
    assert db_session.query(AnalyticsEvent).count() == 0, "the month left retention"
    assert _post(client, [_event(today)]).status_code == 202


def test_with_no_rollup_heartbeat_at_all_every_batch_is_paused(client, db_session, today):
    """Nothing is collected that nothing would delete at six months."""
    db_session.query(AnalyticsMonth).delete()
    db_session.commit()

    response = _post(client, [_event(today), _event(today)])

    assert response.status_code == 503 and response.headers["Retry-After"] == "3600"
    assert db_session.query(AnalyticsEvent).count() == 0
    assert _intake(db_session) == {("", "paused"): 2}


def test_a_heartbeat_older_than_the_stale_days_pauses_collection(client, db_session, today):
    stale = utc_now() - timedelta(days=settings.analytics_rollup_stale_days, minutes=1)
    make_rollup_heartbeat(db_session, now=stale)

    assert _post(client, [_event(today)]).status_code == 503
    assert _intake(db_session) == {("", "paused"): 1}


def test_a_heartbeat_inside_the_stale_days_lets_the_batch_in(client, db_session, today):
    make_rollup_heartbeat(db_session, now=utc_now() - timedelta(days=settings.analytics_rollup_stale_days, minutes=-60))

    assert _post(client, [_event(today)]).status_code == 202


def test_a_batch_both_over_budget_and_paused_is_counted_once_as_over_budget(client, db_session, today, monkeypatch):
    monkeypatch.setattr(settings, "analytics_storage_ceiling_mb", 0)
    db_session.query(AnalyticsMonth).delete()
    db_session.commit()

    _post(client, [_event(today)])

    assert _intake(db_session) == {("", "over_budget"): 1}


def test_a_turned_away_batch_is_told_nothing_about_which_bound_it_met(client, db_session, today, monkeypatch):
    monkeypatch.setattr(settings, "analytics_storage_ceiling_mb", 0)
    by_size = _post(client, [_event(today)]).json()
    monkeypatch.setattr(settings, "analytics_storage_ceiling_mb", 250)
    monkeypatch.setattr(settings, "analytics_daily_row_budget", 0)
    by_count = _post(client, [_event(today)]).json()
    monkeypatch.setattr(settings, "analytics_daily_row_budget", 50_000)
    db_session.query(AnalyticsMonth).delete()
    db_session.commit()

    by_pause = _post(client, [_event(today)]).json()

    assert by_size == by_count == by_pause


def test_a_returning_flag_off_the_months_first_row_is_refused(client, db_session, today):
    """`month_returning` means "counted last month too" and only on the row that
    counts this month; anywhere else it would count a phone as returning twice."""
    response = _post(client, [_event(today, month_returning=True)])

    assert response.json()["refused"] == 1


def test_the_three_phone_answers_are_stored_as_sent(client, db_session, today):
    event = _event(today, month_first=True, month_returning=True, kind_month_first=True, signed_in=True)

    _post(client, [event])

    stored = db_session.get(AnalyticsEvent, event["id"])
    assert (stored.month_returning, stored.kind_month_first, stored.signed_in) == (True, True, True)


def test_a_batch_of_nothing_but_refused_rows_is_still_counted(client, db_session, today):
    response = _post(client, [{"not": "an event"}, 7, None])

    assert response.status_code == 202
    assert response.json() == {"accepted": 0, "duplicates": 0, "refused": 3}
    assert _intake(db_session) == {("", "invalid"): 3}


def test_a_session_may_carry_pageviews_and_a_plan_may_carry_miles(client, db_session, today):
    response = _post(
        client,
        [
            _event(today, event="session", pageviews=7, session_length="m1_to_5"),
            _event(today, event="hike_plan_made", miles=12.4, clubs={"NYNJTC": 0.6667, "AMC-DV": 0.3333}),
        ],
    )

    assert response.status_code == 202


def test_a_date_more_than_a_day_ahead_is_refused_and_the_rest_kept(client, db_session, today):
    response = _post(client, [_event(today + timedelta(days=2)), _event(today)])

    assert response.json() == {"accepted": 1, "duplicates": 0, "refused": 1}
    assert _intake(db_session)[("", "future")] == 1


def test_a_date_older_than_retention_is_refused_and_the_rest_kept(client, db_session, today):
    """It would land in a month the rollup has already deleted - and before
    rows were refused one at a time, it took every good row in its batch with it."""
    response = _post(client, [_event(retention_start(today) - timedelta(days=1)), _event(today)])

    assert response.json() == {"accepted": 1, "duplicates": 0, "refused": 1}
    assert _intake(db_session)[("", "too_old")] == 1


def test_a_batch_over_the_cap_is_refused(client, today):
    response = _post(client, [_event(today) for _ in range(201)])

    assert response.status_code == 422


def test_the_same_id_twice_in_one_batch_is_stored_once(client, db_session, today):
    event = _event(today)

    assert _post(client, [event, event]).json() == {"accepted": 1, "duplicates": 1, "refused": 0}
    assert db_session.query(AnalyticsEvent).count() == 1


# --- the User table ------------------------------------------------------------


def test_the_user_table_sums_a_hikers_events_once(client, db_session, today):
    hiker = _hiker_who_said_yes(db_session)
    headers = auth_headers(hiker.id)
    last_month = add_months(month_start(today), -1)
    batch = [
        _event(last_month, event="user_login", platform="ios"),
        _event(today, event="hike_plan_made", miles=10.0),
        _event(today, event="session", pageviews=5, session_length="m1_to_5"),
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
    hiker = _hiker_who_said_yes(db_session)
    headers = auth_headers(hiker.id)
    _post(client, [_event(today, event="hike_plan_made", miles=3.0)], identified=True, headers=headers)
    earlier = today - timedelta(days=3)
    if earlier < retention_start(today):
        pytest.skip("three days back crosses the retention line today")

    _post(client, [_event(earlier, event="hike_plan_made", miles=3.0)], identified=True, headers=headers)

    row = db_session.get(AnalyticsUser, user_key(SERVER_SECRET, hiker.id))
    assert row.first_plan_on == earlier and row.first_seen_on == earlier and row.last_seen_on == today


def test_a_hikers_new_month_is_set_by_their_first_batch_and_never_moved(client, db_session, today):
    hiker = _hiker_who_said_yes(db_session)
    headers = auth_headers(hiker.id)
    _post(client, [_event(today)], identified=True, headers=headers)
    last_month = add_months(month_start(today), -1)

    _post(client, [_event(last_month, platform="ios")], identified=True, headers=headers)  # a second phone, late

    row = db_session.get(AnalyticsUser, user_key(SERVER_SECRET, hiker.id))
    assert row.first_seen_on == last_month, "the milestone does move earlier"
    assert row.new_month == month_start(today), "the month the hiker was counted new in does not"


def test_a_late_row_from_a_second_phone_does_not_take_a_hiker_out_of_hikers_new(client, db_session, today):
    """Reproduced: the late row moved first_seen_on into last month, and the
    hiker dropped out of this month's hikers_new - and last month's, frozen
    or not, never had them."""
    hiker = _hiker_who_said_yes(db_session)
    headers = auth_headers(hiker.id)
    _post(client, [_event(today)], identified=True, headers=headers)
    run(db_session, today=today)
    assert db_session.get(AnalyticsMonthly, (month_start(today), "hikers_new", "*", "*")).value == 1

    _post(client, [_event(add_months(month_start(today), -1))], identified=True, headers=headers)
    run(db_session, today=today)

    assert db_session.get(AnalyticsMonthly, (month_start(today), "hikers_new", "*", "*")).value == 1


def test_the_user_table_keeps_the_day_it_last_changed_and_not_the_time(client, db_session, today):
    """A time of upload is when a hiker found signal."""
    hiker = _hiker_who_said_yes(db_session)

    _post(client, [_event(today)], identified=True, headers=auth_headers(hiker.id))

    assert db_session.get(AnalyticsUser, user_key(SERVER_SECRET, hiker.id)).updated_on == today


def test_signed_out_rows_never_reach_the_user_table(client, db_session, today):
    _post(client, [_event(today), _event(today, event="session", pageviews=2, session_length="under_1m")])

    assert db_session.query(AnalyticsUser).count() == 0


def test_there_is_no_way_to_read_events_back(client):
    assert client.get("/usage-events").status_code == 405


def test_a_second_batch_in_the_same_month_adds_no_second_month(client, db_session, today):
    """`active_months` is a set, kept sorted."""
    hiker = _hiker_who_said_yes(db_session)
    headers = auth_headers(hiker.id)

    _post(client, [_event(today)], identified=True, headers=headers)
    _post(client, [_event(today)], identified=True, headers=headers)

    row = db_session.get(AnalyticsUser, user_key(SERVER_SECRET, hiker.id))
    assert row.active_months == [today.year * 100 + today.month]
