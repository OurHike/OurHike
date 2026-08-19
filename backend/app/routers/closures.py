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

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_user, require_role
from app.core.orm import commit_and_refresh, get_or_404
from app.core.time import to_naive_utc
from app.db.session import get_db
from app.models.closure import Closure, ModerationStatus
from app.models.profile import MODERATOR_ROLES, Profile
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
    `visibility`/`severity` server-controlled pattern.

    The real-world `status` is server-controlled too, and starts at `closed`:
    somebody filing this is telling us the trail is shut. See the column's
    own comment in app/models/closure.py for why that default is the whole of
    #246, and why a REPORTER never picks this field - reopening a trail, or
    confirming a reroute exists, is a maintainer's judgment (PATCH, or the
    verify call in app/routers/moderation.py).
    """
    closure = Closure(
        reported_by=current_user.id,
        reason_type=payload.reason_type,
        note=payload.note,
        start_mile_marker=payload.start_mile_marker,
        end_mile_marker=payload.end_mile_marker,
        # Stored exactly as sent, after ClosureCreate has normalised the
        # ordering of both the miles and the points together (#674). Nothing
        # here derives, checks or repairs a position: this backend holds no
        # centerline, so it cannot tell a point on the trail from a point in
        # the sea, and pretending otherwise would be a check that always
        # passes.
        start_lat=payload.start_lat,
        start_lon=payload.start_lon,
        end_lat=payload.end_lat,
        end_lon=payload.end_lon,
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
    current_user: Profile = Depends(require_role(*MODERATOR_ROLES)),
    db: Session = Depends(get_db),
) -> Closure:
    """Update a closure's real-world status/reason/note. Role-gated -
    modifying a closure (as opposed to reporting one) is a moderator
    action."""
    closure = get_or_404(db, Closure, closure_id, detail="Closure not found")

    # `model_fields_set` rather than a None check, so a maintainer can put a
    # nullable field back to unknown - a slipped reopening date, a stale note
    # (#255). For `status` and `reason_type` the two tests are equivalent:
    # ClosureUpdate rejects an explicit null on them before this runs.
    provided = payload.model_fields_set

    if "status" in provided:
        closure.status = payload.status
    if "reason_type" in provided:
        closure.reason_type = payload.reason_type
    if "note" in provided:
        closure.note = payload.note

    def settled(field: str, incoming: object) -> object:
        return incoming if field in provided else getattr(closure, field)

    closed_since = settled("closed_since", to_naive_utc(payload.closed_since))
    expected_reopen = settled("expected_reopen", to_naive_utc(payload.expected_reopen))

    # Checked against the state this request would leave behind, not against
    # the payload, and BEFORE anything is assigned. Two reasons, in that
    # order. The dates arrive in whichever order a maintainer happens to send
    # them, quite possibly in separate requests days apart, so a payload-only
    # check passes on every second half of an inconsistent pair. And a check
    # that runs after the assignment leaves the rejected values sitting on a
    # live ORM instance, where the next autoflush - any query on this session,
    # not necessarily a commit - can write them out behind the 422.
    if closed_since is not None and expected_reopen is not None and expected_reopen < closed_since:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="expected_reopen cannot be before closed_since",
        )

    closure.closed_since = closed_since
    closure.expected_reopen = expected_reopen
    if "reroute_url" in provided:
        closure.reroute_url = payload.reroute_url

    return commit_and_refresh(db, closure)


# `POST /closures/{id}/verify` and `/dismiss` - the actual moderation-queue
# actions that move `moderation_status` - live in app/routers/moderation.py
# alongside Report's equivalent actions, not here: verifying/dismissing is a
# cross-resource workflow concern, not per-resource CRUD.
