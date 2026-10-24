"""Supporting OurHike: Buy Me a Coffee's webhook, Stop, and the total (#1876).

The decisions are the maintainer's, by poll on 2026-10-23, and
features/SUPPORTING_OURHIKE.md is their one home. What this module adds is
the mechanism, and three things about it worth knowing before changing it.

**A WEBHOOK IS ONLY BELIEVED WITH A GOOD SIGNATURE.** Buy Me a Coffee signs
each delivery with HMAC-SHA256 of the raw body under the secret shown on the
webhook's own page, hex in `x-signature-sha256` (its webhook OpenAPI spec,
read 2026-10-23). Without that check anybody could POST "membership.started"
for an address of their choosing and make the app stop asking them - or
inflate the published total. So a missing secret refuses everything rather
than accepting everything.

**DELIVERIES ARE RETRIED AND MAY REPEAT**, up to four times (the same spec),
so every handler here sets a state rather than incrementing one: applying the
same event twice leaves the row where once did.

**TEST EVENTS ARE IGNORED.** The dashboard's "Send test event" arrives with
`live_mode: false`, and recording it would put a fake supporter into the
published total.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.core.mail import MailDisabled, MailFailed, MailSuppressed, normalise, send
from app.core.time import utc_now
from app.models.mail import MailPurpose
from app.models.support import SupportCadence, SupportChoice, SupportStatus

log = logging.getLogger(__name__)

PROVIDER = "buymeacoffee"

# The events this module acts on. Everything else Buy Me a Coffee sends
# (donations, shop purchases, wishlist payments) is acknowledged and left
# alone: OurHike offers memberships only, and a one-off coffee somebody buys
# on the page directly is not a choice anybody made in the app.
MEMBERSHIP_EVENTS = {"membership.started", "membership.updated", "membership.cancelled", "membership.paused"}


def signature_ok(raw_body: bytes, signature: str | None, secret: str) -> bool:
    """Buy Me a Coffee's own recipe, constant-time. False on anything missing."""
    if not secret or not signature:
        return False
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature.strip().lower())


def _when(unix: Any) -> datetime | None:
    """A payload's Unix seconds as naive UTC, or None for anything else."""
    if isinstance(unix, bool) or not isinstance(unix, (int, float)):
        return None
    return datetime.fromtimestamp(unix, tz=timezone.utc).replace(tzinfo=None)


def _cents(amount: Any) -> int | None:
    """`amount` is a number of whole currency units (the spec: `number`)."""
    if isinstance(amount, bool) or not isinstance(amount, (int, float)):
        return None
    return int(round(amount * 100))


def _find(db: Session, ref: str | None, email: str | None) -> SupportChoice | None:
    """The row an event is about: by Buy Me a Coffee's own id when this
    server has seen it before, else the newest pending choice made with the
    same email - which is the moment a choice in the app meets the payment."""
    if ref:
        row = (
            db.query(SupportChoice)
            .filter(SupportChoice.provider == PROVIDER, SupportChoice.provider_ref == ref)
            .order_by(SupportChoice.chosen_at.desc().nullslast())
            .first()
        )
        if row is not None:
            return row
    if email:
        return (
            db.query(SupportChoice)
            .filter(
                SupportChoice.email == email,
                SupportChoice.provider_ref.is_(None),
                SupportChoice.status == SupportStatus.pending,
            )
            .order_by(SupportChoice.chosen_at.desc().nullslast())
            .first()
        )
    return None


def apply_event(db: Session, envelope: dict[str, Any], now: datetime | None = None) -> str:
    """Apply one verified delivery. Returns a word for the acknowledgement.

    Does not commit - the router owns the transaction.
    """
    now = now or utc_now()
    kind = envelope.get("type")
    if envelope.get("live_mode") is False:
        return "ignored_test_event"
    if kind not in MEMBERSHIP_EVENTS:
        return "ignored_event_type"

    data = envelope.get("data")
    if not isinstance(data, dict):
        return "ignored_no_data"

    ref = str(data["id"]) if isinstance(data.get("id"), int) else None
    raw_email = data.get("supporter_email")
    email = normalise(raw_email) if isinstance(raw_email, str) and raw_email.strip() else None
    row = _find(db, ref, email)

    if kind == "membership.started" or kind == "membership.updated":
        if row is None:
            if email is None:
                return "ignored_no_supporter"
            # Somebody joined on the page without choosing in the app. Kept,
            # unattached, so the total is honest; a later choice by an
            # account with this email does not claim it automatically - that
            # would let anybody who signs up with an address read a stranger's
            # history - so a maintainer links it if asked.
            row = SupportChoice(email=email, provider=PROVIDER, amount_cents=0, chosen_at=None)
            db.add(row)
        row.provider_ref = ref or row.provider_ref
        psp = data.get("psp_id")
        if isinstance(psp, str) and psp:
            row.psp_ref = psp
        cents = _cents(data.get("amount"))
        if cents is not None:
            row.amount_cents = cents
        currency = data.get("currency")
        if isinstance(currency, str) and len(currency) == 3:
            row.currency = currency.upper()
        duration = data.get("duration_type")
        if duration in (SupportCadence.year.value, SupportCadence.month.value):
            row.cadence = SupportCadence(duration)
        row.started_at = row.started_at or _when(data.get("started_at")) or now

        cancelled = data.get("status") == "canceled" or data.get("canceled") == "true"
        if cancelled:
            row.status = SupportStatus.stopped
            row.ended_at = row.ended_at or _when(data.get("canceled_at")) or now
            return "stopped"
        # A Stop the founder has not got to yet stays requested: an
        # `updated` from a renewal must not quietly undo it.
        if row.status != SupportStatus.stop_requested:
            row.status = SupportStatus.active
        return "active"

    if kind == "membership.cancelled":
        if row is None:
            return "ignored_unknown_membership"
        row.status = SupportStatus.stopped
        row.ended_at = row.ended_at or _when(data.get("canceled_at")) or now
        return "stopped"

    # membership.paused. @unvalidated: what a paused membership means for a
    # yearly supporter is not known - Buy Me a Coffee's spec says a member or
    # the creator can pause one and gives no billing semantics. Left exactly
    # as it was rather than guessed at; the event is logged so the first real
    # one can settle it.
    log.info("support: membership.paused for %s left unchanged", ref)
    return "paused_unchanged"


