"""Buy Me a Coffee, behind the provider seam (#1876). See base.py for the seam.

Everything here is read off Buy Me a Coffee's webhook OpenAPI spec
(https://cdn.buymeacoffee.com/assets/integrations/bmc-webhooks-openapi.json,
read 2026-10-23 and again by the #1885 review on 2026-10-26):

- each delivery is signed: HMAC-SHA256 of the raw body under the secret shown
  on the webhook's own page, as hex in `x-signature-sha256`;
- the envelope carries `event_id`, `type`, `live_mode`, `created` (Unix
  seconds), `attempt` and `data`; the dashboard's "Send test event" arrives
  with `live_mode: false`;
- a membership's `data` carries `id` (the membership, an integer),
  `supporter_id`, `psp_id` ("Stripe subscription ID"), `membership_level_id`,
  `supporter_email`, `amount` (a number of whole currency units), `currency`,
  `duration_type` (`month` or `year`), `status`, `canceled` and
  `cancel_at_period_end` (the strings "true" and "false"), and `started_at`,
  `canceled_at` and `current_period_end` (Unix seconds).

**A `status` OF "paused" OR "canceled" OUTRANKS THE EVENT'S NAME.** A
`membership.updated` carrying either is read as that, because the spec lets
an update carry any status and the name alone would read one as running.

**THERE IS NO CANCEL API** that the 2026-10-23 search found, so a Stop is a
person's job: `request_cancel` emails the founder, who cancels it in the
dashboard, and the `membership.cancelled` webhook then closes the record.

**WHAT IS DROPPED**, before anything is stored: `supporter_name`,
`supporter_name_type`, `support_note`, `note_hidden` and `supporter_feedback`.
The last one is a reason for cancelling, and the app promises never to ask
for one - storing one Buy Me a Coffee asked for instead would break that
promise by the back door. The email is kept on the choice, not in the log.
"""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.config import settings
from app.core.mail import normalise
from app.core.support_mail import email_founder_to_cancel
from app.core.support_providers.base import EventKind, ProviderEvent
from app.models.support import SupportCadence, SupportChoice

_KINDS = {
    "membership.started": EventKind.started,
    "membership.updated": EventKind.updated,
    "membership.paused": EventKind.paused,
    "membership.cancelled": EventKind.ended,
}

_DROPPED = {"supporter_name", "supporter_name_type", "support_note", "note_hidden", "supporter_feedback", "supporter_email"}

# RFC 5321's longest path, and the column's width.
MAX_EMAIL_LENGTH = 320

# The largest single amount believed, in cents: $100,000, this stage's whole
# yearly line. A signed delivery claiming more is a fault, not a supporter,
# and it would otherwise go straight into the published total.
MAX_AMOUNT_CENTS = 10_000_000


def _when(unix: Any) -> datetime | None:
    if isinstance(unix, bool) or not isinstance(unix, (int, float)):
        return None
    try:
        return datetime.fromtimestamp(unix, tz=timezone.utc).replace(tzinfo=None)
    except (OverflowError, OSError, ValueError):
        return None


def _cents(amount: Any) -> int | None:
    """Whole units to cents, or None for anything not a sane positive amount."""
    if isinstance(amount, bool) or not isinstance(amount, (int, float)):
        return None
    cents = int(round(amount * 100))
    return cents if 0 < cents <= MAX_AMOUNT_CENTS else None


def _ref(value: Any) -> str | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str) and value.strip() and len(value) <= 100:
        return value.strip()
    return None


def _flag(value: Any) -> bool | None:
    if value in (True, "true"):
        return True
    if value in (False, "false"):
        return False
    return None


class BuyMeACoffee:
    key = "buymeacoffee"
    label = "Buy Me a Coffee"
    cancel: Literal["api", "manual"] = "manual"

    def checkout_url(self, choice: SupportChoice) -> str | None:
        """The page's membership link. One link for every tier: Buy Me a
        Coffee's page lists the three levels and the hiker picks there, so
        the amount chosen in the app is matched afterwards by email and
        amount rather than enforced by the link (UNVERIFIED whether a level
        can be preselected by URL)."""
        url = settings.buymeacoffee_checkout_url
        return url if url.startswith("https://") else None

    def webhook_configured(self) -> bool:
        return bool(settings.buymeacoffee_webhook_secret)

    def verify(self, headers: Mapping[str, str], raw_body: bytes) -> bool:
        secret = settings.buymeacoffee_webhook_secret
        signature = headers.get("x-signature-sha256")
        if not secret or not signature or not signature.isascii():
            # `compare_digest` raises on a non-ASCII str, which was a 500
            # for a header anybody can send (#1885 review).
            return False
        expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature.strip().lower())

    def _level_allowed(self, level: str | None) -> bool:
        allowed = {part.strip() for part in settings.buymeacoffee_level_ids.split(",") if part.strip()}
        return not allowed or level in allowed

    def normalise(self, envelope: Mapping[str, Any]) -> list[ProviderEvent]:
        if envelope.get("live_mode") is not True:
            # False is the dashboard's test button; absent is not a delivery
            # this spec describes. Neither is recorded.
            return []
        kind = _KINDS.get(envelope.get("type"))  # type: ignore[arg-type]
        data = envelope.get("data")
        if kind is None or not isinstance(data, Mapping):
            return []

        level = _ref(data.get("membership_level_id"))
        if not self._level_allowed(level):
            return []
        if data.get("status") == "canceled" or _flag(data.get("canceled")):
            kind = EventKind.ended
        elif data.get("status") == "paused":
            kind = EventKind.paused
        email = data.get("supporter_email")
        email = normalise(email) if isinstance(email, str) and email.strip() else None
        duration = data.get("duration_type")
        currency = data.get("currency")
        return [
            ProviderEvent(
                kind=kind,
                event_id=_ref(envelope.get("event_id")),
                occurred_at=_when(envelope.get("created")) or _when(data.get("canceled_at")),
                subscription_ref=_ref(data.get("id")),
                customer_ref=_ref(data.get("supporter_id")),
                psp_ref=_ref(data.get("psp_id")),
                plan_ref=level,
                email=email if email and len(email) <= MAX_EMAIL_LENGTH else None,
                started_at=_when(data.get("started_at")),
                amount_cents=_cents(data.get("amount")),
                currency=currency.upper() if isinstance(currency, str) and len(currency) == 3 else None,
                cadence=SupportCadence(duration) if duration in ("year", "month") else None,
                period_end=_when(data.get("current_period_end")),
                cancel_at_period_end=_flag(data.get("cancel_at_period_end")),
                payload={
                    "type": envelope.get("type"),
                    "attempt": envelope.get("attempt"),
                    "data": {k: v for k, v in data.items() if k not in _DROPPED},
                },
            )
        ]

    def request_cancel(self, db: Session, choice: SupportChoice, mail_provider: Any) -> bool:
        return email_founder_to_cancel(
            db,
            choice,
            provider_label=self.label,
            refs=[
                ("Buy Me a Coffee membership id", choice.provider_ref),
                ("Buy Me a Coffee supporter id", choice.customer_ref),
                ("Stripe subscription id", choice.psp_ref),
            ],
            how="Cancel it in the Buy Me a Coffee dashboard today. Its membership.cancelled webhook "
            "marks the record stopped and emails the hiker that it is done.",
            mail_provider=mail_provider,
        )
