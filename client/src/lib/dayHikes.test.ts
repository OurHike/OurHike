// Tests for dayHikes.ts (#976) - the persisted day-hike store.
//
// The load-bearing ones are the sanitise-versus-drop asymmetry (junk in one
// field costs that field, junk in the route costs that hike, and nothing ever
// costs the store) and the ledger separation at the bottom: a day-hike save
// that touched the trips ledger would upload tombstones no synced_trips row
// matches - a silent no-op that looks like a working sync.

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('idb-keyval', () => {
  const store = new Map<string, unknown>()
  return {
    __store: store,
    get: vi.fn(async (key: string) => store.get(key)),
    set: vi.fn(async (key: string, value: unknown) => {
      store.set(key, value)
    }),
    del: vi.fn(async (key: string) => {
      store.delete(key)
    }),
    update: vi.fn(),
  }
})

import * as idb from 'idb-keyval'
import {
  DAY_HIKES_KEY,
  EMPTY_DAY_HIKES,
  adoptDayHikes,
  clearDayHikes,
  loadDayHikes,
  saveDayHikes,
  validateDayHikeStore,
  type DayHike,
  type DayHikeStore,
} from './dayHikes'
import { DAY_HIKES_SYNC_KEY, dayHikeSyncState } from './dayHikeSyncState'
import { TRIPS_SYNC_KEY } from './tripSyncState'

const store = (idb as unknown as { __store: Map<string, unknown> }).__store

function hike(id = 'hike-1', over: Partial<DayHike> = {}): DayHike {
  return {
    id,
    name: 'Bear Mountain loop',
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
    ...over,
  }
}

function storeWith(...hikes: DayHike[]): DayHikeStore {
  return { hikes, openId: hikes[0]?.id ?? null }
}

beforeEach(() => {
  store.clear()
})

afterEach(() => {
  vi.clearAllMocks()
})

