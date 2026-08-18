// Tests for the hiker's own buckets (#800).
//
// The one that matters most is MANY GROUPS PER TRIP - the maintainer's own
// case, "the entire AT" and "my section this year" being true of the same
// walk at once. That is the whole difference between a group and a hike,
// and it is one line away from being wrong in either direction.

import { describe, expect, it } from 'vitest'

import { buildPlan, type HikePlan } from './plan'
import {
  groupFigures,
  groupTrips,
  groupsOfTrip,
  validateTripGroup,
  type TripGroup,
} from './tripGroups'
import {
  addGroup,
  addToGroup,
  EMPTY_STORE,
  removeFromGroup,
  removeGroup,
  removeTrip,
  renameGroup,
  type Trip,
  type TripStore,
} from './trips'

function trip(id: string, from: number, to: number, date?: string): Trip {
  const plan: HikePlan = buildPlan(
    [
      { mile: from, resupply: false },
      { mile: to, resupply: false },
    ],
    { miles: 15 },
    date,
  )
  plan.days[0].walked = true
  return { id, name: id, plan }
}

function storeOf(...trips: Trip[]): TripStore {
  return { ...EMPTY_STORE, trips, openId: trips[0]?.id ?? null }
}

describe('a trip in several groups at once', () => {
  it('joins a group without leaving the others', () => {
    let store = storeOf(trip('a', 0, 10))
    store = addGroup(store, 'Every Sunday')
    store = addGroup(store, 'With Dad')
    const [sunday, dad] = store.groups

    store = addToGroup(store, sunday.id, 'a')
    store = addToGroup(store, dad.id, 'a')

    expect(groupsOfTrip(store.groups, 'a').map((group) => group.name)).toEqual([
      'Every Sunday',
      'With Dad',
    ])
  })

  it('takes a trip out of one group only', () => {
    let store = storeOf(trip('a', 0, 10))
    store = addGroup(store, 'One')
    store = addGroup(store, 'Two')
    store = addToGroup(store, store.groups[0].id, 'a')
    store = addToGroup(store, store.groups[1].id, 'a')

    store = removeFromGroup(store, store.groups[0].id, 'a')
    expect(groupsOfTrip(store.groups, 'a').map((group) => group.name)).toEqual(['Two'])
  })

  it('refuses to add a trip that does not exist, and never adds one twice', () => {
    let store = addGroup(storeOf(trip('a', 0, 10)), 'One')
    const id = store.groups[0].id

    store = addToGroup(store, id, 'ghost')
    expect(store.groups[0].tripIds).toEqual([])

    store = addToGroup(store, id, 'a')
    store = addToGroup(store, id, 'a')
    expect(store.groups[0].tripIds).toEqual(['a'])
  })
})

describe('the edits', () => {
  it('starts a group empty rather than full', () => {
    // "Every Sunday" must not mean "everything" until it is emptied.
    const store = addGroup(storeOf(trip('a', 0, 10), trip('b', 10, 20)), 'Every Sunday')
    expect(store.groups[0].tripIds).toEqual([])
  })

  it('deletes a group without deleting a single trip', () => {
    let store = addGroup(storeOf(trip('a', 0, 10)), 'One')
    store = addToGroup(store, store.groups[0].id, 'a')

    store = removeGroup(store, store.groups[0].id)
    expect(store.groups).toHaveLength(0)
    expect(store.trips).toHaveLength(1)
  })

  it('refuses an empty name rather than storing one', () => {
    let store = addGroup(storeOf(trip('a', 0, 10)), 'One')
    store = renameGroup(store, store.groups[0].id, '   ')
    expect(store.groups[0].name).toBe('One')
  })

  it('drops a deleted trip out of every group that named it', () => {
    let store = addGroup(storeOf(trip('a', 0, 10), trip('b', 10, 20)), 'One')
    store = addGroup(store, 'Two')
    store = addToGroup(store, store.groups[0].id, 'a')
    store = addToGroup(store, store.groups[1].id, 'a')

    store = removeTrip(store, 'a')
    expect(store.groups.every((group) => group.tripIds.length === 0)).toBe(true)
  })
})

describe('validateTripGroup', () => {
  it('accepts a group and refuses what cannot be one', () => {
    expect(validateTripGroup({ id: 'g', name: 'One', tripIds: ['a'] })).toEqual({
      id: 'g',
      name: 'One',
      tripIds: ['a'],
    })
    expect(validateTripGroup({ id: '', name: 'One', tripIds: [] })).toBeNull()
    expect(validateTripGroup({ id: 'g', name: 'One' })).toBeNull()
    expect(validateTripGroup(null)).toBeNull()
  })
})

describe('groupFigures', () => {
  const group: TripGroup = { id: 'g', name: 'Every Sunday', tripIds: ['a', 'b'] }

  it('counts trips, days and the ground - never a fraction of anything', () => {
    const figures = groupFigures(group, [
      trip('a', 0, 10, '2026-02-01'),
      trip('b', 20, 35, '2026-02-08'),
    ])

    expect(figures.tripCount).toBe(2)
    expect(figures.walkedMi).toBe(25)
    expect(figures.daysWalked).toBe(2)
    expect(figures.from).toBe('2026-02-01')
    expect(figures.to).toBe('2026-02-08')
  })

  it('counts a re-walked mile once, the way every other roll-up does', () => {
    const figures = groupFigures(group, [trip('a', 0, 10), trip('b', 5, 15)])
    expect(figures.walkedMi).toBe(15) // not 20
  })

  it('says nothing about dates when nothing carries one', () => {
    const figures = groupFigures(group, [trip('a', 0, 10), trip('b', 20, 30)])
    expect(figures.from).toBeNull()
    expect(figures.to).toBeNull()
  })
})

describe('groupTrips', () => {
  it('sorts by date, with the undated last', () => {
    const group: TripGroup = { id: 'g', name: 'g', tripIds: ['a', 'b', 'c'] }
    const sorted = groupTrips(group, [
      trip('a', 0, 10),
      trip('b', 10, 20, '2026-02-08'),
      trip('c', 20, 30, '2026-02-01'),
    ])
    expect(sorted.map((t) => t.id)).toEqual(['c', 'b', 'a'])
  })
})
