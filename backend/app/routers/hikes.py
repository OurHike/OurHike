"""`/hikes` endpoints - standard CRUD scoped to the authenticated user, plus
a derived-direction endpoint for ../../../features/HIKER_SAFETY.md section
5's wrong-way alert. See app/models/hike.py for why this table exists.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.hike_direction import derive_direction
from app.core.orm import commit_and_refresh, get_or_404
from app.db.session import get_db
from app.models.hike import Hike
from app.models.profile import Profile
from app.schemas.hike import HikeCreate, HikeDirectionOut, HikeOut, HikeUpdate

router = APIRouter(prefix="/hikes", tags=["hikes"])


def _get_owned_hike_or_404(hike_id: str, current_user: Profile, db: Session) -> Hike:
    """Fetch a hike by id, scoped to the caller.

    A hike that exists but belongs to someone else 404s exactly like one
    that doesn't exist at all - not a 403 - so a caller can't use this
    endpoint to learn whether some other user's hike id is valid.
    """
    hike = get_or_404(db, Hike, hike_id, detail="Hike not found")
    if hike.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hike not found")
    return hike


@router.post("", response_model=HikeOut, status_code=status.HTTP_201_CREATED)
def create_hike(
    payload: HikeCreate,
    current_user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Hike:
    hike = Hike(user_id=current_user.id, **payload.model_dump())
    db.add(hike)
    return commit_and_refresh(db, hike)


@router.get("", response_model=list[HikeOut])
def list_hikes(
    current_user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Hike]:
    """Return only the caller's own hikes, never another user's."""
    return db.execute(select(Hike).where(Hike.user_id == current_user.id)).scalars().all()


@router.get("/{hike_id}", response_model=HikeOut)
def get_hike(
    hike_id: str,
    current_user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Hike:
    return _get_owned_hike_or_404(hike_id, current_user, db)


@router.patch("/{hike_id}", response_model=HikeOut)
def update_hike(
    hike_id: str,
    payload: HikeUpdate,
    current_user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Hike:
    hike = _get_owned_hike_or_404(hike_id, current_user, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(hike, field, value)
    return commit_and_refresh(db, hike)


@router.delete("/{hike_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_hike(
    hike_id: str,
    current_user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    hike = _get_owned_hike_or_404(hike_id, current_user, db)
    db.delete(hike)
    db.commit()


@router.get("/{hike_id}/direction", response_model=HikeDirectionOut)
def get_hike_direction(
    hike_id: str,
    current_user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """The wrong-way alert's dependency: NOBO/SOBO, derived, never stored."""
    hike = _get_owned_hike_or_404(hike_id, current_user, db)
    return {"direction": derive_direction(hike.overall_start_reference, hike.overall_end_reference)}
