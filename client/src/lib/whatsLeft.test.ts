// Tests for what is left, and the orderings offered over it (#791).
//
// Two things are held here on purpose. THE REMAINDER: a sliver the cards
// drop is still counted and still reported, so the screen can say so rather
// than quietly calling a hike finished. And THE SORTS AS PEERS: every
// ordering is available, none is "next", and one that cannot be computed
// honestly is not silently replaced by another.

import { describe, expect, it } from 'vitest'

import type { Hike } from './hikes'
import { buildPlan, type HikePlan } from './plan'
import type { StoredPoi } from './trailData'
import type { Trip } from './trips'
import { sortGaps, whatsLeft, MIN_GAP_MI, type Gap } from './whatsLeft'

const POIS: readonly StoredPoi[] = []

function trip(id: string, from: number, to: number): Trip {
  const plan: HikePlan = buildPlan(
    [
      { mile: from, name: `Stop ${from}`, resupply: false },
      { mile: to, name: `Stop ${to}`, resupply: false },
    ],
    { miles: 15 },
  )
  plan.days[0].walked = true
  return { id, name: id, plan }
}

const HIKE: Hike = {
  id: 'h1',
  name: 'Virginia',
  type: 'section',
  start: { name: 'Damascus', mile: 0 },
  end: { name: 'Rockfish Gap', mile: 100 },
  tripIds: ['a', 'b'],
}

describe('whatsLeft', () => {
  it('gives every gap both of its ends, and neither is "the start"', () => {
    const { gaps } = whatsLeft(HIKE, [trip('a', 0, 30)], POIS)

    expect(gaps).toHaveLength(1)
    expect(gaps[0].low).toEqual({ name: 'Stop 30', mile: 30 })
    expect(gaps[0].high).toEqual({ name: 'Rockfish Gap', mile: 100 })
    expect(gaps[0].lengthMi).toBe(70)
  })

  it('counts the slivers it does not show, rather than dropping them', () => {
    // Two trips that meet a tenth of a mile apart leave something nobody
    // skipped. It gets no card - and it is still counted and still said.
    const { gaps, slivers, totalMi } = whatsLeft(
      HIKE,
      [trip('a', 0, 49.9), trip('b', 50, 100)],
      POIS,
    )

    expect(gaps).toHaveLength(0)
    expect(slivers.count).toBe(1)
    expect(slivers.miles).toBeCloseTo(0.1)
    // The whole is the sum of both halves, so the two cannot disagree.
    expect(totalMi).toBeCloseTo(0.1)
    expect(slivers.miles).toBeLessThan(MIN_GAP_MI)
  })

  it('is the whole hike when nothing has been walked', () => {
    const { gaps, totalMi } = whatsLeft({ ...HIKE, tripIds: [] }, [], POIS)

    expect(gaps).toHaveLength(1)
    expect(totalMi).toBe(100)
  })
})

describe('sortGaps', () => {
  const gaps: Gap[] = [
    {
      id: 'far',
      span: { from: 200, to: 260 },
      low: { mile: 200 },
      high: { mile: 260 },
      lengthMi: 60,
    },
    {
      id: 'near',
      span: { from: 10, to: 200 },
      low: { mile: 10 },
      high: { mile: 200 },
      lengthMi: 190,
    },
    {
      id: 'short',
      span: { from: 300, to: 320 },
      low: { mile: 300 },
      high: { mile: 320 },
      lengthMi: 20,
    },
  ]

  it('orders by trail order when that is what was asked for', () => {
    expect(
      sortGaps(gaps, 'trail', { gpsMile: null, reachMi: null }).map((gap) => gap.id),
    ).toEqual(['near', 'far', 'short'])
  })

  it('orders by how far the hiker is from each piece', () => {
    // Standing at mile 150, inside the long one: that is nearest of all.
    expect(
      sortGaps(gaps, 'near', { gpsMile: 150, reachMi: null }).map((gap) => gap.id),
    ).toEqual(['near', 'far', 'short'])

    expect(
      sortGaps(gaps, 'near', { gpsMile: 310, reachMi: null }).map((gap) => gap.id),
    ).toEqual(['short', 'far', 'near'])
  })

  it('puts what the days could finish first, then the shortest shortfall', () => {
    expect(
      sortGaps(gaps, 'fits', { gpsMile: null, reachMi: 70 }).map((gap) => gap.id),
    ).toEqual(['short', 'far', 'near'])
  })

  it('falls back to trail order rather than pretending to know', () => {
    // No fix, no log: the sort is not offered by the screen, and asking for
    // it anyway gets an ordering that claims nothing rather than one that
    // claims something false.
    expect(
      sortGaps(gaps, 'near', { gpsMile: null, reachMi: null }).map((gap) => gap.id),
    ).toEqual(['near', 'far', 'short'])
    expect(
      sortGaps(gaps, 'fits', { gpsMile: null, reachMi: null }).map((gap) => gap.id),
    ).toEqual(['near', 'far', 'short'])
  })

  it('does not mutate what it was given', () => {
    const before = gaps.map((gap) => gap.id)
    sortGaps(gaps, 'fits', { gpsMile: null, reachMi: 70 })
    expect(gaps.map((gap) => gap.id)).toEqual(before)
  })
})
