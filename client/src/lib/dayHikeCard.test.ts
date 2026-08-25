// Tests for lib/dayHikeCard.ts - the finished-hike card's derivations (#980).
//
// The two rules worth a suite: a saved hike the current graph cannot claim is
// REFUSED whole (never partially rerouted), and a bail-out's mile is the
// distance a hiker has actually walked when they reach the junction - which
// pair-wise accumulation gets right and a deduplicated edge list gets wrong
// on any out-and-back.

import { describe, expect, it } from 'vitest'

import { dayHikeBailOuts, resolveDayHike } from './dayHikeCard'
import type { DayHike, DayHikeEnd, DayHikeSegment } from './dayHikes'
import { buildGraphIndex, type TrailGraph } from './trailGraph'

// The App.dayHike fixture's Harriman-ish T, grown one arm so the junction is
// a real crossing: Seven Hills passes THROUGH node 1, one edge each side,
// same trail_id - the shape whose two edges must collapse onto one row.
//
//        3 (-74.09, 41.26)   Seven Hills Trail, white (edge 2)
//        |
//   0 -- 1 -- 2              Pine Meadow Trail, blue (edges 0, 1)
//        |
//        4 (-74.09, 41.24)   Seven Hills Trail, white (edge 3)
const GRAPH: TrailGraph = {
  nodes: [
    [-74.1, 41.25],
    [-74.09, 41.25],
    [-74.08, 41.25],
    [-74.09, 41.26],
    [-74.09, 41.24],
  ],
  edges: [
    {
      from: 0,
      to: 1,
      length_m: 836,
      trail_id: 'oprhp_trails:1',
      source: 'oprhp_trails',
      name: 'Pine Meadow Trail',
      blaze_color: 'blue',
    },
    {
      from: 1,
      to: 2,
      length_m: 836,
      trail_id: 'oprhp_trails:1',
      source: 'oprhp_trails',
      name: 'Pine Meadow Trail',
      blaze_color: 'blue',
    },
    {
      from: 1,
      to: 3,
      length_m: 1112,
      trail_id: 'nynjtc_long_path:2',
      source: 'nynjtc_long_path',
      name: 'Seven Hills Trail',
      blaze_color: 'white',
    },
    {
      from: 1,
      to: 4,
      length_m: 1112,
      trail_id: 'nynjtc_long_path:2',
      source: 'nynjtc_long_path',
      name: 'Seven Hills Trail',
      blaze_color: 'white',
    },
  ],
}

const index = buildGraphIndex(GRAPH)

const end = (lon: number, lat: number): DayHikeEnd => ({ coord: [lon, lat], poiId: null })

function hikeOf(segments: DayHikeSegment[], looped = false): DayHike {
  return {
    id: 'hike-1',
    name: 'Pine Meadow out',
    date: null,
    segments,
    // A stale cache on purpose: nothing below may read it.
    figures: { miles: 99, legs: [] },
    looped,
    recorded: 'planned',
  }
}

describe('resolveDayHike', () => {
  it('re-claims the stored ends and re-derives the figures', () => {
    const resolved = resolveDayHike(
      index,
      hikeOf([[end(-74.095, 41.25), end(-74.085, 41.25)]]),
    )

    expect(resolved).not.toBeNull()
    // Half of each 836 m edge: 836 m, not the cache's planted 99 miles.
    expect(resolved?.miles).toBeCloseTo(0.52, 2)
    expect(resolved?.legs.map((leg) => leg.name)).toEqual(['Pine Meadow Trail'])
    expect(resolved?.looped).toBe(false)
  })

  it('refuses the whole hike when one end is off every trail', () => {
    const resolved = resolveDayHike(
      index,
      hikeOf([[end(-74.095, 41.25), end(-74.095, 41.3)]]),
    )

    expect(resolved).toBeNull()
  })

  it('refuses a multi-segment hike asked to loop, rather than guessing across the gap', () => {
    const resolved = resolveDayHike(
      index,
      hikeOf(
        [
          [end(-74.095, 41.25), end(-74.085, 41.25)],
          [end(-74.09, 41.252), end(-74.09, 41.258)],
        ],
        true,
      ),
    )

    expect(resolved).toBeNull()
  })

  it('sums walked miles across segments and keeps their legs in order', () => {
    const resolved = resolveDayHike(
      index,
      hikeOf([
        [end(-74.095, 41.25), end(-74.085, 41.25)],
        [end(-74.09, 41.252), end(-74.09, 41.258)],
      ]),
    )

    expect(resolved).not.toBeNull()
    // 836 m of Pine Meadow, then 41.252→41.258 of Seven Hills (0.006 of the
    // 0.01-degree, 1,112 m edge): 836 + 667.2 = 1,503 m.
    expect(resolved?.miles).toBeCloseTo(0.93, 2)
    expect(resolved?.legs.map((leg) => leg.name)).toEqual([
      'Pine Meadow Trail',
      'Seven Hills Trail',
    ])
  })
})

describe('dayHikeBailOuts', () => {
  it('lists a crossing trail once, at the mile actually walked to its junction', () => {
    const resolved = resolveDayHike(
      index,
      hikeOf([[end(-74.095, 41.25), end(-74.085, 41.25)]]),
    )
    const bailOuts = dayHikeBailOuts(index, resolved!)

    // Seven Hills crosses node 1 with an edge on each side; one trail is one
    // way off, so the two edges are one row.
    expect(bailOuts).toHaveLength(1)
    expect(bailOuts[0].name).toBe('Seven Hills Trail')
    expect(bailOuts[0].blaze_color).toBe('white')
    // Half of the first 836 m edge walked to reach the junction.
    expect(bailOuts[0].miles).toBeCloseTo(0.26, 2)
  })

  it('answers a single-edge walk with an empty list, which the card must print', () => {
    const resolved = resolveDayHike(
      index,
      hikeOf([[end(-74.098, 41.25), end(-74.092, 41.25)]]),
    )

    expect(dayHikeBailOuts(index, resolved!)).toEqual([])
  })

  it('lists a junction once per pass on an out-and-back, at increasing miles', () => {
    // Up Seven Hills and back down to Pine Meadow's far side: node 1 is
    // walked through twice, and each pass is a real chance to get off.
    const resolved = resolveDayHike(
      index,
      hikeOf([[end(-74.095, 41.25), end(-74.09, 41.255), end(-74.085, 41.25)]]),
    )
    const bailOuts = dayHikeBailOuts(index, resolved!)

    expect(bailOuts).toHaveLength(2)
    expect(bailOuts[0].name).toBe('Seven Hills Trail')
    expect(bailOuts[1].name).toBe('Seven Hills Trail')
    expect(bailOuts[1].miles).toBeGreaterThan(bailOuts[0].miles)
    // Pass one: 418 m of Pine Meadow. Pass two: that, plus 556 m up and 556 m
    // back down Seven Hills - the doubled climb a deduplicated edge list
    // would have counted once.
    expect(bailOuts[0].miles).toBeCloseTo(0.26, 2)
    expect(bailOuts[1].miles).toBeCloseTo(0.95, 2)
  })

  it('walks the closing leg of a loop too', () => {
    const resolved = resolveDayHike(
      index,
      hikeOf([[end(-74.095, 41.25), end(-74.085, 41.25)]], true),
    )
    const bailOuts = dayHikeBailOuts(index, resolved!)

    // Out through the junction, and back through it on the closing leg.
    expect(bailOuts).toHaveLength(2)
    expect(bailOuts[1].miles).toBeGreaterThan(bailOuts[0].miles)
  })
})
