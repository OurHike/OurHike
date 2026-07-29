"""`/preferences` endpoints - the sync target for the client-owned
`UserPreferences` model (../../../features/IDENTITY_AND_PRIVACY.md).
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.db.session import get_db
from app.models.preferences import UserPreferences
from app.models.profile import Profile
from app.schemas.preferences import PreferencesIn, PreferencesOut

router = APIRouter(prefix="/preferences", tags=["preferences"])


@router.get("/me", response_model=PreferencesOut)
def get_my_preferences(
    current_user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PreferencesOut:
    """Return the current user's last-synced preferences.

    404 until the client's first PUT establishes a row - there is nothing to
    sync down before that.
    """
    row = db.get(UserPreferences, current_user.id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No synced preferences yet")
    return PreferencesOut(**row.data, updated_at=row.updated_at)


@router.put("/me", response_model=PreferencesOut)
def put_my_preferences(
    preferences: PreferencesIn,
    current_user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PreferencesOut:
    """Upsert the current user's preferences.

    A full replace of the stored blob (not a merge/patch) - creates the row
    on the first call, replaces its contents on every later call, matching a
    client syncing its whole local `UserPreferences` state wholesale.
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    data = preferences.model_dump(mode="json")

    row = db.get(UserPreferences, current_user.id)
    if row is None:
        row = UserPreferences(profile_id=current_user.id, data=data, updated_at=now)
        db.add(row)
    else:
        row.data = data
        row.updated_at = now

    db.commit()
    db.refresh(row)
    return PreferencesOut(**row.data, updated_at=row.updated_at)
