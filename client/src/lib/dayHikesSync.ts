// Day hikes follow the account from day one (#976, the maintainer's decision
// 2026-08-25) - lib/tripsSync.ts's reconciliation, mirrored for the other
// store.
//
// That file's header holds the arguments and they carry over whole: **the
// conflict rule is not here** (the server is the only party that can see
// both versions, and keep-both implemented twice slightly differently would
// look exactly like the data loss it exists to prevent); every sync is a
// delta against a watermark rather than a full upload; deletions travel as
// recorded tombstones because a hike missing from a device is not evidence
// it was deleted. NO WRITE WAITS ON THE NETWORK - day hikes save to
// IndexedDB exactly as before, and an offline device, an unconfigured build
// and a signed-out hiker are all silent no-ops.
//
// What is deliberately NOT mirrored: the planned-hike singleton. Nothing
// like `ourhike:hike` rides this exchange, so there is no `applyHike`, no
// `hikeDirty`, and no `hike` field in the payload - see
// lib/dayHikeSyncState.ts, which also states the rule this split exists to
// keep: day-hike ids never enter the trips ledger, and trips ids never enter
// this one.

import { syncDayHikes, type DayHikeUpload, type SyncedDayHikeRow } from './api'
import {
  dayHikeSyncState,
  forgetDayHikeSync,
  recordDayHikeSync,
  type DayHikeSyncState,
} from './dayHikeSyncState'
import {
  adoptDayHikes,
  loadDayHikes,
  validateDayHikeStore,
  type DayHike,
  type DayHikeStore,
} from './dayHikes'

export { forgetDayHikeSync }

/** The three states that are not faults, by name rather than by class -
 *  `lib/preferencesSync.ts` explains why the classification must not read a
 *  value off the api module. */
const SILENT_FAILURES = new Set([
  'ApiNotConfiguredError',
  'NotSignedInError',
  'TypeError',
])

function isOrdinarySilence(error: unknown): boolean {
  return error instanceof Error && SILENT_FAILURES.has(error.name)
}

function reportSyncFailure(error: unknown): void {
  console.error(
    'Day-hike sync failed for a reason that is not offline, signed out or ' +
      'unconfigured. Nothing was lost - every day hike is still on this device, ' +
      'and the changes stay queued for the next attempt (#976).',
    error,
  )
}

/** What this device has to offer, from the ledger and the store. */
export function uploadsFor(
  store: DayHikeStore,
  state: DayHikeSyncState,
): DayHikeUpload[] {
  const byId = new Map(store.hikes.map((hike) => [hike.id, hike]))
  const deleted = new Set(state.deleted)

  const edits = state.dirty
    // A hike both dirty and deleted is a hike the hiker edited and then
    // binned. The delete is the later act and the one that travels.
    .filter((id) => !deleted.has(id))
    .flatMap((id) => {
      const hike = byId.get(id)
      // Dirty with no hike behind it: the ledger and the store disagree,
      // which a half-written save can produce. Sending nothing is right -
      // an upload with no document would read as a deletion the hiker never
      // performed, which is the one thing this feature must not invent.
      if (hike === undefined) return []
      return [
        {
          id,
          document: hike as unknown,
          base_updated_at: state.seen[id] ?? null,
          deleted: false,
        },
      ]
    })

  const tombstones = state.deleted.map((id) => ({
    id,
    document: null,
    base_updated_at: state.seen[id] ?? null,
    deleted: true,
  }))

  return [...edits, ...tombstones]
}

/**
 * The record a server row carries, identified by the ROW.
 *
 * The document carries its own `id` and normally the two agree - an upload
 * sends `{id, document}` minted together on the phone. They disagree in
 * exactly one case, and it is the case that matters: a conflict copy, which
 * the server writes under a fresh row id to keep beside the record it lost
 * to. A copy whose document still said the original's id landed on top of
 * the very trip it was created to preserve (#1036).
 *
 * The server is the one that mints a copy's identity, so it is fixed there
 * too - `trip_sync.document_for_copy` now sets both. This is the belt: a
 * phone talking to a server that has not been redeployed yet still keeps
 * both records rather than silently collapsing them, and the row id is the
 * identity the server files the record under either way.
 */
