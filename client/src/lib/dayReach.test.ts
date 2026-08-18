// Tests for the hiker's own reach (#791).
//
// The load-bearing ones are the REFUSALS: nothing is offered until there is
// enough log to say it, and a recorded stretch never becomes a "day". Both
// are the same rule the rest of the planner runs on - omit rather than
// guess - applied where guessing would be easiest and least visible.

import { describe, expect, it } from 'vitest'

import { dayReach, middleHalf, reachOver, tripReach, MIN_REACH_DAYS } from './dayReach'
import { recordedPlan } from './hikes'
import { buildPlan, type HikePlan } from './plan'
import type { Trip } from './trips'

/** A trip of `days` walked days, each `perDay` miles. */
function walked(id: string, days: number, perDay: number): Trip {
  const stops = Array.from({ length: days + 1 }, (_, index) => ({
    mile: index * perDay,
    resupply: false,
  }))
  const plan: HikePlan = buildPlan(stops, { miles: perDay })
  plan.days.forEach((day) => (day.walked = true))
  return { id, name: id, plan }
}

describe('middleHalf', () => {
  it('takes the middle half rather than the extremes', () => {
    // One 26-mile push and one 4-mile afternoon must not widen the range
    // until it says nothing.
    expect(middleHalf([4, 12, 13, 14, 15, 26])).toEqual({ low: 12.25, high: 14.75 })
  })

  it('interpolates rather than jumping between samples', () => {
    expect(middleHalf([10, 20])).toEqual({ low: 12.5, high: 17.5 })
  })
})

describe('dayReach', () => {
  it('says nothing at all until there is enough log to say it', () => {
    // #791's requirement, and not a soft one: on day one there is no pace
    // of theirs to reckon with, and borrowing Naismith's estimate and
    // calling it "yours" is the failure this refusal prevents.
    expect(dayReach([])).toBeNull()
    expect(dayReach([walked('a', MIN_REACH_DAYS - 1, 12)])).toBeNull()
    expect(dayReach([walked('a', MIN_REACH_DAYS, 12)])).not.toBeNull()
  })

  it('reads the miles a day of this hiker’s walking has covered', () => {
    const reach = dayReach([walked('a', 3, 10), walked('b', 3, 20)])

    expect(reach?.samples).toBe(6)
    expect(reach?.lowMi).toBe(10)
    expect(reach?.highMi).toBe(20)
  })

  it('counts no day nobody walked', () => {
    // A trip on the calendar says nothing about how far this hiker walks.
    const planned = walked('p', 6, 14)
    planned.plan.days.forEach((day) => (day.walked = false))

    expect(dayReach([planned])).toBeNull()
  })

  it('never lets a remembered stretch become a 470-mile day', () => {
    // #789: a recorded stretch's boundaries are what somebody could recall
    // years later, not days anybody walked as days.
    const recorded: Trip = {
      id: 'r',
      name: 'From memory',
      recorded: true,
      plan: recordedPlan([
        { mile: 0, resupply: false },
        { mile: 470.8, resupply: false },
      ]),
    }
    const reach = dayReach([recorded, walked('a', 5, 12)])

    expect(reach?.samples).toBe(5)
    expect(reach?.highMi).toBe(12)
  })
})

describe('tripReach', () => {
  it('waits for a few finished trips, then reads their sizes', () => {
    expect(tripReach([walked('a', 2, 10), walked('b', 2, 10)])).toBeNull()

    const reach = tripReach([walked('a', 2, 10), walked('b', 3, 10), walked('c', 4, 10)])
    expect(reach?.samples).toBe(3)
    expect(reach?.lowMi).toBe(25) // the middle half of 20, 30, 40
    expect(reach?.highMi).toBe(35)
  })

  it('ignores a recorded stretch, which says nothing about trip size', () => {
    // Ten years of section hikes entered as one remembered stretch is not
    // one trip that size.
    const recorded: Trip = {
      id: 'r',
      name: 'From memory',
      recorded: true,
      plan: recordedPlan([
        { mile: 0, resupply: false },
        { mile: 470.8, resupply: false },
      ]),
    }
    expect(tripReach([recorded, walked('a', 2, 10), walked('b', 2, 10)])).toBeNull()
  })
})

describe('reachOver', () => {
  it('multiplies the range, and stays a range', () => {
    expect(reachOver({ lowMi: 11, highMi: 16, samples: 40 }, 5)).toEqual({
      lowMi: 55,
      highMi: 80,
    })
  })
})
