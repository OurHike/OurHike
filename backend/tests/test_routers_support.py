"""Tests for the `/support` router (#1876, features/SUPPORTING_OURHIKE.md).

What these hold: a paid choice is recorded against the caller's VERIFIED
email and never a typed one, and checks out through the tier's Stripe Payment
Link carrying the choice's id; a store-app choice travels by email, at most
once a day, and never as a checkout link; Stop on a pending choice clears it
at once, and on a running payment asks Stripe to stop renewing (or the
founder, when Stripe cannot be reached), is retried until somebody is told,
and ends with the hiker emailed; a webhook is believed only with Stripe's
signature inside its replay window; a payment meets its choice by the
choice's own id, and by email only when it starts, for the same amount,
after the choice was made; a late or repeated event never undoes a later
one; every event is logged without a name, address or email; and the
published total sums the charges Stripe reports, each once.

The `# P<n>`, `# B<n>`, `# S<n>` and `# C<n>` marks name the #1885 security
and architecture reviews' findings each test answers.
"""

import email
import email.policy
import hashlib
import hmac
import json
import time
import uuid
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlsplit

import pytest
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.core import support as support_core
from app.core.mail import is_suppressed
from app.core.support import year_total
from app.core.support_providers import PROVIDERS
from app.core.support_providers import stripe as stripe_provider
from app.core.time import utc_now
from app.models.mail import EmailSend, MailPurpose
from app.models.support import SupportChoice, SupportEvent, SupportStatus
from app.routers.support import clear_total_cache
from tests.tokens import auth_headers

SECRET = "whsec_test"
LINKS = {
    1200: "https://buy.stripe.com/test_twelve",
    6000: "https://buy.stripe.com/test_sixty",
    12000: "https://buy.stripe.com/test_hundred_twenty",
}


class Mail:
    """A stand-in for SES, as tests/test_nomination_mail.py builds one."""

    def __init__(self) -> None:
        self.sent: list[dict] = []

    def send_email(self, **kwargs):
        self.sent.append(kwargs)
        return {"MessageId": f"ses-{len(self.sent)}"}

    def to(self, address):
        return [m for m in self.sent if m["Destination"]["ToAddresses"] == [address]]


class StripeApi:
    """A stand-in for Stripe's API: records each call, answers `status`."""

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.status = 200

    def post(self, url, **kwargs):
        self.calls.append({"url": url, **kwargs})

        class Response:
            status_code = self.status

        return Response()


class World:
    def __init__(self, mail: Mail, api: StripeApi) -> None:
        self.mail = mail
        self.api = api
        self.sent = mail.sent

    def to(self, address):
        return self.mail.to(address)


def _text(message) -> str:
    return message["Content"]["Raw"]["Data"].decode()


def _parsed(message):
    return email.message_from_bytes(message["Content"]["Raw"]["Data"], policy=email.policy.default)


@pytest.fixture(autouse=True)
def _fresh_total():
    clear_total_cache()
    yield
    clear_total_cache()


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setattr(settings, "support_provider", "stripe")
    monkeypatch.setattr(settings, "stripe_payment_links", ",".join(f"{c}={u}" for c, u in LINKS.items()))
    monkeypatch.setattr(settings, "stripe_webhook_secret", SECRET)
    monkeypatch.setattr(settings, "stripe_secret_key", "rk_live_fixture")
    monkeypatch.setattr(settings, "support_notify_address", "founder@ourhike.org")
    monkeypatch.setattr(settings, "api_public_url", "")
    monkeypatch.setattr(settings, "mail_enabled", True)
    monkeypatch.setattr(settings, "mail_allowed_suffixes", "")
    mail = Mail()
    api = StripeApi()
    monkeypatch.setattr("app.routers.support.ses_client", lambda: mail)
    monkeypatch.setattr("app.routers.profiles.ses_client", lambda: mail)
    monkeypatch.setattr(stripe_provider.httpx, "post", api.post)
    return World(mail, api)


@pytest.fixture
def t0():
    """Now, in Stripe's Unix seconds, for tests that order events."""
    return int(time.time())


def _choose(client, user_id, email="hiker@example.com", **body):
    return client.put(
        "/support/me",
        json={"amount_cents": 6000, "accounting_email": False, "delivery": "redirect", **body},
        headers=auth_headers(user_id, email=email),
    )


