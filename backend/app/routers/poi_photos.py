"""`/waypoints/{poi_id}/photos` - the community photo gallery behind rung 2.

See ../../../features/POI_PHOTOS.md ("Source 3: sharing, and becoming the
default") and #576. Browsing needs no account, matching every other browsing
endpoint; sharing and withdrawing require the identity the attribution and
the withdrawal promise both hang off.

The write path is the outbox's two-phase flush, the same shape report photos
use (#369): POST creates or replaces the caller's share row, PUT lands the
bytes. Either half retries safely - the row upserts on its (poi, contributor)
identity, and the object overwrites at its derived key.

What a hiker can do here: share, upload, withdraw, and report somebody
else's photo (#579's report path - the mechanism that keeps the rolling
twelve safe without pre-approval). The moderator's half - pin, unpin,
review, refuse - lives with the rest of the moderation workflow in
app/routers/moderation.py, the one review mechanism this app has.

Screening (#837) is not a gate anywhere by decision. What this path carries
of it is the phone's own flag arriving with a share, and the one narrow
consequence the queue mockups drew: a nudity flag holds the photo from the
gallery until one human glance. Held is not refused - the share succeeded,
the queue has it, and a moderator decides.
"""

import re
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import Date, cast, func, or_
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.orm import commit_and_refresh
from app.core.photos import (
    ALLOWED_CONTENT_TYPE,
    JPEG_MAGIC,
    MAX_PHOTO_BYTES,
    PhotoStorageUnavailable,
    delete_photo_object,
    photo_storage_configured,
    photo_uploads_enabled,
    poi_photo_key,
    presigned_object_url,
    store_photo_object,
)
from app.core.time import utc_now
from app.db.session import get_db
from app.models.poi_photo import PoiPhoto, PoiPhotoStatus
from app.models.preferences import UserPreferences
from app.models.profile import Profile
from app.routers.reports import read_capped_body
from app.schemas.poi_photo import PoiPhotoOut, PoiPhotoReport, PoiPhotoShare

router = APIRouter(prefix="/waypoints/{poi_id}/photos", tags=["poi-photos"])

# The gallery's shape (POI_PHOTOS.md, decided 2026-08-09): at most 3 pinned
# by the maintaining club, the 12 most recent community photos rolling
# beneath them, 15 total. The 12 ROLL so a gallery of a burned-down shelter
# heals within a season; a hard first-come cap would hold fifteen photographs
# of a building that no longer exists. PINNED_MAX is enforced where pinning
# happens (#579); ROLLING_WINDOW is enforced here, at upload, where the
# thirteenth photo arrives.
PINNED_MAX = 3
ROLLING_WINDOW = 12

# The cooling-off window (#577, drawn in the maintainer-adopted share-sheet
# mockups and settled here): a shared photo goes public TWO HOURS after its
# bytes land. Inside the window a withdrawal is a true undo - nobody ever
# saw the photo, so no copy exists and the CC licence has reached no one;
# after it, withdrawal remains available forever but stops being an undo.
# POI_PHOTOS.md sketched "hours, not days... a delay nobody would notice,
# since moderation already sits in that path", and two hours is that shape:
# the doc's own regret case is minutes-scale, and a gallery two hours
# behind the newest snapshot is a lag no hiker's decision turns on.
# Photos are never safety-relevant, so nothing time-critical is delayed.
COOLING_OFF_HOURS = 2

# What a POI id may look like before it goes into an object key. The real
# ids are the pipeline's "source:identifier" strings ("atc_shelters:abc");
# the guard exists because this is client-supplied text entering
# `poi-photos/{poi_id}/...`, and a slash or a dot-dot in it would let a
# caller address objects outside their derived key. Refused as not-found
# rather than catalogued: an id this store would never hold has no photos.
_POI_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9:_\-.]{0,127}")


def _checked_poi_id(poi_id: str) -> str:
    if _POI_ID_PATTERN.fullmatch(poi_id) is None or ".." in poi_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such waypoint.")
    return poi_id


def _anonymity_window_days(db: Session, profile_id: str) -> int:
    """The sharer's anonymity window, in days. Zero when unset - masking is
    opt-in, and the client's own default is 0 (lib/userPreferences.ts)."""
    stored = db.get(UserPreferences, profile_id)
    if stored is None or not isinstance(stored.data, dict):
        return 0
    days = stored.data.get("anonymity_window_days", 0)
    if not isinstance(days, int) or days < 0:
        return 0
    return days


