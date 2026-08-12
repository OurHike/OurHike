import { describe, it, expect } from 'vitest'
import { computeLegendContents, type MapPoint } from './legendContents'

// WIREFRAMES.md's Legend section: lists only what's in the current
// viewport, with counts. Rows are tappable to hide - except the closure row
// and the serious-warning row, which carry an "Always shown" tag and no
// hide affordance (TESTING.md item 7).

const BBOX = { west: -84, south: 35, east: -83, north: 36 }

function point(overrides: Partial<MapPoint>): MapPoint {
  return {
    id: 'p',
    type: 'water',
    lat: 35.5,
    lon: -83.5,
    confidence: 'high',
    ...overrides,
  }
}

describe('computeLegendContents', () => {
  it('includes only points within the viewport bounding box', () => {
    const inside = point({ id: 'inside', lat: 35.5, lon: -83.5 })
    const outside = point({ id: 'outside', lat: 40, lon: -70 })

    const rows = computeLegendContents(BBOX, [inside, outside])

    const waterRow = rows.find((r) => r.type === 'water')
    expect(waterRow?.count).toBe(1)
  })

  it('counts exactly match what the viewport contains - not a stale/cached count', () => {
    const points = [
      point({ type: 'shelter' }),
      point({ type: 'shelter' }),
      point({ type: 'water' }),
    ]

    const rows = computeLegendContents(BBOX, points)

    expect(rows.find((r) => r.type === 'shelter')?.count).toBe(2)
    expect(rows.find((r) => r.type === 'water')?.count).toBe(1)
  })

  it('recomputes correctly for a different viewport (simulating pan/zoom) - no leftover state from a prior call', () => {
    const points = [
      point({ id: 'a', lat: 35.5, lon: -83.5 }),
      point({ id: 'b', lat: 45, lon: -70 }),
    ]

    const before = computeLegendContents(BBOX, points)
    const after = computeLegendContents(
      { west: -71, south: 44, east: -69, north: 46 },
      points,
    )

    expect(before.find((r) => r.type === 'water')?.count).toBe(1)
    expect(after.find((r) => r.type === 'water')?.count).toBe(1)
  })

  it('counts verified and unverified points of a type as one row, not two', () => {
    // This used to split, giving "Water 1" and "Water · Unverified 1". Two
    // rows per category doubled a panel about 116px wide per column and spent
    // the room on a distinction nobody can act on from a viewport count. The
    // map still draws the broken rim per pin, and PoiCard still says it in
    // words on the waypoint somebody is deciding about.
    const points = [
      point({ id: 'a', confidence: 'high' }),
      point({ id: 'b', confidence: 'low' }),
    ]

    const rows = computeLegendContents(BBOX, points)

    expect(rows.filter((r) => r.type === 'water')).toHaveLength(1)
    expect(rows.find((r) => r.type === 'water')?.count).toBe(2)
  })

  it('marks the closure row as not hideable, always shown', () => {
    const rows = computeLegendContents(BBOX, [point({ type: 'closure' })])

    const closureRow = rows.find((r) => r.type === 'closure')
    expect(closureRow?.hideable).toBe(false)
  })

  it('marks the serious-warning row as not hideable, always shown', () => {
    const rows = computeLegendContents(BBOX, [point({ type: 'serious-warning' })])

    const warningRow = rows.find((r) => r.type === 'serious-warning')
    expect(warningRow?.hideable).toBe(false)
  })

  it('marks every other row type as hideable', () => {
    const rows = computeLegendContents(BBOX, [
      point({ type: 'water' }),
      point({ type: 'shelter' }),
    ])

    expect(rows.every((r) => r.hideable)).toBe(true)
  })

  it('omits a row entirely for a type with zero points in the viewport', () => {
    const rows = computeLegendContents(BBOX, [point({ type: 'water' })])

    expect(rows.find((r) => r.type === 'shelter')).toBeUndefined()
  })
})

describe('the "Verified?" filter', () => {
  it('leaves the counts alone while it is off', () => {
    const points = [point({ id: 'a' }), point({ id: 'b', confidence: 'low' })]

    expect(computeLegendContents(BBOX, points, false)[0].count).toBe(2)
  })

  it('stops counting unverified points while it is on', () => {
    // The count has to move with the filter. The panel's whole promise is that
    // it says what is on screen right now, so "Water 2" over a map drawing one
    // is the exact lie it exists to prevent.
    const points = [point({ id: 'a' }), point({ id: 'b', confidence: 'low' })]

    const rows = computeLegendContents(BBOX, points, true)

    expect(rows.find((r) => r.type === 'water')?.count).toBe(1)
  })

  it('drops a row whose every point is unverified', () => {
    const rows = computeLegendContents(BBOX, [point({ confidence: 'low' })], true)

    expect(rows).toHaveLength(0)
  })

  it.each(['closure', 'serious-warning'])(
    'never filters a %s, however unverified it is',
    (type) => {
      // "No off switch for a safety layer" has to mean every switch. A filter
      // that happens to take a closure off the panel is the same failure as a
      // button that does, and easier to ship without noticing.
      const rows = computeLegendContents(BBOX, [point({ type, confidence: 'low' })], true)

      expect(rows.find((r) => r.type === type)?.count).toBe(1)
    },
  )
})
