"""The one place this project sends mail, and the promises that path keeps.

See ../../../features/ORG_ONBOARDING.md's "What we email on your behalf" and
app/models/mail.py for what is written down. Until 2026-09-17 nothing here
sent mail at all; the nominate flow needs it, because a hiker offers a club's
trails and three people at that club have to be asked.

**THIS IS COLD MAIL AND THE FILE SHOULD SAY SO.** The recipient never signed
up, never gave us their address - we read it off their organization's own
public page - and the first they hear of any of it is this message. That is
defensible only because it is about their own data and asks a question only
they can answer, and it stops being defensible the moment any of the four
promises below stops holding.

**1. OFF UNLESS SWITCHED ON.** `enabled` defaults to off and `allowed` exists
so that everywhere which is not production can exercise this without reaching
a real club. A preview deployment holding a fixture with somebody's real
address must not be one environment variable away from writing to them.

**2. THE SUPPRESSION LIST IS CHECKED HERE, NOT BY CALLERS.** One path, one
check. A promise each caller has to remember is a promise that lasts until
the second caller.

**3. A BOUNCE OR A COMPLAINT WRITES A SUPPRESSION.** `record_delivery_failure`
does both in one call for that reason - a list that records what happened
without preventing it happening again is a log, not a promise.

**4. EVERY MESSAGE SAYS HOW TO STOP IT**, in `List-Unsubscribe` and
`List-Unsubscribe-Post` (RFC 8058), so a mail client can offer one click
without anybody reading to the bottom. A message without somewhere to
unsubscribe is refused rather than sent - it is the one header that is not
optional here.

**SES, because boto3 is already a dependency** for report photos going to R2
over its S3-compatible API. One vendor library rather than two. The provider
is injected rather than constructed here, so the tests exercise the real
message-building against a stand-in rather than mocking the world.

**THE DNS SIDE IS NOT CODE AND IS NOT DONE BY THIS FILE.** SPF, DKIM and a
DMARC policy on the sending domain are what stop this mail being filed as
junk, and they are the maintainer's to set up on the real domain. See
features/ORG_ONBOARDING.md. Sending before they exist is how a domain earns
a reputation it cannot spend.
"""

from __future__ import annotations

import re
from email.message import EmailMessage
from email.utils import parseaddr

from sqlalchemy.orm import Session

from app.core.time import utc_now
from app.models.mail import (
    EmailSend,
    EmailSuppression,
    MailPurpose,
    MailState,
    SuppressionReason,
)

# Deliberately loose. This is a last line rather than a validator - the
# addresses reaching it came off `EmailStr` at the schema edge - and its job
# is to refuse something that is plainly not an address before a row is
# written, not to adjudicate RFC 5322.
_ADDRESS = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# What becomes a suppression, and as what.
_SUPPRESSES: dict[MailState, SuppressionReason] = {
    MailState.bounced: SuppressionReason.bounced,
    MailState.complained: SuppressionReason.complained,
}

DEFAULT_SENDER = "OurHike <hello@ourhike.org>"
DEFAULT_REPLY_TO = "hello@ourhike.org"


class MailDisabled(Exception):
    """Sending is off here, or this address is outside what this environment may reach."""


class MailSuppressed(Exception):
    """This address asked us to stop, and that answer does not expire."""


class MailFailed(Exception):
    """The provider refused it. The attempt is in `email_sends`."""


def normalise(address: str) -> str:
    """One spelling, because a suppression that misses on case is no suppression."""
    return (parseaddr(address or "")[1] or "").strip().lower()


def is_suppressed(db: Session, address: str) -> bool:
    """Whether anything may be sent to this address, ever."""
    return db.query(EmailSuppression).filter(EmailSuppression.address == normalise(address)).first() is not None


def suppress(
    db: Session,
    address: str,
    reason: SuppressionReason,
    *,
    note: str | None = None,
) -> EmailSuppression:
    """Never write to this address again. Idempotent, and keeps the first reason.

    Idempotent because the caller is usually a provider webhook, and those
    are replayed; a second bounce must not fail the handler recording it. The
    first reason is kept because why somebody originally said stop is the more
    useful fact - a complaint followed by a bounce is still a complaint.
    """
    address = normalise(address)
    existing = db.query(EmailSuppression).filter(EmailSuppression.address == address).first()
    if existing is not None:
        return existing
    row = EmailSuppression(address=address, reason=reason, note=note)
    db.add(row)
    db.flush()
    return row


