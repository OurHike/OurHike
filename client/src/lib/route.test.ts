// Tests for route.ts - the route builder's arithmetic (#755).
//
// The insertion rule gets the most attention because it is the whole
// interaction model: no modes, one rule, and the three natural workflows
// (walk-order tapping, filling in a middle, extending backwards) all have to
// fall out of it rather than be special-cased.

import { describe, expect, it } from 'vitest'
import { STANDARD_PACE, type PaceProfile } from './pace'

import type { ElevationProfile } from './elevationProfile'
import { naismithMinutes } from './naismith'
import {
  anchoredClientMile,
  anchoredMile,
  insertRoutePoint,
  legFigures,
  mileAtWalkingMinutes,
  restretchStops,
  routeDirection,
  routeLegs,
  totalFigures,
} from './route'

const at = (mile: number) => ({ mile })
const miles = (points: { mile: number }[]) => points.map((p) => p.mile)

describe('insertRoutePoint', () => {
  it('makes the first tap the start', () => {
    expect(miles(insertRoutePoint([], at(470.8)))).toEqual([470.8])
  })

  it('appends when tapping in walking order', () => {
    const points = insertRoutePoint(insertRoutePoint([at(470.8)], at(486.2)), at(503.4))
    expect(miles(points)).toEqual([470.8, 486.2, 503.4])
  })

  it('inserts between two points when tapping between them', () => {
    // A point inside a leg adds zero trail distance; anywhere else adds some.
    const points = insertRoutePoint([at(470.8), at(503.4)], at(486.2))
    expect(miles(points)).toEqual([470.8, 486.2, 503.4])
  })

  it('extends the hike backwards when tapping behind the start', () => {
    const points = insertRoutePoint([at(470.8), at(503.4)], at(460.0))
    expect(miles(points)).toEqual([460.0, 470.8, 503.4])
  })

  it('works the same way southbound', () => {
    const southbound = insertRoutePoint(
      insertRoutePoint([at(503.4)], at(486.2)),
      at(470.8),
    )
    expect(miles(southbound)).toEqual([503.4, 486.2, 470.8])
  })

  it('ignores a tap landing exactly on an existing point', () => {
    // A zero-length leg describes no trail. Re-tapping a dropped point does
    // not mean "again".
    const points = [at(470.8), at(503.4)]
    expect(miles(insertRoutePoint(points, at(470.8)))).toEqual([470.8, 503.4])
  })
})

describe('routeLegs and routeDirection', () => {
  it('pairs consecutive points into legs', () => {
    const legs = routeLegs([at(1), at(2), at(3)])
    expect(legs.map((l) => [l.from.mile, l.to.mile])).toEqual([
      [1, 2],
      [2, 3],
    ])
  })

  it('withholds a direction until two points exist', () => {
    // One point has no direction, and inventing one would put a
    // confident-looking NOBO on screen that is wrong for half of everyone -
    // the same refusal hikeDirection.ts makes for the first quarter mile.
    expect(routeDirection([])).toBeNull()
    expect(routeDirection([at(5)])).toBeNull()
  })

  it('reads direction from the ends alone', () => {
    expect(routeDirection([at(1), at(9)])).toBe('NOBO')
    expect(routeDirection([at(9), at(1)])).toBe('SOBO')
  })
})

describe('restretchStops', () => {
  it('replaces the ends and keeps the destinations still inside', () => {
    const stops = [at(10), at(25), at(40), at(60)]
    expect(miles(restretchStops(stops, at(20), at(50)))).toEqual([20, 25, 40, 50])
  })

  it('drops destinations the new stretch no longer reaches', () => {
    const stops = [at(10), at(25), at(40), at(60)]
    expect(miles(restretchStops(stops, at(30), at(50)))).toEqual([30, 40, 50])
  })

  it('keeps a southbound route southbound, whichever way the drag ran', () => {
    // A drag normalises to low-then-high before it gets here; a southbound
    // route re-stretched must not come back walking north.
    const stops = [at(60), at(40), at(25), at(10)]
    expect(miles(restretchStops(stops, at(20), at(50)))).toEqual([50, 40, 25, 20])
  })

  it('drops a destination landing exactly on a new end', () => {
    // A via at an end would make a zero-length leg - the same refusal
    // insertRoutePoint makes for an equal mile.
    const stops = [at(10), at(25), at(60)]
    expect(miles(restretchStops(stops, at(25), at(50)))).toEqual([25, 50])
  })

  it('treats fewer than two existing stops as northbound', () => {
    expect(miles(restretchStops([], at(5), at(15)))).toEqual([5, 15])
    expect(miles(restretchStops([at(8)], at(5), at(15)))).toEqual([5, 15])
  })
})

