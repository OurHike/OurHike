// Where a hiker is on the day hike they are following, and what to say when
// they are not on it at all (#1041, frames `D9` and `D11`).
//
// A DAY HIKE HAS NO MILE AXIS, WHICH IS THE WHOLE REASON THIS EXISTS.
//
// The map screen's position line is `mi 486.2 · NOBO` (lib/positionLine.ts),
// and both halves of that are meaningless in a park: #928's finding is that a
// network has no single axis to number, and a loop has no compass direction
// to be walking in. What a hiker following a route can be told instead is
// their distance along THEIR OWN walk - "2.4 mi in · 3.8 to go" - which is
// the same arithmetic measured from their first step rather than from
// Springer.
//
// THE FIX IS PROJECTED ONTO THE ROUTE, NOT ONTO THE NETWORK.
//
// `nearestPointOnGraph` answers "which trail am I on", and a hiker standing
// at a junction is on four. The question here is narrower and has to be:
// "where am I on the walk I said I was doing". So the projection runs over
// the route's own traversals (lib/dayHikeWalk.ts) and a fix 300 ft away on a
// different blazed trail comes back as OFF the route, which is exactly what
// it is.
//
// HYSTERESIS RATHER THAN A TIMER, and it is doing real work. A single
// threshold flips this state every time a fix wobbles across it under
// canopy, and a banner that appears and vanishes twice a minute is a banner
// nobody reads - the same "cry wolf" failure lib/wrongWay.ts's persistence
// window exists to prevent. Going OFF takes {@link OFF_ROUTE_FEET}; coming
// back ON takes the tighter {@link BACK_ON_ROUTE_FEET}, so the boundary
// itself is never a place the state can oscillate. No clock, no trace, no
// stored history: the caller hands back the previous answer and this stays a
// pure function of two fixes.
//
// WHAT IT REFUSES TO SAY. Off the route, this reports the nearest point OF
// THE ROUTE with a straight-line distance and a bearing, and nothing about
// how to get there. There is no marked trail between a hiker in the laurel
// and their route - if there were, they would be on it - so a routed line
// across that ground would be the app drawing a path where none exists.
// Frame `D11` makes that refusal the point of the screen and
// chrome/OffRouteCard.tsx prints it in words.

import { dayHikeWalk, stepPolyline, walkMiles, type WalkStep } from './dayHikeWalk'
import type { ResolvedDayHike } from './dayHikeCard'
import {
  bearingDegrees,
  metresToMiles,
  sameTrail,
  type LonLat,
  type TrailGraphIndex,
} from './trailGraph'
import { formatDistance, formatShortDistance, type UnitSystem } from './units'

/**
 * How far off the route a hiker gets before the screen says so.
 *
 * The same NUMBER `lib/wrongWay.ts` uses for `OFF_TRAIL_THRESHOLD_FT`, and
 * not the same measurement - which is a correction to what this comment used
 * to claim.
 *
 * It said the two "answer the same question", so sharing the constant kept
 * the off-route band and the wrong-way cue on screen at the same moment. That
 * is not true and cannot be made true by choosing the number differently.
 * `wrongWay.ts` states its input as a CONTRACT: it is fed
 * `TrailFix.offTreadFeet`, the distance to the nearest mapped tread of ANY
 * kind, and it says which of the two it must be, because fed the centerline
 * distance instead it fires at roughly three shelter stops in four. This
 * module measures to ONE route's own tread. So a hiker who takes the wrong
 * arm at a fork is 0 ft from mapped tread - silent by that contract, and
 * correctly so - while walking steadily past this threshold. Two surfaces,
 * two events, one number.
 *
 * The number is still borrowed rather than picked afresh, because 90 ft is
 * the only figure anybody here has written down for "off the tread you meant
 * to be on", and inventing a second would be a second unmeasured number.
 *
 * @unvalidated by inheritance, and the inherited caveat travels with it -
 * that constant is a WIREFRAMES.md mock-up placeholder, not a validated
 * HIKER_SAFETY.md figure, and §5 declines to guess pending field testing
 * under tree canopy. What would settle it is the same field test, run against
 * a route rather than against the corridor.
 */
export const OFF_ROUTE_FEET = 90

/**
 * How close a hiker has to get before the screen says they are back on it.
 *
 * @unvalidated Picked as half of OFF_ROUTE_FEET. What it has to be is
 * *enough tighter* that a fix sitting on the boundary cannot flip the state
 * on GPS noise alone; how much tighter is the measurement nobody has: the
 * width of that noise under canopy, which is the same field test above.
 */
export const BACK_ON_ROUTE_FEET = 45