def _me(client, user_id, email="hiker@example.com"):
    return client.get("/support/me", headers=auth_headers(user_id, email=email)).json()


def _stop(client, user_id):
    return client.post("/support/me/stop", headers=auth_headers(user_id))


def _sign(raw: bytes, *, secret=SECRET, at=None) -> str:
    at = int(time.time()) if at is None else at
    digest = hmac.new(secret.encode(), f"{at}.".encode() + raw, hashlib.sha256).hexdigest()
    return f"t={at},v1={digest}"


def _deliver(client, envelope, *, secret=SECRET, at=None, provider="stripe"):
    raw = json.dumps(envelope).encode()
    return client.post(
        f"/support/webhooks/{provider}",
        content=raw,
        headers={"stripe-signature": _sign(raw, secret=secret, at=at), "content-type": "application/json"},
    )


def _event(kind, obj, *, created=None, live=True, event_id=None):
    return {
        "id": event_id or f"evt_{uuid.uuid4().hex[:20]}",
        "object": "event",
        "type": kind,
        "livemode": live,
        "created": int(time.time()) if created is None else created,
        "data": {"object": obj},
    }


def _session(*, choice=None, email="hiker@example.com", sub="sub_777", amount=6000, mode="subscription", created=None, live=True):
    """`checkout.session.completed`, as a Payment Link's checkout sends it."""
    created = int(time.time()) if created is None else created
    return _event(
        "checkout.session.completed",
        {
            "id": f"cs_{uuid.uuid4().hex[:12]}",
            "object": "checkout.session",
            "mode": mode,
            "client_reference_id": choice,
            "subscription": sub,
            "customer": "cus_42",
            "payment_link": "plink_ten",
            "amount_total": amount,
            "currency": "usd",
            "created": created,
            "customer_details": {
                "email": email,
                "name": "Ramen Bomb",
                "address": {"line1": "1 Springer Mountain", "country": "US"},
            },
        },
        created=created,
        live=live,
    )


def _subscription(kind="customer.subscription.updated", *, sub="sub_777", status="active", created=None, basil=True, **fields):
    """A subscription event. `basil` puts the period end on the item, as API
    version 2025-03-31.basil does; otherwise on the subscription."""
    created = int(time.time()) if created is None else created
    period_end = fields.pop("period_end", created + 365 * 86400)
    item = {
        "id": "si_1",
        "quantity": 1,
        "price": {
            "id": "price_ten",
            "unit_amount": fields.pop("amount", 6000),
            "currency": "usd",
            "recurring": {"interval": "year"},
        },
    }
    obj = {
        "id": sub,
        "object": "subscription",
        "status": status,
        "customer": "cus_42",
        "currency": "usd",
        "start_date": created,
        "cancel_at_period_end": False,
        "cancel_at": None,
        "pause_collection": None,
        "items": {"data": [item]},
        **fields,
    }
    if basil:
        item["current_period_end"] = period_end
    else:
        obj["current_period_end"] = period_end
    return _event(kind, obj, created=created)


def _invoice(*, sub="sub_777", amount=6000, currency="usd", paid_at=None, basil=True, event_id=None):
    paid_at = int(time.time()) if paid_at is None else paid_at
    obj = {
        "id": f"in_{uuid.uuid4().hex[:12]}",
        "object": "invoice",
        "customer": "cus_42",
        "customer_email": "hiker@example.com",
        "amount_paid": amount,
        "currency": currency,
        "billing_reason": "subscription_cycle",
        "status_transitions": {"paid_at": paid_at},
    }
    if basil:
        obj["parent"] = {"type": "subscription_details", "subscription_details": {"subscription": sub}}
    else:
        obj["subscription"] = sub
    return _event("invoice.paid", obj, created=paid_at, event_id=event_id)


def _choice_id(receipt) -> str:
    return parse_qs(urlsplit(receipt.json()["checkout_url"]).query)["client_reference_id"][0]


def _paying(client, user_id, **session):
    """A hiker who chose $60 in the app and whose payment then started."""
    choice = _choice_id(_choose(client, user_id))
    assert _deliver(client, _session(choice=choice, **session)).json() == {"result": "active"}
    return choice


