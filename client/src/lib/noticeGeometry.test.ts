import { describe, expect, it } from 'vitest'
import {
  geometryParts,
  inPolygon,
  linesMeetGeometry,
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
