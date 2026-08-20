"""Pydantic request/response models for the `/volunteer-hours` router."""

import uuid
from datetime import date, datetime, timedelta, timezone

from pydantic import BaseModel, ConfigDict, field_validator

from app.core.time import UtcDatetime
from app.models.volunteer_hours import HoursActivity, HoursState
from app.schemas.common import FiniteFloat, NoteText


class VolunteerHoursCreate(BaseModel):
    """What a volunteer files. `state`, `confirmed_by/at` and `recorded_at`
    are server-controlled and have no fields here; `id` is the outbox's
    idempotency key, exactly as on reports and field notes."""

    id: uuid.UUID | None = None

    worked_on: date
    hours: FiniteFloat
    activity: HoursActivity
    note: NoteText | None = None
    club_id: str | None = None
    work_project_id: str | None = None
    mile: FiniteFloat | None = None
    lat: FiniteFloat | None = None
    lon: FiniteFloat | None = None

    @field_validator("worked_on")
    @classmethod
    def _reject_future_work(cls, value: date) -> date:
        # A day of leeway rather than reports' five minutes, because this is
        # a DATE and the volunteer's midnight is not the server's: "today"
        # filed from a US evening is already "tomorrow" in UTC.
        if value > (datetime.now(timezone.utc) + timedelta(days=1)).date():
            raise ValueError("worked_on cannot be in the future")
        return value

    @field_validator("hours")
    @classmethod
    def _reject_impossible_hours(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("hours must be more than zero")
        # A day holds twenty-four. More on one record is a typo, and a typo
        # in a number that reaches ATC's funding reports is worth refusing
        # at the keyboard rather than disputing after.
        if value > 24:
            raise ValueError("one record covers one day of work - 24 hours at most")
        return value

    @field_validator("mile")
    @classmethod
    def _reject_a_negative_mile(cls, value: float | None) -> float | None:
        # ReportCreate's bound, for its reasons: no upper bound (the trail's
        # length is the published centerline's property), negatives refused.
        if value is not None and value < 0:
            raise ValueError("mile cannot be negative")
        return value


class VolunteerHoursOut(BaseModel):
    """One record, whole. No `for_viewer` split, because there is no
    anonymous audience: every read of this resource is the volunteer reading
    their own logbook or a club admin deciding whether to stand behind a
    row, and both are entitled to all of it. There is deliberately no public
    list at all - a private record is the entire design (#761)."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    club_id: str | None
    worked_on: date
    hours: float
    work_project_id: str | None
    activity: HoursActivity
    note: str | None
    mile: float | None
    lat: float | None
    lon: float | None
    state: HoursState
    confirmed_at: UtcDatetime | None
    recorded_at: UtcDatetime
