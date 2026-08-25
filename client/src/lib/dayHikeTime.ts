// What a day hike costs in walking time (#1008), or an honest nothing.
//
// ALL OR NOTHING, AND THAT IS THE WHOLE DESIGN. A day hike is a route across
// the junction graph, and this app's elevation is the A.T. corridor profile -
// which covers the centerline and nothing else. A walk that leaves the
// centerline for one edge has ground under it that nobody can price, and the
// two ways of handling that are both worse than silence:
//
//   - Price the unknown edge at zero ascent. That is a flat-ground claim
//     about real ground, and it always UNDERSTATES: the estimate comes back
//     short, which is the direction that gets somebody caught by the dark.
//   - Price the edges we know and print the total anyway. Same understatement
//     with a number attached, and no way for the reader to tell how much of
//     their walk it left out.
//
// So one unpriceable edge makes the whole walk unpriced, and the surfaces
// print no time rather than a low one. FEATURES.md's line is the rule here:
// "a confidently wrong prediction is more dangerous than an honest unknown",
// and an under-estimate of a day's walking is exactly that prediction.
//
// WHAT MAKES AN EDGE PRICEABLE TODAY: `source === 'centerline'`. That is
// pipeline/build_trail_graph.py's own name for the A.T. itself
// (`AT_GRAPH_SOURCES`), and it is the one thing in the graph that
// export_elevation.py measured. `side_trails` - the blue blazes, in the same
// graph and walkable - has no profile, so a hike onto one prices at nothing.
// When elevation for the other layers is published, this is the function that
// grows a second branch; every caller already handles the null.
//
// ONE THING THIS INHERITS AND DOES NOT FIX: a DEM coverage gap inside the
// walk. `legFigures` counts ascent through `cumulativeGainOverGaps`, which
// treats a NaN sample as a break in the run rather than as a climb - so a
// hole in the elevation data quietly costs the estimate whatever climb was
// under it. That is the A.T. planner's behaviour for its own days too, and
// this module goes through the same function deliberately so the two agree.
// Diverging here would price the same ground two ways depending on which
// screen asked; fixing it belongs in `legFigures`, for both.
//
// THE TWO MILE AXES (HIKE_PLANNING.md Finding 1). The profile is indexed on
// the PIPELINE's mile axis and the graph's coordinates resolve against the
// CLIENT index's, which do not agree. Every mile here is carried across with
// `anchoredMile` before it reaches the profile, and no anchors means no
// answer - a client-scale mile read against pipeline-scale samples is the
// mixed measurement lib/route.ts exists to prevent.

import type { ResolvedDayHike } from './dayHikeCard'
import type { ElevationProfile } from './elevationProfile'
import { type PaceProfile } from './pace'
import { anchoredMile, legFigures, type MileAnchor } from './route'
import { enteredNodes, type GraphPoint, type TrailGraphIndex } from './trailGraph'
import { mileOnTrail, type TrailIndex } from './trailPosition'

/** The A.T. itself, as pipeline/build_trail_graph.py labels it. The only
 *  graph source this phone holds elevation for. */
const PRICEABLE_SOURCE = 'centerline'

/** Everything the pricing needs that is not the route itself. Any of them
 *  missing is a null answer, not a guess. */
export interface DayHikeGround {
  /** The corridor profile, or null on a download without one. */
  profile: ElevationProfile | null
  /** The client's centerline index, for placing a graph node on the trail. */
  trailIndex: TrailIndex | null
  /** POI anchors carrying the client-to-pipeline mile correction. */
  anchors: readonly MileAnchor[]
}

/** A node's place on the PIPELINE mile axis, or null when it cannot be put
 *  there honestly. */
function pipelineMileOf(
  node: [number, number] | undefined,
  ground: DayHikeGround,
): number | null {
  if (node === undefined || ground.trailIndex === null) return null
  const clientMile = mileOnTrail(ground.trailIndex, { lon: node[0], lat: node[1] })
  if (clientMile === null) return null
  return anchoredMile(clientMile, ground.anchors)
}

/**
 * Naismith-family minutes for a routed day hike, or null when any step of it
 * cannot be priced.
 *
 * Runs through `legFigures`, which is what the A.T. planner's own days are
 * priced with - so a stretch of centerline walked as a day hike and the same
 * stretch walked as a trip day come out at the same number. Two copies of
 * this arithmetic is how they would stop agreeing without anybody deciding
 * it, which is the reason lib/naismith.ts gives for keeping one.
 */
