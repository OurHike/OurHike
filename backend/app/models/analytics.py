"""The usage-measurement tables (#1902, ../../../features/EVENTING.md).

Six things a hiker does are counted - installing the app, signing in, making
a hike plan, completing one, viewing the map, and a session with its
pageviews - and every one of them arrives at `POST /usage-events`
(app/routers/analytics.py) as one row of `analytics_events`.

WHAT THE MAINTAINER DECIDED, AND WHAT IT REVERSED

EVENTING.md's first design sent no identifier and no geography at all. On
2026-10-27, across two polls answered against drawn pages, the maintainer
chose instead to keep the account id and the phone's GPS fix with each event,
**encrypted and masked**: encrypted, because both travel only inside
`sealed`, which this backend can write and cannot read
(app/core/analytics_seal.py); masked, because everything a report reads is a
plain column that names nobody - a keyed hash of the account (`user_key`), a
0.1-degree square (`area_lat`/`area_lon`), and the club whose trail the event
was about. #1902 carries both polls, option by option.

THE TWO KINDS OF ROW

Counts are on by default and need no account. Attaching the account is asked
once after sign-in (the "split" consent, poll 2026-10-27). So a row either
carries a `user_key` - the hiker said yes - or it does not, and a row without
one says nothing about who sent it. What a no-key row still carries are the
phone's own answers to "first time this week / month / ever" (EVENTING.md
§2), which is what keeps the total of active devices exact for hikers who
said no.

RETENTION

Raw rows are kept for the current month and the six before it, then the
nightly rollup (app/core/analytics_rollup.py) deletes a month's rows - and
only once that month has been closed into `analytics_monthly`. The keys that
seal a month are derived from one secret and the month's name, so a deleted
row is the only thing that ends a position's readability: that is the
maintainer's "not perfect, but a little better" (poll 2026-10-27), and
EVENTING.md says so where a reader deciding whether to trust it will look.

Every datetime column follows the naive-UTC convention app/models/profile.py
documents; the days are calendar dates, and `local_date` is the PHONE's
calendar, because "which month was this" is the hiker's month, not UTC's.
"""

import enum
import uuid

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    Float,
    Integer,
    LargeBinary,
    Numeric,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY

from app.core.time import utc_now
from app.db.base import Base


class UsageEvent(str, enum.Enum):
    """The six things counted, and nothing else - the registry EVENTING.md §3
    asks for. `POST /usage-events` refuses any other name, which is what stops
    "no free text" being a rule everyone remembers until the afternoon somebody
    interpolates a trail name into an event key."""

    app_installed = "app_installed"
    user_login = "user_login"
    hike_plan_made = "hike_plan_made"
    hike_plan_completed = "hike_plan_completed"
    map_screen_viewed = "map_screen_viewed"
    session = "session"


class UsagePlatform(str, enum.Enum):
    ios = "ios"
    android = "android"
    web = "web"


class SessionLength(str, enum.Enum):
    """A session's length in four buckets rather than in seconds: an exact
    duration next to a date and an area is a sharper fingerprint than anything
    a monthly report needs (EVENTING.md §3's argument for bucketing)."""

    under_1m = "under_1m"
    m1_to_5 = "m1_to_5"
    m5_to_20 = "m5_to_20"
    over_20m = "over_20m"


class SealState(str, enum.Enum):
    """What happened to the part of a row that had to be sealed.

    `no_key` is the honest third state: the row arrived with a fix or an
    account to seal, and no public key had been published for its month
    (`analytics_seal_keys`), so both were thrown away rather than kept in the
    clear. The count of these is on the report's data-health line, because a
    month of `no_key` rows is a month nobody ran `scripts/analytics_keys.py
    publish` for.
    """

    none = "none"
    sealed = "sealed"
    no_key = "no_key"


class MonthStatus(str, enum.Enum):
    """`provisional` while the month can still change, `closed` once frozen.

    Closing waits `CLOSE_AFTER_DAYS` past the month's end
    (app/core/analytics_rollup.py) because this app is offline-first: a phone
    that spent the last week of October on a ridge uploads in November, and a
    snapshot taken on 1 November would undercount October every time.
    """

    provisional = "provisional"
    closed = "closed"


