// The route builder's arithmetic: ordered points on the trail, the legs
// between them, and honest figures for each leg (#755,
// features/HIKE_PLANNING.md "The route builder").
//
// EVERY MILE HERE IS THE PIPELINE'S MILE - the axis elevation_profile.json is
// sampled along and StoredPoi.mile is projected onto (#753). The client
// index's own mile (lib/trailPosition.ts) is a different measurement of the
// same line, and comparing the two as one is the exact mistake
// HIKE_PLANNING.md Finding 1 exists to stop: harmless over a ten-mile ribbon
// window, summed ~150 times in a plan. `anchoredMile` below is the one place
// the two scales are allowed to meet, and it exists so nothing else has to.
//
// ONLY THE AT CENTERLINE CAN CARRY A ROUTE. The tap snap
// (trailPosition.buildTrailIndex) indexes `source === 'centerline'` and
// nothing else, so blue-blazed side trails and the road walk into town are
// not routable - the largest single gap between this and a plan a
// thru-hiker would keep, per the doc, and one the UI states rather than
// papers over.

import type { HikeDirection } from '../chrome/Header'
import {
  cumulativeGainOverProfile,
  cumulativeLossOverProfile,
  reverseProfileWindow,
} from './elevationGain'
import { profileSamples, type ElevationProfile } from './elevationProfile'
import { naismithMinutes } from './naismith'

/** A point somewhere along the trail, on the pipeline's mile axis. */
export interface RouteMile {
  mile: number
}

/**
 * Where a new point goes: the position that adds the least trail distance.
 *
 * No modes, and that is the point (wireframe 2a, #755): the first tap is the
 * start, the last is the end, and this one rule makes both natural workflows
 * work without the hiker learning it. Tapping in walking order always
 * appends - extending past the end adds |new - end| while squeezing into the
 * last leg adds twice that. Tapping between two existing points always
 * inserts there - a point inside a leg adds zero distance, and every other
 * position adds some. Tapping behind the start extends the hike backwards
 * from it, by the same arithmetic.
 *
 * What the rule cannot express is doubling back - an out-and-back's return
 * leg re-walks miles, which is never the least-distance placement. That is
 * inherent to the rule the design chose, not an implementation limit.
 *
 * A tap landing exactly on an existing point's mile is returned unchanged
 * rather than inserted: a zero-length leg describes no trail, and a hiker
 * re-tapping a point they already dropped did not mean "again".
 */
export function insertRoutePoint<T extends RouteMile>(
  points: readonly T[],
  point: T,
): T[] {
  if (points.some((existing) => existing.mile === point.mile)) return [...points]
  if (points.length === 0) return [point]

  let bestSlot = 0
  let bestCost = Infinity
  for (let slot = 0; slot <= points.length; slot++) {
    const before = slot > 0 ? points[slot - 1].mile : null
    const after = slot < points.length ? points[slot].mile : null
    const cost =
      before === null
        ? Math.abs((after as number) - point.mile)
        : after === null
          ? Math.abs(point.mile - before)
          : Math.abs(point.mile - before) +
            Math.abs(after - point.mile) -
            Math.abs(after - before)
    // Ties go to the LATER slot. Every workflow above wins its slot
    // strictly except one: against a single point, prepending and appending
    // add the same distance and mean opposite hikes. Appending is the one
    // where the first tap stays the start - which is the rule.
    if (cost <= bestCost) {
      bestCost = cost
      bestSlot = slot
    }
  }

  return [...points.slice(0, bestSlot), point, ...points.slice(bestSlot)]
}

/** The stretches between consecutive points, in walking order. */
export function routeLegs<T extends RouteMile>(
  points: readonly T[],
): { from: T; to: T }[] {
  return points.slice(1).map((to, i) => ({ from: points[i], to }))
}

/**
 * Which way this route runs, from nothing but its ends - the same rule
 * plannedHike.ts follows, and for the same reason: a stored direction would
 * be a second source of truth that could drift from the points it is derived
 * from. Null while fewer than two points exist, because one point has no
 * direction and inventing one would put a wrong NOBO on screen.
 */
export function routeDirection<T extends RouteMile>(
  points: readonly T[],
): HikeDirection | null {
  if (points.length < 2) return null
  const first = points[0].mile
  const last = points[points.length - 1].mile
  return last > first ? 'NOBO' : 'SOBO'
}

/** What one leg (or one day) costs to walk. Unrounded working numbers -
 *  display rules (units.ts, naismith.ts's ≈ and 5-minute step) apply at the
 *  edge, never here, so totals summed from these cannot drift from their
 *  parts. */
export interface LegFigures {
  distanceMi: number
  ascentFt: number
  descentFt: number
  /** Naismith moving minutes. Moving time only - no lunch, no water stops,
   *  no forty minutes at the shelter - and the UI's job is to say so. */
  minutes: number
}

/**
 * Distance, confirmed ascent, confirmed descent and moving time for one
 * stretch, walked from `fromMile` to `toMile`.
 *
 * Direction-aware the way HIKE_PLANNING.md requires: a southbound leg is the
 * window's sample run REVERSED and then counted, not the northbound totals
 * swapped afterwards - the dead-band hysteresis walks the run in order, so
 * the two operations genuinely differ at the margins.
 */
export function legFigures(
  profile: ElevationProfile,
  fromMile: number,
  toMile: number,
): LegFigures {
  const low = Math.min(fromMile, toMile)
  const high = Math.max(fromMile, toMile)
  const forward = profileSamples(profile, { startMile: low, endMile: high })
  const walked = toMile >= fromMile ? forward : reverseProfileWindow(forward)

  const distanceMi = high - low
  const ascentFt = cumulativeGainOverProfile(walked)
  const descentFt = cumulativeLossOverProfile(walked)
  return {
    distanceMi,
    ascentFt,
    descentFt,
    minutes: naismithMinutes({ distanceMi, ascentFt }),
  }
}

