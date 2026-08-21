// What this device knows about its own sync with the account (#892).
//
// Phase A put the same bookkeeping beside the preferences blob and this is
// the same shape one grain finer: preferences are one document, trips are
// many, so "did we change something" becomes "which ones".
//
// WHY A LEDGER WRITTEN AT THE MOMENT OF THE EDIT, RATHER THAN A DIFF
//
// The obvious alternative is to keep the last-synced copy of every trip and
// work out what moved by comparing. It is exact, and it is wrong here for a
// reason features/ACCOUNT_SYNC.md states as a rule: **a delete travels only
// as the hiker's own delete, never as an absence inferred from one device's
// silence.**
//
// A diff cannot tell those apart. `loadTrips` falls back to `EMPTY_STORE`
// when the stored document cannot be validated - which is the right answer
// for drawing a screen and a catastrophe for a diff, because every trip the
// hiker has would read as deleted and the tombstones would travel to every
// other device. Recording the deletion when the hiker performs it means the
// question never arises: a store that failed to load never calls
// `saveTrips`, so nothing is ever recorded as deleted by a failure to read.
//
// It also costs less. The diff version holds a second copy of every plan
// (~24 KB each, HIKE_PLANNING.md Q6); this holds a handful of ids.
//
// THE STAMPS ARE THE SERVER'S, ALWAYS
//
// `seen` is what the server said, verbatim, and it is only ever compared
// against what the server says next. Nothing here compares a phone's clock
// to anything - `lib/preferencesSync.ts` has the long version of why, and it
// applies harder at this grain: two devices editing the same trip is the
// case this whole feature is about, and resolving it with a handset's clock
// would resolve it in favour of whichever handset is set wrong.

import { get, set } from 'idb-keyval'

export const TRIPS_SYNC_KEY = 'ourhike:trips:sync'

export interface TripSyncState {
  /** Trips changed on this device since its last successful sync. */
  dirty: string[]
  /**
   * Trips the hiker deleted here, waiting to travel as tombstones.
   *
   * Kept until the server has been told, and deliberately NOT derived from
   * the store's contents - see the header. An id can be in here and absent
   * from `seen` (deleted before it ever synced), which is not a
   * contradiction: the tombstone still travels, because another device may
   * have the trip and would otherwise re-upload it for ever.
   */
  deleted: string[]
  /** The server's `updated_at` for each trip, as this device last saw it. */
  seen: Record<string, string>
  /** The watermark from the last successful sync, or null on a first run. */
  since: string | null
  /** The planned hike changed here since the last sync. */
  hikeDirty: boolean
  /** The server's stamp for the planned hike, as last seen. */
  hikeSeen: string | null
}

const NEVER_SYNCED: TripSyncState = {
  dirty: [],
  deleted: [],
  seen: {},
  since: null,
  hikeDirty: false,
  hikeSeen: null,
}

function ids(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((id): id is string => typeof id === 'string')
    : []
}

/**
 * The ledger, repaired rather than trusted.
 *
 * Every field falls back to its never-synced value independently. A
 * half-written ledger reading as "never synced" costs a full re-upload and a
 * round of conflict copies; reading it as "synced and clean" would lose
 * whatever it was in the middle of recording, which is the direction that
 * loses planning.
 */
export async function tripSyncState(): Promise<TripSyncState> {
  const stored = (await get(TRIPS_SYNC_KEY)) as Partial<TripSyncState> | undefined
  if (stored === undefined) return NEVER_SYNCED

  const seen = stored.seen
  return {
    dirty: ids(stored.dirty),
    deleted: ids(stored.deleted),
    seen:
      typeof seen === 'object' && seen !== null
        ? Object.fromEntries(
            Object.entries(seen).filter(([, stamp]) => typeof stamp === 'string'),
          )
        : {},
    since: typeof stored.since === 'string' ? stored.since : null,
    hikeDirty: stored.hikeDirty === true,
    hikeSeen: typeof stored.hikeSeen === 'string' ? stored.hikeSeen : null,
  }
}

async function write(next: TripSyncState): Promise<void> {
  await set(TRIPS_SYNC_KEY, next)
}

/**
 * Record what the hiker just did to their trips on THIS device.
 *
 * Called by `saveTrips` with the store as it was and as it now is, so a
 * deletion is recorded because the hiker deleted something, never because a
 * read came back empty.
 */
export async function recordTripEdits(
  before: readonly { id: string }[],
  after: readonly { id: string }[],
): Promise<void> {
  const state = await tripSyncState()
  const remaining = new Set(after.map((trip) => trip.id))
  const gone = before.map((trip) => trip.id).filter((id) => !remaining.has(id))

  // Every surviving trip is marked, not only the changed one. `saveTrips`
  // takes a whole store and the callers hand it edits from half a dozen
  // modules, so working out WHICH trip moved would mean this file knowing
  // about every one of them. Over-marking costs an upload the server
  // recognises as identical and drops; under-marking loses an edit.
  const dirty = new Set([...state.dirty, ...remaining])
  gone.forEach((id) => dirty.delete(id))

  await write({
    ...state,
    dirty: [...dirty],
    deleted: [...new Set([...state.deleted, ...gone])],
  })
}

/** Record that the hiker changed their planned hike here. */
export async function recordHikeEdit(): Promise<void> {
  const state = await tripSyncState()
  await write({ ...state, hikeDirty: true })
}

/**
 * Record a completed exchange: this device is level with the account again.
 *
 * `keptSeen` replaces the whole stamp map rather than merging into it, so a
 * trip that no longer exists anywhere stops being carried for ever. The
 * caller builds it from what the server just said plus what it already knew.
 */
export async function recordTripSync(
  since: string,
  keptSeen: Record<string, string>,
  hikeSeen: string | null,
): Promise<void> {
  await write({
    dirty: [],
    deleted: [],
    seen: keptSeen,
    since,
    hikeDirty: false,
    hikeSeen,
  })
}

/**
 * Forget the sync bookkeeping, keeping every trip.
 *
 * What sign-out does, and `lib/preferences.ts`'s `forgetPreferencesSync`
 * has the reasoning: the trips are the phone's, but `since` and `seen` are
 * claims about an account this device no longer has. Leaving them would let
 * the next sign-in - possibly by somebody else on a shared handset - look
 * like a device that had already synced, and upload one person's trips into
 * another person's account as ordinary edits.
 */
export async function forgetTripSync(): Promise<void> {
  await write(NEVER_SYNCED)
}