def _sanitise_header(value: str) -> str:
    """A header value with no way out of its own line.

    A club's own name reaches the subject, and a newline in it would open a
    second header of somebody else's choosing. Stripped rather than refused:
    the words survive, harmlessly, on one line.
    """
    return re.sub(r"[\r\n\x00-\x1f\x7f]+", " ", value or "").strip()


def _build(
    *,
    sender: str,
    reply_to: str,
    to: str,
    subject: str,
    body_text: str,
    body_html: str | None,
    unsubscribe_url: str,
) -> bytes:
    message = EmailMessage()
    message["From"] = _sanitise_header(sender)
    message["To"] = to
    message["Reply-To"] = _sanitise_header(reply_to)
    message["Subject"] = _sanitise_header(subject)
    # RFC 8058. The Post header is what makes it one click rather than a page
    # the recipient has to read and understand.
    message["List-Unsubscribe"] = f"<{_sanitise_header(unsubscribe_url)}>"
    message["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
    # Says this is a machine's message, so a mail client does not offer an
    # out-of-office reply back to a mailbox nobody watches for them.
    message["Auto-Submitted"] = "auto-generated"
    message.set_content(body_text)
    if body_html:
        message.add_alternative(body_html, subtype="html")
    return message.as_bytes()


def send(
    db: Session,
    *,
    to: str,
    purpose: MailPurpose,
    subject: str,
    body_text: str,
    unsubscribe_url: str,
    provider,
    enabled: bool = False,
    allowed: tuple[str, ...] = (),
    body_html: str | None = None,
    sender: str = DEFAULT_SENDER,
    reply_to: str = DEFAULT_REPLY_TO,
    nomination_id: str | None = None,
    now=None,
) -> EmailSend:
    """Send one message, or refuse and say which promise stopped it.

    Does not commit - the caller owns the transaction, the same rule
    `account_deletion.py` follows. The refusals happen before anything is
    written, so a message that was never sent leaves no row claiming
    otherwise.
    """
    address = normalise(to)
    if not _ADDRESS.match(address):
        raise ValueError(f"{to!r} is not an email address.")
    if not unsubscribe_url or not unsubscribe_url.strip():
        raise ValueError("Every message needs somewhere to unsubscribe - see this module's promise 4.")

    if not enabled:
        raise MailDisabled("Sending is switched off in this environment.")
    if allowed and not any(address.endswith(suffix.lower()) for suffix in allowed):
        raise MailDisabled(f"This environment may only write to {', '.join(allowed)}, and {address} is not one.")
    if is_suppressed(db, address):
        raise MailSuppressed(f"{address} has asked not to hear from us.")

    row = EmailSend(
        to_address=address,
        purpose=purpose,
        subject=_sanitise_header(subject),
        state=MailState.queued,
        nomination_id=nomination_id,
    )
    db.add(row)
    db.flush()

    raw = _build(
        sender=sender,
        reply_to=reply_to,
        to=address,
        subject=subject,
        body_text=body_text,
        body_html=body_html,
        unsubscribe_url=unsubscribe_url,
    )
    try:
        answer = provider.send_email(
            FromEmailAddress=sender,
            Destination={"ToAddresses": [address]},
            Content={"Raw": {"Data": raw}},
        )
    except Exception as exc:  # the provider's own exception types are boto3's
        row.state = MailState.failed
        row.error = str(exc)[:2000]
        db.flush()
        raise MailFailed(f"The mail provider refused the message to {address}.") from exc

    row.state = MailState.sent
    row.provider_message_id = (answer or {}).get("MessageId")
    row.sent_at = now or utc_now()
    db.flush()
    return row


def record_delivery_failure(db: Session, provider_message_id: str, state: MailState) -> EmailSend | None:
    """A bounce or a complaint: mark the message and stop writing to the address.

    Both halves in one call deliberately. A caller that could do the first
    without the second would produce a list that records what happened and
    does not prevent it happening again.

    A notice about a message we have no record of is ignored rather than
    raising: provider webhooks are replayed, reordered, and occasionally
    about something we never sent.
    """
    row = db.query(EmailSend).filter(EmailSend.provider_message_id == provider_message_id).first()
    if row is None:
        return None
    row.state = state
    reason = _SUPPRESSES.get(state)
    if reason is not None:
        suppress(db, row.to_address, reason, note=f"from the provider, message {provider_message_id}")
    db.flush()
    return row
