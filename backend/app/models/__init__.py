"""Import every ORM model here so app.db.base's Base.metadata is fully
populated - SQLAlchemy only registers a model's table as a side effect of
its module actually being imported somewhere. Without this, alembic/env.py's
`target_metadata = Base.metadata` sees an empty schema regardless of how
many real models exist in the codebase, and `alembic revision --autogenerate`
silently produces an empty migration instead of one creating any tables -
confirmed: this was the actual state before this file existed, per
app/db/base.py's own docstring warning that a model must be "imported
somewhere reachable from here... before autogenerate will see it."
"""

from app.models.app_failure import AppFailure, Harm
from app.models.closure import Closure, ClosureStatus, ModerationStatus, ReasonType
from app.models.club import Club
from app.models.field_note import FieldNote, NoteFlag, Observation
from app.models.hike import Hike
from app.models.maintainer_assignment import MaintainerAssignment
from app.models.poi_photo import PoiPhoto, PoiPhotoStatus
from app.models.preferences import UserPreferences
from app.models.profile import Profile, Role
from app.models.report import (
    Report,
    ReporterType,
    ReportStatus,
    ReportType,
    Severity,
    Visibility,
)
from app.models.volunteer_hours import HoursActivity, HoursState, VolunteerHoursRecord

__all__ = [
    "AppFailure",
    "Harm",
    "Closure",
    "ClosureStatus",
    "ModerationStatus",
    "ReasonType",
    "Club",
    "FieldNote",
    "NoteFlag",
    "Observation",
    "Hike",
    "MaintainerAssignment",
    "PoiPhoto",
    "PoiPhotoStatus",
    "UserPreferences",
    "Profile",
    "Role",
    "Report",
    "ReporterType",
    "ReportStatus",
    "ReportType",
    "Severity",
    "Visibility",
    "HoursActivity",
    "HoursState",
    "VolunteerHoursRecord",
]