// Miles chosen to be exactly representable in the Float32Array the profile
// stores distances in - 0.1 is not, and a window bound of 0.5 must not
// exclude its own last sample over a float32 rounding step.
function profile(entries: [number, number, boolean?][]): ElevationProfile {
  return {
    distanceMi: Float32Array.from(entries.map(([mile]) => mile)),
    elevationFt: Float32Array.from(entries.map(([, elevation]) => elevation)),
    partStart: Uint8Array.from(entries.map(([, , seam]) => (seam === true ? 1 : 0))),
  }
}

describe('legFigures', () => {
  const climb = profile([
    [0, 1000],
    [0.25, 1400],
    [0.5, 1200],
  ])

  it('measures a northbound leg: distance, gain, loss, moving minutes', () => {
    const figures = legFigures(climb, 0, 0.5)
    expect(figures.distanceMi).toBeCloseTo(0.5)
    expect(figures.ascentFt).toBeCloseTo(400)
    expect(figures.descentFt).toBeCloseTo(200)
    expect(figures.minutes).toBeCloseTo(
      naismithMinutes({ distanceMi: 0.5, ascentFt: 400 }),
    )
  })

  it('swaps gain and loss for the same stretch walked south, via the reversed run', () => {
    const figures = legFigures(climb, 0.5, 0)
    expect(figures.distanceMi).toBeCloseTo(0.5)
    expect(figures.ascentFt).toBeCloseTo(200)
    expect(figures.descentFt).toBeCloseTo(400)
    // Time follows the direction too: less climbing south over this stretch,
    // so a shorter estimate. Naismith's no-descent-credit rule is untouched -
    // descent still buys nothing, it just stops being counted as ascent.
    expect(figures.minutes).toBeCloseTo(
      naismithMinutes({ distanceMi: 0.5, ascentFt: 200 }),
    )
  })

  it('does not count a part seam as a climb in either direction', () => {
    const seamed = profile([
      [0, 0],
      [0.25, 10],
      [0.5, 100, true],
      [0.75, 110],
    ])
    expect(legFigures(seamed, 0, 0.75).ascentFt).toBeCloseTo(20)
    expect(legFigures(seamed, 0.75, 0).descentFt).toBeCloseTo(20)
  })
})

describe('totalFigures', () => {
  it('sums legs before any display rounding', () => {
    const total = totalFigures([
      { distanceMi: 15.4, ascentFt: 2900, descentFt: 1750, minutes: 425.2 },
      { distanceMi: 17.2, ascentFt: 4100, descentFt: 2200, minutes: 500.3 },
    ])
    expect(total.distanceMi).toBeCloseTo(32.6)
    expect(total.ascentFt).toBeCloseTo(7000)
    expect(total.descentFt).toBeCloseTo(3950)
    expect(total.minutes).toBeCloseTo(925.5)
  })

  it('rolls an empty route up to zeros', () => {
    expect(totalFigures([])).toEqual({
      distanceMi: 0,
      ascentFt: 0,
      descentFt: 0,
      minutes: 0,
    })
  })
})

describe('anchoredMile', () => {
  it('carries the nearest anchor offset across to the pipeline axis', () => {
    // The client index reads this spot as 100.0; the nearest POI sits at
    // client 99.0 and published 99.4, so the tap lands at 100.4.
    const anchors = [
      { clientMile: 99.0, mile: 99.4 },
      { clientMile: 250.0, mile: 251.2 },
    ]
    expect(anchoredMile(100.0, anchors)).toBeCloseTo(100.4)
    expect(anchoredMile(249.0, anchors)).toBeCloseTo(250.2)
  })

  it('refuses rather than guesses when there are no anchors', () => {
    // A data release that predates POI miles (#753) offers no honest way
    // onto the pipeline axis. The caller says "needs a newer download".
    expect(anchoredMile(100.0, [])).toBeNull()
  })
})

describe('anchoredClientMile', () => {
  it('is anchoredMile run the other way - the two round-trip', () => {
    const anchors = [
      { clientMile: 99.0, mile: 99.4 },
      { clientMile: 250.0, mile: 251.2 },
    ]
    expect(anchoredClientMile(100.4, anchors)).toBeCloseTo(100.0)
    expect(anchoredClientMile(250.2, anchors)).toBeCloseTo(249.0)
    // Round trip: a pipeline mile carried to the client scale and back is
    // itself, as long as both trips picked the same anchor.
    expect(
      anchoredMile(anchoredClientMile(100.4, anchors) as number, anchors),
    ).toBeCloseTo(100.4)
  })

  it('refuses without anchors, like its inverse', () => {
    expect(anchoredClientMile(100.4, [])).toBeNull()
  })
})

