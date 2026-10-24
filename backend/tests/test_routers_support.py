"""Tests for the `/support` router (#1876, features/SUPPORTING_OURHIKE.md).

What these hold: a paid choice is recorded against the caller's VERIFIED
email and never a typed one; a store-app choice travels by email and never as
a checkout link; Stop is recorded at once, emails the founder to cancel it by
hand, and is idempotent; a webhook is believed only with Buy Me a Coffee's
signature, test events and repeated deliveries change nothing, and a
membership meets the choice it belongs to by email; and the published total
counts what started, not what was chosen.
"""

import hashlib
import hmac
import json
import uuid
from datetime import datetime

import pytest

from app.config import settings
from app.core.support import year_total
from app.models.support import SupportCadence, SupportChoice, SupportStatus
from tests.tokens import auth_headers

SECRET = "whsec-test"
CHECKOUT = "https://buymeacoffee.com/ourhike/membership"


class Provider:
    """A stand-in for SES, as tests/test_nomination_mail.py builds one."""

    def __init__(self) -> None:
        self.sent: list[dict] = []

    def send_email(self, **kwargs):
        self.sent.append(kwargs)
        return {"MessageId": f"ses-{len(self.sent)}"}


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setattr(settings, "buymeacoffee_checkout_url", CHECKOUT)
    monkeypatch.setattr(settings, "buymeacoffee_webhook_secret", SECRET)
    monkeypatch.setattr(settings, "support_notify_address", "founder@ourhike.org")
    monkeypatch.setattr(settings, "mail_enabled", True)
    monkeypatch.setattr(settings, "mail_allowed_suffixes", "")
    provider = Provider()
    monkeypatch.setattr("app.routers.support.ses_client", lambda: provider)
    return provider


def _choose(client, user_id, email="hiker@example.com", **body):
    return client.put(
        "/support/me",
        json={"amount_cents": 1000, "accounting_email": False, "delivery": "redirect", **body},
        headers=auth_headers(user_id, email=email),
    )


def _deliver(client, envelope, *, secret=SECRET):
    raw = json.dumps(envelope).encode()
    signature = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return client.post(
        "/support/webhooks/buymeacoffee",
        content=raw,
        headers={"x-signature-sha256": signature, "content-type": "application/json"},
    )


def _membership(kind, *, email="hiker@example.com", sub_id=777, amount=10, live=True, **data):
    return {
        "event_id": 1,
        "type": kind,
        "live_mode": live,
        "created": 1790812800,
        "attempt": 1,
        "data": {
            "object": "membership",
            "id": sub_id,
            "psp_id": "sub_1Test",
            "duration_type": "year",
            "status": "active",
            "supporter_email": email,
            "amount": amount,
            "currency": "USD",
            "started_at": 1790812800,
            **data,
        },
    }


# ---- Reading and choosing ----


def test_no_choice_reads_as_none_rather_than_missing(client):
    response = client.get("/support/me", headers=auth_headers(str(uuid.uuid4())))

    assert response.status_code == 200
    assert response.json()["status"] == "none"


def test_reading_requires_authentication(client):
    assert client.get("/support/me").status_code == 401


def test_a_website_choice_is_pending_and_answers_with_the_checkout(client, configured):
    response = _choose(client, str(uuid.uuid4()))

    assert response.status_code == 200
    body = response.json()
    assert body["support"]["status"] == "pending"
    assert body["support"]["amount_cents"] == 1000
    assert body["support"]["email"] == "hiker@example.com"
    assert body["checkout_url"] == CHECKOUT
    assert body["emailed"] is False


def test_the_email_is_the_tokens_never_one_the_request_carries(client, configured):
    """A typed address could point a stranger's payment at this account."""
    response = client.put(
        "/support/me",
        json={"amount_cents": 1000, "delivery": "redirect", "email": "someone-else@example.com"},
        headers=auth_headers(str(uuid.uuid4()), email="Hiker@Example.com "),
    )

    assert response.json()["support"]["email"] == "hiker@example.com"


def test_a_sign_in_with_no_email_cannot_choose(client, configured):
    response = client.put(
        "/support/me",
        json={"amount_cents": 1000, "delivery": "redirect"},
        headers=auth_headers(str(uuid.uuid4())),
    )
    assert response.status_code == 422


