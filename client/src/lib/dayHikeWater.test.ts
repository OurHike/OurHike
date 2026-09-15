import { describe, expect, it } from 'vitest'

import { WATER_ON_ROUTE_FEET, waterOnCourse } from './dayHikeWater'
import { buildCourse, type DayHikeCourse } from './dayHikeCourse'
import { resolveDayHike } from './dayHikeCard'
import { followDayHike } from './dayHikeFollow'
import type { DayHike } from './dayHikes'
import { buildGraphIndex, metresToMiles, type TrailGraph } from './trailGraph'
import type { StoredPoi } from './trailData'

// Step 3's "Water on route" (#1373): the published water points along the
// walk, on the walk's own mile axis, and nothing at all where there are
// none - the header of lib/dayHikeWater.ts says why an empty list must not
// become "no water".

// A straight east-west walk along 41.25°N, two miles long: ~0.01° of
// longitude is ~0.52 mi here, so the vertices below sit half a mile apart.
const COURSE: DayHikeCourse = {
  points: [
    { lon: -74.1, lat: 41.25, mile: 0 },
    { lon: -74.09, lat: 41.25, mile: 0.52 },
    { lon: -74.08, lat: 41.25, mile: 1.04 },
    { lon: -74.07, lat: 41.25, mile: 1.56 },
    { lon: -74.06, lat: 41.25, mile: 2.08 },
  ],
  stretchStarts: [0],
  miles: 2.08,
}

const poi = (id: string, type: string, lon: number, lat: number): StoredPoi => ({
  id,
  type,
  name: `${type} ${id}`,
  lat,
  lon,
  confidence: 'high',
})

describe('waterOnCourse', () => {
  it('lists water on the line at the mile the walk reaches it, in walk order', () => {
    const rows = waterOnCourse(COURSE, [
      poi('far', 'water', -74.07, 41.2501),
      poi('near', 'water', -74.09, 41.25),
      poi('shelter', 'shelter', -74.08, 41.25),
    ])

    expect(rows.map((row) => row.poiId)).toEqual(['near', 'far'])
    expect(rows[0].alongMi).toBeCloseTo(0.52, 5)
    expect(rows[0].offCourseFeet).toBeLessThan(1)
    expect(rows[1].alongMi).toBeCloseTo(1.56, 5)
  })

  it('leaves out water past the threshold, and says how far off the walk the rest sit', () => {
    // 0.002° of latitude is ~730 ft - past the 500 ft this build calls on
    // the route; 0.001° is ~365 ft, inside it and worth saying.
    const rows = waterOnCourse(COURSE, [
      poi('off', 'water', -74.09, 41.252),
      poi('beside', 'water', -74.08, 41.251),
    ])

    expect(rows.map((row) => row.poiId)).toEqual(['beside'])
    expect(rows[0].offCourseFeet).toBeGreaterThan(300)
    expect(rows[0].offCourseFeet).toBeLessThan(WATER_ON_ROUTE_FEET)
  })

  it('lists a point once per pass of the walk, so an out-and-back has it going and coming', () => {
    // The same line walked out and back: the return leg is the outbound
    // vertices reversed, with the mile still climbing.
    const outAndBack: DayHikeCourse = {
      points: [
        ...COURSE.points,
        ...[...COURSE.points]
          .reverse()
          .slice(1)
          .map((point, index) => ({
            ...point,
            mile: 2.08 + 0.52 * (index + 1),
          })),
      ],
      stretchStarts: [0],
      miles: 4.16,
    }

    const rows = waterOnCourse(outAndBack, [poi('spring', 'water', -74.09, 41.25)])

    // Going, 0.52 mi in; coming back, 0.52 mi from the end. The first
    // version of this listed the outbound pass only, so a hiker past the
    // turnaround was shown no water ahead at all.
    expect(rows.map((row) => row.alongMi)).toEqual([0.52, 3.64])
    expect(rows.every((row) => row.poiId === 'spring')).toBe(true)
  })

  it('lists a point at the turnaround once - one visit, not two', () => {
    const outAndBack: DayHikeCourse = {
      points: [
        ...COURSE.points,
        ...[...COURSE.points]
          .reverse()
          .slice(1)
          .map((point, index) => ({
            ...point,
            mile: 2.08 + 0.52 * (index + 1),
          })),
      ],
      stretchStarts: [0],
      miles: 4.16,
    }

    const rows = waterOnCourse(outAndBack, [poi('end', 'water', -74.06, 41.25)])

    expect(rows.map((row) => row.alongMi)).toEqual([2.08])
  })

  it('is empty - never a sentence - with no water and with no walk', () => {
    expect(waterOnCourse(COURSE, [poi('s', 'shelter', -74.09, 41.25)])).toEqual([])
    expect(
      waterOnCourse({ points: [], stretchStarts: [], miles: 0 }, [
        poi('w', 'water', -74.09, 41.25),
      ]),
    ).toEqual([])
  })
})

