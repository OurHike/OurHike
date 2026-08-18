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
  MAP_STYLE_VALUES,
  MAX_BACKGROUND_ZOOM_VALUES,
  REPORTER_TYPE_VALUES,
  THEME_VALUES,
  UNIT_SYSTEM_VALUES,
  type UserPreferences,
} from './userPreferences'
import { get, set } from 'idb-keyval'

export const PREFERENCES_KEY = 'ourhike:preferences'

/**
 * Merging over the defaults fixes a MISSING key, but not a key holding a value
 * this build no longer knows.
 *
 * `background_source` was the first through this door - it used to offer
 * `usgs_topo_live` and `osm_styled_live`, neither of which was ever built,
 * and both of which could be sitting in IndexedDB on a phone that ran an
 * earlier build. Left alone, that value survives the merge (it is present,
 * so there is nothing to fill in), reaches buildMapStyle, matches no
 * background, and draws no background - the exact black-map class of bug
 * MAP_OPTIONS.md spent a section on, arriving by a different road. Theme,
 * map style and the hiking level each then re-derived the same conclusion
 * as their own hand-rolled function, which is how `unit_system` and
 * `max_background_zoom` ended up with no guard at all - the argument covers
 * every enum-typed key, so since #175 the table below does too.
 *
 * An unrecognised value is treated as absent rather than trusted, and the
 * phone falls back to the default it would have had if it had never stored
 * anything. `null` counts as unrecognised except where the model itself is
 * nullable - `reporter_type`'s null is an answer ("hasn't said"), not a
 * corrupt value, and dropping it would re-ask a question the hiker declined.
 */
const KNOWN_ENUM_VALUES: {
  [K in keyof UserPreferences]?: { allowed: readonly unknown[]; nullable?: true }
} = {
  theme: { allowed: THEME_VALUES },
  unit_system: { allowed: UNIT_SYSTEM_VALUES },
  background_source: { allowed: BACKGROUND_SOURCES },
  max_background_zoom: { allowed: MAX_BACKGROUND_ZOOM_VALUES },
  hiking_detail_level: { allowed: HIKING_DETAIL_LEVEL_VALUES },
  map_style: { allowed: MAP_STYLE_VALUES },
  reporter_type: { allowed: REPORTER_TYPE_VALUES, nullable: true },
}

function dropUnknownEnumValues(
  stored: Partial<UserPreferences>,
): Partial<UserPreferences> {
  const repaired = { ...stored }
  for (const [key, rule] of Object.entries(KNOWN_ENUM_VALUES)) {
    const value = repaired[key as keyof UserPreferences]
    if (value === undefined) continue
    if (value === null && rule.nullable) continue
    if (rule.allowed.includes(value)) continue
    delete repaired[key as keyof UserPreferences]
  }
  return repaired
}

export async function loadPreferences(): Promise<UserPreferences> {
  const stored = (await get(PREFERENCES_KEY)) as Partial<UserPreferences> | undefined
  return {
    ...DEFAULT_PREFERENCES,
    ...dropUnknownEnumValues(stored ?? {}),
  }
}

export async function savePreferences(
  preferences: UserPreferences,
): Promise<UserPreferences> {
  await set(PREFERENCES_KEY, preferences)
  return preferences
}
