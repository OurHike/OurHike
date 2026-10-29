"""Tests for the `/support` router (#1876, features/SUPPORTING_OURHIKE.md).

What these hold: a paid choice is recorded against the caller's VERIFIED
email and never a typed one, and checks out through the tier's Stripe Payment
Link carrying the choice's id; a store-app choice travels by email, at most
once a day, and never as a checkout link; Stop on a pending choice clears it
at once, and on a running payment asks Stripe to stop renewing (or the
founder, when Stripe cannot be reached), is recorded before anybody is
asked, is retried until somebody is told but never more often than
`RETRY_EVERY`, and ends with the hiker emailed; a failing renewal is cancelled
at once; a webhook is believed only with Stripe's signature inside its replay
window and OurHike's own link metadata; a payment meets its choice by the
choice's own id and never by email, and a payment for a choice that no longer
wants one is stopped; a late or repeated event never undoes a later one;
every event is logged without a name, address or email; and the published
total sums the charges Stripe reports, each once by invoice id.

The `# P<n>`, `# B<n>`, `# S<n>` and `# C<n>` marks name the first two #1885
reviews' findings each test answers; `# R3-B<n>` the third review's.
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
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.config import settings
from app.core import support as support_core
from app.core.mail import is_suppressed, suppress
from app.core.support import year_total
from app.core.support_mail import support_mail_on
from app.core.support_providers import PROVIDERS
from app.core.support_providers import stripe as stripe_provider
from app.core.support_providers.stripe import MARKER
from app.core.time import utc_now
from app.models.analytics import AnalyticsEvent, UsageEvent
from app.models.mail import EmailSend, MailPurpose, SuppressionReason
from app.models.profile import Profile
from app.models.support import SupportCharge, SupportChoice, SupportEvent, SupportStatus
from app.routers.support import clear_total_cache
from tests.factories import make_usage_consent
from tests.tokens import auth_headers

SECRET = "whsec_test"
LINKS = {
    1200: "https://buy.stripe.com/twelve",
    6000: "https://buy.stripe.com/sixty",
    12000: "https://buy.stripe.com/hundred_twenty",
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
    """A stand-in for Stripe's API: records each call, answers `status`.
    `during` runs inside the call, for tests about what is committed then."""

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.status = 200
        self.during = None

    def _call(self, method, url, kwargs):
        self.calls.append({"method": method, "url": url, **kwargs})
        if self.during is not None:
            self.during()

        class Response:
            status_code = self.status

        return Response()

    def post(self, url, **kwargs):
        return self._call("POST", url, kwargs)

    def delete(self, url, **kwargs):
        return self._call("DELETE", url, kwargs)


class World:
    def __init__(self, mail: Mail, api: StripeApi) -> None:
        self.mail = mail
        self.api = api
        self.sent = mail.sent

    def to(self, address, about=None):
        """Messages to `address`, or only those whose text carries `about`."""
        return [m for m in self.mail.to(address) if about is None or about in _body(m)]


def _text(message) -> str:
    return message["Content"]["Raw"]["Data"].decode()


def _parsed(message):
    return email.message_from_bytes(message["Content"]["Raw"]["Data"], policy=email.policy.default)


def _body(message) -> str:
    """The plain-text body, decoded and unfolded, plus the subject."""
    parsed = _parsed(message)
    return f"{parsed['Subject']}\n{parsed.get_body(('plain',)).get_content()}"


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
    monkeypatch.setattr(settings, "stripe_mode", "live")
    monkeypatch.setattr(settings, "support_notify_address", "founder@ourhike.org")
    monkeypatch.setattr(settings, "api_public_url", "")
    monkeypatch.setattr(settings, "mail_enabled", True)
    monkeypatch.setattr(settings, "mail_allowed_suffixes", "")
    mail = Mail()
    api = StripeApi()
    monkeypatch.setattr("app.routers.support.ses_client", lambda: mail)
    monkeypatch.setattr("app.routers.profiles.ses_client", lambda: mail)
    monkeypatch.setattr(stripe_provider.httpx, "post", api.post)
    monkeypatch.setattr(stripe_provider.httpx, "delete", api.delete)
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


def _session(
    *,
    choice=None,
    email="hiker@example.com",
    sub="sub_777",
    amount=6000,
    mode="subscription",
    created=None,
    live=True,
    paid="paid",
    ours=True,
    kind="checkout.session.completed",
):
    """`checkout.session.completed`, as one of OurHike's Payment Links sends
    it: `ours=False` is a link without OurHike's metadata."""
    created = int(time.time()) if created is None else created
    return _event(
        kind,
        {
            "id": f"cs_{uuid.uuid4().hex[:12]}",
            "object": "checkout.session",
            "mode": mode,
            "payment_status": paid,
            "metadata": {MARKER: str(amount)} if ours else {},
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
        "metadata": {MARKER: "6000"},
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


def _invoice(*, sub="sub_777", amount=6000, currency="usd", paid_at=None, basil=True, event_id=None, invoice=None):
    paid_at = int(time.time()) if paid_at is None else paid_at
    obj = {
        "id": invoice or f"in_{uuid.uuid4().hex[:12]}",
        "object": "invoice",
        "customer": "cus_42",
        "customer_email": "hiker@example.com",
        "amount_paid": amount,
        "currency": currency,
        "billing_reason": "subscription_cycle",
        "status_transitions": {"paid_at": paid_at},
        "lines": {"data": [{"period": {"start": paid_at, "end": paid_at + 365 * 86400}}]},
    }
    snapshot = {"metadata": {MARKER: str(amount)}}
    if basil:
        obj["parent"] = {"type": "subscription_details", "subscription_details": {"subscription": sub, **snapshot}}
    else:
        obj["subscription"] = sub
        obj["subscription_details"] = snapshot
    return _event("invoice.paid", obj, created=paid_at, event_id=event_id)


def _refund(*, charge="ch_1", customer="cus_42", refunded=6000, created=None, event_id=None):
    """`charge.refunded`: the Charge with its running `amount_refunded`, and
    no invoice or subscription metadata (since 2025-03-31.basil)."""
    created = int(time.time()) if created is None else created
    return _event(
        "charge.refunded",
        {
            "id": charge,
            "object": "charge",
            "customer": customer,
            "amount": 6000,
            "amount_refunded": refunded,
            "currency": "usd",
            "refunded": refunded >= 6000,
            "billing_details": {"name": "Ramen Bomb", "email": "hiker@example.com"},
        },
        created=created,
        event_id=event_id,
    )


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


def test_the_hiker_gets_a_receipt_saying_what_renews_and_how_to_stop(client, configured):  # R3-B15
    _paying(client, str(uuid.uuid4()))

    [receipt] = configured.to("hiker@example.com")
    assert _parsed(receipt)["Subject"] == "You're giving OurHike $60 a year"
    assert "renews every year" in _body(receipt)
    assert "More → Your support → Stop my support" in _body(receipt)


@pytest.mark.parametrize("status", ["past_due", "unpaid"])
def test_a_failing_renewal_reads_as_failing_and_still_blocks_a_second_choice(client, configured, t0, status):  # R3-B1
    user_id = str(uuid.uuid4())
    _paying(client, user_id, created=t0)

    assert _deliver(client, _subscription(created=t0 + 60, status=status)).json() == {"result": "payment_failed"}

    mine = _me(client, user_id)
    assert (mine["status"], mine["supporting"], mine["can_stop"], mine["can_choose"]) == (
        "payment_failed",
        True,
        True,
        False,
    )
    assert _choose(client, user_id).status_code == 409


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
    assert (call["method"], call["url"]) == ("POST", "https://api.stripe.com/v1/subscriptions/sub_777")
    assert call["data"] == {"cancel_at_period_end": "true"}
    assert call["auth"] == ("rk_live_fixture", "")
    # A fixed key would replay a refusal for 24 hours (R3-B2).
    assert "Idempotency-Key" not in call.get("headers", {})
    assert configured.to("founder@ourhike.org") == []
    assert db_session.query(SupportChoice).one().stop_notified_at is not None


def test_stop_on_a_failing_renewal_cancels_it_at_once_so_no_retry_can_charge(client, configured, t0):  # R3-B1
    user_id = str(uuid.uuid4())
    _paying(client, user_id, created=t0)
    _deliver(client, _subscription(created=t0 + 60, status="past_due"))

    assert _stop(client, user_id).json()["status"] == "stop_requested"

    [call] = configured.api.calls
    assert (call["method"], call["url"]) == ("DELETE", "https://api.stripe.com/v1/subscriptions/sub_777")


def test_when_stripe_cannot_be_reached_a_failing_renewal_is_handed_over_as_cancel_now(client, configured, t0):  # R3-B1
    configured.api.status = 500
    user_id = str(uuid.uuid4())
    _paying(client, user_id, created=t0)
    _deliver(client, _subscription(created=t0 + 60, status="unpaid"))

    _stop(client, user_id)

    [notice] = configured.to("founder@ourhike.org", about="Stop requested")
    assert "IMMEDIATELY" in _text(notice)


def test_stop_is_committed_before_stripe_is_asked(client, configured, db_engine):  # R3-B7
    """A confirmation that lands while the cancel call is out must find the
    Stop recorded, and must not be written over when the call returns."""
    user_id = str(uuid.uuid4())
    _paying(client, user_id)
    seen = []

    def confirmation_lands_meanwhile():
        with Session(db_engine) as other:
            other.execute(text("SET LOCAL lock_timeout = '2s'"))
            row = other.query(SupportChoice).one()
            seen.append(row.status)
            row.status = SupportStatus.cancel_scheduled
            row.ended_at = utc_now() + timedelta(days=300)
            other.commit()

    configured.api.during = confirmation_lands_meanwhile

    assert _stop(client, user_id).json()["status"] == "cancel_scheduled"
    assert seen == [SupportStatus.stop_requested]


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


def _tried_long_ago(db_session):
    """Move every Stop's last try back past `RETRY_EVERY`."""
    db_session.query(SupportChoice).update(
        {SupportChoice.stop_attempted_at: utc_now() - support_core.RETRY_EVERY - timedelta(minutes=1)}
    )
    db_session.commit()


def test_a_stop_nobody_was_told_about_is_asked_again_until_somebody_is(client, configured, monkeypatch, db_session):  # B1
    user_id = str(uuid.uuid4())
    _paying(client, user_id)
    # Stripe's key and the founder's address both gone, after the payment began.
    monkeypatch.setattr(settings, "stripe_secret_key", "")
    monkeypatch.setattr(settings, "support_notify_address", "")

    assert _stop(client, user_id).json()["status"] == "stop_requested"
    assert db_session.query(SupportChoice).one().stop_notified_at is None

    monkeypatch.setattr(settings, "stripe_secret_key", "rk_live_fixture")
    _tried_long_ago(db_session)
    _me(client, user_id)

    assert len(configured.api.calls) == 1
    db_session.expire_all()
    assert db_session.query(SupportChoice).one().stop_notified_at is not None


def test_a_stop_that_did_not_go_is_not_retried_on_every_look(client, configured, monkeypatch, db_session):  # R3-B12
    configured.api.status = 500
    monkeypatch.setattr(settings, "support_notify_address", "")
    user_id = str(uuid.uuid4())
    _paying(client, user_id)
    _stop(client, user_id)

    for _ in range(3):
        _me(client, user_id)
        _deliver(client, _subscription())

    assert len(configured.api.calls) == 1


def test_a_webhook_delivery_retries_a_stop_nobody_was_told_about(client, configured, monkeypatch, db_session):  # B1
    user_id = str(uuid.uuid4())
    _paying(client, user_id)
    # Stripe's key and the founder's address both gone, after the payment began.
    monkeypatch.setattr(settings, "stripe_secret_key", "")
    monkeypatch.setattr(settings, "support_notify_address", "")
    _stop(client, user_id)
    monkeypatch.setattr(settings, "stripe_secret_key", "rk_live_fixture")
    _tried_long_ago(db_session)

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
    [told] = configured.to("hiker@example.com", about="is stopped")
    assert "covers you to" in _text(told)


def test_the_hiker_is_told_once_whichever_order_stripes_events_arrive_in(client, configured, t0):  # R3-B7
    user_id = str(uuid.uuid4())
    _paying(client, user_id, created=t0)
    _stop(client, user_id)

    _deliver(client, _subscription("customer.subscription.deleted", status="canceled", created=t0 + 120))
    _deliver(client, _subscription(created=t0 + 60, cancel_at_period_end=True))

    assert len(configured.to("hiker@example.com", about="is stopped")) == 1


def test_a_cancellation_undone_at_stripe_needs_a_new_stop_and_a_new_stop_reaches_stripe(
    client, configured, t0, db_session
):  # R3-B2
    """Stripe's "Don't cancel": the old Stop is over, and the next one must
    not be swallowed as already told."""
    user_id = str(uuid.uuid4())
    _paying(client, user_id, created=t0)
    _stop(client, user_id)
    _deliver(client, _subscription(created=t0 + 60, cancel_at_period_end=True))

    assert _deliver(client, _subscription(created=t0 + 120)).json() == {"result": "active"}
    row = db_session.query(SupportChoice).one()
    assert (row.stop_requested_at, row.stop_notified_at, row.stop_confirmed_at) == (None, None, None)
    assert _me(client, user_id)["can_stop"] is True

    assert _stop(client, user_id).json()["status"] == "stop_requested"
    assert len(configured.api.calls) == 2


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

    [notice] = configured.to("founder@ourhike.org", about="Stop requested")
    assert "Other records under the same address" in _text(notice)


def test_deleting_the_account_asks_stripe_to_stop_it(client, configured):
    """A deleted account can no longer reach Stop, so the deletion presses it."""
    user_id = str(uuid.uuid4())
    _paying(client, user_id)

    assert client.delete("/profiles/me", headers=auth_headers(user_id)).status_code == 200

    [call] = configured.api.calls
    assert call["url"].endswith("/v1/subscriptions/sub_777")


def test_deleting_the_account_empties_a_choice_nobody_paid_for(client, configured, db_session):  # P6, S7, R3-B3
    user_id = str(uuid.uuid4())
    choice = _choice_id(_choose(client, user_id, accounting_email=True))
    token = db_session.query(SupportChoice).one().link_token

    assert client.delete("/profiles/me", headers=auth_headers(user_id)).status_code == 200

    db_session.expire_all()
    row = db_session.query(SupportChoice).one()
    assert (row.id, row.profile_id, row.email, row.status) == (choice, None, "", SupportStatus.stopped)
    assert (row.accounting_email, row.accounting_email_at) == (False, None)
    assert row.link_token != token
    assert configured.sent == []


def test_a_checkout_finished_after_the_account_was_deleted_is_stopped(client, configured, db_session):  # R3-B3
    """An open checkout tab, or the setup email, can still be paid."""
    user_id = str(uuid.uuid4())
    choice = _choice_id(_choose(client, user_id))
    client.delete("/profiles/me", headers=auth_headers(user_id))

    assert _deliver(client, _session(choice=choice, sub="sub_late")).json() == {"result": "unwanted"}

    db_session.expire_all()
    late = db_session.query(SupportChoice).filter(SupportChoice.provider_ref == "sub_late").one()
    assert (late.profile_id, late.status) == (None, SupportStatus.stop_requested)
    [call] = configured.api.calls
    assert call["url"].endswith("/v1/subscriptions/sub_late")
    assert configured.to("founder@ourhike.org", about="no longer waiting for one")


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


def test_test_mode_believes_test_mode_events_so_ua_can_run_on_them(client, configured, monkeypatch):
    monkeypatch.setattr(settings, "stripe_mode", "test")
    monkeypatch.setattr(settings, "stripe_secret_key", "rk_test_fixture")
    assert _deliver(client, _session(live=False)).json() == {"result": "active"}
    assert _deliver(client, _session(sub="sub_live")).json() == {"result": "ignored"}


def test_a_key_for_the_other_mode_switches_support_off_rather_than_half_on(client, configured, monkeypatch):  # R3
    """A live server holding a test key would take real money and could
    cancel none of it."""
    monkeypatch.setattr(settings, "stripe_secret_key", "rk_test_fixture")

    assert _me(client, str(uuid.uuid4()))["can_choose"] is False
    assert _choose(client, str(uuid.uuid4())).status_code == 503


def test_test_mode_links_on_a_live_server_switch_support_off(client, configured, monkeypatch):  # R3
    """The setup the third review found dropping every event: test links,
    no key, and STRIPE_MODE left at live."""
    monkeypatch.setattr(settings, "stripe_secret_key", "")
    monkeypatch.setattr(settings, "stripe_payment_links", "6000=https://buy.stripe.com/test_sixty")

    assert _choose(client, str(uuid.uuid4())).status_code == 503


def test_a_one_off_payment_and_other_event_types_are_left_alone(client, configured, db_session):
    assert _deliver(client, _session(mode="payment")).json() == {"result": "ignored"}
    assert _deliver(client, _event("customer.created", {"id": "cus_1"})).json() == {"result": "ignored"}
    assert db_session.query(SupportChoice).count() == 0


def test_only_events_from_ourhikes_own_links_are_believed(client, configured, db_session):  # R3-B5
    """Another product on the same Stripe account can neither enter the
    published total nor be cancelled with OurHike's key."""
    other = _subscription(sub="sub_shop")
    other["data"]["object"]["metadata"] = {}
    invoice = _invoice(sub="sub_shop")
    invoice["data"]["object"]["parent"]["subscription_details"]["metadata"] = {}

    for envelope in (_session(ours=False, sub="sub_shop"), other, invoice):
        assert _deliver(client, envelope).json() == {"result": "ignored"}
    assert db_session.query(SupportChoice).count() == 0
    assert client.get("/support/total").json()["total_cents"] == 0


def test_a_checkout_is_a_payment_only_once_it_is_paid(client, configured, db_session):  # R3
    """A bank debit completes the session unpaid and settles days later."""
    user_id = str(uuid.uuid4())
    choice = _choice_id(_choose(client, user_id))

    assert _deliver(client, _session(choice=choice, paid="unpaid")).json() == {"result": "ignored"}
    assert _me(client, user_id)["status"] == "pending"

    settled = _session(choice=choice, kind="checkout.session.async_payment_succeeded")
    assert _deliver(client, settled).json() == {"result": "active"}


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


def test_a_delivery_the_database_could_not_take_is_refused_so_stripe_sends_it_again(
    client, configured, monkeypatch, db_session
):  # R3-B9
    def unreachable(*args, **kwargs):
        raise OperationalError("SELECT 1", {}, Exception("connection refused"))

    monkeypatch.setattr(support_core, "apply_event", unreachable)

    assert _deliver(client, _session()).status_code == 503
    assert db_session.query(SupportEvent).count() == 0


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


def test_without_the_choice_id_a_payment_is_kept_apart_and_the_founder_told(client, configured, db_session):  # R3-B4
    user_id = str(uuid.uuid4())
    _choose(client, user_id)

    assert _deliver(client, _session(email="HIKER@example.com")).json() == {"result": "active"}

    mine = db_session.query(SupportChoice).filter(SupportChoice.profile_id == user_id).one()
    assert (mine.status, mine.provider_ref) == (SupportStatus.pending, None)
    apart = db_session.query(SupportChoice).filter(SupportChoice.profile_id.is_(None)).one()
    assert (apart.status, apart.provider_ref) == (SupportStatus.active, "sub_777")
    [note] = configured.to("founder@ourhike.org", about="names no OurHike choice")
    assert "sub_777" in _text(note)


def test_a_stranger_who_types_a_hikers_address_can_neither_block_nor_be_stopped_by_them(client, configured, db_session):  # R3-B4
    """The third review's attack on matching by email: nothing here reads
    the address to decide whose a payment is."""
    _deliver(client, _session(sub="sub_stranger", amount=1200))  # the hiker's address, nobody's choice
    hiker = str(uuid.uuid4())

    assert _me(client, hiker)["status"] == "none"
    assert _stop(client, hiker).status_code == 404
    assert _choose(client, hiker).status_code == 200
    assert configured.api.calls == []


def test_a_choice_paid_twice_keeps_the_first_and_stops_the_second(client, configured, db_session):  # R3-B3
    """Two tabs, or the setup email clicked after paying on the website."""
    user_id = str(uuid.uuid4())
    choice = _choice_id(_choose(client, user_id))
    _deliver(client, _session(choice=choice, sub="sub_first"))

    assert _deliver(client, _session(choice=choice, sub="sub_second")).json() == {"result": "unwanted"}

    rows = {row.provider_ref: row for row in db_session.query(SupportChoice).all()}
    assert rows["sub_first"].status == SupportStatus.active
    assert (rows["sub_second"].status, rows["sub_second"].profile_id) == (SupportStatus.stop_requested, user_id)
    [call] = configured.api.calls
    assert call["url"].endswith("/v1/subscriptions/sub_second")
    [note] = configured.to("founder@ourhike.org", about="no longer waiting for one")
    assert "sub_second" in _text(note)


def test_a_payment_for_a_choice_already_stopped_is_stopped_too(client, configured, db_session):  # R3-B3
    """Paid, then Stop pressed before Stripe's webhook landed."""
    user_id = str(uuid.uuid4())
    choice = _choice_id(_choose(client, user_id))
    _stop(client, user_id)

    assert _deliver(client, _session(choice=choice)).json() == {"result": "unwanted"}

    assert db_session.get(SupportChoice, choice).status == SupportStatus.stopped
    mine = _me(client, user_id)
    assert (mine["status"], mine["can_choose"]) == ("stop_requested", True)
    assert len(configured.api.calls) == 1


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


def test_a_payment_from_a_link_with_no_choice_is_never_claimed_by_email(client, configured, db_session):  # S6, R3-B4
    _deliver(client, _session(email="walk-in@example.com", amount=12000))

    [row] = db_session.query(SupportChoice).all()
    assert row.profile_id is None
    assert (row.status, row.amount_cents) == (SupportStatus.active, 12000)

    assert _me(client, str(uuid.uuid4()), email="walk-in@example.com")["status"] == "none"
    db_session.expire_all()
    assert db_session.query(SupportChoice).one().profile_id is None


# ---- The webhook: order and repeats ----


def test_a_retried_delivery_changes_nothing_the_first_did_not(client, configured, db_session):
    session = _session(choice=_choice_id(_choose(client, str(uuid.uuid4()))))
    _deliver(client, session)
    _deliver(client, session)

    assert db_session.query(SupportChoice).count() == 1
    assert db_session.query(SupportEvent).count() == 2
    assert len(configured.to("hiker@example.com", about="You're giving OurHike")) == 1


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

    def ready(self):
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


# ---- Counted by level, as a usage event (#1876 on #1902) ----
#
# The maintainer, poll 2026-10-27: "track once for each dollar level, even 0",
# a paid level counted when Stripe confirms the payment, carrying the level
# only. The $0 half is the phone's (tests/test_routers_usage_events.py).


def _support_rows(db_session) -> list[AnalyticsEvent]:
    db_session.expire_all()
    return db_session.query(AnalyticsEvent).filter(AnalyticsEvent.event == UsageEvent.support_chosen).all()


def test_a_confirmed_payment_is_counted_once_at_its_level_and_names_nobody(client, configured, db_session):
    user_id = str(uuid.uuid4())
    _paying(client, user_id, amount=6000)

    [row] = _support_rows(db_session)
    assert row.support_cents == 6000
    assert row.user_key is None and row.sealed is None and row.has_fix is False
    assert row.platform.value == "web" and row.clubs is None
    assert not any((row.week_first, row.month_first, row.ever_first, row.kind_month_first, row.signed_in))


def test_a_checkout_not_yet_paid_is_not_counted(client, configured, db_session):
    choice = _choice_id(_choose(client, str(uuid.uuid4())))

    _deliver(client, _session(choice=choice, paid="unpaid"))

    assert _support_rows(db_session) == []


def test_a_redelivered_confirmation_is_counted_once(client, configured, db_session):
    choice = _choice_id(_choose(client, str(uuid.uuid4())))
    envelope = _session(choice=choice)

    _deliver(client, envelope)
    _deliver(client, envelope)

    assert len(_support_rows(db_session)) == 1


def test_a_choice_paid_in_two_tabs_is_one_choice_counted_once(client, configured, db_session):
    choice = _choice_id(_choose(client, str(uuid.uuid4())))

    _deliver(client, _session(choice=choice, sub="sub_first"))
    assert _deliver(client, _session(choice=choice, sub="sub_second")).json() == {"result": "unwanted"}

    assert len(_support_rows(db_session)) == 1


def test_a_payment_whose_choice_was_stopped_before_it_landed_is_still_counted_once(client, configured, db_session):
    """Stop pressed before Stripe's confirmation: the payment went through, at
    its level, and is being stopped - one choice, one count."""
    user_id = str(uuid.uuid4())
    choice = _choice_id(_choose(client, user_id))
    _stop(client, user_id)

    assert _deliver(client, _session(choice=choice, amount=1200)).json() == {"result": "unwanted"}

    assert [row.support_cents for row in _support_rows(db_session)] == [1200]


def test_two_payments_from_links_that_named_no_choice_are_two_counts(client, configured, db_session):
    _deliver(client, _session(sub="sub_walk_in_1", amount=12000))
    _deliver(client, _session(sub="sub_walk_in_2", amount=12000))

    assert sorted(row.support_cents for row in _support_rows(db_session)) == [12000, 12000]


def test_a_hiker_who_stops_and_chooses_again_is_counted_at_each_choice(client, configured, db_session, t0):
    user_id = str(uuid.uuid4())
    _paying(client, user_id, sub="sub_one", amount=1200)
    _stop(client, user_id)
    _deliver(client, _subscription("customer.subscription.deleted", sub="sub_one", status="canceled"))

    choice = _choice_id(_choose(client, user_id, amount_cents=6000))
    _deliver(client, _session(choice=choice, sub="sub_two", amount=6000))

    assert sorted(row.support_cents for row in _support_rows(db_session)) == [1200, 6000]


def test_an_account_that_turned_usage_statistics_off_is_not_counted(client, configured, db_session):
    """The account's synced "off" wins, as it does at POST /usage-events."""
    user_id = str(uuid.uuid4())
    _me(client, user_id)
    make_usage_consent(db_session, db_session.get(Profile, user_id), enabled=False, linked=None)
    db_session.commit()

    _paying(client, user_id)

    assert _support_rows(db_session) == []
    assert db_session.query(SupportChoice).filter(SupportChoice.status == SupportStatus.active).count() == 1


def test_a_move_between_providers_is_not_counted_as_a_new_choice(client, configured, monkeypatch, db_session):
    old = OldPay()
    monkeypatch.setitem(PROVIDERS, old.key, old)
    user_id = str(uuid.uuid4())
    _me(client, user_id)
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
    choice = _choice_id(_choose(client, user_id))

    _deliver(client, _session(choice=choice))

    assert _support_rows(db_session) == []


# ---- Unsubscribing ----


def test_a_hikers_support_email_carries_a_real_one_click_unsubscribe(client, configured, monkeypatch, db_session):  # P5
    monkeypatch.setattr(settings, "api_public_url", "https://api.ourhike.org")
    _choose(client, str(uuid.uuid4()), delivery="email")
    token = db_session.query(SupportChoice).one().link_token

    [message] = configured.sent
    headers = _parsed(message)
    assert headers["List-Unsubscribe"] == f"<https://api.ourhike.org/support/mail/stop/{token}>"
    assert f"Choose which emails you get from OurHike: https://api.ourhike.org/support/mail/stop/{token}" in (
        headers.get_body(("plain",)).get_content()
    )

    page = client.get(f"/support/mail/stop/{token}")
    assert page.status_code == 200
    assert page.text.count('role="switch"') == 2
    assert not is_suppressed(db_session, "hiker@example.com")

    # A mail app's own Unsubscribe button: support emails only (poll, 2026-10-27).
    one_click = client.post(f"/support/mail/stop/{token}", content=b"List-Unsubscribe=One-Click")
    assert one_click.status_code == 200
    assert not support_mail_on(db_session, "hiker@example.com")
    assert not is_suppressed(db_session, "hiker@example.com")


def _save_switches(client, token, **on):
    fields = "&".join(["form=1", *(f"{name}=on" for name, value in on.items() if value)])
    return client.post(
        f"/support/mail/stop/{token}",
        content=fields.encode(),
        headers={"content-type": "application/x-www-form-urlencoded"},
    )


def test_the_email_page_switches_each_kind_of_mail_on_and_off(client, configured, monkeypatch, db_session):
    monkeypatch.setattr(settings, "api_public_url", "https://api.ourhike.org")
    _choose(client, str(uuid.uuid4()), delivery="email")
    token = db_session.query(SupportChoice).one().link_token

    assert "Saved." in _save_switches(client, token, support=True, everything=False).text
    db_session.expire_all()
    assert (support_mail_on(db_session, "hiker@example.com"), is_suppressed(db_session, "hiker@example.com")) == (True, True)

    _save_switches(client, token, support=False, everything=True)
    db_session.expire_all()
    assert (support_mail_on(db_session, "hiker@example.com"), is_suppressed(db_session, "hiker@example.com")) == (False, False)


def test_the_email_page_cannot_switch_back_on_an_address_that_bounced(client, configured, monkeypatch, db_session):
    monkeypatch.setattr(settings, "api_public_url", "https://api.ourhike.org")
    _choose(client, str(uuid.uuid4()), delivery="email")
    token = db_session.query(SupportChoice).one().link_token
    suppress(db_session, "hiker@example.com", SuppressionReason.bounced)
    db_session.commit()

    page = client.get(f"/support/mail/stop/{token}")
    assert "disabled" in page.text
    _save_switches(client, token, support=True, everything=True)

    db_session.expire_all()
    assert is_suppressed(db_session, "hiker@example.com")


def test_with_support_emails_off_no_receipt_goes_but_an_asked_for_setup_link_does(client, configured, db_session):
    user_id = str(uuid.uuid4())
    assert (
        client.put(
            "/support/me/mail", json={"support_emails": False}, headers=auth_headers(user_id, email="hiker@example.com")
        ).status_code
        == 200
    )

    _paying(client, user_id)
    assert configured.to("hiker@example.com", about="You're giving OurHike") == []

    other = str(uuid.uuid4())
    client.put("/support/me/mail", json={"support_emails": False}, headers=auth_headers(other, email="store@example.com"))
    _choose(client, other, email="store@example.com", delivery="email")
    assert configured.to("store@example.com", about="Set up your")


def test_the_apps_switch_reads_back_and_turns_support_emails_on_again(client, configured):
    user_id = str(uuid.uuid4())
    _paying(client, user_id)

    off = client.put("/support/me/mail", json={"support_emails": False}, headers=auth_headers(user_id, email="hiker@example.com"))
    assert off.json()["support_emails"] is False
    assert _me(client, user_id)["support_emails"] is False

    on = client.put("/support/me/mail", json={"support_emails": True}, headers=auth_headers(user_id, email="hiker@example.com"))
    assert on.json()["support_emails"] is True


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


def test_one_charge_sent_as_two_events_counts_once(client, configured):  # R3-B6
    """Stripe says some actions produce two events for one object; the
    invoice id, not the event id, is what is counted once."""
    assert _deliver(client, _invoice(invoice="in_one")).json() == {"result": "charged"}
    assert _deliver(client, _invoice(invoice="in_one")).json() == {"result": "duplicate"}

    assert client.get("/support/total").json()["total_cents"] == 6000


@pytest.mark.parametrize("basil", [True, False])
def test_a_charge_that_arrives_before_its_checkout_still_counts_and_joins_it(client, configured, db_session, basil):  # R3-B6
    """Stripe does not promise order: `invoice.paid` often beats the session."""
    _deliver(client, _invoice(sub="sub_early", amount=12000, basil=basil))

    assert client.get("/support/total").json() == {
        "year": utc_now().year,
        "total_cents": 12000,
        "supporters": 1,
        "accepting": True,
    }

    user_id = str(uuid.uuid4())
    choice = _choice_id(_choose(client, user_id, amount_cents=12000))
    _deliver(client, _session(choice=choice, sub="sub_early", amount=12000))

    charge = db_session.query(SupportCharge).one()
    assert charge.choice_id == choice
    assert _me(client, user_id)["period_end"] is not None


def test_a_refund_comes_off_the_total_and_a_second_partial_refund_updates_it(client, configured):
    """The maintainer, 2026-10-27: the published total is net of refunds."""
    _deliver(client, _invoice(amount=6000))

    assert _deliver(client, _refund(refunded=1000)).json() == {"result": "refunded"}
    clear_total_cache()
    assert client.get("/support/total").json()["total_cents"] == 5000

    assert _deliver(client, _refund(refunded=6000)).json() == {"result": "refunded"}
    assert _deliver(client, _refund(refunded=6000)).json() == {"result": "duplicate"}
    clear_total_cache()
    assert client.get("/support/total").json() == {"year": utc_now().year, "total_cents": 0, "supporters": 1, "accepting": True}


def test_a_refund_of_anything_else_on_the_stripe_account_is_left_alone(client, configured, db_session):
    _deliver(client, _invoice(amount=6000))

    assert _deliver(client, _refund(customer="cus_shop")).json() == {"result": "ignored_not_ours"}
    assert db_session.query(SupportCharge).count() == 1


def test_the_refund_event_keeps_no_name_or_email(client, configured, db_session):
    _deliver(client, _invoice(amount=6000))
    _deliver(client, _refund())

    stored = json.dumps([event.payload for event in db_session.query(SupportEvent).all()])
    assert "Ramen Bomb" not in stored and "hiker@example.com" not in stored


def test_the_total_is_computed_at_most_hourly(client, configured):  # C3
    assert client.get("/support/total").json()["total_cents"] == 0
    _deliver(client, _invoice(amount=12000))

    assert client.get("/support/total").json()["total_cents"] == 0


def _charge(at: datetime, cents=6000, currency="USD", subscription="sub_1"):
    return SupportCharge(
        provider="stripe",
        charge_ref=f"in_{uuid.uuid4().hex[:12]}",
        subscription_ref=subscription,
        amount_cents=cents,
        currency=currency,
        charged_at=at,
    )


def test_a_yearly_supporters_renewal_counts_in_the_year_it_was_charged(db_session):
    db_session.add_all([_charge(datetime(2025, 3, 1)), _charge(datetime(2026, 3, 1))])
    db_session.commit()

    assert year_total(db_session, 2025) == (6000, 1)
    assert year_total(db_session, 2026) == (6000, 1)
    assert year_total(db_session, 2027) == (0, 0)


def test_two_renewals_of_one_payment_in_one_year_are_one_supporter(db_session):
    db_session.add_all([_charge(datetime(2026, 1, 5)), _charge(datetime(2026, 12, 30))])
    db_session.commit()

    assert year_total(db_session, 2026) == (12000, 1)


def test_another_currency_is_left_out_of_the_dollar_total(db_session):  # C1
    db_session.add_all([_charge(datetime(2026, 3, 1), currency="EUR"), _charge(datetime(2026, 4, 1), subscription="sub_2")])
    db_session.commit()

    assert year_total(db_session, 2026) == (6000, 1)


def test_a_refund_counts_in_the_year_it_was_made(db_session):
    db_session.add_all([_charge(datetime(2026, 12, 1)), _charge(datetime(2027, 1, 5), cents=-6000)])
    db_session.commit()

    assert year_total(db_session, 2026) == (6000, 1)
    assert year_total(db_session, 2027) == (-6000, 0)


# ---- Keeping paid records seven years, then not ----


def _ended_row(db_session, *, profile_id=None, ended=None, status=SupportStatus.stopped):
    row = SupportChoice(
        profile_id=profile_id,
        email="hiker@example.com",
        provider="stripe",
        provider_ref=f"sub_{uuid.uuid4().hex[:8]}",
        amount_cents=6000,
        status=status,
        ended_at=ended,
    )
    db_session.add(row)
    db_session.flush()
    db_session.add(_charge(datetime(2018, 3, 1), subscription=row.provider_ref))
    db_session.query(SupportCharge).filter(SupportCharge.subscription_ref == row.provider_ref).update(
        {SupportCharge.choice_id: row.id}
    )
    db_session.commit()
    return row.id


def test_a_deleted_accounts_paid_record_goes_seven_years_after_it_ended(client, db_session):
    """The maintainer's seven years (poll, 2026-10-27)."""
    gone = str(uuid.uuid4())
    _me(client, gone)  # creates the profile
    db_session.query(Profile).filter(Profile.id == gone).update({Profile.deleted_at: utc_now()})
    db_session.commit()
    old = _ended_row(db_session, profile_id=gone, ended=utc_now() - support_core.RETENTION - timedelta(days=1))
    recent = _ended_row(db_session, profile_id=gone, ended=utc_now() - timedelta(days=400))

    assert support_core.purge_expired(db_session) == 1
    db_session.commit()

    assert db_session.get(SupportChoice, old) is None
    assert db_session.get(SupportChoice, recent) is not None
    assert db_session.query(SupportCharge).filter(SupportCharge.choice_id == old).count() == 0


def test_a_live_accounts_record_and_anything_still_charging_are_never_purged(client, db_session):
    live = str(uuid.uuid4())
    _me(client, live)
    ancient = utc_now() - support_core.RETENTION - timedelta(days=30)
    kept = [
        _ended_row(db_session, profile_id=live, ended=ancient),
        _ended_row(db_session, ended=ancient, status=SupportStatus.stop_requested),
    ]

    assert support_core.purge_expired(db_session) == 0
    assert all(db_session.get(SupportChoice, row_id) is not None for row_id in kept)
