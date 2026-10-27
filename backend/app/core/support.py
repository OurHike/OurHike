"""Supporting OurHike: matching payments to choices, Stop, and the total (#1876).

The decisions are the maintainer's, by poll from 2026-10-23, and
features/SUPPORTING_OURHIKE.md is their one home. Everything provider-shaped
lives behind app/core/support_providers/ - this module never reads a Buy Me a
Coffee field name, and a second provider is a module there, not a change here.

What this module is for, and the rules the #1885 adversarial review made it
keep:

**A PAYMENT MEETS ITS CHOICE BY THE PROVIDER'S OWN ID WHEREVER IT CAN.** Only a
`started` event may fall back to the email, and only onto a `pending` choice
for the same amount, made with that provider, that was chosen no later than
the payment began. The review found the old fallback matched any event by
email - so a stranger's cancellation typed with a hiker's address could stop
the hiker's pending choice, and a stranger's $1 could become the hiker's
record. An `updated`, `paused` or `ended` for an id nobody has seen is
acknowledged and left alone.

**A LATE EVENT NEVER UNDOES A LATER ONE.** Deliveries are retried for up to an
hour (Buy Me a Coffee's spec) and may arrive in any order, so each row keeps
the time of the newest event it took (`last_event_at`) and drops anything
older. And `stopped` is final for a provider id: a retried "updated" written
before the cancellation cannot bring a stopped payment back to life. A new
payment is a new id, and so a new row.

**EVERY EVENT IS KEPT** in `support_events`, with what was done about it, so
the order and the outcome can be read back - including an event whose
handling raised, which is stored as `failed` and still acknowledged, because
a provider that keeps getting errors switches the webhook off (Buy Me a
Coffee: after ten in a row) and then nothing is recorded at all.

**A STOP IS RECORDED AT ONCE AND RETRIED UNTIL SOMEBODY IS TOLD.** For a
provider with no cancel API the request is an email to the founder; a row
whose request did not go keeps `stop_notified_at` empty, and the next Stop
press, the hiker's next look at the page, or the next webhook tries again. A
`pending` choice has nothing to cancel, so its Stop lands as `stopped` at
once - the review found it otherwise wedged the hiker with no way to choose
again.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.support_mail import email_hiker_stopped
from app.core.support_providers import EventKind, ProviderEvent, SupportProvider, provider_for
from app.core.time import utc_now
from app.models.support import SupportCadence, SupportChoice, SupportEvent, SupportStatus

log = logging.getLogger(__name__)

# A recurring payment exists and nothing has ended it.
RUNNING = (SupportStatus.active, SupportStatus.paused, SupportStatus.cancel_scheduled, SupportStatus.stop_requested)
# What a hiker's Stop applies to: anything that could still charge them, and
# a pending choice, which is how one is cleared.
STOPPABLE = (SupportStatus.pending, SupportStatus.active, SupportStatus.paused)
# What blocks a new choice: a payment on the current provider that is still
# charging and that nobody has asked to stop.
BLOCKS_CHOICE = (SupportStatus.active, SupportStatus.paused)

# The published total is in dollars. Another currency's amount is not
# summed into it, because no conversion here would be anybody's real rate.
TOTAL_CURRENCY = "USD"

# @unvalidated: how far a provider's clock may run behind this server's and
# still have a payment meet the choice made just before it. Ten minutes is a
# guess at clock drift plus checkout time going the wrong way, not a
# measurement; what would settle it is `chosen_at` against the provider's
# `started_at` on the first real supporters.
EMAIL_MATCH_SKEW = timedelta(minutes=10)

# How many unsent stop requests one webhook delivery retries, so a long outage
# cannot turn one delivery into a long request.
RETRY_BATCH = 20


def summary_row(db: Session, profile_id: str) -> SupportChoice | None:
    """The row "Your support" describes: the newest running payment, else the
    newest pending choice, else the newest stopped one."""
    rows = db.query(SupportChoice).filter(SupportChoice.profile_id == profile_id).all()
    if not rows:
        return None

    def newest(row: SupportChoice) -> datetime:
        return row.started_at or row.chosen_at or row.updated_at or datetime.min

    for statuses in (RUNNING, (SupportStatus.pending,), (SupportStatus.stopped,)):
        group = [row for row in rows if row.status in statuses]
        if group:
            return max(group, key=newest)
    return None


def claim_unattached(db: Session, profile_id: str, email: str | None) -> int:
    """Attach payments made on a provider's page to the account whose
    VERIFIED email they carry. Returns how many. Does not commit.

    A supporter who paid on the page without choosing in the app otherwise
    has no Stop button at all. The address is the token's, which
    core/auth.py's `get_current_email` treats as a provider fact - the same
    trust a paid choice already rests on.
    """
    if not email:
        return 0
    rows = db.query(SupportChoice).filter(SupportChoice.profile_id.is_(None), SupportChoice.email == email).all()
    for row in rows:
        row.profile_id = profile_id
    return len(rows)


def _match(db: Session, provider: SupportProvider, event: ProviderEvent) -> SupportChoice | None:
    if event.subscription_ref:
        row = (
            db.query(SupportChoice)
            .filter(SupportChoice.provider == provider.key, SupportChoice.provider_ref == event.subscription_ref)
            .first()
        )
        if row is not None:
            return row
    if event.choice_ref:
        row = db.get(SupportChoice, event.choice_ref)
        if row is not None and row.provider == provider.key and row.provider_ref is None and row.status == SupportStatus.pending:
            return row
    if event.kind is not EventKind.started or not event.email:
        return None
    query = db.query(SupportChoice).filter(
        SupportChoice.provider == provider.key,
        SupportChoice.email == event.email,
        SupportChoice.provider_ref.is_(None),
        SupportChoice.status == SupportStatus.pending,
        SupportChoice.profile_id.isnot(None),
    )
    if event.amount_cents is not None:
        query = query.filter(SupportChoice.amount_cents == event.amount_cents)
    began = event.started_at or event.occurred_at
    if began is not None:
        query = query.filter(SupportChoice.chosen_at <= began + EMAIL_MATCH_SKEW)
    return query.order_by(SupportChoice.chosen_at.desc()).first()


def _new_unattached(db: Session, provider: SupportProvider, event: ProviderEvent) -> SupportChoice | None:
    """A payment begun on the provider's page with no choice in the app.

    Kept so the total is honest; `claim_unattached` gives it to the account
    with the same verified email. Two deliveries racing to create the same
    one meet the unique (provider, provider_ref) constraint, and the loser
    reads the winner's row.
    """
    row = SupportChoice(
        email=event.email,
        provider=provider.key,
        provider_ref=event.subscription_ref,
        amount_cents=event.amount_cents or 0,
        status=SupportStatus.active,
    )
    try:
        with db.begin_nested():
            db.add(row)
            db.flush()
    except IntegrityError:
        return _match(db, provider, event)
    return row


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
    row = _match(db, provider, event)
    if row is None:
        if event.kind not in (EventKind.started, EventKind.updated):
            return "ignored_unknown_payment", None
        if not event.subscription_ref or not event.email:
            return "ignored_no_supporter", None
        row = _new_unattached(db, provider, event)
        if row is None:
            return "ignored_no_supporter", None

    if row.last_event_at is not None and event.occurred_at is not None and event.occurred_at < row.last_event_at:
        return "stale", row
    if row.status == SupportStatus.stopped:
        return "already_stopped", row

    if event.occurred_at is not None:
        row.last_event_at = max(row.last_event_at or event.occurred_at, event.occurred_at)
    row.provider_ref = row.provider_ref or event.subscription_ref
    for field in ("customer_ref", "psp_ref", "plan_ref", "currency", "period_end", "cancel_at_period_end"):
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
    else:
        row.status = SupportStatus.active
    if was == SupportStatus.stop_requested and row.status in (SupportStatus.active, SupportStatus.paused):
        # The founder has not got to it yet: a renewal's `updated` must not
        # quietly undo the hiker's Stop.
        row.status = SupportStatus.stop_requested

    if was == SupportStatus.stop_requested and row.status in (SupportStatus.stopped, SupportStatus.cancel_scheduled):
        email_hiker_stopped(db, row, mail_provider=mail_provider)
    if was == SupportStatus.pending and row.status == SupportStatus.active and row.replaces_choice_id:
        # A move between providers: the new payment started, so the old one
        # is asked to stop exactly as the hiker's own Stop would.
        old = db.get(SupportChoice, row.replaces_choice_id)
        if old is not None and old.status in STOPPABLE:
            request_stop(db, old, mail_provider=mail_provider, now=now)
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
    """Keep a delivery whose handling raised, to replay once the bug is
    fixed. The payload is the provider's own redaction, never the raw body.
    Does not commit."""
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


def request_stop(db: Session, row: SupportChoice, *, mail_provider, now: datetime | None = None) -> SupportChoice:
    """Stop one recurring payment, as far as this server can. Does not commit.

    `pending` with nothing confirmed by the provider has nothing to cancel and
    lands as `stopped`. Anything still charging becomes `stop_requested`, and
    whoever cancels it is asked; a request that did not go is retried by the
    next call. Idempotent: a row already asked is not asked again.
    """
    now = now or utc_now()
    if row.status == SupportStatus.pending and row.provider_ref is None:
        row.status = SupportStatus.stopped
        row.stop_requested_at = row.stop_requested_at or now
        row.ended_at = now
        return row
    if row.status in (SupportStatus.active, SupportStatus.paused, SupportStatus.pending):
        row.status = SupportStatus.stop_requested
        row.stop_requested_at = now
    if row.status == SupportStatus.stop_requested and row.stop_notified_at is None:
        provider = provider_for(row.provider)
        if provider is not None and provider.request_cancel(db, row, mail_provider):
            row.stop_notified_at = now
        else:
            log.warning("support: stop %s recorded but whoever cancels it was not reached", row.id)
    return row


def retry_stop_requests(
    db: Session,
    *,
    mail_provider,
    profile_id: str | None = None,
    now: datetime | None = None,
) -> int:
    """Ask again for every Stop nobody was told about. Returns how many went.

    `profile_id` narrows it to one hiker's rows. Without it, the oldest
    `RETRY_BATCH`. Does not commit.
    """
    query = db.query(SupportChoice).filter(
        SupportChoice.status == SupportStatus.stop_requested,
        SupportChoice.stop_notified_at.is_(None),
    )
    if profile_id is not None:
        query = query.filter(SupportChoice.profile_id == profile_id)
    rows = query.order_by(SupportChoice.stop_requested_at).limit(RETRY_BATCH).all()
    for row in rows:
        request_stop(db, row, mail_provider=mail_provider, now=now)
    return sum(1 for row in rows if row.stop_notified_at is not None)


def year_total(db: Session, year: int, now: datetime | None = None) -> tuple[int, int]:
    """(cents, supporters) given in `year`, in dollars, before fees.

    **Reasoned from start dates, not read from payouts.** Nothing Buy Me a
    Coffee sends reports each renewal charge, so a yearly payment is counted
    once in the year it started and once in every later year whose
    anniversary has passed before it ended. A refunded or failed charge, or a
    paused membership's skipped one, would make this high and nothing here
    can see one - which is why the page calls it "given", reads it live, and
    never rounds it up.

    Only `TOTAL_CURRENCY`: an amount in another currency is left out rather
    than converted at a rate nobody here can stand behind.
    """
    now = now or utc_now()
    total = 0
    supporters = 0
    rows = (
        db.query(SupportChoice)
        .filter(
            SupportChoice.started_at.isnot(None),
            SupportChoice.amount_cents > 0,
            SupportChoice.currency == TOTAL_CURRENCY,
        )
        .all()
    )
    for row in rows:
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
            # A payment ending exactly on an anniversary is not charged on it:
            # `cancel_scheduled` stores the period's end, which is that date.
            if charge > now or (row.ended_at is not None and charge >= row.ended_at) or charge.year > year:
                break
            if charge.year == year:
                charges += 1
            k += 1
        if charges:
            total += charges * row.amount_cents
            supporters += 1
    return total, supporters
