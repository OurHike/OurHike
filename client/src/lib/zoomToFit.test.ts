import { describe, it, expect } from 'vitest'
import {
  MAX_FIT_STEP,
  MAX_FIT_ZOOM,
  POI_COLLISION_PX,
  collisionMetres,
  zoomToFit,
} from './zoomToFit'
import type { MapPoint } from './legendContents'

// The zoom that would actually fit the pins being dropped (#528). Saying "38 of
// 112 fit" and leaving the hiker to find that zoom by pinching is half a
// feature; the number is computable.
//
// The alternative - fanning the hidden pins out - is refused by
// features/POI_SITES.md because it draws every displaced pin at a position it is
// not at. Moving the camera reaches the same pins where they really are.

const DEGREE_PER_METRE = 1 / 111_320

function at(id: string, northOfMetres: number, lat = 40, lon = -74): MapPoint {
  return {
    id,
    type: 'water',
    lat: lat + northOfMetres * DEGREE_PER_METRE,
    lon,
    confidence: 'high',
  }
}

describe('collisionMetres', () => {
  it('matches the design doc’s own measured table', () => {
    // features/POI_SITES.md, latitude 40: z12 615 m, z14 154 m, z16 38 m. If
    // this drifts, the zoom computed below fits nothing and the button lies.
    expect(collisionMetres(12, 40)).toBeCloseTo(615, -1)
    expect(collisionMetres(14, 40)).toBeCloseTo(154, -1)
    expect(collisionMetres(16, 40)).toBeCloseTo(38, -1)
  })

  it('halves for every zoom level in', () => {
    expect(collisionMetres(15, 40)).toBeCloseTo(collisionMetres(14, 40) / 2, 5)
  })

  it('is the pin box, not one pixel', () => {
    expect(POI_COLLISION_PX).toBe(42)
  })
})

describe('zoomToFit', () => {
  it('offers nothing when nothing is crowded', () => {
    // Two waypoints a kilometre apart at z14 do not collide - 154 m is the
    // distance that matters - so there is nothing for a button to fix, and one
    // that would not move the camera is worse than none.
    expect(zoomToFit([at('a', 0), at('b', 1_000)], 14, 40)).toBeNull()
  })

  it('offers nothing for a single waypoint', () => {
    expect(zoomToFit([at('a', 0)], 9, 40)).toBeNull()
  })

  it('offers nothing at the ceiling', () => {
    expect(zoomToFit([at('a', 0), at('b', 5)], MAX_FIT_ZOOM, 40)).toBeNull()
  })

  it('returns a zoom at which the crowded pair really does fit', () => {
    // 100 m apart: collides at z14 (154 m) and not at z15 (77 m). The whole
    // claim of the control is that the zoom it picks separates them.
    const target = zoomToFit([at('a', 0), at('b', 100)], 14, 40)

    expect(target).not.toBeNull()
    expect(collisionMetres(target as number, 40)).toBeLessThan(100)
  })

  it('always moves at least one level', () => {
    const target = zoomToFit([at('a', 0), at('b', 150)], 14, 40)

    expect(target).toBeGreaterThan(14)
  })

  it('does not fling the camera across the state for one impossible pair', () => {
    // Two waypoints two metres apart would demand z22 on their own. The control
    // aims at the 25th percentile of the crowded pins instead, so one
    // pathological pair cannot take the viewport with it.
    const points = [
      at('a', 0),
      at('b', 2),
      at('c', 120),
      at('d', 240),
      at('e', 360),
      at('f', 480),
    ]

    const target = zoomToFit(points, 12, 40)

    expect(target).toBeLessThanOrEqual(12 + MAX_FIT_STEP)
  })

  it('never goes past the ceiling', () => {
    const target = zoomToFit([at('a', 0), at('b', 1), at('c', 2)], MAX_FIT_ZOOM - 1, 40)

    expect(target).toBeLessThanOrEqual(MAX_FIT_ZOOM)
  })

  it('still offers a step when no zoom could separate the pair', () => {
    // Identical coordinates - ATC records them, and no zoom ever separates them.
    // The honest behaviour is to go as far as one press sensibly goes rather
    // than to refuse: the counts recompute afterwards and say what still does
    // not fit.
    const target = zoomToFit([at('a', 0), at('b', 0)], 10, 40)

    expect(target).toBe(10 + MAX_FIT_STEP)
  })

  it('asks for more zoom the more crowded the viewport is', () => {
    const loose = zoomToFit([at('a', 0), at('b', 140), at('c', 280)], 14, 40)
    const tight = zoomToFit([at('a', 0), at('b', 20), at('c', 40)], 14, 40)

    expect(tight as number).toBeGreaterThan(loose as number)
  })

  it('accounts for latitude, since a pixel is fewer metres further north', () => {
    // Maine is 45 degrees and Georgia is 34. The same spacing is a different
    // number of pixels at each, and the trail spans both.
    const south = collisionMetres(14, 34)
    const north = collisionMetres(14, 45)

    expect(north).toBeLessThan(south)
  })
})
