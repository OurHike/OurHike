// What a hiker is told about their own sync (#894, ACCOUNT_SYNC.md phase D).
//
// The question this screen exists to answer is one question: *if I drop this
// phone tomorrow, what have I lost?* An offline-first app that syncs
// invisibly cannot answer it, and silence reads as "everything is fine"
// whether or not it is - which is the failure value #4 names, and the same
// argument `lib/outbox.ts` already won when it started showing failures on
// the More screen, because "waiting to send" is a lie once it has stopped
// being true.
//
// TWO CLOCKS, AND THEY ARE NOT THE SAME CLOCK
//
// `Settings.tsx`'s existing "Last synced" row is the PUBLISHED CONDITIONS
// bucket - closures, notes, drought - which every hiker gets whether or not
// they have an account (`lib/useConditions.ts`). This is the account
// exchange: preferences, trips, the planned hike. A hiker whose conditions
// refreshed an hour ago and whose trips have not reached the server since
// Tuesday is in a state neither number describes alone, and one row saying
// "1h ago" would be a confident answer to a question nobody asked.
//
// So this reports its own, in its own section, and never borrows the other's
// number.
//
// WHAT "NEVER REACHED THE SERVER" MEANS, EXACTLY
//
// A trip whose id has no stamp in the sync ledger. That is not the same as
// "changed since the last sync": a trip the server already holds, edited
// here and not yet sent, is still recoverable from the account in its older
// form, while a trip that has never been sent exists only on this handset.
// Both are worth saying and they are different sentences, so they are
// counted separately rather than added up.
//
// NAMED, NOT COUNTED. The issue is explicit and it is right: "3 items
// pending" tells a hiker nothing they can act on, and a trip they recognise
// by name tells them whether to worry.

import { get, set } from 'idb-keyval'
import type { TripStore } from './trips'
import type { TripSyncState } from './tripSyncState'
import type { PreferencesSyncState } from './preferences'

/**
 * Whether this device syncs at all.
 *
 * DEVICE-LOCAL, and deliberately not a `UserPreferences` key. Turning sync
 * off is a decision about this handset - a hiker who stops syncing their
 * laptop has not asked their phone to stop - so putting it in the blob that
 * syncs would make the setting travel to exactly the devices it is meant to
 * exclude. It would also be a schema change on an `extra="forbid"` contract
 * (#242) for a value that should never cross the wire at all.
 */
export const SYNC_ENABLED_KEY = 'ourhike:sync:enabled'

/**
 * Defaults to ON, and that is the safe direction here rather than the
 * convenient one: a hiker who signed in did so to have their things follow
 * them, and a sync that silently defaulted to off would be this screen's own
 * failure mode - a confident "everything is fine" over a phone that has
 * never sent anything.
 */
export async function syncEnabled(): Promise<boolean> {
  return (await get(SYNC_ENABLED_KEY)) !== false
}

export async function setSyncEnabled(on: boolean): Promise<void> {
  await set(SYNC_ENABLED_KEY, on)
}

/** What the screen has to say, as data. */
export interface SyncStatus {
  /** When the account exchange last completed, or null if it never has.
   *  The SERVER's stamp, which is what makes it comparable across devices -
   *  and what means a device whose own clock is wrong renders a wrong age.
   *  `syncAgeLabel` reads anything in the future as "just now", which is the
   *  least wrong thing to say about a disagreement this app cannot detect. */
  lastSyncedAt: Date | null
  /** Trips that exist only on this handset, by name. */
  neverSent: string[]
  /** Trips the account holds in an older form, with newer edits still here. */
  unsentEdits: string[]
  /** Settings changed here and not yet sent. */
  preferencesUnsent: boolean
  /** The planned hike changed here and not yet sent. */
  hikeUnsent: boolean
}

function latest(...stamps: (string | null)[]): Date | null {
  const dates = stamps
    .filter((stamp): stamp is string => stamp !== null)
    .map((stamp) => new Date(stamp))
    .filter((date) => !Number.isNaN(date.getTime()))
  if (dates.length === 0) return null
  return new Date(Math.max(...dates.map((date) => date.getTime())))
}

/**
 * Everything the screen says, from the two ledgers and the store.
 *
 * Pure, so the wording can be tested against states that only occur on
 * somebody's second device after a week offline.
 */
export function summariseSync(
  trips: TripStore,
  tripState: TripSyncState,
  preferencesState: PreferencesSyncState,
): SyncStatus {
  const dirty = new Set(tripState.dirty)
  const named = (predicate: (id: string) => boolean): string[] =>
    trips.trips
      .filter((trip) => predicate(trip.id))
      .map((trip) => trip.name)
      .sort()

  return {
    // The later of the two exchanges: "when did this device last manage to
    // talk to the account at all". Reporting the earlier one would age the
    // whole account by its quietest half.
    lastSyncedAt: latest(tripState.since, preferencesState.syncedAt),
    neverSent: named((id) => !(id in tripState.seen)),
    // Only trips the server already holds. A trip that is both dirty and
    // unsent is in `neverSent`, and saying it twice would be two warnings
    // about one thing.
    unsentEdits: named((id) => id in tripState.seen && dirty.has(id)),
    preferencesUnsent: preferencesState.dirty,
    hikeUnsent: tripState.hikeDirty,
  }
}

/** True when there is nothing anywhere that has not reached the account. */
export function everythingIsSafe(status: SyncStatus): boolean {
  return (
    status.neverSent.length === 0 &&
    status.unsentEdits.length === 0 &&
    !status.preferencesUnsent &&
    !status.hikeUnsent
  )
}