describe('mileAtWalkingMinutes', () => {
  /** Flat ground from 0 to 40 miles, in quarter-mile steps. */
  const flat = (): ElevationProfile => {
    const miles: number[] = []
    for (let mile = 0; mile <= 40; mile += 0.25) miles.push(mile)
    return {
      distanceMi: Float32Array.from(miles),
      elevationFt: Float32Array.from(miles.map(() => 2000)),
    }
  }

  it('reaches the flat-pace distance on flat ground, both directions', () => {
    const budget = naismithMinutes({ distanceMi: 10, ascentFt: 0 })
    expect(mileAtWalkingMinutes(flat(), 5, budget, 'NOBO')).toBeCloseTo(15, 1)
    expect(mileAtWalkingMinutes(flat(), 35, budget, 'SOBO')).toBeCloseTo(25, 1)
  })

  it('reaches less where the ground climbs - ascent buys no distance', () => {
    // 200 ft up every quarter mile from mile 10 on: relentless, and enough
    // for Naismith's ascent term to visibly shorten the reach.
    const miles: number[] = []
    const feet: number[] = []
    for (let mile = 0; mile <= 40; mile += 0.25) {
      miles.push(mile)
      feet.push(mile <= 10 ? 2000 : 2000 + (mile - 10) * 800)
    }
    const climbing = {
      distanceMi: Float32Array.from(miles),
      elevationFt: Float32Array.from(feet),
    }
    const budget = naismithMinutes({ distanceMi: 10, ascentFt: 0 })
    const reached = mileAtWalkingMinutes(climbing, 5, budget, 'NOBO')
    expect(reached).toBeLessThan(14)
    // And the answer prices back to the budget through the same arithmetic
    // the route card uses. The tolerance is one profile sample's worth of
    // this deliberately relentless climb (200 ft ≈ 6 minutes): the window's
    // ascent moves in whole-sample steps, so the crossing can sit a step
    // past the budget - the profile's own resolution, not the search's.
    expect(Math.abs(legFigures(climbing, 5, reached).minutes - budget)).toBeLessThan(8)
  })

  it('clamps to the profile end when the budget out-walks the data', () => {
    const budget = naismithMinutes({ distanceMi: 100, ascentFt: 0 })
    expect(mileAtWalkingMinutes(flat(), 5, budget, 'NOBO')).toBeCloseTo(40, 5)
    expect(mileAtWalkingMinutes(flat(), 5, budget, 'SOBO')).toBeCloseTo(0, 5)
  })
})

/**
 * The hiker's own pace, through the route (#880).
 *
 * Every figure the planner prints comes from here, so a pace that reached the
 * highlight sheet and not this would have two screens disagreeing about one
 * day.
 */
describe("a route measured at the hiker's own pace", () => {
  const SLOWER: PaceProfile = { ...STANDARD_PACE, flatPaceMph: 2.6 }
  const FASTER: PaceProfile = { ...STANDARD_PACE, flatPaceMph: 4.0 }

  /** Ten miles climbing steadily, sampled every mile. */
  const rising = profile(
    Array.from({ length: 11 }, (_, i) => [i, i * 200] as [number, number]),
  )

  it('defaults to the standard, so callers that pass none are unchanged', () => {
    expect(legFigures(rising, 0, 5).minutes).toBeCloseTo(
      legFigures(rising, 0, 5, STANDARD_PACE).minutes,
      9,
    )
  })

  it('takes longer over the same ground for a slower hiker', () => {
    expect(legFigures(rising, 0, 5, SLOWER).minutes).toBeGreaterThan(
      legFigures(rising, 0, 5, STANDARD_PACE).minutes,
    )
  })

  it('lets a faster hiker reach FURTHER in the same walking minutes', () => {
    // FLAT ground, twenty miles of it, and deliberately so. The bound inside
    // mileAtWalkingMinutes is derived from flat walking, and on a climbing
    // profile the ascent term dominates so completely that the bound never
    // binds - a version of this test on `rising` passes whether or not the
    // bound uses the hiker's pace, which is a test that cannot fail.
    //
    // Here it binds. Two hours at the standard 3.107 mph reaches 6.2 mi; at
    // 4.0 mph it reaches 8.0. With the bound left on the standard pace, the
    // faster hiker is clamped to 6.2 - silently short, never an error.
    const flat = profile(Array.from({ length: 21 }, (_, i) => [i, 0] as [number, number]))
    const standard = mileAtWalkingMinutes(flat, 0, 120, 'NOBO', STANDARD_PACE)
    const faster = mileAtWalkingMinutes(flat, 0, 120, 'NOBO', FASTER)

    expect(standard).toBeCloseTo(6.2, 1)
    expect(faster).toBeCloseTo(8.0, 1)
    expect(faster).toBeGreaterThan(standard)
  })

  it('stops a slower hiker sooner, in the same minutes', () => {
    const standard = mileAtWalkingMinutes(rising, 0, 120, 'NOBO', STANDARD_PACE)
    const slower = mileAtWalkingMinutes(rising, 0, 120, 'NOBO', SLOWER)
    expect(slower).toBeLessThan(standard)
  })
})
