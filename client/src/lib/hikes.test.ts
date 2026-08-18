// Tests for hikes.ts (#788).
//
// The load-bearing ones are in `resolvePlace`: they are what decides
// whether a hike opened in 2026 still describes the same ground in 2031,
// which is the whole reason the ends are references rather than miles.

import { describe, expect, it } from 'vitest'

import {
  clipSpans,
  hikeFigures,
  recordedPlan,
  hikeFromTrips,
  hikeOfTrip,
  mergeSpans,
  resolvePlace,
  spanLength,
  validateHike,
  walkedSpans,
  type Hike,
} from './hikes'
import { buildPlan, type HikePlan } from './plan'
import type { StoredPoi } from './trailData'
import type { Trip } from './trips'

const poi = (id: string, name: string, mile: number | undefined): StoredPoi => ({
  id,
  type: 'shelter',
  name,
  lat: 0,
  lon: 0,
  confidence: 'high',
  ...(mile === undefined ? {} : { mile }),
})

/** The download as it stands today: Damascus has been re-measured 0.4 mi
 *  further along since the hike was written. */
const POIS = [
  poi('damascus', 'Damascus', 471.2),
  poi('atkins', 'Atkins', 503.3),
  poi('nomile', 'Pre-#753 Shelter', undefined),
]

describe('resolvePlace - why the ends are references', () => {
  it('uses the POI’s CURRENT mile, not the mile that was stored', () => {
    // The hike was written when Damascus published as 470.8. A relocation
    // moved it. The reference still names the same place, so the resolved
    // mile is today's - which is the entire point of storing a reference.
    const resolved = resolvePlace(
      { poiId: 'damascus', name: 'Damascus', mile: 470.8 },
      POIS,
    )

    expect(resolved.mile).toBe(471.2)
    expect(resolved.from).toBe('reference')
    expect(resolved.movedMi).toBeCloseTo(0.4)
    expect(resolved.name).toBe('Damascus')
  })

  it('reports no movement when the published mile has not moved', () => {
    const resolved = resolvePlace({ poiId: 'atkins', mile: 503.3 }, POIS)

    expect(resolved.mile).toBe(503.3)
    expect(resolved.movedMi).toBe(0)
  })

  it('says a dropped point is a dropped point', () => {
    // No reference was ever recorded, so its mile is all there has ever
    // been. Honest, and not drift-proof - and it says which it is.
    const resolved = resolvePlace({ mile: 486.2 }, POIS)

    expect(resolved.mile).toBe(486.2)
    expect(resolved.from).toBe('stored')
    expect(resolved.movedMi).toBeNull()
  })

  it('falls back to the hint when the reference is gone, and SAYS so', () => {
    // The open question this issue names: a POI removed or merged away by a
    // later release. The cached mile is used because there is nothing else,
    // and `from` is what the screen reads to admit it.
    const resolved = resolvePlace(
      { poiId: 'demolished', name: 'Old Shelter', mile: 490.1 },
      POIS,
    )

    expect(resolved.mile).toBe(490.1)
    expect(resolved.from).toBe('missing')
    expect(resolved.name).toBe('Old Shelter')
  })

  it('treats a POI without a published mile as missing too', () => {
    // A pre-#753 download has the POI but no mile to resolve against, which
    // leaves the hint load-bearing in exactly the same way.
    expect(resolvePlace({ poiId: 'nomile', mile: 12.0 }, POIS).from).toBe('missing')
  })
})

describe('validateHike', () => {
  const good: Hike = {
    id: 'h1',
    name: 'Appalachian Trail',
    type: 'thru',
    start: { poiId: 'damascus', mile: 470.8 },
    end: { mile: 2197.4 },
    tripIds: ['a'],
  }

  it('accepts a hike, keeping both ends', () => {
    const validated = validateHike(good)
    expect(validated?.start.poiId).toBe('damascus')
    expect(validated?.end.mile).toBe(2197.4)
  })

  it('refuses what cannot be a hike', () => {
    expect(validateHike(null)).toBeNull()
    expect(validateHike({ ...good, type: 'expedition' })).toBeNull()
    expect(validateHike({ ...good, start: { mile: -3 } })).toBeNull()
    expect(validateHike({ ...good, end: undefined })).toBeNull()
    expect(validateHike({ ...good, id: '' })).toBeNull()
  })
})

