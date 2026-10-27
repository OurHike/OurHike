"""`POST /usage-events` - where the app's usage measurement arrives (#1902).

See ../../../features/EVENTING.md for the design and app/models/analytics.py
for what each column means. Five things about this endpoint are decisions,
not oversights:

**It takes no account, and a token alone links nothing.** Counts are on by
default for everyone (the "split" consent, poll 2026-10-27), so a batch with
no token is ordinary. A row is linked to an account only when the batch says
`identified` - the hiker said yes - AND carries a valid token, and the account
then comes from the token, never from the body.

**It seals what it cannot read back.** The account id and the GPS fix go into
`sealed` under the month's public key (app/core/analytics_seal.py). If no key
has been published for the month, both are thrown away, never kept in the
clear, and the row says `no_key`.

**It refuses rather than repairs, one row at a time.** A usage event is the
first thing a phone drops (EVENTING.md §1 rule 4), so a row that does not
match the registry, or is dated outside what is kept, is refused - but only
that row. Refusing the batch meant one row from a phone whose clock jumped
cost the 199 good rows sent with it, because the phone drops a refused batch
whole. Every outcome is counted per day and app version in
`analytics_intake`, which is the only trace a refused row leaves.
app/schemas/analytics.py has the rules.

**It writes no IP address and keeps no batch.** No column holds one, and
nothing here logs the request. A batch is momentarily linkable on the wire -
nine heartbeats in one request came from one phone - and the claim is only
that the grouping is never written (EVENTING.md §2).

**What is deliberately NOT built:** rate limiting, the same gap
app/routers/app_failures.py names for the other unauthenticated write. A
flood of fake events would skew the counts; it could not reach anybody's
data. Said out loud so it is noticed before it is discovered.
"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from datetime import date, timedelta
from typing import Any

from fastapi import APIRouter, Depends, status
from pydantic import ValidationError
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.config import settings
from app.core.analytics_rollup import month_start, retention_start
from app.core.analytics_seal import month_label, seal, user_key
from app.core.auth import get_current_user_optional
from app.core.time import utc_now
from app.db.session import get_db
from app.models.analytics import (
    AnalyticsEvent,
    AnalyticsIntake,
    AnalyticsSealKey,
    IntakeOutcome,
    SealState,
    UsageEvent,
)
from app.models.profile import Profile
from app.schemas.analytics import VERSION_PATTERN, UsageBatchAck, UsageBatchIn, UsageEventIn

router = APIRouter(prefix="/usage-events", tags=["usage-events"])

# A phone's calendar may run a day ahead of the server's UTC one - it is
# already tomorrow in the hiker's own day for some hours of every evening
# west of Greenwich, and the other way round east of it. One day of slack
# covers both, and anything further ahead is a wrong clock.
FUTURE_SLACK = timedelta(days=1)


def _area(degrees: float) -> float:
    """The 0.1-degree square a coordinate falls in, by its south-west corner."""
    return math.floor(degrees * 10) / 10


_REFUSED = frozenset({IntakeOutcome.invalid, IntakeOutcome.too_old, IntakeOutcome.future})
_VERSION = re.compile(VERSION_PATTERN)


def _version_of(raw: Any) -> str:
    """A refused row's version when it carried a readable one, for the intake count."""
    version = raw.get("app_version") if isinstance(raw, dict) else None
    return version if isinstance(version, str) and len(version) <= 40 and _VERSION.match(version) else ""


def _sort_rows(raws: list[Any], today: date) -> tuple[list[UsageEventIn], Counter]:
    """The rows worth storing, and a count of the rest by version and outcome.

    A row dated before retention would land in a month the rollup has already
    deleted; one more than a day ahead is a wrong clock. Both are refused like
    a row that breaks the registry - alone.
    """
    earliest = retention_start(today)
    latest = today + FUTURE_SLACK
    kept: list[UsageEventIn] = []
    seen: set = set()
    outcomes: Counter = Counter()
    for raw in raws:
        version = _version_of(raw)
        try:
            event = UsageEventIn.model_validate(raw)
        except ValidationError:
            outcomes[(version, IntakeOutcome.invalid)] += 1
            continue
        if event.local_date > latest:
            outcomes[(version, IntakeOutcome.future)] += 1
        elif event.local_date < earliest:
            outcomes[(version, IntakeOutcome.too_old)] += 1
        elif event.id in seen:
            # The same row twice in one batch is a resend that met itself.
            outcomes[(version, IntakeOutcome.duplicate)] += 1
        else:
            seen.add(event.id)
            kept.append(event)
    return kept, outcomes


