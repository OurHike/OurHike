import { describe, it, expect } from 'vitest'
import { LANES, laneFor, clusterWaypoints, COLLAPSE_THRESHOLD_PCT } from './waypointLanes'

// WIREFRAMES.md, map screen §4: three lanes - WATER, SLEEP, ELSE - with pins
// positioned by percentage along the visible mile window, and overlapping pins
// collapsed into a count pill. The collapse is the point: at a 5-mile window a
// cluster of four campsites within a tenth of a mile would otherwise render as
// one illegible smear of overlapping glyphs.

const WINDOW = { startMile: 1400, endMile: 1410 }

function at(mile: number, type = 'water', id = `p${mile}-${type}`) {
  return { id, type, mile }
}

describe('laneFor', () => {
  it('sends water to the WATER lane', () => {
    expect(laneFor('water')).toBe('water')
  })

  it.each(['shelter', 'campsite'])('sends %s to the SLEEP lane', (type) => {
    expect(laneFor(type)).toBe('sleep')
  })

  it.each(['resupply', 'town', 'parking', 'crossing', 'closure'])(
    'sends %s to the ELSE lane',
    (type) => {
      expect(laneFor(type)).toBe('else')
    },
  )

  it('sends an unrecognised type to ELSE rather than dropping it off the ribbon', () => {
    expect(laneFor('something-new-from-a-later-import')).toBe('else')
  })
})

describe('LANES', () => {
  it('is exactly the three lanes WIREFRAMES.md names, in order', () => {
    expect(LANES.map((l) => l.id)).toEqual(['water', 'sleep', 'else'])
    expect(LANES.map((l) => l.label)).toEqual(['WATER', 'SLEEP', 'ELSE'])
  })
})

describe('clusterWaypoints', () => {
  it('positions a waypoint by its percentage along the visible window', () => {
    const [cluster] = clusterWaypoints([at(1405)], WINDOW).water

    expect(cluster.positionPct).toBe(50)
  })

  it('puts the window start at 0% and the end at 100%', () => {
    const start = clusterWaypoints([at(1400)], WINDOW).water[0]
    const end = clusterWaypoints([at(1410)], WINDOW).water[0]

    expect(start.positionPct).toBe(0)
    expect(end.positionPct).toBe(100)
  })

  it('drops waypoints outside the visible window', () => {
    const lanes = clusterWaypoints([at(1399), at(1411)], WINDOW)

    expect(lanes.water).toHaveLength(0)
  })

  it('keeps well-separated waypoints as separate pins', () => {
    const lanes = clusterWaypoints([at(1401), at(1408)], WINDOW)

    expect(lanes.water).toHaveLength(2)
    expect(lanes.water.every((c) => c.count === 1)).toBe(true)
  })

  it('collapses waypoints closer together than the threshold into one pill', () => {
    // Three springs within a tenth of a mile - one pill reading "3", not three
    // glyphs stacked on the same pixel.
    const lanes = clusterWaypoints([at(1405), at(1405.03), at(1405.06)], WINDOW)

    expect(lanes.water).toHaveLength(1)
    expect(lanes.water[0].count).toBe(3)
  })

  it('carries every collapsed member so a tap can still open the whole set', () => {
    const lanes = clusterWaypoints([at(1405), at(1405.03)], WINDOW)

    expect(lanes.water[0].members.map((m) => m.mile)).toEqual([1405, 1405.03])
  })

  it('places a collapsed pill at the midpoint of what it swallowed', () => {
    // 1405 is 50%, 1405.1 is 51% - a 1% gap, inside the 1.5% threshold, so
    // these collapse and the pill sits between them.
    const lanes = clusterWaypoints([at(1405), at(1405.1)], WINDOW)

    expect(lanes.water).toHaveLength(1)
    expect(lanes.water[0].positionPct).toBeCloseTo(50.5, 5)
  })

  it('leaves a gap wider than the threshold as two separate pins', () => {
    // 2% apart - just outside the threshold, and the boundary that the
    // midpoint case above sits on the other side of.
    const lanes = clusterWaypoints([at(1405), at(1405.2)], WINDOW)

    expect(lanes.water).toHaveLength(2)
  })

  it('never collapses across lanes - a spring and a shelter stay separate', () => {
    const lanes = clusterWaypoints([at(1405, 'water'), at(1405, 'shelter')], WINDOW)

    expect(lanes.water).toHaveLength(1)
    expect(lanes.sleep).toHaveLength(1)
  })

  it('clusters by rendered distance, so the same points collapse at a wider window', () => {
    // Two points 0.5mi apart are 5% apart in a 10-mile window (separate) but
    // 0.5% apart in a 100-mile window (collapsed). The threshold is about
    // pixels on screen, not miles on the ground.
    const near = [at(1405), at(1405.5)]

    expect(clusterWaypoints(near, WINDOW).water).toHaveLength(2)
    expect(clusterWaypoints(near, { startMile: 1350, endMile: 1450 }).water).toHaveLength(
      1,
    )
  })

  it('sorts pins left to right, so render order matches reading order', () => {
    const lanes = clusterWaypoints([at(1408), at(1401), at(1405)], WINDOW)

    expect(lanes.water.map((c) => c.positionPct)).toEqual([10, 50, 80])
  })

  it('exposes the collapse threshold rather than burying it as a literal', () => {
    expect(COLLAPSE_THRESHOLD_PCT).toBeGreaterThan(0)
  })

  it('returns all three lanes even when nothing is in view', () => {
    const lanes = clusterWaypoints([], WINDOW)

    expect(Object.keys(lanes).sort()).toEqual(['else', 'sleep', 'water'])
  })
})
