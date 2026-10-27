"""The support tables - what a hiker chose to give OurHike, and what the
payment provider said about it (#1876).

`support_choices` holds one row per paid choice. A $0 answer never reaches
it: it stays on the hiker's phone and needs no account (maintainer decision,
2026-10-23). A paid choice is verified through the account instead, which is
the only reason this table exists. `support_events` is every provider event
that arrived, kept so ordering, idempotency and an audit are possible and so
a field nobody modelled yet can be recovered later.

THE LIFE OF A ROW

  pending           chosen in the app; nothing has been paid
  active            the provider says the recurring payment started
  payment_failed    the provider says a renewal failed and it is retrying
                    the card (Stripe's `past_due` and `unpaid`); a Stop here
                    cancels at once, so a retry cannot charge after it
  paused            the provider says it exists and is not charging
  cancel_scheduled  the provider says it ends at `period_end`; no more charges
  stop_requested    the hiker pressed Stop and the provider has not yet said
                    it ended - asked through Stripe's API, or the founder
                    by email when the API cannot be reached
  stopped           ended; also how a Stop on a never-paid `pending` choice
                    lands at once, since there is nothing to cancel

A later choice after `stopped` is a new row, so what was given survives - the
accounting reads these rows, and a refund question months later needs the old
one. A choice that moves a supporter to a new provider names the row it
replaces (`replaces_choice_id`), and the old one is asked to stop once the
new one starts.

WHY THE EMAIL IS STORED HERE, when core/auth.py's `get_current_email` says
"Nothing stores it". Supabase owns the address for signing in, and that rule
stands for signing in. Here it is the address the receipt and the stopped
notice go to, and the maintainer chose to keep it so one email can move a
supporter if OurHike changes provider. It is NEVER used to match a payment to
an account - a payment meets its choice by id only (core/support.py; the
third #1885 review showed what matching by an address anybody can type
allows). It is the verified address on the hiker's token or the one a signed
provider event carried, never one typed into a form, and empty on a choice
emptied by an account deletion.

WHAT IS KEPT FOR A PROVIDER MOVE ("grab the right info from the get-go", the
maintainer's brief), and why each:

- `provider`, `provider_ref`, `customer_ref`, `psp_ref`, `plan_ref`: the
  provider's ids for the recurring payment, the person, the card processor's
  subscription behind it (empty for Stripe, which is its own processor), and
  the tier's price or link. Whether a Stripe customer id lets a later move
  skip the supporter re-confirming is UNVERIFIED: Stripe's import guide
  copies customers but "Subscription data isn't copied" (docs.stripe.com,
  read by the #1885 review, 2026-10-26).
- `chosen_amount_cents` (what the hiker agreed to) beside `amount_cents`
  (what the provider reports), `currency`, `cadence`, `period_end` (the real
  renewal anniversary) and `started_at`: enough to recreate the same amount
  on the same anniversary somewhere else.
- `terms_version`, `delivery`, `migrate_notice_at` and `accounting_email_at`:
  which wording the hiker was shown, on which path, and when - the consent
  record for the one move email and the opt-in accounting email.

WHAT IS NOT KEPT: a supporter's display name, their note, a cancellation
reason, anything about a card. The providers drop those before storing
(core/support_providers/).

`profile_id` is null for a payment that named no choice (a link opened
outside the app, or edited) - kept so the founder can find it and cancel it
by hand, and never attached to an account by email - and for a choice emptied
by an account deletion, which keeps its id so a payment that still arrives
for it is recognised and stopped (app/core/account_deletion.py).

See app/models/profile.py for the naive-UTC convention.
"""

import enum
import secrets
import uuid

from sqlalchemy import JSON, Boolean, Column, DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint

from app.core.time import utc_now
from app.db.base import Base


class SupportStatus(str, enum.Enum):
    pending = "pending"
    active = "active"
    payment_failed = "payment_failed"
    paused = "paused"
    cancel_scheduled = "cancel_scheduled"
    stop_requested = "stop_requested"
    stopped = "stopped"


class SupportCadence(str, enum.Enum):
    """Yearly, the maintainer's choice over monthly (2026-10-23). The column
    holds the word so a monthly schedule later is a value, not a migration."""

    year = "year"
    month = "month"


# The wording a hiker agrees to on the choice screen - the one move email and
# the stop terms. Bumped whenever client/src/screens/SupportAsk.tsx's
# confirmation copy changes, so a stored choice says which words it was.
SUPPORT_TERMS_VERSION = "support-terms-2026-10-27"


