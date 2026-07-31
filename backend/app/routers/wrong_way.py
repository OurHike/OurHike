"""`/wrong-way-events` - a thin relay, deliberately not much more.

See ../../../features/HIKER_SAFETY.md §5. The actual off-trail/wrong-
direction detection (distance-from-centerline via the same snap math Map
Options' snap-to-segment uses, plus a reversed-bearing check against the
Hike's derived direction) is pure client-side geometry run continuously
against live GPS - an ephemeral `WrongWayCheck` that is never persisted
here, by design (see HIKER_SAFETY.md's "Data model additions" section).

This endpoint's entire job: once the client's own detection decides a
sustained divergence is real and escalates toward the wrong-way push (the
one notification OurHike ever sends), verify the referenced hike actually
belongs to the caller, and accept the event. Real push delivery (APNs/FCM)
needs real infrastructure/credentials that don't exist yet - out of scope
here; a later task wires this endpoint's acceptance to an actual push send.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.orm import get_or_404
from app.db.session import get_db
from app.models.hike import Hike
from app.models.profile import Profile
from app.schemas.wrong_way import WrongWayEventAck, WrongWayEventCreate

router = APIRouter(prefix="/wrong-way-events", tags=["wrong-way"])


@router.post("", response_model=WrongWayEventAck, status_code=status.HTTP_202_ACCEPTED)
def create_wrong_way_event(
    payload: WrongWayEventCreate,
    current_user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WrongWayEventAck:
    hike = get_or_404(db, Hike, payload.hike_id, detail="Hike not found")
    # 404, not 403, matching hikes.py's "don't leak id validity to a
    # non-owner" convention - a nonexistent hike and someone else's hike
    # look identical to the caller.
    if hike.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hike not found")

    return WrongWayEventAck(received=True)
