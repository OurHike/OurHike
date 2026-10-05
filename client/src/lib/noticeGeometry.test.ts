import { describe, expect, it } from 'vitest'
import {
  geometryParts,
  inPolygon,
  linesMeetParts,
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

describe('linesMeetParts on a state-sized area of many polygons', () => {
  // The shape of Utah FFSL's fire-restriction order 19 after decision 77's
  // shaping (899 polygons and 53,358 vertices, measured 2026-10-05 by running
  // the macro's SQL over soak run 536's row in DuckDB): invented here as 899
  // 60-gons, 53,940 vertices, on a 30 x 30 grid over a box the size of Utah,
  // with one grid square left empty for a hike to walk through.
  function stateOfPolygons(): ReturnType<typeof geometryParts> {
    const polygons: number[][][][] = []
    for (let r = 0; r < 30; r += 1) {
      for (let c = 0; c < 30; c += 1) {
        if ((r === 15 && c === 15) || polygons.length === 899) continue
        const cx = -114 + (c + 0.5) / 6
        const cy = 37 + (r + 0.5) / 6
        const ring: number[][] = []
        for (let k = 0; k < 59; k += 1) {
          const a = (2 * Math.PI * k) / 59
          ring.push([cx + 0.05 * Math.cos(a), cy + 0.05 * Math.sin(a)])
        }
        ring.push(ring[0])
        polygons.push([ring])
      }
    }
    return geometryParts({ type: 'MultiPolygon', coordinates: polygons })
  }
  /** About 7 miles due north through the empty square, 400 vertices. */
  const throughTheGap: Position[] = Array.from({ length: 400 }, (_, i) => [
    -114 + 15.5 / 6,
    37 + 15.05 / 6 + (0.1 * i) / 399,
  ])

  it('answers a hike that misses every polygon in under 250 ms, where measuring every edge took 2.3 s', () => {
    // Before the box test, every one of the 400 pieces was measured against
    // every one of the 53,940 edges: 2,294 ms in this sandbox's vitest on
    // 2026-10-05, and the whole case 33 to 56 ms after, under coverage or
    // not. The bound is loose on purpose, for a slower CI runner.
    const parts = stateOfPolygons()
    expect(parts.polygons).toHaveLength(899)
    const started = performance.now()
    expect(linesMeetParts([throughTheGap], parts, 300)).toBe(false)
    expect(performance.now() - started).toBeLessThan(250)
  })

  it('still meets the one polygon a hike passes within reach of, among 899', () => {
    const parts = stateOfPolygons()
    // The square west of the gap has its 60-gon's east edge 0.05 degrees
    // short of the square's own east side: move the hike to 50 ft east of it.
    const westEdge = -114 + 14.5 / 6 + 0.05
    const feet50 = 50 / 3.28084 / (111_320 * Math.cos(((37 + 15.5 / 6) * Math.PI) / 180))
    const beside = throughTheGap.map(([, lat]): Position => [westEdge + feet50, lat])
    expect(linesMeetParts([beside], parts, 300)).toBe(true)
    expect(linesMeetParts([beside], parts, 10)).toBe(false)
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