export function dayHikeWalkingMinutes(
  resolved: ResolvedDayHike,
  index: TrailGraphIndex,
  ground: DayHikeGround,
  pace: PaceProfile,
): number | null {
  return walkingMinutesOver(
    resolved.segments.map((segment, at) => ({
      ...segment,
      // `resolveDayHike` closes the loop on the LAST segment and refuses a
      // multi-segment hike that asks to loop, so this mirrors its rule
      // rather than inventing a second one.
      looped: resolved.looped && at === resolved.segments.length - 1,
    })),
    index,
    ground,
    pace,
  )
}

/** One walked stretch: where the walk entered and left, and the edges between.
 *  The narrowest thing this pricing needs, so the builder's live draft (which
 *  has a route and its own points, and is not a saved hike yet) and a resolved
 *  saved hike can both be priced by the same arithmetic. */
export interface PricedStretch {
  points: readonly GraphPoint[]
  route: { edgeIndices: number[] }
  /** Whether the route was closed back to its first tap. Load-bearing: a
   *  looped walk's last edge ends at `points[0]`, NOT at the last tap, so
   *  taking the final fraction from the wrong end mis-prices the stretch
   *  home. */
  looped: boolean
}

/** The same answer for a walk that is not a saved hike yet. */
export function walkingMinutesOver(
  stretches: readonly PricedStretch[],
  index: TrailGraphIndex,
  ground: DayHikeGround,
  pace: PaceProfile,
): number | null {
  const { profile } = ground
  if (profile === null) return null

  let minutes = 0
  for (const segment of stretches) {
    const miles = walkedMiles(segment, index, ground)
    if (miles === null) return null
    // legFigures reads its window in walk order, so a slope walked downhill
    // is not charged as the climb it would be walked the other way.
    for (const [from, to] of monotonicRuns(miles)) {
      minutes += legFigures(profile, from, to, pace).minutes
    }
  }

  return Number.isFinite(minutes) ? minutes : null
}

/**
 * The pipeline miles the walk passes through, in order: where it starts, then
 * every node it leaves, ending where it stops.
 *
 * Null the moment any of it cannot be placed on the profile's axis.
 */
function walkedMiles(
  segment: PricedStretch,
  index: TrailGraphIndex,
  ground: DayHikeGround,
): number[] | null {
  const { edgeIndices } = segment.route
  if (edgeIndices.length === 0) return null
  const from = segment.points[0]
  // A closed loop finishes where it started; an open walk finishes at its
  // last tap.
  const to = segment.looped ? from : segment.points[segment.points.length - 1]
  const entered = enteredNodes(index.graph, edgeIndices, from, to)

  const miles: number[] = []
  for (let at = 0; at < edgeIndices.length; at += 1) {
    const edge = index.graph.edges[edgeIndices[at]]
    if (edge === undefined || edge.source !== PRICEABLE_SOURCE) return null

    const fromMile = pipelineMileOf(index.graph.nodes[edge.from], ground)
    const toMile = pipelineMileOf(index.graph.nodes[edge.to], ground)
    if (fromMile === null || toMile === null) return null

    // `fraction` runs from->to along the edge whichever way it is walked, so
    // the miles interpolate on that axis and the direction falls out of which
    // end the walk enters by.
    const mileAt = (fraction: number) => fromMile + (toMile - fromMile) * fraction
    const forward = entered[at] === edge.from
    const first = at === 0
    const last = at === edgeIndices.length - 1

    if (first) miles.push(mileAt(from.fraction))
    miles.push(mileAt(last ? to.fraction : forward ? 1 : 0))
  }
  return miles
}

/**
 * The walk split into its uphill and downhill runs - maximal spans that do
 * not change direction.
 *
 * ONE CALL PER RUN, NEVER ONE PER EDGE, and the difference is ascent that
 * goes missing. A profile window ends at the last sample at or before its
 * end mile, and the next window starts at the first sample at or after its
 * start mile - so a run cut at every node drops the climb between those two
 * samples at every cut. Measured on this module's own fixture: three
 * centerline edges summed edge by edge came out 100 ft of ascent and three
 * minutes short of the same three miles taken whole, purely from the two
 * internal joins. Short is the dangerous direction.
 */
function monotonicRuns(miles: readonly number[]): Array<[number, number]> {
  const runs: Array<[number, number]> = []
  let start = miles[0]
  let direction = 0
  for (let at = 1; at < miles.length; at += 1) {
    const step = Math.sign(miles[at] - miles[at - 1])
    if (step === 0) continue
    if (direction !== 0 && step !== direction) {
      runs.push([start, miles[at - 1]])
      start = miles[at - 1]
    }
    direction = step
  }
  const end = miles[miles.length - 1]
  if (start !== end) runs.push([start, end])
  return runs
}
