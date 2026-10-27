"""Tests for the `/support` router (#1876, features/SUPPORTING_OURHIKE.md).

What these hold: a paid choice is recorded against the caller's VERIFIED
email and never a typed one; a store-app choice travels by email, at most
once a day, and never as a checkout link; Stop on a pending choice clears it
at once, and on a running payment is recorded, asks whoever cancels it, is
retried until somebody is told, and ends with the hiker emailed; a webhook
is believed only with the provider's signature, and a payment meets a choice
by the provider's id - by email only when it starts, for the same amount,
after the choice was made; a late or repeated event never undoes a later
one; every event is logged without a name or a note; and the published total
counts dollars that started, not what was chosen.

The `# P<n>` and `# B<n>` / `# S<n>` marks name the #1885 security and
architecture reviews' findings each test answers.
"""

import email
import hashlib
import hmac
import json
import time
import uuid
from datetime import datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.core import support as support_core
from app.core.mail import is_suppressed
from app.core.support import year_total
from app.core.support_providers import PROVIDERS
from app.core.time import utc_now
from app.models.mail import EmailSend, MailPurpose
from app.models.support import SupportCadence, SupportChoice, SupportEvent, SupportStatus
from app.routers.support import clear_total_cache
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

    def to(self, address):
        return [m for m in self.sent if m["Destination"]["ToAddresses"] == [address]]


def _text(message) -> str:
    return message["Content"]["Raw"]["Data"].decode()


@pytest.fixture(autouse=True)
def _fresh_total():
    clear_total_cache()
    yield
    clear_total_cache()


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setattr(settings, "support_provider", "buymeacoffee")
    monkeypatch.setattr(settings, "buymeacoffee_checkout_url", CHECKOUT)
    monkeypatch.setattr(settings, "buymeacoffee_webhook_secret", SECRET)
    monkeypatch.setattr(settings, "buymeacoffee_level_ids", "")
    monkeypatch.setattr(settings, "support_notify_address", "founder@ourhike.org")
    monkeypatch.setattr(settings, "api_public_url", "")
    monkeypatch.setattr(settings, "mail_enabled", True)
    monkeypatch.setattr(settings, "mail_allowed_suffixes", "")
    provider = Provider()
    monkeypatch.setattr("app.routers.support.ses_client", lambda: provider)
    monkeypatch.setattr("app.routers.profiles.ses_client", lambda: provider)
    return provider


def _choose(client, user_id, email="hiker@example.com", **body):
    return client.put(
        "/support/me",
        json={"amount_cents": 1000, "accounting_email": False, "delivery": "redirect", **body},
        headers=auth_headers(user_id, email=email),
    )


def _me(client, user_id, email="hiker@example.com"):
    return client.get("/support/me", headers=auth_headers(user_id, email=email)).json()


def _stop(client, user_id):
    return client.post("/support/me/stop", headers=auth_headers(user_id))


def _deliver(client, envelope, *, secret=SECRET, provider="buymeacoffee"):
    raw = json.dumps(envelope).encode()
    signature = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return client.post(
        f"/support/webhooks/{provider}",
        content=raw,
        headers={"x-signature-sha256": signature, "content-type": "application/json"},
    )


def _membership(kind, *, email="hiker@example.com", sub_id=777, amount=10, live=True, created=None, **data):
    """A Buy Me a Coffee membership event, shaped as its webhook spec says.
    `created` defaults to now: a payment meets a choice only if it began
    after the choice was made."""
    created = int(time.time()) if created is None else created
    return {
        "event_id": uuid.uuid4().int % 10**9,
        "type": kind,
        "live_mode": live,
        "created": created,
        "attempt": 1,
        "data": {
            "object": "membership",
            "id": sub_id,
            "supporter_id": 4242,
            "psp_id": "sub_1Test",
            "membership_level_id": 11,
            "duration_type": "year",
            "status": "active",
            "supporter_email": email,
            "supporter_name": "Ramen Bomb",
            "support_note": "for the maps",
            "amount": amount,
            "currency": "USD",
            "started_at": created,
            "current_period_end": created + 365 * 86400,
            **data,
        },
    }


