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

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import get_current_user, require_role
from app.core.orm import commit_and_refresh, get_or_404
from app.core.time import to_naive_utc
from app.db.session import get_db
from app.models.closure import Closure, ModerationStatus
from app.models.profile import MODERATOR_ROLES, Profile
from app.schemas.closure import ClosureCreate, ClosureOut, ClosureUpdate

router = APIRouter(prefix="/closures", tags=["closures"])


def _already_filed(db: Session, closure_id: str, current_user: Profile) -> Closure | None:
    """The caller's own closure under this id, if it is already stored.

    Reports' contract verbatim (#832): None means go ahead, and an id
    belonging to somebody else raises rather than returning their row -
    handing it back would turn a guessed UUID into a way to read another
    person's unmoderated report.
    """
    existing = db.get(Closure, closure_id)
    if existing is None:
        return None
    if existing.reported_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That closure id belongs to someone else.",
        )
    return existing


@router.post("", response_model=ClosureOut, status_code=status.HTTP_201_CREATED)
def create_closure(
    payload: ClosureCreate,
    response: Response,
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

    **Idempotent on `id`, and dated by the client (#832).** Both arrived with
    this app's closure form, and both are the offline path showing through: a
    closure is authored at the washout with no signal, so the request that
    commits here and loses its response on the way back is the ordinary case
    rather than the unlucky one, and the day it was written is not the day it
    arrives. `201` still means newly created; a resend gets `200` and the
    stored row.
    """
    closure_id = str(payload.id) if payload.id is not None else None

    if closure_id is not None:
        settled = _already_filed(db, closure_id, current_user)
        if settled is not None:
            response.status_code = status.HTTP_200_OK
            return settled

    closure = Closure(
        **({"id": closure_id} if closure_id is not None else {}),
        reported_by=current_user.id,
        # The client's own claim when it made one, the server clock
        # otherwise - `reports.authored_at`'s exact posture, and what keeps
        # the sheet's age honest for a closure that waited days in an
        # outbox. The schema has already refused anything meaningfully in
        # the future.
        **({"reported_at": to_naive_utc(payload.reported_at)} if payload.reported_at is not None else {}),
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
    try:
        return commit_and_refresh(db, closure)
    except IntegrityError:
        # The lookup above and this insert are two statements, so two
        # concurrent flushes of the same id both see "not filed yet" and both
        # insert. Reports met this first (#265) and the reasoning carries: it
        # is not a rare interleaving to shrug at, it is exactly what the
        # retry path exists to produce, and losing the race would surface as
        # a 500 from the one endpoint whose whole promise is that sending
        # twice is safe.
        db.rollback()
        settled = _already_filed(db, closure_id, current_user) if closure_id is not None else None
        if settled is None:
            raise
        response.status_code = status.HTTP_200_OK
        return settled


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