class AnalyticsEvent(Base):
    __tablename__ = "analytics_events"

    # Minted on the phone, so a resend after a dropped connection is the same
    # row rather than a second one - `POST /usage-events` inserts with ON
    # CONFLICT DO NOTHING on it, the outbox pattern app/routers/app_failures.py
    # uses for the same trail-side reason.
    id = Column(String(36), primary_key=True)

    # The phone's calendar day. Indexed because the rollup and the retention
    # delete both select a month of these at a time.
    local_date = Column(Date, nullable=False, index=True)
    # A date, not a time: what the rollup needs is "did this arrive after its
    # month closed", and a time of upload says when a hiker found signal.
    received_on = Column(Date, nullable=False)

    event = Column(Enum(UsageEvent, native_enum=False, length=24), nullable=False)
    platform = Column(Enum(UsagePlatform, native_enum=False, length=8), nullable=False)
    app_version = Column(String(40), nullable=True)

    # HMAC-SHA256 of the account id under a key only this backend holds
    # (app/core/analytics_seal.py `user_key`). Null on every row from a hiker
    # who has not said yes. Indexed for account deletion, which recomputes it.
    user_key = Column(String(32), nullable=True, index=True)

    # EVENTING.md §2's heartbeat, answered by the phone: the first event this
    # ISO week, this calendar month, and ever, on that device.
    week_first = Column(Boolean, nullable=False, default=False)
    month_first = Column(Boolean, nullable=False, default=False)
    ever_first = Column(Boolean, nullable=False, default=False)
    # The clubs this event was the device's FIRST of the month to touch -
    # §2's trick applied per club, so "devices active on a club's trails"
    # needs no identifier either.
    club_firsts = Column(JSON(none_as_null=True), nullable=True)

    # Which clubs the event was about, and in what share: {club: share}, the
    # shares summing to 1. A plan is split by its miles in each club ("assigned
    # by # miles specific for each club", poll 2026-10-27); a point event - a
    # map view, a session - is one club at a share of 1. Null when the event was
    # about no trail at all.
    clubs = Column(JSON(none_as_null=True), nullable=True)
    # A plan's length, so each club's planned miles are `share * miles`.
    miles = Column(Float, nullable=True)

    pageviews = Column(SmallInteger, nullable=True)
    session_length = Column(Enum(SessionLength, native_enum=False, length=10), nullable=True)

    # Whether the phone sent a fix with this event. The fix itself is in
    # `sealed`; this and the square below are what a report may read.
    has_fix = Column(Boolean, nullable=False, default=False)
    # The fix's 0.1-degree square, by its south-west corner: about 11 km of
    # latitude by 8 km of longitude at 41 N. Worked out here, at ingest, from a
    # fix that is then sealed - so the plain half and the sealed half can never
    # disagree about where a row was.
    area_lat = Column(Numeric(4, 1), nullable=True)
    area_lon = Column(Numeric(4, 1), nullable=True)

    seal = Column(Enum(SealState, native_enum=False, length=8), nullable=False, default=SealState.none)
    # The account id (rows from hikers who said yes) and the exact fix, sealed
    # to the month's public key. Nothing in this backend can open it; only
    # `scripts/analytics_keys.py open`, run with the secret, can.
    sealed = Column(LargeBinary, nullable=True)


class AnalyticsMonth(Base):
    """One row per month the rollup has computed: where it is in its life."""

    __tablename__ = "analytics_months"

    # The first day of the month.
    month = Column(Date, primary_key=True)
    status = Column(Enum(MonthStatus, native_enum=False, length=12), nullable=False)
    # Bumped when a metric's definition changes. A month closed under an old
    # definition keeps its number: its raw rows may be gone, so it cannot be
    # restated, and a new definition starts a new series instead.
    definition_version = Column(Integer, nullable=False)
    computed_at = Column(DateTime, nullable=False, default=utc_now)
    closed_at = Column(DateTime, nullable=True)
    # When retention deleted this month's raw rows. Null while they exist.
    raw_deleted_at = Column(DateTime, nullable=True)


