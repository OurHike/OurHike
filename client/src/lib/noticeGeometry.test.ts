import { describe, expect, it } from 'vitest'
import {
  geometryParts,
  inPolygon,
  insideByMoreThan,
  linesMeetGeometry,
  MAX_COLLECTION_DEPTH,
  positionMeetsParts,
  type Position,
} from './noticeGeometry'

// The one question lib/plannedNotices.ts and lib/hazardAreas.ts both ask:
// does a line a hiker walks meet a place a notice names. At lat 41, a degree
// of longitude is about 84 km, so 0.001 degrees is about 275 ft.

const SQUARE = {
  type: 'Polygon',
  coordinates: [
    [
      [-74.01, 41.0],
      [-74.0, 41.0],
      [-74.0, 41.01],
      [-74.01, 41.01],
      [-74.01, 41.0],
    ],
  ],
}

const north: Position[] = [
  [-74.005, 40.99],
  [-74.005, 41.02],
]

describe('linesMeetGeometry', () => {
  it('meets a polygon a line crosses with no vertex inside it', () => {
    expect(linesMeetGeometry([north], SQUARE, 0)).toBe(true)
  })

  it('meets a polygon a line starts inside', () => {
    expect(
      linesMeetGeometry(
        [
          [
            [-74.005, 41.005],
            [-74.2, 41.2],
          ],
        ],
        SQUARE,
        0,
      ),
    ).toBe(true)
  })

  it('does not meet a polygon it passes outside the reach of', () => {
    const east: Position[] = [
      [-73.99, 40.99],
      [-73.99, 41.02],
    ]
    // 0.01 degrees east of the square's edge is about half a mile.
    expect(linesMeetGeometry([east], SQUARE, 300)).toBe(false)
  })

  it('meets a polygon it passes just outside, within the reach', () => {
    const beside: Position[] = [
      [-73.9997, 40.99],
      [-73.9997, 41.02],
    ]
    // About 82 ft from the edge.
    expect(linesMeetGeometry([beside], SQUARE, 0)).toBe(false)
    expect(linesMeetGeometry([beside], SQUARE, 300)).toBe(true)
  })

  it('does not meet a polygon through its hole', () => {
    const ring = {
      type: 'Polygon',
      coordinates: [
        SQUARE.coordinates[0],
        [
          [-74.008, 41.002],
          [-74.002, 41.002],
          [-74.002, 41.008],
          [-74.008, 41.008],
          [-74.008, 41.002],
        ],
      ],
    }
    const insideTheHole: Position[] = [
      [-74.005, 41.004],
      [-74.005, 41.006],
    ]
    expect(linesMeetGeometry([insideTheHole], ring, 0)).toBe(false)
  })

  it('meets a point within the reach and not one past it', () => {
    const point = { type: 'Point', coordinates: [-74.0045, 41.005] }
    // 0.0005 degrees is about 137 ft.
    expect(linesMeetGeometry([north], point, 300)).toBe(true)
    expect(linesMeetGeometry([north], point, 100)).toBe(false)
  })

  it('meets a line that crosses it', () => {
    const across = {
      type: 'LineString',
      coordinates: [
        [-74.1, 41.0],
        [-73.9, 41.0],
      ],
    }
    expect(linesMeetGeometry([north], across, 0)).toBe(true)
  })

  it('reads a multi-part shape part by part', () => {
    const far = {
      type: 'Polygon',
      coordinates: [
        [
          [-80, 30],
          [-79.9, 30],
          [-79.9, 30.1],
          [-80, 30],
        ],
      ],
    }
    const multi = {
      type: 'MultiPolygon',
      coordinates: [far.coordinates, SQUARE.coordinates],
    }
    expect(linesMeetGeometry([north], multi, 0)).toBe(true)
  })

  it('meets nothing for a shape it cannot read', () => {
    expect(
      linesMeetGeometry([north], { type: 'Circle', coordinates: [1, 2] }, 1000),
    ).toBe(false)
    expect(
      linesMeetGeometry([north], { type: 'Polygon', coordinates: 'nope' }, 1000),
    ).toBe(false)
    expect(linesMeetGeometry([north], null, 1000)).toBe(false)
  })
})

