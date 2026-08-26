// Tests for cascade.ts (#758) - the piece HIKE_PLANNING.md marks as
// carrying the most product risk, so what gets pinned here is the safety
// architecture: the past never edited, pins never re-planned through,
// resupply towns never moved, zeros never spent, and every consequence
// computed rather than promised.

import { describe, expect, it } from 'vitest'

import { absorbPlan, callItADay, cascadeChoices, nearestStop, shiftPlan } from './cascade'
import {
  buildPlan,
  insertZeroAfter,
  NEARO_MAX_MI,
  planDayViews,
  togglePinned,
  validatePlan,
  type HikePlan,
} from './plan'
import type { StoredPoi } from './trailData'

const stop = (mile: number, name: string, resupply = false) => ({
  mile,
  name,
  resupply,
})

/** Damascus → Atkins, four walking days at a 15-mile target, dated. */
function plan() {
  return buildPlan(
    [
      stop(470.8, 'Damascus'),
      stop(486.2, 'Lost Mountain Shelter'),
      stop(503.3, 'Thomas Knob Shelter'),
      stop(516.1, 'Old Orchard Shelter'),
      stop(525.7, 'Atkins', true),
    ],
    { miles: 15 },
    '2026-05-12',
  )
}

const shelter = (id: string, mile: number, name: string): StoredPoi => ({
  id,
  type: 'shelter',
  name,
  lat: 0,
  lon: 0,
  confidence: 'high',
  mile,
})

const POIS: StoredPoi[] = [
  shelter('lost', 486.2, 'Lost Mountain Shelter'),
  shelter('wise', 490.4, 'Wise Shelter'),
  shelter('a', 496, 'Shelter A'),
  shelter('thomas', 503.3, 'Thomas Knob Shelter'),
  shelter('b', 508, 'Shelter B'),
  shelter('old', 516.1, 'Old Orchard Shelter'),
  shelter('c', 520, 'Shelter C'),
]

describe('callItADay', () => {
  it('rewrites the boundary to where the day really ended, and records it', () => {
    const called = callItADay(plan(), 0, { mile: 490.4, name: 'Wise Shelter' })

    expect(called.stops[1].name).toBe('Wise Shelter')
    expect(called.days[0].walked).toBe(true)
    // Tomorrow starts where the hiker is - the boundary is one stop.
    expect(called.stops[1].mile).toBeCloseTo(490.4)
    expect(validatePlan(called)).not.toBeNull()
  })

  it('keeps the planned stop whole when the day ended exactly there', () => {
    const called = callItADay(plan(), 0, { mile: 486.2 })
    expect(called.stops[1].name).toBe('Lost Mountain Shelter')
    expect(called.days[0].walked).toBe(true)
  })

  it('only the current day can be called - days are walked in order', () => {
    const fresh = plan()
    expect(callItADay(fresh, 2, { mile: 510 })).toBe(fresh)
    const one = callItADay(fresh, 0, { mile: 486.2 })
    expect(callItADay(one, 0, { mile: 490 })).toBe(one)
  })

  it('refuses an end that would run tomorrow backwards', () => {
    // Past Thomas Knob is past the boundary AFTER the one being replaced -
    // the hiker overtook a whole planned day, which is a structural edit
    // the cascade does not attempt. Behind the start is the same refusal
    // mirrored.
    const fresh = plan()
    expect(callItADay(fresh, 0, { mile: 510 })).toBe(fresh)
    expect(callItADay(fresh, 0, { mile: 460 })).toBe(fresh)
    // Exactly AT the following boundary is the degenerate edge: allowed,
    // and tomorrow becomes a zero-length day the hiker can remove.
    const toTheEdge = callItADay(fresh, 0, { mile: 503.3 })
    expect(toTheEdge).not.toBe(fresh)
    expect(toTheEdge.stops[1].mile).toBe(503.3)
  })
})

