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

/** As a value list like BACKGROUND_SOURCES below, and for the same reason:
 *  preferences.ts drops stored values this build does not know, and it can
 *  only check against a list that exists at runtime. */
export const THEME_VALUES = ['light', 'dark', 'auto'] as const
export type Theme = (typeof THEME_VALUES)[number]
export type UnitSystem = 'imperial' | 'metric'
/**
 * Which of the sheet's palettes the map is drawn in (MAP_STYLE_SPEC.md).
 *
 * All five of the spec's styles, each with its reviewed day and night
 * palettes in map/liveTopo.ts's SHEET_VARIANTS - on the same rule
 * BACKGROUND_SOURCES states below: the settings screen can only offer a
 * style that exists, and the backend's enum mirrors this exactly. Listed in
 * the spec's own order, which is the order the picker shows.
 *
 * This is a STYLE, orthogonal to the light/dark `theme` above (the spec's
 * "mapMode", which this codebase already had under that name): the day
 * sheets follow the theme to their own night forms, `night_hike` chosen
 * outright is dark under either theme - a hiker readying night vision before
 * dusk should not have to flip the whole app to do it - and field's
 * auto-dark is night_hike (see liveTopo.ts's sheetVariant for the one
 * distinction that carries).
 */
export const MAP_STYLE_VALUES = [
  'quiet_pine',
  'field',
  'night_hike',
  'parchment',
  'ridgeline',
] as const
export type MapStyle = (typeof MAP_STYLE_VALUES)[number]
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
/**
 * The hiking sheet's download level (#276): which basemap cut the default
 * background fetches - the z13 Standard package or the full z14 Fine one.
 * Its own key rather than an overload of `max_background_zoom`, which is the
 * USGS raster's tier choice with its own zoom range; the two sheets'
 * decisions must not share one dial. The backend's `HikingDetailLevel`
 * mirrors this exactly.
 */
export const HIKING_DETAIL_LEVEL_VALUES = ['standard', 'fine'] as const
export type HikingDetailLevel = (typeof HIKING_DETAIL_LEVEL_VALUES)[number]

export interface UserPreferences {
  // Identity
  trail_name: string | null

  // App-wide display
  theme: Theme
  unit_system: UnitSystem

  // Map display
  background_source: BackgroundSource
  max_background_zoom: MaxBackgroundZoom
  hiking_detail_level: HikingDetailLevel
  map_style: MapStyle
  /**
   * night_hike's red-light sub-mode (MAP_STYLE_SPEC.md): the dark sheet
   * re-inked in red to spare dark adaptation entirely. A toggle under the
   * style rather than a third style, because it modifies night_hike and
   * means nothing without it - and never a default.
   */
  red_light_enabled: boolean
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
  // Standard: the recommended level, and the safe one - a hiker who never
  // made the choice gets the sheet that fits the storage envelope, not the
  // 1.1 GB one.
  hiking_detail_level: 'standard',
  // Field: the reviewed day sheet (MAP_STYLE_SPEC.md's "reviewed favorite"),
  // which the resolved theme turns into night_hike after dark - so the
  // default pair is right for most hikers with nothing chosen at all.
  map_style: 'field',
  red_light_enabled: false,
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
