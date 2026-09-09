// Tests for trips.ts (#787) - keeping more than one plan.
//
// The load-bearing ones are the migration and the partial-refusal rule:
// between them they decide whether a hiker who upgrades still has their
// plans, which is the entire point of this issue.

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
import { TRIPS_SYNC_KEY } from './tripSyncState'
import { PLAN_KEY, buildPlan, type HikePlan } from './plan'
import {
  EMPTY_STORE,
  TRIPS_KEY,
  addHike,
  addTrip,
  clearTrips,
  finishHike,
  loadTrips,
  openTrip,
  openTripOf,
  pauseHike,
  removeHike,
  removeTrip,
  renameTrip,
  resumeHike,
  saveTrips,
  setActiveHike,
  setHikePoints,
  tripName,
  turnHikeAround,
  updateTrip,
  validateTripStore,
  type TripStore,
} from './trips'
import type { Hike } from './hikes'

const store = (idb as unknown as { __store: Map<string, unknown> }).__store

function plan(from = 470.8, to = 503.3): HikePlan {
  return buildPlan(
    [
      { mile: from, name: 'Damascus', resupply: false },
      { mile: (from + to) / 2, name: 'Lost Mountain Shelter', resupply: false },
      { mile: to, name: 'Atkins', resupply: false },
    ],
    { walkingHours: 7 },
  )
}

/** The same route with nothing named - the dropped-point case, whose trip
 *  name has to come from mile markers. */
function bare(from: number, to: number): HikePlan {
  return buildPlan(
    [
      { mile: from, resupply: false },
      { mile: to, resupply: false },
    ],
    { miles: 15 },
  )
}

beforeEach(() => {
  store.clear()
})

afterEach(() => {
  vi.clearAllMocks()
})

describe('tripName', () => {
  it('names a trip from its own ends', () => {
    expect(tripName(plan())).toBe('Damascus → Atkins')
  })

  it('falls back to mile markers for an unnamed end - never a blank', () => {
    expect(tripName(bare(470.8, 486.2))).toBe('mi 470.8 → mi 486.2')
  })
})

describe('validateTripStore', () => {
  it('refuses a value that cannot describe a store', () => {
    expect(validateTripStore(null)).toBeNull()
    expect(validateTripStore({ trips: 'nope', openId: null })).toBeNull()
    expect(validateTripStore({ trips: [], openId: 7 })).toBeNull()
    // A bare plan is not a store. This is exactly what a phone holding the
    // single-plan key would hand over, and reading it as an empty store is
    // the silent data loss loadTrips' migration exists to prevent.
    expect(validateTripStore(plan())).toBeNull()
  })

  it('drops one unreadable trip rather than losing every trip', () => {
    const good = { id: 'a', name: 'Kept', plan: plan() }
    const bad = { id: 'b', name: 'Broken', plan: { stops: [], days: [{}] } }
    const validated = validateTripStore({ trips: [good, bad], openId: 'b' })

    expect(validated?.trips.map((trip) => trip.id)).toEqual(['a'])
    // The pointer named the trip that did not survive, so it falls back to
    // one that did - the Plan tab must not open on a pointer to nothing.
    expect(validated?.openId).toBe('a')
  })

  it('keeps a pointer that still names a live trip', () => {
    const validated = validateTripStore({
      trips: [
        { id: 'a', name: 'One', plan: plan() },
        { id: 'b', name: 'Two', plan: plan() },
      ],
      openId: 'b',
    })
    expect(validated?.openId).toBe('b')
  })
})

describe('the migration off the single-plan key', () => {
  it('turns the plan already on the phone into a trip, named from its ends', async () => {
    store.set(PLAN_KEY, plan())

    const loaded = await loadTrips()

    expect(loaded.trips).toHaveLength(1)
    expect(loaded.trips[0].name).toBe('Damascus → Atkins')
    expect(loaded.openId).toBe(loaded.trips[0].id)
    expect(loaded.trips[0].plan.stops).toHaveLength(3)
  })

  it('writes the new document, so the old key is never read again', async () => {
    store.set(PLAN_KEY, plan())
    const first = await loadTrips()

    // A second plan arrives and is kept; the legacy key still holds the old
    // one, and must not resurrect it or overwrite what came after.
    await saveTrips(addTrip(first, bare(600, 620)))
    const second = await loadTrips()

    expect(second.trips).toHaveLength(2)
    expect(second.trips[1].name).toBe('mi 600.0 → mi 620.0')
  })

  it('leaves the legacy key in place rather than destroying the only copy', async () => {
    store.set(PLAN_KEY, plan())
    await loadTrips()

    expect(store.get(PLAN_KEY)).toBeDefined()
  })

  it('is an empty store when there is nothing to migrate', async () => {
    expect(await loadTrips()).toEqual(EMPTY_STORE)
  })

  it('is an empty store when the legacy plan is itself unreadable', async () => {
    store.set(PLAN_KEY, { stops: [], days: [{ id: 'x' }] })
    expect(await loadTrips()).toEqual(EMPTY_STORE)
  })
})

