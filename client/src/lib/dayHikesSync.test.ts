import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { get, set, del } from 'idb-keyval'
import { syncDayHikes } from './api'
import {
  mergeServerDayHikes,
  stampsAfter,
  syncDayHikesWithAccount,
  uploadsFor,
} from './dayHikesSync'
import { DAY_HIKES_KEY, type DayHike, type DayHikeStore } from './dayHikes'
import { DAY_HIKES_SYNC_KEY, dayHikeSyncState } from './dayHikeSyncState'
import { TRIPS_SYNC_KEY } from './tripSyncState'

// Day hikes following the account (#976), from this device's side.
//
// The conflict rule is the server's, exactly as it is for trips. What is
// tested here is everything a device can get wrong on its own, and the two
// worst are the same two tripsSync.test.ts names - **adopting what the
// account sent and then pushing it straight back**, and **inventing a
// deletion** - plus the one a review found in this feature specifically:
// day-hike ids leaking into the TRIPS ledger, where they upload as
// tombstones no synced_trips row matches and the sync looks like it works
// while nothing travels.

vi.mock('idb-keyval', () => ({
  get: vi.fn(),
  set: vi.fn(),
  del: vi.fn(),
  update: vi.fn(),
}))
vi.mock('./api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./api')>()),
  syncDayHikes: vi.fn(),
}))

const store = new Map<string, unknown>()
const NOW = '2026-08-25T12:00:00Z'
const EARLIER = '2026-08-25T09:00:00Z'

function hike(id = 'hike-1', name = 'Bear Mountain loop'): DayHike {
  return {
    id,
    name,
    date: '2026-09-06',
    segments: [
      [
        { coord: [-73.988997, 41.312807], poiId: null },
        { coord: [-73.968708, 41.322614], poiId: null },
      ],
    ],
    figures: {
      miles: 3.4,
      legs: [
        { name: 'Appalachian Trail', source: 'nynjtc', blaze_color: 'white', miles: 3.4 },
      ],
    },
    looped: false,
    recorded: 'planned',
    note: '',
  }
}

function storeWith(...hikes: DayHike[]): DayHikeStore {
  return { hikes, openId: hikes[0]?.id ?? null }
}

function row(id = 'hike-1', name = 'Bear Mountain loop', over = {}) {
  return { id, document: hike(id, name), updated_at: NOW, deleted_at: null, ...over }
}

const CLEAN = { dirty: [], deleted: [], seen: {}, since: null }

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
  vi.mocked(syncDayHikes).mockReset()
  vi.mocked(syncDayHikes).mockResolvedValue({
    now: NOW,
    day_hikes: [],
    conflicts: 0,
  })
  vi.spyOn(console, 'error').mockImplementation(() => {})
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('what this device offers', () => {
  it('offers nothing when nothing changed here', () => {
    expect(uploadsFor(storeWith(hike()), CLEAN)).toEqual([])
  })

  it('offers a changed hike with the stamp it was working from', () => {
    const changed = hike()

    const uploads = uploadsFor(storeWith(changed), {
      ...CLEAN,
      dirty: ['hike-1'],
      seen: { 'hike-1': EARLIER },
    })

    expect(uploads).toEqual([
      { id: 'hike-1', document: changed, base_updated_at: EARLIER, deleted: false },
    ])
  })

  it('offers a brand-new hike with no stamp at all', () => {
    // Null is "this device believes this is new", which the server reads as
    // a claim rather than as a missing field.
    expect(
      uploadsFor(storeWith(hike()), { ...CLEAN, dirty: ['hike-1'] })[0].base_updated_at,
    ).toBe(null)
  })

  it('offers a deletion as a tombstone rather than as an omission', () => {
    const uploads = uploadsFor(storeWith(), { ...CLEAN, deleted: ['hike-1'] })

    expect(uploads).toEqual([
      { id: 'hike-1', document: null, base_updated_at: null, deleted: true },
    ])
  })

  it('sends the delete, not the edit, for a hike edited and then binned', () => {
    const uploads = uploadsFor(storeWith(), {
      ...CLEAN,
      dirty: ['hike-1'],
      deleted: ['hike-1'],
    })

    expect(uploads.map((upload) => upload.deleted)).toEqual([true])
  })

  it('never turns a dirty id with no hike behind it into a deletion', () => {
    // A half-written save can leave the ledger and the store disagreeing.
    // An upload with no document would read as a delete the hiker never
    // performed, which is the one thing this feature must not invent.
    expect(uploadsFor(storeWith(), { ...CLEAN, dirty: ['ghost'] })).toEqual([])
  })
})

describe('folding in what the account sent', () => {
  it('adds a hike this device has never seen', () => {
    const merged = mergeServerDayHikes({ hikes: [], openId: null }, [row()])

    expect(merged.hikes.map((entry) => entry.id)).toEqual(['hike-1'])
  })

  it('replaces a hike this device already has', () => {
    const merged = mergeServerDayHikes(storeWith(hike()), [
      row('hike-1', 'Renamed elsewhere'),
    ])

    expect(merged.hikes.map((entry) => entry.name)).toEqual(['Renamed elsewhere'])
  })

  it('applies a tombstone, because that is the hiker’s own delete arriving', () => {
    const merged = mergeServerDayHikes(storeWith(hike()), [
      row('hike-1', 'gone', { document: null, deleted_at: NOW }),
    ])

    expect(merged.hikes).toEqual([])
  })

  it('repairs a pointer at a hike another device deleted to null', () => {
    // This store's decided openId rule, not trips' first-item fallback:
    // nothing opens a walk the hiker did not choose.
    const merged = mergeServerDayHikes(storeWith(hike('hike-1'), hike('hike-2')), [
      row('hike-1', 'gone', { document: null, deleted_at: NOW }),
    ])

    expect(merged.hikes.map((entry) => entry.id)).toEqual(['hike-2'])
    expect(merged.openId).toBeNull()
  })

  it('drops one unreadable hike rather than the whole response', () => {
    // validateDayHikeStore refuses per hike for exactly this reason: one
    // hike written by a newer build must not cost a hiker every other one.
    const merged = mergeServerDayHikes({ hikes: [], openId: null }, [
      { id: 'bad', document: { nonsense: true }, updated_at: NOW, deleted_at: null },
      row('hike-2', 'Fine'),
    ])

    expect(merged.hikes.map((entry) => entry.id)).toEqual(['hike-2'])
  })

  it('is the same object when nothing arrived, so nothing is rewritten', () => {
    const before = storeWith(hike())

    expect(mergeServerDayHikes(before, [])).toBe(before)
  })
})