# ---- Reading and choosing ----


def test_no_choice_reads_as_none_rather_than_missing(client, configured):
    body = _me(client, str(uuid.uuid4()))

    assert body["status"] == "none"
    assert (body["supporting"], body["can_stop"], body["can_choose"]) == (False, False, True)


def test_reading_requires_authentication(client):
    assert client.get("/support/me").status_code == 401


def test_a_website_choice_checks_out_through_its_tiers_link_carrying_the_choice(client, configured, db_session):
    response = _choose(client, str(uuid.uuid4()), amount_cents=12000)

    assert response.status_code == 200
    body = response.json()
    assert body["support"]["status"] == "pending"
    assert body["support"]["amount_cents"] == 12000
    assert body["support"]["email"] == "hiker@example.com"
    assert body["support"]["provider_label"] == "Stripe"
    assert (body["support"]["supporting"], body["support"]["can_stop"], body["support"]["can_choose"]) == (
        False,
        True,
        True,
    )
    url = urlsplit(body["checkout_url"])
    assert f"{url.scheme}://{url.netloc}{url.path}" == LINKS[12000]
    query = parse_qs(url.query)
    assert query["client_reference_id"] == [db_session.query(SupportChoice).one().id]
    assert query["prefilled_email"] == ["hiker@example.com"]
    assert body["emailed"] is False


def test_a_choice_keeps_the_consent_record_a_provider_move_needs(client, configured, db_session):
    _choose(client, str(uuid.uuid4()), accounting_email=True, delivery="email")

    row = db_session.query(SupportChoice).one()
    assert row.terms_version is not None
    assert row.delivery == "email"
    assert row.chosen_amount_cents == 6000
    assert row.accounting_email_at is not None
    assert row.migrate_notice_at is not None


def test_the_email_is_the_tokens_never_one_the_request_carries(client, configured):
    """A typed address could point a stranger's payment at this account."""
    response = client.put(
        "/support/me",
        json={"amount_cents": 6000, "delivery": "redirect", "email": "someone-else@example.com"},
        headers=auth_headers(str(uuid.uuid4()), email="Hiker@Example.com "),
    )

    assert response.json()["support"]["email"] == "hiker@example.com"


def test_a_sign_in_with_no_email_cannot_choose(client, configured):
    response = client.put(
        "/support/me",
        json={"amount_cents": 6000, "delivery": "redirect"},
        headers=auth_headers(str(uuid.uuid4())),
    )
    assert response.status_code == 422


# The old tiers ($1, $10, $100) are refused too: a client from before the
# change must not record an amount nobody offers any more.
@pytest.mark.parametrize("amount", [0, 100, 1000, 10000, 1201, 120000])
def test_only_the_three_paid_answers_are_accepted(client, configured, amount):
    assert _choose(client, str(uuid.uuid4()), amount_cents=amount).status_code == 422


def test_with_no_payment_links_configured_the_website_path_says_not_yet(client, configured, monkeypatch, db_session):
    monkeypatch.setattr(settings, "stripe_payment_links", "")
    assert _choose(client, str(uuid.uuid4())).status_code == 503
    assert db_session.query(SupportChoice).count() == 0


def test_a_payment_link_that_is_not_https_is_never_handed_out(client, configured, monkeypatch):
    monkeypatch.setattr(settings, "stripe_payment_links", "6000=javascript:alert(1)")
    assert _choose(client, str(uuid.uuid4())).status_code == 503


def test_with_no_known_provider_nothing_can_be_chosen(client, configured, monkeypatch):
    monkeypatch.setattr(settings, "support_provider", "nobody")
    assert _choose(client, str(uuid.uuid4())).status_code == 503
    assert _me(client, str(uuid.uuid4()))["can_choose"] is False


def test_a_store_app_choice_is_emailed_and_never_answers_with_a_link(client, configured):
    response = _choose(client, str(uuid.uuid4()), delivery="email", amount_cents=12000)

    body = response.json()
    assert body["checkout_url"] is None
    assert body["emailed"] is True
    [message] = configured.sent
    assert message["Destination"]["ToAddresses"] == ["hiker@example.com"]
    assert LINKS[12000] + "?client_reference_id=" in _parsed(message).get_body(("plain",)).get_content()


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
    _choose(client, user_id, amount_cents=6000)
    _choose(client, user_id, amount_cents=12000)

    rows = db_session.query(SupportChoice).filter(SupportChoice.profile_id == user_id).all()
    assert [row.amount_cents for row in rows] == [12000]


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
    assert configured.api.calls == []
    assert _choose(client, user_id).status_code == 200