describe('absorbPlan - the finish holds', () => {
  it('re-balances only the stretch, keeps every date, and says what changed', () => {
    // Stopped six miles short at a dropped point.
    const called = callItADay(plan(), 0, { mile: 480 })
    const absorbed = absorbPlan(called, POIS)

    expect(absorbed).not.toBeNull()
    const next = absorbed!.plan
    // Same day count, same dates - the finish did not move.
    expect(next.days).toHaveLength(4)
    expect(next.days.map((day) => day.date)).toEqual([
      '2026-05-12',
      '2026-05-13',
      '2026-05-14',
      '2026-05-15',
    ])
    // The walked record is untouched.
    expect(next.stops[0].name).toBe('Damascus')
    expect(next.stops[1].mile).toBe(480)
    expect(next.days[0].walked).toBe(true)
    // The resupply town did not move.
    expect(next.stops[4].name).toBe('Atkins')
    expect(next.stops[4].resupply).toBe(true)
    // Re-balanced between: 480 → 496 → 508 → 525.7.
    expect(next.stops.map((s) => s.mile)).toEqual([470.8, 480, 496, 508, 525.7])
    // And each re-planned day says what it used to be - a fact about the
    // plan, not a verdict. "Was" is the pre-cascade plan: tomorrow had
    // become the whole 23.3-mile stretch to Thomas Knob the moment today
    // ended six miles short of Lost Mountain.
    const was = next.days.slice(1).map((day) => day.wasDistanceMi as number)
    expect(was[0]).toBeCloseTo(23.3)
    expect(was[1]).toBeCloseTo(12.8)
    expect(was[2]).toBeCloseTo(9.6)
    expect(validatePlan(next)).not.toBeNull()
  })

  it('never re-plans through a pin - the stretch ends at its start', () => {
    const pinned = togglePinned(plan(), 2)
    const called = callItADay(pinned, 0, { mile: 480 })
    const absorbed = absorbPlan(called, POIS)

    expect(absorbed).not.toBeNull()
    const next = absorbed!.plan
    // Day 1 alone absorbed the shortfall; the pinned day and everything
    // after it kept their stops.
    expect(next.stops.map((s) => s.mile)).toEqual([470.8, 480, 503.3, 516.1, 525.7])
    expect(next.days[2].pinned).toBe(true)
    expect(next.days[2].wasDistanceMi).toBeUndefined()
  })

  it('carries a zero through re-planning without spending it', () => {
    const withZero = insertZeroAfter(plan(), 1)
    const called = callItADay(withZero, 0, { mile: 480 })
    const absorbed = absorbPlan(called, POIS)

    expect(absorbed).not.toBeNull()
    const next = absorbed!.plan
    const zeroIndex = next.days.findIndex(
      (_, i) => next.stops[i].mile === next.stops[i + 1].mile,
    )
    // Still a zero, still on its date, riding wherever its preceding day
    // now ends.
    expect(zeroIndex).toBe(2)
    expect(next.days[zeroIndex].date).toBe('2026-05-14')
    expect(validatePlan(next)).not.toBeNull()
  })

  it('refuses a download with no published miles rather than guessing', () => {
    const called = callItADay(plan(), 0, { mile: 480 })
    const noMiles = POIS.map(({ mile: _mile, ...poi }) => poi as StoredPoi)
    expect(absorbPlan(called, noMiles)).toBeNull()
  })
})

describe('shiftPlan - the day sizes hold', () => {
  it('lets the count fall out and moves the calendar by the delta', () => {
    // Walked long - 13.8 past Lost Mountain. 25.7 miles remain, which two
    // target-sized days cover where three used to.
    const called = callItADay(plan(), 0, { mile: 500 })
    const shifted = shiftPlan(called, POIS, 15)

    expect(shifted).not.toBeNull()
    expect(shifted!.deltaDays).toBe(-1)
    expect(shifted!.finishDate).toBe('2026-05-14')
    expect(shifted!.plan.days).toHaveLength(3)
    expect(shifted!.plan.days.map((day) => day.date)).toEqual([
      '2026-05-12',
      '2026-05-13',
      '2026-05-14',
    ])
    expect(validatePlan(shifted!.plan)).not.toBeNull()
  })

  it('is refused outright while any pinned day lies ahead', () => {
    // A pin is a dated commitment; a shifted date is a moved pin.
    const pinned = togglePinned(plan(), 3)
    const called = callItADay(pinned, 0, { mile: 480 })
    expect(shiftPlan(called, POIS, 15)).toBeNull()
  })
})

