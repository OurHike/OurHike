from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from steward_api.auth import current_user
from steward_api.db import get_db
from steward_api.models import StewardUser
from steward_api.schemas import Me, MeUpdate

router = APIRouter(prefix="/me", tags=["me"])


@router.get("", response_model=Me)
def read_me(user: StewardUser = Depends(current_user)) -> Me:
    return Me(display_name=user.display_name)


@router.patch("", response_model=Me)
def update_me(body: MeUpdate, user: StewardUser = Depends(current_user), db: Session = Depends(get_db)) -> Me:
    user.display_name = body.display_name
    db.commit()
    return Me(display_name=user.display_name)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def delete_me(user: StewardUser = Depends(current_user), db: Session = Depends(get_db)) -> None:
    """Everything this API holds about the caller: their lists go, and their
    weights changes stay in the clubs' histories without a name (models.py).
    The Supabase account itself is OurHike's, and is not touched here."""
    db.delete(user)
    db.commit()
