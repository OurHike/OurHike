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

`show_closures` is deliberately not a field anywhere in this module, and
OurHike/OurHike#1047 sharpened rather than softened that. Map Options used
to make closures always-on and never hideable; the client's legend now
carries an Alerts switch that clears the bands from the canvas while a
hiker is looking at it. What that switch must never be is a *preference* -
this object syncs, so a field here would put a hiker's one-off tap in
Virginia onto a new phone in Maine. The client holds it in memory and
resets it at the next open instead.

`model_config = ConfigDict(extra="forbid")` on `PreferencesIn` is what
turns a client sending it anyway into a real 422 (a rejected, visible
error) rather than the field being silently dropped and the rest of the
request quietly succeeding.
"""

from enum import Enum

from pydantic import BaseModel, ConfigDict

from app.core.time import UtcDatetime
from app.models.report import ReporterType


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
    """The hiking sheet's download level (#276) - which pair of archives the
    default background fetches. Standard and Fine differ in the basemap cut
    (the z13 package or the full z14 one); Light differs in the DEM, whose
    corridor tapers harder with depth (#1088). Mirrors
    client/src/lib/userPreferences.ts `HIKING_DETAIL_LEVEL_VALUES` exactly,
    like every enum in this module.

    Defaulted, unlike `max_background_zoom`, because Standard has a
    documented recommendation behind it: it is the level a hiker who never
    made the choice should get - the sheet that fits the storage envelope -
    and it is what pre-#276 blobs, which have no such key, must read back
    as.

    `light` is accepted here before anything publishes its archives, and that
    ordering is deliberate rather than premature: this schema is `extra=forbid`
    and a stored value it does not know is rejected outright, so the value has
    to be storable before the first phone can choose it. What stops it being
    OFFERED meanwhile is client-side - hikingDetail.ts's `published` - not this
    enum, which only says what may be persisted."""

    light = "light"
    standard = "standard"
    fine = "fine"


class MapStyle(str, Enum):
    """Which of the live sheet's palettes the map is drawn in
    (MAP_STYLE_SPEC.md). Mirrors client/src/lib/userPreferences.ts
    `MAP_STYLE_VALUES` exactly, like every enum in this module - all five
    values are implemented palettes (map/liveTopo.ts's SHEET_VARIANTS), so a
    value nothing can render is also a value nothing can sync."""

    quiet_pine = "quiet_pine"
    field = "field"
    night_hike = "night_hike"
    parchment = "parchment"
    ridgeline = "ridgeline"


class PreferencesIn(BaseModel):
    """What a client PUTs to `/preferences/me` - a full replace of the
    synced blob, not a partial patch (see the router's upsert docstring)."""

    model_config = ConfigDict(extra="forbid")

    # Identity
    trail_name: str | None = None
    # None until the hiker says, and deliberately not defaulted to a type
    # (#233). Every report used to be filed as `thru` from a hardcoded literal
    # in the client, and `reporter_type` is the one attribution that survives
    # HIKER_SAFETY.md 2's anonymity window - so a value invented here would be
    # the same false claim, written one layer deeper. What a report carries
    # while this is None is the client's decision
    # (client/src/lib/reporterIdentity.ts).
    reporter_type: ReporterType | None = None

    # App-wide display
    theme: Theme = Theme.auto
    unit_system: UnitSystem = UnitSystem.imperial

    # Map display
    background_source: BackgroundSource
    max_background_zoom: MaxBackgroundZoom
    hiking_detail_level: HikingDetailLevel = HikingDetailLevel.standard
    # Defaulted like hiking_detail_level, and for the same two reasons: Field
    # with red light off is the documented recommendation (the reviewed day
    # sheet, never the red one), and rows synced before these keys existed
    # must read back as exactly that rather than as a ValidationError.
    map_style: MapStyle = MapStyle.field
    red_light_enabled: bool = False
    show_roads: bool = False
    # Defaulted rather than required, like map_style and red_light_enabled
    # above and for the same second reason: rows written before this key
    # existed have to read back as "off" rather than as a ValidationError.
    # False is also the client's own default, so the two agree by value and
    # not just by type - a hiker who never touched the switch syncs the same
    # thing whichever side answers first.
    drought_layer_shown: bool = False
    # Mirrors client/src/lib/userPreferences.ts's DEFAULT_PREFERENCES exactly:
    # the curated subset a maintainer decision (#865) chose over every
    # category, resolving the open question IDENTITY_AND_PRIVACY.md used to
    # record as "(default: all)".
    waypoint_types_shown: list[str] = ["shelter", "water", "campsite", "privy"]
    layer_detail_level: LayerDetailLevel
    auto_rotate_enabled: bool = False

    # Safety / privacy
    #
    # `wrong_way_alert_enabled` SYNCS, and that is a decision rather than an
    # oversight corrected (#242). It is not the OS notification permission -
    # that is genuinely per-device and lives with the platform. This is the
    # app-level question "do I want OurHike's one alert at all", which
    # belongs to a person rather than to a handset.
    #
    # It defaults ON, so the safety path is opt-out - which is exactly why
    # not syncing it would be the wrong way round: a hiker who deliberately
    # turned the alert off would get it back on a reinstalled phone, firing
    # when they had chosen silence. For the one notification this app ever
    # sends (client/src/lib/push.ts), spending the trust budget that way is
    # worse than losing a preference.
    #
    # Defaulted here for the same reason `map_style` is: a row synced before
    # this key existed must read back as the safety default rather than as a
    # ValidationError.
    wrong_way_alert_enabled: bool = True
    anonymity_window_days: int

    # The Volunteer tab's contribution opt-in (#759, DATA_NUDGES.md): "ask me
    # more thoroughly when I am already looking". Defaulted off for both of
    # the standing reasons - it is the client's own default (a hiker who
    # never touched the switch syncs the same answer whichever side answers
    # first), and rows synced before this key existed must read back as
    # "off" rather than as a ValidationError.
    contribute_conditions: bool = False

    # Onboarding progress
    onboarding_completed: bool = False
    download_choice_made: bool = False
    location_permission_requested: bool = False


class PreferencesOut(PreferencesIn):
    """`PreferencesIn` plus the server-assigned sync timestamp."""

    updated_at: UtcDatetime