/** Which leg of the walk a hiker is on - the header's "leg 2 of 3". */
export interface FollowedLeg {
  /** 1-based, so it prints as a hiker counts. */
  at: number
  of: number
  name: string | null
  blaze_color: string | null
  source: string | null
}

export interface OnRoute {
  kind: 'on-route'
  /** Miles walked along the route to reach here. */
  walkedMi: number
  /** Miles of route still ahead. */
  toGoMi: number
  totalMi: number
  /** How far off the line the fix fell - inside OFF_ROUTE_FEET by
   *  definition, and carried because it is the honest width of the claim
   *  above it. */
  offRouteFeet: number
  leg: FollowedLeg
  /** Where on the route the fix projected, for anything that draws it. */
  at: LonLat
}

export interface OffRoute {
  kind: 'off-route'
  offRouteFeet: number
  /** The nearest point OF THE ROUTE, and nothing about reaching it. */
  nearest: {
    walkedMi: number
    feet: number
    /** Degrees clockwise from north, from the hiker toward that point. */
    bearingDeg: number
    at: LonLat
  }
  totalMi: number
}

export type FollowState = OnRoute | OffRoute

export interface FollowInputs {
  index: TrailGraphIndex
  resolved: ResolvedDayHike
  /** The hiker's fix, or null when there is not one. */
  at: LonLat | null
  /**
   * The last answer this returned, when there is one.
   *
   * Two jobs, both of which need the caller's memory rather than a clock.
   * It supplies the hysteresis above, and it disambiguates an out-and-back:
   * a fix half a mile along a trail walked twice matches two moments in the
   * day, and the honest tie-break is the one nearer to where the hiker
   * already was. With no previous answer the earlier moment wins, which is
   * where a walk starts.
   */
  previous?: FollowState | null
}

/**
 * Where the hiker is on their route, or null when nothing can be said - no
 * fix, a walk this graph cannot re-route, or an edge of it this phone has no
 * vertices for.
 *
 * Null rather than a zeroed position: "0.0 mi in" is a claim that somebody is
 * standing at the trailhead.
 *
 * THE GEOMETRY IS A REQUIREMENT, not a nicety. Without an edge's own vertices
 * the only line available is the chord between its two junctions, and across
 * a switchback that runs far enough from the tread to raise "You are not on
 * your route" at a hiker standing on it - a false safety alert, which is the
 * one failure this module exists to prevent. lib/dayHikeTurns.ts withholds a
 * turn's SIDE in the same state; this withholds the whole answer, because
 * there is no part of it the chord does not poison. The caller loads the
 * geometry artifact whenever a hike is being followed.
 */
export function followDayHike({
  index,
  resolved,
  at,
  previous = null,
}: FollowInputs): FollowState | null {
  if (at === null) return null
  const steps = dayHikeWalk(index, resolved)
  if (steps.length === 0) return null

  const totalMi = walkMiles(steps)

  // One candidate per traversal, priced at the miles that traversal is
  // reached at - so the two passes of an out-and-back stay two answers.
  //
  // EVERY ONE OF THEM MEASURED AGAINST THE GROUND THE HIKER WALKS, not
  // against the whole edge it is part of. Two faults this replaces, both
  // found reviewing #1044 and both of them a confident wrong answer:
  //
  //  - the distance used to come from a projection onto the ENTIRE edge, so
  //    a fix beside the unwalked half of a partly-walked edge read as
  //    on-route at zero feet off;
  //  - and where no vertices were published it came off the chord between two
  //    junctions, which across a switchback runs hundreds of metres from the
  //    tread - raising "You are not on your route" at somebody standing on it.
  //
  // A walk with an unmeasured edge is refused whole rather than half-priced,
  // the same all-or-nothing `ResolvedDayHike.climb` applies one layer down.
  const candidates: Array<{
    position: number
    walkedMi: number
    feet: number
    at: LonLat
  }> = []
  for (let position = 0; position < steps.length; position += 1) {
    const step = steps[position]
    const walked = stepPolyline(index, step)
    if (walked === null) return null
    const onIt = nearestOnPolyline(walked, at)
    candidates.push({
      position,
      // Scaled to the metres the pipeline measured for this traversal rather
      // than to the polyline's own length: `length_m` is EPSG:5070 and these
      // vertices are lon/lat, and every other mile in this app comes from the
      // former. One axis, so the header and the turn list agree.
      walkedMi: metresToMiles(
        step.beforeMetres +
          (onIt.alongFraction === 0 ? 0 : onIt.alongFraction * step.metres),
      ),
      feet: onIt.feet,
      at: onIt.at,
    })
  }

  const threshold =
    previous !== null && previous.kind === 'off-route'
      ? BACK_ON_ROUTE_FEET
      : OFF_ROUTE_FEET

  const near = candidates.filter((candidate) => candidate.feet <= threshold)
  if (near.length > 0) {
    const since = previous === null ? 0 : walkedMiOf(previous)
    // Nearest to where the hiker already was, which is continuity rather
    // than a guess: a walk does not teleport between two passes of one edge.
    //
    // ON THE FIRST FIX THERE IS NO "ALREADY WAS", and `since` of 0 makes this
    // pick the EARLIEST pass. That is a guess, and it is the cautious one on
    // purpose: the earliest pass reports the most walk still to come, so
    // somebody who pressed Follow half way round an out-and-back is told they
    // have further to go rather than less. Rounding toward more work left is
    // the same direction Naismith is left rounding here, and for the same
    // reason - the other error is the one that gets somebody benighted.
    //
    // @unvalidated that a guess is the right answer at all. What would settle
    // it: two fixes give a direction of travel, which distinguishes the
    // passes outright, and the shell already holds the previous answer this
    // would need. Until then the first reading of an out-and-back can be a
    // whole walk out of date, and nothing on screen says so.
    const chosen = near.reduce((best, candidate) =>
      Math.abs(candidate.walkedMi - since) < Math.abs(best.walkedMi - since)
        ? candidate
        : best,
    )
    return {
      kind: 'on-route',
      walkedMi: chosen.walkedMi,
      toGoMi: Math.max(0, totalMi - chosen.walkedMi),
      totalMi,
      offRouteFeet: chosen.feet,
      leg: legAt(index, steps, chosen.position),
      at: chosen.at,
    }
  }

  const nearest = candidates.reduce((best, candidate) =>
    candidate.feet < best.feet ? candidate : best,
  )
  return {
    kind: 'off-route',
    offRouteFeet: nearest.feet,
    nearest: {
      walkedMi: nearest.walkedMi,
      feet: nearest.feet,
      bearingDeg: bearingDegrees(at, nearest.at),
      at: nearest.at,
    },
    totalMi,
  }
}

