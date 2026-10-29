"""Eight months of phones, through the real route and the real nightly rollup (#1902).

The other analytics tests each pin one rule. This one runs them together for
long enough that the rules meet: phones install, come and go, take trips with
no signal and upload a fortnight late across a month boundary, link an account
or not - and every simulated night the rollup runs exactly as
.github/workflows/analytics-rollup.yml runs it, before that afternoon's uploads
arrive. The simulation knows the truth about every phone, so what the monthly
table says can be checked against it rather than against itself:

  - every closed month's active, new, returning and back-again phones equal the
    phones that were really active, new, back from last month or back after a
    gap - counted with no identifier, by the phones' own answers;
  - a closed month's figures never move again, and its late rows are counted
    exactly (rows held now less rows frozen at the close);
  - the oldest month's raw rows are deleted six months on and its figures stay;
  - every linked hiker's `active_months` is the months they were really active;
  - the nightly sums-that-must-hold find nothing;
  - and a month frozen past `MONTH_JUDGED_DAYS` is not judged again.

Seeded: a failure names the seed that reproduces it.
"""

from __future__ import annotations

import random
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from app.config import settings
from app.core import analytics_quality as quality
from app.core.analytics_rollup import ALL, add_months, closes_on, month_start, retention_start, run
from app.core.analytics_seal import user_key
from app.models.analytics import AnalyticsEvent, AnalyticsMonthly, AnalyticsUser
from tests.factories import make_profile, make_usage_consent
from tests.tokens import auth_headers

START = date(2026, 1, 1)
END = date(2026, 8, 31)
SECRET = "simulation-user-key-secret"
KINDS = ["map_screen_viewed", "hike_plan_made", "hike_plan_completed", "user_login"]


def _month(day: date) -> str:
    return f"{day:%Y-%m}"


def _week(day: date) -> str:
    year, week, _ = day.isocalendar()
    return f"{year}-W{week:02d}"


@dataclass
class Phone:
    """One phone, and the heartbeat it keeps (client/src/lib/usageEvents.ts)."""

    installed: date
    retires: date
    activity: float
    linked_to: str | None
    platform: str
    weeks: set = field(default_factory=set)
    months: set = field(default_factory=set)
    kinds: set = field(default_factory=set)
    ever: bool = False
    waiting: list = field(default_factory=list)
    offline_until: date | None = None

    def row(self, day: date, event: str, **extra) -> dict:
        month = _month(day)
        month_first = month not in self.months
        stamped = {
            "id": str(uuid.uuid4()),
            "event": event,
            "local_date": day.isoformat(),
            "platform": self.platform,
            "week_first": _week(day) not in self.weeks,
            "month_first": month_first,
            "ever_first": not self.ever,
            "month_returning": month_first and _month(add_months(month_start(day), -1)) in self.months,
            "kind_month_first": (month, event) not in self.kinds,
            "signed_in": self.linked_to is not None,
            **extra,
        }
        self.weeks.add(_week(day))
        self.months.add(month)
        self.kinds.add((month, event))
        self.ever = True
        return stamped


