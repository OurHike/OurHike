"""Wire shapes for community waypoint photos (#576).

The public read contract is deliberately narrower than the row. What the
gallery serves is what the card prints and nothing more: a URL, a month, a
credit, a licence, and whether the club pinned it. The exact capture date
never crosses the wire - the card shows month precision anyway
(POI_PHOTOS.md's honesty rule), and while the anonymity window holds, the
name is withheld too, which is HIKER_SAFETY.md §2's "name and exact date"
masking applied at the only precision this surface ever had.
"""

from datetime import date, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

from app.core.time import UtcDatetime, utc_now
from app.models.poi_photo import PoiPhoto

# How far past today (UTC) a capture date may sit before it is a date the
# photo cannot have. A whole day rather than reports' five minutes, because
# this is a DATE and the phone's midnight is not the server's -
# `VolunteerHoursCreate.worked_on`'s allowance, for its reason.
CAPTURE_DATE_LEEWAY = timedelta(days=1)


class PoiPhotoShare(BaseModel):
    """What a share carries besides the bytes: the capture-date claim, and
    what the on-device check found.

    Nothing else is the client's to say. Attribution comes from the
    sharer's profile, the licence from the design, the timestamps from the
    server - a share that could name its own attribution would be a share
    sheet able to sign someone else's name.

    `flagged` is the phone's own claim about its own photo (#837), and it
    can only make things MORE reviewed, never less: 'faces' sorts the queue,
    'nudity' holds the photo for one human glance. A client lying "nothing
    found" gets exactly the report-driven posture every photo has anyway.
    """

    taken: date | None = None
    flagged: Literal["nudity", "faces"] | None = None

    @field_validator("taken")
    @classmethod
    def _a_capture_date_from_the_future_is_no_date(cls, value: date | None) -> date | None:
        """A `taken` past tomorrow is dropped, and the photo dates by its share.

        The model's own comment calls `taken` "a claim... the server has no
        way to check", which is true of the past and false of the future: a
        photo cannot have been taken after it was shared. And the claim is
        not decoration. `_recency()` (routers/poi_photos.py) orders the
        rolling window by `coalesce(taken, shared_at)`, so a share claiming
        9999-12-31 listed first in a place's gallery ahead of a photo shared
        after it, would have held one of the twelve slots for as long as it
        existed, and answered `taken_month: "9999-12"` for the card to
        print - measured on the unfixed tree, 2026-09-17, by the two cases
        in `tests/test_poi_photos.py` that now hold the opposite.

        DROPPED RATHER THAN REFUSED, which is the opposite of what
        `ReportCreate.authored_at` does with a future time, and deliberately.
        A report's authored time is the report's substance - a moderation
        queue is read by it - so a wrong one is refused and the hiker is told
        to check the clock. A capture date is a month on a card plus a sort
        key, and the share stands without it: "omit rather than guess" gives
        the photo the one date this server can stand behind, the share
        month, exactly as a photo whose original carried no EXIF date is
        dated. A 422 would instead strand the share in the outbox with the
        client's "this app is too old" message (`permanentFailureReason`,
        lib/api.ts), over a camera clock that runs ahead.
        """
        if value is None or value <= utc_now().date() + CAPTURE_DATE_LEEWAY:
            return value
        return None


class PoiPhotoReport(BaseModel):
    """Why a hiker reported a photo (#579's report-this-photo path).

    Three reasons, from the report sheet: it is not this place; somebody in
    it did not agree to this ('person' - sorts to the top of the queue); it
    should not be public for any other reason.
    """

    reason: Literal["wrong_place", "person", "other"]


class PoiPhotoOut(BaseModel):
    """One gallery entry, as the card renders it."""

    model_config = ConfigDict(from_attributes=False)

    id: str
    poi_id: str
    # A short-lived signed URL for the bytes (app/core/photos.py). Minted per
    # response; a stored URL would be a bearer token with no expiry.
    url: str
    # "YYYY-MM": capture month where the original carried a date, else the
    # month it was shared. Never absent - dating the photo is the honesty
    # rule, and the share month always exists.
    taken_month: str
    # The trail name the photographer asked to be credited as, or null while
    # their anonymity window holds. Null is "withheld by the photographer's
    # request", never "unknown" - a share without a trail name is refused.
    attribution: str | None
    license: str
    pinned: bool

    @classmethod
    def from_row(cls, photo: PoiPhoto, url: str) -> "PoiPhotoOut":
        masked = photo.masked_until is not None and photo.masked_until > utc_now()
        taken_month = photo.taken.strftime("%Y-%m") if photo.taken is not None else photo.shared_at.strftime("%Y-%m")
        return cls(
            id=photo.id,
            poi_id=photo.poi_id,
            url=url,
            taken_month=taken_month,
            attribution=None if masked else photo.attribution_name,
            license=photo.license,
            pinned=photo.pinned_at is not None,
        )


class PoiPhotoModerationOut(PoiPhotoOut):
    """A queue row: the public shape plus what a moderator's decision needs.

    The trail name stays masked here exactly as it is on the card - the
    queue mockup shows the withheld state to the moderator rather than the
    name, and a moderator judges the photograph, not the photographer. What
    is added is the machinery: when it was offered, what the phone flagged,
    whether it is held from the gallery, and what a hiker reported.
    """

    shared_at: UtcDatetime
    masked_until: UtcDatetime | None
    flagged: str | None
    # True while a nudity flag waits on its one human glance - the only
    # state in this feature where a photo exists and nobody can see it.
    held: bool
    reported_reason: str | None
    reported_at: UtcDatetime | None
    # How many times a moderator has taken down this contributor's photo of
    # this place (#1551): the ledger's count for the pair, which outlives the
    # row being replaced or withdrawn. Zero for a first-time share; on the
    # answer to a dismissal it counts that dismissal too. Additive on the
    # wire, so a client that does not read it is unaffected.
    dismissal_count: int = 0

    @classmethod
    def from_moderation_row(cls, photo: PoiPhoto, url: str, dismissal_count: int = 0) -> "PoiPhotoModerationOut":
        base = PoiPhotoOut.from_row(photo, url)
        return cls(
            **base.model_dump(),
            shared_at=photo.shared_at,
            masked_until=photo.masked_until,
            flagged=photo.flagged,
            held=photo.flagged == "nudity" and photo.reviewed_at is None,
            reported_reason=photo.reported_reason,
            reported_at=photo.reported_at,
            dismissal_count=dismissal_count,
        )
