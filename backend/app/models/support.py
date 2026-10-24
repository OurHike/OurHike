"""The `support_choices` table - what a hiker chose to give OurHike (#1876).

One row per paid choice. A $0 answer never reaches this table: it stays on
the hiker's phone and needs no account (maintainer decision, 2026-10-23). A
paid choice is verified through the account instead, which is the only
reason this table exists.

THE LIFE OF A ROW

  pending         the hiker chose in the app; nothing has been paid
  active          Buy Me a Coffee's signed `membership.started` arrived
  stop_requested  the hiker pressed Stop; the founder cancels it by hand,
                  because Buy Me a Coffee publishes no cancel API (searched
                  2026-10-23) - the maintainer chose "we stop it for you"
                  over sending a hiker through Buy Me a Coffee's own
                  eight-step cancel
  stopped         Buy Me a Coffee's `membership.cancelled` arrived

A later choice by the same hiker after `stopped` is a new row, so the history
of what they gave survives - the accounting the support page promises reads
these rows, and a refund question months later needs the old one.

WHY THE EMAIL IS STORED HERE, when core/auth.py's `get_current_email` says
"Nothing stores it". Supabase owns the address for signing in, and that rule
stands for signing in. Here the address is the only thing Buy Me a Coffee's
webhook names the supporter by (`supporter_email`, its webhook spec read
2026-10-23), so matching a payment to an account needs a copy on this side;
and the maintainer chose to keep it so that one email can move a supporter if
OurHike ever changes payment provider. It is the address the hiker confirmed
on the choice screen, not one a webhook made up.

WHAT IS KEPT FOR A LATER PROVIDER MOVE ("grab the right info from the
get-go", the maintainer's brief): the provider's own subscription id
(`provider_ref`), the card processor's (`psp_ref`, Stripe's subscription id
in Buy Me a Coffee's payload), the amount in cents and its currency rather
than a tier label, the cadence, every date, and when the hiker was told about
the one move email (`migrate_notice_at`). Whether a Stripe subscription id
lets a move happen WITHOUT the supporter re-confirming is not known - Buy Me
a Coffee says it uses "Stripe Standard Connect", which would put the
subscriptions in the creator's own Stripe account, and nobody has checked.

`profile_id` is nullable for one case: a membership that starts on Buy Me a
Coffee with an email no OurHike account chose with (somebody who found the
page directly). The row is kept, unattached, so the total is honest and a
later choice with that email can claim it.

See app/models/profile.py for the naive-UTC convention.
"""

import enum
import uuid

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Integer, String

from app.core.time import utc_now
from app.db.base import Base


class SupportStatus(str, enum.Enum):
    pending = "pending"
    active = "active"
    stop_requested = "stop_requested"
    stopped = "stopped"


class SupportCadence(str, enum.Enum):
    """Yearly, the maintainer's choice over monthly (2026-10-23). The column
    holds the word so a monthly schedule later is a value, not a migration."""

    year = "year"
    month = "month"


class SupportChoice(Base):
    __tablename__ = "support_choices"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # "My support" is the hot read - every signed-in launch past day five.
    profile_id = Column(String, ForeignKey("profiles.id"), nullable=True, index=True)
    # Lowercased and trimmed, which is how the webhook's address is matched.
    email = Column(String(320), nullable=False, index=True)

    provider = Column(String(40), nullable=False, default="buymeacoffee")
    provider_ref = Column(String(100), nullable=True, index=True)
    psp_ref = Column(String(100), nullable=True)

    amount_cents = Column(Integer, nullable=False)
    currency = Column(String(3), nullable=False, default="USD")
    cadence = Column(Enum(SupportCadence, native_enum=False, length=10), nullable=False, default=SupportCadence.year)

    status = Column(
        Enum(SupportStatus, native_enum=False, length=20),
        nullable=False,
        default=SupportStatus.pending,
        index=True,
    )

    # Opted in on the choice screen; off unless ticked.
    accounting_email = Column(Boolean, nullable=False, default=False)
    # When the hiker was shown "we'll email you once to move it".
    migrate_notice_at = Column(DateTime, nullable=True)

    chosen_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    stop_requested_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)
