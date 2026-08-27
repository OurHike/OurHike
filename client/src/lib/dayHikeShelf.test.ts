// The day-hike shelf's rules (#1008): the split, the orderings, the
// trailhead door's radius, and the gap measurements.

import { describe, expect, it } from 'vitest'

import type { DayHike } from './dayHikes'
import {
  cachedEstimate,
  dayHikeGaps,
  dayHikesNearHere,
  distanceToStartMiles,
  NEAR_START_MILES,
  sortedByDate,
  sortedByNearest,
  sortedByTime,
  splitDayHikes,
} from './dayHikeShelf'
import { STANDARD_PACE } from './pace'

/** A valid stored hike at a grid coordinate, tweakable per test. */
function hikeAt(
  id: string,
  lon: number,
  lat: number,
  overrides: Partial<DayHike> = {},
): DayHike {
  return {
    id,
    name: id,
    date: null,
    segments: [
      [
        { coord: [lon, lat], poiId: null },
        { coord: [lon + 0.01, lat], poiId: null },
      ],
    ],
    figures: { miles: 3.4, legs: [] },
    looped: false,
    recorded: 'planned',
    note: '',
    ...overrides,
  }
}

describe('the split - to walk against walked, the only state that matters', () => {
  it('splits by recorded, keeping the newest-first-undated-last order in each shelf', () => {
    const shelf = splitDayHikes([
      hikeAt('old-plan', -74, 41, { date: '2026-07-01' }),
      hikeAt('walked-one', -74, 41, { recorded: 'walked', date: '2026-08-02' }),
      hikeAt('undated-plan', -74, 41),
      hikeAt('new-plan', -74, 41, { date: '2026-09-12' }),
    ])
    expect(shelf.toWalk.map((hike) => hike.id)).toEqual([
      'new-plan',
      'old-plan',
      'undated-plan',
    ])
    expect(shelf.walked.map((hike) => hike.id)).toEqual(['walked-one'])
  })

  it('keeps the Plan home ordering: newest date first, undated last', () => {
    const sorted = sortedByDate([
      hikeAt('undated', -74, 41),
      hikeAt('august', -74, 41, { date: '2026-08-01' }),
      hikeAt('september', -74, 41, { date: '2026-09-01' }),
    ])
    expect(sorted.map((hike) => hike.id)).toEqual(['september', 'august', 'undated'])
  })
})

describe('the trailhead door (frame D8)', () => {
  it('offers a hike whose start is inside the radius, with its distance', () => {
    const near = dayHikesNearHere([hikeAt('close', -74.095, 41.25)], {
      lon: -74.0955,
      lat: 41.2502,
    })
    expect(near).toHaveLength(1)
    expect(near[0].hike.id).toBe('close')
    // ~50 m of ground - well under a tenth of a mile.
    expect(near[0].miles).toBeGreaterThan(0)
    expect(near[0].miles).toBeLessThan(0.1)
  })

  it('does not offer a start past the radius', () => {
    // ~0.7 mi east at this latitude - outside the half-mile door.
    const near = dayHikesNearHere([hikeAt('far', -74.095, 41.25)], {
      lon: -74.0815,
      lat: 41.25,
    })
    expect(near).toEqual([])
  })

  it('never offers a walked record - the door says "still to walk"', () => {
    const near = dayHikesNearHere(
      [hikeAt('done', -74.095, 41.25, { recorded: 'walked' })],
      { lon: -74.095, lat: 41.25 },
    )
    expect(near).toEqual([])
  })

  it('sorts nearest first', () => {
    const near = dayHikesNearHere(
      [hikeAt('half-off', -74.09, 41.25), hikeAt('right-here', -74.095, 41.25)],
      { lon: -74.095, lat: 41.25 },
    )
    expect(near.map((entry) => entry.hike.id)).toEqual(['right-here', 'half-off'])
  })

  it('the radius is the documented half mile, and stays tagged unvalidated', () => {
    // Pinning the constant is deliberate: the number is a reading of the
    // storyboard, not a measurement, and a silent change to it should have
    // to explain itself against the derivation in dayHikeShelf.ts.
    expect(NEAR_START_MILES).toBe(0.5)
  })
})

