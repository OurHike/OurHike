"""The wire shape of `POST /usage-events` (#1902, features/EVENTING.md).

**Unlike app/schemas/app_failure.py, this refuses rather than truncates.** An
app-failure report is somebody asking to be heard, and losing one to a strict
schema gets the priority backwards. A usage event is the opposite: the first
thing dropped and the last thing sent (EVENTING.md §1 rule 4), so a batch that
does not match the registry costs nothing worth keeping, while one that is
let through is how free text, an unregistered key or a coordinate in the wrong
field gets stored. Every field is closed: `extra="forbid"`, enums for the
names, patterns for the two strings, ranges for the numbers.

THE TWO THINGS A CLIENT CANNOT DO WITH THIS SCHEMA

- **Name an account.** There is no account field. A row is linked to an
  account only when the batch says `identified` AND carries a valid token,
  and then the server reads the account from the token (app/routers/
  analytics.py) - a phone can say "this is me" but never "this is somebody".
- **Send a place as text.** A club is an id from a closed alphabet, and the
  only coordinates are the `fix`, which is sealed on arrival and never stored
  in the clear.

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
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.analytics import SessionLength, UsageEvent, UsagePlatform
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
CLUB_NOT_RECORDED = "_unrecorded"
ClubId = Annotated[str, Field(pattern=r"^(_unrecorded|[A-Za-z0-9][A-Za-z0-9._-]{0,63})$")]

# Clubs' shares must add up to one event. Floating point and the phone's own
# rounding of mile splits are allowed this much slack and no more.
SHARE_TOLERANCE = 0.02

_PLAN_EVENTS = (UsageEvent.hike_plan_made, UsageEvent.hike_plan_completed)


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
    app_version: str | None = Field(default=None, max_length=40, pattern=r"^[0-9A-Za-z][0-9A-Za-z.+_-]*$")

    week_first: bool = False
    month_first: bool = False
    ever_first: bool = False
    club_firsts: list[ClubId] = Field(default_factory=list, max_length=MAX_CLUBS_PER_EVENT)

    clubs: dict[ClubId, FiniteFloat] | None = Field(default=None, max_length=MAX_CLUBS_PER_EVENT)
    miles: FiniteFloat | None = Field(default=None, ge=0, le=MAX_PLAN_MILES)

    pageviews: int | None = Field(default=None, ge=0, le=10_000)
    session_length: SessionLength | None = None

    fix: FixIn | None = None

    @model_validator(mode="after")
    def _fields_belong_to_their_event(self) -> UsageEventIn:
        """A field on the wrong event is a client bug, and storing it would
        make a metric mean two things. Refused by name."""
        if self.event is not UsageEvent.session and (self.pageviews is not None or self.session_length is not None):
            raise ValueError("pageviews and session_length belong to session events only")
        if self.event not in _PLAN_EVENTS and self.miles is not None:
            raise ValueError("miles belongs to hike plan events only")
        if self.clubs is not None:
            if not self.clubs:
                raise ValueError("clubs is null when the event is about no trail, never an empty map")
            if any(not (0 < share <= 1) for share in self.clubs.values()):
                raise ValueError("each club's share is above 0 and at most 1")
            if not math.isclose(sum(self.clubs.values()), 1.0, abs_tol=SHARE_TOLERANCE):
                raise ValueError("clubs' shares add up to one event")
        if len(set(self.club_firsts)) != len(self.club_firsts):
            raise ValueError("club_firsts names each club once")
        return self


class UsageBatchIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # The hiker said yes to linking their account (the split consent, poll
    # 2026-10-27). Honoured only alongside a valid token; ignored without one.
    identified: bool = False
    events: list[UsageEventIn] = Field(min_length=1, max_length=MAX_EVENTS_PER_BATCH)

    @model_validator(mode="after")
    def _ids_are_unique(self) -> UsageBatchIn:
        if len({event.id for event in self.events}) != len(self.events):
            raise ValueError("each event id appears once in a batch")
        return self


class UsageBatchAck(BaseModel):
    """How many rows were new and how many were resends of rows already held.

    Deliberately says nothing else - not whether the batch was linked to an
    account, not whether a fix was sealed - because the phone does nothing
    differently either way, and an acknowledgement is not a place to confirm
    facts about the database to whoever sent it.
    """

    accepted: int
    duplicates: int
