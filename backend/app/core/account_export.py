"""Everything this backend holds about one account, as plain JSON.

Phase E of ../../../features/ACCOUNT_SYNC.md (#895), the half that runs
before the deletion: *"a hiker taking their data back should not have to
choose between having it and being rid of us."*

WHY THIS DUMPS COLUMNS RATHER THAN REUSING THE RESPONSE SCHEMAS

Every `*Out` schema in app/schemas/ is built for a reader who is not
necessarily the author, so several of them redact - `ReportOut.from_row`
withholds `reporter_id` from anyone but a moderator or the reporter,
`ClosureOut` drops `reported_by` outright (#430). Those are the right rules
for a public read and exactly the wrong ones for handing somebody their own
file: an export that quietly omitted a column would be this feature failing
in the one direction nobody would notice.

So the archive is generated from the table definitions themselves. A column
added to a model tomorrow appears here tomorrow, without anybody remembering
to add it - the opposite failure mode from a hand-maintained field list, and
the reason this is not a nicer-looking bespoke shape.

That has a cost worth stating rather than discovering: **column names are
the archive's field names**, so this file's readability depends on the
columns being decently named. They mostly are. `worked_on`, `reported_by`
and `authored_at` read fine; `poi_id` needs the app to mean anything, and
nothing here pretends otherwise.

WHAT IS NOT IN IT, WHICH THE ARCHIVE ITSELF SAYS

Three things, listed in `NOT_INCLUDED` below and written into every export so
a hiker reading the file offline learns it from the file rather than from us:
the photograph bytes, anything that never left their handset, and Supabase
Auth's own record of them.

The photographs are the one that deserves an argument rather than a bullet.
Their bytes live in R2 and the only way to hand out an R2 object is a signed
URL, which is a bearer token and lives `PHOTO_URL_TTL_SECONDS` - five
minutes (core/photos.py, which argues that number and declines to raise it
for a moderation queue). Five minutes is shorter than the time it takes to
download a file and open it, so a URL baked in here would be dead on arrival
and would read as the export being broken rather than as the link being
old. The keys are exported instead, which is what actually identifies each
object, and closing the gap properly means bundling the bytes - a real
archive format, not a longer TTL.
"""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.core.photos import poi_photo_key
from app.core.time import utc_now
from app.models.app_failure import AppFailure
from app.models.closure import Closure
from app.models.field_note import FieldNote, NoteFlag
from app.models.hike import Hike
from app.models.maintainer_assignment import MaintainerAssignment
from app.models.poi_photo import PoiPhoto
from app.models.preferences import UserPreferences
from app.models.profile import Profile
from app.models.report import Report
from app.models.synced_trip import SyncedPlannedHike, SyncedTrip
from app.models.volunteer_hours import VolunteerHoursRecord

# Written into every archive. Plain sentences rather than a schema, because
# the reader is a hiker with a text editor and no context, possibly months
# later, possibly after the account is gone.
NOT_INCLUDED: tuple[str, ...] = (
    "The photographs themselves. Every photo you shared is listed below with its "
    "storage key and everything else we know about it, but the image files are not "
    "in this archive: they are served through links that expire five minutes after "
    "they are made, which is no use inside a file you keep.",
    "Anything that never left your phone. Trips you made while signed out, or with "
    "syncing turned off, exist only on that handset - this file is what the account "
    "holds, which is deliberately less.",
    "Your sign-in details. Your email address, password and any linked Google or "
    "Apple account are held by Supabase Auth, not by OurHike, and are not ours to "
    "put in this file.",
)


def _plain(value: Any) -> Any:
    """One column value as something `json.dumps` will take.

    Timestamps go out as ISO-8601. The stored values are naive UTC by this
    backend's convention (app/core/time.py), so a bare `.isoformat()` would
    write `2026-08-22T11:40:00` with no zone and hand the reader's editor -
    or their next tool - a timestamp to interpret as local. The `Z` is put
    back on for the same reason `UtcDatetime` puts it back on at the API
    boundary: an unmarked UTC timestamp is a wrong timestamp waiting to be
    read.
    """
    if isinstance(value, datetime):
        return value.isoformat() + "Z"
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        return float(value)
    return value


def _row(instance: Any) -> dict[str, Any]:
    """Every mapped column on one row, by its own name."""
    return {column.key: _plain(getattr(instance, column.key)) for column in inspect(type(instance)).mapper.columns}


def _rows(db: Session, model: Any, condition: Any) -> list[dict[str, Any]]:
    return [_row(instance) for instance in db.query(model).filter(condition).all()]


def build_export(db: Session, profile: Profile) -> dict[str, Any]:
    """The whole archive for one account.

    Sections are named for what a hiker calls them rather than for the table
    - "trips" and not "synced_trips", "your account" and not "profiles" -
    because the table names are an implementation detail of ours and the
    file is theirs. The column names inside each section are not translated,
    for the reason the module docstring gives.
    """
    profile_id = profile.id

    preferences = db.get(UserPreferences, profile_id)
    planned_hike = db.get(SyncedPlannedHike, profile_id)

    photos = db.query(PoiPhoto).filter(PoiPhoto.contributor_id == profile_id).all()

    return {
        "exported_at": _plain(utc_now()),
        "exported_for": profile_id,
        "what_this_file_does_not_contain": list(NOT_INCLUDED),
        "your_account": _row(profile),
        "preferences": _row(preferences) if preferences is not None else None,
        "trips": _rows(db, SyncedTrip, SyncedTrip.profile_id == profile_id),
        "planned_hike": _row(planned_hike) if planned_hike is not None else None,
        "hikes": _rows(db, Hike, Hike.user_id == profile_id),
        "condition_reports": _rows(db, Report, Report.reporter_id == profile_id),
        "trail_notes": _rows(db, FieldNote, FieldNote.reporter_id == profile_id),
        "notes_you_flagged": _rows(db, NoteFlag, NoteFlag.flagged_by == profile_id),
        "closures_you_reported": _rows(db, Closure, Closure.reported_by == profile_id),
        # The one section that gains a field the table does not have: the R2
        # key is DERIVED from (poi_id, contributor_id) rather than stored
        # (core/photos.py), so dumping the columns alone would omit the only
        # thing that identifies the object. Named `storage_key` rather than
        # `key` so it cannot be mistaken for a column.
        "photos_you_shared": [
            {**_row(photo), "storage_key": poi_photo_key(photo.poi_id, photo.contributor_id)} for photo in photos
        ],
        "volunteer_hours": _rows(db, VolunteerHoursRecord, VolunteerHoursRecord.user_id == profile_id),
        "trail_sections_you_maintain": _rows(db, MaintainerAssignment, MaintainerAssignment.maintainer_id == profile_id),
        "app_problems_you_reported": _rows(db, AppFailure, AppFailure.reporter_id == profile_id),
    }
