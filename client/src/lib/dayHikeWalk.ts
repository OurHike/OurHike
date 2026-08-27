// The walk itself: a saved day hike flattened into the ordered pieces of
// trail a hiker actually puts their feet on (#1041, frames `D9`-`D11`).
//
// WHY THIS IS A MODULE AND NOT A LOOP INSIDE THE TWO THINGS THAT NEED IT
//
// `dayHikeBailOuts` (lib/dayHikeCard.ts) already walks a resolved hike
// pair-by-pair to price its junctions, and its own comment says why it must:
// "an out-and-back walks parts of an edge twice while the deduplicated list
// holds it once, so pair-wise is the only accumulation whose 'mi 3.2' is the
// distance a hiker has actually walked when they reach the junction."
//
// Following a hike needs that same accumulation twice more - once to say
// where the next turn is (lib/dayHikeTurns.ts) and once to say where the
// hiker is (lib/dayHikeFollow.ts). Three copies of an accumulation this
// fiddly is three chances for the turn card to say "in 0.4 mi" over a header
// reading a different number for the same junction. So the walk is derived
// once, here, and the three consumers read it.
//
// A PIECE IS NOT AN EDGE, and the difference is what makes the miles right.
// An edge is a whole piece of tread between two junctions; a walk enters its
// first edge part-way along and leaves its last part-way along, and an
// out-and-back covers the same edge twice as two different moments in the
// day. So a `WalkStep` is one TRAVERSAL of one edge, carrying the fractions
// it actually covered and the metres walked before it started.
//
// WHAT IT DELIBERATELY DOES NOT DO: re-route. Everything here reads a
// `ResolvedDayHike` that lib/dayHikeCard.ts already produced against this
// phone's live graph, so a hike this graph cannot claim has already been
// refused whole, one layer down, rather than half-walked here.

import type { ResolvedDayHike } from './dayHikeCard'
import {
  cutPolyline,
  enteredNodes,
  hasVertices,
  metresToMiles,
  routeBetween,
  walkedMetresPerEdge,
  type TrailGraphIndex,
} from './trailGraph'

/** One traversal of one edge, in walking order. */
export interface WalkStep {
  edgeIndex: number
  /** The node this traversal is entered from - the orientation every bearing
   *  and every fraction below is measured against. */
  fromNode: number
  /** True when the traversal runs the edge's own `from` -> `to` direction.
   *  A published edge has one direction and a hiker may walk it either way. */
  forward: boolean
  /**
   * The junction this traversal ENDS at, or null when it ends at a tap
   * instead.
   *
   * Null is not an edge case to smooth over: #934's rule is that a tap splits
   * the segment, so the first and last piece of every tapped pair end mid-edge
   * by design. A turn can only happen where a hiker stands at a junction with
   * a choice, so `null` here means "no turn is possible at this boundary" and
   * lib/dayHikeTurns.ts reads exactly that.
   */
  junctionNode: number | null
  /** Fraction along the edge (from its own `from` end) where this traversal
   *  starts and ends. `endFraction` may be below `startFraction` - that is a
   *  backwards traversal, not a mistake. */
  startFraction: number
  endFraction: number
  /** Metres of tread this traversal covers. */
  metres: number
  /** Metres walked from the hike's first step to the START of this
   *  traversal. */
  beforeMetres: number
  /** Which of the hike's segments this belongs to. Segments are separated by
   *  deliberate gaps (#935), so nothing - not a leg, not a turn - continues
   *  across the boundary between two of them. */
  segment: number
}

/**
 * Every piece of the resolved hike, in walking order, or an empty list when
 * the graph cannot re-route one of its tapped pairs.
 *
 * The empty list is the honest shape of "this phone can say nothing about
 * this walk" and the callers all render nothing from it. It should be
 * unreachable in practice - `resolveDayHike` already refused a hike whose
 * pairs will not route - but the two re-route independently, and a half-walk
 * is the one thing this must never hand back.
 */
