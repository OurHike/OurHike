"""The `user_preferences` table - a sync target for the client-owned
`UserPreferences` model.

See ../../../features/IDENTITY_AND_PRIVACY.md (the canonical, consolidated
model - it merges what used to be five separate small settings models). That
model is PRIMARILY client-side/IndexedDB; this table only exists so a hiker
who links a real account has somewhere to sync it to, once linked (same
"local-first, syncs on linking" story as `Profile.display_name`/trail name -
see app/models/profile.py).

One row per profile. `profile_id` is both the primary key and the foreign
key back to `profiles.id` - there is exactly one preferences row per
account, never a history of them, so there's no separate surrogate id to
invent.

Most of the fields (trail_name, theme, unit_system, background_source,
max_background_zoom, show_roads, waypoint_types_shown, layer_detail_level,
auto_rotate_enabled, anonymity_window_days, onboarding_completed,
download_choice_made, location_permission_requested) live together in a
single JSON column rather than one column per field. This is a client-owned
blob that syncs wholesale, not a table anything here queries relationally
(no route filters "profiles where theme=dark") - a single JSON column means
the client-side model can gain/rename/drop a field without a migration on
this table. That's a storage-layer simplification only: the *contents* of
the blob are still strictly validated at the API boundary (see
app/schemas/preferences.py), including that `show_closures` is rejected
outright - it is deliberately not part of `UserPreferences` at all (Map
Options: closures are always shown, never hideable).

`updated_at` follows the same naive-UTC pattern as `Profile.created_at`
(see app/models/profile.py's comment) - duckdb-engine can't marshal a
`TIMESTAMPTZ` back out without the optional `pytz` package, so a tz-aware
`datetime` is stored with its tzinfo stripped, which is safe because every
value going in is already UTC by construction.
"""

from sqlalchemy import JSON, Column, DateTime, ForeignKey, String

from app.core.time import utc_now
from app.db.base import Base


class UserPreferences(Base):
    __tablename__ = "user_preferences"

    profile_id = Column(String, ForeignKey("profiles.id"), primary_key=True)

    data = Column(JSON, nullable=False)

    updated_at = Column(
        DateTime,
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )
