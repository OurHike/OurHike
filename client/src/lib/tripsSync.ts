// Trips and the planned hike follow the account (#892, ACCOUNT_SYNC.md B).
//
// A section hiker lays out four days on a laptop and leaves with a phone.
// Until this, the laptop's plan did not exist on the phone in any form.
//
// WHAT IS HERE AND WHAT IS ON THE SERVER
//
// **The conflict rule is not here.** `backend/app/core/trip_sync.py` owns
// it, because the server is the only party that can see both versions - a
// device knows what it did and what it last heard, and cannot know that a
// laptop in another time zone edited the same trip an hour ago. This module
// offers what changed, takes back what the server decided, and applies it.
//
// That division matters for a specific failure: if each device implemented
// keep-both, two devices implementing it slightly differently would produce
// a divergence that looks exactly like the data loss the rule exists to
// prevent.
//
// WHAT THIS ADDS THAT PHASE A DID NOT NEED
//
// `lib/preferencesSync.ts` reconciles one document. This reconciles many,
// which brings two things with it:
//
//  - **A delta.** Every sync sends only what this device changed and asks
//    only for what moved since its watermark. A full upload of every trip on
//    every run would be a hiker's whole planning history over a connection
//    this app assumes is bad.
//  - **Deletions that travel.** A trip missing from a device is not evidence
//    it was deleted; a phone in a rucksack since March is not a claim about
//    March's trips. So a delete is recorded when the hiker performs it
//    (lib/tripSyncState.ts) and sent as a tombstone.
//
// NO WRITE WAITS ON THE NETWORK, as in phase A. Trips save to IndexedDB
// exactly as before; this is a reconciliation on top, and an offline device,
// an unconfigured build and a signed-out hiker are all silent no-ops.

import { syncTrips, type SyncedTripRow, type TripUpload } from './api'
import { adoptPlannedHike, loadPlannedHike, type PlannedHike } from './plannedHike'
import {
  forgetTripSync,
  recordTripSync,
  tripSyncState,
  type TripSyncState,
} from './tripSyncState'
import {
  adoptTrips,
  loadTrips,
  validateTripStore,
  type Trip,
  type TripStore,
} from './trips'

export { forgetTripSync }

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
    'Trip sync failed for a reason that is not offline, signed out or unconfigured. ' +
      'Nothing was lost - every trip is still on this device, and the changes stay ' +
      'queued for the next attempt (#892).',
    error,
  )
}