export function dayHikeWalk(
  index: TrailGraphIndex,
  resolved: ResolvedDayHike,
): WalkStep[] {
  const graph = index.graph
  const steps: WalkStep[] = []
  let walkedMetres = 0

  for (let at = 0; at < resolved.segments.length; at += 1) {
    const segment = resolved.segments[at]
    // The same wrap `dayHikeBailOuts` applies, and for the same reason: a
    // looped hike's walk home is real ground with real junctions on it, and
    // it is only ever the LAST segment that closes (lib/dayHikeCard.ts).
    const looped = resolved.looped && at === resolved.segments.length - 1
    const pairs = looped ? [...segment.points, segment.points[0]] : segment.points

    for (let step = 0; step + 1 < pairs.length; step += 1) {
      const from = pairs[step]
      const to = pairs[step + 1]
      const leg = routeBetween(index, from, to)
      if (leg === null) return []

      const edges = leg.edgeIndices
      const entered = enteredNodes(graph, edges, from, to)
      // The one arithmetic (#1002) both the card's bail-out miles and this
      // are priced from, rather than a second opinion about how much of an
      // edge a pair walks.
      const perEdge = walkedMetresPerEdge(graph, edges, from, to)

      for (let i = 0; i < edges.length; i += 1) {
        const edge = graph.edges[edges[i]]
        const fromNode = entered[i]
        const forward = fromNode === edge.from
        const single = edges.length === 1
        const first = i === 0
        const last = i === edges.length - 1

        // Mirrors walkedMetresPerEdge's own cases exactly: the ends of a pair
        // are trimmed to the taps and everything between is walked whole. Two
        // functions reading the same shape, which is why they are written to
        // the same three cases rather than to two different simplifications.
        const startFraction = single
          ? from.fraction
          : first
            ? from.fraction
            : forward
              ? 0
              : 1
        const endFraction = single ? to.fraction : last ? to.fraction : forward ? 1 : 0

        steps.push({
          edgeIndex: edges[i],
          fromNode,
          forward,
          // A traversal reaches a junction only where another edge of the
          // same pair follows it. The pair's last piece stops at the tap.
          junctionNode: last ? null : entered[i + 1],
          startFraction,
          endFraction,
          metres: perEdge[i],
          beforeMetres: walkedMetres,
          segment: at,
        })
        walkedMetres += perEdge[i]
      }
    }
  }

  return steps
}

/** Walked miles from the hike's first step to the end of the walk. */
export function walkMiles(steps: readonly WalkStep[]): number {
  const last = steps[steps.length - 1]
  return last === undefined ? 0 : metresToMiles(last.beforeMetres + last.metres)
}

/**
 * The stretch of trail one traversal actually covers, as its own vertices in
 * walking order - or null when this phone's graph carries none for that edge.
 *
 * NULL RATHER THAN THE CHORD, and that is the whole reason this exists
 * (#1044 review). `projectOntoEdge` falls back to the straight line between
 * two junctions when an edge has no vertices, which is right for accepting a
 * tap and wrong for everything lib/dayHikeFollow.ts does with it: across a
 * switchback that chord can run hundreds of metres from the tread, so a hiker
 * standing squarely on the trail measures as far off it. Refusing is the same
 * call lib/dayHikeTurns.ts's `armBearing` already makes in the same state.
 *
 * Cut to the WALKED span, not handed back whole. #934's rule is that a tap
 * splits the segment, so the first and last edge of every tapped pair are
 * partly walked - and a fix beside the unwalked half of one is not near this
 * walk at all.
 */
export function stepPolyline(
  index: TrailGraphIndex,
  step: WalkStep,
): Array<[number, number]> | null {
  const edge = index.graph.edges[step.edgeIndex]
  if (edge === undefined || !hasVertices(edge)) return null

  // Oriented so the list runs the way the hiker does. Fractions are measured
  // from the edge's own `from`, so a backwards traversal flips them with it.
  const forward = step.forward
  const coords = forward ? edge.geometry : [...edge.geometry].reverse()
  const from = forward ? step.startFraction : 1 - step.startFraction
  const to = forward ? step.endFraction : 1 - step.endFraction
  const low = Math.min(from, to)
  const high = Math.max(from, to)

  const cut = low <= 0 && high >= 1 ? coords : cutPolyline(coords, low, high)
  return cut.length >= 2 ? cut : null
}
