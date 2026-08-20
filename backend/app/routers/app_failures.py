"""`/app-failures` - the report a hiker files when this software failed them
on the trail (#848).

See ../../../features/APP_FAILURE_REPORTS.md for the whole path and
app/models/app_failure.py for why this is not a `Report`.

Three things about this endpoint are unlike every other write here, and each
one is a decision rather than an oversight:

**It takes no account.** Every other write in this backend is behind
`get_current_user`. This one uses `get_current_user_optional`, because the
hiker whose app just failed may never have signed in - browsing the map has
never needed an account - and telling them to make one first, from a ridge,
is a way of not hearing from them. A token is recorded when there is one.

**It refuses almost nothing.** A 422 from here does not bounce a request; it
strands the report permanently in the sender's outbox (client/src/lib/api.ts,
`permanentFailureReason`). app/schemas/app_failure.py truncates and drops
rather than raising, for that reason, and this handler adds no rules of its
own on top.

**It never reads back.** There is no `GET`, no list, no detail. A row here
holds a contact detail somebody gave while shaken, and nothing serving it
means nothing to get wrong about who may see it. The acknowledgement carries
the id and the arrival time - facts the sender already has - and nothing else.

**What is deliberately NOT built, and would be needed before this is
load-bearing:** rate limiting. This is the first unauthenticated write in
the app, so it is the first one an abuser can reach without an account.
Nothing here throttles, and nothing upstream is known to - a proxy-level
limit is the natural home and no claim is made that one exists. Said out
loud rather than implied, because "we accept anything from anyone" is a
property somebody should notice before it is discovered.
"""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import get_current_user_optional
from app.core.orm import commit_and_refresh
from app.core.time import to_naive_utc, utc_now
from app.db.session import get_db
from app.models.app_failure import AppFailure
from app.models.profile import Profile
from app.schemas.app_failure import AppFailureAck, AppFailureCreate

router = APIRouter(prefix="/app-failures", tags=["app-failures"])


def _ack(failure: AppFailure) -> AppFailureAck:
    return AppFailureAck(id=failure.id, received_at=failure.received_at)


@router.post("", response_model=AppFailureAck, status_code=status.HTTP_201_CREATED)
def create_app_failure(
    payload: AppFailureCreate,
    response: Response,
    current_user: Profile | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
) -> AppFailureAck:
    """File a report that the app failed on the trail.

    **Idempotent on `id`**, the same way `POST /reports` is and for the same
    trail-side reason: the request that commits here and whose response never
    arrives is the ordinary failure on one bar of signal, and the outbox will
    resend. A resend returns the stored row with `200` rather than filing a
    second copy.

    Unlike reports, a resend under an id that belongs to somebody ELSE is not
    refused - it is treated as already filed and acknowledged. There is
    nothing to leak by doing so: the acknowledgement carries only the id the
    caller already sent and an arrival time, never the stored report. Refusing
    instead would hand a hiker a 409, which their outbox reads as permanent
    and which would lose a real report to a UUID collision.
    """
    failure_id = str(payload.id) if payload.id is not None else None

    if failure_id is not None:
        settled = db.get(AppFailure, failure_id)
        if settled is not None:
            response.status_code = status.HTTP_200_OK
            return _ack(settled)

    now = utc_now()
    # Stored naive-UTC throughout (app/models/profile.py). Absent falls back
    # to the server clock, which is the honest answer for a client that did
    # not say - not a refusal.
    authored = to_naive_utc(payload.authored_at) or now

    failure = AppFailure(
        **({"id": failure_id} if failure_id is not None else {}),
        reporter_id=current_user.id if current_user is not None else None,
        what_happened=payload.what_happened,
        whereabouts=payload.whereabouts,
        contact=payload.contact,
        # Stored as the plain strings the enum carries, so a row read with
        # psql - which is how these are read - is readable without knowing
        # this codebase. Empty stays empty rather than becoming null: the
        # form was answered with "none of these", and that is not the same
        # fact as a report filed before the question existed.
        harms=[harm.value for harm in payload.harms],
        build=payload.build,
        was_offline=payload.was_offline,
        authored_at=authored,
        received_at=now,
    )
    db.add(failure)
    try:
        return _ack(commit_and_refresh(db, failure))
    except IntegrityError:
        # The get above and this insert are two statements, so two concurrent
        # sends of one id both see "not filed" and both insert - which is
        # exactly what the retry path produces, not a rare interleaving
        # (#265, the same shape reports hit). The row the loser wanted is the
        # one the winner just wrote.
        db.rollback()
        settled = db.get(AppFailure, failure_id) if failure_id is not None else None
        if settled is None:
            raise
        response.status_code = status.HTTP_200_OK
        return _ack(settled)