def test_stop_asks_stripe_to_stop_renewing_and_nobody_has_to_do_it_by_hand(client, configured, db_session):
    user_id = str(uuid.uuid4())
    _paying(client, user_id)

    response = _stop(client, user_id)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "stop_requested"
    assert body["stop_requested_at"] is not None
    assert (body["supporting"], body["can_stop"]) == (True, False)
    [call] = configured.api.calls
    assert call["url"] == "https://api.stripe.com/v1/subscriptions/sub_777"
    assert call["data"] == {"cancel_at_period_end": "true"}
    assert call["auth"] == ("rk_live_fixture", "")
    assert call["headers"]["Idempotency-Key"].startswith("ourhike-stop-")
    assert configured.to("founder@ourhike.org") == []
    assert db_session.query(SupportChoice).one().stop_notified_at is not None


def test_pressing_stop_twice_asks_stripe_once(client, configured):
    user_id = str(uuid.uuid4())
    _paying(client, user_id)
    _stop(client, user_id)
    second = _stop(client, user_id)

    assert second.status_code == 200
    assert len(configured.api.calls) == 1


def test_stop_with_nothing_running_is_404(client):
    assert _stop(client, str(uuid.uuid4())).status_code == 404


@pytest.mark.parametrize("reason", ["refused", "no key"])
def test_when_stripe_cannot_be_reached_the_founder_is_asked_instead(client, configured, monkeypatch, reason):
    if reason == "refused":
        configured.api.status = 500
    else:
        monkeypatch.setattr(settings, "stripe_secret_key", "")
    user_id = str(uuid.uuid4())
    _paying(client, user_id)

    assert _stop(client, user_id).json()["status"] == "stop_requested"

    [notice] = configured.to("founder@ourhike.org")
    assert "sub_777" in _text(notice)
    assert "Cancel at end of period" in _text(notice)


def test_a_stop_nobody_was_told_about_is_asked_again_until_somebody_is(client, configured, monkeypatch, db_session):  # B1
    monkeypatch.setattr(settings, "stripe_secret_key", "")
    monkeypatch.setattr(settings, "support_notify_address", "")
    user_id = str(uuid.uuid4())
    _paying(client, user_id)

    assert _stop(client, user_id).json()["status"] == "stop_requested"
    assert db_session.query(SupportChoice).one().stop_notified_at is None

    monkeypatch.setattr(settings, "stripe_secret_key", "rk_live_fixture")
    _me(client, user_id)

    assert len(configured.api.calls) == 1
    db_session.expire_all()
    assert db_session.query(SupportChoice).one().stop_notified_at is not None


def test_a_webhook_delivery_retries_a_stop_nobody_was_told_about(client, configured, monkeypatch):  # B1
    monkeypatch.setattr(settings, "stripe_secret_key", "")
    monkeypatch.setattr(settings, "support_notify_address", "")
    user_id = str(uuid.uuid4())
    _paying(client, user_id)
    _stop(client, user_id)
    monkeypatch.setattr(settings, "stripe_secret_key", "rk_live_fixture")

    _deliver(client, _session(email="other@example.com", sub="sub_1"))

    assert len(configured.api.calls) == 1


def test_the_hiker_is_emailed_once_stripe_confirms_it_will_not_renew(client, configured, t0):  # B1
    user_id = str(uuid.uuid4())
    _paying(client, user_id, created=t0)
    _stop(client, user_id)

    scheduled = _subscription(created=t0 + 60, cancel_at_period_end=True)
    assert _deliver(client, scheduled).json() == {"result": "cancel_scheduled"}
    _deliver(client, scheduled)

    mine = _me(client, user_id)
    assert (mine["status"], mine["supporting"], mine["can_stop"]) == ("cancel_scheduled", True, False)
    [told] = configured.to("hiker@example.com")
    assert "is stopped" in _text(told)
    assert "covers you to" in _text(told)


