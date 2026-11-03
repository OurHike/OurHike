"""Pydantic request/response models for the challenge routes (#1780).

See app/routers/trail_challenges.py for the routes and features/CHALLENGES.md
for the design. Named `trail_challenge` because `challenge` already means
proof-of-work in this backend (app/core/challenge.py).
"""

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from app.core.time import UtcDatetime
from app.core.trail_challenge import CHALLENGE_COUNT_FLOOR, ID_MAX_CHARS, ID_PATTERN
from app.models.trail_challenge import TagHow
from app.schemas.common import EmailAddress

ChallengeId = Annotated[str, StringConstraints(pattern=ID_PATTERN, max_length=ID_MAX_CHARS)]
ItemId = Annotated[str, StringConstraints(pattern=ID_PATTERN, max_length=ID_MAX_CHARS)]

#: One entry names at most this many items. @unvalidated: picked as five
#: times the ATC's list, the only challenge that exists - 100 items in
#: pipeline/reference/challenges/atc/ (counted 2026-10-01: the PDF's 97
#: lines and the three mystery items its _README describes) - so that no
#: real list meets it and a runaway client does. What would settle it: the
#: longest list a club actually publishes.
ENTRY_MAX_ITEMS = 500

#: @unvalidated: long enough for any postal address anybody writes on an
#: envelope (four or five lines), short enough that the column cannot become a
#: free-text channel. Nobody has measured real addresses against it.
MAILING_ADDRESS_MAX_CHARS = 1000

ENTRY_NAME_MAX_CHARS = 200


def _blank_is_absent(value: Any) -> Any:
    """An empty or whitespace-only field is a field the hiker left empty.

    A form sends `""` for a box nobody typed in. Treating that as an address
    would 422 an entry over an email box the hiker never touched, and would
    count as "contact details given" on a finished notice that has none.
    """
    if isinstance(value, str) and value.strip() == "":
        return None
    return value


class ChallengeTagCreate(BaseModel):
    """One tag, as the outbox sends it: item id, authored time, `gps`/`hand`.

    That is all of it, and principle 6 is why - no position, no photo, no
    register line ever leaves the phone.
    """

    # The outbox idempotency key. A UUID rather than a string for report.py's
    # reason (#265): it becomes a primary key, and `{ID}` and `{id}` must not
    # be two different rows.
    id: uuid.UUID
    challenge_id: ChallengeId
    item_id: ItemId
    how: TagHow
    authored_at: datetime

    @field_validator("authored_at")
    @classmethod
    def _reject_future_authoring(cls, value: datetime) -> datetime:
        # schemas/report.py's rule and its five minutes: phone clocks drift,
        # so a small lead is skew rather than tampering, and a tag dated next
        # week is neither.
        skew = timedelta(minutes=5)
        compared = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
        if compared > datetime.now(timezone.utc) + skew:
            raise ValueError("authored_at cannot be in the future")
        return value


