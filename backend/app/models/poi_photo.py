"""The `poi_photos` table - community waypoint photos a hiker chose to share.

See ../../../features/POI_PHOTOS.md, "Source 3: sharing, and becoming the
default", and #576. This is the store behind rung 2 of the card's precedence
ladder: the club's pick, else the newest community photo. The bytes live in
the same private R2 photo bucket report photos use (app/core/photos.py);
this row is the authoritative half, and the object is derived and disposable
- the same direction of truth, stated there once and not re-litigated here.

WHY THE ROW IS UNIQUE ON (POI, CONTRIBUTOR)

"One photo per person per POI" is the design's anti-domination rule, and
"a hiker's second photo replaces their first rather than being refused" is
its self-healing half. Making the pair the row's identity gets both for
free: a re-share upserts, the derived object key
(`poi-photos/{poi_id}/{contributor_id}.jpg`) overwrites, and the cap is a
property of the schema rather than a constraint someone has to enforce in
every code path that writes.

WHY MASKING IS A STORED FACT HERE, WHEN REPORTS EVALUATE IT LIVE

HIKER_SAFETY.md §2 evaluates the anonymity window live against a report's
timestamp. A photo cannot do the same, and POI_PHOTOS.md says why: the
photo is published under CC BY-SA 4.0, where the attribution owed is the
attribution the licensor asked for - so the *request* ("credited as Sawyer,
name withheld until 12 September by the photographer's request") has to be
recorded with the photo, or a downstream reuser cannot comply at all. So
`masked_until` is computed once, at share time, from the sharer's
`anonymity_window_days` - a licence record, not a display preference, and
later preference changes do not rewrite it.

WHY `pinned_*` AND `dismissed_*` EXIST WITH NO ENDPOINT SETTING THEM

The read path's contract needs them now - pins order first and do not roll,
a dismissed photo is not served - and the actions belong to the moderation
surface (#579), which is claimed and being designed separately. Columns
without actions are the same shape ReportStatus.resolved wore between #257
and the moderation surface: vocabulary held open, honestly documented.
"""

import enum
import uuid

from sqlalchemy import Column, Date, DateTime, Enum, ForeignKey, String, UniqueConstraint

from app.core.time import utc_now
from app.db.base import Base

# The licence every shared photo is released under - decided 2026-08-07 in
# POI_PHOTOS.md, and per #569 (2026-08-19) it is one licence event whatever
# the audience. Stored per row rather than assumed, because the licence
# record travels with the photo: a future licence change must not silently
# relabel photos shared under this one.
SHARED_PHOTO_LICENSE = "CC BY-SA 4.0"


class PoiPhotoStatus(str, enum.Enum):
    live = "live"
    # Taken down by a moderator (#579's action). Distinct from withdrawal,
    # which is the contributor's own act and deletes the row outright - a
    # hiker who asked OurHike to stop showing their photo is owed removal,
    # not a flag.
    dismissed = "dismissed"


class PoiPhoto(Base):
    __tablename__ = "poi_photos"
    __table_args__ = (UniqueConstraint("poi_id", "contributor_id", name="uq_poi_photos_poi_contributor"),)

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # A soft reference into the pipeline's static POI export, exactly as
    # Report.poi_id is - the dataset lives outside this database, so there is
    # no table for a real FK to point at.
    poi_id = Column(String, nullable=False, index=True)

    contributor_id = Column(String, ForeignKey("profiles.id"), nullable=False, index=True)

    # EXIF capture date, claimed by the client from the original file before
    # its re-encode (client lib/exifDate.ts). Null when the original carried
    # none; the card then dates the photo by its share month. A claim, like
    # `authored_at` on reports - the server has no way to check it, and the
    # public read path coarsens it to a month either way.
    taken = Column(Date, nullable=True)

    # When the share landed (server truth). Replaced on self-replacement -
    # the row is the CURRENT photo of this place by this person, and recency
    # is what the rolling window orders by.
    shared_at = Column(DateTime, nullable=False, default=utc_now)

    # When the bytes actually landed in the bucket. Null between the share
    # row being created and its upload completing (the outbox's two-phase
    # flush), and the read path serves nothing until it is set: a gallery
    # entry pointing at an object that is not there is a broken image, not a
    # photo.
    uploaded_at = Column(DateTime, nullable=True)

    # The trail name the photographer asked to be credited as, captured at
    # share time. Non-null by construction: a share with no trail name is
    # refused, because CC attribution is the condition of use and "usable,
    # uncredited" is not a state this store admits.
    attribution_name = Column(String, nullable=False)

    # End of the anonymity window's masking, or null when the sharer's
    # window was zero. See the module docstring for why this is stored
    # rather than evaluated live.
    masked_until = Column(DateTime, nullable=True)

    license = Column(String, nullable=False, default=SHARED_PHOTO_LICENSE)

    status = Column(
        Enum(PoiPhotoStatus, native_enum=False, length=20),
        nullable=False,
        default=PoiPhotoStatus.live,
        index=True,
    )

    # The club's pick (POI_PHOTOS.md: at most 3 per POI, pre-moderated,
    # exempt from the rolling window). Set and cleared by #579's actions;
    # cleared here on self-replacement, because a pin is a judgement about
    # one photograph and the replacement is a different photograph.
    pinned_at = Column(DateTime, nullable=True)
    pinned_by = Column(String, ForeignKey("profiles.id"), nullable=True)

    # Who took it down and when - the moderation-trail pair every moderated
    # resource here carries (#658).
    dismissed_at = Column(DateTime, nullable=True)
    dismissed_by = Column(String, ForeignKey("profiles.id"), nullable=True)

    # What the on-device check found, claimed by the client at share time
    # (#837): 'nudity' or 'faces', null when nothing was found or no check
    # ran. A claim like `taken` is - the server cannot verify it - and the
    # decided posture holds: the flag never decides. 'faces' is friction on
    # the sheet and priority in the queue; 'nudity' additionally HOLDS the
    # photo from the public gallery until one human glance (`reviewed_at`),
    # the narrow hold #837 names - not the general pre-moderation the design
    # rejects, because it reaches only what the phone itself flagged.
    flagged = Column(String, nullable=True)

    # A hiker's report against this photo (#579's report-this-photo path,
    # the mechanism that makes the rolling twelve safe without
    # pre-approval). One report is enough to surface it; reason 'person'
    # ("somebody in it did not agree to this") sorts first.
    reported_at = Column(DateTime, nullable=True)
    reported_by = Column(String, ForeignKey("profiles.id"), nullable=True)
    reported_reason = Column(String, nullable=True)

    # One human looked (#579's "leave it in the twelve"): clears a hold and
    # takes the row out of the queue's attention without touching the photo.
    reviewed_at = Column(DateTime, nullable=True)
    reviewed_by = Column(String, ForeignKey("profiles.id"), nullable=True)
