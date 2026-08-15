import { describe, it, expect } from 'vitest'
import {
  computeLegendContents,
  legendDropSummary,
  withEveryType,
  type MapPoint,
} from './legendContents'

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

// What is DRAWN, as against what is present (#528). The panel's promise is "what
// am I looking at right now", and since collision culling arrived it had been
// answering "what is inside this rectangle" - a row reading `Privy 6` on a map
// with no privy pin, because 3% of privies place at z14.
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
      false,
      new Map([
        ['water', 1],
        ['privy', 0],
      ]),
    )

    expect(rows).toEqual([
      { type: 'water', count: 2, hideable: true, drawnCount: 1 },
      { type: 'privy', count: 1, hideable: true, drawnCount: 0 },
    ])
  })

  it('is undefined, not zero, when nobody measured', () => {
    // The pin layer is absent on a cold start. "0 shown" then would claim a drop
    // that has not happened.
    const [row] = computeLegendContents(bbox, [at('w1', 'water')])

    expect(row.drawnCount).toBeUndefined()
  })

  it('is zero for a category the measurement did not mention', () => {
    // The whole map was measured, so a missing key is an answer rather than a gap
    // - this is exactly the privy row at a hiking zoom.
    const [row] = computeLegendContents(bbox, [at('p1', 'privy')], false, new Map())

    expect(row.drawnCount).toBe(0)
  })

  it('never reports more drawn than present', () => {
    // A drawn figure over the rectangle's own count can only be a duplicate the
    // probe failed to fold, and `Water 1 · 3 shown` would discredit every other
    // row on the panel.
    const [row] = computeLegendContents(
      bbox,
      [at('w1', 'water')],
      false,
      new Map([['water', 3]]),
    )

    expect(row.drawnCount).toBe(1)
  })

  it('counts a verified and an unverified spring in one row, as the rows do', () => {
    // #580 folded the confidence split out, so the drawn figure folds with it -
    // keying this the old way would produce a count that never matched a row.
    const rows = computeLegendContents(
      bbox,
      [at('w1', 'water'), at('w2', 'water', 'low')],
      false,
      new Map([['water', 1]]),
    )

    expect(rows).toEqual([{ type: 'water', count: 2, hideable: true, drawnCount: 1 }])
  })

  it('agrees with the verified-only filter rather than fighting it', () => {
    // With the toggle on, the counts exclude unverified points and the MAP has
    // filtered them out too, so both halves shrink together.
    const rows = computeLegendContents(
      bbox,
      [at('w1', 'water'), at('w2', 'water', 'low')],
      true,
      new Map([['water', 1]]),
    )

    expect(rows).toEqual([{ type: 'water', count: 1, hideable: true, drawnCount: 1 }])
  })
})

// The grid is also the hide toggles, and a toggle that only exists while its
// category is in front of the hiker is one they cannot find (#723). This pads
// the grid; nothing else on the panel sees the padded list.
describe('withEveryType', () => {
  const TYPES = ['water', 'privy', 'shelter']

  it('leaves a row that is already there exactly as it found it', () => {
    const measured = { type: 'water', count: 14, hideable: true, drawnCount: 4 }

    expect(withEveryType([measured], TYPES)[0]).toEqual(measured)
  })

  it('gives an absent category a row that counts none of it', () => {
    const rows = withEveryType([], TYPES)

    expect(rows.map((row) => [row.type, row.count])).toEqual([
      ['water', 0],
      ['privy', 0],
      ['shelter', 0],
    ])
  })

  it('makes a padded row a working switch', () => {
    expect(withEveryType([], TYPES).every((row) => row.hideable)).toBe(true)
  })

  it('reports no drop on a category with nothing to drop', () => {
    // Not zero. `drawnCount` says how many of the ones HERE did not fit, and a
    // zero would enter legendDropSummary's arithmetic as a measured row - the
    // panel reporting a drop that never happened.
    expect(withEveryType([], TYPES)[0].drawnCount).toBeUndefined()
    expect(legendDropSummary(withEveryType([], TYPES))).toBeNull()
  })

  it('returns them in the order it was given, whatever order the counts came in', () => {
    // computeLegendContents keys off a Map filled in whatever order the points
    // were encountered, so the grid re-shuffled itself as a hiker panned.
    const rows = withEveryType(
      [
        { type: 'shelter', count: 1, hideable: true },
        { type: 'water', count: 2, hideable: true },
      ],
      TYPES,
    )

    expect(rows.map((row) => row.type)).toEqual(TYPES)
  })

  it('keeps a safety row it was not asked to pad, after the ones it was', () => {
    // Closures and serious warnings are never in the caller's list: they have no
    // switch to reach, and a permanent "Closure 0" would be a standing claim
    // about closures on a panel with no business making one.
    const closure = { type: 'closure', count: 1, hideable: false }

    const rows = withEveryType([closure], TYPES)

    expect(rows).toHaveLength(TYPES.length + 1)
    expect(rows.at(-1)).toEqual(closure)
  })

  it('cannot be made to build a switch for a safety layer', () => {
    // The guard is NEVER_HIDEABLE rather than the caller's list, so a caller
    // handing this the wrong array gets a row it cannot toggle rather than an
    // off switch for a closure.
    expect(withEveryType([], ['closure'])[0].hideable).toBe(false)
  })
})

describe('legendDropSummary', () => {
  const row = (type: string, count: number, drawnCount?: number) => ({
    type,
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
    expect(legendDropSummary([row('water', 14, 14), row('privy', 6)])).toBeNull()
  })
})
