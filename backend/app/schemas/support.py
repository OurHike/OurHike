"""Pydantic request/response models for the `/support` router (#1876)."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.core.support import BLOCKS_CHOICE, RUNNING, STOPPABLE
from app.core.support_providers import current_provider, provider_for
from app.core.time import UtcDatetime
from app.models.support import SupportCadence, SupportChoice

# The three paid answers, in cents a year - the maintainer's $12, $60 and
# $120, which are $1, $5 and $10 a month (2026-10-27, replacing the $1, $10
# and $100 of the 2026-10-23 poll). $0 is the fourth answer and never reaches
# this API.
PaidTier = Literal[1200, 6000, 12000]


class SupportChoiceIn(BaseModel):
    """A paid choice. The email is not a field: it is the verified address on
    the caller's token (core/auth.py's `get_current_email`), never one typed
    into a form, so a hiker cannot point somebody else's payment at their own
    account."""

    amount_cents: PaidTier
    accounting_email: bool = False
    # `redirect` from the website app; `email` from the iOS and Android apps,
    # which may not link to a payment outside the store's own.
    delivery: Literal["redirect", "email"]
    # "Share usage statistics" was on on the phone that chose. Off, the
    # level is never counted (core/analytics_support.py), even before that
    # answer has synced to the account.
    usage_counts: bool = True


SupportStatusOut = Literal[
    "none", "pending", "active", "payment_failed", "paused", "cancel_scheduled", "stop_requested", "stopped"
]


class SupportOut(BaseModel):
    """The caller's support, or `status: "none"` with every other field null.
    Mirrors the client's `SupportSummary` (client/src/lib/api.ts), which
    tests/test_client_response_contract.py holds it to.

    The three booleans are the server's answer so the app does not keep its
    own copy of the state machine (the #1885 architecture review):
    `supporting` - a recurring payment exists and nothing has ended it, so the
    day-5 ask has its answer; `can_stop` - the Stop button does something;
    `can_choose` - a new choice would be accepted rather than 409.
    `provider_label` is for the website only: the store apps never name a
    payment provider.
    """

    status: SupportStatusOut
    amount_cents: int | None
    cadence: SupportCadence | None
    provider: str | None
    provider_label: str | None
    email: str | None
    chosen_at: UtcDatetime | None
    started_at: UtcDatetime | None
    period_end: UtcDatetime | None
    stop_requested_at: UtcDatetime | None
    ended_at: UtcDatetime | None
    supporting: bool
    can_stop: bool
    can_choose: bool
    # The "Emails about my support" switch, for the address this support is
    # under (the maintainer, poll 2026-10-27). True when nothing turned it off.
    support_emails: bool

    @classmethod
    def from_row(
        cls,
        row: SupportChoice | None,
        *,
        blocked: bool | None = None,
        stoppable: bool | None = None,
        support_emails: bool = True,
    ) -> "SupportOut":
        """`blocked` is whether ANY of the caller's rows blocks a new choice
        (see core/support.BLOCKS_CHOICE), and `stoppable` whether any of them
        could still be stopped; the router knows, a single row may not - a
        stopped duplicate beside a payment still charging is the fourth
        review's case. Left None, each is read off this row."""
        if row is None:
            return cls(
                status="none",
                amount_cents=None,
                cadence=None,
                provider=None,
                provider_label=None,
                email=None,
                chosen_at=None,
                started_at=None,
                period_end=None,
                stop_requested_at=None,
                ended_at=None,
                supporting=False,
                can_stop=False,
                can_choose=current_provider() is not None,
                support_emails=support_emails,
            )
        provider = provider_for(row.provider)
        if blocked is None:
            current = current_provider()
            blocked = current is not None and row.provider == current.key and row.status in BLOCKS_CHOICE
        return cls(
            status=row.status.value,
            amount_cents=row.amount_cents,
            cadence=row.cadence,
            provider=row.provider,
            provider_label=provider.label if provider is not None else None,
            email=row.email,
            chosen_at=row.chosen_at,
            started_at=row.started_at,
            period_end=row.period_end,
            stop_requested_at=row.stop_requested_at,
            ended_at=row.ended_at,
            supporting=row.status in RUNNING,
            can_stop=row.status in STOPPABLE if stoppable is None else stoppable,
            can_choose=current_provider() is not None and not blocked,
            support_emails=support_emails,
        )


class SupportChoiceReceipt(BaseModel):
    support: SupportOut
    # Where the website app goes to pay; null for `delivery: "email"`.
    # Always https - the app refuses to navigate anywhere else.
    checkout_url: str | None
    # Whether a setup email reached the hiker's address, now or within the
    # last day (core/support_mail.SETUP_LINK_EVERY).
    emailed: bool


class SupportTotalOut(BaseModel):
    """The published running total (the maintainer chose to publish it rather
    than cut anything off at the $100,000 line, 2026-10-23). Dollars only,
    before fees."""

    year: int
    # Never below zero: a refund is dated when the money went back (the
    # maintainer, 2026-10-29), so a December charge refunded in January
    # would otherwise print as minus that much.
    total_cents: int
    supporters: int
    # Whether this server takes a paid choice now. The app asks nobody while
    # it does not - a required question every answer to which fails is worse
    # than none (the fourth #1885 review).
    accepting: bool


class WebhookAck(BaseModel):
    """What this server did with one delivery, in a word - for the provider's
    delivery log and for the test that reads it."""

    result: str


class SupportMailIn(BaseModel):
    """The app's "Emails about my support" switch."""

    model_config = ConfigDict(extra="forbid")

    support_emails: bool
