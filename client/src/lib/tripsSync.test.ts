import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { get, set, del } from 'idb-keyval'
import { syncTrips } from './api'
import {
  mergeServerTrips,
  stampsAfter,
  syncTripsWithAccount,
  uploadsFor,
} from './tripsSync'
import { EMPTY_STORE, removeTrip, TRIPS_KEY, type Trip, type TripStore } from './trips'
import { buildPlan, type HikePlan } from './plan'
import { PLANNED_HIKE_KEY } from './plannedHike'
import { TRIPS_SYNC_KEY, tripSyncState } from './tripSyncState'

// Trips following the account (#892), from this device's side.
//
// The conflict rule is the server's and is tested in
// backend/tests/test_core_trip_sync.py. What is tested here is everything a
// device can get wrong on its own, and the two that would be worst are both
// silent:
//
//   - **adopting what the account sent and then pushing it straight back**,
//     which looks from the outside exactly like a sync that works and never
//     stops; and
//   - **inventing a deletion**, which is the one thing
//     features/ACCOUNT_SYNC.md forbids outright.

vi.mock('idb-keyval', () => ({
  get: vi.fn(),
  set: vi.fn(),
  del: vi.fn(),
  update: vi.fn(),
}))
vi.mock('./api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./api')>()),
  syncTrips: vi.fn(),
}))

const store = new Map<string, unknown>()
const NOW = '2026-08-21T12:00:00Z'
const EARLIER = '2026-08-21T09:00:00Z'

/** A real plan, because `validateTripStore` refuses shapes it does not
 *  recognise - and a fake one would make every merge test pass by dropping
 *  the trip it was supposed to be merging. */
function plan(): HikePlan {
  return buildPlan(
    [
      { mile: 470.8, name: 'Damascus', resupply: false },
      { mile: 503.3, name: 'Atkins', resupply: false },
    ],
    { walkingHours: 7 },
  )
}

function trip(id = 'trip-1', name = 'Grayson Highlands'): Trip {
  return { id, name, plan: plan() }
}

function storeWith(...trips: Trip[]): TripStore {
  return { ...EMPTY_STORE, trips, openId: trips[0]?.id ?? null }
}

function row(id = 'trip-1', name = 'Grayson Highlands', over = {}) {
  return { id, document: trip(id, name), updated_at: NOW, deleted_at: null, ...over }
}

