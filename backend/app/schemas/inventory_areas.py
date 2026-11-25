"""Request and response models for a club's survey areas and claims.

#1988 — Priority areas are sections scored by the records in them, and a
claim is a day a volunteer means to walk one. features/STRUCTURE_INVENTORY.md
is the design; `app/routers/inventory_areas.py` says how each field is
computed.

**What a claim says about its volunteer is a first name and nothing else.**
SPEC.md's endpoint list: "claims (walk_on, first name only)". Another
volunteer reading the coverage page learns that somebody called Pat means to
walk a section on Saturday. They do not learn who Pat is, and they get no id
to look Pat up by. Only the volunteer's own claims carry the claim's id,
because only they can release it.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.core.time import UtcDatetime

#: The three answers the coverage map colours by, worst first.
Need = Literal["none_in_a_year", "under_3_in_90", "covered"]


class AreaClaimOut(BaseModel):
    walk_on: date
    #: The first word of the name the volunteer typed on the club's waiver,
    #: or null when that name is blank.
    first_name: str | None
    #: Whether this claim is the caller's own.
    mine: bool
    #: The claim's id, present only on the caller's own claims.
    id: str | None = None


class AreaOut(BaseModel):
    section_id: str
    name: str
    start_anchor: str | None
    end_anchor: str | None
    miles: float | None
    #: Records in the club's coverage window (90 days unless the club changed
    #: it), counted by the rule in `inventory_areas.COUNTED_REVIEW_STATES`.
    records_90d: int
    #: The newest counted record's `captured_at`, at any age. Null when the
    #: section has none.
    last_record_at: UtcDatetime | None
    need: Need
    #: Current claims only (`walk_on` is today or later, not released),
    #: soonest first.
    claims: list[AreaClaimOut]


class ClaimCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    section_id: str
    walk_on: date


class ClaimOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    section_id: str
    walk_on: date
    claimed_at: UtcDatetime
    released_at: UtcDatetime | None