function dayHikeFrom(row: SyncedDayHikeRow): DayHike | null {
  const store = validateDayHikeStore({ hikes: [row.document], openId: null })
  const record = store?.hikes[0]
  if (record === undefined) return null
  return record.id === row.id ? record : { ...record, id: row.id }
}

/**
 * Fold what the server sent into the store this device holds.
 *
 * Pure, and exported so the merge can be argued with directly. The same
 * three rules as `mergeServerTrips`, including the one worth reading twice:
 * replacing a row this device has (rule 3) cannot lose an edit, because
 * anything this device changed was uploaded in the same request, and the
 * server either accepted it (the row coming back IS this device's edit) or
 * kept both (this device's version is coming back too, under a new id -
 * which is how a conflict lands as two hikes rather than a loss).
 *
 * The openId repair is this store's: a pointer at a hike another device
 * deleted becomes null, matching `validateDayHikeStore` - not trips'
 * first-item fallback.
 */
export function mergeServerDayHikes(
  store: DayHikeStore,
  rows: readonly SyncedDayHikeRow[],
): DayHikeStore {
  let hikes = store.hikes

  for (const row of rows) {
    if (row.deleted_at !== null) {
      hikes = hikes.filter((hike) => hike.id !== row.id)
      continue
    }
    const incoming = dayHikeFrom(row)
    if (incoming === null) continue

    const at = hikes.findIndex((hike) => hike.id === row.id)
    hikes =
      at === -1 ? [...hikes, incoming] : hikes.map((h, i) => (i === at ? incoming : h))
  }

  if (hikes === store.hikes) return store

  const live = new Set(hikes.map((hike) => hike.id))
  return {
    hikes,
    openId: store.openId !== null && live.has(store.openId) ? store.openId : null,
  }
}

/** The stamp map to carry forward: what the server just said, plus what this
 *  device already knew about hikes the response did not mention. Tombstoned
 *  ids are dropped - a stamp for a hike that is gone everywhere is a row
 *  this ledger would carry for ever. */
export function stampsAfter(
  state: DayHikeSyncState,
  rows: readonly SyncedDayHikeRow[],
): Record<string, string> {
  const seen = { ...state.seen }
  for (const row of rows) {
    if (row.deleted_at !== null) delete seen[row.id]
    else seen[row.id] = row.updated_at
  }
  for (const id of state.deleted) delete seen[id]
  return seen
}

/**
 * Reconcile this device with the account.
 *
 * Returns the store to adopt, or null when nothing changed - and **never
 * rejects.** Its only caller is a background effect, so a rejection would be
 * an unhandled one; the preferences sync shipped that bug once and it is not
 * worth shipping a third time.
 */
export async function syncDayHikesWithAccount(): Promise<DayHikeStore | null> {
  try {
    const store = await loadDayHikes()
    const state = await dayHikeSyncState()

    const response = await syncDayHikes({
      since: state.since,
      day_hikes: uploadsFor(store, state),
    })

    // The ledger is cleared BEFORE the store is written, and the order is
    // deliberate - `syncTripsWithAccount` states it: a crash between the two
    // re-sends what the server recognises as identical and drops; the other
    // order uploads stale local claims over what was just adopted.
    await recordDayHikeSync(response.now, stampsAfter(state, response.day_hikes))

    const merged = mergeServerDayHikes(store, response.day_hikes)
    if (merged === store) return null
    await adoptDayHikes(merged)
    return merged
  } catch (error) {
    if (!isOrdinarySilence(error)) reportSyncFailure(error)
    return null
  }
}