describe('spans', () => {
  it('records only walked days, and never a zero', () => {
    const plan = buildPlan(
      [
        { mile: 10, resupply: false },
        { mile: 20, resupply: false },
        { mile: 20, resupply: false },
        { mile: 32, resupply: false },
      ],
      { miles: 12 },
    )
    plan.days[0].walked = true
    plan.days[1].walked = true // the zero: walked, but no ground covered

    expect(walkedSpans(plan)).toEqual([{ from: 10, to: 20 }])
  })

  it('merges rather than sums, so a re-walked mile counts once', () => {
    // A hiker who walked Georgia twice has not walked twice the trail.
    const merged = mergeSpans([
      { from: 0, to: 30 },
      { from: 20, to: 50 },
      { from: 80, to: 90 },
    ])
    expect(merged).toEqual([
      { from: 0, to: 50 },
      { from: 80, to: 90 },
    ])
    expect(spanLength(merged)).toBe(60)
  })

  it('clips to the hike, so a trip past its ends does not lengthen it', () => {
    expect(clipSpans([{ from: 0, to: 100 }], { from: 20, to: 60 })).toEqual([
      { from: 20, to: 60 },
    ])
    expect(clipSpans([{ from: 0, to: 10 }], { from: 20, to: 60 })).toEqual([])
  })
})

describe('hikeFigures', () => {
  function trip(id: string, from: number, to: number, walked: boolean): Trip {
    const plan: HikePlan = buildPlan(
      [
        { mile: from, resupply: false },
        { mile: to, resupply: false },
      ],
      { miles: 15 },
    )
    if (walked) plan.days[0].walked = true
    return { id, name: id, plan }
  }

  const hike: Hike = {
    id: 'h1',
    name: 'Virginia',
    type: 'section',
    start: { mile: 0 },
    end: { mile: 100 },
    tripIds: ['a', 'b'],
  }

  it('counts walked miles as a union, and leaves the rest', () => {
    const trips = [trip('a', 0, 30, true), trip('b', 20, 50, true)]
    const figures = hikeFigures(hike, trips, POIS)

    expect(figures.totalMi).toBe(100)
    expect(figures.walkedMi).toBe(50) // not 60 - the overlap counts once
    expect(figures.leftMi).toBe(50)
    expect(figures.daysWalked).toBe(2)
    expect(figures.tripCount).toBe(2)
  })

  it('does not count a planned trip as walked', () => {
    // A trip on the calendar closes no gap until it happens.
    const figures = hikeFigures(hike, [trip('a', 0, 30, false)], POIS)

    expect(figures.walkedMi).toBe(0)
    expect(figures.leftMi).toBe(100)
    expect(figures.tripCount).toBe(1)
  })

  it('ignores trips that belong to another hike', () => {
    const figures = hikeFigures(
      { ...hike, tripIds: ['a'] },
      [trip('a', 0, 30, true), trip('b', 30, 60, true)],
      POIS,
    )
    expect(figures.walkedMi).toBe(30)
  })

  it('flags figures resting on a reference this download has lost', () => {
    const stranded: Hike = { ...hike, start: { poiId: 'demolished', mile: 0 } }
    expect(hikeFigures(stranded, [], POIS).uncertain).toBe(true)
    expect(hikeFigures(hike, [], POIS).uncertain).toBe(false)
  })

  it('moves with the reference, so a relocation does not silently resize a hike', () => {
    const anchored: Hike = {
      ...hike,
      start: { poiId: 'damascus', mile: 470.8 },
      end: { poiId: 'atkins', mile: 503.3 },
      tripIds: [],
    }
    // 471.2 → 503.3 today, not the 32.5 the stored hints would have given.
    expect(hikeFigures(anchored, [], POIS).totalMi).toBeCloseTo(32.1)
  })
})

