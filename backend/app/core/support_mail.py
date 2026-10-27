"""The mail supporting OurHike sends, and the limits on it (#1876).

Five messages, none cold - each is one somebody needs to finish a thing they
asked for or to act on money (app/models/mail.py's rule for `MailPurpose`):

- **the setup link**, to a store-app hiker who pressed "Email me how to set
  it up". The one place a payment link reaches a store-app hiker: Apple's
  3.1.3 allows "communications outside of the app", and its 3.1.1(a) does not
  allow the link inside one outside the US.
- **the cancel request**, to the founder, when the provider's cancel API
  cannot be reached (no key configured, or Stripe refused) and a person has
  to do it.
- **the stopped notice**, to the hiker, once the provider says the payment
  their Stop asked about has ended - the second half of what the Stop screen
  promises ("we email you when it's done").
- **the started receipt**, to the hiker, when a payment begins: the amount,
  that it renews yearly on that date, and how to stop. Auto-renewal law
  (California's, amended 2025) expects exactly this acknowledgement, and an
  unrecognised charge a year later is the textbook card dispute.
- **the payment note**, to the founder, when a payment arrives that the app
  could not place: one for a choice already stopped, paid or deleted (it is
  set not to renew, and may need refunding), or one carrying no choice at
  all (nobody can stop it from the app).

**A SETUP LINK GOES AT MOST ONCE A DAY PER ADDRESS AND AMOUNT.** The #1885
security review found it had no limit: every PUT with `delivery: "email"`
sent one, and the address is whatever the token carries. `SETUP_LINK_EVERY`
is the limit, read off the send log rather than a column so that two rows (a
choice, then a new one) cannot each send their own; it is per amount, so a
hiker who changes tier gets the link for the tier they now chose.

**EVERY HIKER-FACING MESSAGE CARRIES A REAL UNSUBSCRIBE** when
`settings.api_public_url` is set: a per-row token whose page holds two
switches, "Emails about my support" and "Every other email from OurHike"
(the maintainer's choice, poll 2026-10-27, over one link that stopped
everything). A mail app's own one-click Unsubscribe turns off only the
first. The first is `SupportMailPreference`, checked here and nowhere else;
the second is app/core/mail.py's one suppression list. The setup link is
sent only when the hiker asks for it, so only the second stops it. The
founder's mail carries neither - a founder who could opt out of a cancel
request could opt a hiker into being charged.

**NOTHING HERE RAISES AND NOTHING HERE LOGS AN ADDRESS.** Each returns whether
the message went; a refusal is logged by the row id and the exception's class,
because the exception's own text carries the address (app/core/mail.py writes
it into every refusal).
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.config import settings
from app.core.mail import MailDisabled, MailFailed, MailSuppressed, normalise, send
from app.core.time import utc_now
from app.models.mail import EmailSend, MailPurpose, MailState
from app.models.support import SupportChoice, SupportMailPreference, SupportStatus

log = logging.getLogger(__name__)

# @unvalidated: one day is a round number picked to stop a loop, not a
# measurement of how often a real hiker re-asks. What would settle it is the
# send log once store-app choices exist - how many re-asks land inside a day.
SETUP_LINK_EVERY = timedelta(hours=24)

UNSUBSCRIBE_PATH = "/support/mail/stop/{token}"

# How a hiker stops, said the same way in every email. No count of taps: the
# #1885 review counted four and a sign-in where the copy said two.
HOW_TO_STOP = "To stop, open OurHike and go to More → Your support → Stop my support. No reason needed, and we cancel it for you."


def manage_url() -> str:
    """The app's own More → Your support, where a payment is stopped."""
    return f"{(settings.public_site_url or 'https://ourhike.org').rstrip('/')}/app/"


def unsubscribe_url(choice: SupportChoice) -> str:
    """This row's one-click unsubscribe, or the manage page when this API's
    public address is not configured (see `settings.api_public_url`)."""
    base = settings.api_public_url.rstrip("/")
    if base.startswith("https://") and choice.link_token:
        return base + UNSUBSCRIBE_PATH.format(token=choice.link_token)
    return manage_url()


def _stop_line(choice: SupportChoice) -> str:
    """The body's own unsubscribe line, when there is a real one to give."""
    url = unsubscribe_url(choice)
    return "" if url == manage_url() else f"\nChoose which emails you get from OurHike: {url}\n"


def support_mail_on(db: Session, address: str | None) -> bool:
    """Whether this address still wants emails about its support."""
    if not address:
        return True
    row = db.get(SupportMailPreference, normalise(address))
    return row is None or row.off_at is None