def _simulate(client, db_session, monkeypatch) -> dict:
    """Run the eight months, and hand back what really happened."""
    monkeypatch.setattr(settings, "analytics_user_key_secret", SECRET)
    clock = {"now": datetime.combine(START, time(12))}
    monkeypatch.setattr("app.routers.analytics.utc_now", lambda: clock["now"])
    random_ = random.Random(1902)

    phones = []
    for _ in range(36):
        installed = START + timedelta(days=random_.randint(0, 150))
        profile = make_profile(db_session) if random_.random() < 0.35 else None
        if profile is not None:
            # The yes, synced, without which the route links nothing.
            make_usage_consent(db_session, profile)
        phones.append(
            Phone(
                installed=installed,
                retires=installed + timedelta(days=random_.randint(25, 220)),
                activity=random_.uniform(0.08, 0.35),
                linked_to=profile.id if profile else None,
                platform=random_.choice(["ios", "android", "web"]),
            )
        )
    # The section hiker, scripted so every seed meets the hardest case: out
    # for the last week of April and in no signal until after April closed,
    # so the whole of their April arrives late.
    section_hiker = Phone(
        installed=date(2026, 4, 24),
        retires=date(2026, 4, 28),
        activity=1.0,
        linked_to=None,
        platform="android",
        offline_until=closes_on(date(2026, 4, 1)) + timedelta(days=5),
    )
    phones.append(section_hiker)

    # firsts: month -> phone -> (day its month_first row was posted, its answers)
    truth = {"active": {}, "firsts": {}, "linked_months": {}, "posted_on": {}}
    snapshots: dict[date, dict] = {}
    day = START
    while day <= END:
        # The night's run, at 10:17 UTC, before the afternoon's uploads.
        result = run(db_session, today=day, now=datetime.combine(day, time(10, 17)))
        for closed in result.closed:
            snapshots[closed] = {
                (r.metric, r.club, r.platform): r.value
                for r in db_session.query(AnalyticsMonthly).filter(AnalyticsMonthly.month == closed).all()
                if r.metric not in LATE_COUNTS
            }
        clock["now"] = datetime.combine(day, time(15))

        for phone in phones:
            if day < phone.installed:
                continue
            if day > phone.retires:
                pass  # records nothing more, but still uploads what it holds
            elif day == phone.installed:
                phone.waiting.append(phone.row(day, "app_installed"))
            if day > phone.retires or (day != phone.installed and random_.random() > phone.activity):
                pass
            else:
                for _ in range(random_.randint(1, 3)):
                    kind = random_.choice(KINDS)
                    extra = {"miles": round(random_.uniform(2, 30), 1)} if "plan" in kind else {}
                    phone.waiting.append(phone.row(day, kind, **extra))
                phone.waiting.append(phone.row(day, "session", pageviews=random_.randint(1, 9), session_length="m1_to_5"))
                if phone.offline_until is None and random_.random() < 0.08:
                    # Mostly a weekend or a week out; sometimes a section hike
                    # long enough to upload after its month has closed.
                    days_out = random_.randint(3, 18) if random_.random() < 0.8 else random_.randint(20, 40)
                    phone.offline_until = day + timedelta(days=days_out)
            if phone.offline_until is not None and day < phone.offline_until:
                continue
            phone.offline_until = None
            if not phone.waiting:
                continue
            batch, phone.waiting = phone.waiting, []
            headers = auth_headers(phone.linked_to) if phone.linked_to else {}
            response = client.post(
                "/usage-events",
                json={"identified": phone.linked_to is not None, "events": batch},
                headers=headers,
            )
            assert response.status_code == 202 and response.json()["refused"] == 0, response.json()
            for row in batch:
                row_day = date.fromisoformat(row["local_date"])
                month = month_start(row_day)
                truth["active"].setdefault(month, set()).add(id(phone))
                if row["month_first"]:
                    truth["firsts"].setdefault(month, {})[id(phone)] = (
                        day,
                        row["ever_first"],
                        row["month_returning"],
                    )
                if phone.linked_to:
                    truth["linked_months"].setdefault(phone.linked_to, set()).add(month)
                truth["posted_on"].setdefault(month, []).append(day)
        day += timedelta(days=1)

    final = run(db_session, today=END + timedelta(days=1), now=datetime.combine(END + timedelta(days=1), time(10, 17)))
    return {"truth": truth, "snapshots": snapshots, "final": final, "phones": phones}


def _value(db_session, month: date, metric: str) -> float:
    row = db_session.get(AnalyticsMonthly, (month, metric, ALL, ALL))
    return row.value if row else 0.0


def _closed_months_count_exactly_the_phones_that_were_there(db_session, simulated):
    """A closed month counts the phones whose first row of it had arrived by
    the close - and every phone that was really there is either one of those
    or one whose first row came late, which events_after_close owns."""
    truth = simulated["truth"]
    checked = 0
    for month, frozen in simulated["snapshots"].items():
        firsts = truth["firsts"].get(month, {})
        counted = {phone: answers for phone, answers in firsts.items() if answers[0] < closes_on(month)}
        assert frozen[("devices_active", ALL, ALL)] == len(counted), month
        assert frozen[("devices_new", ALL, ALL)] == sum(1 for _, new, _ in counted.values() if new), month
        assert frozen[("devices_returning", ALL, ALL)] == sum(1 for _, _, back in counted.values() if back), month
        assert frozen[("devices_back", ALL, ALL)] == sum(1 for _, new, back in counted.values() if not new and not back), month
        assert set(firsts) == truth["active"][month], f"{month:%Y-%m}: a phone was there with no first row"
        checked += 1
    assert checked >= 6, "the simulation closed fewer months than it was built to"