def _count_intake(db: Session, today: date, outcomes: Counter) -> None:
    """Add this batch's outcomes to the day's counts, in one statement.

    Sorted, so two batches arriving together take the counters' row locks in
    the same order and cannot deadlock each other.
    """
    if not outcomes:
        return
    table = AnalyticsIntake.__table__
    values = [
        {"received_on": today, "app_version": version, "outcome": outcome.value, "rows": count}
        for (version, outcome), count in sorted(outcomes.items(), key=lambda item: (item[0][0], item[0][1].value))
    ]
    statement = insert(table).values(values)
    db.execute(
        statement.on_conflict_do_update(
            index_elements=["received_on", "app_version", "outcome"],
            set_={"rows": table.c.rows + statement.excluded.rows},
        )
    )


def _public_keys(db: Session, months: set[date]) -> dict[date, bytes]:
    rows = db.execute(select(AnalyticsSealKey.month, AnalyticsSealKey.public_key).where(AnalyticsSealKey.month.in_(months)))
    return {month: bytes(key) for month, key in rows}


def _row(event: UsageEventIn, *, today: date, key: str | None, account_id: str | None, public_keys: dict) -> dict:
    event_id = str(event.id)
    month = month_start(event.local_date)

    to_seal: dict = {}
    if account_id is not None:
        to_seal["account"] = account_id
    if event.fix is not None:
        to_seal["lat"] = event.fix.lat
        to_seal["lon"] = event.fix.lon
        if event.fix.accuracy_m is not None:
            to_seal["accuracy_m"] = event.fix.accuracy_m

    sealed = None
    seal_state = SealState.none
    if to_seal:
        public_key = public_keys.get(month)
        if public_key is None:
            seal_state = SealState.no_key
        else:
            sealed = seal(public_key, month_label(month), event_id, to_seal)
            seal_state = SealState.sealed

    has_fix = event.fix is not None
    return {
        "id": event_id,
        "local_date": event.local_date,
        "received_on": today,
        "event": event.event.value,
        "platform": event.platform.value,
        "app_version": event.app_version,
        "user_key": key,
        "week_first": event.week_first,
        "month_first": event.month_first,
        "ever_first": event.ever_first,
        "club_firsts": list(event.club_firsts) or None,
        "kind_month_first": event.kind_month_first,
        "month_returning": event.month_returning,
        "signed_in": event.signed_in,
        "clubs": dict(event.clubs) if event.clubs else None,
        "miles": event.miles,
        "pageviews": event.pageviews,
        "session_length": event.session_length.value if event.session_length is not None else None,
        "has_fix": has_fix,
        # Kept only while the fix is sealed. A fix thrown away for want of a key
        # leaves no trace of where it was, not even the square.
        "area_lat": _area(event.fix.lat) if has_fix and seal_state == SealState.sealed else None,
        "area_lon": _area(event.fix.lon) if has_fix and seal_state == SealState.sealed else None,
        "seal": seal_state.value,
        "sealed": sealed,
    }


def _yyyymm(day: date) -> int:
    return day.year * 100 + day.month


# LEAST and GREATEST skip nulls, which is exactly the rule for a milestone:
# the earliest date anybody has seen it, or none yet. The months a hiker was
# active are a set, kept sorted so a row read with psql reads as a timeline.
_UPSERT_USER = text(
    """
    insert into analytics_users as u (
      user_key, first_seen_on, last_seen_on, first_platform, last_platform,
      first_login_on, first_plan_on, first_completion_on,
      logins, plans_made, plans_completed, plan_miles, completed_miles,
      map_views, sessions, pageviews, active_months, updated_at
    ) values (
      :user_key, :first_seen_on, :last_seen_on, :first_platform, :last_platform,
      :first_login_on, :first_plan_on, :first_completion_on,
      :logins, :plans_made, :plans_completed, :plan_miles, :completed_miles,
      :map_views, :sessions, :pageviews, cast(:active_months as integer[]), :updated_at
    )
    on conflict (user_key) do update set
      first_seen_on = least(u.first_seen_on, excluded.first_seen_on),
      last_seen_on = greatest(u.last_seen_on, excluded.last_seen_on),
      first_platform = case when excluded.first_seen_on < u.first_seen_on
                            then excluded.first_platform else u.first_platform end,
      last_platform = case when excluded.last_seen_on >= u.last_seen_on
                           then excluded.last_platform else u.last_platform end,
      first_login_on = least(u.first_login_on, excluded.first_login_on),
      first_plan_on = least(u.first_plan_on, excluded.first_plan_on),
      first_completion_on = least(u.first_completion_on, excluded.first_completion_on),
      logins = u.logins + excluded.logins,
      plans_made = u.plans_made + excluded.plans_made,
      plans_completed = u.plans_completed + excluded.plans_completed,
      plan_miles = u.plan_miles + excluded.plan_miles,
      completed_miles = u.completed_miles + excluded.completed_miles,
      map_views = u.map_views + excluded.map_views,
      sessions = u.sessions + excluded.sessions,
      pageviews = u.pageviews + excluded.pageviews,
      active_months = (
        select array_agg(distinct m order by m) from unnest(u.active_months || excluded.active_months) as m
      ),
      updated_at = excluded.updated_at
    """
)


