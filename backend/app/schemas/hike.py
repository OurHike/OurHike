"""Pydantic schemas for the `/hikes` router."""

from datetime import date

from pydantic import BaseModel, ConfigDict

from app.core.time import UtcDatetime
from app.schemas.partial import reject_explicit_null


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

    The three fields backed by `nullable=False` columns (app/models/hike.py)
    reject an explicit null as a 422 rather than letting it through to die as
    an IntegrityError 500 (#255). `planned_start_date` is the nullable one,
    so `{"planned_start_date": null}` is a deliberate clear and works.
    """

    trail_id: str | None = None
    overall_start_reference: float | None = None
    overall_end_reference: float | None = None
    planned_start_date: date | None = None

    _no_explicit_nulls = reject_explicit_null("trail_id", "overall_start_reference", "overall_end_reference")


class HikeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    trail_id: str
    overall_start_reference: float
    overall_end_reference: float
    planned_start_date: date | None
    created_at: UtcDatetime


class HikeDirectionOut(BaseModel):
    direction: str
