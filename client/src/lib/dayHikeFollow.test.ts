// Tests for lib/dayHikeFollow.ts - where a hiker is on the walk they said
// they were doing (#1041, frames `D9` and `D11`).
//
// THE TWO THINGS THIS SUITE IS REALLY ABOUT.
//
// The state must not flicker. A banner that appears and vanishes as a fix
// wobbles under canopy is a banner nobody reads, which is the same trust the
// wrong-way cue's persistence window exists to protect - so the hysteresis
// below is tested from BOTH sides, at one distance that reads differently
// depending on where the hiker just was.
//
// And it must never invent a way back. Off the route, the only things
// reported are a distance, a bearing, and which point of the route they
// belong to; there is no path across ground nobody mapped, and no test here
// should ever start expecting one.

import { describe, expect, it } from 'vitest'

import { resolveDayHike, type ResolvedDayHike } from './dayHikeCard'
import {
  BACK_ON_ROUTE_FEET,
  OFF_ROUTE_FEET,
  compassPoint,
  followDayHike,
  followHeader,
  followPosition,
  type FollowState,
} from './dayHikeFollow'
import {
  EAST_END,
  NETWORK,
  NORTH_END,
  WEST_END,
  hikeThrough,
} from './dayHikeWalk.fixtures'
import { buildGraphIndex, metresToMiles } from './trailGraph'

const INDEX = buildGraphIndex(NETWORK)

/** Metres of latitude as one degree, on lib/trailGraph.ts's own projection -
 *  so an offset below is a distance a reader can convert by hand. */
const METRES_PER_DEGREE_LAT = (Math.PI / 180) * 6_378_137
const FEET_PER_METRE = 3.280839895

/** A point `feet` due north of one on the Pine Meadow line. */
function northOf(lon: number, lat: number, feet: number) {
  return { lon, lat: lat + feet / FEET_PER_METRE / METRES_PER_DEGREE_LAT }
}

function resolvedFor(hike = hikeThrough([WEST_END, NORTH_END])): ResolvedDayHike {
  const resolved = resolveDayHike(INDEX, hike)
  expect(resolved).not.toBeNull()
  return resolved!
}

describe('followDayHike', () => {
  it('says nothing at all without a fix', () => {
    // Null rather than "0.0 mi in", which would be a claim that somebody is
    // standing at the trailhead.
    expect(followDayHike({ index: INDEX, resolved: resolvedFor(), at: null })).toBeNull()
  })

  it('measures distance along the hiker s own walk, not any trail axis', () => {
    const state = followDayHike({
      index: INDEX,
      resolved: resolvedFor(),
      // Halfway along the first edge.
      at: { lon: -74.095, lat: 41.25 },
    })

    expect(state?.kind).toBe('on-route')
    if (state?.kind !== 'on-route') return
    expect(state.walkedMi).toBeCloseTo(metresToMiles(418), 3)
    expect(state.toGoMi).toBeCloseTo(metresToMiles(1530), 3)
    expect(state.totalMi).toBeCloseTo(metresToMiles(1948), 3)
  })

  it('names the leg the hiker is on, counted as the card counts legs', () => {
    const resolved = resolvedFor()
    const state = followDayHike({
      index: INDEX,
      resolved,
      at: { lon: -74.095, lat: 41.25 },
    })

    expect(state?.kind).toBe('on-route')
    if (state?.kind !== 'on-route') return
    expect(state.leg).toMatchObject({ at: 1, of: 2, name: 'Pine Meadow Trail' })
    // The count is the card's own, not a second opinion about it.
    expect(state.leg.of).toBe(resolved.legs.length)
  })

  it('reports a distance and a bearing off the route, and no way back', () => {
    const state = followDayHike({
      index: INDEX,
      resolved: resolvedFor(),
      at: northOf(-74.095, 41.25, 200),
    })

    expect(state?.kind).toBe('off-route')
    if (state?.kind !== 'off-route') return
    expect(state.offRouteFeet).toBeCloseTo(200, 0)
    // Due south of the hiker, because that is where the line is. A bearing
    // and a distance is the whole answer: nothing here is a route.
    expect(compassPoint(state.nearest.bearingDeg)).toBe('south')
    expect(state.nearest.walkedMi).toBeCloseTo(metresToMiles(418), 3)
    expect(Object.keys(state)).not.toContain('back')
  })

  it('takes more to come back on than it took to go off', () => {
    // One distance, between the two thresholds, read twice.
    const between = (OFF_ROUTE_FEET + BACK_ON_ROUTE_FEET) / 2
    expect(between).toBeGreaterThan(BACK_ON_ROUTE_FEET)
    expect(between).toBeLessThan(OFF_ROUTE_FEET)

    const at = northOf(-74.095, 41.25, between)
    const resolved = resolvedFor()

    const walkingIn = followDayHike({ index: INDEX, resolved, at })
    expect(walkingIn?.kind).toBe('on-route')

    const wandered = followDayHike({
      index: INDEX,
      resolved,
      at: northOf(-74.095, 41.25, 200),
    })
    expect(wandered?.kind).toBe('off-route')

    // Same fix, and now it reads as still off - which is what stops the band
    // strobing while somebody stands at the edge of the threshold.
    const comingBack = followDayHike({ index: INDEX, resolved, at, previous: wandered })
    expect(comingBack?.kind).toBe('off-route')
  })

  it('puts a hiker on the pass of an out-and-back they are actually on', () => {
    const resolved = resolvedFor(hikeThrough([WEST_END, EAST_END, WEST_END]))
    const at = { lon: -74.095, lat: 41.25 }

    // With nothing known, the earlier pass - which is where a walk starts.
    const first = followDayHike({ index: INDEX, resolved, at })
    expect(first?.kind).toBe('on-route')
    if (first?.kind !== 'on-route') return
    expect(first.walkedMi).toBeCloseTo(metresToMiles(418), 3)

    // Having already walked past the far end, the SAME fix is the way home.
    // A walk does not teleport between two passes of one edge.
    const homeward = followDayHike({
      index: INDEX,
      resolved,
      at,
      previous: { ...first, walkedMi: metresToMiles(2700) },
    })
    expect(homeward?.kind).toBe('on-route')
    if (homeward?.kind !== 'on-route') return
    expect(homeward.walkedMi).toBeCloseTo(metresToMiles(2926), 3)
  })
})