def _recency():
    """The rolling window's ordering key: capture date where claimed, else
    the share date. The same date the card prints, so what the gallery
    serves and what it evicts cannot disagree about which photo is newer."""
    return func.coalesce(PoiPhoto.taken, cast(PoiPhoto.shared_at, Date))


def _held():
    """A nudity flag waiting on its one human glance (#837): the photo
    exists, the queue can see it, and the gallery may not - the narrow hold
    the decided posture allows, reaching only what the phone itself
    flagged."""
    return (PoiPhoto.flagged == "nudity") & PoiPhoto.reviewed_at.is_(None)


def _not_held():
    """The gallery-side complement, spelled out rather than `~_held()`.

    NOT of the expression above is a three-valued-logic trap: for an
    unflagged row `flagged == 'nudity'` is NULL, the AND is NULL, and NOT
    NULL is still NULL - which a WHERE treats as false, silently filtering
    out every ordinary photo. Each disjunct here is null-safe.
    """
    return or_(
        PoiPhoto.flagged.is_(None),
        PoiPhoto.flagged != "nudity",
        PoiPhoto.reviewed_at.isnot(None),
    )


def _public_from():
    """When an upload becomes the gallery's to serve: its bytes landed at
    least the cooling-off window ago."""
    return utc_now() - timedelta(hours=COOLING_OFF_HOURS)


@router.post("", response_model=PoiPhotoOut, status_code=status.HTTP_201_CREATED)
def share_photo(
    poi_id: str,
    payload: PoiPhotoShare,
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_user),
):
    """Share (or replace) the caller's photo of this waypoint.

    One per person per POI is the row's identity, so a second share by the
    same hiker REPLACES their first rather than being refused - the design's
    self-healing rule, free here because the upsert and the overwriting
    object key are the same fact. Replacement clears any pin: a pin is a
    club's judgement about one photograph, and this is a different
    photograph.

    Refused without a trail name, because there is nothing to attribute:
    CC BY-SA's condition of use is the credit, and "usable, uncredited" is
    not a state the store admits. The sheet asks for the trail name before
    it offers the share, so an ordinary client never sees this.
    """
    poi_id = _checked_poi_id(poi_id)

    if current_user.display_name is None or current_user.display_name.strip() == "":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Sharing a photo needs a trail name to credit it to. Set one first.",
        )

    now = utc_now()
    window_days = _anonymity_window_days(db, current_user.id)
    masked_until = now + timedelta(days=window_days) if window_days > 0 else None

    photo = db.query(PoiPhoto).filter(PoiPhoto.poi_id == poi_id, PoiPhoto.contributor_id == current_user.id).one_or_none()
    if photo is None:
        photo = PoiPhoto(poi_id=poi_id, contributor_id=current_user.id)
        db.add(photo)

    photo.taken = payload.taken
    photo.shared_at = now
    # The bytes for THIS share have not landed yet, whatever the previous
    # share had - serving the old photograph under the new date would be the
    # gallery lying about what it is showing.
    photo.uploaded_at = None
    photo.attribution_name = current_user.display_name
    photo.masked_until = masked_until
    photo.status = PoiPhotoStatus.live
    photo.pinned_at = None
    photo.pinned_by = None
    photo.dismissed_at = None
    photo.dismissed_by = None
    # A replacement is a different photograph, so nothing decided about the
    # old one carries: not the pin (above), not a hiker's report against it,
    # not the human glance that cleared it, and not the old flag. What the
    # phone found in THIS photo is what arrives with this share.
    photo.flagged = payload.flagged
    photo.reported_at = None
    photo.reported_by = None
    photo.reported_reason = None
    photo.reviewed_at = None
    photo.reviewed_by = None

    commit_and_refresh(db, photo)
    return PoiPhotoOut.from_row(photo, url=_url_or_placeholder(photo))


def _url_or_placeholder(photo: PoiPhoto) -> str:
    """A signed URL where storage is configured, else an empty string.

    Only the write path's own response ever carries the empty form - the
    public list refuses to serve rows it cannot sign at all. The sharer just
    sent the bytes themselves; an unusable URL costs them nothing, where a
    refused share would strand the outbox.
    """
    if not photo_storage_configured():
        return ""
    return presigned_object_url(poi_photo_key(photo.poi_id, photo.contributor_id))