@pytest.fixture
def t0():
    """Now, in the provider's Unix seconds, for tests that order events."""
    return int(time.time())


def _paying(client, user_id, **membership):
    """A hiker who chose $10 in the app and whose payment then started."""
    _choose(client, user_id)
    assert _deliver(client, _membership("membership.started", **membership)).json() == {"result": "active"}


# ---- Reading and choosing ----


def test_no_choice_reads_as_none_rather_than_missing(client, configured):
    body = _me(client, str(uuid.uuid4()))

    assert body["status"] == "none"
    assert (body["supporting"], body["can_stop"], body["can_choose"]) == (False, False, True)


def test_reading_requires_authentication(client):
    assert client.get("/support/me").status_code == 401


def test_a_website_choice_is_pending_and_answers_with_the_checkout(client, configured):
    response = _choose(client, str(uuid.uuid4()))

    assert response.status_code == 200
    body = response.json()
    assert body["support"]["status"] == "pending"
    assert body["support"]["amount_cents"] == 1000
    assert body["support"]["email"] == "hiker@example.com"
    assert body["support"]["provider_label"] == "Buy Me a Coffee"
    assert (body["support"]["supporting"], body["support"]["can_stop"], body["support"]["can_choose"]) == (
        False,
        True,
        True,
    )
    assert body["checkout_url"] == CHECKOUT
    assert body["emailed"] is False


def test_a_choice_keeps_the_consent_record_a_provider_move_needs(client, configured, db_session):
    user_id = str(uuid.uuid4())
    _choose(client, user_id, accounting_email=True, delivery="email")

    row = db_session.query(SupportChoice).one()
    assert row.terms_version is not None
    assert row.delivery == "email"
    assert row.chosen_amount_cents == 1000
    assert row.accounting_email_at is not None
    assert row.migrate_notice_at is not None


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


def test_with_no_checkout_configured_the_website_path_says_not_yet(client, configured, monkeypatch, db_session):
    monkeypatch.setattr(settings, "buymeacoffee_checkout_url", "")
    assert _choose(client, str(uuid.uuid4())).status_code == 503
    assert db_session.query(SupportChoice).count() == 0


def test_a_checkout_that_is_not_https_is_never_handed_out(client, configured, monkeypatch):
    monkeypatch.setattr(settings, "buymeacoffee_checkout_url", "javascript:alert(1)")
    assert _choose(client, str(uuid.uuid4())).status_code == 503


def test_with_no_known_provider_nothing_can_be_chosen(client, configured, monkeypatch):
    monkeypatch.setattr(settings, "support_provider", "nobody")
    assert _choose(client, str(uuid.uuid4())).status_code == 503
    assert _me(client, str(uuid.uuid4()))["can_choose"] is False


def test_a_store_app_choice_is_emailed_and_never_answers_with_a_link(client, configured):
    response = _choose(client, str(uuid.uuid4()), delivery="email", amount_cents=10000)

    body = response.json()
    assert body["checkout_url"] is None
    assert body["emailed"] is True
    [message] = configured.sent
    assert message["Destination"]["ToAddresses"] == ["hiker@example.com"]
    assert CHECKOUT in _text(message)


def test_the_setup_link_goes_once_a_day_however_often_it_is_asked_for(client, configured):  # P5
    user_id = str(uuid.uuid4())
    answers = [_choose(client, user_id, delivery="email").json()["emailed"] for _ in range(5)]

    assert answers == [True] * 5
    assert len(configured.sent) == 1


def test_an_address_mail_cannot_take_is_a_quiet_no_rather_than_a_500(client, configured):  # P7
    response = _choose(client, str(uuid.uuid4()), email="hiker@localhost", delivery="email")

    assert response.status_code == 200
    assert response.json()["emailed"] is False


