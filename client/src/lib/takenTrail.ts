// The trail a hiker has taken from the map, or null (the maintainer's review
// of #1374, 2026-09-10).
//
// The map's plate used to name the Appalachian Trail and wear the ATC's mark
// from the first frame of a fresh install, and its position line then said
// "Off the trail" - a sentence about a trail nobody had chosen, read by a
// hiker in a park loop or a city. The review's instruction: "A user should
// have to select the AT line or choose a hike for that to happen." A long
// hike names its trail by construction (`Hike.trailId`, App.tsx's
// `chosenTrailId`); this store is the other half - the trail a tap on a line
// took, through chrome/LineSheet.tsx's "Take this trail".
//
// ITS OWN STORE, NOT A UserPreferences KEY, for lib/hikerMode.ts's two
// reasons: the synced blob is PUT wholesale at a backend schema with
// `extra="forbid"`, so a key here is a coordinated schema change or a 422
// on every signed-in hiker's first sync; and "the trail I am looking at" is
// a statement about this phone today, not a preference an account should
// replay onto a laptop at home. The default place (lib/defaultPlace.ts)
// syncs because it is where somebody hikes; this does not because it is
// what they tapped.
//
// Mirrored beside the mode in localStorage (lib/launchMirror.ts) for the
// mode's reason: the plate is on the first frame, and "No trail taken"
// corrected to "Appalachian Trail" a tick later is the flash the mirror
// exists to prevent. A stored id this build's registry does not know falls
// back to null rather than reaching the plate - lib/preferences.ts's
// KNOWN_ENUM_VALUES argument, one key at a time.

import { get, set } from 'idb-keyval'
import { TRAILS } from './trails'

export const TAKEN_TRAIL_KEY = 'ourhike:taken-trail'

/** A stored value made safe to use: a registry trail's id, or null. */
export function normaliseTakenTrail(stored: unknown): string | null {
  return typeof stored === 'string' && stored in TRAILS ? stored : null
}

export async function loadTakenTrail(): Promise<string | null> {
  return normaliseTakenTrail(await get(TAKEN_TRAIL_KEY))
}

export async function saveTakenTrail(trailId: string | null): Promise<string | null> {
  await set(TAKEN_TRAIL_KEY, trailId)
  return trailId
}