describe('the edits', () => {
  const base: TripStore = {
    trips: [],
    openId: null,
    hikes: [],
    groups: [],
    activeHikeId: null,
  }

  it('keeps a plan and opens it', () => {
    const one = addTrip(base, plan())
    expect(one.trips).toHaveLength(1)
    expect(one.openId).toBe(one.trips[0].id)

    const two = addTrip(one, plan(600, 620))
    expect(two.trips).toHaveLength(2)
    // The newly kept trip is the one you are looking at.
    expect(two.openId).toBe(two.trips[1].id)
    // And the first is untouched - these return new stores.
    expect(one.trips).toHaveLength(1)
  })

  it('takes a name when given one, and writes one when not', () => {
    expect(addTrip(base, plan(), 'Grayson week').trips[0].name).toBe('Grayson week')
    expect(addTrip(base, plan()).trips[0].name).toBe('Damascus → Atkins')
  })

  it('writes a plan back to the trip it came from', () => {
    const one = addTrip(base, plan())
    const id = one.trips[0].id
    const edited = updateTrip(one, id, plan(600, 620))

    expect(edited.trips[0].plan.stops[0].mile).toBe(600)
    expect(one.trips[0].plan.stops[0].mile).toBe(470.8)
  })

  it('will not resurrect a trip that is gone', () => {
    const one = addTrip(base, plan())
    expect(updateTrip(one, 'not-a-trip', plan(600, 620))).toBe(one)
    expect(openTrip(one, 'not-a-trip')).toBe(one)
    expect(removeTrip(one, 'not-a-trip')).toBe(one)
  })

  it('renames, and refuses to store a blank', () => {
    const one = addTrip(base, plan())
    const id = one.trips[0].id

    expect(renameTrip(one, id, '  Spring section  ').trips[0].name).toBe('Spring section')
    // Cleared to nothing, it comes back as its ends rather than as a blank row.
    expect(renameTrip(one, id, '   ').trips[0].name).toBe('Damascus → Atkins')
  })

  it('opens what is left when the open trip is removed', () => {
    const two = addTrip(addTrip(base, plan()), plan(600, 620))
    const openId = two.openId as string

    const after = removeTrip(two, openId)
    expect(after.trips).toHaveLength(1)
    expect(after.openId).toBe(after.trips[0].id)

    // And the last one leaves nothing open, which every screen handles - it
    // is where every hiker starts.
    const empty = removeTrip(after, after.openId as string)
    expect(empty.trips).toHaveLength(0)
    expect(empty.openId).toBeNull()
  })

  it('reads back the open trip, or null', () => {
    const one = addTrip(base, plan())
    expect(openTripOf(one)?.name).toBe('Damascus → Atkins')
    expect(openTripOf(base)).toBeNull()
    expect(
      openTripOf({
        trips: one.trips,
        openId: 'gone',
        hikes: [],
        groups: [],
        activeHikeId: null,
      }),
    ).toBeNull()
  })
})

describe('what a save may record as a delete', () => {
  it('never tombstones a trip this build simply could not read (#1040)', async () => {
    // loadTrips drops a plan a newer build wrote - deliberate, and the right
    // call. The save then diffed the store it wrote against the RAW stored
    // document, so the validator's refusal read as the hiker's own delete
    // and travelled as one, taking a plan off the account and every other
    // device. An older phone destroyed what a newer one had made.
    const future = {
      id: 'trip-from-a-newer-build',
      name: 'Someone else’s section',
      // A target shape this build has no reader for.
      plan: { target: { lightYears: 3 }, stops: [], days: [] },
    }
    await idb.set(TRIPS_KEY, {
      trips: [future],
      openId: null,
      hikes: [],
      groups: [],
    })

    // Any ordinary save by a hiker who never touched it.
    await saveTrips(addTrip(await loadTrips(), plan(), 'Mine'))

    const ledger = store.get(TRIPS_SYNC_KEY) as { deleted?: string[] } | undefined
    expect(ledger?.deleted ?? []).toEqual([])
  })
})

describe('clearTrips', () => {
  it('forgets the trips and nothing else', async () => {
    store.set(PLAN_KEY, plan())
    await saveTrips(addTrip(EMPTY_STORE, plan()))

    await clearTrips()

    expect(store.get(TRIPS_KEY)).toBeUndefined()
    expect(store.get(PLAN_KEY)).toBeDefined()
  })
})

// ---------------------------------------------------------------------------
// The long hike the app is IN, and how one moves through its life (#1317).