def test_a_second_choice_while_pending_changes_the_amount_rather_than_adding_one(client, configured, db_session):
    user_id = str(uuid.uuid4())
    _choose(client, user_id, amount_cents=1000)
    _choose(client, user_id, amount_cents=10000)

    rows = db_session.query(SupportChoice).filter(SupportChoice.profile_id == user_id).all()
    assert [row.amount_cents for row in rows] == [10000]


def test_a_running_payment_blocks_a_second_choice(client, configured):
    user_id = str(uuid.uuid4())
    _paying(client, user_id)

    assert _choose(client, user_id).status_code == 409
    assert _me(client, user_id)["can_choose"] is False


# ---- Stop ----


def test_stop_on_a_choice_nobody_paid_for_clears_it_at_once(client, configured):  # P2, B2
    user_id = str(uuid.uuid4())
    _choose(client, user_id)

    response = _stop(client, user_id)

    assert response.json()["status"] == "stopped"
    assert configured.sent == []
    assert _choose(client, user_id).status_code == 200


def test_stop_is_recorded_at_once_and_the_founder_is_emailed_to_cancel_it(client, configured, db_session):
    user_id = str(uuid.uuid4())
    _paying(client, user_id)

    response = _stop(client, user_id)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "stop_requested"
    assert body["stop_requested_at"] is not None
    assert (body["supporting"], body["can_stop"]) == (True, False)
    [notice] = configured.to("founder@ourhike.org")
    assert "hiker@example.com" in _text(notice)
    assert "777" in _text(notice)
    assert db_session.query(SupportChoice).one().stop_notified_at is not None


def test_pressing_stop_twice_sends_one_notice(client, configured):
    user_id = str(uuid.uuid4())
    _paying(client, user_id)
    _stop(client, user_id)
    second = _stop(client, user_id)

    assert second.status_code == 200
    assert len(configured.to("founder@ourhike.org")) == 1


def test_stop_with_nothing_running_is_404(client):
    assert _stop(client, str(uuid.uuid4())).status_code == 404


def test_a_stop_nobody_was_told_about_is_asked_again_until_somebody_is(client, configured, monkeypatch, db_session):  # B1
    monkeypatch.setattr(settings, "support_notify_address", "")
    user_id = str(uuid.uuid4())
    _paying(client, user_id)

    assert _stop(client, user_id).json()["status"] == "stop_requested"
    assert configured.to("founder@ourhike.org") == []
    assert db_session.query(SupportChoice).one().stop_notified_at is None

    monkeypatch.setattr(settings, "support_notify_address", "founder@ourhike.org")
    _me(client, user_id)

    assert len(configured.to("founder@ourhike.org")) == 1
    db_session.expire_all()
    assert db_session.query(SupportChoice).one().stop_notified_at is not None


def test_a_webhook_delivery_retries_a_stop_nobody_was_told_about(client, configured, monkeypatch):  # B1
    monkeypatch.setattr(settings, "support_notify_address", "")
    user_id = str(uuid.uuid4())
    _paying(client, user_id)
    _stop(client, user_id)
    monkeypatch.setattr(settings, "support_notify_address", "founder@ourhike.org")

    _deliver(client, _membership("membership.started", email="other@example.com", sub_id=1))

    assert len(configured.to("founder@ourhike.org")) == 1


def test_the_hiker_is_emailed_once_the_payment_has_actually_stopped(client, configured, t0):  # B1
    user_id = str(uuid.uuid4())
    _paying(client, user_id, created=t0)
    _stop(client, user_id)

    _deliver(client, _membership("membership.cancelled", created=t0 + 60, canceled_at=t0 + 60))
    _deliver(client, _membership("membership.cancelled", created=t0 + 60, canceled_at=t0 + 60))

    mine = _me(client, user_id)
    assert mine["status"] == "stopped"
    assert mine["ended_at"] is not None
    [told] = configured.to("hiker@example.com")
    assert "is stopped" in _text(told)


