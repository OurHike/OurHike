"""`/day-hikes/sync` - one exchange that carries a hiker's day hikes between devices.

#976, the maintainer's decision that day hikes sync from day one. This is
`app/routers/synced_trips.py` over `synced_day_hikes`, minus the planned-hike
singleton - one endpoint, not CRUD, for the reasons that file gives.

ITS OWN ROUTE, NOT MORE ROWS THROUGH `/trips/sync`, because deployed clients
already consume that exchange and validate every returned document as a
trip: `app/models/synced_day_hike.py` walks through what would happen to a
day hike arriving there. The route boundary is what keeps the two kinds
apart on every deployed phone that predates day hikes.

THE CONFLICT RULE IS SHARED, NOT MIRRORED. `app/core/trip_sync.resolve_upload`
takes dataclasses that carry nothing trip-specific, and keep-both / tombstones
travel / base_updated_at-not-clocks is the same rule for any collection of
client-owned documents - so both routers call the one implementation, and a
fix to it fixes both exchanges. The one trip-flavoured edge inside it:
`name_for_copy` falls back to "Untitled trip" for a document with no name.
A day-hike conflict copy hits that fallback only if the document carries no
"name" key at all; tolerated rather than forked, because forking the rule to
rename a fallback would buy a second copy of the code this module exists not
to have.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.time import to_naive_utc, utc_now
from app.core.trip_sync import StoredTrip, UploadedTrip, resolve_upload
from app.db.session import get_db
from app.models.profile import Profile
from app.models.synced_day_hike import SyncedDayHike
from app.schemas.synced_day_hike import DayHikeOut, DayHikeSyncIn, DayHikeSyncOut

router = APIRouter(prefix="/day-hikes", tags=["day-hikes"])


def _owned(db: Session, profile: Profile, ids: list[str]) -> dict[str, SyncedDayHike]:
    """This hiker's rows among the ids offered, keyed by id.

    Scoped by `profile_id` in the query rather than filtered afterwards, so
    an id belonging to somebody else simply is not here - the upload naming
    it would land as a new row under a primary key that already exists, so
    the collision is checked explicitly below and the upload dropped.
    Dropping rather than 409ing is `app/routers/synced_trips.py._owned`'s
    call, made there in full: a stranger's colliding UUID is nothing a hiker
    can act on, and naming it would answer a question nobody should be able
    to ask (`app/routers/hikes.py`'s 404-not-403 rule).
    """
    if not ids:
        return {}
    rows = db.scalars(
        select(SyncedDayHike).where(
            SyncedDayHike.profile_id == profile.id,
            SyncedDayHike.id.in_(ids),
        )
    ).all()
    return {row.id: row for row in rows}


def _foreign_ids(db: Session, profile: Profile, ids: list[str]) -> set[str]:
    """Ids that exist and belong to somebody else. See `_owned`."""
    if not ids:
        return set()
    rows = db.scalars(
        select(SyncedDayHike.id).where(
            SyncedDayHike.id.in_(ids),
            SyncedDayHike.profile_id != profile.id,
        )
    ).all()
    return set(rows)


@router.post("/sync", response_model=DayHikeSyncOut)
def sync_day_hikes(
    payload: DayHikeSyncIn,
    current_user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DayHikeSyncOut:
    ids = [day_hike.id for day_hike in payload.day_hikes]
    mine = _owned(db, current_user, ids)
    theirs = _foreign_ids(db, current_user, ids)

    written_at = utc_now()
    conflicts = 0

    for upload in payload.day_hikes:
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
                # rule sees it, exactly as the trips router does - an aware
                # value never equals a naive one, so skipping this would
                # resolve every ordinary edit as a conflict and bury the
                # hiker in copies (`app/routers/synced_trips.py` in full).
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
                target = SyncedDayHike(id=write.id, profile_id=current_user.id)
                db.add(target)
                mine[write.id] = target
            target.document = write.document
            target.updated_at = written_at
            # Set once and never cleared: a tombstone a slow device could
            # un-set would be a delete that syncing could undo.
            if write.deleted and target.deleted_at is None:
                target.deleted_at = written_at

    db.commit()

    # AFTER the uploads and after the commit, so a device's own writes come
    # back with the stamps it must record - and a row written by a third
    # device between here and the client storing the watermark arrives on
    # the next sync rather than being skipped.
    now = utc_now()
    changed = db.scalars(
        select(SyncedDayHike)
        .where(
            SyncedDayHike.profile_id == current_user.id,
            *([] if payload.since is None else [SyncedDayHike.updated_at > to_naive_utc(payload.since)]),
        )
        .order_by(SyncedDayHike.updated_at)
    ).all()

    return DayHikeSyncOut(
        now=now,
        day_hikes=[
            DayHikeOut(
                id=row.id,
                document=row.document,
                updated_at=row.updated_at,
                deleted_at=row.deleted_at,
            )
            for row in changed
        ],
        conflicts=conflicts,
    )