class AnalyticsMonthly(Base):
    """The month-end table: one value per month, metric and slice.

    Exact. The fewer-than-25 mask is applied when a report is BUILT, not
    here - "a mask at runtime though. Dont mess with the data" (poll
    2026-10-27) - so the stored figures stay true and every reader applies
    the same floor (app/core/analytics_report.py `K_FLOOR`).

    `club` and `platform` are "*" on the all-clubs and all-platforms slices.
    The two are never crossed: a club broken down by platform is a cell too
    small to show at this app's scale, and a table with no such rows cannot
    be read into one.
    """

    __tablename__ = "analytics_monthly"

    month = Column(Date, primary_key=True)
    metric = Column(String(40), primary_key=True)
    club = Column(String(64), primary_key=True)
    platform = Column(String(8), primary_key=True)
    value = Column(Float, nullable=False)


class AnalyticsUser(Base):
    """The User table: aggregate figures about one hiker who said yes.

    Kept until the account is deleted (app/core/account_deletion.py), not for
    six months: these are lifetime totals, and the raw rows they came from are
    gone after six. **There is no location column, and there must not be one**
    - a per-hiker home area kept for as long as the account lives would be the
    identifier-next-to-a-place pair #252 removed from the report API, without
    even the six-month limit the raw rows have.

    Milestones are dates rather than flags, so "hikers who had ever completed a
    hike as of 31 October" is a WHERE clause on any later day - the stock a
    monthly snapshot would otherwise have to freeze at exactly the right moment.
    `active_months` (yyyymm) does the same for retention cohorts.
    """

    __tablename__ = "analytics_users"

    user_key = Column(String(32), primary_key=True)
    first_seen_on = Column(Date, nullable=False)
    last_seen_on = Column(Date, nullable=False)
    first_platform = Column(Enum(UsagePlatform, native_enum=False, length=8), nullable=False)
    last_platform = Column(Enum(UsagePlatform, native_enum=False, length=8), nullable=False)
    first_login_on = Column(Date, nullable=True)
    first_plan_on = Column(Date, nullable=True)
    first_completion_on = Column(Date, nullable=True)
    logins = Column(Integer, nullable=False, default=0)
    plans_made = Column(Integer, nullable=False, default=0)
    plans_completed = Column(Integer, nullable=False, default=0)
    plan_miles = Column(Float, nullable=False, default=0.0)
    completed_miles = Column(Float, nullable=False, default=0.0)
    map_views = Column(Integer, nullable=False, default=0)
    sessions = Column(Integer, nullable=False, default=0)
    pageviews = Column(Integer, nullable=False, default=0)
    active_months = Column(ARRAY(Integer), nullable=False, default=list)
    updated_at = Column(DateTime, nullable=False, default=utc_now)


class AnalyticsSealKey(Base):
    """The public half of each month's sealing key.

    Written by `scripts/analytics_keys.py publish`, which derives the pair
    from the maintainer's secret and the month's name and sends only this
    half. A public key opens nothing, which is the whole reason it may sit in
    a table the running backend reads.
    """

    __tablename__ = "analytics_seal_keys"

    month = Column(Date, primary_key=True)
    public_key = Column(LargeBinary(32), nullable=False)
    published_at = Column(DateTime, nullable=False, default=utc_now)


class AnalyticsOpening(Base):
    """One use of the secret: who opened which sealed rows, and why.

    Written by `scripts/analytics_keys.py open` BEFORE it decrypts anything,
    and committed first, so an opening that crashes halfway is still on the
    record. Honest about its limit: the script writes this row; somebody with
    the secret and their own code need not. It is a record kept by the
    careful, not a lock.
    """

    __tablename__ = "analytics_openings"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    opened_at = Column(DateTime, nullable=False, default=utc_now)
    opened_by = Column(String(120), nullable=False)
    reason = Column(Text, nullable=False)
    month = Column(Date, nullable=False)
    # What was asked for, in the script's own words: "event <id>",
    # "user_key <key>" or "whole month".
    selector = Column(String(120), nullable=False)
    rows_opened = Column(Integer, nullable=True)