def test_the_founders_notice_lists_every_other_record_under_the_same_address(client, configured):  # P10
    user_id = str(uuid.uuid4())
    _paying(client, user_id)
    # Somebody else paid $1 on the page with the same address.
    _deliver(client, _membership("membership.started", sub_id=1, amount=1))

    _stop(client, user_id)

    notices = configured.to("founder@ourhike.org")
    assert notices
    assert "Other records under the same address" in _text(notices[0])


def test_deleting_the_account_asks_for_a_stop_and_emails_the_founder(client, configured):
    """A deleted account can no longer reach Stop, so the deletion presses it."""
    user_id = str(uuid.uuid4())
    _paying(client, user_id)

    assert client.delete("/profiles/me", headers=auth_headers(user_id)).status_code == 200

    [notice] = configured.to("founder@ourhike.org")
    assert "777" in _text(notice)


def test_deleting_the_account_deletes_a_choice_nobody_paid_for(client, configured, db_session):  # P6, S7
    user_id = str(uuid.uuid4())
    _choose(client, user_id)

    assert client.delete("/profiles/me", headers=auth_headers(user_id)).status_code == 200

    assert db_session.query(SupportChoice).count() == 0
    assert configured.sent == []


# ---- The webhook: believing it ----


def test_a_delivery_without_the_signature_is_refused(client, configured):
    raw = json.dumps(_membership("membership.started")).encode()
    response = client.post("/support/webhooks/buymeacoffee", content=raw)
    assert response.status_code == 401


def test_a_delivery_signed_with_another_secret_is_refused(client, configured):
    assert _deliver(client, _membership("membership.started"), secret="not-ours").status_code == 401


def test_a_signature_that_is_not_ascii_is_refused_rather_than_a_500(client, configured):  # P4
    response = client.post(
        "/support/webhooks/buymeacoffee",
        content=b"{}",
        headers=[(b"x-signature-sha256", "\xe9".encode("latin-1"))],
    )
    assert response.status_code == 401


def test_with_no_secret_configured_every_delivery_is_refused(client, configured, monkeypatch):
    monkeypatch.setattr(settings, "buymeacoffee_webhook_secret", "")
    assert _deliver(client, _membership("membership.started"), secret="anything").status_code == 503


def test_a_provider_this_server_does_not_know_is_404(client, configured):
    assert _deliver(client, _membership("membership.started"), provider="stripe").status_code == 404


def test_a_dashboard_test_event_is_ignored(client, configured, db_session):
    response = _deliver(client, _membership("membership.started", live=False))

    assert response.json() == {"result": "ignored"}
    assert db_session.query(SupportChoice).count() == 0


def test_a_one_off_coffee_is_acknowledged_and_left_alone(client, configured, db_session):
    envelope = {**_membership("membership.started"), "type": "donation.created"}
    assert _deliver(client, envelope).json() == {"result": "ignored"}
    assert db_session.query(SupportChoice).count() == 0


def test_a_level_that_is_not_support_is_left_alone_once_levels_are_listed(client, configured, monkeypatch, db_session):
    monkeypatch.setattr(settings, "buymeacoffee_level_ids", "12, 13")
    assert _deliver(client, _membership("membership.started")).json() == {"result": "ignored"}
    assert db_session.query(SupportChoice).count() == 0


def test_a_delivery_whose_handling_raises_is_kept_and_still_acknowledged(client, configured, monkeypatch, db_session):  # S4
    def broken(*args, **kwargs):
        raise RuntimeError("a bug")

    monkeypatch.setattr(support_core, "apply_event", broken)

    response = _deliver(client, _membership("membership.started"))

    assert response.status_code == 200
    assert response.json() == {"result": "failed"}
    [event] = db_session.query(SupportEvent).all()
    assert event.outcome == "failed: RuntimeError"
    assert event.payload["data"]["id"] == 777


# ---- The webhook: which choice a payment belongs to ----