describe('the active hike', () => {
  const hike: Hike = {
    id: 'h1',
    name: 'Springer → Katahdin',
    type: 'thru',
    trailId: 'AT',
    points: [
      { name: 'Springer', mile: 0 },
      { name: 'Katahdin', mile: 2197.4 },
    ],
    status: 'walking',
    tripIds: [],
  }

  const withHike = addHike(EMPTY_STORE, hike)

  it('enters a hike, and leaves the state without abandoning it', () => {
    const inIt = setActiveHike(withHike, 'h1')
    expect(inIt.activeHikeId).toBe('h1')

    // Tapping Day hike keeps the hike - it is not abandoned, just not
    // leading - so only an explicit null clears the pointer.
    const out = setActiveHike(inIt, null)
    expect(out.activeHikeId).toBeNull()
    expect(out.hikes).toHaveLength(1)
  })

  it('refuses a pointer it cannot honour rather than writing and repairing it', () => {
    expect(setActiveHike(withHike, 'nobody').activeHikeId).toBeNull()

    // Fewer than two points is unusable as an active hike and is still a
    // hike: the store keeps it, and only the pointer is refused.
    const short = addHike(EMPTY_STORE, { ...hike, id: 'h2', points: [{ mile: 0 }] })
    expect(setActiveHike(short, 'h2').activeHikeId).toBeNull()
    expect(short.hikes).toHaveLength(1)
  })

  it('drops a pointer at a hike that did not survive the read', () => {
    const store = validateTripStore({
      trips: [],
      openId: null,
      hikes: [],
      groups: [],
      activeHikeId: 'h1',
    })
    expect(store?.activeHikeId).toBeNull()
  })

  it('does not enter a long hike on the hiker’s behalf', () => {
    // openId falls back to the first trip so the Plan tab shows something
    // recognisable. This must NOT: being in a long hike is a state the
    // hiker entered deliberately.
    const store = validateTripStore({ ...withHike, activeHikeId: 'gone' })
    expect(store?.hikes).toHaveLength(1)
    expect(store?.activeHikeId).toBeNull()
  })

  it('lets go of the pointer when the hike is forgotten, and keeps the sections', () => {
    const one = addTrip(EMPTY_STORE, plan())
    const grouped = addHike(one, { ...hike, tripIds: one.trips.map((t) => t.id) })

    const forgotten = removeHike(setActiveHike(grouped, 'h1'), 'h1')
    expect(forgotten.activeHikeId).toBeNull()
    expect(forgotten.hikes).toEqual([])
    // The whole reason forgetting is safe.
    expect(forgotten.trips).toHaveLength(1)
  })
})

describe('stepping away and coming back', () => {
  const hike: Hike = {
    id: 'h1',
    name: 'Springer → Katahdin',
    type: 'thru',
    trailId: 'AT',
    points: [
      { name: 'Springer', mile: 0 },
      { name: 'Katahdin', mile: 2197.4 },
    ],
    status: 'walking',
    tripIds: [],
  }
  const withHike = addHike(EMPTY_STORE, hike)

  it('keeps the mile it stopped at, and deletes nothing', () => {
    const paused = pauseHike(withHike, 'h1', 1407.2, '2026-08-28')

    expect(paused.hikes[0].status).toBe('paused')
    expect(paused.hikes[0].pausedAtMile).toBe(1407.2)
    expect(paused.hikes[0].pausedOn).toBe('2026-08-28')
    expect(paused.hikes[0].points).toEqual(hike.points)
  })

  it('clears the pause when the hiker comes back', () => {
    // A stale pausedAtMile on a walking hike is a fact waiting to be
    // printed by mistake. What was actually walked lives in the sections.
    const back = resumeHike(pauseHike(withHike, 'h1', 1407.2, '2026-08-28'), 'h1')

    expect(back.hikes[0].status).toBe('walking')
    expect(back.hikes[0].pausedAtMile).toBeUndefined()
    expect(back.hikes[0].pausedOn).toBeUndefined()
  })

  it('turns around by appending, so the walked legs keep their directions', () => {
    // Swapping the ends would silently reverse every leg already walked:
    // 300 miles north would afterwards read as 300 miles south.
    const turned = turnHikeAround(withHike, 'h1', 700, 'Damascus')

    expect(turned.hikes[0].points.map((point) => point.mile)).toEqual([0, 2197.4, 700, 0])
    expect(turned.hikes[0].points[2].name).toBe('Damascus')
  })

  it('closes a hike and keeps every section in it', () => {
    const one = addTrip(EMPTY_STORE, plan())
    const grouped = addHike(one, { ...hike, tripIds: one.trips.map((t) => t.id) })
    const done = finishHike(grouped, 'h1', '2026-08-12')

    expect(done.hikes[0].status).toBe('finished')
    expect(done.hikes[0].finishedOn).toBe('2026-08-12')
    expect(done.hikes[0].tripIds).toHaveLength(1)
    expect(done.trips).toHaveLength(1)
  })

  it('edits the route without touching the walking', () => {
    const one = addTrip(EMPTY_STORE, plan())
    const grouped = addHike(one, { ...hike, tripIds: one.trips.map((t) => t.id) })
    const rerouted = setHikePoints(grouped, 'h1', [
      { mile: 0 },
      { mile: 1023.4 },
      { mile: 2197.4 },
    ])

    expect(rerouted.hikes[0].points).toHaveLength(3)
    expect(rerouted.hikes[0].tripIds).toHaveLength(1)
    expect(rerouted.trips).toHaveLength(1)
  })

  it('changes nothing for a hike it does not hold', () => {
    expect(pauseHike(withHike, 'nobody', 10, '2026-08-28')).toEqual(withHike)
    expect(finishHike(withHike, 'nobody', '2026-08-28')).toEqual(withHike)
    expect(turnHikeAround(withHike, 'nobody', 10)).toEqual(withHike)
  })
})
