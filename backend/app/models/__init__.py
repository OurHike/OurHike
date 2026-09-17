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
from app.models.assist import AssistUsage
from app.models.closure import (
    CLOSURE_APPROVALS_REQUIRED,
    Closure,
    ClosureApproval,
    ClosureStatus,
    ModerationStatus,
    ReasonType,
)
from app.models.club import Club, OrgAdmin, OrgState, VerifiedBy
from app.models.console_key import (
    CONSOLE_TOKEN_TTL_SECONDS,
    ConsoleKey,
    ConsoleTokenGrant,
)
from app.models.field_note import FieldNote, NoteFlag, Observation
from app.models.hike import Hike
from app.models.maintainer_assignment import MaintainerAssignment
from app.models.org_registry import OrgPark, OrgSection, OrgTrail, ParkKind, RegistrySignoff
from app.models.org_role import (
    DEACTIVATION_HOLD_FRACTION,
    OrgRole,
    RoleCategory,
    RoleInvite,
    RosterSyncRun,
)
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
from app.models.ridge_runner import (
    COMMITMENT_TASKS,
    MAX_COMMITMENT_DAYS,
    RidgeRunnerCommitment,
)
from app.models.synced_day_hike import SyncedDayHike
from app.models.synced_hike import SyncedActiveHike, SyncedHike
from app.models.synced_trip import SyncedPlannedHike, SyncedTrip
from app.models.volunteer_hours import HoursActivity, HoursState, VolunteerHoursRecord
from app.models.work_project import (
    ProjectSource,
    ProjectStatus,
    SignupMode,
    SignupState,
    WorkProject,
    WorkProjectSignup,
)

__all__ = [
    "RegistrySignoff",
    "AssistUsage",
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
    "SyncedActiveHike",
    "SyncedDayHike",
    "SyncedHike",
    "SyncedPlannedHike",
    "SyncedTrip",
    "HoursActivity",
    "HoursState",
    "VolunteerHoursRecord",
    "CLOSURE_APPROVALS_REQUIRED",
    "ClosureApproval",
    "OrgAdmin",
    "OrgState",
    "VerifiedBy",
    "CONSOLE_TOKEN_TTL_SECONDS",
    "ConsoleKey",
    "ConsoleTokenGrant",
    "OrgPark",
    "OrgSection",
    "OrgTrail",
    "ParkKind",
    "DEACTIVATION_HOLD_FRACTION",
    "OrgRole",
    "RoleCategory",
    "RoleInvite",
    "RosterSyncRun",
    "COMMITMENT_TASKS",
    "MAX_COMMITMENT_DAYS",
    "RidgeRunnerCommitment",
    "ProjectSource",
    "ProjectStatus",
    "SignupMode",
    "SignupState",
    "WorkProject",
    "WorkProjectSignup",
]
