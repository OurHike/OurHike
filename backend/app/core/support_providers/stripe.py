"""Stripe, behind the provider seam (#1876). See base.py for the seam.

The maintainer replaced Buy Me a Coffee with Stripe on 2026-10-27, before any
supporter existed, for four things this project found no way to do through
Buy Me a Coffee (searched 2026-10-23 and by the #1885 review): carry
OurHike's own choice id through checkout (so a payment never has to be
matched by an email anybody can type), preselect the tier, cancel by API (so
Stop needs nobody to do it by hand), and report every renewal charge (so the
published total is read rather than reasoned).

Everything here is read off Stripe's documentation (docs.stripe.com, read
2026-10-27):

- **Checkout is a Payment Link per tier.** A link accepts
  `client_reference_id` (letters, digits, `-` and `_`, up to 200; anything
  else is silently dropped) and `prefilled_email` (editable by the payer), and
  hands both to the `checkout.session.completed` event. A link never expires,
  which the store apps' setup email needs, and making one URL needs no key.
- **Each delivery is signed** in `Stripe-Signature`: `t=<unix>,v1=<hex>`,
  where the hex is HMAC-SHA256 of `<t>.<raw body>` under the endpoint's
  signing secret. Stripe's own libraries refuse a `t` more than five minutes
  from now, which is the replay window `TOLERANCE_SECONDS` keeps.
- **Stripe resends the same event id on a retry**, and its docs say to guard
  against duplicates by logging event ids - which core/support.py does for
  the one event where a duplicate would count twice, a charge.
- **API version 2025-03-31.basil moved fields**: a subscription's period end
  is on its items, and an invoice's subscription is under
  `parent.subscription_details`. Both shapes are read, so the webhook
  endpoint's API version does not matter.

**WHAT IS KEPT** is a short list of fields named in `_payload`, not the event
minus a few: a Stripe object carries the payer's name, address and card
brand, and none of it is stored. The email is kept on the choice, never in
the event log.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import re
import time
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any, Literal
from urllib.parse import urlencode

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.core.mail import normalise
from app.core.support_mail import email_founder_to_cancel
from app.core.support_providers.base import EventKind, ProviderEvent
from app.models.support import SupportCadence, SupportChoice

log = logging.getLogger(__name__)

API = "https://api.stripe.com"

# Stripe's own libraries' default: a signature older (or newer) than this is
# a replay, whatever its HMAC says.
TOLERANCE_SECONDS = 300

# The largest single amount believed, in cents: $100,000, this stage's whole
# yearly line. A signed delivery claiming more is a fault, not a supporter,
# and it would otherwise go straight into the published total.
MAX_AMOUNT_CENTS = 10_000_000

# RFC 5321's longest path, and the column's width.
MAX_EMAIL_LENGTH = 320

# What may go in a URL path or a client_reference_id without escaping.
_SUBSCRIPTION_ID = re.compile(r"^sub_[A-Za-z0-9]{1,90}$")
_CHOICE_ID = re.compile(r"^[A-Za-z0-9_-]{1,200}$")

_SUBSCRIPTION_KINDS = {
    "customer.subscription.updated": EventKind.updated,
    "customer.subscription.paused": EventKind.paused,
    "customer.subscription.resumed": EventKind.updated,
    "customer.subscription.deleted": EventKind.ended,
}


def _when(unix: Any) -> datetime | None:
    if isinstance(unix, bool) or not isinstance(unix, (int, float)):
        return None
    try:
        return datetime.fromtimestamp(unix, tz=timezone.utc).replace(tzinfo=None)
    except (OverflowError, OSError, ValueError):
        return None


def _cents(amount: Any) -> int | None:
    """Stripe amounts are already integer cents. None for anything not a sane
    positive amount."""
    if isinstance(amount, bool) or not isinstance(amount, int):
        return None
    return amount if 0 < amount <= MAX_AMOUNT_CENTS else None


def _ref(value: Any) -> str | None:
    if isinstance(value, str) and value.strip() and len(value) <= 100:
        return value.strip()
    if isinstance(value, Mapping):
        # An expanded object instead of its id.
        return _ref(value.get("id"))
    return None


def _currency(value: Any) -> str | None:
    return value.upper() if isinstance(value, str) and len(value) == 3 else None


def _email(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    address = normalise(value)
    return address if address and len(address) <= MAX_EMAIL_LENGTH else None


def _first_item(subscription: Mapping[str, Any]) -> Mapping[str, Any]:
    items = subscription.get("items")
    data = items.get("data") if isinstance(items, Mapping) else None
    return data[0] if isinstance(data, list) and data and isinstance(data[0], Mapping) else {}


def payment_links() -> dict[int, str]:
    """`settings.stripe_payment_links` as {cents: url}, https links only."""
    links: dict[int, str] = {}
    for pair in settings.stripe_payment_links.split(","):
        cents, _, url = pair.strip().partition("=")
        url = url.strip()
        if cents.strip().isdigit() and url.startswith("https://"):
            links[int(cents)] = url
    return links


class Stripe:
    key = "stripe"
    label = "Stripe"
    cancel: Literal["api", "manual"] = "api"

    def checkout_url(self, choice: SupportChoice) -> str | None:
        """The tier's Payment Link, carrying this choice's id and email."""
        link = payment_links().get(choice.amount_cents)
        if link is None or not _CHOICE_ID.match(choice.id or ""):
            return None
        query = {"client_reference_id": choice.id}
        if choice.email:
            query["prefilled_email"] = choice.email
        return f"{link}{'&' if '?' in link else '?'}{urlencode(query)}"

    def webhook_configured(self) -> bool:
        return bool(settings.stripe_webhook_secret)

    def verify(self, headers: Mapping[str, str], raw_body: bytes) -> bool:
        secret = settings.stripe_webhook_secret
        header = headers.get("stripe-signature")
        if not secret or not header or not header.isascii():
            return False
        timestamp = None
        signatures = []
        for part in header.split(","):
            name, _, value = part.strip().partition("=")
            if name == "t":
                timestamp = value
            elif name == "v1":
                signatures.append(value)
        if timestamp is None or not timestamp.isdigit() or not signatures:
            return False
        if abs(time.time() - int(timestamp)) > TOLERANCE_SECONDS:
            return False
        expected = hmac.new(secret.encode(), timestamp.encode() + b"." + raw_body, hashlib.sha256).hexdigest()
        return any(hmac.compare_digest(expected, signature) for signature in signatures)

    def _expected_livemode(self) -> bool:
        """Live events only, unless this backend holds a test-mode key - which
        is how UA runs against Stripe's test mode without production ever
        believing a test event."""
        return "_test_" not in settings.stripe_secret_key

    def normalise(self, envelope: Mapping[str, Any]) -> list[ProviderEvent]:
        if envelope.get("livemode") is not self._expected_livemode():
            return []
        data = envelope.get("data")
        obj = data.get("object") if isinstance(data, Mapping) else None
        if not isinstance(obj, Mapping):
            return []
        kind = envelope.get("type")
        event_id = _ref(envelope.get("id"))
        created = _when(envelope.get("created"))

        if kind == "checkout.session.completed":
            if obj.get("mode") != "subscription":
                return []
            details = obj.get("customer_details")
            email = _email(details.get("email") if isinstance(details, Mapping) else None)
            choice = obj.get("client_reference_id")
            return [
                ProviderEvent(
                    kind=EventKind.started,
                    event_id=event_id,
                    occurred_at=created,
                    subscription_ref=_ref(obj.get("subscription")),
                    customer_ref=_ref(obj.get("customer")),
                    plan_ref=_ref(obj.get("payment_link")),
                    choice_ref=choice if isinstance(choice, str) and _CHOICE_ID.match(choice) else None,
                    email=email or _email(obj.get("customer_email")),
                    amount_cents=_cents(obj.get("amount_total")),
                    currency=_currency(obj.get("currency")),
                    started_at=_when(obj.get("created")),
                    payload=_payload(kind, obj),
                )
            ]

        if kind in _SUBSCRIPTION_KINDS:
            event_kind = _SUBSCRIPTION_KINDS[kind]
            status = obj.get("status")
            if status in ("canceled", "incomplete_expired"):
                event_kind = EventKind.ended
            elif status == "incomplete":
                # The first payment has not gone through; nothing exists yet.
                return []
            elif status == "paused" or obj.get("pause_collection"):
                event_kind = EventKind.paused
            item = _first_item(obj)
            price = item.get("price") if isinstance(item.get("price"), Mapping) else {}
            recurring = price.get("recurring") if isinstance(price.get("recurring"), Mapping) else {}
            quantity = item.get("quantity") if isinstance(item.get("quantity"), int) else 1
            unit = price.get("unit_amount")
            interval = recurring.get("interval")
            cancel_at = _when(obj.get("cancel_at"))
            period_end = _when(item.get("current_period_end")) or _when(obj.get("current_period_end"))
            return [
                ProviderEvent(
                    kind=event_kind,
                    event_id=event_id,
                    occurred_at=created,
                    subscription_ref=_ref(obj.get("id")),
                    customer_ref=_ref(obj.get("customer")),
                    plan_ref=_ref(price.get("id")),
                    amount_cents=_cents(unit * quantity) if isinstance(unit, int) else None,
                    currency=_currency(obj.get("currency") or price.get("currency")),
                    cadence=SupportCadence(interval) if interval in ("year", "month") else None,
                    # An ended subscription has no period left to schedule an
                    # end for, whatever its last flags said.
                    period_end=None if event_kind is EventKind.ended else cancel_at or period_end,
                    cancel_at_period_end=None
                    if event_kind is EventKind.ended
                    else bool(obj.get("cancel_at_period_end")) or cancel_at is not None,
                    started_at=_when(obj.get("start_date")),
                    payload=_payload(kind, obj),
                )
            ]

        if kind == "invoice.paid":
            parent = obj.get("parent")
            details = parent.get("subscription_details") if isinstance(parent, Mapping) else None
            subscription = _ref(details.get("subscription")) if isinstance(details, Mapping) else None
            subscription = subscription or _ref(obj.get("subscription"))
            amount = _cents(obj.get("amount_paid"))
            if subscription is None or amount is None:
                return []
            transitions = obj.get("status_transitions")
            paid_at = _when(transitions.get("paid_at")) if isinstance(transitions, Mapping) else None
            return [
                ProviderEvent(
                    kind=EventKind.charged,
                    event_id=event_id,
                    occurred_at=paid_at or created,
                    subscription_ref=subscription,
                    customer_ref=_ref(obj.get("customer")),
                    amount_cents=amount,
                    currency=_currency(obj.get("currency")),
                    # The total reads these three off the stored event.
                    payload=_payload(kind, obj, subscription=subscription, amount_cents=amount),
                )
            ]
        return []

    def request_cancel(self, db: Session, choice: SupportChoice, mail_provider: Any) -> bool:
        """Stop the subscription renewing (`cancel_at_period_end`), keeping the
        year already paid for. Falls back to asking the founder by email when
        no key is configured or Stripe refuses, so a Stop is never stranded."""
        ref = choice.provider_ref or ""
        if settings.stripe_secret_key and _SUBSCRIPTION_ID.match(ref):
            try:
                response = httpx.post(
                    f"{API}/v1/subscriptions/{ref}",
                    data={"cancel_at_period_end": "true"},
                    auth=(settings.stripe_secret_key, ""),
                    # The same request twice is the same cancellation.
                    headers={"Idempotency-Key": f"ourhike-stop-{choice.id}"},
                    timeout=10.0,
                )
                if response.status_code == 200:
                    return True
                log.warning("support: Stripe refused the stop for choice %s: HTTP %s", choice.id, response.status_code)
            except httpx.HTTPError as exc:
                log.warning("support: Stripe unreachable for the stop of choice %s: %s", choice.id, type(exc).__name__)
        return email_founder_to_cancel(
            db,
            choice,
            provider_label=self.label,
            refs=[("Stripe subscription id", choice.provider_ref), ("Stripe customer id", choice.customer_ref)],
            how="The app could not cancel it through Stripe's API. In the Stripe dashboard, open "
            "Subscriptions, find this id, and choose Cancel at end of period. Stripe's webhook then "
            "records it and emails the hiker that it is done.",
            mail_provider=mail_provider,
        )


def _payload(kind: str, obj: Mapping[str, Any], **extra: Any) -> dict[str, Any]:
    """The few fields worth keeping, by name - never the payer's name,
    address, card or email."""
    item = _first_item(obj)
    price = item.get("price") if isinstance(item.get("price"), Mapping) else {}
    recurring = price.get("recurring") if isinstance(price.get("recurring"), Mapping) else {}
    kept = {
        "type": kind,
        "object_id": _ref(obj.get("id")),
        "status": obj.get("status") if isinstance(obj.get("status"), str) else None,
        "subscription": _ref(obj.get("subscription")),
        "customer": _ref(obj.get("customer")),
        "client_reference_id": obj.get("client_reference_id") if isinstance(obj.get("client_reference_id"), str) else None,
        "payment_link": _ref(obj.get("payment_link")),
        "amount_total": obj.get("amount_total") if isinstance(obj.get("amount_total"), int) else None,
        "currency": _currency(obj.get("currency")),
        "price": _ref(price.get("id")),
        "interval": recurring.get("interval") if isinstance(recurring.get("interval"), str) else None,
        "cancel_at_period_end": obj.get("cancel_at_period_end") if isinstance(obj.get("cancel_at_period_end"), bool) else None,
        "billing_reason": obj.get("billing_reason") if isinstance(obj.get("billing_reason"), str) else None,
        **extra,
    }
    return {name: value for name, value in kept.items() if value is not None}
