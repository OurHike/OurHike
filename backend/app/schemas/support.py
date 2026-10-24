"""Pydantic request/response models for the `/support` router (#1876)."""

from typing import Literal

from pydantic import BaseModel

from app.core.time import UtcDatetime
from app.models.support import SupportCadence, SupportChoice

# The three paid answers, in cents a year - the maintainer's $1, $10 and $100
# (poll, 2026-10-23). $0 is the fourth answer and never reaches this API.
PaidTier = Literal[100, 1000, 10000]


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


SupportStatusOut = Literal["none", "pending", "active", "stop_requested", "stopped"]


class SupportOut(BaseModel):
    """The caller's latest paid choice, or `status: "none"` with every other
    field null. Mirrors the client's `SupportSummary` (client/src/lib/
    support.ts), which tests/test_client_response_contract.py holds it to."""

    status: SupportStatusOut
    amount_cents: int | None
    cadence: SupportCadence | None
    provider: str | None
    email: str | None
    chosen_at: UtcDatetime | None
    started_at: UtcDatetime | None
    stop_requested_at: UtcDatetime | None
    ended_at: UtcDatetime | None

    @classmethod
    def from_row(cls, row: SupportChoice | None) -> "SupportOut":
        if row is None:
            return cls(
                status="none",
                amount_cents=None,
                cadence=None,
                provider=None,
                email=None,
                chosen_at=None,
                started_at=None,
                stop_requested_at=None,
                ended_at=None,
            )
        return cls(
            status=row.status.value,
            amount_cents=row.amount_cents,
            cadence=row.cadence,
            provider=row.provider,
            email=row.email,
            chosen_at=row.chosen_at,
            started_at=row.started_at,
            stop_requested_at=row.stop_requested_at,
            ended_at=row.ended_at,
        )


class SupportChoiceReceipt(BaseModel):
    support: SupportOut
    # Where the website app goes to pay; null for `delivery: "email"`.
    checkout_url: str | None
    # Whether the store apps' setup email actually went.
    emailed: bool


class SupportTotalOut(BaseModel):
    """The published running total (the maintainer chose to publish it rather
    than cut anything off at the $100,000 line, 2026-10-23). Before fees."""

    year: int
    total_cents: int
    supporters: int


class WebhookAck(BaseModel):
    """What this server did with one delivery, in a word - for Buy Me a
    Coffee's delivery log and for the test that reads it."""

    result: str