describe('followHeader', () => {
  const onRoute = (): FollowState => {
    const state = followDayHike({
      index: INDEX,
      resolved: resolvedFor(),
      at: { lon: -74.095, lat: 41.25 },
    })
    expect(state).not.toBeNull()
    return state!
  }

  it('is nothing at all when no hike is being followed', () => {
    expect(followHeader({ following: false, follow: onRoute() })).toBeNull()
  })

  it('keeps saying "Day hike" while the first fix is still coming', () => {
    // The hiker pressed Follow; an eyebrow that flipped back to the trail's
    // name while GPS settled would be the screen forgetting what they asked.
    expect(followHeader({ following: true, follow: null })).toEqual({
      trailName: 'Day hike',
      state: undefined,
    })
  })

  it('reads the leg, and then the two states that outrank it', () => {
    expect(followHeader({ following: true, follow: onRoute() })).toEqual({
      trailName: 'Day hike',
      state: 'leg 1 of 2 · Pine Meadow Trail',
    })
    expect(
      followHeader({ following: true, follow: onRoute(), atJunction: true })?.state,
    ).toBe('at a junction')

    const off = followDayHike({
      index: INDEX,
      resolved: resolvedFor(),
      at: northOf(-74.095, 41.25, 200),
    })
    expect(followHeader({ following: true, follow: off })?.state).toBe('off the route')
  })
})

describe('followPosition', () => {
  it('is two distances in, and converts with the preference', () => {
    const state = followDayHike({
      index: INDEX,
      resolved: resolvedFor(),
      at: { lon: -74.095, lat: 41.25 },
    })
    expect(state).not.toBeNull()

    expect(followPosition(state!, 'imperial')).toBe('0.3 mi in · 1.0 mi to go')
    expect(followPosition(state!, 'metric')).toBe('420 m in · 1.5 km to go')
  })

  it('is the displacement when the hiker is off it', () => {
    const off = followDayHike({
      index: INDEX,
      resolved: resolvedFor(),
      at: northOf(-74.095, 41.25, 200),
    })
    expect(off).not.toBeNull()
    expect(followPosition(off!, 'imperial')).toMatch(/^200 ft off your route$/)
  })
})

describe('compassPoint', () => {
  it('is eight points, which is about the width of the answer', () => {
    expect(compassPoint(0)).toBe('north')
    expect(compassPoint(44)).toBe('north-east')
    expect(compassPoint(225)).toBe('south-west')
    // Wraps rather than falling off the end of the table.
    expect(compassPoint(359)).toBe('north')
  })
})
