// The "today I'm…" mode (#1054): day hiker, thru-hiker, volunteer.
//
// One person is a day-hiker in May and a maintainer in June, and the redesign's
// call (recorded on #1054) is that the app never guesses which day this is:
// the mode is an explicit, visible, reversible control - three segments, all
// three always rendered - not an inference from a planned hike. Changing it
// re-ranks and re-emphasises what the Today screen shows. It never hides a
// feature and never gates one; a control that gated would make "Volunteer" a
// door instead of a description, and the product intent is that the word is
// on screen every day.
//
// ITS OWN STORE, NOT A UserPreferences KEY, and that is a correctness rule
// rather than tidiness. The preferences blob is PUT wholesale at a backend
// schema with `extra="forbid"` (lib/preferences.ts's header carries #242, the
// 422 that rule comes from), so a key added here without a coordinated schema
// change breaks every signed-in hiker's first sync. It is also the right
// modelling: "today I'm volunteering" is a statement about today on this
// phone, not a durable preference an account should replay onto a different
// device on a different day.
//
// Persisted the way lib/preferences.ts persists the blob - idb-keyval, read
// once at app start (App.tsx loads it in the same bootstrap gate as the
// preferences, so nothing renders against a default that is about to be
// corrected and there is no first-paint flash), unknown stored values treated
// as absent rather than trusted. The repair argument is preferences.ts's
// KNOWN_ENUM_VALUES table's, one key at a time: a build that renames a mode
// leaves the old word in IndexedDB on every phone that chose it, and a value
// nothing recognises must fall back to the default rather than reach a
// `match` that draws nothing.

import { get, set } from 'idb-keyval'

export const HIKER_MODE_VALUES = ['day', 'thru', 'volunteer'] as const
export type HikerMode = (typeof HIKER_MODE_VALUES)[number]

/**
 * 'day' rather than 'thru', because it assumes the least. A day hike is the
 * mode whose ranking needs no plan, no section and no history to be useful,
 * which makes it the honest answer for a phone that has never said otherwise.
 * (Unvalidated against real installs - what would settle it is which mode
 * new installs actually pick in their first week, which nothing measures yet.)
 */
export const DEFAULT_HIKER_MODE: HikerMode = 'day'

export const HIKER_MODE_KEY = 'ourhike:hiker-mode'

/** A stored-or-received value made safe to use, whatever wrote it - the same
 *  contract normalisePreferences keeps, for the same reason. */
export function normaliseHikerMode(stored: unknown): HikerMode {
  return HIKER_MODE_VALUES.includes(stored as HikerMode)
    ? (stored as HikerMode)
    : DEFAULT_HIKER_MODE
}

export async function loadHikerMode(): Promise<HikerMode> {
  return normaliseHikerMode(await get(HIKER_MODE_KEY))
}

export async function saveHikerMode(mode: HikerMode): Promise<HikerMode> {
  await set(HIKER_MODE_KEY, mode)
  return mode
}
