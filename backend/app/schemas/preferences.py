"""Pydantic schemas for the `/preferences` router - strict API-boundary
validation for the client-owned `UserPreferences` model
(../../../features/IDENTITY_AND_PRIVACY.md).

The backend's job here is narrow (be a sync target once an account is
linked), but the *validation* is not narrow just because the storage is a
JSON blob (see app/models/preferences.py) - `PreferencesIn` is exactly as
strict as a relationally-modeled table would be.

Which fields default and which are required mirrors what
IDENTITY_AND_PRIVACY.md actually states: fields the doc marks
`(default: ...)` get that default here; fields it lists with no stated
default (`background_source`, `max_background_zoom`,
`layer_detail_level`, `anonymity_window_days`) are required - a client
syncing preferences is expected to always know its own current values for
these, rather than the backend silently substituting a guess for
something safety/display relevant.

`show_closures` is deliberately not a field anywhere in this module. Map
Options makes closures always-on, never hideable, so it isn't a preference
at all - and `model_config = ConfigDict(extra="forbid")` on `PreferencesIn`
is what turns a client sending it anyway into a real 422 (a rejected,
visible error) rather than the field being silently dropped and the rest of
the request quietly succeeding.
"""

from enum import Enum

from pydantic import BaseModel, ConfigDict

from app.core.time import UtcDatetime


class Theme(str, Enum):
    light = "light"
    dark = "dark"
    auto = "auto"


class UnitSystem(str, Enum):
    imperial = "imperial"
    metric = "metric"


class BackgroundSource(str, Enum):
    """Mirrors client/src/lib/userPreferences.ts `BACKGROUND_SOURCES`
    exactly - both values are implemented backgrounds, so a value that
    nothing can render is also a value that nothing can sync.

    Two names this enum used to carry, `usgs_topo_live` and
    `osm_styled_live`, were removed rather than kept as aliases: neither
    was ever built, and accepting a value no client can render would mean
    storing a preference that comes back as a map with no background on
    it. A phone that still has one saved drops it on read (see that
    module's `loadPreferences`) and syncs the default instead, so the 422
    this now produces is only reachable by a client that skipped that
    path.

    Rows in `user_preferences` were written while those names were valid,
    though, and a stored blob is not a client that can be asked to re-sync
    first - GET /preferences/me reads it straight into PreferencesOut. So
    the read side repairs rather than trusts, the same move
    `loadPreferences` makes: see `repair_stored_background`.
    """

    hiking_topo_live = "hiking_topo_live"
    usgs_topo_offline = "usgs_topo_offline"


# The client's DEFAULT_PREFERENCES choice (userPreferences.ts documents why:
# the live sheet draws OVER the downloaded archive, so it costs the offline
# premise nothing) - what a phone that had stored a removed value would have
# ended up syncing anyway.
DEFAULT_BACKGROUND_SOURCE = BackgroundSource.hiking_topo_live


def repair_stored_background(data: dict) -> dict:
    """A stored preferences blob with its `background_source` made current.

    A row written while the enum still carried `usgs_topo_live` or
    `osm_styled_live` holds a value that was valid at write time and is a
    ValidationError now - and surfacing that as a 500 from a GET punishes
    the one client that cannot do anything about it (its own repair runs on
    PUT, which it may not have reached yet). Unknown values become the
    default, exactly what the client's `knownBackground` does with the same
    blob on the phone.
    """
    known = {source.value for source in BackgroundSource}
    if data.get("background_source") in known:
        return data
    return {**data, "background_source": DEFAULT_BACKGROUND_SOURCE}


class MaxBackgroundZoom(int, Enum):
    """One of 11 | 12 | 13 - not an arbitrary int, per
    IDENTITY_AND_PRIVACY.md."""

    eleven = 11
    twelve = 12
    thirteen = 13


class LayerDetailLevel(str, Enum):
    minimal = "minimal"
    standard = "standard"
    full = "full"


class HikingDetailLevel(str, Enum):
    """The hiking sheet's download level (#276) - which basemap cut the
    default background fetches: the z13 Standard package or the full z14
    Fine one. Mirrors client/src/lib/userPreferences.ts
    `HIKING_DETAIL_LEVELS` exactly, like every enum in this module.

    Defaulted, unlike `max_background_zoom`, because Standard has a
    documented recommendation behind it: it is the level a hiker who never
    made the choice should get - the sheet that fits the storage envelope -
    and it is what pre-#276 blobs, which have no such key, must read back
    as."""

    standard = "standard"
    fine = "fine"


class PreferencesIn(BaseModel):
    """What a client PUTs to `/preferences/me` - a full replace of the
    synced blob, not a partial patch (see the router's upsert docstring)."""

    model_config = ConfigDict(extra="forbid")

    # Identity
    trail_name: str | None = None

    # App-wide display
    theme: Theme = Theme.auto
    unit_system: UnitSystem = UnitSystem.imperial

    # Map display
    background_source: BackgroundSource
    max_background_zoom: MaxBackgroundZoom
    hiking_detail_level: HikingDetailLevel = HikingDetailLevel.standard
    show_roads: bool = False
    waypoint_types_shown: list[str] = []
    layer_detail_level: LayerDetailLevel
    auto_rotate_enabled: bool = False

    # Safety / privacy
    anonymity_window_days: int

    # Onboarding progress
    onboarding_completed: bool = False
    download_choice_made: bool = False
    location_permission_requested: bool = False


class PreferencesOut(PreferencesIn):
    """`PreferencesIn` plus the server-assigned sync timestamp."""

    updated_at: UtcDatetime