@router.put("/mine", response_model=PoiPhotoOut)
async def upload_shared_photo(
    poi_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_user),
):
    """Land the bytes for the caller's share of this waypoint.

    The same checks the report-photo upload runs, for the same reasons
    (#379): the body is capped as it streams, and JPEG is decided by the
    bytes' own magic rather than a header the client writes. The client
    re-encodes to 640px before upload (lib/poiPhotos.ts CARD_PHOTO_EDGE),
    so a body near the cap is a client that skipped the resize.

    Completing an upload is when the rolling window is enforced: beyond the
    newest ROLLING_WINDOW unpinned photos, the oldest are withdrawn from
    the gallery and the store - the self-healing eviction POI_PHOTOS.md
    chose over refusing the thirteenth share.
    """
    poi_id = _checked_poi_id(poi_id)

    if not photo_uploads_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Photo storage is not configured on this server.",
        )

    photo = db.query(PoiPhoto).filter(PoiPhoto.poi_id == poi_id, PoiPhoto.contributor_id == current_user.id).one_or_none()
    if photo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Share the photo before uploading its bytes.",
        )

    if request.headers.get("content-type", "").split(";")[0].strip() != ALLOWED_CONTENT_TYPE:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Waypoint photos must be {ALLOWED_CONTENT_TYPE}.",
        )

    body = await read_capped_body(request, MAX_PHOTO_BYTES)
    if not body:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No photo in the request body.")
    if not body.startswith(JPEG_MAGIC):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Waypoint photos must be {ALLOWED_CONTENT_TYPE}.",
        )

    try:
        store_photo_object(poi_photo_key(poi_id, current_user.id), body)
    except PhotoStorageUnavailable as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error

    photo.uploaded_at = utc_now()
    commit_and_refresh(db, photo)

    _evict_beyond_rolling_window(db, poi_id)

    return PoiPhotoOut.from_row(photo, url=_url_or_placeholder(photo))


def _evict_beyond_rolling_window(db: Session, poi_id: str) -> None:
    """Withdraw the oldest unpinned photos past the rolling twelve.

    Deletion, not hiding: "a POI holds at most 15 shared photos" is a claim
    about the store as much as the gallery, and it is what bounds the
    moderation surface at 45,000 decisions rather than an unbounded backlog.
    The evicted contributor may share again any time - the window is not a
    ban, it is recency doing its job.

    Rows first, objects second, per the direction of truth: an object whose
    delete fails is an orphan for the reconciliation sweep, never a served
    row pointing at nothing.
    """
    excess = (
        db.query(PoiPhoto)
        .filter(
            PoiPhoto.poi_id == poi_id,
            PoiPhoto.status == PoiPhotoStatus.live,
            PoiPhoto.uploaded_at.isnot(None),
            PoiPhoto.pinned_at.is_(None),
            # A held photo neither fills a window slot nor gets evicted by
            # recency: it is a queue item waiting on a person, and deleting
            # it here would erase the decision it is waiting for.
            _not_held(),
        )
        .order_by(_recency().desc(), PoiPhoto.shared_at.desc(), PoiPhoto.id)
        .offset(ROLLING_WINDOW)
        .all()
    )
    if not excess:
        return

    keys = [poi_photo_key(photo.poi_id, photo.contributor_id) for photo in excess]
    for photo in excess:
        db.delete(photo)
    db.commit()

    for key in keys:
        try:
            delete_photo_object(key)
        except PhotoStorageUnavailable:
            # The row is gone, which is the authoritative half; the object
            # is now an orphan the set-difference sweep reclaims.
            pass


