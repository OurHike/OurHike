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

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict


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
    """

    hiking_topo_live = "hiking_topo_live"
    usgs_topo_offline = "usgs_topo_offline"


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

    updated_at: datetime
