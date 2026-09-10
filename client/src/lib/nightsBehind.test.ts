import { describe, it, expect } from 'vitest'
import { nightsBehind } from './nightsBehind'
import type { HikePlan } from './plan'

const stop = (mile: number, name?: string, poiId?: string) => ({
  mile,
  ...(name === undefined ? {} : { name }),
  ...(poiId === undefined ? {} : { poiId }),
  resupply: false,
})

const PLAN = {
  target: { kind: 'miles', value: 15 },
  stops: [
    stop(1331.2, 'Gren Anderson Shelter', 'atc_shelters:1'),
    stop(1342.1, 'High Point Shelter', 'atc_shelters:2'),
    stop(1349.8, 'Rutherford campsite', 'atc_campsites:3'),
    stop(1360.0, 'Unionville', 'atc_communities:4'),
  ],
  days: [
    { id: 'd0', date: '2026-09-08' },
    { id: 'd1', date: '2026-09-09' },
    { id: 'd2', date: '2026-09-10' },
  ],
} as unknown as HikePlan

describe('nightsBehind', () => {
  it('names tonight, last night, and the night before by its weekday, tonight first', () => {
    expect(nightsBehind(PLAN, 1)).toEqual([
      {
        label: 'Tonight',
        poiId: 'atc_campsites:3',
        name: 'Rutherford campsite',
        mile: 1349.8,
      },
      {
        label: 'Last night',
        poiId: 'atc_shelters:2',
        name: 'High Point Shelter',
        mile: 1342.1,
      },
      // The first stop is where the hiker slept BEFORE day 0 (dated Tue
      // 8 Sep), so that night is Monday's - an earlier draft read it off
      // day 0's own date and called it Tuesday.
      {
        label: 'Mon night',
        poiId: 'atc_shelters:1',
        name: 'Gren Anderson Shelter',
        mile: 1331.2,
      },
    ])
  })

  it('dates the night before last by the day that ended at it', () => {
    // Day 2 (Thu): tonight is Unionville, last night Rutherford, and the
    // night before that High Point - where day 0, dated Tuesday, ended.
    expect(nightsBehind(PLAN, 2).map((night) => night.label)).toEqual([
      'Tonight',
      'Last night',
      'Tue night',
    ])
  })

  it('has nothing before the first day but its two ends', () => {
    expect(nightsBehind(PLAN, 0).map((night) => night.label)).toEqual([
      'Tonight',
      'Last night',
    ])
  })

  it('skips a dropped point, which is not a place anybody can answer for', () => {
    const plan = {
      ...PLAN,
      stops: [stop(1331.2), PLAN.stops[1], stop(1349.8), PLAN.stops[3]],
    }

    expect(nightsBehind(plan as HikePlan, 1).map((night) => night.name)).toEqual([
      'High Point Shelter',
    ])
  })

  it('says "two nights ago" rather than inventing a weekday the plan never dated', () => {
    const plan = {
      ...PLAN,
      days: PLAN.days.map(({ id }) => ({ id })),
    } as unknown as HikePlan

    expect(nightsBehind(plan, 1)[2].label).toBe('Two nights ago')
  })
})
