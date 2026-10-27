"""`POST /usage-events` - where the app's usage measurement arrives (#1902).

See ../../../features/EVENTING.md for the design and app/models/analytics.py
for what each column means. Each of these is a decision, not an oversight:

**It takes no account, and a token alone links nothing.** Counts are on by
default for everyone (the "split" consent, poll 2026-10-27), so a batch with
no token is ordinary. A row is linked to an account only when the batch says
`identified` - the hiker said yes - AND carries a valid token AND the
account's own synced preferences say yes (`measurement_linked`), and the
account then comes from the token, never from the body. **A no the account
has synced wins over what any one phone sends**: with `measurement_enabled`
off, a batch carrying that account's token is counted as `declined` and
nothing in it is stored - a second phone that never heard the hiker turn
measurement off does not get to measure them.

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

**It writes no IP address and keeps no batch.** No column holds one, nothing
here logs the request, and Uvicorn's access line for this path - which opens
with the client's address - is dropped before any handler sees it
(app/core/logs.py `DropUnloggedPaths`). A batch is momentarily linkable on
the wire - nine heartbeats in one request came from one phone - and the
claim is only that the grouping is never written (EVENTING.md §2).

**It caps what it stores, and turns a batch away rather than fill the
database.** Past `analytics_daily_row_budget` rows stored in a UTC day, or
with more rows held than `analytics_storage_ceiling_mb` allows (app/config.py,
counted by app/core/analytics_storage.py), a batch is counted as
`over_budget` unread and answered 503 with a `Retry-After`. The phone keeps a
batch a 5xx answered and sends it later (client/src/lib/usageQueue.ts
`sendUsageBatch`), so a real day that runs over arrives late rather than
going missing - up to the 200 rows a phone holds.

**It collects nothing that nothing would delete.** Six-month retention is
kept by the nightly rollup (app/core/analytics_rollup.py), so when that
job's heartbeat - the newest `analytics_months.computed_at` - is older than
`analytics_rollup_stale_days`, every batch is counted as `paused` and turned
away the same way, until the job runs again.

**What is still NOT built: a limit per sender.** There is no IP to limit by,
on purpose, and no account. So a flood of fake rows can still skew a day's
counts, and can use up its budget so that real rows wait for the next day.
It cannot reach anybody's data. Said out loud so it is noticed before it is
discovered.
"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from typing import Any, NoReturn

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.config import settings
from app.core.analytics_rollup import month_start, retention_start
from app.core.analytics_seal import month_label, seal, user_key
from app.core.analytics_storage import ROWS_HELD_SQL, ceiling_rows
from app.core.auth import get_current_user_optional
from app.core.time import utc_now
from app.db.session import get_db
from app.models.analytics import (
    LEVEL_ONLY_EVENTS,
    AnalyticsEvent,
    AnalyticsIntake,
    AnalyticsSealKey,
    IntakeOutcome,
    SealState,
    UsageEvent,
)
from app.models.preferences import UserPreferences
from app.models.profile import Profile
from app.schemas.analytics import VERSION_BODY, UsageBatchAck, UsageBatchIn, UsageEventIn

router = APIRouter(prefix="/usage-events", tags=["usage-events"])

# How long a phone is asked to wait after a batch is turned away. An hour,
# because both reasons it is turned away - the day's budget, the table's
# ceiling - clear on a scale of hours or longer, and a sooner retry would only
# be turned away again. @unvalidated: nobody has watched what phones do with it.
RETRY_AFTER_SECONDS = 3600

# The same words whichever bound was reached: the caller is told to come back
# later, and nothing about this database's size or traffic.
TURNED_AWAY = "Usage counts are not being accepted right now. Send them again later."

# A phone's calendar may run a day ahead of the server's UTC one - it is
# already tomorrow in the hiker's own day for some hours of every evening
# west of Greenwich, and the other way round east of it. One day of slack
# covers both, and anything further ahead is a wrong clock.
FUTURE_SLACK = timedelta(days=1)


def _area(degrees: float) -> float:
    """The 0.1-degree square a coordinate falls in, by its south-west corner."""
    return math.floor(degrees * 10) / 10


_REFUSED = frozenset({IntakeOutcome.invalid, IntakeOutcome.too_old, IntakeOutcome.future})
_VERSION = re.compile(VERSION_BODY)


def _version_of(raw: Any) -> str:
    """A refused row's version when it carried a readable one, for the intake count.

    `fullmatch`, never `match` with a `$`: Python's `$` also matches before a
    trailing newline, and "1.4.0\\n" is not a version this table should hold.
    """
    version = raw.get("app_version") if isinstance(raw, dict) else None
    return version if isinstance(version, str) and _VERSION.fullmatch(version) else ""


def normalised_shares(clubs: dict[str, float] | None) -> dict[str, float] | None:
    """Each club's share divided by the row's own sum, so a stored row is exactly one event.

    The schema lets a row's shares miss one by `SHARE_TOLERANCE` (0.02), for
    the phone's rounding of its mile splits. Stored as sent, that slack adds
    up: two clubs at 0.509 each is 1.018 of a plan, and a month of such rows
    puts the clubs' plans above the app's own (the nightly
    `club_plans_within_total` check, app/core/analytics_quality.py) with no
    way to correct it once the month closes. `math.fsum` so shares that
    already add up to 1.0 come back unchanged.
    """
    if not clubs:
        return None
    total = math.fsum(clubs.values())
    return {club: share / total for club, share in clubs.items()}


# Read once per batch, in one round trip, before anything in it is: how many
# rows today has stored, how many are held at all
# (app/core/analytics_storage.py), and when the nightly rollup last ran.
_INTAKE_GATE = text(
    f"""
    select
      (select coalesce(sum(rows), 0) from analytics_intake
        where received_on = :today and outcome = 'stored') as stored_today,
      ({ROWS_HELD_SQL}) as rows_held,
      (select max(computed_at) from analytics_months) as rollup_ran_at
    """
)


def _gate_outcome(db: Session, now: datetime) -> IntakeOutcome | None:
    """Why this batch must be turned away unread, or None to read it.

    The budget first: it is the bound on what a stranger can cost, and it
    holds whether or not the rollup is running.
    """
    gate = db.execute(_INTAKE_GATE, {"today": now.date()}).one()
    if gate.stored_today >= settings.analytics_daily_row_budget or gate.rows_held >= ceiling_rows():
        return IntakeOutcome.over_budget
    if gate.rollup_ran_at is None or gate.rollup_ran_at < now - timedelta(days=settings.analytics_rollup_stale_days):
        return IntakeOutcome.paused
    return None


def _synced_consent(db: Session, account: Profile | None) -> tuple[bool, bool]:
    """(measurement on, linking agreed) as the token's account last synced them to `/preferences/me`.

    No token: on, and not linked - there is no account to ask, and counts are
    on by default. A token whose account never synced: the same, because
    `measurement_linked` reads as no until it is a stored yes.
    """
    if account is None:
        return True, False
    stored = db.get(UserPreferences, account.id)
    data = stored.data if stored is not None and isinstance(stored.data, dict) else {}
    return data.get("measurement_enabled", True) is not False, data.get("measurement_linked") is True


def _turn_away(db: Session, today: date, outcome: IntakeOutcome, rows: int) -> NoReturn:
    """Count a whole batch under `outcome`, unread, and answer 503 so the phone keeps it."""
    _count_intake(db, today, Counter({("", outcome): rows}))
    db.commit()
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=TURNED_AWAY,
        headers={"Retry-After": str(RETRY_AFTER_SECONDS)},
    )


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
    if event.event in LEVEL_ONLY_EVENTS:
        # Never linked, whatever the batch says: a support choice is counted
        # by its level alone (poll 2026-10-27), so no key and no sealed
        # account - and so no User-table row moves for it either.
        key = account_id = None

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
        "clubs": normalised_shares(event.clubs),
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
        "support_cents": event.support_cents,
    }


def _yyyymm(day: date) -> int:
    return day.year * 100 + day.month


# LEAST and GREATEST skip nulls, which is exactly the rule for a milestone:
# the earliest date anybody has seen it, or none yet. The months a hiker was
# active are a set, kept sorted so a row read with psql reads as a timeline.
# `new_month` is written by the insert and never by the update: it is the
# month the rollup counts this hiker new in, and a late row must not move it
# (app/models/analytics.py says why). Part of DEFINITION_FINGERPRINTS
# (app/core/analytics_rollup.py), because `hikers_new` is counted from it.
_UPSERT_USER = text(
    """
    insert into analytics_users as u (
      user_key, first_seen_on, new_month, last_seen_on, first_platform, last_platform,
      first_login_on, first_plan_on, first_completion_on,
      logins, plans_made, plans_completed, plan_miles, completed_miles,
      map_views, sessions, pageviews, active_months, updated_on
    ) values (
      :user_key, :first_seen_on, :new_month, :last_seen_on, :first_platform, :last_platform,
      :first_login_on, :first_plan_on, :first_completion_on,
      :logins, :plans_made, :plans_completed, :plan_miles, :completed_miles,
      :map_views, :sessions, :pageviews, cast(:active_months as integer[]), :updated_on
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
      updated_on = excluded.updated_on
    """
)


def _update_users(db: Session, key: str, rows: list[dict], *, today: date) -> None:
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

    values = {
        "user_key": key,
        "first_seen_on": earliest["local_date"],
        "new_month": month_start(earliest["local_date"]),
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
        "updated_on": today,
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

    503 only when the batch was turned away whole, before a row was read -
    the one answer that tells the phone to keep it.
    """
    now = utc_now()
    today = now.date()
    turned_away = _gate_outcome(db, now)
    if turned_away is not None:
        _turn_away(db, today, turned_away, len(payload.events))

    enabled, said_yes = _synced_consent(db, current_user)
    if not enabled:
        # Counted, so a phone ignoring the switch shows up somewhere, and
        # acknowledged as refused, so it drops the rows rather than resend them.
        _count_intake(db, today, Counter({("", IntakeOutcome.declined): len(payload.events)}))
        db.commit()
        return UsageBatchAck(accepted=0, duplicates=0, refused=len(payload.events))

    events, outcomes = _sort_rows(payload.events, today)

    linked = payload.identified and said_yes and current_user is not None and bool(settings.analytics_user_key_secret)
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
        linked_rows = [row for row in rows if row["id"] in stored_ids and row["user_key"] is not None]
        if key is not None and linked_rows:
            _update_users(db, key, linked_rows, today=today)
    _count_intake(db, today, outcomes)
    db.commit()

    return UsageBatchAck(
        accepted=len(stored_ids),
        duplicates=sum(count for (_, outcome), count in outcomes.items() if outcome == IntakeOutcome.duplicate),
        refused=sum(count for (_, outcome), count in outcomes.items() if outcome in _REFUSED),
    )
