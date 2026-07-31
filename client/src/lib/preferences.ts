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

import { get, set } from 'idb-keyval'
import { DEFAULT_PREFERENCES, type UserPreferences } from './userPreferences'

export const PREFERENCES_KEY = 'ourhike:preferences'

export async function loadPreferences(): Promise<UserPreferences> {
  const stored = (await get(PREFERENCES_KEY)) as Partial<UserPreferences> | undefined
  return { ...DEFAULT_PREFERENCES, ...stored }
}

export async function savePreferences(
  preferences: UserPreferences,
): Promise<UserPreferences> {
  await set(PREFERENCES_KEY, preferences)
  return preferences
}
