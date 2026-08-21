"""The `synced_trips` table - a hiker's saved plans, following the account.

Phase B of ../../../features/ACCOUNT_SYNC.md (#892). A section hiker lays
out four days on a laptop and leaves with a phone, and until this table the
laptop's plan did not exist on the phone in any form: `ourhike:trips` lives
in one browser's IndexedDB and nowhere else.

WHY THIS IS NOT `user_preferences`' SHAPE, AND WHERE IT DIVERGES

`app/models/preferences.py` established the pattern this follows in one
respect and deliberately breaks in another. It follows it in storage: the
trip DOCUMENT is a JSON column, because it is client-owned, syncs wholesale
per trip, and nothing here queries inside it - no route filters "trips where
day 3 is longer than twelve miles". The client-side model can gain a field
without a migration on this table.

It breaks it in grain. Preferences are one blob per hiker, replaced whole.
Trips are MANY, and a sync that shipped the whole collection every time
would be a full upload of every trip a hiker has ever planned on every run.
So `id`, `updated_at` and `deleted_at` are real columns rather than keys
inside the document: they are precisely the three things the sync QUERIES
on, and a JSON blob you have to open to find the changed rows is not a
delta.

WHY THERE IS A `deleted_at` AND NOT A `DELETE`

The doc's rule, and it is not negotiable: **a delete travels only as the
hiker's own delete, never as an absence inferred from one device's
silence.** A phone that has not synced since March is not evidence that
March's trips are gone - it is evidence of a phone in a rucksack. A row that
vanished would be indistinguishable from a row a device has not heard about
yet, so a deletion has to be a thing that EXISTS in order to travel.

The tombstone keeps the id and drops the document, which is the other half:
what a hiker deleted is not something this table should go on holding.

WHY THE ID IS THE CLIENT'S

`lib/trips.ts` mints a trip's id when the hiker saves it, offline, possibly
weeks before an account exists. Re-keying it here would mean every device
holding a mapping from its own ids to ours, which is a second identity to
keep in step and a new way to lose a plan. `app/models/hike.py` already
takes the same position for the same reason.

The cost is that an id arrives from outside, so `profile_id` is checked on
every write rather than assumed: an id that exists and belongs to somebody
else must not be writable, and must not be reported as existing either -
`app/routers/hikes.py`'s 404-not-403 rule, for the same reason.
"""

from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, Index, String

from app.core.time import utc_now
from app.db.base import Base


class SyncedTrip(Base):
    __tablename__ = "synced_trips"

    #: The client's own trip id (`lib/trips.ts`). See the module docstring.
    id = Column(String, primary_key=True)

    profile_id = Column(String, ForeignKey("profiles.id"), nullable=False)

    #: The trip as the client holds it - name, plan, `recorded`. Null on a
    #: tombstone: what a hiker deleted is not something to go on holding.
    document = Column(JSON, nullable=True)

    #: Server-assigned on every write, and the sync's whole ordering. Never
    #: the client's clock: two devices' clocks disagree, and this is the
    #: value both of them compare against to decide what is new.
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)

    #: When the hiker deleted it, or null. Set once and never cleared - a
    #: tombstone that could be un-set would be a delete that a slow device
    #: could undo by syncing.
    deleted_at = Column(DateTime, nullable=True)


# The sync's only query: this hiker's rows, changed since a watermark. Both
# columns together, because `profile_id` alone would scan a hiker's whole
# history to answer "what is new" - which is the question every sync asks and
# the one this table exists to answer cheaply.
Index("ix_synced_trips_profile_updated", SyncedTrip.profile_id, SyncedTrip.updated_at)


class SyncedPlannedHike(Base):
    """The hike a person says they are on - two numbers, following the account.

    Its own table rather than a row in `synced_trips`, because it is not a
    trip and does not have a trip's grain: `lib/plannedHike.ts` holds a
    singleton with no id at all, and giving it one so it could ride in a
    collection would be inventing an identity to fit a container.

    **It is also the one thing here that does NOT keep both on a conflict**,
    and that is why it is visibly separate rather than quietly mixed in. Two
    trips a hiker planned are two plans, and both can be real. Two answers to
    "where am I walking, right now" are not: the hiker is on one hike, and
    presenting them with two would be the app asking a question it invented.
    So this is last-write-wins, and being wrong costs re-entering two numbers.

    NOT the `hikes` table, which stays exactly what `app/models/hike.py` says
    it is - the durable start/end reference the wrong-way alert reads
    server-side. That table is complete CRUD over a COLLECTION with ids, so
    syncing a singleton through it would mean every device remembering which
    row is "the" one: a second identifier to keep in step, and a second
    `updated_at` clock for one hiker's state. #247 is the feature that wants
    the server to know a hike; this is the feature that wants two devices to
    agree on one.
    """

    __tablename__ = "synced_planned_hikes"

    profile_id = Column(String, ForeignKey("profiles.id"), primary_key=True)

    #: Miles from the southern terminus. BOTH null means the hiker cleared
    #: their planned hike - which is a decision with a date on it, not an
    #: absence, so the row stays and `updated_at` records when. A missing row
    #: means "never synced one", and the two are different claims.
    start_mile = Column(Float, nullable=True)
    end_mile = Column(Float, nullable=True)

    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)