@pytest.mark.parametrize("amount", [0, 500, 1001, 100000])
def test_only_the_three_paid_answers_are_accepted(client, configured, amount):
    assert _choose(client, str(uuid.uuid4()), amount_cents=amount).status_code == 422


def test_with_no_checkout_configured_the_website_path_says_not_yet(client, monkeypatch):
    monkeypatch.setattr(settings, "buymeacoffee_checkout_url", "")
    assert _choose(client, str(uuid.uuid4())).status_code == 503


def test_a_store_app_choice_is_emailed_and_never_answers_with_a_link(client, configured):
    response = _choose(client, str(uuid.uuid4()), delivery="email", amount_cents=10000)

    body = response.json()
    assert body["checkout_url"] is None
    assert body["emailed"] is True
    [message] = configured.sent
    assert message["Destination"]["ToAddresses"] == ["hiker@example.com"]
    assert CHECKOUT in message["Content"]["Raw"]["Data"].decode()


def test_a_second_choice_while_pending_changes_the_amount_rather_than_adding_one(client, configured, db_session):
    user_id = str(uuid.uuid4())
    _choose(client, user_id, amount_cents=1000)
    _choose(client, user_id, amount_cents=10000)

    rows = db_session.query(SupportChoice).filter(SupportChoice.profile_id == user_id).all()
    assert [row.amount_cents for row in rows] == [10000]


# ---- Stop ----


def test_stop_is_recorded_at_once_and_the_founder_is_emailed_to_cancel_it(client, configured):
    user_id = str(uuid.uuid4())
    _choose(client, user_id)

    response = client.post("/support/me/stop", headers=auth_headers(user_id))

    assert response.status_code == 200
    assert response.json()["status"] == "stop_requested"
    assert response.json()["stop_requested_at"] is not None
    [notice] = configured.sent
    assert notice["Destination"]["ToAddresses"] == ["founder@ourhike.org"]
    assert "hiker@example.com" in notice["Content"]["Raw"]["Data"].decode()


def test_pressing_stop_twice_sends_one_notice(client, configured):
    user_id = str(uuid.uuid4())
    _choose(client, user_id)
    client.post("/support/me/stop", headers=auth_headers(user_id))
    second = client.post("/support/me/stop", headers=auth_headers(user_id))

    assert second.status_code == 200
    assert len(configured.sent) == 1


def test_stop_with_nothing_running_is_404(client):
    assert client.post("/support/me/stop", headers=auth_headers(str(uuid.uuid4()))).status_code == 404


def test_a_stop_is_still_recorded_when_no_notice_can_be_sent(client, configured, monkeypatch):
    monkeypatch.setattr(settings, "support_notify_address", "")
    user_id = str(uuid.uuid4())
    _choose(client, user_id)

    response = client.post("/support/me/stop", headers=auth_headers(user_id))

    assert response.json()["status"] == "stop_requested"
    assert configured.sent == []


# ---- The webhook ----


def test_a_delivery_without_the_signature_is_refused(client, configured):
    raw = json.dumps(_membership("membership.started")).encode()
    response = client.post("/support/webhooks/buymeacoffee", content=raw)
    assert response.status_code == 401


def test_a_delivery_signed_with_another_secret_is_refused(client, configured):
    assert _deliver(client, _membership("membership.started"), secret="not-ours").status_code == 401


def test_with_no_secret_configured_every_delivery_is_refused(client, monkeypatch):
    monkeypatch.setattr(settings, "buymeacoffee_webhook_secret", "")
    assert _deliver(client, _membership("membership.started"), secret="anything").status_code == 503


def test_a_membership_meets_the_choice_made_with_its_email(client, configured, db_session):
    user_id = str(uuid.uuid4())
    _choose(client, user_id)

    response = _deliver(client, _membership("membership.started", email="HIKER@example.com"))

    assert response.json() == {"result": "active"}
    mine = client.get("/support/me", headers=auth_headers(user_id)).json()
    assert mine["status"] == "active"
    assert mine["started_at"] is not None
    row = db_session.query(SupportChoice).filter(SupportChoice.profile_id == user_id).one()
    assert (row.provider_ref, row.psp_ref) == ("777", "sub_1Test")