describe('nearest-me ordering for the list', () => {
  it('sorts by distance to each start, unplaceable records last', () => {
    const broken = hikeAt('unreadable', -74, 41)
    // A record whose segments validation would normally refuse - simulated
    // here as empty, which distanceToStartMiles answers with null.
    const noStart = { ...broken, segments: [] as DayHike['segments'] }
    const sorted = sortedByNearest(
      [hikeAt('far', -74.06, 41.25), noStart, hikeAt('near', -74.095, 41.25)],
      { lon: -74.095, lat: 41.25 },
    )
    expect(sorted.map((hike) => hike.id)).toEqual(['near', 'far', 'unreadable'])
    expect(distanceToStartMiles(noStart, { lon: -74.095, lat: 41.25 })).toBeNull()
  })
})

describe('gaps between segments (frame D5, #935)', () => {
  it('measures each gap straight-line between the ends that face it', () => {
    const hike = hikeAt('gappy', -74.095, 41.25, {
      segments: [
        [
          { coord: [-74.095, 41.25], poiId: null },
          { coord: [-74.09, 41.25], poiId: null },
        ],
        [
          // ~0.26 mi east of the first segment's last end.
          { coord: [-74.085, 41.25], poiId: null },
          { coord: [-74.08, 41.25], poiId: null },
        ],
      ],
    })
    const gaps = dayHikeGaps(hike)
    expect(gaps).toHaveLength(1)
    expect(gaps[0].afterSegment).toBe(0)
    expect(gaps[0].miles).toBeGreaterThan(0.2)
    expect(gaps[0].miles).toBeLessThan(0.35)
  })

  it('a single-segment hike has no gaps', () => {
    expect(dayHikeGaps(hikeAt('plain', -74.095, 41.25))).toEqual([])
  })
})

describe('pricing a walk from its cache (#1045, 2026-08-27)', () => {
  const priced = (id: string, miles: number, gainFt: number) =>
    hikeAt(id, -74.1, 41.25, {
      figures: { miles, legs: [], climb: { gainFt, lossFt: gainFt } },
    })

  it('has nothing to say about a hike whose record holds no climb', () => {
    // Both ways of getting here answer the same: a record saved before the
    // field existed, and one the graph could not price. Neither may fall
    // back to distance alone - Naismith with no ascent is a flat-ground
    // claim, and it fails SHORT.
    const older = hikeAt('older', -74.1, 41.25)
    const unpriceable = hikeAt('unpriceable', -74.1, 41.25, {
      figures: { miles: 3.4, legs: [], climb: null },
    })

    expect(cachedEstimate(older, STANDARD_PACE)).toBeNull()
    expect(cachedEstimate(unpriceable, STANDARD_PACE)).toBeNull()
  })

  it('prices one it can, and a climb makes the walk longer than the miles alone', () => {
    const flat = cachedEstimate(priced('flat', 5, 0), STANDARD_PACE)
    const steep = cachedEstimate(priced('steep', 5, 2000), STANDARD_PACE)

    expect(flat).not.toBeNull()
    expect(steep).not.toBeNull()
    expect(steep!.minutes).toBeGreaterThan(flat!.minutes)
  })

  it('sorts shortest first and leaves the unpriceable ones at the end', () => {
    // A sort that dropped them would be a filter wearing a sort's label, and
    // a hiker would lose a walk off the screen by pressing a chip.
    const sorted = sortedByTime(
      [priced('long', 9, 2400), hikeAt('nothing', -74.1, 41.25), priced('short', 2, 300)],
      STANDARD_PACE,
    )

    expect(sorted.map((hike) => hike.id)).toEqual(['short', 'long', 'nothing'])
  })
})
