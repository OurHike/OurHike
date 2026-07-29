"""Pydantic response models for the `/profiles` router."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.profile import Role


class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    role: Role
    display_name: str | None
    created_at: datetime