describe('validateDayHikeStore', () => {
  it('refuses a value that cannot describe a store', () => {
    expect(validateDayHikeStore(null)).toBeNull()
    expect(validateDayHikeStore(7)).toBeNull()
    expect(validateDayHikeStore({ hikes: 'nope', openId: null })).toBeNull()
    // A bare day hike is not a store - handing one over must not read as an
    // empty store with the hike silently gone.
    expect(validateDayHikeStore(hike())).toBeNull()
  })

  it('drops one unreadable hike rather than losing every hike', () => {
    const validated = validateDayHikeStore({
      hikes: [
        hike('kept'),
        { ...hike('no-id'), id: 7 },
        { ...hike('no-route'), segments: 'nope' },
        { ...hike('bad-end'), segments: [[{ coord: [Number.NaN, 41.3], poiId: null }]] },
        { ...hike('bad-miles'), figures: { miles: 'far', legs: [] } },
      ],
      openId: 'kept',
    })

    expect(validated?.hikes.map((entry) => entry.id)).toEqual(['kept'])
  })

  it('drops a hike whose route lost an end, never silently reroutes it', () => {
    // The cached figures describe the walk as tapped. A hike with a junk end
    // quietly removed would be a different walk still wearing the old miles.
    const validated = validateDayHikeStore({
      hikes: [
        {
          ...hike('torn'),
          segments: [[{ coord: [-73.98, 41.31], poiId: null }, { coord: 'gone' }]],
        },
      ],
      openId: null,
    })

    expect(validated?.hikes).toEqual([])
  })

  it('drops a hike with no segments at all - a name is not a walk', () => {
    expect(
      validateDayHikeStore({ hikes: [{ ...hike('none'), segments: [] }], openId: null })
        ?.hikes,
    ).toEqual([])
  })

  it('sanitises junk in the fields that carry no invariant', () => {
    const validated = validateDayHikeStore({
      hikes: [
        {
          ...hike('messy'),
          name: 7,
          date: 'last Sunday',
          looped: 'yes',
          recorded: 'jogged',
        },
      ],
      openId: 'messy',
    })
    const cleaned = validated?.hikes[0]

    expect(cleaned?.name).toBe('')
    expect(cleaned?.date).toBeNull()
    expect(cleaned?.looped).toBe(false)
    // 'planned' is the weaker claim - junk provenance must not invent a walk.
    expect(cleaned?.recorded).toBe('planned')
    // And the hike itself survived; only the junk fields paid.
    expect(validated?.openId).toBe('messy')
  })

  it('keeps a walked, looped hike as exactly that', () => {
    const validated = validateDayHikeStore({
      hikes: [hike('walked', { looped: true, recorded: 'walked' })],
      openId: null,
    })

    expect(validated?.hikes[0].looped).toBe(true)
    expect(validated?.hikes[0].recorded).toBe('walked')
  })

  it('sanitises a junk poiId to null - unjoined, not broken', () => {
    const validated = validateDayHikeStore({
      hikes: [
        {
          ...hike('poi'),
          segments: [
            [
              { coord: [-73.98, 41.31], poiId: 9 },
              { coord: [-73.96, 41.32], poiId: 'atc_shelter_0421' },
            ],
          ],
        },
      ],
      openId: null,
    })
    const ends = validated?.hikes[0].segments[0]

    expect(ends?.[0].poiId).toBeNull()
    expect(ends?.[1].poiId).toBe('atc_shelter_0421')
  })

  it('never lets an edgeIndex smuggled onto an end survive a load', () => {
    // The CRITICAL rule in dayHikes.ts: an edgeIndex is positional into an
    // array the pipeline compacts in input order, so a republished graph
    // silently shifts it onto a different trail. Ends are rebuilt field by
    // field so nothing downstream can come to depend on one being stored.
    const validated = validateDayHikeStore({
      hikes: [
        {
          ...hike('indexed'),
          segments: [
            [
              { coord: [-73.98, 41.31], poiId: null, edgeIndex: 512 },
              { coord: [-73.96, 41.32], poiId: null, edgeIndex: 513 },
            ],
          ],
        },
      ],
      openId: null,
    })

    expect(validated?.hikes[0].segments[0][0]).toEqual({
      coord: [-73.98, 41.31],
      poiId: null,
    })
    expect(validated?.hikes[0].segments[0][0]).not.toHaveProperty('edgeIndex')
  })

  it('keeps two segments as two segments - a gap is part of the walk (#935)', () => {
    const gapped = hike('gapped', {
      segments: [
        [
          { coord: [-73.98, 41.31], poiId: null },
          { coord: [-73.97, 41.32], poiId: null },
        ],
        [
          { coord: [-73.95, 41.33], poiId: null },
          { coord: [-73.94, 41.34], poiId: null },
        ],
      ],
    })

    const validated = validateDayHikeStore({ hikes: [gapped], openId: null })

    expect(validated?.hikes[0].segments).toHaveLength(2)
    expect(validated?.hikes[0].segments).toEqual(gapped.segments)
  })

  it('drops a junk figures leg, and only that leg', () => {
    const validated = validateDayHikeStore({
      hikes: [
        {
          ...hike('legs'),
          figures: {
            miles: 5.1,
            legs: [
              {
                name: 'Appalachian Trail',
                source: 'nynjtc',
                blaze_color: 'white',
                miles: 3,
              },
              'nonsense',
              { name: 'Long Path', source: null, blaze_color: null, miles: 'far' },
              { name: 42, source: null, blaze_color: null, miles: 2.1 },
            ],
          },
        },
      ],
      openId: null,
    })
    const figures = validated?.hikes[0].figures

    expect(figures?.miles).toBe(5.1)
    expect(figures?.legs).toEqual([
      { name: 'Appalachian Trail', source: 'nynjtc', blaze_color: 'white', miles: 3 },
      // A junk name is unknown, not broken - the row's miles still count.
      { name: null, source: null, blaze_color: null, miles: 2.1 },
    ])
  })

  it('reads junk legs as no breakdown rather than dropping the hike', () => {
    const validated = validateDayHikeStore({
      hikes: [{ ...hike('bare'), figures: { miles: 3.4, legs: 'nope' } }],
      openId: null,
    })

    expect(validated?.hikes[0].figures).toEqual({ miles: 3.4, legs: [] })
  })

  it('repairs an openId pointing at a vanished hike to null, not to another hike', () => {
    // The decided rule for THIS store, distinct from trips' first-item
    // fallback: nothing opens a walk the hiker did not choose.
    expect(
      validateDayHikeStore({ hikes: [hike('here')], openId: 'gone' })?.openId,
    ).toBeNull()
  })

  it('keeps an openId that still names a live hike', () => {
    expect(
      validateDayHikeStore({ hikes: [hike('a'), hike('b')], openId: 'b' })?.openId,
    ).toBe('b')
  })

  it('sanitises a junk openId to null rather than refusing the store', () => {
    expect(validateDayHikeStore({ hikes: [hike('a')], openId: 7 })?.openId).toBeNull()
  })
})

