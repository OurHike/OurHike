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
/**
 * Which background the map draws.
 *
 * Two values, both implemented, rather than a list of intentions - the map
 * screen can only offer a background that exists, and the backend's enum
 * mirrors this exactly, so a value nothing can render is also a value nothing
 * can sync.
 *
 * - `hiking_topo_live` - the live topographic sheet (map/liveTopo.ts) drawn
 *   over the downloaded archive. Not "instead of": the archive is still in the
 *   style underneath, so this degrades to `usgs_topo_offline` on its own the
 *   moment there is no signal, with nothing to detect or switch.
 * - `usgs_topo_offline` - the downloaded corridor archive alone, and no
 *   network request for background tiles at all. The honest choice for someone
 *   metering data or deliberately dark.
 */
export const BACKGROUND_SOURCES = ['hiking_topo_live', 'usgs_topo_offline'] as const

export type BackgroundSource = (typeof BACKGROUND_SOURCES)[number]
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

  // The live sheet, because it costs the offline premise nothing: it is drawn
  // OVER the downloaded archive rather than in place of it (see
  // map/style.ts), so with no signal this default renders exactly what
  // `usgs_topo_offline` would. Defaulting the other way would mean someone who
  // has not downloaded anything yet - which is everyone on first run - opens
  // the app to blank paper and has to go find a setting to see a map.
  background_source: 'hiking_topo_live',
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
