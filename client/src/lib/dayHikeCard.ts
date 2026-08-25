// What the finished-hike card derives, and from where (#980, frame `1l`).
//
// A SAVED day hike stores its tapped ends and a cache of figures - never a
// route (lib/dayHikes.ts's header has the whole argument). So everything this
// card shows about the ground is re-derived here, at open time, against
// whatever graph THIS phone holds now, through the same `nearestPointOnGraph`
// projection a fresh tap uses. A republished graph that can no longer claim
// an end fails the WHOLE resolution rather than quietly rerouting part of the
// walk - the refusal-over-reassignment rule the store enforces at its read
// boundary, applied at the next layer up.
//
// BAIL-OUTS ARE TRAILS ONLY, AND SAY SO WHEN THERE ARE NONE. The maintainer's
// call, recorded in #980: "There should be no guessing as to whether something
// is walkable or not" (#935). Every departure listed here is an edge of the
// junction graph, which holds nothing but trails the three organizations
// maintain - a road shoulder cannot appear because roads are not in the graph
// (#931 ships as the bar's LATER row). An empty list is an answer the card
// must print, not omit: "no marked way off this stretch" is the most
// safety-relevant sentence on the card.
//
// What a bail-out row does NOT claim, deliberately: where the trail comes out,
// how long it runs, or how far down it drops. Frame `1l` writes "Kakiat Trail
// down to Route 202 · 1.1 mi · −640 ft" - the destination needs road data
// (#931), the descent needs elevation no network trail has. Until those exist
// the row is the junction's mile, the trail's name and its blaze: everything
// the graph actually knows.

import type { DayHike } from './dayHikes'
import {
  enteredNodes,
  walkedMetresPerEdge,
  nearestPointOnGraph,
  metresToMiles,
  routeBetween,
  routeThrough,
  closeTheLoop,
  type GraphPoint,
  type GraphRoute,
  type RouteLeg,
  type TrailGraphIndex,
} from './trailGraph'

export interface ResolvedSegment {
  /** The stored ends, re-claimed by the live graph. */
  points: GraphPoint[]
  route: GraphRoute
}

export interface ResolvedDayHike {
  segments: ResolvedSegment[]
  /** Walked-trail miles, summed across segments. Gaps between segments add
   *  ground this app has no evidence for and contribute nothing. */
  miles: number
  legs: RouteLeg[]
  /** Whether the last segment was routed back to its first tap - carried
   *  here so the bail-out walk enumerates the same pairs the route used,
   *  rather than re-deriving the answer from a shape that cannot hold it. */
  looped: boolean
}

/**
 * The saved hike against the live graph, or null when this phone's current
 * trail map cannot honestly carry it - an end no edge claims within the tap
 * tolerance, or ends the network no longer connects. The caller says so and
 * falls back to the STORED figures, which are labelled as the cache they are.
 */
export function resolveDayHike(
  index: TrailGraphIndex,
  hike: DayHike,
): ResolvedDayHike | null {
  const segments: ResolvedSegment[] = []
  let milesTotal = 0

  for (let at = 0; at < hike.segments.length; at += 1) {
    const points: GraphPoint[] = []
    for (const end of hike.segments[at]) {
      const point = nearestPointOnGraph(index, {
        lon: end.coord[0],
        lat: end.coord[1],
      })
      if (point === null) return null
      points.push(point)
    }
    if (points.length < 2) return null

    // `looped` closes the walk back to its first tap. The builder only makes
    // single-segment hikes today, so the flag is only ever asked to close one
    // segment; a multi-segment looped hike (a future client, via sync) has no
    // defined geometry for "back to the start" across a gap, and resolving it
    // unlooped would print miles that contradict the stored figures - so it
    // takes the null path and the card falls back to the cache.
    const looped = hike.looped && at === hike.segments.length - 1
    if (looped && hike.segments.length > 1) return null
    const route = looped ? closeTheLoop(index, points) : routeThrough(index, points)
    if (route === null) return null

    segments.push({ points, route })
    milesTotal += route.miles
  }

  return {
    segments,
    miles: milesTotal,
    legs: segments.flatMap((segment) => segment.route.legs),
    looped: hike.looped,
  }
}

/** One marked way off the route: the junction's walked mile, and the trail
 *  that leaves there - nothing the graph does not know (see the header). */
export interface BailOut {
  /** Walked-trail miles from the hike's start to this junction. */
  miles: number
  name: string | null
  blaze_color: string | null
  source: string | null
}

/**
 * Every junction along the walk where a maintained trail the route does not
 * use departs, in walking order, with the miles walked to reach it.
 *
 * Accumulated PER TAPPED PAIR rather than over a segment's deduplicated edge
 * list, because the two disagree exactly where it matters: an out-and-back
 * walks parts of an edge twice while the deduplicated list holds it once, so
 * pair-wise is the only accumulation whose "mi 3.2" is the distance a hiker
 * has actually walked when they reach the junction. A junction passed twice
 * appears twice, at two different miles - both are real chances to get off.
 */
export function dayHikeBailOuts(
  index: TrailGraphIndex,
  resolved: ResolvedDayHike,
): BailOut[] {
  const graph = index.graph
  const out: BailOut[] = []
  let walkedMetresBefore = 0

  for (let at = 0; at < resolved.segments.length; at += 1) {
    const segment = resolved.segments[at]
    const looped = resolved.looped && at === resolved.segments.length - 1
    const pairs = looped ? [...segment.points, segment.points[0]] : segment.points

    // Edges walked anywhere in this segment, for "does the route use it".
    const onRoute = new Set(segment.route.edgeIndices)

    for (let step = 0; step + 1 < pairs.length; step += 1) {
      const from = pairs[step]
      const to = pairs[step + 1]
      const leg = routeBetween(index, from, to)
      if (leg === null) continue

      const edges = leg.edgeIndices
      const entered = enteredNodes(graph, edges, from, to)
      // The pair's per-edge walked metres, from the same helper that prices
      // the route's legs (#1002) - one arithmetic, two consumers, no drift.
      const walkedPerEdge = walkedMetresPerEdge(graph, edges, from, to)

      let walked = walkedMetresBefore
      for (let i = 0; i < edges.length; i += 1) {
        walked += walkedPerEdge[i]

        // The junction between this edge and the next, reached at `walked`
        // metres... minus the last edge's partial, which ends at the tap, not
        // at a node. So the junction after edge i exists only while i+1 does.
        if (i + 1 >= edges.length) continue
        const junction = entered[i + 1]

        const seenTrails = new Set<string>()
        for (const neighbour of index.adjacency[junction] ?? []) {
          if (onRoute.has(neighbour.edgeIndex)) continue
          const departing = graph.edges[neighbour.edgeIndex]
          // A trail CROSSING the junction contributes an edge on each side;
          // one trail is one way off, so both collapse onto one row.
          const identity = departing.trail_id ?? `${departing.name}|${departing.source}`
          if (seenTrails.has(identity)) continue
          seenTrails.add(identity)
          out.push({
            miles: metresToMiles(walked),
            name: departing.name,
            blaze_color: departing.blaze_color,
            source: departing.source,
          })
        }
      }
      walkedMetresBefore = walked
    }
  }

  return out
}
