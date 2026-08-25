"""The `synced_day_hikes` table - a hiker's day hikes, following the account.

#976 - Day hikes get account sync from day one (the maintainer's decision,
2026-08-25): the day-hike planner ships with sync rather than growing it
later, so there is no generation of devices holding day hikes that only
exist locally. The machinery is features/ACCOUNT_SYNC.md phase B's exchange,
already built and argued for trips - `app/models/synced_trip.py` carries the
full case for the client-minted id, the opaque JSON document, the
server-assigned `updated_at`, and the tombstone that a delete has to BE in
order to travel. A day hike is the same kind of thing a trip is (a
client-owned document with an id the client minted), so every one of those
arguments transfers, and this module refers to them rather than restating
them.

WHY THIS IS ITS OWN TABLE AND NOT A `kind` COLUMN IN `synced_trips`

Because `/trips/sync` answers with EVERY row for the profile past the
watermark, and the row carries nothing a deployed client could filter on.
Mix day hikes into `synced_trips` and each one rides back to every device
through the exchange that already shipped - where
`client/src/lib/tripsSync.ts`'s `tripFrom` validates each returned document
as a trip and drops what does not validate. So a day hike in that table is,
on a deployed phone, either re-sent and silently re-dropped on every sync
for ever, or - if its document happens to pass `validatePlan` - filed in
the hiker's TRIP list as a trip. A separate table under a separate route
(`/day-hikes/sync`) is what makes "deployed clients never receive a
day-hike document through `/trips/sync`" a property of the schema rather
than a discipline.

The cost is a second copy of a five-column shape. The conflict rule is NOT
copied: `app/core/trip_sync.resolve_upload` is dataclass-generic and both
routers call the same one, so keep-both cannot drift between the two kinds.

There is no day-hike counterpart to `SyncedPlannedHike`. That table exists
because the planned hike is a singleton with no id; day hikes are a
collection exactly like trips, so this module has one table, not two.
"""

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Index, String

from app.core.time import utc_now
from app.db.base import Base


class SyncedDayHike(Base):
    __tablename__ = "synced_day_hikes"

    #: The client's own day-hike id, minted when the hiker saves it, possibly
    #: offline and before an account exists - the position `synced_trips`
    #: (and `app/models/hike.py` before it) already takes, for the reasons
    #: `app/models/synced_trip.py` gives. An id that arrives from outside
    #: means `profile_id` is checked on every write, never assumed.
    id = Column(String, primary_key=True)

    profile_id = Column(String, ForeignKey("profiles.id"), nullable=False)

    #: The day hike as the client holds it, carried opaquely. Null on a
    #: tombstone: what a hiker deleted is not something to go on holding.
    document = Column(JSON, nullable=True)

    #: Server-assigned on every write, and the sync's whole ordering. Never
    #: the client's clock - `app/models/synced_trip.py` says why.
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)

    #: When the hiker deleted it, or null. Set once and never cleared - a
    #: tombstone that could be un-set would be a delete that a slow device
    #: could undo by syncing.
    deleted_at = Column(DateTime, nullable=True)


# The sync's only query, same as ix_synced_trips_profile_updated: this
# hiker's rows, changed since a watermark. Both columns together, because
# `profile_id` alone would scan a hiker's whole history to answer "what is
# new" - the question every sync asks.
Index(
    "ix_synced_day_hikes_profile_updated",
    SyncedDayHike.profile_id,
    SyncedDayHike.updated_at,
)
