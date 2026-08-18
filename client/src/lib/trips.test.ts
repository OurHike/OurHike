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
import { PLAN_KEY, buildPlan, type HikePlan } from './plan'
import {
  EMPTY_STORE,
  TRIPS_KEY,
  addTrip,
  clearTrips,
  loadTrips,
  openTrip,
  openTripOf,
  removeTrip,
  renameTrip,
  saveTrips,
  tripName,
  updateTrip,
  validateTripStore,
  type TripStore,
} from './trips'

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
  const base: TripStore = { trips: [], openId: null }

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
    expect(openTripOf({ trips: one.trips, openId: 'gone' })).toBeNull()
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
