// What this device knows about its own day-hike sync (#976).
//
// lib/tripSyncState.ts's ledger, mirrored for the day-hike store: day hikes
// are many documents, so "did we change something" is "which ones", and a
// delete travels only as the hiker's own delete - recorded here at the moment
// they perform it, never inferred from a store that came back empty. That
// file's header carries the full argument (why a ledger and not a diff, why
// every stamp is the server's); none of it changes at this key.
//
// **DAY-HIKE IDS MUST NEVER ENTER THE TRIPS LEDGER (`ourhike:trips:sync`) OR
// RIDE `recordTripEdits`.** A review found this failure mode, and it is
// silent twice over: a day-hike id in the trips ledger uploads to
// `/trips/sync` as a tombstone that no `synced_trips` row matches - a no-op
// the server absorbs without complaint - and the exchange then clears the
// ledger and records a watermark, so from the outside it looks exactly like
// a working sync while the day hike itself never travels. The two stores get
// two ledgers, two record functions, and two exchanges; nothing is shared
// but the shape.
//
// One difference from the trips ledger, by subtraction: no `hikeDirty` /
// `hikeSeen` pair, because there is no planned-hike singleton riding this
// exchange - that pair exists for `ourhike:hike`, which syncs with the trips.

import { get, set } from 'idb-keyval'

export const DAY_HIKES_SYNC_KEY = 'ourhike:day-hikes:sync'

export interface DayHikeSyncState {
  /** Day hikes changed on this device since its last successful sync. */
  dirty: string[]
  /**
   * Day hikes the hiker deleted here, waiting to travel as tombstones.
   *
   * Kept until the server has been told, and deliberately NOT derived from
   * the store's contents - see the trips ledger's header. An id can be in
   * here and absent from `seen` (deleted before it ever synced), and the
   * tombstone still travels, because another device may hold the hike and
   * would otherwise re-upload it for ever.
   */
  deleted: string[]
  /** The server's `updated_at` for each day hike, as this device last saw it. */
  seen: Record<string, string>
  /** The watermark from the last successful sync, or null on a first run. */
  since: string | null
}

const NEVER_SYNCED: DayHikeSyncState = {
  dirty: [],
  deleted: [],
  seen: {},
  since: null,
}

function ids(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((id): id is string => typeof id === 'string')
    : []
}

/**
 * The ledger, repaired rather than trusted.
 *
 * Every field falls back to its never-synced value independently, and the
 * direction is the trips ledger's: a half-written ledger reading as "never
 * synced" costs a re-upload and a round of conflict copies; reading it as
 * "synced and clean" would lose whatever it was in the middle of recording.
 */
export async function dayHikeSyncState(): Promise<DayHikeSyncState> {
  const stored = (await get(DAY_HIKES_SYNC_KEY)) as Partial<DayHikeSyncState> | undefined
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
  }
}

async function write(next: DayHikeSyncState): Promise<void> {
  await set(DAY_HIKES_SYNC_KEY, next)
}

/**
 * Record what the hiker just did to their day hikes on THIS device.
 *
 * Called by `saveDayHikes` with the store as it was and as it now is, so a
 * deletion is recorded because the hiker deleted something, never because a
 * read came back empty. Every surviving hike is marked rather than only the
 * changed one, for `recordTripEdits`' reason: over-marking costs an upload
 * the server recognises as identical, under-marking loses an edit.
 */
export async function recordDayHikeEdits(
  before: readonly { id: string }[],
  after: readonly { id: string }[],
): Promise<void> {
  const state = await dayHikeSyncState()
  const remaining = new Set(after.map((hike) => hike.id))
  const gone = before.map((hike) => hike.id).filter((id) => !remaining.has(id))

  const dirty = new Set([...state.dirty, ...remaining])
  gone.forEach((id) => dirty.delete(id))

  await write({
    ...state,
    dirty: [...dirty],
    deleted: [...new Set([...state.deleted, ...gone])],
  })
}

/**
 * Record a completed exchange: this device is level with the account again.
 *
 * `keptSeen` replaces the whole stamp map rather than merging into it, so a
 * day hike that no longer exists anywhere stops being carried for ever. The
 * caller builds it from what the server just said plus what it already knew.
 */
export async function recordDayHikeSync(
  since: string,
  keptSeen: Record<string, string>,
): Promise<void> {
  await write({
    dirty: [],
    deleted: [],
    seen: keptSeen,
    since,
  })
}

/**
 * Forget the sync bookkeeping, keeping every day hike.
 *
 * What sign-out does, for `forgetTripSync`'s reason: the hikes are the
 * phone's, but `since` and `seen` are claims about an account this device no
 * longer has, and leaving them would let the next sign-in - possibly by
 * somebody else on a shared handset - upload one person's day hikes into
 * another person's account as ordinary edits.
 */
export async function forgetDayHikeSync(): Promise<void> {
  await write(NEVER_SYNCED)
}
