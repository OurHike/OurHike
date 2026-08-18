// Tests for dayPlanner.ts - the auto-generated plan's DP (#757).
//
// The scenarios are small and hand-checkable on purpose: the spike
// (pipeline/spike_day_planner.py, #754) already measured the algorithm
// against the real trail, so what these pin is the judgement - the
// asymmetry, the cap, the shelters-over-campsites nudge - each against the
// smallest stop set where it changes the answer.

import { describe, expect, it } from 'vitest'

import {
  candidateStops,
  dayCost,
  DEFAULT_CAP_MI,
  OVER_TARGET_WEIGHT,
  planDays,
  planDaysExact,
  type CandidateStop,
} from './dayPlanner'
import type { StoredPoi } from './trailData'

const terminus = (mile: number): CandidateStop => ({ mile, kind: 'terminus' })
const shelter = (mile: number): CandidateStop => ({
  mile,
  kind: 'shelter',
  name: `shelter ${mile}`,
})
const campsite = (mile: number): CandidateStop => ({
  mile,
  kind: 'campsite',
  name: `campsite ${mile}`,
})
const miles = (stops: CandidateStop[]) => stops.map((stop) => stop.mile)

describe('dayCost', () => {
  it('prices overshooting harder than undershooting by the same amount', () => {
    expect(dayCost(17, 15)).toBeCloseTo(OVER_TARGET_WEIGHT * 4)
    expect(dayCost(13, 15)).toBeCloseTo(4)
    expect(dayCost(15, 15)).toBe(0)
  })
})

describe('planDays', () => {
  it('keeps both ends - a hike starts and finishes where the hiker said', () => {
    const chosen = planDays([terminus(0), shelter(10), terminus(20)], 10)
    expect(miles(chosen)).toEqual([0, 10, 20])
  })

  it('spreads the unavoidable error rather than paying it all at the far end', () => {
    // Greedy takes the 9 then the 18 - both look fine - and is left with a
    // 2-mile final day (cost 64). The DP eats one 11-mile day instead.
    const chosen = planDays([terminus(0), shelter(9), shelter(18), terminus(20)], 10)
    expect(miles(chosen)).toEqual([0, 9, 20])
  })

  it('never schedules past the cap while any stop inside it exists', () => {
    const stops = [terminus(0), shelter(12), shelter(24), terminus(36)]
    const chosen = planDays(stops, 36, { capMi: 15 })
    const spans = chosen.slice(1).map((stop, i) => stop.mile - chosen[i].mile)
    expect(Math.max(...spans)).toBeLessThanOrEqual(15)
  })

  it('returns the over-cap day as it is where the trail offers nothing', () => {
    // A 30-mile stop gap under a 25-mile cap: refusing to plan there would
    // be refusing to describe a stretch of trail that exists.
    const chosen = planDays([terminus(0), terminus(30)], 15)
    expect(miles(chosen)).toEqual([0, 30])
    expect(30).toBeGreaterThan(DEFAULT_CAP_MI)
  })

  it('breaks a near-tie toward the shelter', () => {
    // The campsite hits the 10-mile target exactly; the shelter misses it
    // by a tenth. The nudge is sized so the shelter still wins a near-tie -
    // and only a near-tie.
    const nearTie = planDays([terminus(0), shelter(9.9), campsite(10), terminus(20)], 10)
    expect(miles(nearTie)).toEqual([0, 9.9, 20])

    const notATie = planDays([terminus(0), shelter(8), campsite(10), terminus(20)], 10)
    expect(miles(notATie)).toEqual([0, 10, 20])
  })

  it('plans in whatever unit the effort function measures', () => {
    // An effort that calls every mile two units doubles the target's reach:
    // with a 20-unit target, ten-mile days are on target.
    const chosen = planDays([terminus(0), shelter(10), shelter(15), terminus(20)], 20, {
      effort: (from, to) => Math.abs(to.mile - from.mile) * 2,
    })
    expect(miles(chosen)).toEqual([0, 10, 20])
  })

  it('plans a southbound route in walk order', () => {
    const chosen = planDays([terminus(20), shelter(10), terminus(0)], 10)
    expect(miles(chosen)).toEqual([20, 10, 0])
  })
})

describe('planDaysExact - the absorb DP (#758)', () => {
  it('spends exactly the days it was given, balanced', () => {
    const chosen = planDaysExact(
      [terminus(0), shelter(8), shelter(15), shelter(23), terminus(30)],
      2,
    )
    expect(chosen).not.toBeNull()
    expect(miles(chosen as CandidateStop[])).toEqual([0, 15, 30])
  })

  it('still refuses to cross the cap while a stop inside it exists', () => {
    const chosen = planDaysExact([terminus(0), shelter(10), shelter(20), terminus(40)], 2)
    // One 20-20 split exists inside the cap; a 10-30 split does not.
    expect(miles(chosen as CandidateStop[])).toEqual([0, 20, 40])
  })

  it('answers null when the count cannot be walked over these stops', () => {
    // Three days need three boundaries to end at; two stops offer one.
    expect(planDaysExact([terminus(0), terminus(30)], 3)).toBeNull()
    expect(planDaysExact([terminus(0), terminus(30)], 0)).toBeNull()
  })
})

describe('candidateStops', () => {
  const poi = (
    id: string,
    type: string,
    mile: number | undefined,
    name = id,
  ): StoredPoi => ({
    id,
    type,
    name,
    lat: 0,
    lon: 0,
    confidence: 'high',
    ...(mile === undefined ? {} : { mile }),
  })

  it('keeps shelters and campsites inside the span, in walk order, ends forced', () => {
    const stops = candidateStops(
      [
        poi('a', 'shelter', 12),
        poi('b', 'campsite', 5),
        poi('c', 'water', 8),
        poi('d', 'shelter', 40),
        poi('e', 'shelter', undefined),
      ],
      0,
      20,
    )
    expect(stops).not.toBeNull()
    expect(miles(stops as CandidateStop[])).toEqual([0, 5, 12, 20])
    expect((stops as CandidateStop[])[0].kind).toBe('terminus')
  })

  it('orders a southbound span south', () => {
    const stops = candidateStops(
      [poi('a', 'shelter', 12), poi('b', 'campsite', 5)],
      20,
      0,
    )
    expect(miles(stops as CandidateStop[])).toEqual([20, 12, 5, 0])
  })

  it('refuses a download that carries no published miles at all', () => {
    // Pre-#753 data: there is no honest way onto the profile's axis, and
    // the caller says "needs a newer download" rather than measuring one
    // locally (HIKE_PLANNING.md Findings 1-2).
    expect(candidateStops([poi('a', 'shelter', undefined)], 0, 20)).toBeNull()
  })
})
