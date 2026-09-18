"""Mail this project sends to people who did not ask to hear from it.

See ../../../features/ORG_ONBOARDING.md's "What we email on your behalf".
Until 2026-09-17 this repository sent no mail at all, anywhere. The nominate
flow needs it - a hiker proposes a club's trails and three people at that
club have to be asked - and the maintainer chose to build sending properly
rather than hand the hiker a `mailto:`.

**COLD MAIL ABOUT SOMEBODY'S OWN DATA IS THE HARDEST KIND TO SEND WELL, and
the two tables here are the whole of what makes it defensible.** A send log,
so there is an answer to "did you write to us, and what did you say"; and a
suppression list that is checked before every send and never expires.

**THE SUPPRESSION LIST IS THE ONE THAT MATTERS.** A bounce, a complaint, or
a club clicking "No thank you" all land here, and nothing this project sends
may reach an address on it again - not a different nomination, not a
different hiker, not next year. A suppression that some later feature can
step around is not a suppression, which is why the check belongs in
`app/core/mail.py`'s send path and not in each caller.

**WE LOG THAT WE SENT, NOT WHAT WE SAID.** `subject` is here because a
person asking "what did you send about us" deserves to be told, and the
body is not, because it is reconstructible from the template and the
nomination and storing it would turn this into a copy of every message this
project has ever sent to somebody who never signed up.
"""

import enum
import uuid

from sqlalchemy import Column, DateTime, Enum, ForeignKey, String, Text

from app.core.time import utc_now
from app.db.base import Base


class MailPurpose(str, enum.Enum):
    """Why we wrote. One value per template, so the log can be read by kind.

    There is no `marketing` and there is not going to be: every value here is
    a message somebody at an organization needs in order to answer a question
    that was asked about them.
    """

    nomination_proposal = "nomination_proposal"
    nomination_reminder = "nomination_reminder"
    nomination_outcome = "nomination_outcome"


class MailState(str, enum.Enum):
    """What became of one message.

    `bounced` and `complained` are terminal and both write a suppression -
    that coupling is in `app/core/mail.py` rather than here, because a state
    machine cannot enforce a promise.
    """

    queued = "queued"
    sent = "sent"
    failed = "failed"
    bounced = "bounced"
    complained = "complained"


class EmailSend(Base):
    """One message, to one address, with what became of it."""

    __tablename__ = "email_sends"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    to_address = Column(String, nullable=False, index=True)
    purpose = Column(Enum(MailPurpose, native_enum=False, length=30), nullable=False)
    subject = Column(String, nullable=False)
    state = Column(Enum(MailState, native_enum=False, length=20), nullable=False, default=MailState.queued)
    # Which nomination this was about, so a club asking can be told the whole
    # story rather than shown a message with no context.
    nomination_id = Column(String, ForeignKey("org_nominations.id"), nullable=True, index=True)
    # The provider's own id, which is the only handle a deliverability
    # question can actually be chased with.
    provider_message_id = Column(String, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=utc_now, index=True)
    sent_at = Column(DateTime, nullable=True)


class SuppressionReason(str, enum.Enum):
    """Why an address is never written to again.

    `refused` is a club pressing "No thank you" and is the one that is a
    decision rather than a delivery event. It is in the same table as the
    bounces deliberately: one list checked on one path is a promise that
    holds, and two lists are a promise that holds until somebody forgets the
    second one.
    """

    bounced = "bounced"
    complained = "complained"
    refused = "refused"
    manual = "manual"


class EmailSuppression(Base):
    """An address nothing this project sends may reach again.

    No expiry column, deliberately. Every mechanism for ageing a suppression
    out is a mechanism for writing again to somebody who said stop.
    """

    __tablename__ = "email_suppressions"

    # Lowercased on the way in, because `Maps@Club.org` and `maps@club.org`
    # are one mailbox and a suppression that misses on case is no suppression.
    address = Column(String, primary_key=True)
    reason = Column(Enum(SuppressionReason, native_enum=False, length=20), nullable=False)
    created_at = Column(DateTime, nullable=False, default=utc_now)
    note = Column(Text, nullable=True)