def test_a_deleted_subscription_is_stopped(client, configured, t0):
    user_id = str(uuid.uuid4())
    _paying(client, user_id, created=t0)

    deleted = _subscription("customer.subscription.deleted", status="canceled", created=t0 + 60, cancel_at_period_end=True)
    assert _deliver(client, deleted).json() == {"result": "stopped"}

    assert _me(client, user_id)["status"] == "stopped"


def test_the_founders_notice_lists_every_other_record_under_the_same_address(client, configured):  # P10
    configured.api.status = 500
    user_id = str(uuid.uuid4())
    _paying(client, user_id)
    # Somebody else paid $12 on a link with the same address and no choice id.
    _deliver(client, _session(sub="sub_1", amount=1200))

    _stop(client, user_id)

    notices = configured.to("founder@ourhike.org")
    assert notices
    assert "Other records under the same address" in _text(notices[0])


def test_deleting_the_account_asks_stripe_to_stop_it(client, configured):
    """A deleted account can no longer reach Stop, so the deletion presses it."""
    user_id = str(uuid.uuid4())
    _paying(client, user_id)

    assert client.delete("/profiles/me", headers=auth_headers(user_id)).status_code == 200

    [call] = configured.api.calls
    assert call["url"].endswith("/v1/subscriptions/sub_777")


def test_deleting_the_account_deletes_a_choice_nobody_paid_for(client, configured, db_session):  # P6, S7
    user_id = str(uuid.uuid4())
    _choose(client, user_id)

    assert client.delete("/profiles/me", headers=auth_headers(user_id)).status_code == 200

    assert db_session.query(SupportChoice).count() == 0
    assert configured.sent == []


# ---- The webhook: believing it ----


def test_a_delivery_without_the_signature_is_refused(client, configured):
    raw = json.dumps(_session()).encode()
    response = client.post("/support/webhooks/stripe", content=raw)
    assert response.status_code == 401


def test_a_delivery_signed_with_another_secret_is_refused(client, configured):
    assert _deliver(client, _session(), secret="whsec_not_ours").status_code == 401


def test_a_replayed_delivery_outside_stripes_window_is_refused(client, configured):
    assert _deliver(client, _session(), at=int(time.time()) - 3600).status_code == 401


def test_a_signature_that_is_not_ascii_is_refused_rather_than_a_500(client, configured):  # P4
    response = client.post(
        "/support/webhooks/stripe",
        content=b"{}",
        headers=[(b"stripe-signature", "\xe9".encode("latin-1"))],
    )
    assert response.status_code == 401


def test_with_no_secret_configured_every_delivery_is_refused(client, configured, monkeypatch):
    monkeypatch.setattr(settings, "stripe_webhook_secret", "")
    assert _deliver(client, _session(), secret="anything").status_code == 503


def test_a_provider_this_server_does_not_know_is_404(client, configured):
    assert _deliver(client, _session(), provider="buymeacoffee").status_code == 404


def test_a_test_mode_event_is_ignored_by_a_live_key(client, configured, db_session):
    response = _deliver(client, _session(live=False))

    assert response.json() == {"result": "ignored"}
    assert db_session.query(SupportChoice).count() == 0


def test_a_test_mode_key_believes_test_mode_events_so_ua_can_run_on_them(client, configured, monkeypatch):
    monkeypatch.setattr(settings, "stripe_secret_key", "rk_test_fixture")
    assert _deliver(client, _session(live=False)).json() == {"result": "active"}
    assert _deliver(client, _session(sub="sub_live")).json() == {"result": "ignored"}


def test_a_one_off_payment_and_other_event_types_are_left_alone(client, configured, db_session):
    assert _deliver(client, _session(mode="payment")).json() == {"result": "ignored"}
    assert _deliver(client, _event("customer.created", {"id": "cus_1"})).json() == {"result": "ignored"}
    assert db_session.query(SupportChoice).count() == 0


def test_a_subscription_whose_first_payment_has_not_gone_through_is_left_alone(client, configured):
    user_id = str(uuid.uuid4())
    _paying(client, user_id)

    assert _deliver(client, _subscription(status="incomplete")).json() == {"result": "ignored"}