beforeEach(() => {
  store.clear()
  vi.mocked(get).mockImplementation((key) => Promise.resolve(store.get(key as string)))
  vi.mocked(set).mockImplementation((key, value) => {
    store.set(key as string, value)
    return Promise.resolve()
  })
  vi.mocked(del).mockImplementation((key) => {
    store.delete(key as string)
    return Promise.resolve()
  })
  vi.mocked(syncTrips).mockReset()
  vi.mocked(syncTrips).mockResolvedValue({
    now: NOW,
    trips: [],
    hike: null,
    conflicts: 0,
  })
  vi.spyOn(console, 'error').mockImplementation(() => {})
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('what this device offers', () => {
  const clean = {
    dirty: [],
    deleted: [],
    seen: {},
    since: null,
    hikeDirty: false,
    hikeSeen: null,
  }

  it('offers nothing when nothing changed here', () => {
    expect(uploadsFor(storeWith(trip()), clean)).toEqual([])
  })

  it('offers a changed trip with the stamp it was working from', () => {
    // Built once and reused: `buildPlan` mints a fresh id per day, so two
    // calls to `trip()` are not equal and comparing against a second one
    // would fail for a reason that has nothing to do with syncing.
    const changed = trip()

    const uploads = uploadsFor(storeWith(changed), {
      ...clean,
      dirty: ['trip-1'],
      seen: { 'trip-1': EARLIER },
    })

    expect(uploads).toEqual([
      { id: 'trip-1', document: changed, base_updated_at: EARLIER, deleted: false },
    ])
  })

  it('offers a brand-new trip with no stamp at all', () => {
    // Null is "this device believes this is new", which the server reads as
    // a claim rather than as a missing field.
    expect(
      uploadsFor(storeWith(trip()), { ...clean, dirty: ['trip-1'] })[0].base_updated_at,
    ).toBe(null)
  })

  it('offers a deletion as a tombstone rather than as an omission', () => {
    const uploads = uploadsFor(storeWith(), { ...clean, deleted: ['trip-1'] })

    expect(uploads).toEqual([
      { id: 'trip-1', document: null, base_updated_at: null, deleted: true },
    ])
  })

  it('sends the delete, not the edit, for a trip edited and then binned', () => {
    const uploads = uploadsFor(storeWith(), {
      ...clean,
      dirty: ['trip-1'],
      deleted: ['trip-1'],
    })

    expect(uploads.map((u) => u.deleted)).toEqual([true])
  })

  it('never turns a dirty id with no trip behind it into a deletion', () => {
    // A half-written save can leave the ledger and the store disagreeing.
    // An upload with no document would read as a delete the hiker never
    // performed, which is the one thing this feature must not invent.
    expect(uploadsFor(storeWith(), { ...clean, dirty: ['ghost'] })).toEqual([])
  })
})

describe('folding in what the account sent', () => {
  it('adds a trip this device has never seen', () => {
    const merged = mergeServerTrips(EMPTY_STORE, [row()])

    expect(merged.trips.map((t) => t.id)).toEqual(['trip-1'])
  })

  it('replaces a trip this device already has', () => {
    const merged = mergeServerTrips(storeWith(trip()), [
      row('trip-1', 'Renamed elsewhere'),
    ])

    expect(merged.trips.map((t) => t.name)).toEqual(['Renamed elsewhere'])
  })

  it('applies a tombstone, because that is the hiker’s own delete arriving', () => {
    const merged = mergeServerTrips(storeWith(trip()), [
      row('trip-1', 'gone', { document: null, deleted_at: NOW }),
    ])

    expect(merged.trips).toEqual([])
  })

  it('never leaves the Plan tab pointing at a trip another device deleted', () => {
    const merged = mergeServerTrips(storeWith(trip('trip-1'), trip('trip-2', 'Second')), [
      row('trip-1', 'gone', { document: null, deleted_at: NOW }),
    ])

    expect(merged.openId).toBe('trip-2')
  })

  it('drops a deleted trip out of the hikes and groups that named it', () => {
    const base: TripStore = {
      ...storeWith(trip()),
      hikes: [{ id: 'h1', name: 'Virginia', tripIds: ['trip-1'] } as never],
      groups: [{ id: 'g1', name: 'With Dad', tripIds: ['trip-1'] } as never],
    }

    const merged = mergeServerTrips(base, [
      row('trip-1', 'gone', { document: null, deleted_at: NOW }),
    ])

    expect(merged.hikes[0].tripIds).toEqual([])
    expect(merged.groups[0].tripIds).toEqual([])
  })

  it('drops one unreadable trip rather than the whole response', () => {
    // validateTripStore refuses per trip for exactly this reason: one trip
    // written by a newer build must not cost a hiker every other one.
    const merged = mergeServerTrips(EMPTY_STORE, [
      { id: 'bad', document: { nonsense: true }, updated_at: NOW, deleted_at: null },
      row('trip-2', 'Fine'),
    ])

    expect(merged.trips.map((t) => t.id)).toEqual(['trip-2'])
  })

  it('is the same object when nothing arrived, so nothing is rewritten', () => {
    const before = storeWith(trip())

    expect(mergeServerTrips(before, [])).toBe(before)
  })
})

// #1036: the backend keeps both sides of a conflict by writing the loser
// beside the winner. That only works if the copy is a separate record, and
// the client identifies a record by the id inside its DOCUMENT - so these
// drive the merge with the row pairs `trip_sync.resolve_upload` emits.
describe('a conflict copy survives as its own trip (#1036)', () => {
  /** What the server sends for edit-vs-edit: the winner untouched, and the
   *  loser beside it under a fresh id - in its row AND in its document. */
  const editVsEdit = [
    row('trip-1', 'Grayson Highlands, four days'),
    {
      id: 'copy-1',
      document: trip(
        'copy-1',
        'Grayson Highlands, three days (edited on another device)',
      ),
      updated_at: NOW,
      deleted_at: null,
    },
  ]

  it('keeps both, under two different ids', () => {
    const merged = mergeServerTrips(storeWith(trip()), editVsEdit)

    expect(merged.trips.map((t) => t.id).sort()).toEqual(['copy-1', 'trip-1'])
  })

  it('deleting one afterwards does not take the other with it', () => {
    // The consequence that made the old shape dangerous rather than untidy:
    // two records sharing an id meant `removeTrip` deleted both.
    const merged = mergeServerTrips(storeWith(trip()), editVsEdit)
    const after = removeTrip(merged, 'trip-1')

    expect(after.trips.map((t) => t.id)).toEqual(['copy-1'])
  })

  it('keeps both even from a server that has not been redeployed', () => {
    // The belt: a legacy copy row whose DOCUMENT still carries the original's
    // id. The row id is the identity the server filed it under, so the merge
    // takes that and the two records stay two.
    const legacyCopy = {
      id: 'copy-1',
      document: trip('trip-1', 'Grayson Highlands, three days (edited elsewhere)'),
      updated_at: NOW,
      deleted_at: null,
    }
    const merged = mergeServerTrips(storeWith(trip()), [
      row('trip-1', 'Grayson Highlands, four days'),
      legacyCopy,
    ])

    expect(merged.trips.map((t) => t.id).sort()).toEqual(['copy-1', 'trip-1'])
    expect(removeTrip(merged, 'trip-1').trips.map((t) => t.id)).toEqual(['copy-1'])
  })

  it('survives delete-vs-edit whichever order the rows arrive in', () => {
    // The tombstone is keyed on the original id and the copy is not, so the
    // outcome no longer depends on an order nothing in the exchange pins.
    const tombstone = row('trip-1', 'gone', { document: null, deleted_at: NOW })
    const copy = {
      id: 'copy-1',
      document: trip('copy-1', 'Grayson Highlands, four days (edited on another device)'),
      updated_at: NOW,
      deleted_at: null,
    }

    const tombstoneFirst = mergeServerTrips(storeWith(trip()), [tombstone, copy])
    const copyFirst = mergeServerTrips(storeWith(trip()), [copy, tombstone])

    expect(tombstoneFirst.trips.map((t) => t.id)).toEqual(['copy-1'])
    expect(copyFirst.trips.map((t) => t.id)).toEqual(['copy-1'])
  })
})

describe('the stamps carried forward', () => {
  const state = {
    dirty: [],
    deleted: ['old'],
    seen: { 'trip-1': EARLIER, old: EARLIER, untouched: EARLIER },
    since: null,
    hikeDirty: false,
    hikeSeen: null,
  }

  it('takes the server’s new stamp for a trip it sent', () => {
    expect(stampsAfter(state, [row()])['trip-1']).toBe(NOW)
  })

  it('keeps what it already knew about a trip the response did not mention', () => {
    expect(stampsAfter(state, [row()]).untouched).toBe(EARLIER)
  })

  it('stops carrying a stamp for a trip that is gone everywhere', () => {
    const after = stampsAfter(state, [
      row('trip-1', 'gone', { document: null, deleted_at: NOW }),
    ])

    expect(after).not.toHaveProperty('trip-1')
    expect(after).not.toHaveProperty('old')
  })
})

describe('a whole exchange', () => {
  it('adopts the account’s trips on a device that had none', async () => {
    vi.mocked(syncTrips).mockResolvedValue({
      now: NOW,
      trips: [row()],
      hike: null,
      conflicts: 0,
    })

    const adopted = await syncTripsWithAccount()

    expect(adopted?.trips.map((t) => t.id)).toEqual(['trip-1'])
    expect(store.get(TRIPS_KEY)).toMatchObject({
      trips: [expect.objectContaining({ id: 'trip-1' })],
    })
  })

  it('does NOT push back what it just pulled', async () => {
    // The loop that would look exactly like a sync that works. Adopting has
    // to go through the path that does not mark the store dirty.
    vi.mocked(syncTrips).mockResolvedValue({
      now: NOW,
      trips: [row()],
      hike: null,
      conflicts: 0,
    })
    await syncTripsWithAccount()

    expect(await tripSyncState()).toMatchObject({ dirty: [], deleted: [] })

    vi.mocked(syncTrips).mockClear()
    vi.mocked(syncTrips).mockResolvedValue({
      now: NOW,
      trips: [],
      hike: null,
      conflicts: 0,
    })
    await syncTripsWithAccount()

    expect(vi.mocked(syncTrips).mock.calls[0][0].trips).toEqual([])
  })

  it('records the watermark so the next sync asks only for what moved', async () => {
    await syncTripsWithAccount()

    expect((await tripSyncState()).since).toBe(NOW)
  })

  it('says nothing about the planned hike unless this device changed it', async () => {
    store.set(PLANNED_HIKE_KEY, { startMile: 100, endMile: 200 })

    await syncTripsWithAccount()

    expect(vi.mocked(syncTrips).mock.calls[0][0]).not.toHaveProperty('hike')
  })

  it('sends the planned hike once this device has changed it', async () => {
    store.set(PLANNED_HIKE_KEY, { startMile: 100, endMile: 200 })
    store.set(TRIPS_SYNC_KEY, {
      dirty: [],
      deleted: [],
      seen: {},
      since: null,
      hikeDirty: true,
      hikeSeen: EARLIER,
    })

    await syncTripsWithAccount()

    expect(vi.mocked(syncTrips).mock.calls[0][0].hike).toEqual({
      start_mile: 100,
      end_mile: 200,
      base_updated_at: EARLIER,
    })
  })

  it('adopts a planned hike cleared on another device', async () => {
    store.set(PLANNED_HIKE_KEY, { startMile: 100, endMile: 200 })
    vi.mocked(syncTrips).mockResolvedValue({
      now: NOW,
      trips: [],
      hike: { start_mile: null, end_mile: null, updated_at: NOW },
      conflicts: 0,
    })

    await syncTripsWithAccount()

    expect(store.has(PLANNED_HIKE_KEY)).toBe(false)
    expect((await tripSyncState()).hikeDirty).toBe(false)
  })
})

describe('the silences', () => {
  it.each([
    ['no backend configured', 'ApiNotConfiguredError'],
    ['signed out', 'NotSignedInError'],
    ['no signal', 'TypeError'],
  ])('is a quiet no-op when %s', async (_why, name) => {
    const failure = new Error('nope')
    failure.name = name
    vi.mocked(syncTrips).mockRejectedValue(failure)

    expect(await syncTripsWithAccount()).toBeNull()
    expect(console.error).not.toHaveBeenCalled()
  })

  it('leaves the changes queued when the exchange cannot land', async () => {
    store.set(TRIPS_KEY, storeWith(trip()))
    store.set(TRIPS_SYNC_KEY, {
      dirty: ['trip-1'],
      deleted: [],
      seen: {},
      since: null,
      hikeDirty: false,
      hikeSeen: null,
    })
    const offline = new Error('Failed to fetch')
    offline.name = 'TypeError'
    vi.mocked(syncTrips).mockRejectedValue(offline)

    await syncTripsWithAccount()

    expect((await tripSyncState()).dirty).toEqual(['trip-1'])
  })

  it('says a real refusal out loud, and still never rejects', async () => {
    const refused = new Error('PUT failed: 500')
    refused.name = 'ApiError'
    vi.mocked(syncTrips).mockRejectedValue(refused)

    await expect(syncTripsWithAccount()).resolves.toBeNull()
    expect(console.error).toHaveBeenCalled()
  })
})
