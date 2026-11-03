"""The seam between OurHike's support record and whoever takes the money (#1876).

The maintainer's plan has more than one payment provider in it: Stripe now,
Open Source Collective next, a nonprofit's own processor later
(features/SUPPORTING_OURHIKE.md §2). The adversarial review of #1885 found
the first provider (Buy Me a Coffee) assumed in every layer - its event names
and payload shapes in the state machine, its settings read in the router, its
name in the founder's email - so a second provider would have been a rewrite.
This file is the answer: what a provider must do, in OurHike's words rather
than any provider's, and nothing else. It was proved the same week: the
maintainer replaced Buy Me a Coffee with Stripe (2026-10-27), and the swap was
one module.

A PROVIDER DOES FOUR THINGS and owns everything provider-shaped about them:

- **checkout_url** - where a hiker pays for a choice, or None when this
  provider is not set up here. Per choice rather than one fixed link, so a
  provider that can carry the amount or OurHike's choice id in the URL can.
- **verify** - whether a webhook delivery really came from it: a signature,
  a fetch-back, whatever that provider offers. Raw bytes in, so a signature
  is computed over exactly what arrived.
- **normalise** - its payload, turned into `ProviderEvent`s: a provider's
  dialect stops here, and `core/support.py` never sees it. Personal fields a
  provider sends that OurHike has no use for (a supporter's display name,
  their note, a cancellation reason the app promised never to ask for) are
  dropped here, before anything is stored.
- **request_cancel** - start stopping one hiker's recurring payment: an API
  call where the provider has one, an email to the founder where it does not
  or the call fails. True when the request reached something that will act.

The state machine, the matching of a payment to a choice, the guard against
late retries, the event log and the published total live in
`core/support.py` and are the same for every provider.
"""

from __future__ import annotations

import enum
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Literal, Protocol

from app.models.support import SupportCadence

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.models.support import SupportChoice


class EventKind(str, enum.Enum):
    """What happened, in OurHike's words. A provider maps its own names here.

    - `started` / `updated`: a recurring payment exists and is current.
    - `paused`: it exists and is not charging, by the member's or the
      creator's hand.
    - `failing`: it exists, a renewal failed, and the provider is retrying
      the card.
    - `ended`: it will charge no more.
    - `charged`: money actually arrived - one charge, which the published
      total sums. It never changes a row's state.
    - `refunded`: money went back. `charge_ref` is the provider's id for
      what was refunded, `amount_cents` the total refunded of it so far, and
      `customer_ref` the payer, which is how core/support.py tells one of
      OurHike's charges from anything else on the account. It never changes
      a row's state either.
    """

    started = "started"
    updated = "updated"
    failing = "failing"
    paused = "paused"
    ended = "ended"
    charged = "charged"
    refunded = "refunded"


@dataclass(frozen=True)
class ProviderEvent:
    """One provider event, normalised. Every field but `kind` may be None,
    because providers differ in what they send and an unknown is stored as
    unknown rather than guessed."""

    kind: EventKind
    # The provider's own id for this delivery, kept in the event log.
    event_id: str | None = None
    # When the provider says it happened. The ordering guard reads this.
    occurred_at: datetime | None = None
    # The provider's id for the recurring payment, and for the person.
    subscription_ref: str | None = None
    # The provider's id for one charge (`charged` only): what stops the same
    # money being counted twice.
    charge_ref: str | None = None
    # The provider's own word for the payment's state, stored on the row.
    provider_status: str | None = None
    customer_ref: str | None = None
    # The card processor's id behind it, when the provider is not the card
    # processor itself and passes it on. None for Stripe, which is both.
    psp_ref: str | None = None
    # The level or plan the supporter picked on the provider's page.
    plan_ref: str | None = None
    # OurHike's own choice id, for a provider that carries it through
    # checkout. Matched after the subscription id; the email is the fallback.
    choice_ref: str | None = None
    email: str | None = None
    # When the recurring payment began, by the provider's clock. The email
    # fallback reads it: a payment that began before the choice was made
    # cannot be the payment for that choice.
    started_at: datetime | None = None
    amount_cents: int | None = None
    # The tier OurHike's own link was for, in cents a year - not the amount
    # charged, which a tax or a discount could move. The level a paid choice
    # is counted at (core/analytics_support.py).
    tier_cents: int | None = None
    currency: str | None = None
    cadence: SupportCadence | None = None
    period_end: datetime | None = None
    cancel_at_period_end: bool | None = None
    # The payload with personal fields removed, for the event log.
    payload: dict[str, Any] = field(default_factory=dict)


class SupportProvider(Protocol):
    """See the module docstring. `key` is the stored `provider` value and the
    webhook path segment; `label` is what a person reads; `cancel` says
    whether `request_cancel` reaches an API or a person."""

    key: str
    label: str
    cancel: Literal["api", "manual"]

    def checkout_url(self, choice: SupportChoice) -> str | None: ...

    def webhook_configured(self) -> bool: ...

    def ready(self) -> bool:
        """Whether new choices may go here: a hiker can pay, the payment will
        be recorded, and a Stop can reach somebody. A provider that is not
        ready takes no choices, rather than taking money it cannot stop."""
        ...

    def verify(self, headers: Mapping[str, str], raw_body: bytes) -> bool: ...

    def normalise(self, envelope: Mapping[str, Any]) -> list[ProviderEvent]: ...

    def request_cancel(self, db: Session, choice: SupportChoice, mail_provider: Any) -> bool: ...

    def refund_from_log(self, payload: Mapping[str, Any], occurred_at: datetime | None) -> ProviderEvent | None:
        """A `refunded` event rebuilt from its logged payload, or None.

        For a refund that arrived before the charge it reverses, and was
        logged as not OurHike's: once the charge lands, core/support.py asks
        for it back, so the provider's field names stay in its own module."""
        return None
