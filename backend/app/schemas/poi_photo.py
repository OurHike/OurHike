"""Wire shapes for community waypoint photos (#576).

The public read contract is deliberately narrower than the row. What the
gallery serves is what the card prints and nothing more: a URL, a month, a
credit, a licence, and whether the club pinned it. The exact capture date
never crosses the wire - the card shows month precision anyway
(POI_PHOTOS.md's honesty rule), and while the anonymity window holds, the
name is withheld too, which is HIKER_SAFETY.md §2's "name and exact date"
masking applied at the only precision this surface ever had.
"""

from datetime import date

from pydantic import BaseModel, ConfigDict

from app.core.time import utc_now
from app.models.poi_photo import PoiPhoto


class PoiPhotoShare(BaseModel):
    """What a share carries besides the bytes: the capture-date claim.

    Nothing else is the client's to say. Attribution comes from the
    sharer's profile, the licence from the design, the timestamps from the
    server - a share that could name its own attribution would be a share
    sheet able to sign someone else's name.
    """

    taken: date | None = None


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
