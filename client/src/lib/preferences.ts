// Persistence for UserPreferences.
//
// Preferences live on the phone first and sync to an account only if there
// ever is one (features/IDENTITY_AND_PRIVACY.md), so IndexedDB is the store
// of record rather than a cache of the server's copy.
//
// Reads merge over DEFAULT_PREFERENCES rather than trusting what was stored.
// A build that adds a key would otherwise read `undefined` for it on every
// phone that saved preferences before the key existed, and an undefined
// `wrong_way_alert_enabled` is a safety default silently turning itself off.

import {
  BACKGROUND_SOURCES,
  DEFAULT_PREFERENCES,
  HIKING_DETAIL_LEVEL_VALUES,
  THEME_VALUES,
  type UserPreferences,
} from './userPreferences'
import { get, set } from 'idb-keyval'

export const PREFERENCES_KEY = 'ourhike:preferences'

/**
 * Merging over the defaults fixes a MISSING key, but not a key holding a value
 * this build no longer knows.
 *
 * `background_source` has already been through one such change - it used to
 * offer `usgs_topo_live` and `osm_styled_live`, neither of which was ever
 * built, and both of which could be sitting in IndexedDB on a phone that ran
 * an earlier build. Left alone, that value survives the merge (it is present,
 * so there is nothing to fill in), reaches buildMapStyle, matches no
 * background, and draws no background - the exact black-map class of bug
 * MAP_OPTIONS.md spent a section on, arriving by a different road.
 *
 * So an unrecognised value is treated as absent rather than trusted, and the
 * phone falls back to the default it would have had if it had never stored
 * anything.
 */
function knownBackground(stored: Partial<UserPreferences>): Partial<UserPreferences> {
  const value = stored.background_source
  if (value === undefined || BACKGROUND_SOURCES.includes(value)) return stored

  const { background_source: _dropped, ...rest } = stored
  return rest
}

/** The same treatment for the hiking sheet's level (#276): a value this
 *  build does not know would otherwise survive the merge, reach the level
 *  lookup, and throw where a hiker can see it. Absent, it falls back to
 *  Standard like a phone that never stored anything. */
function knownHikingDetail(stored: Partial<UserPreferences>): Partial<UserPreferences> {
  const value = stored.hiking_detail_level
  if (value === undefined || HIKING_DETAIL_LEVEL_VALUES.includes(value)) return stored

  const { hiking_detail_level: _dropped, ...rest } = stored
  return rest
}

/** And again for the theme. An unknown stored value would ride the merge into
 *  resolveTheme, come back out unresolved, and reach the map as a backdrop
 *  colour MAP_BACKDROP does not have - `undefined`, which MapLibre draws as
 *  the default black. The same road to the same black map, so it gets the
 *  same guard. */
function knownTheme(stored: Partial<UserPreferences>): Partial<UserPreferences> {
  const value = stored.theme
  if (value === undefined || THEME_VALUES.includes(value)) return stored

  const { theme: _dropped, ...rest } = stored
  return rest
}

export async function loadPreferences(): Promise<UserPreferences> {
  const stored = (await get(PREFERENCES_KEY)) as Partial<UserPreferences> | undefined
  return {
    ...DEFAULT_PREFERENCES,
    ...knownTheme(knownHikingDetail(knownBackground(stored ?? {}))),
  }
}

export async function savePreferences(
  preferences: UserPreferences,
): Promise<UserPreferences> {
  await set(PREFERENCES_KEY, preferences)
  return preferences
}
