// The last day this phone had a fix on the trail (#1317).
//
// WHY THIS EXISTS AT ALL. The resume offer has two triggers and the second -
// "you have not been on this corridor for eleven days" - needs a record of
// when the phone last was. Nothing kept one: `lib/gpsTrace.ts` holds a
// session's own track and `lastSyncedAt` is about the account, not the
// trail. So this is the smallest thing that answers the question.
//
// ONE ISO DAY, DEVICE-LOCAL, AND THAT IS DELIBERATE. Not a list of days, not
// a track, not a timestamp:
//
//  - A DAY rather than an instant, because the question is "how many days
//    ago", asked on the hiker's own calendar. A pause at 23:00 and a read at
//    07:00 is one day, not nine hours.
//  - ONE day rather than a history, because nothing reads a history and a
//    list of every day somebody was on the trail is a movement record this
//    app has no reason to keep. features/IDENTITY_AND_PRIVACY.md's minimum
//    is the standard: hold what the feature needs and nothing beside it.
//  - DEVICE-LOCAL, beside `hikerMode` rather than in the synced store,
//    because it is a statement about THIS phone. A laptop that has never
//    been on the trail has not been away from it, and syncing this would let
//    the laptop's silence read as the hiker's.
//
// It records only that the phone was somewhere on the trail, never where.

import { get, set } from 'idb-keyval'

export const LAST_ON_TRAIL_KEY = 'ourhike:last-on-trail'

/** The ISO day this phone last had a fix on the trail, or null. */
export async function loadLastOnTrail(): Promise<string | null> {
  const stored = await get(LAST_ON_TRAIL_KEY)
  // Anything this build does not recognise reads as "never", which costs a
  // resume offer that does not fire - the safe direction. Trusting a garbled
  // value would fire one against a date nobody wrote.
  return typeof stored === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(stored) ? stored : null
}

/**
 * Note that the phone is on the trail today.
 *
 * Idempotent within a day and cheap to call on every fix: it writes only
 * when the day actually changes, so a hiker walking for nine hours does one
 * IndexedDB write rather than several thousand.
 */
export async function noteOnTrail(today: string): Promise<string> {
  if ((await loadLastOnTrail()) === today) return today
  await set(LAST_ON_TRAIL_KEY, today)
  return today
}
