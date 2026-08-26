// The client-side `UserPreferences` model (features/IDENTITY_AND_PRIVACY.md).
//
// Lives in IndexedDB and syncs to backend/app/schemas/preferences.py once an
// account is linked, so the field names here match that contract exactly - a
// key this file invents becomes a 422 the moment someone signs in.
//
// There is deliberately NO key for hiding closures or serious warnings, and
// #1047 is the sharpest argument for that absence rather than a reason to
// revisit it. The legend now carries an Alerts switch (chrome/Legend.tsx),
// so the old sentence here - "always shown, with no switch here or anywhere"
// - is no longer true. What is true, and is the part this file decides, is
// that the switch is not a PREFERENCE: this object syncs, so a key here
// would mean a hiker who cleared the bands once in Virginia opening a new
// phone in Maine with them already gone. The flag is a `useState` in
// chrome/alertLayerPanel.ts, is written nowhere, and is back on at the next
// open.
//
// Keeping the invariant at the schema level rather than at the settings
// screen is what makes it hold: a control nobody can build is stronger than
// a control nobody has built yet, and a control that exists elsewhere cannot
// creep into this object by accident. The backend guards the same line with
// `extra="forbid"` (features/MAP_OPTIONS.md, features/IDENTITY_AND_PRIVACY.md).

import { DEFAULT_SHOWN_TYPES } from './waypointVisibility'

/** As a value list like BACKGROUND_SOURCES below, and for the same reason:
 *  preferences.ts drops stored values this build does not know, and it can
 *  only check against a list that exists at runtime. */
export const THEME_VALUES = ['light', 'dark', 'auto'] as const
export type Theme = (typeof THEME_VALUES)[number]
export type UnitSystem = 'imperial' | 'metric'
// The union above stays a literal because backend/tests/test_preferences_contract.py
// parses it as text; `satisfies` holds this runtime list to it (#175).
export const UNIT_SYSTEM_VALUES = [
  'imperial',
  'metric',
] as const satisfies readonly UnitSystem[]
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
// Same shape as UNIT_SYSTEM_VALUES above, and the union stays literal for the
// same reason - the backend contract test reads it as text.
export const MAX_BACKGROUND_ZOOM_VALUES = [
  11, 12, 13,
] as const satisfies readonly MaxBackgroundZoom[]
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

/**
 * Who a report is from, in the only terms the trail cares about.
 *
 * Declared here rather than imported from lib/outbox.ts, which spells the
 * same four out for `ReportDraft`: preferences are the durable half and the
 * outbox is the wire half, and a preferences model that imported the outbox
 * would make the stored shape depend on the submission shape. The two are
 * held together by lib/reporterIdentity.ts, which is the only place they
 * meet, and by its test.
 */
export const REPORTER_TYPE_VALUES = ['thru', 'section', 'day', 'maintainer'] as const
export type ReporterType = (typeof REPORTER_TYPE_VALUES)[number]

export interface UserPreferences {
  // Identity
  trail_name: string | null
  /**
   * How this hiker's reports are signed - null until they say (#233).
   *
   * Null is the honest starting state and it is not the same as any of the
   * four answers. Every report used to be filed as `thru` from a hardcoded
   * literal at both call sites, so a day hiker, a section hiker and a club
   * maintainer all reached the moderation queue claiming to be thru-hikers.
   * `reporter_type` is the ONE attribution that survives HIKER_SAFETY.md §2's
   * anonymity window - it is kept visible precisely because it carries
   * information without identifying anyone - so a maintainer weighs a report
   * by it, and a field that says the same thing about everybody weighs
   * nothing.
   *
   * What a report carries when this is still null is lib/reporterIdentity.ts's
   * decision, not this file's.
   */
  reporter_type: ReporterType | null

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
  /**
   * The U.S. Drought Monitor wash over the map (#720).
   *
   * Off by default, and that is the honest default rather than a cautious
   * one. It is context, not a hazard: FEATURES.md's "use the app less often,
   * and find information faster when you do" argues against tinting the whole
   * map for everyone, and pipeline/WATER_CONDITIONS.md is emphatic that this
   * data says nothing about the spring at the next shelter. A hiker who wants
   * to know what the region is doing turns it on.
   *
   * Its own key rather than a value of `background_source`, which is a closed
   * two-value enum of BACKGROUNDS - the live sheet or the downloaded archive.
   * The drought is drawn over whichever of those is showing, so folding it in
   * there would make two independent choices into one list of four.
   */
  drought_layer_shown: boolean
  waypoint_types_shown: string[]
  layer_detail_level: LayerDetailLevel
  /**
   * STAGED, NOT SHIPPED (#657): stored, synced, and read by nothing.
   *
   * `UX_CUSTOMIZATION.md`'s auto-rotate needs a movement bearing from the
   * trailing GPS window, and no such computation exists in this client -
   * which is the same missing piece #308 found on the other side of it, where
   * the wrong-way cue's reversed-bearing mode has no producer either. One
   * computation was always meant to serve both.
   *
   * Kept rather than removed: it is in the backend's `extra="forbid"` schema,
   * so dropping it is a coordinated change on both sides for a field the
   * feature will want back.
   */
  auto_rotate_enabled: boolean

  // Safety / privacy. The wrong-way alert is a NOTIFICATION preference - it
  // governs whether the one push OurHike sends is delivered, not whether
  // hazards appear on the map. Defaulted on, so the safety path is opt-out.
  wrong_way_alert_enabled: boolean
  anonymity_window_days: number

  /**
   * The Volunteer tab's opt-in (#759, features/DATA_NUDGES.md): "yes, ask me
   * more thoroughly when I am already looking" - the longer note form on the
   * card, and the places-you-passed list. Off by default, because the
   * passive surface interrupts nobody and the assertive one is only
   * legitimate when it was asked for. NOT a notification consent of any
   * kind: nothing behind this toggle ever interrupts anyone, and the
   * wrong-way alert above stays the only notification this app sends.
   */
  contribute_conditions: boolean

  // Onboarding progress
  onboarding_completed: boolean
  download_choice_made: boolean
  location_permission_requested: boolean
}

export const DEFAULT_PREFERENCES: UserPreferences = {
  trail_name: null,
  reporter_type: null,

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
  drought_layer_shown: false,
  // The curated subset, not `[]` (all) - lib/waypointVisibility.ts's
  // DEFAULT_SHOWN_TYPES and the maintainer decision behind it (#865).
  waypoint_types_shown: [...DEFAULT_SHOWN_TYPES],
  layer_detail_level: 'standard',
  auto_rotate_enabled: false,

  wrong_way_alert_enabled: true,
  anonymity_window_days: 0,

  contribute_conditions: false,

  onboarding_completed: false,
  download_choice_made: false,
  location_permission_requested: false,
}

/** The complete key set, so invariants can be asserted against the schema
 *  itself rather than against whatever a given screen happens to render. */
export const PREFERENCE_KEYS = Object.keys(DEFAULT_PREFERENCES) as Array<
  keyof UserPreferences
>
