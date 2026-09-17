"""Request/response models for `/workdays` - VOLUNTEERING.md phase D (#762).

**The one rule that shapes every model here: a signup is an introduction, not
an enrolment.** `SignupState.confirmed` is set by the organization and by
nothing else, so `WorkProjectSignupCreate` has no `state` field at all - not
a defaulted one, not an optional one. A field the wire cannot carry is a
field no client can send by accident.
"""

from __future__ import annotations

from datetime import date, timedelta

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from app.core.time import UtcDatetime
from app.models.work_project import ProjectSource, ProjectStatus, SignupMode, SignupState
from app.schemas.common import FiniteFloat, NoteText

# The organization's own reply. `interested` is absent because it is what a
# signup already is - replying "interested" says nothing the volunteer does
# not already see, and offering it as a reply would let an org think it had
# answered somebody when it had not.
REPLY_STATES = (SignupState.confirmed, SignupState.waitlisted, SignupState.declined)


class WorkProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    club_id: str
    title: str
    description: str | None
    starts_on: date
    ends_on: date
    meet_point: str | None
    mile: float | None
    lat: float | None
    lon: float | None
    status: ProjectStatus
    cap: int | None
    source: ProjectSource
    signup_mode: SignupMode
    signup_contact: str | None
    signup_url: str | None
    # How many hands are up, and how many the org has confirmed. Two numbers
    # rather than one, because a cap applies to the confirmed count and a
    # volunteer reading "12 of 10" on an uncapped interest list would take it
    # for a queue position.
    interested_count: int = 0
    confirmed_count: int = 0


class WorkProjectCreate(BaseModel):
    title: str
    starts_on: date
    ends_on: date | None = None
    description: NoteText | None = None
    meet_point: str | None = None
    mile: FiniteFloat | None = None
    lat: FiniteFloat | None = None
    lon: FiniteFloat | None = None
    cap: int | None = None
    source: ProjectSource = ProjectSource.ourhike
    signup_mode: SignupMode = SignupMode.in_app
    signup_contact: str | None = None
    signup_url: str | None = None

    @model_validator(mode="after")
    def _a_signup_has_to_go_somewhere(self) -> WorkProjectCreate:
        # A single-day workday is the common case, so `ends_on` defaults to
        # `starts_on` rather than being typed twice.
        if self.ends_on is None:
            self.ends_on = self.starts_on
        if self.ends_on < self.starts_on:
            raise ValueError("a workday cannot end before it starts")

        # A mirrored project's whole point is that the organization's own
        # system is authoritative, so it must say where that is. Without a
        # URL the screen would render "sign up on our site" pointing at
        # nothing, which is worse than refusing the row.
        if self.source == ProjectSource.mirrored and not (self.signup_url or self.signup_contact):
            raise ValueError("a mirrored workday needs the signup URL or contact on your own system")
        if self.signup_mode == SignupMode.contact and not self.signup_contact:
            raise ValueError("a contact-mode workday needs a signup contact")
        if self.cap is not None and self.cap < 1:
            raise ValueError("a cap of zero is not a cap - leave it unset to say you have not capped it")
        return self

    @field_validator("starts_on")
    @classmethod
    def _not_deep_in_the_past(cls, value: date) -> date:
        # A year of leeway, so an org importing last season's calendar is not
        # refused, while a typo in the year is.
        if value < date.today() - timedelta(days=365):
            raise ValueError("that date is more than a year ago - check the year")
        return value


class WorkProjectSignupCreate(BaseModel):
    """What a volunteer sends. No `state` field: see the module docstring."""

    note: NoteText | None = None


class WorkProjectSignupOut(BaseModel):
    """One signup, with the organization's reply travelling beside its state.

    `reply_message` is returned even when it is null, because the client
    renders the org's own words where there are any and its own honest
    fallback where there are not - and it cannot tell the two apart if the
    field is omitted.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    work_project_id: str
    person_id: str
    state: SignupState
    note: str | None
    reply_message: str | None
    replied_at: UtcDatetime | None
    attended: int | None
    created_at: UtcDatetime


class WorkProjectSignupReply(BaseModel):
    """The organization answering one person.

    A message is optional but strongly wanted on a decline, which the screen
    says rather than this schema enforcing: an org that has to write a
    sentence before it can say no will sometimes just not answer, and no
    answer is worse for the volunteer than a bare one.
    """

    state: SignupState
    message: NoteText | None = None

    @field_validator("state")
    @classmethod
    def _an_org_may_only_reply(cls, value: SignupState) -> SignupState:
        if value not in REPLY_STATES:
            allowed = ", ".join(s.value for s in REPLY_STATES)
            raise ValueError(f"an organization's reply is one of: {allowed}")
        return value


class WorkProjectAttendance(BaseModel):
    """Who turned up, recorded after the fact.

    It pre-fills an hours claim rather than creating one. Hours are claimed,
    not computed - the person who worked four hours is the one who knows it
    was four, and a number the app wrote is a number no organization should
    report to ATC.
    """

    attended: int

    @field_validator("attended")
    @classmethod
    def _a_real_count(cls, value: int) -> int:
        if value < 0:
            raise ValueError("attendance cannot be negative")
        return value
