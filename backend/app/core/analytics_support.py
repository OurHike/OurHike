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
`support_cents`, the day of the confirmation in `local_date`, and nothing
else - no `user_key`, nothing sealed, no club, every heartbeat flag false. It
is counted into the month's `support_chosen_<cents>` figure by the nightly
rollup and deleted with that month's other rows six months on, like any row.

- **The level is the amount Stripe confirmed**, the session's `amount_total`
  in cents: what was paid, which is the tier the link was for. A zero or
  missing amount writes nothing - a paid level of $0 would be counted as the
  phone's $0, which is a different answer.
- **Platform `web`**, because the column must hold one and every payment is
  taken on Stripe's page in a browser ("take payment only on the website").
  It says where the money was taken, not which app the hiker uses.
- **Once per choice.** The row's id is derived from the choice the payment
  named (`client_reference_id`), or from the subscription when it named
  none, so a redelivered event, or a second tab paying for the same choice,
  meets the first row and writes nothing (`ON CONFLICT DO NOTHING`). A
  hiker who stops and later chooses again has made a second choice, with a
  new id, and is counted again at its level.
- **A provider move is not a choice.** A row that replaces a choice on an
  older provider (`replaces_choice_id`) was already counted when it began.

WHAT IT DOES NOT CLAIM

- **"Never linked" means no column links it**, not that nobody could. The
  row's date and level are copied from a `support_choices` row that names
  its payer, so whoever can read that table can match them up. It adds
  nothing to what that table already holds, and outlives none of it: raw
  usage rows go after six months, support rows after seven years.
- **A refund does not take it back.** It counts choices Stripe confirmed,
  and a month already closed cannot change; refunds come off the published
  total, which is read from `support_charges` (app/core/support.py).
- **An account that turned "Share usage statistics" off is not counted.**
  The same rule `POST /usage-events` keeps - the account's synced "off" wins
  (app/routers/analytics.py `_synced_consent`) - applied to the one row the
  server writes for it. So the monthly figures can read lower than the
  number of payments; the money is in `support_charges`, not here. A payment
  with no account behind it (a link used straight from the website) has no
  switch to read, and is counted.
- **The intake gates do not apply.** The day's row budget and the "rollup
  stopped" pause exist to bound what strangers can post
  (app/routers/analytics.py); this row is written by the server, at most once
  per payment.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.analytics_rollup import retention_start
from app.models.analytics import AnalyticsEvent, SealState, UsageEvent, UsagePlatform
from app.models.preferences import UserPreferences

# Fixed, so the same choice always derives the same row id. A random UUID
# chosen once (2026-10-27); it means nothing and must never change.
_ROW_NAMESPACE = uuid.UUID("6b1f0b8e-3f5d-4c1a-9a63-2d7f5c0e8a41")


def row_id(provider: str, choice_ref: str | None, subscription_ref: str | None) -> str | None:
    """The id a paid choice's row is stored under, or None when nothing names it."""
    if choice_ref:
        return str(uuid.uuid5(_ROW_NAMESPACE, f"{provider}:choice:{choice_ref}"))
    if subscription_ref:
        return str(uuid.uuid5(_ROW_NAMESPACE, f"{provider}:payment:{subscription_ref}"))
    return None


def _measurement_off(db: Session, profile_id: str | None) -> bool:
    """The account synced "Share usage statistics" off. No account: nothing to read."""
    if profile_id is None:
        return False
    stored = db.get(UserPreferences, profile_id)
    data = stored.data if stored is not None and isinstance(stored.data, dict) else {}
    return data.get("measurement_enabled", True) is False


def count_paid_choice(
    db: Session,
    *,
    provider: str,
    choice_ref: str | None,
    subscription_ref: str | None,
    cents: int | None,
    day: date,
    today: date,
    profile_id: str | None,
) -> bool:
    """Write the paid choice's one row. True when a row was written now.

    Does not commit: it rides in the transaction that recorded the payment,
    so the count and the payment land together or not at all.
    """
    if cents is None or cents <= 0:
        return False
    if day < retention_start(today):
        # A confirmation dated before retention lands in a month whose rows
        # are already gone - refused, as `POST /usage-events` refuses `too_old`.
        return False
    event_id = row_id(provider, choice_ref, subscription_ref)
    if event_id is None or _measurement_off(db, profile_id):
        return False
    row = {
        "id": event_id,
        "local_date": day,
        "received_on": today,
        "event": UsageEvent.support_chosen.value,
        "platform": UsagePlatform.web.value,
        "app_version": None,
        "user_key": None,
        "week_first": False,
        "month_first": False,
        "ever_first": False,
        "club_firsts": None,
        "kind_month_first": False,
        "month_returning": False,
        "signed_in": False,
        "clubs": None,
        "miles": None,
        "pageviews": None,
        "session_length": None,
        "has_fix": False,
        "area_lat": None,
        "area_lon": None,
        "seal": SealState.none.value,
        "sealed": None,
        "support_cents": cents,
    }
    written = db.execute(
        insert(AnalyticsEvent.__table__)
        .values(row)
        .on_conflict_do_nothing(index_elements=["id"])
        .returning(AnalyticsEvent.__table__.c.id)
    ).first()
    return written is not None