class ChallengeTagOut(BaseModel):
    """A tag as stored.

    No `late` flag: one here told any signed-in caller, by binary search on
    `authored_at`, whether a challenge id was owned and when it closed - and
    every probe was a tag counted in that club's numbers (review, 2026-09-30).
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    challenge_id: str
    item_id: str
    how: TagHow
    authored_at: UtcDatetime
    received_at: UtcDatetime


class ChallengeEntryCreate(BaseModel):
    """What the finish screen sends: an entry, or a finished notice.

    **An entry** (`finished_only` false) carries a name, at least one way to
    reach the hiker, and the items they tagged - what the club's own email
    form collects today.

    **A finished notice** (`finished_only` true) is the no-reward finish
    screen's "Let the club know you finished": a name and nothing else. An
    email or address on one is refused rather than dropped, so "just tell
    them" can never carry contact details the hiker did not mean to send - a
    422 is a bug the client fixes, where a silently stored address is a
    disclosure nobody notices. Its item list is stored empty whatever is sent,
    because the design gives the notice a name and a date only.

    `consented` has to be `true` on both. The form does not send without it,
    and a request claiming otherwise is refused rather than stored as an
    entry nobody agreed to.
    """

    id: uuid.UUID
    #: The web domain of the org the hiker's finish screen named, from the
    #: published list a maintainer reviewed (pipeline/reference/challenges/
    #: publishers.json). The route takes the entry only when the club that
    #: owns the challenge id has proved this domain - see `send_entry`.
    org_domain: Annotated[
        str, StringConstraints(strip_whitespace=True, to_lower=True, min_length=3, max_length=253, pattern=r"^[A-Za-z0-9.-]+$")
    ]
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=ENTRY_NAME_MAX_CHARS)]
    email: EmailAddress | None = None
    mailing_address: Annotated[str, StringConstraints(strip_whitespace=True, max_length=MAILING_ADDRESS_MAX_CHARS)] | None = None
    item_ids: list[ItemId] = Field(default_factory=list, max_length=ENTRY_MAX_ITEMS)
    consented: bool
    finished_only: bool = False

    @field_validator("email", "mailing_address", mode="before")
    @classmethod
    def _blank_is_absent(cls, value: Any) -> Any:
        return _blank_is_absent(value)

    @field_validator("item_ids")
    @classmethod
    def _each_item_once(cls, value: list[str]) -> list[str]:
        # Order kept, repeats dropped: the list is the hiker's, and a club
        # counting 26 items where 25 were tagged is a drawing entered on a
        # number nobody walked.
        return list(dict.fromkeys(value))

    @field_validator("consented")
    @classmethod
    def _consent_is_not_optional(cls, value: bool) -> bool:
        if value is not True:
            raise ValueError("an entry is sent only with the hiker's consent")
        return value

    @model_validator(mode="after")
    def _an_entry_or_a_notice(self) -> "ChallengeEntryCreate":
        if self.finished_only:
            if self.email is not None or self.mailing_address is not None:
                raise ValueError("a finished notice carries a name only - leave out the email and mailing address")
            self.item_ids = []
            return self
        if self.email is None and self.mailing_address is None:
            raise ValueError("an entry needs an email address or a mailing address, so the club can reach you")
        if not self.item_ids:
            raise ValueError("an entry lists at least one tagged place")
        return self


class ChallengeEntryOut(BaseModel):
    """The entry as stored, back to the hiker who sent it. Nobody else reads
    this shape: the club reads entries only as the CSV."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    challenge_id: str
    name: str
    email: str | None
    mailing_address: str | None
    item_ids: list[str]
    finished_only: bool
    consented_at: UtcDatetime
    sent_at: UtcDatetime


class ClubChallengeUpsert(BaseModel):
    """What the console saves.

    `definition` is the reviewed file's shape and is checked only as far as
    this backend reads it (routers/trail_challenges.py). `takes_entries`
    left out keeps whatever the row already says, off for a new row.
    """

    definition: dict[str, Any]
    takes_entries: bool | None = None


class ChallengeWindowOut(BaseModel):
    opens: date | None = None
    closes: date | None = None


class ClubChallengeOut(BaseModel):
    """One saved challenge, whole - the console's own copy, for its admins."""

    model_config = ConfigDict(from_attributes=True)

    challenge_id: str
    definition: dict[str, Any]
    window_closes: date | None
    takes_entries: bool
    pr_url: str | None
    updated_at: UtcDatetime


class ClubChallengeSummary(BaseModel):
    """One row of the console's Challenges list: the challenge and its counts.

    `hikers_in` is null below `hikers_in_floor` rather than a small number -
    see `CHALLENGE_COUNT_FLOOR`. `finished` has no floor: every finisher is a
    row the same admin already reads by name in the CSV, so the count tells
    them nothing the file does not.
    """

    challenge_id: str
    name: str
    status: str
    window: ChallengeWindowOut
    takes_entries: bool
    pr_url: str | None
    updated_at: UtcDatetime
    # The saved definition, so the console can show and edit it from the
    # list without a second read. Admins only, like the row it comes from.
    definition: dict[str, Any]
    hikers_in: int | None
    hikers_in_floor: int = CHALLENGE_COUNT_FLOOR
    finished: int


class ChallengeCountsOut(BaseModel):
    """What a club may know about who is walking its challenge: counts, never names.

    `hikers_in` is null while fewer than `hikers_in_floor` distinct hikers
    stand behind it. There is no count of tags made after closing: the club
    sets the closing date and can re-save it, and two reads a day apart
    differenced one hiker's late day out of a floored number (review,
    2026-09-30).
    """

    hikers_in: int | None
    hikers_in_floor: int = CHALLENGE_COUNT_FLOOR
    finished: int


class ChallengePublishOut(BaseModel):
    pull_request: str | None
    detail: str
