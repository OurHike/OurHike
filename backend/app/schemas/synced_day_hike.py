"""What a device sends and receives when its day hikes follow the account (#976).

The trip exchange's shapes (`schemas/synced_trip.py`), minus the planned-hike
singleton, over the day-hike table. One exchange rather than a read endpoint
and a write endpoint, and a document carried opaquely rather than
re-declared here, for the reasons that file argues at length - a day hike's
document is client-owned the same way a trip's is, and a second definition
of it on this side of the wire would be a second definition to drift.

A separate module rather than reused Trip* classes with a different route,
because these are different wire contracts that must be free to diverge:
the first field a day-hike document exchange needs that a trip's does not
must not be a change to what deployed trip clients parse.
`app/models/synced_day_hike.py` is the argument for the separation itself.
"""

from pydantic import BaseModel, ConfigDict, Field

from app.core.time import UtcDatetime


class DayHikeUpload(BaseModel):
    """One day hike a device is offering."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    #: The day hike as the client holds it. Null when this upload is a
    #: deletion - what a hiker deleted is not something to go on sending.
    document: dict | None = None
    #: The server stamp this device last saw for this day hike. Null means
    #: the device believes it is new. `core/trip_sync.py` explains why this
    #: is the conflict test rather than any comparison of clocks.
    base_updated_at: UtcDatetime | None = None
    deleted: bool = False


class DayHikeOut(BaseModel):
    """One day hike as the server holds it now."""

    id: str
    #: Null on a tombstone, which is a row a device must ACT on rather than
    #: ignore: it is how the hiker's own delete reaches another device.
    document: dict | None
    updated_at: UtcDatetime
    deleted_at: UtcDatetime | None


class DayHikeSyncIn(BaseModel):
    """A device's whole side of the exchange."""

    model_config = ConfigDict(extra="forbid")

    #: The watermark from this device's last successful sync, or null on its
    #: first. Null asks for everything, INCLUDING tombstones - a device that
    #: has never synced has no way to know a day hike was deleted except by
    #: being told (`schemas/synced_trip.py`, same field, same reason).
    since: UtcDatetime | None = None
    day_hikes: list[DayHikeUpload] = Field(default_factory=list, max_length=500)


class DayHikeSyncOut(BaseModel):
    """Everything that changed elsewhere, plus the next watermark.

    `now` is taken after the uploads have landed, so a row written by a third
    device in between comes back on the NEXT sync rather than being skipped -
    a watermark that could skip a row is a watermark that silently loses a
    day hike.
    """

    now: UtcDatetime
    day_hikes: list[DayHikeOut]
    #: How many day hikes this exchange kept beside an existing one rather
    #: than overwriting it - reported for the same auditability reason
    #: `TripSyncOut.conflicts` is (#894 is the surface that says it out loud).
    conflicts: int
