// Tests for lib/dayHikeStops.ts - shelters and campsites as route stops
// (#1194).
//
// The rules worth pinning are the ones that keep a stop from becoming a
// claim the app cannot back:
//
//   ORDER IS DERIVED, NEVER STORED. A stop's place in the list is where the
//   walk reaches it, recomputed on every change - so a stop cannot end up
//   listed between two legs it does not sit between.
//
//   A STOP OFF THE LINE IS ACCEPTED AND SAID, not refused. Most real shelters
//   are off the centerline by design (up a spur, at the water), so a distance
//   guard would refuse the normal case.
//
//   THE DETOUR IS NEVER PRICED. The app knows how far off the walk a shelter
//   is and knows nothing about the ground between - so `stoppingMinutes`
//   counts stops and never distance.

import { describe, expect, it } from 'vitest'

import { buildCourse, type DayHikeCourse } from './dayHikeCourse'
import { draftStatus, tapAt, EMPTY_DRAFT } from './dayHikeDraft'
import {
  isStoppable,
  orderStops,
  STOP_MINUTES,
  stoppingMinutes,
  toggleStop,
} from './dayHikeStops'
import { buildGraphIndex, type TrailGraph } from './trailGraph'
import type { StoredPoi } from './trailData'

//   0 --- 836 m --- 1 --- 836 m --- 2   Pine Meadow Trail, west to east
const GRAPH: TrailGraph = {
  nodes: [
    [-74.1, 41.25],
    [-74.09, 41.25],
    [-74.08, 41.25],
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
      geometry: [
        [-74.1, 41.25],
        [-74.09, 41.25],
      ],
    },
    {
      from: 1,
      to: 2,
      length_m: 836,
      trail_id: 'oprhp_trails:1',
      source: 'oprhp_trails',
      name: 'Pine Meadow Trail',
      blaze_color: 'blue',
      geometry: [
        [-74.09, 41.25],
        [-74.08, 41.25],
      ],
    },
  ],
}

const index = buildGraphIndex(GRAPH)

function poi(id: string, type: string, lon: number, lat: number): StoredPoi {
  return { id, type, name: `${id} place`, lat, lon, confidence: 'high' }
}

/** Near the far (east) end, and near the near (west) end. */
const EAST_SHELTER = poi('east', 'shelter', -74.081, 41.2502)
const WEST_CAMP = poi('west', 'campsite', -74.099, 41.2502)
/** A long way north of the walk - a real shelter up a long spur. */
const FAR_SHELTER = poi('far', 'shelter', -74.09, 41.256)
const POIS = [EAST_SHELTER, WEST_CAMP, FAR_SHELTER]

function course(): DayHikeCourse {
  const draft = tapAt(index, tapAt(index, EMPTY_DRAFT, { lon: -74.1, lat: 41.25 }), {
    lon: -74.08,
    lat: 41.25,
  })
  const status = draftStatus(index, draft)
  if (status.kind !== 'routed') throw new Error('fixture should route')
  return buildCourse(GRAPH, status.stretches)
}

describe('which waypoints can be stopped at', () => {
  it('takes shelters and campsites', () => {
    expect(isStoppable({ type: 'shelter' })).toBe(true)
    expect(isStoppable({ type: 'campsite' })).toBe(true)
  })

  it('refuses everything else - a privy is not a stop', () => {
    for (const type of ['water', 'privy', 'parking', 'viewpoint', 'crossing']) {
      expect(isStoppable({ type })).toBe(false)
    }
  })
})

describe('ordering stops along the walk', () => {
  it('lists them in the order the walk reaches them, not the order picked', () => {
    // Chosen east-first; the walk runs west to east, so west must list first.
    const stops = orderStops(course(), new Set(['east', 'west']), POIS)

    expect(stops.map((stop) => stop.poiId)).toEqual(['west', 'east'])
    expect(stops[0].mile).toBeLessThan(stops[1].mile)
  })

  it('re-orders when the walk does, because order is derived', () => {
    // The same two stops against a walk built the other way round.
    const draft = tapAt(index, tapAt(index, EMPTY_DRAFT, { lon: -74.08, lat: 41.25 }), {
      lon: -74.1,
      lat: 41.25,
    })
    const status = draftStatus(index, draft)
    if (status.kind !== 'routed') throw new Error('fixture should route')

    const stops = orderStops(
      buildCourse(GRAPH, status.stretches),
      new Set(['east', 'west']),
      POIS,
    )

    expect(stops.map((stop) => stop.poiId)).toEqual(['east', 'west'])
  })

  it('accepts a stop well off the line and says how far', () => {
    // The guard that is deliberately absent: most shelters sit off the
    // centerline, so a distance refusal would refuse the normal case.
    const stops = orderStops(course(), new Set(['far']), POIS)

    expect(stops).toHaveLength(1)
    expect(stops[0].offCourseFeet).toBeGreaterThan(1000)
  })

  it('is empty while the walk has no course to measure against', () => {
    const empty = buildCourse(GRAPH, [])

    expect(orderStops(empty, new Set(['east']), POIS)).toEqual([])
  })

  it('ignores a chosen id no waypoint answers to', () => {
    expect(orderStops(course(), new Set(['nobody']), POIS)).toEqual([])
  })
})

describe('toggling', () => {
  it('adds one that is not there and removes one that is', () => {
    const once = toggleStop(new Set<string>(), 'east')
    expect([...once]).toEqual(['east'])

    expect([...toggleStop(once, 'east')]).toEqual([])
  })

  it('does not mutate the set it was given', () => {
    const before = new Set(['east'])
    toggleStop(before, 'west')

    expect([...before]).toEqual(['east'])
  })
})

describe('the stopping time', () => {
  it('counts stops and never distance', () => {
    const stops = orderStops(course(), new Set(['east', 'west']), POIS)

    expect(stoppingMinutes(stops)).toBe(2 * STOP_MINUTES)
  })

  it('prices a stop a long way off the walk the same as one beside it', () => {
    // THE RULE: the detour is shown, never priced. The app has no evidence
    // about the ground out to a shelter, so minutes for it would be invented.
    const near = orderStops(course(), new Set(['east']), POIS)
    const far = orderStops(course(), new Set(['far']), POIS)

    expect(stoppingMinutes(far)).toBe(stoppingMinutes(near))
  })

  it('is null rather than zero for a walk with no stops', () => {
    // Absent and "zero minutes" say different things, and only one is true.
    expect(stoppingMinutes([])).toBeNull()
  })
})
