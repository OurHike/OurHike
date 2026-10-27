from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy import delete, func, update
from sqlalchemy.orm import Session

from steward_api.auth import current_user
from steward_api.db import get_db
from steward_api.models import Claim, ClubWeights, Hours, SiteList, StewardUser
from steward_api.routes.claims import WORKING_STATES
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
    """Deletes what this API holds that is the caller's own: their name (here
    and on every history entry it was copied to), their lists and their hours.
    Claims they were working on go back to Open.

    What stays, without a name: the claims and weights changes they made, which
    are other people's history too, and their crew places, which keep them from
    ever reviewing work they were part of. The account row stays, marked, so
    those rows still point at it: deleting the row let the same sign-in return
    as a stranger the moment after (the adversarial review's finding 3,
    2026-10-27). Signing in again starts an empty account (auth.current_user).

    The Supabase account itself is OurHike's, and is not touched here."""
    db.execute(
        update(Claim)
        .where(Claim.claimer_id == user.id, Claim.state.in_(WORKING_STATES))
        .values(state="released", released_at=func.now(), invite_token_sha256=None)
    )
    db.execute(update(ClubWeights).where(ClubWeights.changed_by == user.id).values(changed_by_name=None))
    db.execute(update(Claim).where(Claim.reviewed_by == user.id).values(reviewed_by_name=None))
    db.execute(delete(SiteList).where(SiteList.owner_id == user.id))
    db.execute(delete(Hours).where(Hours.user_id == user.id))
    user.display_name = None
    user.deleted_at = func.now()
    db.commit()
