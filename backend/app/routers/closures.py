"""`/closures` endpoints - trail closures (storm damage, flooding, reroutes).

See ../../../features/MAP_OPTIONS.md. Browsing (`GET`) needs no account,
matching every other browsing endpoint in this app. Reporting a closure
(`POST`) requires a real identity, mirroring Report a Problem's create
permissions. Modifying one (`PATCH`) is role-gated to maintainer/club_admin
- MAP_OPTIONS.md doesn't spell out a separate create-vs-verify permission
split for Closures the way REPORT_A_PROBLEM.md does for Reports, only that
Closures reuse "the same permission tier" - read here as the same split
Report a Problem establishes, not a stated decision of its own.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_user, require_role
from app.core.orm import commit_and_refresh, get_or_404
from app.db.session import get_db
from app.models.closure import Closure, ModerationStatus
from app.models.profile import Profile
from app.schemas.closure import ClosureCreate, ClosureOut, ClosureUpdate

router = APIRouter(prefix="/closures", tags=["closures"])


@router.post("", response_model=ClosureOut, status_code=status.HTTP_201_CREATED)
def create_closure(
    payload: ClosureCreate,
    current_user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Closure:
    """Report a new closure. `moderation_status` always starts at
    `submitted` - never accepted from the client, matching Report's
    `visibility`/`severity` server-controlled pattern."""
    closure = Closure(
        reported_by=current_user.id,
        reason_type=payload.reason_type,
        note=payload.note,
        start_mile_marker=payload.start_mile_marker,
        end_mile_marker=payload.end_mile_marker,
    )
    db.add(closure)
    return commit_and_refresh(db, closure)


@router.get("", response_model=list[ClosureOut])
def list_closures(db: Session = Depends(get_db)) -> list[Closure]:
    """List closures visible to anyone: verified only. No auth required -
    browsing needs no account, and closures are never hideable once
    verified (MAP_OPTIONS.md - `show_closures` isn't a setting anywhere)."""
    return db.query(Closure).filter(Closure.moderation_status == ModerationStatus.verified).all()


@router.patch("/{closure_id}", response_model=ClosureOut)
def update_closure(
    closure_id: str,
    payload: ClosureUpdate,
    current_user: Profile = Depends(require_role("maintainer", "club_admin")),
    db: Session = Depends(get_db),
) -> Closure:
    """Update a closure's real-world status/reason/note. Role-gated -
    modifying a closure (as opposed to reporting one) is a moderator
    action."""
    closure = get_or_404(db, Closure, closure_id, detail="Closure not found")

    if payload.status is not None:
        closure.status = payload.status
    if payload.reason_type is not None:
        closure.reason_type = payload.reason_type
    if payload.note is not None:
        closure.note = payload.note

    return commit_and_refresh(db, closure)


# `POST /closures/{id}/verify` and `/dismiss` - the actual moderation-queue
# actions that move `moderation_status` - live in app/routers/moderation.py
# alongside Report's equivalent actions, not here: verifying/dismissing is a
# cross-resource workflow concern, not per-resource CRUD.