describe('geometryParts of nested GeometryCollections', () => {
  /** A point wrapped in `depth` GeometryCollections. */
  function nested(depth: number): unknown {
    let geometry: unknown = { type: 'Point', coordinates: [-74.005, 41.005] }
    for (let i = 0; i < depth; i += 1) {
      geometry = { type: 'GeometryCollection', geometries: [geometry] }
    }
    return geometry
  }

  it('reads a point inside a collection inside a collection', () => {
    expect(geometryParts(nested(2) as never).points).toEqual([[-74.005, 41.005]])
  })

  it('reads a collection nested 20,000 deep as no parts, rather than overflowing the stack', () => {
    const deep = nested(20_000) as never
    expect(() => geometryParts(deep)).not.toThrow()
    expect(geometryParts(deep)).toEqual({ points: [], lines: [], polygons: [] })
    expect(linesMeetGeometry([north], deep, 1000)).toBe(false)
  })

  it('reads a collection nested past MAX_COLLECTION_DEPTH as no parts, whatever its shallower members hold', () => {
    const past = {
      type: 'GeometryCollection',
      geometries: [SQUARE, nested(MAX_COLLECTION_DEPTH)],
    }
    expect(geometryParts(past as never)).toEqual({ points: [], lines: [], polygons: [] })
    expect(geometryParts(nested(MAX_COLLECTION_DEPTH) as never).points).toHaveLength(1)
  })
})

describe('positionMeetsParts', () => {
  it('says a tapped place is inside an area', () => {
    const parts = geometryParts(SQUARE)
    expect(positionMeetsParts([-74.005, 41.005], parts, 0)).toBe(true)
    expect(positionMeetsParts([-74.05, 41.005], parts, 300)).toBe(false)
  })
})

describe('inPolygon', () => {
  it('holds the shell and not the outside', () => {
    const polygon = geometryParts(SQUARE).polygons[0]
    expect(inPolygon([-74.005, 41.005], polygon)).toBe(true)
    expect(inPolygon([-74.02, 41.005], polygon)).toBe(false)
  })
})

describe('insideByMoreThan', () => {
  // SQUARE is 0.01 degrees a side: about 840 m east to west and 1,105 m north
  // to south at 41 N, so its middle is about 420 m from its nearest edge.
  const parts = geometryParts(SQUARE)

  it('holds a place deep inside, and not one within the margin of an edge', () => {
    expect(insideByMoreThan([-74.005, 41.005], parts, 300)).toBe(true)
    expect(insideByMoreThan([-74.005, 41.005], parts, 500)).toBe(false)
    // 0.001 degrees inside the east edge: about 84 m.
    expect(insideByMoreThan([-74.001, 41.005], parts, 50)).toBe(true)
    expect(insideByMoreThan([-74.001, 41.005], parts, 100)).toBe(false)
  })

  it('never holds a place outside the shape, however far from its edge', () => {
    expect(insideByMoreThan([-74.5, 41.005], parts, 0)).toBe(false)
  })

  it('measures a hole’s edge too, and holds nothing inside the hole', () => {
    const holed = geometryParts({
      type: 'Polygon',
      coordinates: [
        SQUARE.coordinates[0],
        [
          [-74.006, 41.004],
          [-74.004, 41.004],
          [-74.004, 41.006],
          [-74.006, 41.006],
          [-74.006, 41.004],
        ],
      ],
    })
    expect(insideByMoreThan([-74.005, 41.005], holed, 0)).toBe(false)
    // Between the hole and the west edge: about 252 m from the shell, 84 m from the hole.
    expect(insideByMoreThan([-74.007, 41.005], holed, 50)).toBe(true)
    expect(insideByMoreThan([-74.007, 41.005], holed, 100)).toBe(false)
  })
})