describe('the stamps carried forward', () => {
  const state = {
    dirty: [],
    deleted: ['old'],
    seen: { 'hike-1': EARLIER, old: EARLIER, untouched: EARLIER },
    since: null,
  }

  it('takes the server’s new stamp for a hike it sent', () => {
    expect(stampsAfter(state, [row()])['hike-1']).toBe(NOW)
  })

  it('keeps what it already knew about a hike the response did not mention', () => {
    expect(stampsAfter(state, [row()]).untouched).toBe(EARLIER)
  })

  it('stops carrying a stamp for a hike that is gone everywhere', () => {
    const after = stampsAfter(state, [
      row('hike-1', 'gone', { document: null, deleted_at: NOW }),
    ])

    expect(after).not.toHaveProperty('hike-1')
    expect(after).not.toHaveProperty('old')
  })
})

describe('a whole exchange', () => {
  it('adopts the account’s day hikes on a device that had none', async () => {
    vi.mocked(syncDayHikes).mockResolvedValue({
      now: NOW,
      day_hikes: [row()],
      conflicts: 0,
    })

    const adopted = await syncDayHikesWithAccount()

    expect(adopted?.hikes.map((entry) => entry.id)).toEqual(['hike-1'])
    expect(store.get(DAY_HIKES_KEY)).toMatchObject({
      hikes: [expect.objectContaining({ id: 'hike-1' })],
    })
  })

  it('does NOT push back what it just pulled', async () => {
    // The loop that would look exactly like a sync that works. Adopting has
    // to go through the path that does not mark the store dirty.
    vi.mocked(syncDayHikes).mockResolvedValue({
      now: NOW,
      day_hikes: [row()],
      conflicts: 0,
    })
    await syncDayHikesWithAccount()

    expect(await dayHikeSyncState()).toMatchObject({ dirty: [], deleted: [] })

    vi.mocked(syncDayHikes).mockClear()
    vi.mocked(syncDayHikes).mockResolvedValue({
      now: NOW,
      day_hikes: [],
      conflicts: 0,
    })
    await syncDayHikesWithAccount()

    expect(vi.mocked(syncDayHikes).mock.calls[0][0].day_hikes).toEqual([])
  })

  it('records the watermark so the next sync asks only for what moved', async () => {
    await syncDayHikesWithAccount()

    expect((await dayHikeSyncState()).since).toBe(NOW)
  })

  it('leaves the trips ledger untouched, whole exchange included', async () => {
    // The review-found failure mode, asserted end to end: a day-hike
    // exchange reads and writes ONLY its own ledger. A day-hike id that
    // reached the trips ledger would ride /trips/sync as a tombstone no
    // synced_trips row matches - a silent no-op looking like a working sync.
    const tripsLedger = {
      dirty: ['trip-1'],
      deleted: ['trip-2'],
      seen: { 'trip-1': EARLIER },
      since: EARLIER,
      hikeDirty: false,
      hikeSeen: null,
    }
    store.set(TRIPS_SYNC_KEY, tripsLedger)
    store.set(DAY_HIKES_KEY, storeWith(hike()))
    store.set(DAY_HIKES_SYNC_KEY, { ...CLEAN, dirty: ['hike-1'] })

    await syncDayHikesWithAccount()

    expect(store.get(TRIPS_SYNC_KEY)).toEqual(tripsLedger)
    // And the upload carried the day-hike id through its own exchange.
    expect(
      vi.mocked(syncDayHikes).mock.calls[0][0].day_hikes.map((upload) => upload.id),
    ).toEqual(['hike-1'])
    expect((await dayHikeSyncState()).dirty).toEqual([])
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
    vi.mocked(syncDayHikes).mockRejectedValue(failure)

    expect(await syncDayHikesWithAccount()).toBeNull()
    expect(console.error).not.toHaveBeenCalled()
  })

  it('leaves the changes queued when the exchange cannot land', async () => {
    store.set(DAY_HIKES_KEY, storeWith(hike()))
    store.set(DAY_HIKES_SYNC_KEY, { ...CLEAN, dirty: ['hike-1'] })
    const offline = new Error('Failed to fetch')
    offline.name = 'TypeError'
    vi.mocked(syncDayHikes).mockRejectedValue(offline)

    await syncDayHikesWithAccount()

    expect((await dayHikeSyncState()).dirty).toEqual(['hike-1'])
  })

  it('says a real refusal out loud, and still never rejects', async () => {
    const refused = new Error('POST failed: 500')
    refused.name = 'ApiError'
    vi.mocked(syncDayHikes).mockRejectedValue(refused)

    await expect(syncDayHikesWithAccount()).resolves.toBeNull()
    expect(console.error).toHaveBeenCalled()
  })
})
