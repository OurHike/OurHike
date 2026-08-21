"""What a device sends and receives when its trips follow the account (#892).

One exchange rather than a read endpoint and a write endpoint, because a
sync IS one exchange: a device offers what it changed and asks what changed
elsewhere, and splitting that into two round trips would open a window in
which the answer to the second no longer matches the first.

WHAT IS AND IS NOT VALIDATED HERE, WHICH DIFFERS FROM PREFERENCES

`schemas/preferences.py` validates every field of its blob as strictly as a
relational table would, and says so. This one deliberately does not, and the
difference is worth stating rather than looking like an omission.

A preferences blob is a fixed, small set of enums the backend can enumerate,
and a value nothing can render is a value nothing should store. A trip
document is `HikePlan` - stops, days, resupply, a timeline - a structure that
`client/src/lib/plan.ts` owns, validates on read, and changes far more often
than this table wants migrating. Re-declaring it here would create a second
definition to drift from the first, and the drift would surface as a hiker's
plan being rejected by their own account.

So the document is carried opaquely, and the invariants that DO live here
are the ones this table's own machinery depends on: the id, the stamps, and
the deletion flag. `client/src/lib/trips.ts`'s `validateTripStore` is the
reader that refuses a plan it cannot understand, and it refuses per trip
rather than per store precisely so one unreadable trip is not every trip.
"""

from pydantic import BaseModel, ConfigDict, Field

from app.core.time import UtcDatetime


class TripUpload(BaseModel):
    """One trip a device is offering."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    #: The trip as the client holds it. Null when this upload is a deletion -
    #: what a hiker deleted is not something to go on sending.
    document: dict | None = None
    #: The server stamp this device last saw for this trip. Null means the
    #: device believes the trip is new. `core/trip_sync.py` explains why this
    #: is the conflict test rather than any comparison of clocks.
    base_updated_at: UtcDatetime | None = None
    deleted: bool = False


class TripOut(BaseModel):
    """One trip as the server holds it now."""

    id: str
    #: Null on a tombstone, which is a row a device must ACT on rather than
    #: ignore: it is how the hiker's own delete reaches another device.
    document: dict | None
    updated_at: UtcDatetime
    deleted_at: UtcDatetime | None


class PlannedHikeSync(BaseModel):
    """The two numbers, with the stamp that orders them.

    Both miles null is the hiker having CLEARED their planned hike - a
    decision with a date on it. The whole object being null is a device
    saying nothing about it, which is a different claim and is why this is
    nullable at the envelope rather than defaulted here.
    """

    model_config = ConfigDict(extra="forbid")

    start_mile: float | None = None
    end_mile: float | None = None
    #: What the device last saw. Null when it has never synced one.
    base_updated_at: UtcDatetime | None = None


class PlannedHikeOut(BaseModel):
    start_mile: float | None
    end_mile: float | None
    updated_at: UtcDatetime


class TripSyncIn(BaseModel):
    """A device's whole side of the exchange."""

    model_config = ConfigDict(extra="forbid")

    #: The watermark from this device's last successful sync, or null on its
    #: first. Null asks for everything, INCLUDING tombstones: a device that
    #: has never synced has no way to know a trip was deleted except by being
    #: told, and telling it nothing would leave it re-uploading the deleted
    #: trip for ever.
    since: UtcDatetime | None = None
    trips: list[TripUpload] = Field(default_factory=list, max_length=500)
    #: Omitted when the device has nothing to say about the planned hike.
    #: Distinct from a hike whose miles are both null, which is the hiker
    #: having cleared it.
    hike: PlannedHikeSync | None = None


class TripSyncOut(BaseModel):
    """Everything that changed elsewhere, plus the next watermark.

    `now` is taken by the server after the uploads have landed and before
    the read, so a row written by a third device in between comes back on the
    NEXT sync rather than being skipped. A watermark that could skip a row is
    a watermark that silently loses a trip.
    """

    now: UtcDatetime
    trips: list[TripOut]
    hike: PlannedHikeOut | None
    #: How many trips this exchange kept beside an existing one rather than
    #: overwriting it. Reported because a conflict is a thing that HAPPENED to
    #: a hiker's data, and a sync that resolves one silently is a sync nobody
    #: can audit - #894 is the surface that will say it out loud.
    conflicts: int
