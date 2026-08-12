import { describe, it, expect } from 'vitest'
import { computeLegendContents, legendDropSummary, type MapPoint } from './legendContents'

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

  it('splits low-confidence points into their own row, labeled Unverified, per WIREFRAMES.md copy', () => {
    const points = [
      point({ id: 'a', confidence: 'high' }),
      point({ id: 'b', confidence: 'low' }),
    ]

    const rows = computeLegendContents(BBOX, points)

    expect(rows.find((r) => r.type === 'water' && r.confidence === 'high')?.count).toBe(1)
    expect(rows.find((r) => r.type === 'water' && r.confidence === 'low')?.count).toBe(1)
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

// What is DRAWN, as against what is present (#528). The panel's promise is
// "what am I looking at right now", and since collision culling arrived it had
// been answering "what is inside this rectangle" - a row reading `Privy · 6` on
// a map with no privy pin, because 3% of privies place at z14.
describe('the drawn count', () => {
  const bbox = { west: -1, south: -1, east: 1, north: 1 }
  const at = (id: string, type: string, confidence: 'high' | 'low' = 'high') => ({
    id,
    type,
    lat: 0,
    lon: 0,
    confidence,
  })

  it('carries how many of each row the map actually drew', () => {
    const rows = computeLegendContents(
      bbox,
      [at('w1', 'water'), at('w2', 'water'), at('p1', 'privy')],
      new Map([
        ['water::high', 1],
        ['privy::high', 0],
      ]),
    )

    expect(rows).toEqual([
      { type: 'water', confidence: 'high', count: 2, hideable: true, drawnCount: 1 },
      { type: 'privy', confidence: 'high', count: 1, hideable: true, drawnCount: 0 },
    ])
  })

  it('is undefined, not zero, when nobody measured', () => {
    // The layer is absent on a cold start. "0 shown" then would claim a drop
    // that has not happened.
    const [row] = computeLegendContents(bbox, [at('w1', 'water')])

    expect(row.drawnCount).toBeUndefined()
  })

  it('is zero for a category the measurement did not mention', () => {
    // The whole map was measured, so a missing key is an answer rather than a
    // gap - this is exactly the privy row at a hiking zoom.
    const [row] = computeLegendContents(bbox, [at('p1', 'privy')], new Map())

    expect(row.drawnCount).toBe(0)
  })

  it('never reports more drawn than present', () => {
    // A drawn figure over the rectangle's own count can only be a duplicate the
    // probe failed to fold, and `Water · 1 · 3 shown` would discredit every
    // other row on the panel.
    const [row] = computeLegendContents(
      bbox,
      [at('w1', 'water')],
      new Map([['water::high', 3]]),
    )

    expect(row.drawnCount).toBe(1)
  })

  it('counts only what is inside the viewport, as it always did', () => {
    const rows = computeLegendContents(
      bbox,
      [at('w1', 'water'), { ...at('w2', 'water'), lat: 40 }],
      new Map([['water::high', 1]]),
    )

    expect(rows[0].count).toBe(1)
  })
})

describe('legendDropSummary', () => {
  const row = (
    type: string,
    count: number,
    drawnCount?: number,
  ): ReturnType<typeof computeLegendContents>[number] => ({
    type,
    confidence: 'high',
    count,
    hideable: true,
    drawnCount,
  })

  it('adds up what is in view against what fits', () => {
    expect(legendDropSummary([row('water', 14, 4), row('privy', 6, 0)])).toEqual({
      present: 20,
      drawn: 4,
    })
  })

  it('says nothing when everything present is drawn', () => {
    // "112 of 112 fit" is noise on a panel someone opens all day to answer a
    // different question.
    expect(legendDropSummary([row('water', 14, 14)])).toBeNull()
  })

  it('says nothing when nothing was measured', () => {
    expect(legendDropSummary([row('water', 14)])).toBeNull()
  })

  it('says nothing about an empty viewport', () => {
    expect(legendDropSummary([])).toBeNull()
  })

  it('ignores rows nobody measured rather than counting them as dropped', () => {
    // Mixing a measured row with an unmeasured one must not turn the unmeasured
    // one's whole count into a claimed drop.
    expect(legendDropSummary([row('water', 14, 14), row('privy', 6)])).toBeNull()
  })
})