def test_a_delivery_whose_handling_raises_is_kept_and_still_acknowledged(client, configured, monkeypatch, db_session):  # S4
    def broken(*args, **kwargs):
        raise RuntimeError("a bug")

    monkeypatch.setattr(support_core, "apply_event", broken)

    response = _deliver(client, _session())

    assert response.status_code == 200
    assert response.json() == {"result": "failed"}
    [event] = db_session.query(SupportEvent).all()
    assert event.outcome == "failed: RuntimeError"
    assert event.payload["subscription"] == "sub_777"


# ---- The webhook: which choice a payment belongs to ----


def test_a_payment_meets_its_choice_by_the_choices_own_id(client, configured, db_session):
    user_id = str(uuid.uuid4())
    choice = _choice_id(_choose(client, user_id))

    # The payer typed a different address on Stripe's page: the id still holds.
    response = _deliver(client, _session(choice=choice, email="typed-something-else@example.com"))

    assert response.json() == {"result": "active"}
    mine = _me(client, user_id)
    assert mine["status"] == "active"
    assert mine["started_at"] is not None
    assert (mine["supporting"], mine["can_stop"], mine["can_choose"]) == (True, True, False)
    row = db_session.query(SupportChoice).filter(SupportChoice.profile_id == user_id).one()
    assert (row.provider_ref, row.customer_ref, row.plan_ref, row.email) == (
        "sub_777",
        "cus_42",
        "plink_ten",
        "hiker@example.com",
    )


def test_without_the_choice_id_a_payment_falls_back_to_email_amount_and_time(client, configured, db_session):
    user_id = str(uuid.uuid4())
    _choose(client, user_id)

    assert _deliver(client, _session(email="HIKER@example.com")).json() == {"result": "active"}
    assert db_session.query(SupportChoice).filter(SupportChoice.profile_id == user_id).one().provider_ref == "sub_777"


def test_a_payment_that_began_before_the_choice_is_not_that_choices_payment(client, configured, db_session, t0):  # P10
    user_id = str(uuid.uuid4())
    _choose(client, user_id)

    _deliver(client, _session(created=t0 - 86400))

    assert db_session.query(SupportChoice).filter(SupportChoice.profile_id == user_id).one().provider_ref is None


def test_a_payment_for_another_amount_does_not_take_the_choice(client, configured, db_session):  # P10
    victim = str(uuid.uuid4())
    _choose(client, victim, amount_cents=12000)

    _deliver(client, _session(sub="sub_1", amount=1200))  # a stranger's $12, the hiker's address
    _deliver(client, _session(sub="sub_2", amount=12000))  # the hiker's own

    mine = db_session.query(SupportChoice).filter(SupportChoice.profile_id == victim).one()
    assert (mine.provider_ref, mine.amount_cents) == ("sub_2", 12000)


def test_a_choice_id_only_claims_a_choice_still_waiting(client, configured, db_session):
    user_id = str(uuid.uuid4())
    choice = _choice_id(_choose(client, user_id))
    _stop(client, user_id)

    _deliver(client, _session(choice=choice))

    assert db_session.get(SupportChoice, choice).status == SupportStatus.stopped


def test_a_cancellation_for_an_unknown_payment_touches_no_choice(client, configured):  # P11
    user_id = str(uuid.uuid4())
    _choose(client, user_id)

    response = _deliver(client, _subscription("customer.subscription.deleted", sub="sub_999", status="canceled"))

    assert response.json() == {"result": "ignored_unknown_payment"}
    assert _me(client, user_id)["status"] == "pending"


def test_an_email_never_matches_a_choice_made_with_another_provider(client, configured, db_session):  # S2
    user_id = str(uuid.uuid4())
    _choose(client, user_id)
    db_session.query(SupportChoice).update({SupportChoice.provider: "opencollective"})
    db_session.commit()

    _deliver(client, _session())

    db_session.expire_all()
    theirs = db_session.query(SupportChoice).filter(SupportChoice.provider == "opencollective").one()
    assert theirs.provider_ref is None


def test_a_payment_after_a_pending_stop_is_kept_and_reaches_the_account_by_its_verified_email(
    client, configured, db_session
):  # P3, S6
    user_id = str(uuid.uuid4())
    _choose(client, user_id)
    _stop(client, user_id)

    _deliver(client, _session())

    mine = _me(client, user_id)
    assert (mine["status"], mine["can_stop"]) == ("active", True)