def test_a_membership_meets_the_choice_made_with_its_email(client, configured, db_session):
    user_id = str(uuid.uuid4())
    _choose(client, user_id)

    response = _deliver(client, _membership("membership.started", email="HIKER@example.com"))

    assert response.json() == {"result": "active"}
    mine = _me(client, user_id)
    assert mine["status"] == "active"
    assert mine["started_at"] is not None
    assert mine["period_end"] is not None
    assert (mine["supporting"], mine["can_stop"], mine["can_choose"]) == (True, True, False)
    row = db_session.query(SupportChoice).filter(SupportChoice.profile_id == user_id).one()
    assert (row.provider_ref, row.customer_ref, row.psp_ref, row.plan_ref) == ("777", "4242", "sub_1Test", "11")


def test_a_payment_that_began_before_the_choice_is_not_that_choices_payment(client, configured, db_session, t0):  # P10
    user_id = str(uuid.uuid4())
    _choose(client, user_id)

    _deliver(client, _membership("membership.started", created=t0 - 86400))

    assert db_session.query(SupportChoice).filter(SupportChoice.profile_id == user_id).one().provider_ref is None


def test_a_payment_for_another_amount_does_not_take_the_choice(client, configured, db_session):  # P10
    victim = str(uuid.uuid4())
    _choose(client, victim, amount_cents=10000)

    _deliver(client, _membership("membership.started", sub_id=1, amount=1))  # a stranger's $1
    _deliver(client, _membership("membership.started", sub_id=2, amount=100))  # the hiker's own

    mine = db_session.query(SupportChoice).filter(SupportChoice.profile_id == victim).one()
    assert (mine.provider_ref, mine.amount_cents) == ("2", 10000)


def test_a_cancellation_for_an_unknown_payment_touches_no_choice(client, configured):  # P11
    user_id = str(uuid.uuid4())
    _choose(client, user_id)

    response = _deliver(client, _membership("membership.cancelled", sub_id=999, status="canceled", canceled="true"))

    assert response.json() == {"result": "ignored_unknown_payment"}
    assert _me(client, user_id)["status"] == "pending"


def test_an_email_never_matches_a_choice_made_with_another_provider(client, configured, db_session):  # S2
    user_id = str(uuid.uuid4())
    _choose(client, user_id)
    db_session.query(SupportChoice).update({SupportChoice.provider: "opencollective"})
    db_session.commit()

    _deliver(client, _membership("membership.started"))

    db_session.expire_all()
    theirs = db_session.query(SupportChoice).filter(SupportChoice.provider == "opencollective").one()
    assert theirs.provider_ref is None


def test_a_payment_after_a_pending_stop_is_kept_and_reaches_the_account_by_its_verified_email(
    client, configured, db_session
):  # P3, S6
    user_id = str(uuid.uuid4())
    _choose(client, user_id)
    _stop(client, user_id)

    _deliver(client, _membership("membership.started"))

    mine = _me(client, user_id)
    assert (mine["status"], mine["can_stop"]) == ("active", True)


def test_a_membership_from_the_page_directly_is_kept_until_its_account_reads_it(client, configured, db_session):  # S6
    _deliver(client, _membership("membership.started", email="walk-in@example.com", amount=100))

    [row] = db_session.query(SupportChoice).all()
    assert row.profile_id is None
    assert (row.status, row.amount_cents) == (SupportStatus.active, 10000)

    user_id = str(uuid.uuid4())
    assert _me(client, user_id, email="walk-in@example.com")["status"] == "active"
    assert _me(client, str(uuid.uuid4()), email="someone@example.com")["status"] == "none"


# ---- The webhook: order and repeats ----


def test_a_retried_delivery_changes_nothing_the_first_did_not(client, configured, db_session):
    _choose(client, str(uuid.uuid4()))
    _deliver(client, _membership("membership.started"))
    _deliver(client, _membership("membership.started"))

    assert db_session.query(SupportChoice).count() == 1
    assert db_session.query(SupportEvent).count() == 2