def year_total(db: Session, year: int, now: datetime | None = None) -> tuple[int, int]:
    """(cents, supporters) given in `year`, before fees.

    **Reasoned from start dates, not read from payouts.** Nothing Buy Me a
    Coffee sends reports each renewal charge, so a yearly membership is
    counted once in the year it started and once in every later year whose
    anniversary has passed before it ended. A refunded or failed charge would
    make this high, and nothing here can see one - which is why the page
    calls it "given", reads it live, and never rounds it up.
    """
    now = now or utc_now()
    total = 0
    supporters = 0
    rows = db.query(SupportChoice).filter(SupportChoice.started_at.isnot(None), SupportChoice.amount_cents > 0).all()
    for row in rows:
        until = min(row.ended_at or now, now)
        step_months = 12 if row.cadence == SupportCadence.year else 1
        charges = 0
        k = 0
        while True:
            months = row.started_at.month - 1 + k * step_months
            try:
                charge = row.started_at.replace(year=row.started_at.year + months // 12, month=months % 12 + 1)
            except ValueError:
                # The 29th-31st of a short month: the provider bills on the
                # last day, and the last day is in the same year either way.
                charge = row.started_at.replace(year=row.started_at.year + months // 12, month=months % 12 + 1, day=28)
            if charge > until or charge.year > year:
                break
            if charge.year == year:
                charges += 1
            k += 1
        if charges:
            total += charges * row.amount_cents
            supporters += 1
    return total, supporters


def _manage_url() -> str:
    """Where a hiker manages this, which is also the message's way to stop:
    the app's own More → Your support. The setup email is one the hiker asked
    for, and the only other mail this table ever leads to is the one move
    email and the opt-in accounting - both controlled from that page."""
    return f"{(settings.public_site_url or 'https://ourhike.org').rstrip('/')}/app/"


def send_setup_link(db: Session, row: SupportChoice, provider) -> bool:
    """Email the checkout link to a store-app hiker. True when it went.

    The one place a payment link reaches a store-app hiker - Apple's 3.1.3
    allows "communications outside of the app", and its 3.1.1(a) does not
    allow the link inside one outside the US. Does not commit.
    """
    checkout = settings.buymeacoffee_checkout_url
    if not checkout or provider is None:
        return False
    amount = f"${row.amount_cents // 100:,}"
    body = (
        f"You chose to give OurHike {amount} a year. Thank you.\n\n"
        f"Set it up here, using this same email address so the app can tell it's you:\n{checkout}\n\n"
        "Stopping is two taps in the app: More → Your support → Stop. We cancel it for you.\n\n"
        "Not tax-deductible: OurHike isn't a nonprofit yet.\n"
    )
    try:
        send(
            db,
            to=row.email,
            purpose=MailPurpose.support_setup_link,
            subject=f"Set up your {amount} a year for OurHike",
            body_text=body,
            unsubscribe_url=_manage_url(),
            provider=provider,
            enabled=settings.mail_enabled,
            allowed=settings.mail_allowed,
        )
    except (MailDisabled, MailSuppressed, MailFailed) as exc:
        log.info("support: setup link not sent: %s", exc)
        return False
    return True


def notify_stop(db: Session, row: SupportChoice, provider) -> bool:
    """Tell the founder a Stop needs cancelling by hand. True when it went.

    There is no cancel API to call (searched 2026-10-23), so this email IS
    the cancellation's first step, and a False here is returned to the router
    to log rather than swallowed. Does not commit.
    """
    to = settings.support_notify_address
    if not to or provider is None:
        return False
    body = (
        "A supporter pressed Stop in the app.\n\n"
        f"Email: {row.email}\n"
        f"Amount: ${row.amount_cents / 100:,.2f} {row.currency} per {row.cadence.value}\n"
        f"Buy Me a Coffee membership id: {row.provider_ref or 'not yet confirmed'}\n"
        f"Stripe subscription id: {row.psp_ref or 'unknown'}\n\n"
        "Cancel it in the Buy Me a Coffee dashboard today. Its membership.cancelled "
        "webhook will mark the record stopped. The app has already told the hiker "
        "it will be cancelled by hand the same day.\n"
    )
    try:
        send(
            db,
            to=to,
            purpose=MailPurpose.support_stop_request,
            subject=f"Stop requested: {row.email}",
            body_text=body,
            unsubscribe_url=_manage_url(),
            provider=provider,
            enabled=settings.mail_enabled,
            allowed=settings.mail_allowed,
        )
    except (MailDisabled, MailSuppressed, MailFailed) as exc:
        log.warning("support: stop notice not sent for %s: %s", row.id, exc)
        return False
    return True
