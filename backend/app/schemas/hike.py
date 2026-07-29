"""Pydantic schemas for the `/hikes` router."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class HikeCreate(BaseModel):
    trail_id: str = "AT"
    overall_start_reference: float
    overall_end_reference: float
    planned_start_date: date | None = None


class HikeUpdate(BaseModel):
    """All fields optional - a PATCH only changes what it includes.

    `exclude_unset=True` at the call site (app/routers/hikes.py) is what
    makes "included but null" and "omitted entirely" behave differently,
    same as any partial-update schema.
    """

    trail_id: str | None = None
    overall_start_reference: float | None = None
    overall_end_reference: float | None = None
    planned_start_date: date | None = None


class HikeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    trail_id: str
    overall_start_reference: float
    overall_end_reference: float
    planned_start_date: date | None
    created_at: datetime


class HikeDirectionOut(BaseModel):
    direction: str