def test_a_late_update_never_brings_a_stopped_payment_back(client, configured, t0):  # P1, S1
    user_id = str(uuid.uuid4())
    _paying(client, user_id, created=t0)
    _stop(client, user_id)
    _deliver(client, _membership("membership.cancelled", created=t0 + 120, canceled_at=t0 + 120))

    late = _deliver(client, _membership("membership.updated", created=t0 + 60))
    same_second = _deliver(client, _membership("membership.updated", created=t0 + 120))

    assert late.json() == {"result": "stale"}
    assert same_second.json() == {"result": "already_stopped"}
    assert _me(client, user_id)["status"] == "stopped"


def test_an_update_does_not_undo_a_stop_nobody_has_cancelled_yet(client, configured, t0):
    user_id = str(uuid.uuid4())
    _paying(client, user_id, created=t0)
    _stop(client, user_id)

    _deliver(client, _membership("membership.updated", created=t0 + 60))

    assert _me(client, user_id)["status"] == "stop_requested"


def test_an_update_saying_paused_is_read_as_paused(client, configured, t0):  # P8
    user_id = str(uuid.uuid4())
    _paying(client, user_id, created=t0)

    response = _deliver(client, _membership("membership.updated", created=t0 + 60, status="paused"))

    assert response.json() == {"result": "paused"}
    assert _me(client, user_id)["supporting"] is True


def test_a_cancellation_at_the_period_end_is_scheduled_not_stopped(client, configured, t0):  # P8, S5
    user_id = str(uuid.uuid4())
    _paying(client, user_id, created=t0)

    response = _deliver(client, _membership("membership.updated", created=t0 + 60, cancel_at_period_end="true"))

    assert response.json() == {"result": "cancel_scheduled"}
    mine = _me(client, user_id)
    assert (mine["supporting"], mine["can_stop"], mine["can_choose"]) == (True, False, True)


def test_one_provider_payment_is_one_row(db_session):  # P9
    for _ in range(2):
        db_session.add(SupportChoice(email="a@x.org", provider="buymeacoffee", provider_ref="1", amount_cents=100))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_the_event_log_keeps_no_name_note_or_email(client, configured, db_session):
    _deliver(client, _membership("membership.started"))

    [event] = db_session.query(SupportEvent).all()
    assert (event.provider, event.kind, event.outcome) == ("buymeacoffee", "started", "active")
    data = event.payload["data"]
    assert not {"supporter_name", "support_note", "supporter_email"} & set(data)
    assert data["amount"] == 10


# ---- Moving provider ----


class OldPay:
    """A provider OurHike used to take payments through."""

    key = "oldpay"
    label = "Old Pay"
    cancel = "api"

    def __init__(self):
        self.cancelled: list[str] = []

    def checkout_url(self, choice):
        return None

    def webhook_configured(self):
        return False

    def verify(self, headers, raw_body):
        return False

    def normalise(self, envelope):
        return []

    def request_cancel(self, db, choice, mail_provider):
        self.cancelled.append(choice.provider_ref)
        return True


def test_a_supporter_on_an_old_provider_can_move_and_the_old_payment_stops_when_the_new_starts(
    client, configured, monkeypatch, db_session
):  # C2
    old = OldPay()
    monkeypatch.setitem(PROVIDERS, old.key, old)
    user_id = str(uuid.uuid4())
    _me(client, user_id)  # creates the profile
    db_session.add(
        SupportChoice(
            profile_id=user_id,
            email="hiker@example.com",
            provider="oldpay",
            provider_ref="old-1",
            amount_cents=1000,
            status=SupportStatus.active,
            started_at=utc_now() - timedelta(days=200),
        )
    )
    db_session.commit()

    assert _me(client, user_id)["can_choose"] is True
    assert _choose(client, user_id).status_code == 200
    assert old.cancelled == []

    _deliver(client, _membership("membership.started"))

    assert old.cancelled == ["old-1"]
    db_session.expire_all()
    statuses = {row.provider: row.status for row in db_session.query(SupportChoice).all()}
    assert statuses == {"oldpay": SupportStatus.stop_requested, "buymeacoffee": SupportStatus.active}


# ---- Unsubscribing ----


