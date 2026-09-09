// Which of a day hike's miles are on a long hike's trail (#1317).

import { describe, expect, it } from 'vitest'

import { dayHikeOnTrail, overlaps } from './dayHikeOnTrail'
import type { DayHike } from './dayHikes'
import { buildTrailIndex } from './trailPosition'

/** A short north-south centerline, in the shape the real trails.geojson
 *  uses - a LineString feature carrying `source: 'centerline'`. */
const INDEX = buildTrailIndex({
  type: 'FeatureCollection',
  features: [
    {
      type: 'Feature',
      properties: { source: 'centerline' },
      geometry: {
        type: 'LineString',
        coordinates: [
          [-74.0, 41.0],
          [-74.0, 41.01],
          [-74.0, 41.02],
          [-74.0, 41.03],
        ],
      },
    },
  ],
})

function dayHike(coords: [number, number][]): DayHike {
  return {
    id: 'd1',
    name: 'A walk',
    date: null,
    segments: [coords.map((coord) => ({ coord, poiId: null }))],
    figures: { miles: 4, legs: [] },
    looped: false,
    recorded: 'planned',
  } as unknown as DayHike
}

describe('a day hike’s miles on the trail', () => {
  it('reports the stretch a walk along the trail covers', () => {
    const stretch = dayHikeOnTrail(
      dayHike([
        [-74.0, 41.005],
        [-74.0, 41.025],
      ]),
      INDEX,
    )

    expect(stretch).not.toBeNull()
    expect(stretch!.toMile).toBeGreaterThan(stretch!.fromMile)
  })

  it('reports nothing for a walk nowhere near the corridor', () => {
    // mileOnTrail already refuses a point past MAX_OFF_TRAIL_MILES, so a
    // park two states away resolves to nothing rather than to a mile
    // measured across the map.
    expect(dayHikeOnTrail(dayHike([[-80.0, 35.0]]), INDEX)).toBeNull()
  })

  it('counts a walk that only touched the trail on its way past', () => {
    // A day hike routinely uses side trails and a spur to a car park. The
    // question is how much of it is on the trail, never whether all of it is.
    const stretch = dayHikeOnTrail(
      dayHike([
        [-80.0, 35.0],
        [-74.0, 41.015],
        [-80.0, 35.0],
      ]),
      INDEX,
    )
    expect(stretch).not.toBeNull()
  })

  it('counts touching a hike’s end as overlapping it', () => {
    // A day hike that started at the shelter a section ended at is on this
    // hike's trail.
    expect(overlaps({ fromMile: 10, toMile: 20 }, { from: 20, to: 30 })).toBe(true)
    expect(overlaps({ fromMile: 10, toMile: 19.9 }, { from: 20, to: 30 })).toBe(false)
  })
})