describe('loading and saving', () => {
  it('is empty when nothing was ever stored', async () => {
    expect(await loadDayHikes()).toEqual(EMPTY_DAY_HIKES)
  })

  it('round-trips a store through IndexedDB', async () => {
    const saved = storeWith(hike('a'), hike('b', { recorded: 'walked' }))
    await saveDayHikes(saved)

    expect(await loadDayHikes()).toEqual(saved)
  })

  it('reads an unrecognisable stored value as empty, never as a throw', async () => {
    store.set(DAY_HIKES_KEY, 'nonsense')

    expect(await loadDayHikes()).toEqual(EMPTY_DAY_HIKES)
  })

  it('loses one junk hike from storage, never the store', async () => {
    store.set(DAY_HIKES_KEY, {
      hikes: [hike('kept'), { id: 'broken', segments: 'nope' }],
      openId: 'broken',
    })

    const loaded = await loadDayHikes()

    expect(loaded.hikes.map((entry) => entry.id)).toEqual(['kept'])
    expect(loaded.openId).toBeNull()
  })
})

describe('the ledger a save writes, and the one it must never touch', () => {
  it('stores under its own keys, pinned as the literals a phone holds', () => {
    expect(DAY_HIKES_KEY).toBe('ourhike:day-hikes')
    expect(DAY_HIKES_SYNC_KEY).toBe('ourhike:day-hikes:sync')
  })

  it('marks a saved hike dirty in the day-hike ledger', async () => {
    await saveDayHikes(storeWith(hike('a')))

    expect((await dayHikeSyncState()).dirty).toEqual(['a'])
  })

  it('records a removal as the hiker’s own delete', async () => {
    await saveDayHikes(storeWith(hike('a'), hike('b')))
    await saveDayHikes(storeWith(hike('a')))

    const state = await dayHikeSyncState()
    expect(state.deleted).toEqual(['b'])
    expect(state.dirty).toContain('a')
    expect(state.dirty).not.toContain('b')
  })

  it('never tombstones a hike this build simply could not read (#1040)', async () => {
    // The failure this pins is total and silent: loadDayHikes drops a record
    // a newer build wrote, the save diffed that against the RAW document,
    // and the difference travelled as a delete - taking somebody's walk off
    // the account and every other device. Nobody performed a delete; an
    // older phone just could not parse one.
    const future = {
      id: 'from-a-newer-build',
      name: 'Someone else’s walk',
      date: null,
      // A segment shape this build has no reader for.
      segments: [[{ waypointRef: 'atlas:7', poiId: null }]],
      figures: { miles: 9.1, legs: [] },
      looped: false,
      recorded: 'planned',
    }
    await idb.set(DAY_HIKES_KEY, { hikes: [hike('a'), future], openId: null })

    // Any ordinary save, by a hiker who never touched the unreadable one.
    await saveDayHikes(storeWith(hike('a')))

    const state = await dayHikeSyncState()
    expect(state.deleted).toEqual([])
    expect(state.deleted).not.toContain('from-a-newer-build')
  })

  it('never records a deletion off a read that came back empty', async () => {
    // The store was never written, so there is no before - and an absent
    // document must not read as "everything was deleted".
    await saveDayHikes(storeWith(hike('a')))

    expect((await dayHikeSyncState()).deleted).toEqual([])
  })

  it('NEVER writes day-hike ids into the trips ledger', async () => {
    // The review-found failure mode: a day-hike id in the trips ledger
    // uploads to /trips/sync as a tombstone no synced_trips row matches - a
    // silent no-op that looks exactly like a working sync.
    await saveDayHikes(storeWith(hike('a'), hike('b')))
    await saveDayHikes(storeWith(hike('a')))
    await clearDayHikes()

    expect(store.get(TRIPS_SYNC_KEY)).toBeUndefined()
    expect(store.get(DAY_HIKES_SYNC_KEY)).toBeDefined()
  })

  it('adopts the account’s store without marking anything dirty', async () => {
    await adoptDayHikes(storeWith(hike('from-server')))

    expect(await loadDayHikes()).toEqual(storeWith(hike('from-server')))
    expect((await dayHikeSyncState()).dirty).toEqual([])
  })
})

describe('clearDayHikes', () => {
  it('forgets the hikes and records each as deleted', async () => {
    await saveDayHikes(storeWith(hike('a'), hike('b')))

    await clearDayHikes()

    expect(store.get(DAY_HIKES_KEY)).toBeUndefined()
    expect(await loadDayHikes()).toEqual(EMPTY_DAY_HIKES)
    expect((await dayHikeSyncState()).deleted).toEqual(['a', 'b'])
  })
})
