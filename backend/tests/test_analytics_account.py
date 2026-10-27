"""A hiker's usage rows, on the way out of OurHike (#1902).

Deleting an account deletes the usage events it linked and its User-table
rows; the export hands the hiker every plain column of those events and says
why the sealed one is not in it; taking back a yes unlinks them. Each finds
the rows under every secret the key was ever made with. Rows a hiker sent
without saying yes are nobody's and are left alone - which is what they were
sent for.
"""

import logging
import uuid
from datetime import date

import pytest
from sqlalchemy import inspect

from app.config import settings
from app.core.account_deletion import delete_account
from app.core.account_export import NOT_INCLUDED, USAGE_NOT_LOOKED_UP, build_export
from app.core.analytics_accounts import LinkedUsageUnreachable
from app.core.analytics_seal import user_key
from app.models.analytics import AnalyticsEvent, AnalyticsUser, SealState
from app.models.preferences import UserPreferences
from app.models.profile import Profile
from tests.factories import make_profile, make_usage_consent
from tests.test_routers_preferences import _valid_preferences
from tests.tokens import auth_headers

SERVER_SECRET = "test-only-user-key-secret"
OLD_SECRET = "the-secret-before-the-rotation"


@pytest.fixture(autouse=True)
def _user_key_secret(monkeypatch):
    monkeypatch.setattr(settings, "analytics_user_key_secret", SERVER_SECRET)
    monkeypatch.setattr(settings, "analytics_user_key_previous_secrets", "")


