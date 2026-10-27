"""The wire shape of `POST /usage-events` (#1902, features/EVENTING.md).

**Unlike app/schemas/app_failure.py, this refuses rather than truncates.** An
app-failure report is somebody asking to be heard, and losing one to a strict
schema gets the priority backwards. A usage event is the opposite: the first
thing dropped and the last thing sent (EVENTING.md §1 rule 4), so a row that
does not match the registry costs nothing worth keeping, while one that is
let through is how free text, an unregistered key or a coordinate in the wrong
field gets stored. Every field is closed: `extra="forbid"`, enums for the
names, patterns for the two strings, ranges for the numbers.

**Refused one ROW at a time, not one batch.** `UsageBatchIn.events` is taken
as raw objects and each is checked against `UsageEventIn` by the route, so a
row from a phone whose clock jumped costs that row and not the 199 sent with
it. Refused rows are counted (`analytics_intake`) - the phone keeps no copy,
so that count is the only sign a release broke something.

THE THREE THINGS A CLIENT CANNOT DO WITH THIS SCHEMA

- **Name an account.** There is no account field. A row is linked to an
  account only when the batch says `identified` AND carries a valid token,
  and then the server reads the account from the token (app/routers/
  analytics.py) - a phone can say "this is me" but never "this is somebody".
- **Send a place as text.** A club is an id from a closed alphabet, and the
  only coordinates are the `fix`, which is sealed on arrival and never stored
  in the clear.
- **Report a payment.** A `support_chosen` row from a phone says $0 or is
  refused; a paid level is counted only from Stripe's own confirmation
  (app/core/analytics_support.py).

The caps are @unvalidated - picked as comfortably above anything the client
sends, not measured: 200 rows a batch is EVENTING.md §8's outbox cap, 12
clubs on one event is more than any plan crosses (the A.T. has 30 clubs over
2,197.5 miles, client/src/lib/clubSections.ts), and 5,000 miles is longer than
any trail this app draws. What would settle them is a month of real batches.
"""

from __future__ import annotations

import math
import uuid
from datetime import date
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.analytics import LEVEL_ONLY_EVENTS, SessionLength, UsageEvent, UsagePlatform
from app.schemas.common import FiniteFloat

MAX_EVENTS_PER_BATCH = 200
MAX_CLUBS_PER_EVENT = 12
MAX_PLAN_MILES = 5000.0

# A club as the phone names it: ATC's acronym for an A.T. section (`NYNJTC`,
# `GATC`), an organization's slug elsewhere. A closed alphabet with no spaces,
# so a trail name or a sentence cannot ride in on it.
#
# `_unrecorded` is the one reserved value: an event on a stretch of A.T. whose
# club ATC's own centreline does not name (38.5 miles, 1.90%, measured by
# pipeline/export_club_sections.py, #594). It is a club-shaped answer to
# "which club" that says "not recorded" rather than guessing, and it is not
# the same as no club at all, which is an event that was not about a trail.
#
# At most 16 characters. The ATC acronyms in this repository's tests and
# golden batch run to six (`NYNJTC`, `AMC-DV`), so the cap leaves room for an
# organization's slug while keeping a club id too short to carry a sentence.
CLUB_NOT_RECORDED = "_unrecorded"
ClubId = Annotated[str, Field(pattern=r"^(_unrecorded|[A-Za-z0-9][A-Za-z0-9._-]{0,15})$")]

# A version as the phone's build stamps it: semver, with an optional
# pre-release (`1.5.0`, `1.5.0-beta.2`), and nothing else - no build metadata,
# no spaces, no sentence. VERSION_BODY is the pattern without its anchors, for
# app/routers/analytics.py, which matches it with `re.fullmatch`: Python's `$`
# also matches before a trailing newline, so `^...$` with `re.match` would
# let "1.4.0\n" through.
VERSION_BODY = r"[0-9]{1,4}\.[0-9]{1,4}\.[0-9]{1,4}(?:-[0-9A-Za-z.]{1,24})?"
VERSION_PATTERN = rf"^{VERSION_BODY}$"

# Clubs' shares must add up to one event. Floating point and the phone's own
# rounding of mile splits are allowed this much slack and no more - and the
# route then divides every share by the row's own sum, so the slack is never
# stored (app/routers/analytics.py `normalised_shares`).
SHARE_TOLERANCE = 0.02

_PLAN_EVENTS = (UsageEvent.hike_plan_made, UsageEvent.hike_plan_completed)

# The only support level a phone may report: $0, counted when it is chosen.
# A paid level is counted when Stripe confirms the payment, by the server
# (app/core/analytics_support.py) - a phone saying "$60" is a claim nobody
# has paid, so it is refused (the maintainer, poll 2026-10-27: "when paid,
# $0 when chosen").
PHONE_SUPPORT_CENTS = 0