def set_support_mail(db: Session, address: str, on: bool) -> None:
    """Turn emails about this address's support on or off. Does not commit."""
    key = normalise(address)
    if not key:
        return
    row = db.get(SupportMailPreference, key)
    if row is None:
        row = SupportMailPreference(address=key)
        db.add(row)
    row.off_at = None if on else (row.off_at or utc_now())
    db.flush()


def dollars(cents: int, currency: str = "USD") -> str:
    whole = cents / 100
    text = f"{whole:,.0f}" if cents % 100 == 0 else f"{whole:,.2f}"
    return f"${text}" if currency == "USD" else f"{text} {currency}"


def _send(
    db: Session,
    *,
    choice: SupportChoice,
    to: str,
    purpose: MailPurpose,
    subject: str,
    body: str,
    unsubscribe: str,
    mail_provider,
    optional: bool = True,
) -> bool:
    """Send one message. `optional` mail is what the "Emails about my
    support" switch turns off; the founder's mail and a setup link the hiker
    just asked for are not."""
    if mail_provider is None or not to:
        return False
    if optional and to != settings.support_notify_address and not support_mail_on(db, to):
        log.info("support: %s for choice %s not sent: support emails are off", purpose.value, choice.id)
        return False
    try:
        send(
            db,
            to=to,
            purpose=purpose,
            subject=subject,
            body_text=body,
            unsubscribe_url=unsubscribe,
            provider=mail_provider,
            enabled=settings.mail_enabled,
            allowed=settings.mail_allowed,
        )
    except (MailDisabled, MailSuppressed, MailFailed, ValueError) as exc:
        # ValueError is mail.py refusing something that is not an address -
        # a token's email claim can be odd (`hiker@localhost`), and a 500 for
        # that would be this module's fault, not the hiker's.
        log.warning("support: %s for choice %s not sent: %s", purpose.value, choice.id, type(exc).__name__)
        return False
    return True


def setup_link_sent_since(db: Session, address: str, subject: str, since: datetime) -> bool:
    """Whether this setup link - this address, this subject, which names the
    amount - was sent (or handed to the provider) since `since`. A `failed`
    send does not count: nothing went."""
    return (
        db.query(EmailSend)
        .filter(
            EmailSend.to_address == normalise(address),
            EmailSend.purpose == MailPurpose.support_setup_link,
            EmailSend.subject == subject,
            EmailSend.state != MailState.failed,
            EmailSend.created_at >= since,
        )
        .first()
        is not None
    )


def send_setup_link(
    db: Session,
    choice: SupportChoice,
    *,
    checkout_url: str | None,
    provider_label: str,
    mail_provider,
    now: datetime,
) -> bool:
    """Email the checkout link to a store-app hiker. True when a link reached
    this address, now or inside `SETUP_LINK_EVERY` - either way the hiker has
    one in their inbox. Does not commit."""
    if not checkout_url:
        return False
    amount = dollars(choice.amount_cents, choice.currency)
    subject = f"Set up your {amount} a {choice.cadence.value} for OurHike"
    if setup_link_sent_since(db, choice.email, subject, now - SETUP_LINK_EVERY):
        return True
    body = (
        f"You chose to give OurHike {amount} a {choice.cadence.value}. Thank you.\n\n"
        f"Set it up here, on {provider_label}'s secure payment page:\n"
        f"{checkout_url}\n\n"
        f"{HOW_TO_STOP}\n"
        f"{_stop_line(choice)}"
    )
    return _send(
        db,
        choice=choice,
        to=choice.email,
        purpose=MailPurpose.support_setup_link,
        subject=subject,
        body=body,
        unsubscribe=unsubscribe_url(choice),
        mail_provider=mail_provider,
        optional=False,
    )


def _describe(row: SupportChoice) -> str:
    attached = "an account" if row.profile_id else "no account (paid on the provider's page)"
    return (
        f"- {dollars(row.amount_cents, row.currency)} a {row.cadence.value} on {row.provider}, "
        f"id {row.provider_ref or 'not yet confirmed'}, {row.status.value}, attached to {attached}"
    )


