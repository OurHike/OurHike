"""Pydantic response models for the `/profiles` router."""

from pydantic import BaseModel, ConfigDict

from app.core.time import UtcDatetime
from app.models.profile import Role


class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    role: Role
    display_name: str | None
    created_at: UtcDatetime
