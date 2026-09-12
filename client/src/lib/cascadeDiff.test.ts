import { describe, expect, it } from 'vitest'

import { callItADay, shiftPlan, absorbPlan } from './cascade'
import { diffPlans } from './cascadeDiff'
import { buildPlan, insertZeroAfter } from './plan'
import type { StoredPoi } from './trailData'

// The diff before a cascade applies (#1373, frame 7b): which days move and
// how, as facts about the plan - never a verdict on the hiker.

const shelter = (id: string, mile: number, name: string): StoredPoi => ({
  id,
  type: 'shelter',
  name,
  lat: 0,
  lon: 0,
  confidence: 'high',
  mile,
})

const POIS = [
  shelter('lost', 486.2, 'Lost Mountain Shelter'),
  shelter('wise', 490.4, 'Wise Shelter'),
  shelter('a', 496, 'Shelter A'),
]

/** Two walking days at a miles target, dated. */
function milesPlan() {
  return buildPlan(
    [
      { mile: 470.8, name: 'Damascus', resupply: false },
      { mile: 486.2, name: 'Lost Mountain Shelter', resupply: false },
      { mile: 503.3, name: 'Atkins', resupply: false },
    ],
    { miles: 15 },
    '2026-05-12',
  )
}

describe('diffPlans', () => {
  it('says nothing about a plan against itself', () => {
    const plan = milesPlan()
    const diff = diffPlans(plan, plan)
    expect(diff.rows.map((row) => row.state)).toEqual(['kept', 'kept'])
    expect(diff.fewer).toBe(0)
  })

  it('reads a walked day as a record, and a day whose length or date moved as moved - with what it was', () => {
    const plan = milesPlan()
    // A zero after day 1 takes day 2's slot: by index, the second row is
    // now a zero where a 17.1-mile day stood, and a third day appeared.
    const after = insertZeroAfter(plan, 0)
    const diff = diffPlans(plan, after)
    expect(diff.rows.map((row) => row.state)).toEqual(['kept', 'moved', 'new'])
    expect(diff.rows[1].wasDistanceMi).toBeCloseTo(17.1, 1)
    expect(diff.rows[1].wasDate).toBeNull()
    expect(diff.rows[2].day.date).toBe('2026-05-14')

    const walked = callItADay(plan, 0, { mile: 486.2 })
    expect(diffPlans(plan, walked).rows[0].state).toBe('walked')
  })

  it('says what a re-planned day used to measure, and counts days the plan lost', () => {
    // Stopped short on day 1: the stretch to Atkins re-plans at a slower
    // target, and the days after it are shorter and more numerous.
    const short = callItADay(milesPlan(), 0, { mile: 480, name: 'A camp' })
    const shifted = shiftPlan(short, POIS, 8)
    expect(shifted).not.toBeNull()
    const more = diffPlans(short, shifted!.plan)
    expect(more.rows[0].state).toBe('walked')
    expect(more.rows[1].state).toBe('moved')
    expect(more.rows[1].wasDistanceMi).toBeCloseTo(23.3, 1)
    expect(more.rows.filter((row) => row.state === 'new').length).toBeGreaterThan(0)
    expect(more.fewer).toBe(0)

    // The same move read backwards: rows the shorter plan has none of are
    // counted, never drawn.
    expect(diffPlans(shifted!.plan, short).fewer).toBeGreaterThan(0)
    // And absorbing over the one day left changes nothing it can say.
    const absorbed = absorbPlan(short, POIS)
    expect(absorbed).not.toBeNull()
    expect(diffPlans(short, absorbed!.plan).rows[1].state).toBe('kept')
  })
})
