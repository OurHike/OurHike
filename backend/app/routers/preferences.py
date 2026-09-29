"""`/preferences` endpoints - the sync target for the client-owned
`UserPreferences` model (../../../features/IDENTITY_AND_PRIVACY.md).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.orm import commit_and_refresh
from app.core.time import utc_now
from app.db.session import get_db
from app.models.preferences import UserPreferences
from app.models.profile import Profile
from app.schemas.preferences import PreferencesIn, PreferencesOut, repair_stored_background

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
    # Repaired, not trusted: the row may predate a schema tightening (see
    # repair_stored_background), and a GET is the one place the affected
    # client cannot fix it first.
    return PreferencesOut(**repair_stored_background(row.data), updated_at=row.updated_at)


@router.put("/me", response_model=PreferencesOut)
def put_my_preferences(
    preferences: PreferencesIn,
    current_user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PreferencesOut:
    """Upsert the current user's preferences.

    A full sync of the caller's own local `UserPreferences` state - creates
    the row on the first call, and on every later call merges onto what is
    already stored rather than replacing it outright (see `_merged`). For a
    client that knows every field this schema declares, in practice that is
    still a full overwrite: such a client always sends every key, so nothing
    is ever missing to merge onto.
    """
    now = utc_now()

    row = db.get(UserPreferences, current_user.id)
    if row is None:
        row = UserPreferences(profile_id=current_user.id, data=_merged(existing=None, incoming=preferences), updated_at=now)
        db.add(row)
    else:
        row.data = _merged(existing=row.data, incoming=preferences)
        row.updated_at = now

    try:
        row = commit_and_refresh(db, row)
    except IntegrityError:
        # The upsert is check-then-insert, so two concurrent first syncs
        # race and the loser used to 500 (#658, the #265 shape). The winner's
        # row is the one to merge onto, the same as the ordinary update path
        # above - a retry would have read that row and done the same merge.
        db.rollback()
        row = db.get(UserPreferences, current_user.id)
        if row is None:
            raise
        row.data = _merged(existing=row.data, incoming=preferences)
        row.updated_at = now
        row = commit_and_refresh(db, row)
    return PreferencesOut(**row.data, updated_at=row.updated_at)


def _merged(*, existing: dict | None, incoming: PreferencesIn) -> dict:
    """What gets stored: the incoming sync, laid over what is already there.

    #1641 finding 7: a v1.3.1 client's `PreferencesIn` never declared
    `real_name` (added by #1563) or `blaze_colors_shown` (added by #1575),
    so its own request body never carries those keys - not because the
    hiker chose to clear them, but because that build has no concept of
    either field. A plain `model_dump()` fills the gap with today's schema
    default and writes it over whatever a newer device had synced, silently.

    `exclude_unset=True` is the fix: pydantic tracks which fields a request
    body actually named, distinct from which fields merely defaulted, so a
    key genuinely absent from an old client's JSON stays absent here too and
    the merge leaves the stored value untouched. A current client sending
    every field it knows about - which is what "sync its whole local state"
    means for a build that has never dropped a field - still overwrites
    everything, because every one of those keys IS present, whatever value
    it carries; this only protects a key a client does not know exists.

    `existing=None` (the first sync for this profile) has nothing to merge
    onto, so every field defaults per PreferencesIn's own schema instead -
    the same starting point a brand-new row has always had.
    """
    if existing is None:
        return incoming.model_dump(mode="json")
    return {**existing, **incoming.model_dump(mode="json", exclude_unset=True)}
