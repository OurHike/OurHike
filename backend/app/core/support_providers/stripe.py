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
  A link's metadata is copied to the sessions it makes, and its
  `subscription_data.metadata` to the subscription.
- **Only OurHike's own links are believed.** Every event must carry the
  `ourhike_tier_cents` metadata those links set (on the session, the
  subscription, or the invoice's subscription snapshot); anything else on
  the account - another product, a one-off link - is ignored, so it can
  neither enter the published total nor be cancelled with OurHike's key (the
  third #1885 review).
- **A session is a payment only once it is paid.** `payment_status` must be
  `paid`; a bank debit that settles later arrives as
  `checkout.session.async_payment_succeeded`.
- **Each delivery is signed** in `Stripe-Signature`: `t=<unix>,v1=<hex>`,
  where the hex is HMAC-SHA256 of `<t>.<raw body>` under the endpoint's
  signing secret. Stripe's own libraries refuse a `t` more than five minutes
  from now, which is the replay window `TOLERANCE_SECONDS` keeps.
- **A charge is counted once by its invoice id**, which core/support.py keeps
  unique: Stripe resends an event with the same id on a retry, and says some
  actions produce two separate events for one object.
- **A refund is `charge.refunded`**, carrying the Charge with its running
  `amount_refunded`. Since API version 2025-03-31.basil a Charge no longer
  names its invoice, and finding it takes the Invoice Payments API and a key
  allowed to read invoices ("Using webhooks with subscriptions", read
  2026-10-27). A Charge names its `customer` in every version, and every
  Payment Link checkout makes a customer of its own, so the refund is passed
  on with that and core/support.py counts it only when the customer is one
  of OurHike's. A Charge carries no subscription metadata, so this one event
  is exempt from the metadata check below and filtered there instead.
- **A failed renewal is `past_due`, then `unpaid`**, while Stripe retries the
  card. Cancelling at the period's end would leave that open invoice being
  retried; cancelling the subscription outright stops it. So a Stop on a
  failing renewal cancels at once (`request_cancel`).
- **API version 2025-03-31.basil moved fields**: a subscription's period end
  is on its items, and an invoice's subscription is under
  `parent.subscription_details`. Both shapes are read, so the webhook
  endpoint's API version does not matter.

**WHAT IS KEPT** is a short list of fields named in `_payload`, not the event
minus a few: a Stripe object carries the payer's name, address and card
brand, and none of it is stored. The email is kept on the choice, never in
the event log. An event this module ignores is logged by type and id only.
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

# The metadata key OurHike's Payment Links set on their sessions and
# subscriptions (features/SUPPORTING_OURHIKE.md §7). Its presence is what
# makes an event OurHike's.
MARKER = "ourhike_tier_cents"

# The subscription states in which a renewal is failing and Stripe is still
# retrying the card - a Stop then cancels at once.
FAILING = ("past_due", "unpaid")

# What may go in a URL path or a client_reference_id without escaping.
_SUBSCRIPTION_ID = re.compile(r"^sub_[A-Za-z0-9]{1,90}$")
_CHOICE_ID = re.compile(r"^[A-Za-z0-9_-]{1,200}$")

_SESSION_KINDS = ("checkout.session.completed", "checkout.session.async_payment_succeeded")

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


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _first_item(obj: Mapping[str, Any]) -> Mapping[str, Any]:
    """The first line of a subscription's `items` or an invoice's `lines`."""
    for key in ("items", "lines"):
        data = _mapping(obj.get(key)).get("data")
        if isinstance(data, list) and data and isinstance(data[0], Mapping):
            return data[0]
    return {}


def _is_ourhike(obj: Mapping[str, Any]) -> bool:
    """Whether an object came from one of OurHike's Payment Links, by the
    metadata those links set (`MARKER`). An invoice carries its
    subscription's metadata as a snapshot, in either API version's place."""
    if MARKER in _mapping(obj.get("metadata")):
        return True
    details = _mapping(_mapping(obj.get("parent")).get("subscription_details")) or _mapping(obj.get("subscription_details"))
    return MARKER in _mapping(details.get("metadata"))


def _tier(obj: Mapping[str, Any]) -> int | None:
    """The tier in cents a year that OurHike's link set as `MARKER`, or None."""
    value = _mapping(obj.get("metadata")).get(MARKER)
    if isinstance(value, str) and value.isdigit() and 0 < len(value) <= 7:
        return int(value)
    return None


def payment_links() -> dict[int, str]:
    """`settings.stripe_payment_links` as {cents: url}, https links only."""
    links: dict[int, str] = {}
    for pair in settings.stripe_payment_links.split(","):
        cents, _, url = pair.strip().partition("=")
        url = url.strip()
        if cents.strip().isdigit() and url.startswith("https://"):
            links[int(cents)] = url
    return links


def _ignored(kind: Any, event_id: str | None, why: str) -> list[ProviderEvent]:
    log.info("support: stripe %s %s ignored: %s", kind, event_id, why)
    return []


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

    def _live(self) -> bool:
        return settings.stripe_mode != "test"

    def ready(self) -> bool:
        """Links to pay on, a webhook to record it, and a way to stop it: the
        restricted key, or failing that the founder's address. A key or a link
        from the other mode than `stripe_mode` is a misconfiguration, so not
        ready: a server taking test-mode payments while it believes only
        live-mode events would record none of them (the third #1885 review)."""
        key = settings.stripe_secret_key
        if key and ("_test_" in key) == self._live():
            log.warning("support: STRIPE_SECRET_KEY is for the other mode than STRIPE_MODE; support is off")
            return False
        links = payment_links()
        # Stripe's test-mode Payment Links live under buy.stripe.com/test_.
        if any(("/test_" in url) == self._live() for url in links.values()):
            log.warning("support: STRIPE_PAYMENT_LINKS are for the other mode than STRIPE_MODE; support is off")
            return False
        can_stop = bool(key) or bool(settings.support_notify_address)
        return bool(links) and self.webhook_configured() and can_stop

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
        # Twelve digits is the year 33658; a longer `t` is not a timestamp,
        # and int() on thousands of digits raises (the #1885 review).
        if timestamp is None or not timestamp.isdigit() or len(timestamp) > 12 or not signatures:
            return False
        if abs(time.time() - int(timestamp)) > TOLERANCE_SECONDS:
            return False
        expected = hmac.new(secret.encode(), timestamp.encode() + b"." + raw_body, hashlib.sha256).hexdigest()
        return any(hmac.compare_digest(expected, signature) for signature in signatures)

    def normalise(self, envelope: Mapping[str, Any]) -> list[ProviderEvent]:
        kind = envelope.get("type")
        event_id = _ref(envelope.get("id"))
        if envelope.get("livemode") is not self._live():
            # Loud, because every event dropped this way is a payment the
            # server will never record: usually STRIPE_MODE left unset.
            log.warning("support: stripe %s %s ignored: livemode is not %s (STRIPE_MODE)", kind, event_id, self._live())
            return []
        obj = _mapping(_mapping(envelope.get("data")).get("object"))
        if not obj:
            return _ignored(kind, event_id, "no object")
        if kind not in _SESSION_KINDS and kind not in _SUBSCRIPTION_KINDS and kind not in ("invoice.paid", "charge.refunded"):
            return _ignored(kind, event_id, "not an event support uses")
        created = _when(envelope.get("created"))
        if kind == "charge.refunded":
            refunded = _cents(obj.get("amount_refunded"))
            charge = _ref(obj.get("id"))
            customer = _ref(obj.get("customer"))
            if refunded is None or charge is None or customer is None:
                return _ignored(kind, event_id, "no amount, charge or customer")
            return [
                ProviderEvent(
                    kind=EventKind.refunded,
                    event_id=event_id,
                    occurred_at=created,
                    charge_ref=charge,
                    customer_ref=customer,
                    amount_cents=refunded,
                    currency=_currency(obj.get("currency")),
                    payload=_payload(kind, obj, amount_refunded=refunded),
                )
            ]
        if not _is_ourhike(obj):
            return _ignored(kind, event_id, f"no {MARKER} metadata, so not one of OurHike's links")

        if kind in _SESSION_KINDS:
            if obj.get("mode") != "subscription":
                return _ignored(kind, event_id, "not a subscription")
            if obj.get("payment_status") != "paid":
                return _ignored(kind, event_id, "not paid yet")
            details = _mapping(obj.get("customer_details"))
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
                    email=_email(details.get("email")) or _email(obj.get("customer_email")),
                    amount_cents=_cents(obj.get("amount_total")),
                    tier_cents=_tier(obj),
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
                return _ignored(kind, event_id, "first payment not through yet")
            elif status in FAILING:
                event_kind = EventKind.failing
            elif status == "paused" or obj.get("pause_collection"):
                event_kind = EventKind.paused
            ended = event_kind is EventKind.ended
            item = _first_item(obj)
            price = _mapping(item.get("price"))
            recurring = _mapping(price.get("recurring"))
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
                    provider_status=status if isinstance(status, str) else None,
                    amount_cents=_cents(unit * quantity) if isinstance(unit, int) else None,
                    currency=_currency(obj.get("currency") or price.get("currency")),
                    cadence=SupportCadence(interval) if interval in ("year", "month") else None,
                    # An ended subscription has no period left to schedule an
                    # end for, whatever its last flags said.
                    period_end=None if ended else cancel_at or period_end,
                    cancel_at_period_end=None if ended else bool(obj.get("cancel_at_period_end")) or cancel_at is not None,
                    started_at=_when(obj.get("start_date")),
                    payload=_payload(kind, obj),
                )
            ]

        # invoice.paid
        details = _mapping(_mapping(obj.get("parent")).get("subscription_details"))
        subscription = _ref(details.get("subscription")) or _ref(obj.get("subscription"))
        amount = _cents(obj.get("amount_paid"))
        charge = _ref(obj.get("id"))
        if subscription is None or amount is None or charge is None:
            return _ignored(kind, event_id, "no subscription, amount or invoice id")
        paid_at = _when(_mapping(obj.get("status_transitions")).get("paid_at"))
        line_period = _mapping(_first_item(obj).get("period"))
        return [
            ProviderEvent(
                kind=EventKind.charged,
                event_id=event_id,
                occurred_at=paid_at or created,
                subscription_ref=subscription,
                charge_ref=charge,
                customer_ref=_ref(obj.get("customer")),
                amount_cents=amount,
                currency=_currency(obj.get("currency")),
                period_end=_when(line_period.get("end")),
                payload=_payload(kind, obj, subscription=subscription, amount_paid=amount),
            )
        ]

    def refund_from_log(self, payload: Mapping[str, Any], occurred_at: datetime | None) -> ProviderEvent | None:
        """A `charge.refunded` rebuilt from the fields `_payload` logged for it."""
        if payload.get("type") != "charge.refunded":
            return None
        charge, customer = _ref(payload.get("object_id")), _ref(payload.get("customer"))
        refunded = _cents(payload.get("amount_refunded"))
        if charge is None or customer is None or refunded is None:
            return None
        return ProviderEvent(
            kind=EventKind.refunded,
            occurred_at=occurred_at,
            charge_ref=charge,
            customer_ref=customer,
            amount_cents=refunded,
            currency=_currency(payload.get("currency")),
            payload=dict(payload),
        )

    def request_cancel(self, db: Session, choice: SupportChoice, mail_provider: Any) -> bool:
        """Stop one subscription, as the hiker's Stop asked.

        A renewal that is failing (`past_due`, `unpaid`) is cancelled at once:
        cancelling at the period's end would leave Stripe retrying the open
        invoice, and a retry that succeeds charges a year after the hiker was
        told "nothing more will be charged" (the #1885 reviews). Anything
        else stops renewing (`cancel_at_period_end`), keeping the year already
        paid for. Falls back to asking the founder by email when no key is
        configured or Stripe refuses, so a Stop is never stranded.

        No Idempotency-Key: both calls leave the same state however often
        they are made, and a fixed key would replay a refusal, or a stale
        success, for 24 hours (Stripe's idempotency docs).
        """
        ref = choice.provider_ref or ""
        now = choice.provider_status in FAILING
        if settings.stripe_secret_key and _SUBSCRIPTION_ID.match(ref):
            try:
                if now:
                    response = httpx.delete(f"{API}/v1/subscriptions/{ref}", auth=(settings.stripe_secret_key, ""), timeout=10.0)
                else:
                    response = httpx.post(
                        f"{API}/v1/subscriptions/{ref}",
                        data={"cancel_at_period_end": "true"},
                        auth=(settings.stripe_secret_key, ""),
                        timeout=10.0,
                    )
                if response.status_code == 200:
                    return True
                log.warning("support: Stripe refused the stop for choice %s: HTTP %s", choice.id, response.status_code)
            except httpx.HTTPError as exc:
                log.warning("support: Stripe unreachable for the stop of choice %s: %s", choice.id, type(exc).__name__)
        how = (
            "Its renewal payment is failing and Stripe is retrying the card, so cancel it IMMEDIATELY in the "
            "Stripe dashboard (Subscriptions, find this id, Cancel subscription, Immediately) - cancelling at "
            "the period's end would let a retry still charge them."
            if now
            else "In the Stripe dashboard, open Subscriptions, find this id, and choose Cancel at end of period."
        )
        return email_founder_to_cancel(
            db,
            choice,
            provider_label=self.label,
            refs=[("Stripe subscription id", choice.provider_ref), ("Stripe customer id", choice.customer_ref)],
            how="The app could not cancel it through Stripe's API. "
            + how
            + " Stripe's webhook then records it and emails the hiker that it is done.",
            mail_provider=mail_provider,
        )


def _payload(kind: str, obj: Mapping[str, Any], **extra: Any) -> dict[str, Any]:
    """The few fields worth keeping, by name - never the payer's name,
    address, card or email."""
    item = _first_item(obj)
    price = _mapping(item.get("price"))
    recurring = _mapping(price.get("recurring"))
    kept = {
        "type": kind,
        "object_id": _ref(obj.get("id")),
        "status": obj.get("status") if isinstance(obj.get("status"), str) else None,
        "payment_status": obj.get("payment_status") if isinstance(obj.get("payment_status"), str) else None,
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