@pytest.fixture()
def profile_log_lines(monkeypatch):
    """What app.routers.profiles logs. Alembic's fileConfig, run earlier in the
    same process by tests/test_migrations.py, disables the `app` loggers -
    tests/test_logs.py `lines` has the full story - so the flag is cleared."""
    logger = logging.getLogger("app.routers.profiles")
    monkeypatch.setattr(logger, "disabled", False)
    monkeypatch.setattr(logging.getLogger("app"), "disabled", False)
    captured: list[str] = []

    class Collector(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            captured.append(record.getMessage())

    collector = Collector()
    logger.addHandler(collector)
    yield captured
    logger.removeHandler(collector)


def _linked_rows(db_session, profile_id: str, *, secret: str = SERVER_SECRET) -> str:
    key = user_key(secret, profile_id)
    db_session.add_all(
        [
            AnalyticsEvent(
                id=str(uuid.uuid4()),
                local_date=date(2026, 10, 3),
                received_on=date(2026, 10, 3),
                event="hike_plan_made",
                platform="ios",
                user_key=key,
                miles=8.5,
                clubs={"NYNJTC": 1.0},
                seal="sealed",
                sealed=b"\x01" + b"\x00" * 80,
            ),
            AnalyticsUser(
                user_key=key,
                first_seen_on=date(2026, 10, 3),
                new_month=date(2026, 10, 1),
                last_seen_on=date(2026, 10, 3),
                first_platform="ios",
                last_platform="ios",
                plans_made=1,
                plan_miles=8.5,
                active_months=[202610],
            ),
        ]
    )
    db_session.commit()
    return key


def _unlinked_row(db_session) -> str:
    event = AnalyticsEvent(
        id=str(uuid.uuid4()),
        local_date=date(2026, 10, 3),
        received_on=date(2026, 10, 3),
        event="session",
        platform="ios",
        pageviews=3,
    )
    db_session.add(event)
    db_session.commit()
    return event.id


def test_deleting_an_account_deletes_the_usage_it_linked(db_session):
    hiker = make_profile(db_session)
    key = _linked_rows(db_session, hiker.id)

    summary = delete_account(db_session, hiker)
    db_session.commit()

    assert summary.usage_events_deleted == 1
    assert db_session.query(AnalyticsEvent).filter(AnalyticsEvent.user_key == key).count() == 0
    assert db_session.get(AnalyticsUser, key) is None


def test_deleting_an_account_leaves_rows_nobody_was_linked_to(db_session):
    hiker = make_profile(db_session)
    _linked_rows(db_session, hiker.id)
    unlinked = _unlinked_row(db_session)

    delete_account(db_session, hiker)
    db_session.commit()

    assert db_session.get(AnalyticsEvent, unlinked) is not None


def test_deleting_one_account_leaves_another_hikers_usage(db_session):
    hiker, neighbour = make_profile(db_session), make_profile(db_session)
    _linked_rows(db_session, hiker.id)
    theirs = _linked_rows(db_session, neighbour.id)

    delete_account(db_session, hiker)
    db_session.commit()

    assert db_session.get(AnalyticsUser, theirs) is not None


def test_the_deletion_receipt_counts_the_usage_events(client, db_session):
    hiker = make_profile(db_session)
    _linked_rows(db_session, hiker.id)

    response = client.delete("/profiles/me", headers=auth_headers(hiker.id))

    assert response.status_code == 200
    assert response.json()["usage_events_deleted"] == 1


def test_the_export_carries_the_plain_half_and_never_the_sealed_blob(db_session):
    hiker = make_profile(db_session)
    _linked_rows(db_session, hiker.id)
    _unlinked_row(db_session)

    archive = build_export(db_session, hiker)

    events = archive["usage_events_linked_to_you"]
    assert len(events) == 1, "rows nobody was linked to are not anybody's to export"
    assert events[0]["event"] == "hike_plan_made" and events[0]["clubs"] == {"NYNJTC": 1.0}
    assert "sealed" not in events[0]
    assert [summary["plans_made"] for summary in archive["your_usage_summaries"]] == [1]


def test_the_export_carries_every_plain_column_of_an_event_and_only_leaves_out_the_sealed_one(db_session):
    """A hand-kept column list left out week_first, month_first, ever_first,
    club_firsts, kind_month_first, month_returning, signed_in and user_key."""
    hiker = make_profile(db_session)
    _linked_rows(db_session, hiker.id)

    (event,) = build_export(db_session, hiker)["usage_events_linked_to_you"]

    assert set(event) == {column.key for column in inspect(AnalyticsEvent).mapper.columns} - {"sealed"}


def test_the_export_says_why_positions_are_not_in_it():
    assert any("sealed with a key no OurHike server holds" in sentence for sentence in NOT_INCLUDED)


# --- every secret the key was made with -------------------------------------------------


def test_the_secrets_come_current_first_with_blanks_and_repeats_skipped(monkeypatch):
    monkeypatch.setattr(settings, "analytics_user_key_previous_secrets", f" {OLD_SECRET} ,, {SERVER_SECRET},older")

    assert settings.analytics_user_key_secrets == (SERVER_SECRET, OLD_SECRET, "older")


def test_rows_keyed_under_a_previous_secret_are_exported_and_deleted_with_the_account(db_session, monkeypatch):
    """After a rotation the old rows stay under the old key; without the
    previous list, deleting the account left them behind, still linked."""
    hiker = make_profile(db_session)
    old_key = _linked_rows(db_session, hiker.id, secret=OLD_SECRET)
    new_key = _linked_rows(db_session, hiker.id)
    monkeypatch.setattr(settings, "analytics_user_key_previous_secrets", OLD_SECRET)

    archive = build_export(db_session, hiker)
    summary = delete_account(db_session, hiker)
    db_session.commit()

    assert len(archive["usage_events_linked_to_you"]) == 2
    assert [row["user_key"] for row in archive["your_usage_summaries"]] == [new_key, old_key]
    assert summary.usage_events_deleted == 2
    assert db_session.query(AnalyticsUser).count() == 0


# --- no secret at all ----------------------------------------------------------------------


def test_with_no_secret_but_linked_usage_held_deletion_refuses_and_changes_nothing(
    client, db_session, monkeypatch, profile_log_lines
):
    """Deleting the rest would hand the hiker a receipt while their usage
    stayed linked in the table - the one answer worse than refusing."""
    hiker = make_profile(db_session)
    key = _linked_rows(db_session, hiker.id)
    monkeypatch.setattr(settings, "analytics_user_key_secret", "")

    response = client.delete("/profiles/me", headers=auth_headers(hiker.id))

    assert response.status_code == 503
    assert response.json()["detail"] == "The account was not deleted. Nothing was changed."
    db_session.expire_all()
    assert db_session.get(Profile, hiker.id).deleted_at is None
    assert db_session.get(AnalyticsUser, key) is not None
    assert profile_log_lines and all(hiker.id not in line and key not in line for line in profile_log_lines)


def test_with_no_secret_the_core_refuses_before_deleting_anything(db_session, monkeypatch):
    hiker = make_profile(db_session)
    make_usage_consent(db_session, hiker)
    _linked_rows(db_session, hiker.id)
    monkeypatch.setattr(settings, "analytics_user_key_secret", "")

    with pytest.raises(LinkedUsageUnreachable):
        delete_account(db_session, hiker)

    db_session.rollback()
    assert hiker.deleted_at is None
    assert db_session.get(UserPreferences, hiker.id) is not None, "the preferences, deleted early on, are still there"


def test_with_no_secret_and_nothing_linked_anywhere_deletion_goes_ahead(db_session, monkeypatch):
    """A deployment that never linked a row has nothing to find, and says so truthfully."""
    hiker = make_profile(db_session)
    _unlinked_row(db_session)
    monkeypatch.setattr(settings, "analytics_user_key_secret", "")

    assert delete_account(db_session, hiker).usage_events_deleted == 0


def test_with_no_secret_the_export_says_linked_usage_could_not_be_looked_up(db_session, monkeypatch):
    hiker = make_profile(db_session)
    _linked_rows(db_session, hiker.id)
    monkeypatch.setattr(settings, "analytics_user_key_secret", "")

    archive = build_export(db_session, hiker)

    assert archive["usage_events_linked_to_you"] == []
    assert USAGE_NOT_LOOKED_UP in archive["what_this_file_does_not_contain"]


def test_an_export_that_could_look_does_not_say_it_could_not(db_session):
    hiker = make_profile(db_session)

    assert USAGE_NOT_LOOKED_UP not in build_export(db_session, hiker)["what_this_file_does_not_contain"]


# --- taking back a yes ------------------------------------------------------------------------


def _sync(client, hiker, **measurement):
    response = client.put("/preferences/me", json=_valid_preferences(**measurement), headers=auth_headers(hiker.id))
    assert response.status_code == 200, response.text


@pytest.mark.parametrize(
    "taken_back",
    [{"measurement_linked": False}, {"measurement_enabled": False, "measurement_linked": True}],
    ids=["linking-turned-off", "measurement-turned-off"],
)
def test_taking_back_a_yes_unlinks_the_usage_it_linked(client, db_session, monkeypatch, taken_back):
    """The events stay, counted like any unlinked row; the User-table rows,
    which are only ever about one hiker, go - under every secret."""
    hiker = make_profile(db_session)
    _sync(client, hiker, measurement_enabled=True, measurement_linked=True)
    old_key = _linked_rows(db_session, hiker.id, secret=OLD_SECRET)
    new_key = _linked_rows(db_session, hiker.id)
    monkeypatch.setattr(settings, "analytics_user_key_previous_secrets", OLD_SECRET)

    _sync(client, hiker, **taken_back)

    db_session.expire_all()
    assert db_session.query(AnalyticsUser).filter(AnalyticsUser.user_key.in_([old_key, new_key])).count() == 0
    assert db_session.query(AnalyticsEvent).count() == 2, "the events stay"
    assert db_session.query(AnalyticsEvent).filter(AnalyticsEvent.user_key.isnot(None)).count() == 0


def test_taking_back_a_yes_drops_the_sealed_account_and_keeps_the_count(client, db_session):
    """The sealed blob holds the account id beside the fix, and this server
    cannot take the account out alone - so the blob goes whole, and a later
    account deletion, which finds rows by their key, has nothing of this
    hiker left to miss. The row, its event and its square stay."""
    hiker = make_profile(db_session)
    _sync(client, hiker, measurement_enabled=True, measurement_linked=True)
    _linked_rows(db_session, hiker.id)
    event = db_session.query(AnalyticsEvent).one()
    event.has_fix, event.area_lat, event.area_lon = True, 41.2, -74.1
    db_session.commit()

    _sync(client, hiker, measurement_linked=False)

    db_session.expire_all()
    event = db_session.query(AnalyticsEvent).one()
    assert (event.user_key, event.sealed, event.seal) == (None, None, SealState.unlinked)
    assert (event.event, event.has_fix, float(event.area_lat), float(event.area_lon)) == (
        "hike_plan_made",
        True,
        41.2,
        -74.1,
    )


def test_taking_back_a_yes_leaves_a_row_with_nothing_sealed_as_it_was(client, db_session):
    """A linked row whose month had no published key sealed nothing
    (`no_key`); there is no blob to drop, and it must not claim one went."""
    hiker = make_profile(db_session)
    _sync(client, hiker, measurement_enabled=True, measurement_linked=True)
    _linked_rows(db_session, hiker.id)
    event = db_session.query(AnalyticsEvent).one()
    event.seal, event.sealed = SealState.no_key, None
    db_session.commit()

    _sync(client, hiker, measurement_linked=False)

    db_session.expire_all()
    assert db_session.query(AnalyticsEvent).one().seal == SealState.no_key


def test_a_sync_that_keeps_the_yes_unlinks_nothing(client, db_session):
    hiker = make_profile(db_session)
    _sync(client, hiker, measurement_enabled=True, measurement_linked=True)
    key = _linked_rows(db_session, hiker.id)

    _sync(client, hiker, measurement_enabled=True, measurement_linked=True, theme="light")

    db_session.expire_all()
    assert db_session.get(AnalyticsUser, key) is not None


def test_a_no_that_was_never_a_yes_touches_nobodys_rows(client, db_session):
    hiker, neighbour = make_profile(db_session), make_profile(db_session)
    make_usage_consent(db_session, hiker, linked=None)
    theirs = _linked_rows(db_session, neighbour.id)

    _sync(client, hiker, measurement_linked=False)

    db_session.expire_all()
    assert db_session.get(AnalyticsUser, theirs) is not None
    assert db_session.query(AnalyticsEvent).filter(AnalyticsEvent.sealed.isnot(None)).count() == 1
