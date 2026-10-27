"""A hiker's usage rows, on the way out of OurHike (#1902).

Deleting an account deletes the usage events it linked and its User-table
row; the export hands the hiker the plain half of those events and says why
the sealed half is not in it. Rows a hiker sent without saying yes are
nobody's and are left alone - which is what they were sent for.
"""

import uuid
from datetime import date

import pytest

from app.config import settings
from app.core.account_deletion import delete_account
from app.core.account_export import NOT_INCLUDED, build_export
from app.core.analytics_seal import user_key
from app.models.analytics import AnalyticsEvent, AnalyticsUser
from tests.factories import make_profile
from tests.tokens import auth_headers

SERVER_SECRET = "test-only-user-key-secret"


@pytest.fixture(autouse=True)
def _user_key_secret(monkeypatch):
    monkeypatch.setattr(settings, "analytics_user_key_secret", SERVER_SECRET)


def _linked_rows(db_session, profile_id: str) -> str:
    key = user_key(SERVER_SECRET, profile_id)
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
    assert archive["your_usage_summary"]["plans_made"] == 1


def test_the_export_says_why_positions_are_not_in_it():
    assert any("sealed with a key no OurHike server holds" in sentence for sentence in NOT_INCLUDED)


def test_with_no_server_secret_there_is_nothing_linked_to_find(db_session, monkeypatch):
    hiker = make_profile(db_session)
    _linked_rows(db_session, hiker.id)
    monkeypatch.setattr(settings, "analytics_user_key_secret", "")

    assert build_export(db_session, hiker)["usage_events_linked_to_you"] == []
    assert delete_account(db_session, hiker).usage_events_deleted == 0