/** The walked miles a state stands at, for the continuity tie-break. */
function walkedMiOf(state: FollowState): number {
  return state.kind === 'on-route' ? state.walkedMi : state.nearest.walkedMi
}

/**
 * The nearest point on one walked stretch, how far off it the fix is, and how
 * far along that stretch it lands.
 *
 * Its own loop rather than `projectOntoEdges`, because the question is
 * different: that one asks "where on this EDGE", and every consumer here
 * needs "where on the part of it this walk covers". The arithmetic is
 * lib/trailGraph.ts's own - equirectangular metres, closest point per span -
 * over the vertices lib/dayHikeWalk.ts already cut to the walked stretch.
 */
function nearestOnPolyline(
  coords: ReadonlyArray<[number, number]>,
  at: LonLat,
): { feet: number; at: LonLat; alongFraction: number } {
  let best: { metres: number; at: LonLat; along: number } | null = null
  let walked = 0
  let total = 0

  for (let step = 0; step + 1 < coords.length; step += 1) {
    const start: LonLat = { lon: coords[step][0], lat: coords[step][1] }
    const end: LonLat = { lon: coords[step + 1][0], lat: coords[step + 1][1] }
    const span = localSpan(start, end)
    const length = Math.hypot(span.x, span.y)
    const offset = localSpan(start, at)

    let along = 0
    if (length > 0) {
      along = (offset.x * span.x + offset.y * span.y) / (length * length)
      along = Math.min(1, Math.max(0, along))
    }
    const off = Math.hypot(offset.x - span.x * along, offset.y - span.y * along)
    if (best === null || off < best.metres) {
      best = {
        metres: off,
        at: {
          lon: start.lon + (end.lon - start.lon) * along,
          lat: start.lat + (end.lat - start.lat) * along,
        },
        along: walked + length * along,
      }
    }
    walked += length
    total += length
  }

  // A degenerate stretch - every vertex on one spot. Real in a graph where a
  // junction can be metres from the next; the point is still the point.
  if (best === null || total === 0) {
    const only: LonLat = { lon: coords[0][0], lat: coords[0][1] }
    return { feet: metresBetween(only, at) * FEET_PER_METRE, at: only, alongFraction: 0 }
  }
  return {
    feet: best.metres * FEET_PER_METRE,
    at: best.at,
    alongFraction: best.along / total,
  }
}

const EARTH_RADIUS_M = 6_378_137
const FEET_PER_METRE = 3.280839895

/** Equirectangular metres between two points, on lib/trailGraph.ts's own
 *  projection and for its own reason: every comparison here is local, over a
 *  few hundred metres at most. */