def test_a_payment_from_a_link_with_no_choice_is_kept_until_its_account_reads_it(client, configured, db_session):  # S6
    _deliver(client, _session(email="walk-in@example.com", amount=12000))

    [row] = db_session.query(SupportChoice).all()
    assert row.profile_id is None
    assert (row.status, row.amount_cents) == (SupportStatus.active, 12000)

    assert _me(client, str(uuid.uuid4()), email="walk-in@example.com")["status"] == "active"
    assert _me(client, str(uuid.uuid4()), email="someone@example.com")["status"] == "none"


# ---- The webhook: order and repeats ----


def test_a_retried_delivery_changes_nothing_the_first_did_not(client, configured, db_session):
    session = _session()
    _choose(client, str(uuid.uuid4()))
    _deliver(client, session)
    _deliver(client, session)

    assert db_session.query(SupportChoice).count() == 1
    assert db_session.query(SupportEvent).count() == 2


def test_a_late_update_never_brings_a_stopped_payment_back(client, configured, t0):  # P1, S1
    user_id = str(uuid.uuid4())
    _paying(client, user_id, created=t0)
    _stop(client, user_id)
    _deliver(client, _subscription("customer.subscription.deleted", status="canceled", created=t0 + 120))

    late = _deliver(client, _subscription(created=t0 + 60))
    same_second = _deliver(client, _subscription(created=t0 + 120))

    assert late.json() == {"result": "stale"}
    assert same_second.json() == {"result": "already_stopped"}
    assert _me(client, user_id)["status"] == "stopped"


def test_an_update_does_not_undo_a_stop_that_has_not_landed_yet(client, configured, t0):
    user_id = str(uuid.uuid4())
    _paying(client, user_id, created=t0)
    _stop(client, user_id)

    _deliver(client, _subscription(created=t0 + 60))

    assert _me(client, user_id)["status"] == "stop_requested"


def test_a_paused_collection_is_read_as_paused(client, configured, t0):  # P8
    user_id = str(uuid.uuid4())
    _paying(client, user_id, created=t0)

    response = _deliver(client, _subscription(created=t0 + 60, pause_collection={"behavior": "void"}))

    assert response.json() == {"result": "paused"}
    assert _me(client, user_id)["supporting"] is True


@pytest.mark.parametrize("basil", [True, False])
def test_a_cancellation_at_the_period_end_is_scheduled_not_stopped(client, configured, t0, basil):  # P8, S5
    """Either API version's shape: the period end on the item or the subscription."""
    user_id = str(uuid.uuid4())
    _paying(client, user_id, created=t0)

    response = _deliver(client, _subscription(created=t0 + 60, cancel_at_period_end=True, basil=basil))

    assert response.json() == {"result": "cancel_scheduled"}
    mine = _me(client, user_id)
    assert (mine["supporting"], mine["can_stop"], mine["can_choose"]) == (True, False, True)
    assert mine["period_end"] is not None


def test_a_scheduled_cancellation_reads_as_stopped_once_its_end_has_passed(client, configured, db_session):
    """Stripe sends `deleted` at the end; this covers a delivery that never came."""
    user_id = str(uuid.uuid4())
    _paying(client, user_id)
    db_session.query(SupportChoice).update(
        {SupportChoice.status: SupportStatus.cancel_scheduled, SupportChoice.ended_at: utc_now() - timedelta(days=1)}
    )
    db_session.commit()

    mine = _me(client, user_id)

    assert (mine["status"], mine["supporting"], mine["can_choose"]) == ("stopped", False, True)


def test_one_provider_payment_is_one_row(db_session):  # P9
    for _ in range(2):
        db_session.add(SupportChoice(email="a@x.org", provider="stripe", provider_ref="sub_1", amount_cents=100))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_the_event_log_keeps_no_name_address_or_email(client, configured, db_session):
    _deliver(client, _session())

    [event] = db_session.query(SupportEvent).all()
    assert (event.provider, event.kind, event.outcome) == ("stripe", "started", "active")
    stored = json.dumps(event.payload)
    for personal in ("Ramen Bomb", "Springer", "hiker@example.com"):
        assert personal not in stored
    assert event.payload["amount_total"] == 6000


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
            amount_cents=6000,
            status=SupportStatus.active,
            started_at=utc_now() - timedelta(days=200),
        )
    )
    db_session.commit()

    assert _me(client, user_id)["can_choose"] is True
    choice = _choice_id(_choose(client, user_id))
    assert old.cancelled == []

    _deliver(client, _session(choice=choice))

    assert old.cancelled == ["old-1"]
    db_session.expire_all()
    statuses = {row.provider: row.status for row in db_session.query(SupportChoice).all()}
    assert statuses == {"oldpay": SupportStatus.stop_requested, "stripe": SupportStatus.active}


