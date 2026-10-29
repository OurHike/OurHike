"""Supporting OurHike: matching payments to choices, Stop, and the total (#1876).

The decisions are the maintainer's, by poll from 2026-10-23, and
features/SUPPORTING_OURHIKE.md is their one home. Everything provider-shaped
lives behind app/core/support_providers/ - this module never reads a Stripe
field name, and a second provider is a module there, not a change here (the
Buy Me a Coffee to Stripe swap of 2026-10-27 was exactly that).

What this module is for, and the rules three adversarial reviews of #1885
made it keep:

**A PAYMENT MEETS ITS CHOICE BY ID, NEVER BY EMAIL.** By the provider's id for
the payment once it is known, and before that by OurHike's own choice id,
which the provider carries through checkout. There is no email fallback and
no claiming by email: the third review showed a stranger who types a hiker's
address could put their payment on the hiker's record, block the hiker's own
choice, and have the hiker's Stop cancel it. A payment that names no choice
is kept unattached, for the total, and the founder is told.

**A PAYMENT FOR A CHOICE THAT NO LONGER WANTS ONE IS STOPPED.** A choice id
that is already stopped, already paid, or emptied by an account deletion
still arrives - a hiker who paid and pressed Stop before the webhook landed,
two tabs, an old setup email clicked after deleting the account. Each gets a
row of its own, already `stop_requested`, the provider is asked to stop it,
and the founder is told it may need refunding.

**A LATE EVENT NEVER UNDOES A LATER ONE.** Deliveries are retried and may
arrive in any order (Stripe says so outright), so each row keeps the time of
the newest event it took (`last_event_at`) and drops anything older. And
`stopped` is final for a provider id. A cancellation that is reversed (the
provider's "Don't cancel") clears the Stop's bookkeeping, so a second Stop
reaches the provider again.

**EVERY EVENT THE PROVIDER RECOGNISES IS KEPT** in `support_events`, with what
was done about it. An event whose handling raised is stored as `failed` and
acknowledged - unless the failure was the database connection itself, which
the router answers 503 so the provider retries.

**THE TOTAL IS READ FROM CHARGES**, one row per provider charge id in
`support_charges`, which a unique key keeps from being counted twice, net of
refunds (a refund is a negative row, recognised by the payer's provider id).

**A CONFIRMED PAYMENT IS COUNTED ONCE, BY ITS LEVEL**, as a `support_chosen`
usage event carrying the level and nothing else (app/core/analytics_support.py,
the maintainer's poll of 2026-10-27). Written when a `started` event is
applied, in the same transaction, and keyed by the choice so a redelivery or
a second tab counts nothing twice.

**A PAID RECORD IS KEPT SEVEN YEARS AFTER IT ENDS, THEN DELETED**, once the
account it belonged to is gone (the maintainer, 2026-10-27). `purge_expired`
does it a few rows at a time on each webhook delivery, since nothing here
runs on a schedule.

**A STOP IS RECORDED BEFORE THE PROVIDER IS ASKED, AND RETRIED UNTIL IT IS.**
`mark_stop` changes the row; the caller commits; `notify_stop` then asks the
provider and records the answer with an UPDATE that touches only the stop
columns, so a confirmation webhook landing during the call is never written
over. A row whose request did not go keeps `stop_notified_at` empty and is
retried, at most every `RETRY_EVERY`. A `pending` choice has nothing to
cancel, so its Stop lands as `stopped` at once.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.analytics_support import count_paid_choice
from app.core.support_mail import email_founder_payment_note, email_hiker_started, email_hiker_stopped
from app.core.support_providers import EventKind, ProviderEvent, SupportProvider, provider_for
from app.core.time import utc_now
from app.models.mail import EmailSend, MailPurpose
from app.models.profile import Profile
from app.models.support import (
    SupportCadence,
    SupportCharge,
    SupportChoice,
    SupportEvent,
    SupportMailPreference,
    SupportStatus,
)

log = logging.getLogger(__name__)

# A recurring payment exists and nothing has ended it.
RUNNING = (
    SupportStatus.active,
    SupportStatus.payment_failed,
    SupportStatus.paused,
    SupportStatus.cancel_scheduled,
    SupportStatus.stop_requested,
)
# What a hiker's Stop applies to: anything that could still charge them, and
# a pending choice, which is how one is cleared.
STOPPABLE = (SupportStatus.pending, SupportStatus.active, SupportStatus.payment_failed, SupportStatus.paused)
# What blocks a new choice: a payment on the current provider that nobody has
# asked to stop. A failing one too - a second subscription beside one the
# provider is still retrying would charge twice.
BLOCKS_CHOICE = (SupportStatus.active, SupportStatus.payment_failed, SupportStatus.paused)

# The published total is in dollars. Another currency's amount is not
# summed into it, because no conversion here would be anybody's real rate.
TOTAL_CURRENCY = "USD"

# How many unsent stop requests one webhook delivery retries, and how long a
# row waits between tries. @unvalidated: fifteen minutes is a guess at "long
# enough not to hammer a provider that is down, short enough that a Stop
# lands the same day"; the first real outage would settle it.
RETRY_BATCH = 5
RETRY_EVERY = timedelta(minutes=15)

# How long a paid record outlives its end once its account is deleted: the
# maintainer's seven years (poll, 2026-10-27), chosen over three and over
# forever. Seven covers the IRS's longest ordinary look-back for a return
# (reasoned from IRS guidance on how long to keep records, not a tax
# professional's advice). 2,557 days is seven years with two leap days.
RETENTION = timedelta(days=2557)
PURGE_BATCH = 50


# What "Your support" describes, best first: a payment that can still charge,
# then one being stopped, then a choice waiting for its payment, then one that
# ended. Status before date, because a duplicate the server stopped is newer
# than the payment it duplicated and must never hide it - the fourth #1885
# review found Your support reading "No more charges", with no Stop, over a
# payment that kept renewing.
_SUMMARY_ORDER = (
    BLOCKS_CHOICE,
    (SupportStatus.stop_requested, SupportStatus.cancel_scheduled),
    (SupportStatus.pending,),
    (SupportStatus.stopped,),
)


def summary_row(db: Session, profile_id: str) -> SupportChoice | None:
    """The row "Your support" describes: the newest in the best group of
    `_SUMMARY_ORDER`."""
    rows = db.query(SupportChoice).filter(SupportChoice.profile_id == profile_id).all()
    if not rows:
        return None

    def newest(row: SupportChoice) -> datetime:
        return row.started_at or row.chosen_at or row.updated_at or datetime.min

    for statuses in _SUMMARY_ORDER:
        group = [row for row in rows if row.status in statuses]
        if group:
            return max(group, key=newest)
    return None


def settle_lapsed(db: Session, profile_id: str, now: datetime | None = None) -> int:
    """Move a `cancel_scheduled` payment whose end has passed to `stopped`.

    A provider normally says so itself (Stripe sends `deleted` at the end),
    but a lost delivery would otherwise leave it reading as supporting forever
    and the yearly ask would never come back. Does not commit.
    """
    now = now or utc_now()
    rows = (
        db.query(SupportChoice)
        .filter(
            SupportChoice.profile_id == profile_id,
            SupportChoice.status == SupportStatus.cancel_scheduled,
            SupportChoice.ended_at.isnot(None),
            SupportChoice.ended_at <= now,
        )
        .all()
    )
    for row in rows:
        row.status = SupportStatus.stopped
    return len(rows)


def _by_payment(db: Session, provider: SupportProvider, ref: str | None) -> SupportChoice | None:
    if not ref:
        return None
    return (
        db.query(SupportChoice)
        .filter(SupportChoice.provider == provider.key, SupportChoice.provider_ref == ref)
        .with_for_update()
        .populate_existing()
        .first()
    )


def _by_choice(db: Session, provider: SupportProvider, ref: str | None) -> SupportChoice | None:
    """The choice a checkout names, locked, so two checkouts of one choice
    cannot both attach to it (the third review's two-tabs case)."""
    if not ref:
        return None
    return (
        db.query(SupportChoice)
        .filter(SupportChoice.id == ref, SupportChoice.provider == provider.key)
        .with_for_update()
        .populate_existing()
        .first()
    )


def _insert(db: Session, row: SupportChoice) -> bool:
    """Add a row in a savepoint. False when the unique (provider,
    provider_ref) says another delivery got there first."""
    try:
        with db.begin_nested():
            db.add(row)
            db.flush()
    except IntegrityError:
        return False
    return True


def _new_row(
    db: Session,
    provider: SupportProvider,
    event: ProviderEvent,
    *,
    status: SupportStatus,
    like: SupportChoice | None,
    now: datetime,
) -> tuple[SupportChoice | None, bool]:
    """A row for a payment no pending choice is waiting for, and whether this
    call inserted it. `like` is the choice the payment named, whose account
    it belongs to; None for a payment that named none. When two deliveries of
    the same payment race, the loser gets the winner's row and False.

    **The address is the account's verified one whenever there is an
    account.** The address a payer types on Stripe's page is checked by
    nobody, and on a row an account can see it would hand that account the
    row's email switches for an address of its choosing - and put a
    stranger's address in the hiker's export (the fourth #1885 review). Only
    a row no account sees keeps it, for the founder to reach the payer."""
    verified = like.email if like is not None and like.email else None
    row = SupportChoice(
        profile_id=like.profile_id if like is not None else None,
        email=verified or event.email or "",
        provider=provider.key,
        provider_ref=event.subscription_ref,
        amount_cents=event.amount_cents or (like.amount_cents if like is not None else 0),
        status=status,
        stop_requested_at=now if status == SupportStatus.stop_requested else None,
        duplicate_of=like.id if like is not None else None,
        uncounted=like.uncounted if like is not None else False,
    )
    if _insert(db, row):
        return row, True
    return _by_payment(db, provider, event.subscription_ref), False


def _settled(event: ProviderEvent, now: datetime) -> tuple[SupportStatus, datetime | None] | None:
    """Where an event that ends a payment leaves its row: `cancel_scheduled`
    when the provider says it ends at the close of a period still to come,
    `stopped` for an `ended` event otherwise, None when nothing ends."""
    scheduled = event.cancel_at_period_end and event.kind is not EventKind.paused
    if scheduled and event.period_end is not None and event.period_end > now:
        return SupportStatus.cancel_scheduled, event.period_end
    if event.kind is EventKind.ended:
        return SupportStatus.stopped, event.occurred_at or now
    return None


def _record_charge(
    db: Session, provider: SupportProvider, event: ProviderEvent, now: datetime
) -> tuple[str, SupportChoice | None]:
    """Money arrived: one `support_charges` row per provider charge id, and
    never a change of state. A charge can arrive before the payment it
    belongs to is known; `_join_charges` links it afterwards."""
    row = (
        db.query(SupportChoice)
        .filter(SupportChoice.provider == provider.key, SupportChoice.provider_ref == event.subscription_ref)
        .first()
        if event.subscription_ref
        else None
    )
    if not event.charge_ref or event.amount_cents is None or not event.currency:
        return "ignored_incomplete_charge", row
    charge = SupportCharge(
        provider=provider.key,
        charge_ref=event.charge_ref,
        subscription_ref=event.subscription_ref,
        choice_id=row.id if row is not None else None,
        customer_ref=event.customer_ref or (row.customer_ref if row is not None else None),
        amount_cents=event.amount_cents,
        currency=event.currency,
        charged_at=event.occurred_at or now,
        period_end=event.period_end,
        received_at=now,
    )
    try:
        with db.begin_nested():
            db.add(charge)
            db.flush()
    except IntegrityError:
        return "duplicate", row
    if row is not None and event.period_end is not None:
        row.period_end = max(row.period_end or event.period_end, event.period_end)
    _apply_waiting_refunds(db, provider, charge.customer_ref, now)
    return "charged", row


# How far back a refund logged as "not ours" is looked for when a charge
# lands. Reasoned: a refund can only arrive before the charge it reverses
# while Stripe is still retrying that charge's `invoice.paid` - after this
# server answered 503, say - and Stripe retries for up to three days.
LATE_REFUND_WINDOW = timedelta(days=7)


def _apply_waiting_refunds(db: Session, provider: SupportProvider, customer_ref: str | None, now: datetime) -> None:
    """Apply refunds of `customer_ref` that arrived before any of its charges.

    `_record_refund` recognises a refund by a charge of the same customer, so
    one delivered first was logged as `ignored_not_ours` and answered 200 -
    and lost from the total for good (the fourth #1885 review). Rebuilt from
    the log by the provider, which owns its field names."""
    rebuild = getattr(provider, "refund_from_log", None)
    if not customer_ref or rebuild is None:
        return
    waiting = (
        db.query(SupportEvent)
        .filter(
            SupportEvent.provider == provider.key,
            SupportEvent.kind == EventKind.refunded.value,
            SupportEvent.outcome == "ignored_not_ours",
            SupportEvent.received_at >= now - LATE_REFUND_WINDOW,
        )
        .with_for_update()
        .all()
    )
    for logged in waiting:
        refund = rebuild(logged.payload or {}, logged.occurred_at)
        if refund is None or refund.customer_ref != customer_ref:
            continue
        outcome, _ = _record_refund(db, provider, refund, now)
        logged.outcome = f"late_{outcome}"[:40]


REFUND_PREFIX = "refund:"


def _record_refund(db: Session, provider: SupportProvider, event: ProviderEvent, now: datetime) -> tuple[str, None]:
    """Money went back: one negative `support_charges` row per refunded
    charge, holding the total refunded of it so far, so a second partial
    refund updates it and a resent event changes nothing.

    Counted only when the payer is one of OurHike's - a customer one of its
    charges or choices names. Anything else refunded on the same Stripe
    account is left alone, as its charges were.
    """
    if not event.charge_ref or not event.customer_ref or event.amount_cents is None:
        return "ignored_incomplete_refund", None
    ours = (
        db.query(SupportCharge)
        .filter(
            SupportCharge.provider == provider.key,
            SupportCharge.customer_ref == event.customer_ref,
            SupportCharge.amount_cents > 0,
        )
        .order_by(SupportCharge.charged_at.desc())
        .first()
    )
    if ours is None:
        return "ignored_not_ours", None
    ref = REFUND_PREFIX + event.charge_ref
    amount = -abs(event.amount_cents)
    existing = (
        db.query(SupportCharge)
        .filter(SupportCharge.provider == provider.key, SupportCharge.charge_ref == ref)
        .with_for_update()
        .first()
    )
    if existing is None:
        refund = SupportCharge(
            provider=provider.key,
            charge_ref=ref,
            subscription_ref=ours.subscription_ref,
            choice_id=ours.choice_id,
            customer_ref=event.customer_ref,
            amount_cents=amount,
            currency=event.currency or ours.currency,
            charged_at=event.occurred_at or now,
            received_at=now,
        )
        try:
            with db.begin_nested():
                db.add(refund)
                db.flush()
            return "refunded", None
        except IntegrityError:
            existing = (
                db.query(SupportCharge)
                .filter(SupportCharge.provider == provider.key, SupportCharge.charge_ref == ref)
                .with_for_update()
                .first()
            )
    if existing is not None and amount < existing.amount_cents:
        # A later partial refund: Stripe's figure is the running total.
        existing.amount_cents = amount
        return "refunded", None
    return "duplicate", None


def _join_charges(db: Session, provider: SupportProvider, row: SupportChoice) -> None:
    """Give charges that arrived before their checkout to the row, and take
    the latest period end they paid for."""
    if not row.provider_ref:
        return
    db.query(SupportCharge).filter(
        SupportCharge.provider == provider.key,
        SupportCharge.subscription_ref == row.provider_ref,
        SupportCharge.choice_id.is_(None),
    ).update({SupportCharge.choice_id: row.id}, synchronize_session=False)
    latest = (
        db.query(func.max(SupportCharge.period_end))
        .filter(SupportCharge.provider == provider.key, SupportCharge.subscription_ref == row.provider_ref)
        .scalar()
    )
    if latest is not None and (row.period_end is None or latest > row.period_end):
        row.period_end = latest


def _unwanted(
    db: Session,
    provider: SupportProvider,
    event: ProviderEvent,
    choice: SupportChoice,
    *,
    mail_provider,
    now: datetime,
) -> tuple[str, SupportChoice | None]:
    """A payment for a choice that was stopped, already paid, or emptied by an
    account deletion: a row of its own, asked to stop at once, and the
    founder told it may need refunding.

    Only a row this call created is stopped. When two deliveries of one
    second payment race, the loser finds the winner's row and leaves it be -
    the winner already asked for the stop and told the founder."""
    row, inserted = _new_row(db, provider, event, status=SupportStatus.stop_requested, like=choice, now=now)
    if row is None:
        return "ignored_no_supporter", None
    if not inserted:
        return "duplicate", row
    row.started_at = row.started_at or event.started_at or now
    row.last_event_at = event.occurred_at
    for field in ("customer_ref", "plan_ref", "currency"):
        value = getattr(event, field)
        if value is not None:
            setattr(row, field, value)
    _join_charges(db, provider, row)
    db.flush()
    notify_stop(db, row, mail_provider=mail_provider, now=now)
    email_founder_payment_note(
        db,
        row,
        provider_label=provider.label,
        what="A payment arrived for an OurHike choice that was no longer waiting for one - it had been "
        "stopped, already paid, or emptied when its account was deleted. OurHike has asked for it to stop "
        "renewing. If it was a duplicate, or the hiker did not mean it, refund it in the provider's dashboard.",
        mail_provider=mail_provider,
    )
    return "unwanted", row


def _count_paid(event: ProviderEvent, choice: SupportChoice, db: Session, now: datetime) -> None:
    """Count a confirmed payment's level once, as a usage event (app/core/analytics_support.py).

    `choice` is the choice the payment was for - the hiker's own, even when
    this payment is a duplicate of it - so a redelivery, or a second tab
    paying for the same choice, finds it already counted. Locked by the
    caller.
    """
    count_paid_choice(db, choice, cents=event.tier_cents or choice.chosen_amount_cents, now=now)


def _another_charging(db: Session, row: SupportChoice) -> bool:
    """Another of this row's account's payments can still charge."""
    if row.profile_id is None:
        return False
    return (
        db.query(SupportChoice.id)
        .filter(
            SupportChoice.profile_id == row.profile_id,
            SupportChoice.id != row.id,
            SupportChoice.status.in_(BLOCKS_CHOICE),
        )
        .first()
        is not None
    )


def apply_event(
    db: Session,
    provider: SupportProvider,
    event: ProviderEvent,
    *,
    mail_provider,
    now: datetime | None = None,
) -> tuple[str, SupportChoice | None]:
    """Apply one normalised event. Returns (outcome, row). Does not commit."""
    now = now or utc_now()
    if event.kind is EventKind.charged:
        return _record_charge(db, provider, event, now)
    if event.kind is EventKind.refunded:
        return _record_refund(db, provider, event, now)

    row = _by_payment(db, provider, event.subscription_ref)
    if row is None:
        if event.kind is not EventKind.started:
            return "ignored_unknown_payment", None
        if not event.subscription_ref:
            return "ignored_no_payment_id", None
        choice = _by_choice(db, provider, event.choice_ref)
        if choice is not None and choice.provider_ref == event.subscription_ref:
            # The same payment again, which another delivery attached while
            # this one waited on the choice's lock: not a second payment
            # (the fourth #1885 review measured it cancelling the hiker's
            # only payment).
            row = choice
        elif choice is not None and choice.status == SupportStatus.pending and choice.provider_ref is None:
            row = choice
        elif choice is not None:
            outcome, row = _unwanted(db, provider, event, choice, mail_provider=mail_provider, now=now)
            if outcome == "unwanted":
                _count_paid(event, choice, db, now)
            return outcome, row
        else:
            row, inserted = _new_row(db, provider, event, status=SupportStatus.active, like=None, now=now)
            if row is None:
                return "ignored_no_supporter", None
            if inserted:
                # Charges that came before this checkout join it now, as they
                # do a choice's: unjoined, the seven-year sweep of charges
                # nobody claimed would delete the money record of a payment
                # still running (the fourth #1885 review).
                _join_charges(db, provider, row)
                email_founder_payment_note(
                    db,
                    row,
                    provider_label=provider.label,
                    what="A payment arrived that names no OurHike choice - its link was edited, or it came from "
                    "somewhere other than the app. It counts in the published total, but nobody can stop it from "
                    "the app. If the payer writes in, cancel it in the provider's dashboard.",
                    mail_provider=mail_provider,
                )

    if event.kind is EventKind.started and not row.replaces_choice_id:
        _count_paid(event, row, db, now)

    if row.last_event_at is not None and event.occurred_at is not None and event.occurred_at < row.last_event_at:
        return "stale", row
    if row.status == SupportStatus.stopped:
        return "already_stopped", row

    if event.occurred_at is not None:
        row.last_event_at = max(row.last_event_at or event.occurred_at, event.occurred_at)
    row.provider_ref = row.provider_ref or event.subscription_ref
    for field in ("customer_ref", "psp_ref", "plan_ref", "provider_status", "currency", "period_end", "cancel_at_period_end"):
        value = getattr(event, field)
        if value is not None:
            setattr(row, field, value)
    if event.amount_cents is not None:
        row.amount_cents = event.amount_cents
    if isinstance(event.cadence, SupportCadence):
        row.cadence = event.cadence
    if event.kind is not EventKind.ended:
        row.started_at = row.started_at or event.started_at or now

    was = row.status
    settled = _settled(event, now)
    if settled is not None:
        row.status, row.ended_at = settled
    elif event.kind is EventKind.paused:
        row.status = SupportStatus.paused
    elif event.kind is EventKind.failing:
        row.status = SupportStatus.payment_failed
    else:
        row.status = SupportStatus.active
    if was == SupportStatus.stop_requested and row.status in BLOCKS_CHOICE:
        # The cancellation has not landed yet: an event sent before it must
        # not quietly undo the hiker's Stop.
        row.status = SupportStatus.stop_requested
    if was == SupportStatus.cancel_scheduled and row.status in BLOCKS_CHOICE:
        # The cancellation was reversed at the provider ("Don't cancel"). The
        # old Stop is over; a new one must reach the provider again.
        row.stop_requested_at = row.stop_notified_at = row.stop_attempted_at = row.stop_confirmed_at = None

    if was == SupportStatus.pending and row.status in BLOCKS_CHOICE:
        _join_charges(db, provider, row)
        if row.profile_id is not None:
            email_hiker_started(db, row, mail_provider=mail_provider)
    if (
        row.status in (SupportStatus.stopped, SupportStatus.cancel_scheduled)
        and row.stop_requested_at is not None
        and row.stop_confirmed_at is None
        and row.profile_id is not None
    ):
        # Whatever order the events came in - keyed off the Stop, not off the
        # status the row happened to have a moment ago. Never for a duplicate
        # the server stopped while another of the hiker's payments still
        # charges: "Nothing more will be charged" would be false (the fourth
        # #1885 review). The founder is already asked to refund it, and
        # Stripe's own refund receipt is what the hiker gets.
        if row.duplicate_of is not None and _another_charging(db, row):
            row.stop_confirmed_at = now
        elif email_hiker_stopped(db, row, mail_provider=mail_provider):
            row.stop_confirmed_at = now
    if was == SupportStatus.pending and row.status == SupportStatus.active and row.replaces_choice_id:
        # A move between providers: the new payment started, so the old one
        # is asked to stop exactly as the hiker's own Stop would.
        old = db.get(SupportChoice, row.replaces_choice_id)
        if old is not None and mark_stop(old, now=now):
            db.flush()
            notify_stop(db, old, mail_provider=mail_provider, now=now)
    return row.status.value, row


def apply_delivery(
    db: Session,
    provider: SupportProvider,
    envelope: dict,
    *,
    mail_provider,
    now: datetime | None = None,
) -> str:
    """Normalise, apply and log one verified delivery. Returns the outcome(s)
    as a word for the acknowledgement. Does not commit."""
    now = now or utc_now()
    events = provider.normalise(envelope)
    if not events:
        return "ignored"
    outcomes = []
    for event in events:
        outcome, row = apply_event(db, provider, event, mail_provider=mail_provider, now=now)
        db.add(
            SupportEvent(
                provider=provider.key,
                event_id=event.event_id,
                kind=event.kind.value,
                occurred_at=event.occurred_at,
                received_at=now,
                choice_id=row.id if row is not None else None,
                outcome=outcome,
                payload=event.payload,
            )
        )
        outcomes.append(outcome)
    db.flush()
    return ",".join(outcomes)


def record_failed_delivery(db: Session, provider: SupportProvider, envelope: dict, error: BaseException) -> None:
    """Keep a delivery whose handling raised, by its event id, so it can be
    resent from the provider's dashboard once the bug is fixed (Stripe keeps
    events 30 days). The payload is the provider's own redaction, never the
    raw body. Does not commit."""
    try:
        events = provider.normalise(envelope)
    except Exception:  # the normaliser is what raised
        events = []
    for event in events or [None]:
        db.add(
            SupportEvent(
                provider=provider.key,
                event_id=event.event_id if event else None,
                kind=event.kind.value if event else "unknown",
                occurred_at=event.occurred_at if event else None,
                outcome=f"failed: {type(error).__name__}"[:40],
                payload=event.payload if event else None,
            )
        )
    db.flush()


def mark_stop(row: SupportChoice, *, now: datetime) -> bool:
    """Record a Stop on one row. Returns whether the provider now needs
    asking. Changes the row only; the caller commits before `notify_stop`.

    `pending` with nothing confirmed by the provider has nothing to cancel and
    lands as `stopped`. Anything still charging becomes `stop_requested`.
    """
    if row.status == SupportStatus.pending and row.provider_ref is None:
        row.status = SupportStatus.stopped
        row.stop_requested_at = row.stop_requested_at or now
        row.ended_at = now
        return False
    if row.status in STOPPABLE:
        row.status = SupportStatus.stop_requested
        row.stop_requested_at = now
        row.stop_notified_at = row.stop_attempted_at = row.stop_confirmed_at = None
    return row.status == SupportStatus.stop_requested and row.stop_notified_at is None


def notify_stop(db: Session, row: SupportChoice, *, mail_provider, now: datetime | None = None) -> bool:
    """Ask whoever cancels `row` to cancel it. True when it reached them.

    The provider is called first and the answer recorded after, with UPDATEs
    that touch only the stop columns and never the status: so a router that
    committed its `mark_stop` holds no lock on the row while the provider is
    out, and a provider's confirmation that commits during the call is not
    written over (the third #1885 review's race). Does not commit.
    """
    now = now or utc_now()
    provider = provider_for(row.provider)
    reached = provider is not None and provider.request_cancel(db, row, mail_provider)
    if not reached:
        log.warning("support: stop %s recorded but whoever cancels it was not reached", row.id)
    ids = SupportChoice.id == row.id
    db.query(SupportChoice).filter(ids).update({SupportChoice.stop_attempted_at: now}, synchronize_session=False)
    if reached:
        db.query(SupportChoice).filter(ids, SupportChoice.stop_notified_at.is_(None)).update(
            {SupportChoice.stop_notified_at: now}, synchronize_session=False
        )
    return reached


def request_stop(db: Session, row: SupportChoice, *, mail_provider, now: datetime | None = None) -> SupportChoice:
    """`mark_stop` then `notify_stop`, for a caller already inside one
    transaction with nothing to race (a provider move). Does not commit."""
    now = now or utc_now()
    if mark_stop(row, now=now):
        db.flush()
        notify_stop(db, row, mail_provider=mail_provider, now=now)
    return row


def stops_waiting(db: Session, *, profile_id: str | None = None, now: datetime | None = None) -> list[SupportChoice]:
    """Stops nobody was told about and not tried in the last `RETRY_EVERY`,
    least recently tried first, so a row that keeps failing cannot hold the
    queue."""
    now = now or utc_now()
    query = db.query(SupportChoice).filter(
        SupportChoice.status == SupportStatus.stop_requested,
        SupportChoice.stop_notified_at.is_(None),
        or_(SupportChoice.stop_attempted_at.is_(None), SupportChoice.stop_attempted_at <= now - RETRY_EVERY),
    )
    if profile_id is not None:
        query = query.filter(SupportChoice.profile_id == profile_id)
    return (
        query.order_by(SupportChoice.stop_attempted_at.asc().nullsfirst(), SupportChoice.stop_requested_at)
        .limit(RETRY_BATCH)
        .all()
    )


def retry_stop_requests(
    db: Session,
    *,
    mail_provider,
    profile_id: str | None = None,
    now: datetime | None = None,
) -> int:
    """Ask again for Stops nobody was told about (`stops_waiting`). Returns
    how many went. Does not commit."""
    now = now or utc_now()
    return sum(
        1
        for row in stops_waiting(db, profile_id=profile_id, now=now)
        if notify_stop(db, row, mail_provider=mail_provider, now=now)
    )


def year_total(db: Session, year: int) -> tuple[int, int]:
    """(cents, payments) given in `year`, in dollars, before fees and net of
    refunds.

    **Read from charges, not reasoned.** The sum of every `support_charges`
    row dated in the year - money a provider says arrived, once per charge
    id, less what went back, dated when it went back - and the number of
    distinct recurring payments the money came from. A refund does not
    lower that count: the person did give, and was given it back.

    Only `TOTAL_CURRENCY` is summed: an amount in another currency is left
    out rather than converted at a rate nobody here can stand behind.
    """
    in_year = (
        SupportCharge.currency == TOTAL_CURRENCY,
        SupportCharge.charged_at >= datetime(year, 1, 1),
        SupportCharge.charged_at < datetime(year + 1, 1, 1),
    )
    total = db.query(func.coalesce(func.sum(SupportCharge.amount_cents), 0)).filter(*in_year).scalar() or 0
    # One supporter per account, or per choice with no account left: a
    # duplicate payment, a stopped choice chosen again, or two renewals are
    # one person, not several (the fourth #1885 review).
    supporter = func.coalesce(
        SupportChoice.profile_id,
        SupportChoice.duplicate_of,
        SupportCharge.choice_id,
        SupportCharge.subscription_ref,
        SupportCharge.charge_ref,
    )
    supporters = (
        db.query(func.count(func.distinct(supporter)))
        .select_from(SupportCharge)
        .outerjoin(SupportChoice, SupportChoice.id == SupportCharge.choice_id)
        .filter(*in_year, SupportCharge.amount_cents > 0)
        .scalar()
        or 0
    )
    return int(total), int(supporters)


# What OurHike sends a hiker about their support, logged in `email_sends`
# under their address. The founder's notices go to the founder's address.
HIKER_SUPPORT_MAIL = (MailPurpose.support_setup_link, MailPurpose.support_started, MailPurpose.support_stopped)


def forget_addresses(db: Session, addresses: list[str]) -> None:
    """Remove what still names an address once no support row does.

    The send log keeps each email's address and subject ("You're giving
    OurHike $60 a year"), and an "Emails about my support" row is just the
    address when it says nothing is off. Neither expired, so an account
    deletion that emptied a choice, and the purge seven years on, left the
    address and the amount behind (the fourth #1885 review). An address still
    on another support row keeps both: that row is a money record that still
    names it. A switch set to off stays, because an opt-out must outlive the
    account to be honoured - and so does the one suppression list
    (app/core/mail.py). Does not commit.
    """
    for address in {address.strip().lower() for address in addresses if address and address.strip()}:
        if db.query(SupportChoice.id).filter(func.lower(SupportChoice.email) == address).first() is not None:
            continue
        db.query(EmailSend).filter(func.lower(EmailSend.to_address) == address, EmailSend.purpose.in_(HIKER_SUPPORT_MAIL)).delete(
            synchronize_session=False
        )
        db.query(SupportMailPreference).filter(
            func.lower(SupportMailPreference.address) == address, SupportMailPreference.off_at.is_(None)
        ).delete(synchronize_session=False)


def purge_expired(db: Session, *, now: datetime | None = None) -> int:
    """Delete paid records `RETENTION` after they ended, once nobody's account
    holds them: rows whose account was deleted, rows that never had one, and
    the charges and events that belong to them. At most `PURGE_BATCH` rows a
    call. Returns how many choices went. Does not commit.

    A row still charging, or one whose account still exists, is never
    touched: the hiker can see it under Your support and in their export.
    """
    cutoff = (now or utc_now()) - RETENTION
    deleted_accounts = db.query(Profile.id).filter(Profile.deleted_at.isnot(None))
    ended = func.coalesce(SupportChoice.ended_at, SupportChoice.updated_at)
    # `cancel_scheduled` too: its end is its `ended_at`, and a deleted
    # account's final "ended" event that was lost would otherwise keep it
    # forever, since only the account's own visit settles it (the fourth
    # #1885 review).
    rows = (
        db.query(SupportChoice.id, SupportChoice.email)
        .filter(
            SupportChoice.status.in_((SupportStatus.stopped, SupportStatus.cancel_scheduled)),
            ended < cutoff,
            or_(SupportChoice.profile_id.is_(None), SupportChoice.profile_id.in_(deleted_accounts)),
        )
        .limit(PURGE_BATCH)
        .all()
    )
    ids = [row_id for row_id, _ in rows]
    if ids:
        for column in (SupportChoice.replaces_choice_id, SupportChoice.duplicate_of):
            db.query(SupportChoice).filter(column.in_(ids)).update({column: None}, synchronize_session=False)
        db.query(SupportEvent).filter(SupportEvent.choice_id.in_(ids)).delete(synchronize_session=False)
        db.query(SupportCharge).filter(SupportCharge.choice_id.in_(ids)).delete(synchronize_session=False)
        db.query(SupportChoice).filter(SupportChoice.id.in_(ids)).delete(synchronize_session=False)
        forget_addresses(db, [email for _, email in rows])
    # What never joined a row: charges whose checkout never came, and events
    # about nothing OurHike kept.
    db.query(SupportCharge).filter(SupportCharge.choice_id.is_(None), SupportCharge.charged_at < cutoff).delete(
        synchronize_session=False
    )
    db.query(SupportEvent).filter(SupportEvent.choice_id.is_(None), SupportEvent.received_at < cutoff).delete(
        synchronize_session=False
    )
    return len(ids)
