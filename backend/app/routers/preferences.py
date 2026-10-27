"""`/preferences` endpoints - the sync target for the client-owned
`UserPreferences` model (../../../features/IDENTITY_AND_PRIVACY.md).

One preference here is more than a display setting: usage measurement's
"Link them to my account" (#1902). Saying no, or turning measurement off,
after having said yes unlinks what was linked - see `_forget_withdrawn_link`.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.analytics_accounts import LinkedUsageUnreachable, forget_link
from app.core.auth import get_current_user
from app.core.orm import commit_and_refresh
from app.core.time import utc_now
from app.db.session import get_db
from app.models.preferences import UserPreferences
from app.models.profile import Profile
from app.schemas.preferences import PreferencesIn, PreferencesOut, repair_stored_background

logger = logging.getLogger(__name__)

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
        merged = _merged(existing=row.data, incoming=preferences)
        _forget_withdrawn_link(db, current_user.id, before=row.data, after=merged)
        row.data = merged
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
        merged = _merged(existing=row.data, incoming=preferences)
        _forget_withdrawn_link(db, current_user.id, before=row.data, after=merged)
        row.data = merged
        row.updated_at = now
        row = commit_and_refresh(db, row)
    return PreferencesOut(**row.data, updated_at=row.updated_at)


def _usage_linked(data: dict | None) -> bool:
    """Whether these preferences agree to usage being linked: a yes, with measurement on."""
    data = data or {}
    return data.get("measurement_linked") is True and data.get("measurement_enabled", True) is not False


def _forget_withdrawn_link(db: Session, account_id: str, *, before: dict | None, after: dict) -> None:
    """Unlink this account's usage when this sync takes back a yes it had stored.

    Its User-table rows go and its events lose their key, in the same
    transaction as the preference itself (app/core/analytics_accounts.py
    `forget_link`, which also says what it cannot reach: the account id
    sealed inside each row stays until the row's six months end).

    With no secret configured to find them, the link cannot be forgotten -
    but the preference is still saved, because it is what stops linking from
    here on (app/routers/analytics.py reads it). Logged by names only, for
    whoever restores the secret.
    """
    if not _usage_linked(before) or _usage_linked(after):
        return
    try:
        forget_link(db, account_id)
    except LinkedUsageUnreachable:
        logger.warning("usage link withdrawn but not forgotten: no analytics user-key secret is configured to find the rows")


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