def _update_users(db: Session, key: str, rows: list[dict]) -> None:
    """Fold newly stored rows into this hiker's User-table row.

    Only rows the insert actually stored arrive here, so a resend never counts
    twice. Done at ingest rather than by the rollup because these are lifetime
    totals, and the raw rows they come from are deleted after six months.
    """
    counts: dict[str, float] = defaultdict(float)
    firsts: dict[str, date] = {}
    for row in rows:
        kind, day = row["event"], row["local_date"]
        if kind == UsageEvent.user_login.value:
            counts["logins"] += 1
            firsts["login"] = min(firsts.get("login", day), day)
        elif kind == UsageEvent.hike_plan_made.value:
            counts["plans_made"] += 1
            counts["plan_miles"] += row["miles"] or 0
            firsts["plan"] = min(firsts.get("plan", day), day)
        elif kind == UsageEvent.hike_plan_completed.value:
            counts["plans_completed"] += 1
            counts["completed_miles"] += row["miles"] or 0
            firsts["completion"] = min(firsts.get("completion", day), day)
        elif kind == UsageEvent.map_screen_viewed.value:
            counts["map_views"] += 1
        elif kind == UsageEvent.session.value:
            counts["sessions"] += 1
            counts["pageviews"] += row["pageviews"] or 0

    earliest = min(rows, key=lambda row: row["local_date"])
    latest = max(rows, key=lambda row: row["local_date"])
    months = sorted({_yyyymm(row["local_date"]) for row in rows})
    now = utc_now()

    values = {
        "user_key": key,
        "first_seen_on": earliest["local_date"],
        "last_seen_on": latest["local_date"],
        "first_platform": earliest["platform"],
        "last_platform": latest["platform"],
        "first_login_on": firsts.get("login"),
        "first_plan_on": firsts.get("plan"),
        "first_completion_on": firsts.get("completion"),
        "logins": int(counts["logins"]),
        "plans_made": int(counts["plans_made"]),
        "plans_completed": int(counts["plans_completed"]),
        "plan_miles": counts["plan_miles"],
        "completed_miles": counts["completed_miles"],
        "map_views": int(counts["map_views"]),
        "sessions": int(counts["sessions"]),
        "pageviews": int(counts["pageviews"]),
        "active_months": months,
        "updated_at": now,
    }
    db.execute(_UPSERT_USER, values)


@router.post("", response_model=UsageBatchAck, status_code=status.HTTP_202_ACCEPTED)
def receive_usage_events(
    payload: UsageBatchIn,
    current_user: Profile | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
) -> UsageBatchAck:
    """Store one batch of usage events from a phone.

    202 rather than 201: what was accepted is counted, not created as anything
    the caller can come back for. Idempotent on each event's `id`, so the
    outbox's resend after a lost response stores nothing twice. 202 even when
    every row was refused: the phone drops the batch either way, and the
    counts below are where the refusal is recorded.
    """
    today = utc_now().date()
    events, outcomes = _sort_rows(payload.events, today)

    linked = payload.identified and current_user is not None and bool(settings.analytics_user_key_secret)
    key = user_key(settings.analytics_user_key_secret, current_user.id) if linked else None
    account_id = current_user.id if linked else None

    stored_ids: set[str] = set()
    if events:
        public_keys = _public_keys(db, {month_start(event.local_date) for event in events})
        rows = [_row(event, today=today, key=key, account_id=account_id, public_keys=public_keys) for event in events]
        stored_ids = set(
            db.execute(
                insert(AnalyticsEvent.__table__)
                .values(rows)
                .on_conflict_do_nothing(index_elements=["id"])
                .returning(AnalyticsEvent.__table__.c.id)
            ).scalars()
        )
        for row in rows:
            outcome = IntakeOutcome.stored if row["id"] in stored_ids else IntakeOutcome.duplicate
            outcomes[(row["app_version"] or "", outcome)] += 1
        if key is not None and stored_ids:
            _update_users(db, key, [row for row in rows if row["id"] in stored_ids])
    _count_intake(db, today, outcomes)
    db.commit()

    return UsageBatchAck(
        accepted=len(stored_ids),
        duplicates=sum(count for (_, outcome), count in outcomes.items() if outcome == IntakeOutcome.duplicate),
        refused=sum(count for (_, outcome), count in outcomes.items() if outcome in _REFUSED),
    )