def test_a_retried_delivery_changes_nothing_the_first_did_not(client, configured, db_session):
    _choose(client, str(uuid.uuid4()))
    _deliver(client, _membership("membership.started"))
    _deliver(client, _membership("membership.started"))

    assert db_session.query(SupportChoice).count() == 1


def test_a_dashboard_test_event_is_ignored(client, configured, db_session):
    response = _deliver(client, _membership("membership.started", live=False))

    assert response.json() == {"result": "ignored_test_event"}
    assert db_session.query(SupportChoice).count() == 0


def test_a_one_off_coffee_is_acknowledged_and_left_alone(client, configured, db_session):
    envelope = {**_membership("membership.started"), "type": "donation.created"}
    assert _deliver(client, envelope).json() == {"result": "ignored_event_type"}
    assert db_session.query(SupportChoice).count() == 0


def test_a_membership_from_the_page_directly_is_kept_unattached(client, configured, db_session):
    _deliver(client, _membership("membership.started", email="walk-in@example.com", amount=100))

    [row] = db_session.query(SupportChoice).all()
    assert row.profile_id is None
    assert (row.status, row.amount_cents) == (SupportStatus.active, 10000)


def test_cancelled_closes_a_requested_stop(client, configured):
    user_id = str(uuid.uuid4())
    _choose(client, user_id)
    _deliver(client, _membership("membership.started"))
    client.post("/support/me/stop", headers=auth_headers(user_id))

    _deliver(client, _membership("membership.cancelled", canceled_at=1791000000))

    mine = client.get("/support/me", headers=auth_headers(user_id)).json()
    assert mine["status"] == "stopped"
    assert mine["ended_at"] is not None


def test_an_update_does_not_undo_a_stop_nobody_has_cancelled_yet(client, configured):
    user_id = str(uuid.uuid4())
    _choose(client, user_id)
    _deliver(client, _membership("membership.started"))
    client.post("/support/me/stop", headers=auth_headers(user_id))

    _deliver(client, _membership("membership.updated"))

    assert client.get("/support/me", headers=auth_headers(user_id)).json()["status"] == "stop_requested"


# ---- The published total ----


def test_the_total_counts_what_started_and_not_what_was_only_chosen(client, configured):
    _choose(client, str(uuid.uuid4()))  # chosen, never paid
    _choose(client, str(uuid.uuid4()), email="second@example.com")
    _deliver(client, _membership("membership.started", email="second@example.com", amount=100))

    body = client.get("/support/total").json()

    assert body["total_cents"] == 10000
    assert body["supporters"] == 1


def test_a_yearly_supporter_counts_again_once_their_anniversary_passes(db_session):
    db_session.add(
        SupportChoice(
            email="a@example.com",
            amount_cents=1000,
            cadence=SupportCadence.year,
            status=SupportStatus.active,
            started_at=datetime(2025, 3, 1),
        )
    )
    db_session.commit()

    assert year_total(db_session, 2025, now=datetime(2026, 2, 1)) == (1000, 1)
    assert year_total(db_session, 2026, now=datetime(2026, 2, 1)) == (0, 0)
    assert year_total(db_session, 2026, now=datetime(2026, 3, 2)) == (1000, 1)


def test_a_stopped_supporter_is_not_counted_after_they_ended(db_session):
    db_session.add(
        SupportChoice(
            email="a@example.com",
            amount_cents=1000,
            status=SupportStatus.stopped,
            started_at=datetime(2025, 3, 1),
            ended_at=datetime(2025, 9, 1),
        )
    )
    db_session.commit()

    assert year_total(db_session, 2026, now=datetime(2026, 6, 1)) == (0, 0)


def test_deleting_the_account_asks_for_a_stop_and_emails_the_founder(client, configured, monkeypatch):
    """A deleted account can no longer reach Stop, so the deletion presses it."""
    monkeypatch.setattr("app.routers.profiles.ses_client", lambda: configured)
    user_id = str(uuid.uuid4())
    _choose(client, user_id)
    _deliver(client, _membership("membership.started"))

    assert client.delete("/profiles/me", headers=auth_headers(user_id)).status_code == 200

    [notice] = configured.sent
    assert notice["Destination"]["ToAddresses"] == ["founder@ourhike.org"]