describe('hikeFromTrips', () => {
  function trip(id: string, from: number, to: number): Trip {
    return {
      id,
      name: id,
      plan: buildPlan(
        [
          { mile: from, name: 'Damascus', poiId: 'damascus', resupply: false },
          { mile: to, name: 'Atkins', poiId: 'atkins', resupply: false },
        ],
        { miles: 15 },
      ),
    }
  }

  it('spans the outermost stops, carrying their references across', () => {
    const hike = hikeFromTrips([trip('a', 470.8, 503.3), trip('b', 520, 560)], 'Virginia')

    expect(hike?.start.mile).toBe(470.8)
    expect(hike?.start.poiId).toBe('damascus')
    expect(hike?.end.mile).toBe(560)
    expect(hike?.tripIds).toEqual(['a', 'b'])
    expect(hike?.type).toBe('section')
  })

  it('refuses to make a hike out of no ground', () => {
    expect(hikeFromTrips([], 'Nothing')).toBeNull()
  })
})

describe('hikeOfTrip', () => {
  it('finds the one hike holding a trip, or null', () => {
    const hikes: Hike[] = [
      {
        id: 'h1',
        name: 'One',
        type: 'section',
        start: { mile: 0 },
        end: { mile: 10 },
        tripIds: ['a'],
      },
    ]
    expect(hikeOfTrip(hikes, 'a')?.id).toBe('h1')
    expect(hikeOfTrip(hikes, 'b')).toBeNull()
  })
})

describe('recordedPlan - ground already walked (#789)', () => {
  it('arrives walked, and nobody generated it', () => {
    const plan = recordedPlan([
      { mile: 0, name: 'Springer', resupply: false },
      { mile: 470.8, name: 'Damascus', resupply: false },
    ])

    expect(plan.days).toHaveLength(1)
    expect(plan.days[0].walked).toBe(true)
    expect(plan.days[0].generated).toBe(false)
    expect(walkedSpans(plan)).toEqual([{ from: 0, to: 470.8 }])
  })

  it('keeps every boundary the hiker could remember', () => {
    // More detail when they have it: three stops record two walked
    // stretches rather than flattening to one.
    const plan = recordedPlan([
      { mile: 0, resupply: false },
      { mile: 165.7, resupply: false },
      { mile: 470.8, resupply: false },
    ])

    expect(walkedSpans(plan)).toEqual([
      { from: 0, to: 165.7 },
      { from: 165.7, to: 470.8 },
    ])
  })

  it('takes a date when there is one to give', () => {
    const plan = recordedPlan(
      [
        { mile: 0, resupply: false },
        { mile: 10, resupply: false },
      ],
      '2019-06-01',
    )
    expect(plan.days[0].date).toBe('2019-06-01')
  })

  it('counts once where a recorded stretch overlaps a walked trip', () => {
    // The open question #789 raised, settled by the union rather than by
    // whichever loop ran first: a hiker who recorded Georgia AND walked
    // part of it again has not walked more trail than exists.
    const recorded: Trip = {
      id: 'r',
      name: 'From memory',
      recorded: true,
      plan: recordedPlan([
        { mile: 0, resupply: false },
        { mile: 100, resupply: false },
      ]),
    }
    const walkedAgain: HikePlan = buildPlan(
      [
        { mile: 60, resupply: false },
        { mile: 140, resupply: false },
      ],
      { miles: 15 },
    )
    walkedAgain.days[0].walked = true

    const hike: Hike = {
      id: 'h',
      name: 'Overlapping',
      type: 'section',
      start: { mile: 0 },
      end: { mile: 200 },
      tripIds: ['r', 'w'],
    }
    const figures = hikeFigures(
      hike,
      [recorded, { id: 'w', name: 'Again', plan: walkedAgain }],
      [],
    )

    expect(figures.walkedMi).toBe(140) // not 180
    expect(figures.leftMi).toBe(60)
  })
})
