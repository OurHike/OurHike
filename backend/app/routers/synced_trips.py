"""`/trips/sync` - one exchange that carries a hiker's plans between devices.

Phase B of ../../../features/ACCOUNT_SYNC.md (#892). The conflict rule lives
in `app/core/trip_sync.py` and is tested there against no database at all;
this router is the part that reads rows, applies what the rule decided, and
answers with what changed elsewhere.

ONE ENDPOINT, NOT CRUD, and that is a decision rather than a shortcut. A
REST collection would make a sync several round trips - list, then a PUT per
changed trip - each with its own chance to half-land, and the "what changed
elsewhere" question would be answered against a database that had moved
since the uploads. The two halves belong in one transaction because they are
one question: *here is what I did, what did everyone else do?*

WHAT THIS DOES NOT TOUCH

`app/routers/hikes.py`. That table is the durable start/end reference the
wrong-way alert reads server-side, and it stays exactly that - see
`app/models/synced_trip.py`'s `SyncedPlannedHike` docstring for why syncing
a singleton through a collection with ids would mean every device
remembering which row is "the" one.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.time import to_naive_utc, utc_now
from app.core.trip_sync import StoredTrip, UploadedTrip, resolve_upload
from app.db.session import get_db
from app.models.profile import Profile
from app.models.synced_trip import SyncedPlannedHike, SyncedTrip
from app.schemas.synced_trip import (
    PlannedHikeOut,
    TripOut,
    TripSyncIn,
    TripSyncOut,
)

router = APIRouter(prefix="/trips", tags=["trips"])


def _owned(db: Session, profile: Profile, ids: list[str]) -> dict[str, SyncedTrip]:
    """This hiker's rows among the ids offered, keyed by id.

    Scoped by `profile_id` in the query rather than filtered afterwards,
    which is what makes the next paragraph true rather than intended.

    **An id belonging to somebody else simply is not here**, so the upload
    that names it is treated as a trip the server has never seen and lands
    under that id for THIS hiker - two rows, one id... which the primary key
    forbids. So `_apply` checks for the collision explicitly and drops the
    upload. Dropping rather than 409ing is deliberate: a client-minted UUID
    colliding with a stranger's is not something a hiker can act on, and
    telling them their trip id exists elsewhere would answer a question
    nobody should be able to ask (`app/routers/hikes.py`'s 404-not-403 rule).
    """
    if not ids:
        return {}
    rows = db.scalars(
        select(SyncedTrip).where(
            SyncedTrip.profile_id == profile.id,
            SyncedTrip.id.in_(ids),
        )
    ).all()
    return {row.id: row for row in rows}


def _foreign_ids(db: Session, profile: Profile, ids: list[str]) -> set[str]:
    """Ids that exist and belong to somebody else. See `_owned`."""
    if not ids:
        return set()
    rows = db.scalars(
        select(SyncedTrip.id).where(
            SyncedTrip.id.in_(ids),
            SyncedTrip.profile_id != profile.id,
        )
    ).all()
    return set(rows)


@router.post("/sync", response_model=TripSyncOut)
def sync_trips(
    payload: TripSyncIn,
    current_user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TripSyncOut:
    ids = [trip.id for trip in payload.trips]
    mine = _owned(db, current_user, ids)
    theirs = _foreign_ids(db, current_user, ids)

    written_at = utc_now()
    conflicts = 0

    for upload in payload.trips:
        if upload.id in theirs:
            # Somebody else's id. See `_owned` on why this is silent.
            continue

        row = mine.get(upload.id)
        stored = (
            None
            if row is None
            else StoredTrip(
                id=row.id,
                document=row.document,
                updated_at=row.updated_at,
                deleted_at=row.deleted_at,
            )
        )
        writes = resolve_upload(
            UploadedTrip(
                id=upload.id,
                document=upload.document,
                # Normalised to the naive-UTC storage convention BEFORE the
                # rule sees it. The wire carries `...Z`, the column carries
                # naive UTC, and an aware value never equals a naive one - so
                # without this every single upload compares unequal to the
                # stamp it was built from, and every ordinary edit is
                # resolved as a conflict. That failure is silent and it is
                # the expensive direction: it does not lose data, it buries
                # the hiker in copies of their own trips.
                base_updated_at=to_naive_utc(upload.base_updated_at),
                deleted=upload.deleted,
            ),
            stored,
            written_at,
        )
        for write in writes:
            if write.is_conflict_copy:
                conflicts += 1
            target = mine.get(write.id)
            if target is None:
                target = SyncedTrip(id=write.id, profile_id=current_user.id)
                db.add(target)
                mine[write.id] = target
            target.document = write.document
            target.updated_at = written_at
            # Set once and never cleared: a tombstone a slow device could
            # un-set would be a delete that syncing could undo.
            if write.deleted and target.deleted_at is None:
                target.deleted_at = written_at

    _apply_hike(db, current_user, payload, written_at)
    db.commit()

    # AFTER the uploads and after the commit, so a device's own writes come
    # back with the stamps it must record - and a row written by a third
    # device between here and the client storing the watermark has an
    # `updated_at` past this one, so it arrives on the next sync rather than
    # being skipped.
    now = utc_now()
    changed = db.scalars(
        select(SyncedTrip)
        .where(
            SyncedTrip.profile_id == current_user.id,
            *([] if payload.since is None else [SyncedTrip.updated_at > to_naive_utc(payload.since)]),
        )
        .order_by(SyncedTrip.updated_at)
    ).all()

    hike_row = db.get(SyncedPlannedHike, current_user.id)

    return TripSyncOut(
        now=now,
        trips=[
            TripOut(
                id=row.id,
                document=row.document,
                updated_at=row.updated_at,
                deleted_at=row.deleted_at,
            )
            for row in changed
        ],
        hike=(
            None
            if hike_row is None
            else PlannedHikeOut(
                start_mile=hike_row.start_mile,
                end_mile=hike_row.end_mile,
                updated_at=hike_row.updated_at,
            )
        ),
        conflicts=conflicts,
    )


def _apply_hike(db: Session, profile: Profile, payload: TripSyncIn, written_at) -> None:
    """The planned hike, which is the one thing here that does NOT keep both.

    Two trips a hiker planned are two plans and both can be real. Two answers
    to "where am I walking, right now" are not - so this is last write wins,
    and being wrong costs re-entering two numbers rather than a fortnight of
    planning. `app/models/synced_trip.py` argues it at length.

    "Last write" is still resolved without comparing clocks: the device's
    `base_updated_at` against the stored stamp, exactly as trips do it. A
    device whose base is stale loses, because the other device wrote more
    recently *as this server saw it*.
    """
    if payload.hike is None:
        return

    row = db.get(SyncedPlannedHike, profile.id)
    if row is None:
        db.add(
            SyncedPlannedHike(
                profile_id=profile.id,
                start_mile=payload.hike.start_mile,
                end_mile=payload.hike.end_mile,
                updated_at=written_at,
            )
        )
        return

    if to_naive_utc(payload.hike.base_updated_at) != row.updated_at:
        # Somebody else moved it since this device looked. The stored answer
        # stands, and the device adopts it from the response.
        return

    row.start_mile = payload.hike.start_mile
    row.end_mile = payload.hike.end_mile
    row.updated_at = written_at