/** What this device has to offer, from the ledger and the store. */
export function uploadsFor(store: TripStore, state: TripSyncState): TripUpload[] {
  const byId = new Map(store.trips.map((trip) => [trip.id, trip]))
  const deleted = new Set(state.deleted)

  const edits = state.dirty
    // A trip both dirty and deleted is a trip the hiker edited and then
    // binned. The delete is the later act and the one that travels.
    .filter((id) => !deleted.has(id))
    .flatMap((id) => {
      const trip = byId.get(id)
      // Dirty with no trip behind it: the ledger and the store disagree,
      // which a half-written save can produce. Sending nothing is right -
      // an upload with no document would read as a deletion the hiker never
      // performed, which is the one thing this feature must not invent.
      if (trip === undefined) return []
      return [
        {
          id,
          document: trip as unknown,
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
function tripFrom(row: SyncedTripRow): Trip | null {
  const store = validateTripStore({ trips: [row.document], openId: null })
  const record = store?.trips[0]
  if (record === undefined) return null
  return record.id === row.id ? record : { ...record, id: row.id }
}

/**
 * Fold what the server sent into the store this device holds.
 *
 * Pure, and exported so the merge can be argued with directly. Three rules,
 * and the third is the one worth reading twice:
 *
 *  1. A tombstone removes the trip, wherever it is - that is the hiker's own
 *     delete arriving from their other device.
 *  2. A row this device does not have is added.
 *  3. A row this device DOES have is replaced by the server's version.
 *
 * Rule 3 cannot lose an edit, and that is a property of the exchange rather
 * than of this function: anything this device had changed was uploaded in
 * the same request, and the server either accepted it (so the row coming
 * back IS this device's edit) or kept both (so this device's version is
 * coming back too, under a new id). Replacing is what makes those land.
 */
export function mergeServerTrips(
  store: TripStore,
  rows: readonly SyncedTripRow[],
): TripStore {
  let trips = store.trips

  for (const row of rows) {
    if (row.deleted_at !== null) {
      trips = trips.filter((trip) => trip.id !== row.id)
      continue
    }
    const incoming = tripFrom(row)
    if (incoming === null) continue

    const at = trips.findIndex((trip) => trip.id === row.id)
    trips =
      at === -1 ? [...trips, incoming] : trips.map((t, i) => (i === at ? incoming : t))
  }

  if (trips === store.trips) return store

  const live = new Set(trips.map((trip) => trip.id))
  return {
    ...store,
    trips,
    // A pointer to a trip another device deleted would leave the Plan tab
    // showing nothing with no way back, which `removeTrip` already guards
    // against for a local delete.
    openId:
      store.openId !== null && live.has(store.openId)
        ? store.openId
        : (trips[0]?.id ?? null),
    // Same reasoning as `removeTrip`: a hike or a group naming a trip
    // nobody can open would count miles from a plan that is gone.
    hikes: store.hikes.map((hike) => ({
      ...hike,
      tripIds: hike.tripIds.filter((id) => live.has(id)),
    })),
    groups: store.groups.map((group) => ({
      ...group,
      tripIds: group.tripIds.filter((id) => live.has(id)),
    })),
  }
}

/** The stamp map to carry forward: what the server just said, plus what this
 *  device already knew about trips the response did not mention. Tombstoned
 *  ids are dropped - a stamp for a trip that is gone everywhere is a row
 *  this ledger would carry for ever. */
export function stampsAfter(
  state: TripSyncState,
  rows: readonly SyncedTripRow[],
): Record<string, string> {
  const seen = { ...state.seen }
  for (const row of rows) {
    if (row.deleted_at !== null) delete seen[row.id]
    else seen[row.id] = row.updated_at
  }
  for (const id of state.deleted) delete seen[id]
  return seen
}

async function applyHike(
  hike: { start_mile: number | null; end_mile: number | null } | null,
): Promise<void> {
  if (hike === null) return
  if (hike.start_mile === null || hike.end_mile === null) {
    // Both miles null is the hiker having cleared it on another device -
    // a decision with a date on it, so it is applied rather than ignored.
    await adoptPlannedHike(null)
    return
  }
  await adoptPlannedHike({ startMile: hike.start_mile, endMile: hike.end_mile })
}

/**
 * Reconcile this device with the account.
 *
 * Returns the store to adopt, or null when nothing changed - and **never
 * rejects.** Its only caller is a background effect, so a rejection would be
 * an unhandled one; phase A shipped that bug once and it is not worth
 * shipping twice.
 */
export async function syncTripsWithAccount(): Promise<TripStore | null> {
  try {
    const store = await loadTrips()
    const state = await tripSyncState()
    const hike = await loadPlannedHike()

    const uploads = uploadsFor(store, state)

    const response = await syncTrips({
      since: state.since,
      trips: uploads,
      // Sent only when this device has something to say, so a device that
      // has never had a planned hike cannot wipe the one the hiker set on
      // another. Omission and "both miles null" are different claims.
      ...(state.hikeDirty
        ? {
            hike: {
              start_mile: hike?.startMile ?? null,
              end_mile: hike?.endMile ?? null,
              base_updated_at: state.hikeSeen,
            },
          }
        : {}),
    })

    // The ledger is cleared BEFORE the store is written, and the order is
    // deliberate: a crash between the two leaves a device that re-syncs
    // trips it already sent, which the server recognises as identical and
    // drops. The other order leaves a device that has adopted the account's
    // trips while still claiming its own local edits are unsent - and those
    // would be uploaded over what it just adopted.
    await recordTripSync(
      response.now,
      stampsAfter(state, response.trips),
      response.hike?.updated_at ?? null,
      // Only what actually went out (#1040). The hiker keeps using the app
      // while the request is in the air, and anything they changed since
      // this snapshot has not been sent by anybody.
      {
        dirty: uploads.filter((upload) => !upload.deleted).map((upload) => upload.id),
        deleted: uploads.filter((upload) => upload.deleted).map((upload) => upload.id),
      },
    )
    await applyHike(response.hike)

    // RE-READ, rather than merging into the snapshot taken before the
    // request (#1040). `store` is what this device held when the request
    // left; writing a merge built on it back to disk discarded every edit
    // made while it was in the air. Measured: with any row at all coming
    // back, a trip renamed mid-flight reverted to its old name and the
    // rename was gone from the device as well as from the account.
    const current = await loadTrips()
    const merged = mergeServerTrips(current, response.trips)
    if (merged === current) return null
    await adoptTrips(merged)
    return merged
  } catch (error) {
    if (!isOrdinarySilence(error)) reportSyncFailure(error)
    return null
  }
}

export type { PlannedHike }