class FixIn(BaseModel):
    """The phone's GPS fix, as the map already held it. Sealed on arrival."""

    model_config = ConfigDict(extra="forbid")

    lat: FiniteFloat = Field(ge=-90, le=90)
    lon: FiniteFloat = Field(ge=-180, le=180)
    accuracy_m: FiniteFloat | None = Field(default=None, ge=0, le=10_000)


class UsageEventIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    event: UsageEvent
    local_date: date
    platform: UsagePlatform
    app_version: str | None = Field(default=None, max_length=40, pattern=VERSION_PATTERN)

    week_first: bool = False
    month_first: bool = False
    ever_first: bool = False
    club_firsts: list[ClubId] = Field(default_factory=list, max_length=MAX_CLUBS_PER_EVENT)
    kind_month_first: bool = False
    month_returning: bool = False
    signed_in: bool = False

    clubs: dict[ClubId, FiniteFloat] | None = Field(default=None, max_length=MAX_CLUBS_PER_EVENT)
    miles: FiniteFloat | None = Field(default=None, ge=0, le=MAX_PLAN_MILES)

    pageviews: int | None = Field(default=None, ge=0, le=10_000)
    session_length: SessionLength | None = None

    fix: FixIn | None = None

    support_cents: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _fields_belong_to_their_event(self) -> UsageEventIn:
        """A field on the wrong event is a client bug, and storing it would
        make a metric mean two things. Refused by name."""
        if self.event is not UsageEvent.session and (self.pageviews is not None or self.session_length is not None):
            raise ValueError("pageviews and session_length belong to session events only")
        if self.event is UsageEvent.session and (self.pageviews is None or self.session_length is None):
            # The phone always sends both; a session without its length would
            # make "session lengths add up to sessions" false for every month.
            raise ValueError("a session carries its pageviews and its length")
        if self.event not in _PLAN_EVENTS and self.miles is not None:
            raise ValueError("miles belongs to hike plan events only")
        if self.clubs is not None:
            if not self.clubs:
                raise ValueError("clubs is null when the event is about no trail, never an empty map")
            if any(not (0 < share <= 1) for share in self.clubs.values()):
                raise ValueError("each club's share is above 0 and at most 1")
            if not math.isclose(sum(self.clubs.values()), 1.0, abs_tol=SHARE_TOLERANCE):
                raise ValueError("clubs' shares add up to one event")
        if self.event in LEVEL_ONLY_EVENTS:
            self._level_only()
        elif self.support_cents is not None:
            raise ValueError("support_cents belongs to support_chosen events only")
        if len(set(self.club_firsts)) != len(self.club_firsts):
            raise ValueError("club_firsts names each club once")
        if self.month_returning and not self.month_first:
            raise ValueError("month_returning rides on the month's first row only")
        if self.ever_first and not (self.month_first and self.week_first) or (self.ever_first and self.month_returning):
            # A phone's first row ever is its first of the week and the month,
            # and cannot have been here last month. A row claiming otherwise
            # would count one phone twice in new + returning + back-again.
            raise ValueError("ever_first is a first-of-the-week and -month row that is not returning")
        return self

    def _level_only(self) -> None:
        """A support choice carries its level and nothing about who chose it.

        "The level only" (the maintainer, poll 2026-10-27): no fix, no club,
        no heartbeat flag, not even `signed_in` - a $0 answer beside "this
        phone's first row ever" or "signed in" says more about the hiker than
        the count needs. Refused rather than stripped, as everything here is.
        """
        if self.support_cents != PHONE_SUPPORT_CENTS:
            raise ValueError("a phone counts only the $0 answer; a paid level is counted when the payment is confirmed")
        if self.fix is not None or self.clubs is not None or self.club_firsts:
            raise ValueError("a support choice carries no position and no club")
        flags = (self.week_first, self.month_first, self.ever_first, self.kind_month_first, self.month_returning, self.signed_in)
        if any(flags):
            raise ValueError("a support choice carries no heartbeat flag and no signed-in flag")


class UsageBatchIn(BaseModel):
    """The envelope. Its rows are checked one by one by the route."""

    model_config = ConfigDict(extra="forbid")

    # The hiker said yes to linking their account (the split consent, poll
    # 2026-10-27). Honoured only alongside a valid token; ignored without one.
    identified: bool = False
    # Raw objects, each validated against `UsageEventIn` by the route so a bad
    # one is refused alone. The cap is still the envelope's: over it, the whole
    # batch is refused, because no phone sends one.
    events: list[Any] = Field(min_length=1, max_length=MAX_EVENTS_PER_BATCH)


class UsageBatchAck(BaseModel):
    """How many rows were new, how many were resends, how many were refused.

    Deliberately says nothing else - not whether the batch was linked to an
    account, not whether a fix was sealed, not why a row was refused - because
    the phone does nothing differently either way, and an acknowledgement is
    not a place to confirm facts about the database to whoever sent it.
    """

    accepted: int
    duplicates: int
    refused: int
