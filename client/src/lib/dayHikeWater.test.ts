import { describe, expect, it } from 'vitest'

import { WATER_ON_ROUTE_FEET, waterOnCourse } from './dayHikeWater'
import type { DayHikeCourse } from './dayHikeCourse'
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
