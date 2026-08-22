"""`/profiles` endpoints - who you are, everything we hold, and the way out."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.account_deletion import delete_account
from app.core.account_export import build_export
from app.core.auth import get_current_user
from app.db.session import get_db
from app.models.profile import Profile
from app.schemas.profile import DeletionReceipt, ProfileOut

router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.get("/me", response_model=ProfileOut)
def get_my_profile(current_user: Profile = Depends(get_current_user)) -> Profile:
    """Return the current authenticated user's own profile."""
    return current_user


@router.get("/me/export")
def export_my_account(
    current_user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Everything this backend holds about the caller, as plain JSON.

    Deliberately NOT `response_model`-typed. A pydantic model here would be a
    hand-maintained field list in front of an archive whose entire point is
    that it cannot omit anything - and FastAPI filters the response to the
    declared model, so the first column somebody adds to a table would be
    silently dropped from every hiker's export with nothing failing.
    app/core/account_export.py argues the whole shape.

    A GET rather than a POST because it changes nothing, and because a hiker
    who wants to look before they leap should be able to.
    """
    return build_export(db, current_user)


@router.delete("/me", response_model=DeletionReceipt)
def delete_my_account(
    current_user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DeletionReceipt:
    """Delete the account: the private rows go, the published ones stay.

    What that sentence means table by table is app/core/account_deletion.py,
    which is where a reviewer should disagree with it. This layer owns two
    things only: the transaction, and the receipt.

    THE TRANSACTION IS THE POINT OF THIS FUNCTION EXISTING

    `delete_account` deliberately does not commit. Six deletes and a scrub
    that half-landed is the one outcome nothing can put right afterwards -
    there is no undo for this and no second copy to reconcile against - so
    the commit is one call, here, after every statement has been issued, and
    a failure anywhere rolls the lot back and answers 500 with the account
    intact. That is the safe direction: a hiker who has to press the button
    twice is inconvenienced, and a hiker whose trips went while their
    account stayed has been half-deleted with no way to say so.

    THE RECEIPT

    A hiker is owed the numbers rather than the word "done", and
    specifically is owed the count of what STAYED - the closures and photos
    that outlive the account. The screen says that before the button is
    pressed (client/src/screens/Settings.tsx); this says it again afterwards,
    against the real rows, because the screen's version is a promise and
    this one is a fact.

    204 was considered and refused for exactly that: an empty body is the
    honest answer only if there is nothing the hiker needs to know, and here
    there is.
    """
    summary = delete_account(db, current_user)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The account was not deleted. Nothing was changed.",
        ) from None

    return DeletionReceipt(
        trips_deleted=summary.trips_deleted,
        planned_hikes_deleted=summary.planned_hikes_deleted,
        hikes_deleted=summary.hikes_deleted,
        preferences_deleted=summary.preferences_deleted,
        assignments_released=summary.assignments_deleted,
        hours_deleted=summary.hours_deleted,
        app_failure_reports_unlinked=summary.app_failures_unlinked,
        kept=summary.contributions_kept,
    )
