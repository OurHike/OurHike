"""The `synced_hikes` table - a hiker's long hikes, following the account.

#1317. The `Hike` that groups sections became a real object - a trail, an
ordered list of points, a status - and until this table it lived only inside
one browser's `ourhike:trips` document. The design handoff asks for
`activeHikeId` to sync, and a pointer that syncs while the thing it points
at does not is a pointer to nothing: the second device receives an id naming
a hike it has never heard of.

WHY ITS OWN TABLE, NOT ROWS IN `synced_trips`

`app/models/synced_day_hike.py` settled this shape of question already and
the argument transfers without change: `/trips/sync` returns every row for
the profile past the watermark with nothing to filter on, so hikes mixed
into `synced_trips` would ride back through the exchange deployed clients
already consume, to be mis-filed as trips by `client/src/lib/tripsSync.ts`
on every sync. A hike's document has a `points` list where a trip has a
`plan`, and `validateTripStore` would drop it - silently, on every device
running a shipped build.

WHY THIS DOES NOT KEEP BOTH, WHERE A TRIP DOES

This is the decision a reviewer should weigh, because `synced_trips` sits
next to it doing the opposite.

**A hike's `tripIds` claim sections, and a section belongs to exactly one
hike.** features/SEGMENTS.md models a hike as the root of a tree and a tree
has one parent per node; `client/src/lib/trips.ts`'s `addHike` enforces it
actively, releasing any section a new hike claims from whichever hike had
it. A server-minted copy would produce two hikes claiming the same sections
- the one state the model says cannot exist - and `hikeOfTrip` answers such
a question by returning whichever it finds first, so which hike a section
belonged to would become arbitrary.

**The irreplaceable half is already protected.** What a hiker cannot
reconstruct is the planning: the days, the stops, the resupply. That is a
trip document and `resolve_upload` keeps both copies of it. A hike is the
way of looking at those sections - `removeHike`'s own words, "a hike is a
way of looking at sections, and throwing away the way of looking must never
throw away the walking." Duplicating the way of looking costs a hiker a
cleanup behind a confirm dialog and saves them nothing they had lost.

So this is last-write-wins on the same base-stamp test the planned hike uses
(`SyncedPlannedHike`), and being wrong costs re-entering a point list rather
than a fortnight of planning. That is a real cost and it is named here
rather than hidden: a hiker who lays out a flip-flop's points on a laptop
while a phone edits the same hike loses one of those edits.

DELETIONS STILL TRAVEL, which is why there is a `deleted_at` here at all
despite the rule above being last-write-wins. features/ACCOUNT_SYNC.md's
line is not negotiable and does not bend for a grouping: a hike forgotten on
the laptop has to reach the phone as the hiker's own act, and a row that
simply vanished would be indistinguishable from a row the device has not
heard about yet.
"""

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Index, String

from app.core.time import utc_now
from app.db.base import Base


class SyncedHike(Base):
    __tablename__ = "synced_hikes"

    #: The client's own hike id (`client/src/lib/hikes.ts`). Minted offline,
    #: possibly weeks before an account exists - `app/models/synced_trip.py`
    #: carries the full argument for why it is not re-keyed here.
    id = Column(String, primary_key=True)

    profile_id = Column(String, ForeignKey("profiles.id"), nullable=False)

    #: The hike as the client holds it - name, type, trailId, points, status,
    #: tripIds. Opaque here for `synced_trips`' reason: the client owns the
    #: shape, validates it on read, and changes it more often than this table
    #: wants migrating. Null on a tombstone.
    document = Column(JSON, nullable=True)

    #: Server-assigned on every write, and the sync's whole ordering. Never
    #: the client's clock.
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)

    #: Set once when the hiker forgets the hike, and never cleared.
    deleted_at = Column(DateTime, nullable=True)


#: The sync's only query: this hiker's rows, changed since a watermark.
Index("ix_synced_hikes_profile_updated", SyncedHike.profile_id, SyncedHike.updated_at)


class SyncedActiveHike(Base):
    """Which long hike the app is in - one id, following the account.

    A SINGLETON PER HIKER, so it takes `SyncedPlannedHike`'s shape rather
    than a row in `synced_hikes`: there is no id to give it that is not
    already the id it holds, and putting it in the collection would mean
    every device working out which row is "the" pointer.

    Last write wins, and the handoff says why in one line: a hiker is on one
    hike, and offering them two would be the app asking a question it
    invented. Being wrong costs one tap.

    A NULL `hike_id` IS A REAL ANSWER and is why the column is nullable
    rather than the row being deleted: it is the hiker leaving the long-hike
    state deliberately, which is a decision with a date on it. A MISSING row
    means this account has never said, and the two are different claims -
    exactly the distinction `SyncedPlannedHike` draws between both miles null
    and no row at all.
    """

    __tablename__ = "synced_active_hikes"

    profile_id = Column(String, ForeignKey("profiles.id"), primary_key=True)

    #: Not a ForeignKey to `synced_hikes.id`, deliberately. A device can send
    #: the pointer in the same exchange as the hike it names, and ordering
    #: the two writes to satisfy a constraint would make the pointer fail for
    #: a reason the hiker cannot act on. The client already refuses a pointer
    #: it cannot honour (`setActiveHike`), and `validateTripStore` falls back
    #: to null on read, so a dangling id costs one tap rather than an error.
    hike_id = Column(String, nullable=True)

    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)
