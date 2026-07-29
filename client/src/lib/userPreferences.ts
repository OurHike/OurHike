// The client-side `UserPreferences` model (features/IDENTITY_AND_PRIVACY.md).
//
// Lives in IndexedDB and syncs to backend/app/schemas/preferences.py once an
// account is linked, so the field names here match that contract exactly - a
// key this file invents becomes a 422 the moment someone signs in.
//
// There is deliberately NO key for hiding closures or serious warnings. They
// are always shown, with no switch here or anywhere (features/MAP_OPTIONS.md,
// features/HIKER_SAFETY.md). Keeping the invariant at the schema level rather
// than at the settings screen is what makes it hold: a control nobody can
// build is stronger than a control nobody has built yet. The backend guards
// the same line with `extra="forbid"`.

export type Theme = 'light' | 'dark' | 'auto'
export type UnitSystem = 'imperial' | 'metric'
export type BackgroundSource = 'usgs_topo_offline' | 'usgs_topo_live' | 'osm_styled_live'
export type MaxBackgroundZoom = 11 | 12 | 13
export type LayerDetailLevel = 'minimal' | 'standard' | 'full'

export interface UserPreferences {
  // Identity
  trail_name: string | null

  // App-wide display
  theme: Theme
  unit_system: UnitSystem

  // Map display
  background_source: BackgroundSource
  max_background_zoom: MaxBackgroundZoom
  show_roads: boolean
  waypoint_types_shown: string[]
  layer_detail_level: LayerDetailLevel
  auto_rotate_enabled: boolean

  // Safety / privacy. The wrong-way alert is a NOTIFICATION preference - it
  // governs whether the one push OurHike sends is delivered, not whether
  // hazards appear on the map. Defaulted on, so the safety path is opt-out.
  wrong_way_alert_enabled: boolean
  anonymity_window_days: number

  // Onboarding progress
  onboarding_completed: boolean
  download_choice_made: boolean
  location_permission_requested: boolean
}

export const DEFAULT_PREFERENCES: UserPreferences = {
  trail_name: null,

  theme: 'auto',
  unit_system: 'imperial',

  // The offline topo archive is the only background that works with no
  // signal, which is the whole premise - so it is the default, not an option
  // someone has to find.
  background_source: 'usgs_topo_offline',
  max_background_zoom: 12,
  show_roads: false,
  waypoint_types_shown: [],
  layer_detail_level: 'standard',
  auto_rotate_enabled: false,

  wrong_way_alert_enabled: true,
  anonymity_window_days: 0,

  onboarding_completed: false,
  download_choice_made: false,
  location_permission_requested: false,
}

/** The complete key set, so invariants can be asserted against the schema
 *  itself rather than against whatever a given screen happens to render. */
export const PREFERENCE_KEYS = Object.keys(DEFAULT_PREFERENCES) as Array<
  keyof UserPreferences
>
