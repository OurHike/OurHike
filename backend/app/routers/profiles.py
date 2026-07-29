"""`/profiles` endpoints."""

from fastapi import APIRouter, Depends

from app.core.auth import get_current_user
from app.models.profile import Profile
from app.schemas.profile import ProfileOut

router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.get("/me", response_model=ProfileOut)
def get_my_profile(current_user: Profile = Depends(get_current_user)) -> Profile:
    """Return the current authenticated user's own profile."""
    return current_user