class SupportChoice(Base):
    __tablename__ = "support_choices"
    # One row per provider recurring payment. Null refs (a pending choice)
    # are not unique-checked, in Postgres and SQLite alike.
    __table_args__ = (UniqueConstraint("provider", "provider_ref", name="uq_support_choices_provider_ref"),)

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # "My support" is the hot read - every signed-in launch past day five.
    profile_id = Column(String, ForeignKey("profiles.id"), nullable=True, index=True)
    # Lowercased and trimmed, which is how a provider's address is matched.
    email = Column(String(320), nullable=False, index=True)

    provider = Column(String(40), nullable=False)
    provider_ref = Column(String(100), nullable=True, index=True)
    customer_ref = Column(String(100), nullable=True)
    psp_ref = Column(String(100), nullable=True)
    plan_ref = Column(String(100), nullable=True)

    chosen_amount_cents = Column(Integer, nullable=True)
    amount_cents = Column(Integer, nullable=False)
    currency = Column(String(3), nullable=False, default="USD")
    cadence = Column(Enum(SupportCadence, native_enum=False, length=10), nullable=False, default=SupportCadence.year)

    status = Column(
        Enum(SupportStatus, native_enum=False, length=20),
        nullable=False,
        default=SupportStatus.pending,
        index=True,
    )

    # The consent record: which wording, on which path, and when.
    terms_version = Column(String(40), nullable=True)
    delivery = Column(String(10), nullable=True)
    migrate_notice_at = Column(DateTime, nullable=True)
    accounting_email = Column(Boolean, nullable=False, default=False)
    accounting_email_at = Column(DateTime, nullable=True)

    # The provider's own word for the payment's state ("past_due"), kept
    # because a provider decides from it how to cancel: Stripe cancels a
    # failing renewal at once rather than at the period's end.
    provider_status = Column(String(30), nullable=True)

    chosen_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    period_end = Column(DateTime, nullable=True)
    cancel_at_period_end = Column(Boolean, nullable=True)
    stop_requested_at = Column(DateTime, nullable=True)
    # When whoever cancels it was actually reached. Null on a
    # `stop_requested` row is the retry queue (core/support.retry_stop_requests).
    stop_notified_at = Column(DateTime, nullable=True)
    # When it was last tried, so the queue backs off rather than calling the
    # provider on every webhook and every look at the page.
    stop_attempted_at = Column(DateTime, nullable=True)
    # When the hiker was told the stop landed - once, whatever order the
    # provider's events arrive in.
    stop_confirmed_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)
    # The newest provider event applied - the guard against a late retry
    # undoing a later state.
    last_event_at = Column(DateTime, nullable=True)

    # A move between providers: the row this one replaces.
    replaces_choice_id = Column(String, ForeignKey("support_choices.id"), nullable=True)

    # The token in this hiker's one-click unsubscribe link. Random and per row,
    # so a link stops mail to the address it was sent to and nothing else.
    link_token = Column(String(64), nullable=False, default=lambda: secrets.token_urlsafe(32), unique=True, index=True)

    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)


class SupportEvent(Base):
    """One provider event as it arrived, personal fields removed.

    `outcome` is what core/support did with it, in a word - including
    `failed`, which is how an event that raised while being applied is kept
    rather than lost: the webhook still answers 200 so the provider does not
    disable an endpoint that keeps failing, and this row is where somebody
    finds it to replay. The total is summed from `support_charges`, not here.
    """

    __tablename__ = "support_events"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    provider = Column(String(40), nullable=False)
    event_id = Column(String(100), nullable=True, index=True)
    kind = Column(String(20), nullable=False)
    occurred_at = Column(DateTime, nullable=True)
    received_at = Column(DateTime, nullable=False, default=utc_now)
    choice_id = Column(String, ForeignKey("support_choices.id"), nullable=True, index=True)
    outcome = Column(String(40), nullable=False)
    payload = Column(JSON, nullable=True)


class SupportCharge(Base):
    """Money a provider says arrived: one row per charge, which the published
    total sums.

    Its own table, with typed columns, for two reasons the #1885 reviews gave:
    the same charge can reach this server twice at once, or as two separate
    events (Stripe says so), and only a unique key on the provider's id for
    the charge itself stops it being counted twice; and a total that read a
    provider's payload keys would count nothing for the next provider.
    """

    __tablename__ = "support_charges"
    __table_args__ = (UniqueConstraint("provider", "charge_ref", name="uq_support_charges_provider_ref"),)

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    provider = Column(String(40), nullable=False)
    # The provider's id for the charge (a Stripe invoice).
    charge_ref = Column(String(100), nullable=False)
    # The recurring payment it belongs to, so a charge that arrives before
    # its checkout can be joined to the choice afterwards.
    subscription_ref = Column(String(100), nullable=True, index=True)
    choice_id = Column(String, ForeignKey("support_choices.id"), nullable=True, index=True)
    amount_cents = Column(Integer, nullable=False)
    currency = Column(String(3), nullable=False)
    charged_at = Column(DateTime, nullable=False, index=True)
    # The end of the period this charge paid for.
    period_end = Column(DateTime, nullable=True)
    received_at = Column(DateTime, nullable=False, default=utc_now)