@router.get("", response_model=list[PoiPhotoOut])
def list_photos(poi_id: str, db: Session = Depends(get_db)):
    """This waypoint's gallery, in the order the card shows it.

    The club's pins first (their own order of pinning - an editorial
    judgement, not a queue position), then the newest ROLLING_WINDOW
    community photos by the same recency the card prints. Anonymous by
    design, like every browsing endpoint: a shared photo is published, and
    the anonymity window is honoured by masking the credit, not by hiding
    the photograph.

    Two things a live upload can still be excluded for, both temporary:
    the cooling-off window (COOLING_OFF_HOURS - inside it a withdrawal is
    a true undo, so nothing is public yet), and a nudity hold waiting on a
    moderator's glance (#837). Both apply to the pinned branch too - a pin
    inside a photographer's cooling-off window would publish early and
    break the undo the sheet promised.

    An unconfigured deployment serves an empty gallery rather than URLs
    that cannot be signed - offline and not-configured land on the same
    honest answer the card already has, which is falling through the
    ladder.
    """
    poi_id = _checked_poi_id(poi_id)

    if not photo_storage_configured():
        return []

    servable = db.query(PoiPhoto).filter(
        PoiPhoto.poi_id == poi_id,
        PoiPhoto.status == PoiPhotoStatus.live,
        PoiPhoto.uploaded_at.isnot(None),
        PoiPhoto.uploaded_at <= _public_from(),
        _not_held(),
    )

    pinned = (
        servable.filter(PoiPhoto.pinned_at.isnot(None)).order_by(PoiPhoto.pinned_at.asc(), PoiPhoto.id).limit(PINNED_MAX).all()
    )
    rolling = (
        servable.filter(PoiPhoto.pinned_at.is_(None))
        .order_by(_recency().desc(), PoiPhoto.shared_at.desc(), PoiPhoto.id)
        .limit(ROLLING_WINDOW)
        .all()
    )

    return [
        PoiPhotoOut.from_row(photo, url=presigned_object_url(poi_photo_key(photo.poi_id, photo.contributor_id)))
        for photo in [*pinned, *rolling]
    ]


@router.delete("/mine", status_code=status.HTTP_204_NO_CONTENT)
def withdraw_photo(
    poi_id: str,
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_user),
):
    """Stop showing, and stop holding, the caller's photo of this waypoint.

    The product promise POI_PHOTOS.md splits from the licence: OurHike will
    stop showing the photo when asked - that half is kept here, by deleting
    the row and the object - while the CC BY-SA grant on copies already made
    is the half nobody can undo, and the share sheet said so before the
    photo was ever shared (#577).

    A hard delete, not a status: a withdrawal is the contributor's own act,
    and keeping a copy "for the record" of a photo someone asked us to stop
    holding would be the archive by another name. Idempotent - withdrawing
    a photo that is not there is a wish already granted, and the retrying
    outbox must be able to say it twice.
    """
    poi_id = _checked_poi_id(poi_id)

    photo = db.query(PoiPhoto).filter(PoiPhoto.poi_id == poi_id, PoiPhoto.contributor_id == current_user.id).one_or_none()
    if photo is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    db.delete(photo)
    db.commit()

    try:
        delete_photo_object(poi_photo_key(poi_id, current_user.id))
    except PhotoStorageUnavailable:
        # Row gone, object orphaned; the sweep reclaims it. The promise kept
        # is "no longer served", and that is true the moment the row is gone.
        pass

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{photo_id}/report", status_code=status.HTTP_204_NO_CONTENT)
def report_photo(
    poi_id: str,
    photo_id: str,
    payload: PoiPhotoReport,
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_user),
):
    """Flag a photo for the maintaining club (#579's report-this-photo path).

    This is the mechanism that makes the rolling twelve safe without
    pre-approval: the twelve go straight up, and they come down when
    somebody reports one and a moderator agrees. The photo STAYS on the
    card until that human look - the report sheet says so to the reporter's
    face, because promising it comes down sooner is a promise volunteer
    clubs cannot keep.

    Latest report wins and re-surfaces the row: a photo reviewed last month
    and reported again today is back in front of a person, because the
    second reporter may have seen what the first look missed. Requires an
    account, like every write - a report against somebody's photograph
    needs a reporter to weigh it by.
    """
    poi_id = _checked_poi_id(poi_id)

    photo = (
        db.query(PoiPhoto)
        .filter(
            PoiPhoto.id == photo_id,
            PoiPhoto.poi_id == poi_id,
            PoiPhoto.status == PoiPhotoStatus.live,
        )
        .one_or_none()
    )
    if photo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found")

    photo.reported_at = utc_now()
    photo.reported_by = current_user.id
    photo.reported_reason = payload.reason
    photo.reviewed_at = None
    photo.reviewed_by = None
    db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)