// ONE MILE AXIS UNDER "WHAT'S LEFT TODAY" (#1379)
//
// The next-turn card lists the water a hiker has still to pass as
// `water.alongMi - followState.walkedMi`, and decides what is still ahead on
// `alongMi > walkedMi`. Those two numbers are produced by two modules:
// `alongMi` by lib/dayHikeWater.ts off a course built here, `walkedMi` by
// lib/dayHikeFollow.ts off the pipeline's `length_m`. If they ever measure
// the walk differently, a spring a hiker is standing beside flips from ahead
// to behind on the difference between two ways of measuring one line - which
// is "out of water", one of CLAUDE.md's four ways this app can hurt somebody.
//
// The graph below makes the question impossible to pass by accident.
// `length_m` is 1,200 m on a line whose drawn vertices are about 837 m apart
// at this latitude - a 43% divergence, where the real one (EPSG:5070 against
// WGS84) is 0.8%. A course that re-measured the drawn vertices would put the
// spring at mile 0.52 instead of 0.75 and the answer would be wrong by a
// third of a mile rather than by tens of metres.
//
// The code half of this landed in `49af4767` ("Put the day-hike builder's
// stops and legs back on one mile axis", PR #1351, merged 2026-09-09 22:43
// UTC) - `buildCourse` scales each drawn edge onto its published metres. What
// did not land with it is an assertion that the FOLLOW card's subtraction
// agrees, which is the seam #1379 named and the one this test pins.

describe('the follow card s water rows, against a hand-built graph', () => {
  // Two 1,200 m edges due east along 41.25°N, published lengths deliberately
  // unlike the drawn ones. Nodes at -74.10, -74.09 and -74.08.
  const STRETCHED: TrailGraph = {
    nodes: [
      [-74.1, 41.25],
      [-74.09, 41.25],
      [-74.08, 41.25],
    ],
    edges: [
      {
        from: 0,
        to: 1,
        length_m: 1200,
        trail_id: 'fixture:1',
        source: 'fixture',
        name: 'Long Measure Trail',
        blaze_color: 'Blue',
        geometry: [
          [-74.1, 41.25],
          [-74.09, 41.25],
        ],
      },
      {
        from: 1,
        to: 2,
        length_m: 1200,
        trail_id: 'fixture:1',
        source: 'fixture',
        name: 'Long Measure Trail',
        blaze_color: 'Blue',
        geometry: [
          [-74.09, 41.25],
          [-74.08, 41.25],
        ],
      },
    ],
  }

  const index = buildGraphIndex(STRETCHED)

  function walkTheWhole() {
    const hike: DayHike = {
      id: 'fixture-hike',
      name: 'Fixture walk',
      date: null,
      segments: [
        [
          { coord: [-74.1, 41.25], poiId: null },
          { coord: [-74.08, 41.25], poiId: null },
        ],
      ],
      figures: { miles: 0, legs: [] },
      looped: false,
      recorded: 'planned',
      note: '',
    }
    const resolved = resolveDayHike(index, hike)
    expect(resolved).not.toBeNull()
    return resolved!
  }

  it('measures the spring s mile on the published metres, not the drawn ones', () => {
    const resolved = walkTheWhole()
    const course = buildCourse(STRETCHED, resolved.segments)
    const rows = waterOnCourse(course, [poi('spring', 'water', -74.09, 41.25)])

    expect(rows).toHaveLength(1)
    // 1,200 m, not the ~837 m the vertices are apart.
    expect(rows[0].alongMi).toBeCloseTo(metresToMiles(1200), 6)
    expect(course.miles).toBeCloseTo(metresToMiles(2400), 6)
  })

  it('subtracts two miles of the same kind, so what is left is a real distance', () => {
    const resolved = walkTheWhole()
    const course = buildCourse(STRETCHED, resolved.segments)
    const rows = waterOnCourse(course, [poi('spring', 'water', -74.09, 41.25)])

    // Halfway along the first edge: 600 published metres in.
    const follow = followDayHike({
      index,
      resolved,
      at: { lon: -74.095, lat: 41.25 },
    })
    expect(follow?.kind).toBe('on-route')
    if (follow?.kind !== 'on-route') return
    expect(follow.walkedMi).toBeCloseTo(metresToMiles(600), 6)

    // The subtraction App.tsx performs for the "what's left today" rows.
    const milesAway = rows[0].alongMi - follow.walkedMi
    expect(milesAway).toBeCloseTo(metresToMiles(600), 6)
  })

  it('keeps a spring underfoot on the side of the filter the hiker is on', () => {
    // The `>` in App.tsx is decided on the same two numbers. A hiker standing
    // AT the spring has passed it; a hiker a step short of it has not, and
    // the two answers must not depend on which module did the measuring.
    const resolved = walkTheWhole()
    const course = buildCourse(STRETCHED, resolved.segments)
    const rows = waterOnCourse(course, [poi('spring', 'water', -74.09, 41.25)])

    const atTheSpring = followDayHike({ index, resolved, at: { lon: -74.09, lat: 41.25 } })
    expect(atTheSpring?.kind).toBe('on-route')
    if (atTheSpring?.kind !== 'on-route') return
    expect(rows[0].alongMi > atTheSpring.walkedMi).toBe(false)

    const shortOfIt = followDayHike({ index, resolved, at: { lon: -74.0905, lat: 41.25 } })
    expect(shortOfIt?.kind).toBe('on-route')
    if (shortOfIt?.kind !== 'on-route') return
    expect(rows[0].alongMi > shortOfIt.walkedMi).toBe(true)
  })
})
