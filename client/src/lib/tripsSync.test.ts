import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { get, set, del } from 'idb-keyval'
import { syncTrips } from './api'
import {
  applyActiveHike,
  hikeStampsAfter,
  hikeUploadsFor,
  mergeServerHikes,
  mergeServerTrips,
  stampsAfter,
  syncTripsWithAccount,
  uploadsFor,
} from './tripsSync'
import type { Hike } from './hikes'
import { EMPTY_STORE, removeTrip, TRIPS_KEY, type Trip, type TripStore } from './trips'
import { buildPlan, type HikePlan } from './plan'
import { PLANNED_HIKE_KEY } from './plannedHike'
import {
  recordTripEdits,
  TRIPS_SYNC_KEY,
  tripSyncState,
  type TripSyncState,
} from './tripSyncState'

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
    hikesDirty: [],
    hikesDeleted: [],
    hikesSeen: {},
    activeHikeDirty: false,
    activeHikeSeen: null,
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
  const state: TripSyncState = {
    dirty: [],
    deleted: ['old'],
    seen: { 'trip-1': EARLIER, old: EARLIER, untouched: EARLIER },
    since: null,
    hikeDirty: false,
    hikeSeen: null,
    hikesDirty: [],
    hikesDeleted: [],
    hikesSeen: {},
    activeHikeDirty: false,
    activeHikeSeen: null,
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

// #1040: a sync is not instant, and the hiker keeps using the app while the
// request is in the air. Both of these were measured on the shipped code
// before the fix, and they fail differently, which is why both are here.
describe('an edit made while the request is in flight', () => {
  /** A request that does not resolve until the test says so. */
  function heldRequest(rows: unknown[] = []) {
    let release: () => void = () => {}
    const held = new Promise<void>((resolve) => {
      release = resolve
    })
    vi.mocked(syncTrips).mockReturnValue(
      held.then(() => ({
        now: NOW,
        trips: rows as never,
        hike: null,
        conflicts: 0,
      })) as never,
    )
    return () => release()
  }

  it('stays queued to send, rather than being marked as sent by nobody', async () => {
    // The half that survives on disk and never travels: the ledger used to
    // be cleared wholesale, so an edit made mid-flight was recorded as sent
    // when nothing had sent it - and it sat on this device for ever.
    store.set(TRIPS_KEY, storeWith(trip()))
    const release = heldRequest()

    const syncing = syncTripsWithAccount()
    store.set(TRIPS_KEY, storeWith({ ...trip(), name: 'Renamed mid-flight' }))
    await recordTripEdits([], [trip()])
    release()
    await syncing

    expect((await tripSyncState()).dirty).toContain('trip-1')
  })

  it('is not overwritten by the store the request was built from', async () => {
    // The worse half: with any row at all coming back, the merge was built
    // on the pre-request snapshot and written over the top, so the rename
    // was gone from the device as well as from the account.
    store.set(TRIPS_KEY, storeWith(trip()))
    const release = heldRequest([
      {
        id: 'from-the-laptop',
        document: trip('from-the-laptop', 'Laid out on the laptop'),
        updated_at: NOW,
        deleted_at: null,
      },
    ])

    const syncing = syncTripsWithAccount()
    store.set(TRIPS_KEY, storeWith({ ...trip(), name: 'Renamed mid-flight' }))
    release()
    await syncing

    const after = store.get(TRIPS_KEY) as TripStore
    expect(after.trips.find((t) => t.id === 'trip-1')?.name).toBe('Renamed mid-flight')
    // And the laptop's trip still arrived - the fix must not cost the merge.
    expect(after.trips.map((t) => t.id).sort()).toEqual(['from-the-laptop', 'trip-1'])
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

// ---------------------------------------------------------------------------
// Long hikes and the pointer (#1317). The pointer is the reason the hikes
// travel at all: an id arriving on a device that has never heard of the hike
// names nothing.

function hike(id = 'hike-1', name = 'Springer → Katahdin'): Hike {
  return {
    id,
    name,
    type: 'thru',
    trailId: 'AT',
    points: [
      { name: 'Springer', mile: 0 },
      { name: 'Katahdin', mile: 2197.4 },
    ],
    status: 'walking',
    tripIds: [],
  }
}

function hikeRow(id = 'hike-1', name = 'Springer → Katahdin', over = {}) {
  return { id, document: hike(id, name), updated_at: NOW, deleted_at: null, ...over }
}

function storeWithHike(...hikes: Hike[]): TripStore {
  return { ...EMPTY_STORE, hikes }
}

describe('what this device offers of its long hikes', () => {
  const clean: TripSyncState = {
    dirty: [],
    deleted: [],
    seen: {},
    since: null,
    hikeDirty: false,
    hikeSeen: null,
    hikesDirty: [],
    hikesDeleted: [],
    hikesSeen: {},
    activeHikeDirty: false,
    activeHikeSeen: null,
  }

  it('offers nothing when nothing changed here', () => {
    expect(hikeUploadsFor(storeWithHike(hike()), clean)).toEqual([])
  })

  it('offers a changed hike with the stamp it was working from', () => {
    const changed = hike()
    const uploads = hikeUploadsFor(storeWithHike(changed), {
      ...clean,
      hikesDirty: ['hike-1'],
      hikesSeen: { 'hike-1': EARLIER },
    })

    expect(uploads).toEqual([
      { id: 'hike-1', document: changed, base_updated_at: EARLIER, deleted: false },
    ])
  })

  it('never sends a forget the hiker did not perform', () => {
    // Dirty with no hike behind it: the ledger and the store disagree, which
    // a half-written save produces. An upload with no document would read as
    // a forget, and forgetting somebody's hike is not something to infer.
    expect(hikeUploadsFor(EMPTY_STORE, { ...clean, hikesDirty: ['hike-1'] })).toEqual([])
  })

  it('sends the forget rather than the edit when the hiker did both', () => {
    const uploads = hikeUploadsFor(storeWithHike(hike()), {
      ...clean,
      hikesDirty: ['hike-1'],
      hikesDeleted: ['hike-1'],
    })

    expect(uploads).toEqual([
      { id: 'hike-1', document: null, base_updated_at: null, deleted: true },
    ])
  })
})

describe('folding the account’s long hikes back in', () => {
  it('adds a hike this device has never seen', () => {
    const merged = mergeServerHikes(EMPTY_STORE, [hikeRow()])
    expect(merged.hikes.map((h) => h.name)).toEqual(['Springer → Katahdin'])
  })

  it('replaces one it already has', () => {
    const merged = mergeServerHikes(storeWithHike(hike()), [
      hikeRow('hike-1', 'The whole thing'),
    ])
    expect(merged.hikes).toHaveLength(1)
    expect(merged.hikes[0].name).toBe('The whole thing')
  })

  it('applies a forget from another device, and releases the pointer with it', () => {
    // removeHike's own guarantee, arriving from somewhere else: the app must
    // not be left in a long-hike state naming a hike that is gone.
    const store = { ...storeWithHike(hike()), activeHikeId: 'hike-1' }
    const merged = mergeServerHikes(store, [
      hikeRow('hike-1', 'gone', { document: null, deleted_at: NOW }),
    ])

    expect(merged.hikes).toEqual([])
    expect(merged.activeHikeId).toBeNull()
  })

  it('skips a hike whose document this build cannot read', () => {
    const merged = mergeServerHikes(EMPTY_STORE, [
      { id: 'hike-1', document: { nonsense: true }, updated_at: NOW, deleted_at: null },
    ])
    expect(merged.hikes).toEqual([])
  })

  it('files the record under the ROW id, as tripFrom does', () => {
    const merged = mergeServerHikes(EMPTY_STORE, [
      { ...hikeRow('row-id'), document: hike('document-id') },
    ])
    expect(merged.hikes.map((h) => h.id)).toEqual(['row-id'])
  })
})

describe('the pointer at the hike the app is in', () => {
  it('says nothing when the account has never said', () => {
    const store = { ...storeWithHike(hike()), activeHikeId: 'hike-1' }
    expect(applyActiveHike(store, null)).toBe(store)
  })

  it('leaves the long-hike state when the account says null', () => {
    const store = { ...storeWithHike(hike()), activeHikeId: 'hike-1' }
    expect(applyActiveHike(store, { hike_id: null }).activeHikeId).toBeNull()
  })

  it('refuses a pointer at a hike this device does not have', () => {
    // setActiveHike's rule from the other direction: the app must not enter
    // a long hike it cannot show. The next sync brings the hike.
    expect(applyActiveHike(EMPTY_STORE, { hike_id: 'hike-1' }).activeHikeId).toBeNull()
  })

  it('lands when the hike arrives in the same exchange', () => {
    const merged = mergeServerHikes(EMPTY_STORE, [hikeRow()])
    expect(applyActiveHike(merged, { hike_id: 'hike-1' }).activeHikeId).toBe('hike-1')
  })
})

describe('the long-hike stamps carried forward', () => {
  const state: TripSyncState = {
    dirty: [],
    deleted: [],
    seen: {},
    since: null,
    hikeDirty: false,
    hikeSeen: null,
    hikesDirty: [],
    hikesDeleted: ['old'],
    hikesSeen: { 'hike-1': EARLIER, old: EARLIER, untouched: EARLIER },
    activeHikeDirty: false,
    activeHikeSeen: null,
  }

  it('takes the server’s new stamp, keeps what it knew, and drops what is gone', () => {
    const after = hikeStampsAfter(state, [hikeRow()])

    expect(after['hike-1']).toBe(NOW)
    expect(after.untouched).toBe(EARLIER)
    expect(after.old).toBeUndefined()
  })
})
