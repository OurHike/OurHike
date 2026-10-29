"""A paid support choice, counted as a usage event when Stripe confirms it (#1876 on #1902).

The maintainer, poll 2026-10-27: "track once for each dollar level, even 0",
counted **when paid ($0 when chosen)**, carrying **the level only**. The $0
half is the phone's - it sends a `support_chosen` row the moment a hiker
keeps $0 (client/src/lib/useUsageMeasurement.ts). This is the paid half, and
it cannot be the phone's: a phone knows a hiker went to a payment page, not
that the payment went through. Stripe's `checkout.session.completed` with
`payment_status: paid` is the confirmation (app/core/support_providers/
stripe.py), and app/core/support.py calls `count_paid_choice` when it applies
one.

WHAT THE ROW IS

One `analytics_events` row: `event = support_chosen`, the level in
`support_cents`, the day it was counted in `local_date`, and nothing else -
a random id, no `user_key`, nothing sealed, no club, every heartbeat flag
false. It is counted into the month's `support_chosen_<cents>` figure by the
nightly rollup and deleted with that month's other rows six months on, like
any row.

- **The level is the tier OurHike's link was for** (`ourhike_tier_cents`,
  the metadata every one of its Payment Links sets), not the amount charged:
  a tax or a discount on Stripe's side would otherwise split one tier into
  several levels (the fourth #1885 review). The amount the hiker chose is the
  fallback; a zero or missing level writes nothing, because a paid level of
  $0 would read as the phone's $0, which is a different answer.
- **Dated the day it is counted**, not the day the checkout opened: a
  confirmation Stripe resends weeks later must not land in a month the
  rollup has already closed.
- **Platform `web`**, because the column must hold one and every payment is
  taken on Stripe's page in a browser ("take payment only on the website").
  It says where the money was taken, not which app the hiker uses.
- **Once per choice.** `counted_at` on the choice row records it, and that
  row is locked by the caller (`_by_choice` / `_by_payment`), so a
  redelivered event, or a second tab paying for the same choice, finds it
  set and writes nothing. A hiker who stops and later chooses again has made
  a second choice and is counted again at its level.
- **A provider move is not a choice.** A row that replaces a choice on an
  older provider (`replaces_choice_id`) was already counted when it began.

WHAT IT DOES NOT CLAIM

- **Nothing in the row points back to the payer.** Its id is random, so it
  cannot be recomputed from the choice id - the third review's design derived
  it from the choice, and the fourth showed that joined it straight back to
  the account. The date and the level are still both on the `support_choices`
  row, so whoever reads that table could guess at a match on a quiet day;
  the row adds nothing that table does not already hold.
- **A refund does not take it back.** It counts choices Stripe confirmed,
  and a month already closed cannot change; refunds come off the published
  total, which is read from `support_charges` (app/core/support.py).
- **A choice made with "Share usage statistics" off is never counted**, by
  the phone's answer as it chose (`uncounted`) or the account's synced one
  (`_synced_consent`'s rule in app/routers/analytics.py). So the monthly
  figures can read lower than the number of payments; the money is in
  `support_charges`, not here. A payment with no account behind it (a link
  used straight from the website) has no switch to read, and is counted.
- **The intake gates do not apply.** The day's row budget and the "rollup
  stopped" pause exist to bound what strangers can post
  (app/routers/analytics.py); this row is written by the server, at most once
  per choice.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.analytics import AnalyticsEvent, SealState, UsageEvent, UsagePlatform
from app.models.preferences import UserPreferences
from app.models.support import SupportChoice


def _measurement_off(db: Session, profile_id: str | None) -> bool:
    """The account synced "Share usage statistics" off. No account: nothing to read."""
    if profile_id is None:
        return False
    stored = db.get(UserPreferences, profile_id)
    data = stored.data if stored is not None and isinstance(stored.data, dict) else {}
    return data.get("measurement_enabled", True) is False


def count_paid_choice(db: Session, choice: SupportChoice, *, cents: int | None, now: datetime) -> bool:
    """Count `choice`'s level once. True when a row was written now.

    `choice` must be locked by the caller. Does not commit: it rides in the
    transaction that recorded the payment, so the count and the payment land
    together or not at all.
    """
    if choice.counted_at is not None or cents is None or cents <= 0:
        return False
    if choice.uncounted or _measurement_off(db, choice.profile_id):
        return False
    db.add(
        AnalyticsEvent(
            id=str(uuid.uuid4()),
            local_date=now.date(),
            received_on=now.date(),
            event=UsageEvent.support_chosen,
            platform=UsagePlatform.web,
            user_key=None,
            week_first=False,
            month_first=False,
            ever_first=False,
            kind_month_first=False,
            month_returning=False,
            signed_in=False,
            has_fix=False,
            seal=SealState.none,
            support_cents=cents,
        )
    )
    choice.counted_at = now
    return True