describe('a rest is spent rather than mislabelled (#1031)', () => {
  /** The wireframe plan with a nearo the rhythm placed after day 1 - a
   *  4.2-mile walk to Wise Shelter, flagged as the hiker's own rest. */
  function withNearo(): HikePlan {
    const base = buildPlan(
      [
        stop(470.8, 'Damascus'),
        stop(486.2, 'Lost Mountain Shelter'),
        stop(490.4, 'Wise Shelter'),
        stop(503.3, 'Thomas Knob Shelter'),
        stop(516.1, 'Old Orchard Shelter'),
        stop(525.7, 'Atkins', true),
      ],
      { miles: 15 },
      '2026-05-12',
    )
    return {
      ...base,
      days: base.days.map((day, i) => (i === 1 ? { ...day, rest: true } : day)),
    }
  }

  /** Every day whose badge would print, with the distance it prints beside.
   *  The invariant: no row may claim a rest it is too long to be. */
  const restsAndLengths = (plan: HikePlan) =>
    planDayViews(plan)
      .filter((day) => day.rest)
      .map((day) => Math.abs(day.end.mile - day.start.mile))

  it('shift does not carry the badge onto a re-planned day', () => {
    const called = callItADay(withNearo(), 0, { mile: 486.2 })
    const shifted = shiftPlan(called, POIS, 15)

    expect(shifted).not.toBeNull()
    // Whatever the generator chose, nothing wearing the badge is longer
    // than a nearo. Before the fix this printed a 17.1-mile "rest day".
    for (const miles of restsAndLengths(shifted!.plan)) {
      expect(miles).toBeLessThanOrEqual(NEARO_MAX_MI)
    }
    expect(validatePlan(shifted!.plan)).not.toBeNull()
  })

  it('absorb does not carry the badge onto a re-planned day', () => {
    const called = callItADay(withNearo(), 0, { mile: 480 })
    const absorbed = absorbPlan(called, POIS)

    expect(absorbed).not.toBeNull()
    for (const miles of restsAndLengths(absorbed!.plan)) {
      expect(miles).toBeLessThanOrEqual(NEARO_MAX_MI)
    }
    expect(validatePlan(absorbed!.plan)).not.toBeNull()
  })

  it('a short day recorded today does not stretch tomorrow’s rest', () => {
    // The path that needs no cascade at all: rained off, stopped early, and
    // tomorrow's nearo silently grows by the miles left over.
    const called = callItADay(withNearo(), 0, { mile: 480 })
    const tomorrow = planDayViews(called)[1]

    expect(Math.abs(tomorrow.end.mile - tomorrow.start.mile)).toBeCloseTo(10.4, 1)
    expect(tomorrow.rest).toBe(false)
  })

  it('leaves the badge where the day is still a rest', () => {
    // Called exactly at the planned boundary: tomorrow is the 4.2-mile
    // nearo it always was, and losing the badge would be its own defect.
    const called = callItADay(withNearo(), 0, { mile: 486.2 })
    expect(planDayViews(called)[1].rest).toBe(true)
  })

  it('a zero rest survives every re-plan, badge and all', () => {
    const base = withNearo()
    const zeroed = insertZeroAfter(base, 2)
    const withRest: HikePlan = {
      ...zeroed,
      days: zeroed.days.map((day, i) => (i === 3 ? { ...day, rest: true } : day)),
    }
    const called = callItADay(withRest, 0, { mile: 480 })
    const absorbed = absorbPlan(called, POIS)

    expect(absorbed).not.toBeNull()
    const zeros = planDayViews(absorbed!.plan).filter((day) => day.zero)
    expect(zeros).toHaveLength(1)
    expect(zeros[0].rest).toBe(true)
  })
})

describe('cascadeChoices', () => {
  it('offers three computed outcomes, not one abstract question', () => {
    const called = callItADay(plan(), 0, { mile: 480 })
    const choices = cascadeChoices(called, POIS, 15)

    expect(choices.absorb).not.toBeNull()
    expect(choices.absorb!.days).toBe(3)
    expect(choices.shift).not.toBeNull()
    // Leave: tomorrow is what the shortfall made it - the whole stretch to
    // Thomas Knob.
    expect(choices.leaveTomorrowMi).toBeCloseTo(23.3)
    expect(choices.pinnedAhead).toBe(0)
  })

  it('counts the pins it will not re-plan through', () => {
    const pinned = togglePinned(togglePinned(plan(), 2), 3)
    const called = callItADay(pinned, 0, { mile: 480 })
    const choices = cascadeChoices(called, POIS, 15)

    expect(choices.pinnedAhead).toBe(2)
    expect(choices.shift).toBeNull()
  })
})

describe('nearestStop', () => {
  it('names the place a day ended when one is close enough', () => {
    expect(nearestStop(POIS, 490.3)).toEqual({
      mile: 490.4,
      name: 'Wise Shelter',
      poiId: 'wise',
    })
  })

  it('offers nothing rather than a place half a mile of guess away', () => {
    expect(nearestStop(POIS, 493)).toBeNull()
  })
})