def email_founder_to_cancel(
    db: Session,
    choice: SupportChoice,
    *,
    provider_label: str,
    refs: Sequence[tuple[str, str | None]],
    how: str,
    mail_provider,
) -> bool:
    """Ask the founder to cancel one recurring payment by hand. True when it went.

    Lists every other record not yet stopped under the same address, because
    a provider names a supporter only by an email anybody can type: the #1885
    review showed a stranger's membership bought with a hiker's address
    sitting beside the hiker's own. The founder cancelling by hand is the one
    point a person can see both and pick the right one. Does not commit.
    """
    others = (
        db.query(SupportChoice)
        .filter(
            SupportChoice.email == choice.email,
            SupportChoice.id != choice.id,
            SupportChoice.status != SupportStatus.stopped,
        )
        .order_by(SupportChoice.started_at.desc().nullslast())
        .all()
    )
    amount = dollars(choice.amount_cents, choice.currency)
    lines = [
        f"A supporter asked to stop {amount} a {choice.cadence.value} on {provider_label}.",
        "",
        f"Email: {choice.email}",
        f"OurHike choice id: {choice.id}",
        *(f"{label}: {value or 'unknown'}" for label, value in refs),
        "",
        how,
    ]
    if others:
        lines += [
            "",
            "Other records under the same address, not stopped. A provider matches by email, which anybody can "
            "type, so check you are cancelling the right one:",
            *(_describe(row) for row in others),
        ]
    return _send(
        db,
        choice=choice,
        to=settings.support_notify_address,
        optional=False,
        purpose=MailPurpose.support_stop_request,
        subject=f"Stop requested: {amount} a {choice.cadence.value} on {provider_label}",
        body="\n".join(lines) + "\n",
        unsubscribe=manage_url(),
        mail_provider=mail_provider,
    )


def email_hiker_stopped(db: Session, choice: SupportChoice, *, mail_provider) -> bool:
    """Tell a hiker the payment their Stop asked about has ended. Does not commit."""
    amount = dollars(choice.amount_cents, choice.currency)
    if choice.status == SupportStatus.cancel_scheduled and choice.ended_at is not None:
        when = f"Nothing more will be charged. What you already gave covers you to {choice.ended_at:%B} {choice.ended_at.day}, {choice.ended_at.year}."
    else:
        when = "Nothing more will be charged."
    body = (
        f"Your {amount} a {choice.cadence.value} to OurHike is stopped. {when}\n\n"
        "Thank you for what you gave. Choosing again is in the app, under More → Your support.\n"
        f"{_stop_line(choice)}"
    )
    return _send(
        db,
        choice=choice,
        to=choice.email,
        purpose=MailPurpose.support_stopped,
        subject=f"Your {amount} a {choice.cadence.value} to OurHike is stopped",
        body=body,
        unsubscribe=unsubscribe_url(choice),
        mail_provider=mail_provider,
    )


def _day(when: datetime) -> str:
    return f"{when:%B} {when.day}"


def email_hiker_started(db: Session, choice: SupportChoice, *, mail_provider) -> bool:
    """The receipt when a payment begins: what, how often, and how to stop.
    Does not commit."""
    amount = dollars(choice.amount_cents, choice.currency)
    began = choice.started_at or choice.updated_at
    renews = f"It renews every {choice.cadence.value}" + (f" on {_day(began)}" if began is not None else "") + "."
    body = (
        f"You're giving OurHike {amount} a {choice.cadence.value}. Thank you - it keeps the map free for "
        f"the hiker behind you.\n\n"
        f"{renews} You'll be charged {amount} each time until you stop it.\n\n"
        f"{HOW_TO_STOP}\n\n"
        "Questions, or a charge you don't recognise? Reply to this email.\n"
        f"{_stop_line(choice)}"
    )
    return _send(
        db,
        choice=choice,
        to=choice.email,
        purpose=MailPurpose.support_started,
        subject=f"You're giving OurHike {amount} a {choice.cadence.value}",
        body=body,
        unsubscribe=unsubscribe_url(choice),
        mail_provider=mail_provider,
    )


def email_founder_payment_note(
    db: Session,
    choice: SupportChoice,
    *,
    provider_label: str,
    what: str,
    mail_provider,
) -> bool:
    """Tell the founder about a payment the app could not place. Does not
    commit; never raises."""
    amount = dollars(choice.amount_cents, choice.currency)
    lines = [
        what,
        "",
        f"Amount: {amount} a {choice.cadence.value} on {provider_label}",
        f"Email the provider has: {choice.email or 'none'}",
        f"Subscription id: {choice.provider_ref or 'unknown'}",
        f"OurHike record: {choice.id}",
    ]
    return _send(
        db,
        choice=choice,
        to=settings.support_notify_address,
        optional=False,
        purpose=MailPurpose.support_payment_note,
        subject=f"A {amount} payment the app could not place",
        body="\n".join(lines) + "\n",
        unsubscribe=manage_url(),
        mail_provider=mail_provider,
    )