def test_a_hikers_support_email_carries_a_real_one_click_unsubscribe(client, configured, monkeypatch, db_session):  # P5
    monkeypatch.setattr(settings, "api_public_url", "https://api.ourhike.org")
    _choose(client, str(uuid.uuid4()), delivery="email")
    token = db_session.query(SupportChoice).one().link_token

    [message] = configured.sent
    headers = email.message_from_bytes(message["Content"]["Raw"]["Data"])
    assert headers["List-Unsubscribe"] == f"<https://api.ourhike.org/support/mail/stop/{token}>"

    page = client.get(f"/support/mail/stop/{token}")
    assert page.status_code == 200
    assert "<form" in page.text
    assert not is_suppressed(db_session, "hiker@example.com")

    assert client.post(f"/support/mail/stop/{token}").status_code == 200
    assert is_suppressed(db_session, "hiker@example.com")


def test_an_unsubscribe_link_that_is_not_ours_is_404(client):
    assert client.post("/support/mail/stop/not-a-token").status_code == 404


def test_the_founders_notice_cannot_be_unsubscribed_from_a_hikers_link(client, configured, monkeypatch, db_session):
    monkeypatch.setattr(settings, "api_public_url", "https://api.ourhike.org")
    user_id = str(uuid.uuid4())
    _paying(client, user_id)
    _stop(client, user_id)

    [notice] = configured.to("founder@ourhike.org")
    headers = email.message_from_bytes(notice["Content"]["Raw"]["Data"])
    assert "/support/mail/stop/" not in headers["List-Unsubscribe"]
    assert db_session.query(EmailSend).filter(EmailSend.purpose == MailPurpose.support_stop_request).count() == 1


# ---- The published total ----


def test_the_total_counts_what_started_and_not_what_was_only_chosen(client, configured):
    _choose(client, str(uuid.uuid4()))  # chosen, never paid
    _deliver(client, _membership("membership.started", email="second@example.com", amount=100))

    response = client.get("/support/total")

    assert response.json()["total_cents"] == 10000
    assert response.json()["supporters"] == 1
    assert "max-age=3600" in response.headers["cache-control"]


def test_the_total_is_computed_at_most_hourly(client, configured):  # C3
    assert client.get("/support/total").json()["total_cents"] == 0
    _deliver(client, _membership("membership.started", email="second@example.com", amount=100))

    assert client.get("/support/total").json()["total_cents"] == 0


def _given(**fields):
    defaults = {
        "email": "a@example.com",
        "provider": "buymeacoffee",
        "amount_cents": 1000,
        "cadence": SupportCadence.year,
        "status": SupportStatus.active,
        "started_at": datetime(2025, 3, 1),
    }
    return SupportChoice(**{**defaults, **fields})


def test_a_yearly_supporter_counts_again_once_their_anniversary_passes(db_session):
    db_session.add(_given())
    db_session.commit()

    assert year_total(db_session, 2025, now=datetime(2026, 2, 1)) == (1000, 1)
    assert year_total(db_session, 2026, now=datetime(2026, 2, 1)) == (0, 0)
    assert year_total(db_session, 2026, now=datetime(2026, 3, 2)) == (1000, 1)


def test_a_stopped_supporter_is_not_counted_after_they_ended(db_session):
    db_session.add(_given(status=SupportStatus.stopped, ended_at=datetime(2025, 9, 1)))
    db_session.commit()

    assert year_total(db_session, 2026, now=datetime(2026, 6, 1)) == (0, 0)


def test_a_payment_scheduled_to_end_on_its_anniversary_is_not_charged_on_it(db_session):
    db_session.add(_given(status=SupportStatus.cancel_scheduled, ended_at=datetime(2026, 3, 1)))
    db_session.commit()

    assert year_total(db_session, 2026, now=datetime(2026, 6, 1)) == (0, 0)


def test_another_currency_is_left_out_of_the_dollar_total(db_session):  # C1
    db_session.add(_given(currency="EUR"))
    db_session.commit()

    assert year_total(db_session, 2025, now=datetime(2026, 2, 1)) == (0, 0)