function localSpan(from: LonLat, to: LonLat): { x: number; y: number } {
  const meanLatitude = ((from.lat + to.lat) / 2) * (Math.PI / 180)
  return {
    x: (to.lon - from.lon) * (Math.PI / 180) * EARTH_RADIUS_M * Math.cos(meanLatitude),
    y: (to.lat - from.lat) * (Math.PI / 180) * EARTH_RADIUS_M,
  }
}

function metresBetween(from: LonLat, to: LonLat): number {
  const span = localSpan(from, to)
  return Math.hypot(span.x, span.y)
}

/**
 * Which leg one traversal falls in, counted the way lib/trailGraph.ts counts
 * them: consecutive traversals of one trail merge, INCLUDING across the join
 * between two tapped pairs (`routeThrough` merges there too), and never
 * across a segment boundary (`resolveDayHike` flat-maps its segments, so each
 * starts a leg of its own).
 *
 * Derived from the same walk rather than read off `resolved.legs`, because
 * that list has no positions in it - it says a hike has three legs and not
 * which traversal is in which. The rule is the shared `sameTrail` predicate,
 * so the count here and the count there are the same count.
 */
function legAt(
  index: TrailGraphIndex,
  steps: readonly WalkStep[],
  position: number,
): FollowedLeg {
  const graph = index.graph
  let at = 0
  let count = 0
  for (let i = 0; i < steps.length; i += 1) {
    const edge = graph.edges[steps[i].edgeIndex]
    const previous = i === 0 ? null : steps[i - 1]
    const continues =
      previous !== null &&
      previous.segment === steps[i].segment &&
      sameTrail(graph.edges[previous.edgeIndex], edge)
    if (!continues) count += 1
    if (i === position) at = count
  }
  const edge = graph.edges[steps[position].edgeIndex]
  return {
    at,
    of: count,
    name: edge.name,
    blaze_color: edge.blaze_color,
    source: edge.source,
  }
}

/**
 * The header's two strings for a followed hike, or null when nothing is being
 * followed.
 *
 * The mode signal costs ZERO pixels, which is frame `D9`'s point: it is the
 * header's own eyebrow saying "Day hike" where it usually says the trail's
 * name, not a new band. features/MAP_CHROME.md §2 holds every band on this
 * screen to earning its 249 px, and a strip whose only job is to say which
 * mode you are in would not.
 */
export function followHeader({
  following,
  follow,
  atJunction = false,
}: {
  /** Whether a hike is being followed at all. Separate from `follow`, which
   *  is null for the ordinary reason that no fix has arrived yet: a hiker who
   *  pressed Follow and is waiting for GPS is still in this mode, and an
   *  eyebrow that flipped back to the trail's name while they waited would be
   *  the screen forgetting what they just asked for. */
  following: boolean
  follow: FollowState | null
  atJunction?: boolean
}): { trailName: string; state: string | undefined } | null {
  if (!following) return null
  if (follow === null) return { trailName: 'Day hike', state: undefined }
  if (follow.kind === 'off-route') {
    return { trailName: 'Day hike', state: 'off the route' }
  }
  if (atJunction) return { trailName: 'Day hike', state: 'at a junction' }
  const leg = `leg ${follow.leg.at} of ${follow.leg.of}`
  return {
    trailName: 'Day hike',
    state: follow.leg.name === null ? leg : `${leg} · ${follow.leg.name}`,
  }
}

/**
 * The position line for a followed hike - the one thing in the header's mono
 * slot that says where somebody is.
 *
 * Both readings are DISTANCES the hiker has covered or has left, so both
 * convert with the preference. The A.T. reading this replaces does not and
 * must not: `mi 486.2` is a name on the published axis rather than a
 * measurement of anything, and "km 782.4" would be a milepost that does not
 * exist on any sign or in any guidebook.
 */
export function followPosition(follow: FollowState, units: UnitSystem): string {
  if (follow.kind === 'off-route') {
    return `${formatShortDistance(follow.offRouteFeet, units)} off your route`
  }
  return `${formatDistance(follow.walkedMi, units)} in · ${formatDistance(
    follow.toGoMi,
    units,
  )} to go`
}

const COMPASS = [
  'north',
  'north-east',
  'east',
  'south-east',
  'south',
  'south-west',
  'west',
  'north-west',
] as const

/**
 * Eight points rather than sixteen, and rather than the degrees themselves.
 *
 * A hiker holding a phone that has just told them they are 300 ft from their
 * route is reading this to point their body, and "north-north-east" is a
 * precision neither the fix nor the person has. Eight points is 45 degrees
 * wide, which is about the width of the answer.
 */
export function compassPoint(bearingDeg: number): string {
  const index = Math.round((((bearingDeg % 360) + 360) % 360) / 45) % 8
  return COMPASS[index]
}