# The two counts a closed month still takes: rows that arrive after it closed,
# and support rows that do (counted apart from `events` since the fourth
# #1885 review, so a masked level cannot be subtracted back out).
LATE_COUNTS = ("events_after_close", "support_after_close")


def _closed_months_never_move_and_count_their_late_rows_exactly(db_session, simulated):
    for month, frozen in simulated["snapshots"].items():
        later = {
            (r.metric, r.club, r.platform): r.value
            for r in db_session.query(AnalyticsMonthly).filter(AnalyticsMonthly.month == month).all()
            if r.metric not in LATE_COUNTS
        }
        assert later == frozen, f"{month:%Y-%m} moved after it closed"
        # These phones never answer the support ask, so none of its rows
        # can be late.
        assert _value(db_session, month, "support_after_close") == 0, month
        if month < retention_start(END + timedelta(days=1)):
            continue  # raw rows gone: its late count stopped with them
        late = sum(1 for day in simulated["truth"]["posted_on"][month] if day >= closes_on(month))
        assert _value(db_session, month, "events_after_close") == late, month


def _the_oldest_month_loses_its_raw_rows_and_keeps_its_figures(db_session, simulated):
    january = date(2026, 1, 1)
    assert january in simulated["snapshots"]
    held = db_session.query(AnalyticsEvent).filter(AnalyticsEvent.local_date < date(2026, 2, 1)).count()

    assert held == 0
    assert _value(db_session, january, "devices_active") == len(simulated["truth"]["active"][january])


def _every_linked_hiker_has_exactly_the_months_they_were_active(db_session, simulated):
    linked = simulated["truth"]["linked_months"]
    assert linked, "the simulation linked nobody"
    for account, months in linked.items():
        row = db_session.get(AnalyticsUser, user_key(SECRET, account))
        assert row is not None, account
        assert row.active_months == sorted(m.year * 100 + m.month for m in months)


def _the_sums_that_must_hold_hold_for_every_month(db_session, simulated):
    assert [f for f in quality.invariant_findings(db_session) if f.status == "broken"] == []


def _a_frozen_month_says_nothing_on_the_last_night(db_session, simulated):
    """Reproduced before `frozen_months`: three of these months' late-row
    warnings were re-made every night, so the tracking issue could never close."""
    last_night = END + timedelta(days=1)
    frozen = quality.frozen_months(db_session, last_night)
    every_month = quality.invariant_findings(db_session)
    assert any(f.day in frozen for f in every_month), "no frozen month has a finding to re-make, so this proves nothing"

    month_findings = [f for f in quality.run_checks(db_session, today=last_night) if quality.is_month_check(f.check_name)]

    assert [f for f in month_findings if f.day in frozen] == []


def _the_simulation_met_the_hard_cases(simulated):
    """Guards the guards: checks that pass because nothing late ever arrived
    would prove nothing about late arrivals."""
    truth = simulated["truth"]
    posted = truth["posted_on"]
    after_close = sum(1 for month, days in posted.items() for day in days if day >= closes_on(month))
    across_months = sum(1 for month, days in posted.items() for day in days if month_start(day) > month)
    phones_late = sum(
        1 for month, firsts in truth["firsts"].items() for posted_day, _, _ in firsts.values() if posted_day >= closes_on(month)
    )
    assert after_close > 0, "no row arrived after its month closed"
    assert across_months > 0, "no upload crossed a month boundary"
    assert phones_late > 0, "no phone's whole month arrived after the close"


def test_eight_months_of_phones_add_up_to_what_really_happened(client, db_session, monkeypatch):
    """One run, the things it has to get right. One test rather than one each
    so the eight months are simulated once - about twelve seconds."""
    simulated = _simulate(client, db_session, monkeypatch)

    _the_simulation_met_the_hard_cases(simulated)
    _closed_months_count_exactly_the_phones_that_were_there(db_session, simulated)
    _closed_months_never_move_and_count_their_late_rows_exactly(db_session, simulated)
    _the_oldest_month_loses_its_raw_rows_and_keeps_its_figures(db_session, simulated)
    _every_linked_hiker_has_exactly_the_months_they_were_active(db_session, simulated)
    _the_sums_that_must_hold_hold_for_every_month(db_session, simulated)
    _a_frozen_month_says_nothing_on_the_last_night(db_session, simulated)