# ---- Unsubscribing ----


def test_a_hikers_support_email_carries_a_real_one_click_unsubscribe(client, configured, monkeypatch, db_session):  # P5
    monkeypatch.setattr(settings, "api_public_url", "https://api.ourhike.org")
    _choose(client, str(uuid.uuid4()), delivery="email")
    token = db_session.query(SupportChoice).one().link_token

    [message] = configured.sent
    headers = _parsed(message)
    assert headers["List-Unsubscribe"] == f"<https://api.ourhike.org/support/mail/stop/{token}>"
    assert f"Stop emails like this one: https://api.ourhike.org/support/mail/stop/{token}" in (
        headers.get_body(("plain",)).get_content()
    )

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
    configured.api.status = 500
    user_id = str(uuid.uuid4())
    _paying(client, user_id)
    _stop(client, user_id)

    [notice] = configured.to("founder@ourhike.org")
    assert "/support/mail/stop/" not in _parsed(notice)["List-Unsubscribe"]
    assert db_session.query(EmailSend).filter(EmailSend.purpose == MailPurpose.support_stop_request).count() == 1


# ---- The published total ----


def test_the_total_sums_charges_and_not_what_was_only_chosen(client, configured):
    _choose(client, str(uuid.uuid4()))  # chosen, never paid
    _deliver(client, _session(email="second@example.com", sub="sub_2", amount=12000))
    _deliver(client, _invoice(sub="sub_2", amount=12000))

    response = client.get("/support/total")

    assert response.json()["total_cents"] == 12000
    assert response.json()["supporters"] == 1
    assert "max-age=3600" in response.headers["cache-control"]


def test_a_charge_delivered_twice_counts_once(client, configured):
    invoice = _invoice(amount=6000, event_id="evt_same")
    assert _deliver(client, invoice).json() == {"result": "charged"}
    assert _deliver(client, invoice).json() == {"result": "duplicate"}

    assert client.get("/support/total").json()["total_cents"] == 6000


@pytest.mark.parametrize("basil", [True, False])
def test_a_charge_that_arrives_before_its_checkout_still_counts(client, configured, basil):
    """Stripe does not promise order: `invoice.paid` often beats the session."""
    _deliver(client, _invoice(sub="sub_early", amount=12000, basil=basil))

    assert client.get("/support/total").json() == {
        "year": utc_now().year,
        "total_cents": 12000,
        "supporters": 1,
    }


def test_the_total_is_computed_at_most_hourly(client, configured):  # C3
    assert client.get("/support/total").json()["total_cents"] == 0
    _deliver(client, _invoice(amount=12000))

    assert client.get("/support/total").json()["total_cents"] == 0


def _charge(at: datetime, cents=6000, currency="USD", subscription="sub_1"):
    return SupportEvent(
        provider="stripe",
        kind="charged",
        occurred_at=at,
        outcome="charged",
        payload={"amount_cents": cents, "currency": currency, "subscription": subscription},
    )


def test_a_yearly_supporters_renewal_counts_in_the_year_it_was_charged(db_session):
    db_session.add_all([_charge(datetime(2025, 3, 1)), _charge(datetime(2026, 3, 1))])
    db_session.commit()

    assert year_total(db_session, 2025) == (6000, 1)
    assert year_total(db_session, 2026) == (6000, 1)
    assert year_total(db_session, 2027) == (0, 0)


def test_another_currency_is_left_out_of_the_dollar_total(db_session):  # C1
    db_session.add_all([_charge(datetime(2026, 3, 1), currency="EUR"), _charge(datetime(2026, 4, 1), subscription="sub_2")])
    db_session.commit()

    assert year_total(db_session, 2026) == (6000, 1)
