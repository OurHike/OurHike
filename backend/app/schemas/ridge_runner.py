"""Request/response models for the volunteer trail monitor commitment.

See ../../../features/VOLUNTEERING.md §3, ../../../features/ORG_ONBOARDING.md
and #763. `app/models/ridge_runner.py` carries why the name is qualified
wherever a third party can see it.

**There is no completion field anywhere in this file, and that is the
design.** No percentage, no "days kept", no streak. The record shows what was
submitted, never what was expected and missed - so a partial week reads as a
week's worth of real work, which is what it is.
"""

from __future__ import annotations

from datetime import date, timedelta

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from app.core.time import UtcDatetime
from app.models.ridge_runner import COMMITMENT_TASKS, MAX_COMMITMENT_DAYS
from app.schemas.common import NoteText


class CommitmentCreate(BaseModel):
    starts_on: date
    ends_on: date
    tasks: list[str]
    club_id: str | None = None
    note: NoteText | None = None

    @field_validator("tasks")
    @classmethod
    def _known_tasks(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("pick at least one kind of work - the tasks are what the app asks you about")
        unknown = [task for task in value if task not in COMMITMENT_TASKS]
        if unknown:
            raise ValueError(f"not a task this app knows: {', '.join(unknown)}")
        # Deduplicated and ordered, so two clients sending the same set
        # store the same string and a test can compare them.
        return sorted(set(value))

    @model_validator(mode="after")
    def _seven_days_at_most(self) -> CommitmentCreate:
        if self.ends_on < self.starts_on:
            raise ValueError("a window cannot end before it starts")
        # Inclusive: a window that starts and ends on the same day is one
        # day, and the longest legal window is seven.
        days = (self.ends_on - self.starts_on).days + 1
        if days > MAX_COMMITMENT_DAYS:
            raise ValueError(
                f"a commitment runs {MAX_COMMITMENT_DAYS} days at most - "
                "a window that ends is what keeps this from becoming an obligation that accumulates"
            )
        if self.starts_on < date.today() - timedelta(days=1):
            raise ValueError("a commitment starts today or later")
        return self


class CommitmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    person_id: str
    starts_on: date
    ends_on: date
    tasks: list[str]
    club_id: str | None
    note: str | None
    created_at: UtcDatetime
    ended_early_at: UtcDatetime | None

    @field_validator("tasks", mode="before")
    @classmethod
    def _split_stored_tasks(cls, value: object) -> object:
        # Stored comma-separated on the row; a list on the wire. Done here
        # rather than with a SQLAlchemy type so the storage stays something a
        # person can read in psql while debugging.
        if isinstance(value, str):
            return [task for task in value.split(",") if task]
        return value