/** The route rolled up: legs summed before any display rounding. */
export function totalFigures(legs: readonly LegFigures[]): LegFigures {
  return legs.reduce(
    (sum, leg) => ({
      distanceMi: sum.distanceMi + leg.distanceMi,
      ascentFt: sum.ascentFt + leg.ascentFt,
      descentFt: sum.descentFt + leg.descentFt,
      minutes: sum.minutes + leg.minutes,
    }),
    { distanceMi: 0, ascentFt: 0, descentFt: 0, minutes: 0 },
  )
}

/** A place whose position is known on BOTH mile scales: the pipeline's
 *  published mile (StoredPoi.mile, #753) and the client index's own. Every
 *  POI in a current data release is one. */
export interface MileAnchor {
  clientMile: number
  mile: number
}

/**
 * A tapped point's mile, carried onto the pipeline's axis.
 *
 * A tap has no precomputed answer - locateOnTrail() places it, on the client
 * index's scale (its one remaining job under Finding 2). But the figures a
 * route prints slice the elevation profile, which lives on the pipeline's
 * scale, and the two accumulate their part-gap skips differently. The
 * correction: find the nearest anchor by client mile and carry its offset
 * across. The difference between two NEARBY positions is the quantity the
 * docs say mostly dodges the axis faults (HIKE_PLANNING.md Finding 3 makes
 * the same move against #652), so the error this leaves is the drift over
 * the few miles between the tap and its anchor - small against the ~4.3 mi
 * mean POI spacing - rather than the drift over everything south of it.
 *
 * Null when there are no anchors at all: a data release that predates
 * POI miles (#753) offers no honest way onto the pipeline axis, and the
 * caller says "this needs a newer download" rather than inventing one -
 * the exact degradation HIKE_PLANNING.md Finding 2 prescribes.
 */
export function anchoredMile(
  clientMile: number,
  anchors: readonly MileAnchor[],
): number | null {
  if (anchors.length === 0) return null

  let nearest = anchors[0]
  let nearestDistance = Math.abs(anchors[0].clientMile - clientMile)
  for (const anchor of anchors) {
    const distance = Math.abs(anchor.clientMile - clientMile)
    if (distance < nearestDistance) {
      nearest = anchor
      nearestDistance = distance
    }
  }

  return nearest.mile + (clientMile - nearest.clientMile)
}

/**
 * The same carry run the other way: a pipeline-axis mile brought onto the
 * client index's scale, so a stop that was never tapped can still be DRAWN.
 * A distance-derived stop ("ends near", "a distance from the shelter") is
 * born as pipeline-mile arithmetic and has no located point behind it; the
 * drawing slices the centerline by client miles (trailSlice), and this is
 * how such a stop gets one. Same nearest-anchor offset, same null when no
 * anchors exist - the caller leaves the stop undrawn rather than drawing it
 * on the wrong scale.
 */
export function anchoredClientMile(
  mile: number,
  anchors: readonly MileAnchor[],
): number | null {
  if (anchors.length === 0) return null

  let nearest = anchors[0]
  let nearestDistance = Math.abs(anchors[0].mile - mile)
  for (const anchor of anchors) {
    const distance = Math.abs(anchor.mile - mile)
    if (distance < nearestDistance) {
      nearest = anchor
      nearestDistance = distance
    }
  }

  return nearest.clientMile + (mile - nearest.mile)
}

/**
 * How far `minutes` of Naismith moving time reaches from `fromMile` - toward
 * larger miles for NOBO, smaller for SOBO - clamped to the profile's own
 * coverage. The entrance's "How long" question resolves to a mile through
 * this ("3 days at your 7h-walking target reaches ≈ 45 mi").
 *
 * A binary search over legFigures rather than a second derivation: the mile
 * this returns is DEFINED by the same arithmetic the route card then prices
 * the stretch with, so the two cannot disagree. Monotone because both of
 * Naismith's terms only grow as the window does - distance linearly, ascent
 * never negatively (no descent credit, naismith.ts's own rule).
 *
 * The search window is bounded by the flat-ground reach for the budget
 * (ascent only ever slows Naismith down, so no honest answer lies past it) -
 * which keeps the slice a few thousand samples instead of the whole
 * 141,000-sample profile on every slider step.
 */
export function mileAtWalkingMinutes(
  profile: ElevationProfile,
  fromMile: number,
  minutes: number,
  direction: HikeDirection,
): number {
  const first = profile.distanceMi[0]
  const last = profile.distanceMi[profile.distanceMi.length - 1]
  const limit =
    direction === 'NOBO' ? Math.max(fromMile, last) : Math.min(fromMile, first)

  const flatBound = minutes / naismithMinutes({ distanceMi: 1, ascentFt: 0 })
  const maxSpan = Math.min(Math.abs(limit - fromMile), flatBound)
  if (maxSpan === 0) return fromMile

  const spanEnd = direction === 'NOBO' ? fromMile + maxSpan : fromMile - maxSpan
  if (legFigures(profile, fromMile, spanEnd).minutes <= minutes) return spanEnd

  // 0.02 mi ≈ 32 m, under the profile's own 25 m sample spacing - resolving
  // finer would be precision the data does not have.
  let low = 0
  let high = maxSpan
  while (high - low > 0.02) {
    const mid = (low + high) / 2
    const at = direction === 'NOBO' ? fromMile + mid : fromMile - mid
    if (legFigures(profile, fromMile, at).minutes < minutes) low = mid
    else high = mid
  }
  return direction === 'NOBO' ? fromMile + high : fromMile - high
}
