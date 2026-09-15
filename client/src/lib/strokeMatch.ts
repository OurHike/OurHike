// Turning a drawn line into stretches of real trail (#983, frame `1k`).
//
// > Drag to draw. We'll put it on the trails and tell you what moved.
//
// THIS IS NOT N CALLS TO nearestPointOnGraph, AND THAT IS THE WHOLE MODULE.
//
// Matching each sample independently is the obvious implementation and it
// produces a walk nobody took. Through Harriman-Bear Mountain 64.3% of points
// on a trail have a second marked trail within #935's 25 m (measured against
// the published network, 2026-08-27 - features/HIKE_PLANNING.md carries the
// table), so a stroke drawn along one trail flickers between it and its
// neighbours sample by sample, and the leg list that comes out names four
// trails for a walk down one.
//
// So the rule is CONTINUITY: a stroke stays on the trail it is already on for
// as long as that trail is still a candidate. Changing trail is a decision the
// stroke has to earn by leaving the old one behind, which is what a hiker
// turning at a junction actually does.
//
// WHAT IT REFUSES, AND WHAT REFUSING MEANS HERE
//
// A run of samples with no trail within 25 m ends a stretch (#935's decided
// model). It is not an error and not a hole in a route: the next stretch
// begins where trail resumes, and the gap belongs to the hiker, who may well
// be planning to bushwhack it. Nothing in this module ever bridges one.
//
// AND WHAT IT ASKS ABOUT
//
// Where a stretch could plausibly have run along either of two trails that are
// NOT the same tread, the answer is a question rather than a guess - #935's
// other half. This module reports the ambiguity; the shell asks. See
// {@link StrokeMatch} and lib/trailGraph.ts's `trailChoice`.
//
// EVERY NUMBER IN HERE IS @unvalidated, and the reason is the same one #935
// gives: nobody has drawn on this outdoors. What is measured is the shape of
// the published data, not the shape of a real hand.

import {
  DRAWN_SNAP_METRES,
  SAME_TREAD_METRES,
  askableIdentity,
  askableName,
  trailsNear,
  type GraphPoint,
  type LonLat,
  type TrailGraphIndex,
} from './trailGraph'

/**
 * How far apart two samples have to be before the second one is worth asking
 * about.
 *
 * A finger dragged across a phone emits samples far denser than the trail
 * data underneath them - the published network's MEDIAN edge is 68 m long
 * (data.ourhike.org, 2026-08-27) - so matching every sample asks the same
 * question of the same edge dozens of times for one answer.
 *
 * @unvalidated. 10 m is a fraction of the 25 m match radius, so decimating to
 * it cannot skip past a trail the stroke actually touched: any trail within
 * reach of a dropped sample is within reach of one of its neighbours. That
 * bound is the argument; the exact value is not measured, and what would
 * settle it is somebody drawing on a phone.
 */
export const STROKE_SAMPLE_METRES = 10

/**
 * How much nearer another trail has to be before the stroke leaves the one it
 * is on.
 *
 * THE CONTINUITY RULE IS RELATIVE, NOT AN INFLATED RADIUS, and the first
 * attempt at this got it wrong in a way worth recording. Holding a trail out
 * to twice the match radius (50 m) reads as harmless and is not: through
 * Harriman-Bear Mountain marked trails routinely run within 25 m of each
 * other, so a 50 m hold means a stroke can never move onto the neighbour at
 * all - the hiker draws a turn and the app insists they are still on the first
 * trail. Stickiness that cannot be overcome is not continuity, it is a
 * different bug.
 *
 * So the trail in hand wins TIES and near-ties, and loses to a trail that is
 * clearly nearer. It is still subject to the 25 m match radius like anything
 * else: a held trail that has left that radius is gone whatever the margin
 * says.
 *
 * @unvalidated. What can be argued rather than measured: the margin has to
 * exceed the metre-by-metre noise of a fingertip (or the choice flips
 * sample to sample) and stay well under the 25 m radius (or it swallows the
 * radius and becomes the bug above). 10 m sits between. What would settle it
 * is a real drawn stroke through a corridor where two trails run close, which
 * is #935's own outstanding field test.
 */
export const STROKE_HOLD_MARGIN_METRES = 10

const EARTH_RADIUS_M = 6_378_137
const FEET_PER_METRE = 3.280839895

/** Equirectangular metres - the same approximation, and the same reasoning,
 *  that lib/trailGraph.ts uses for every local distance. */
function metresBetween(from: LonLat, to: LonLat): number {
  const midLat = ((from.lat + to.lat) / 2) * (Math.PI / 180)
  const x = (to.lon - from.lon) * (Math.PI / 180) * EARTH_RADIUS_M * Math.cos(midLat)
  const y = (to.lat - from.lat) * (Math.PI / 180) * EARTH_RADIUS_M
  return Math.hypot(x, y)
}

/**
 * Which trail a candidate belongs to, for the purpose of "is this still the
 * same trail".
 *
 * The name-and-blaze identity lib/trailGraph.ts's `trailsNear` groups on, not
 * `trail_id`: a publisher splits one trail into many lines, and a stroke that
 * ran the length of the Pine Meadow Trail crosses several of them without
 * ever leaving the trail.
 *
 * NOW ONE HELPER RATHER THAN TWO COPIES (#1444). This function reimplemented
 * `askableIdentity` line for line - the same `null`-only guard, the same
 * `source\0name\0blaze` key, a different NUL escape - so the drawn-stroke
 * path and the tap path could disagree about which trail a hiker meant, and
 * did: a name that is only whitespace is not `null`, and 12,510 of the
 * network's 631,915 edges carry one. Both read `edge.name` directly, so
 * fixing either alone would have left the other wrong. The separator argument
 * the two copies shared lives with the helper now; what mattered about it was
 * that a literal NUL byte made this file BINARY to git, so `git diff`
 * answered "Binary files differ" and a review of any change here saw nothing.
 */
function trailKeyOf(index: TrailGraphIndex, point: GraphPoint): string {
  return askableIdentity(index.graph.edges[point.edgeIndex], point.edgeIndex)
}

/** One stretch of a matched stroke: the trail it ran along, and the points on
 *  it in walking order. */
export interface StrokeStretch {
  /** The points, on the trail, in the order the stroke visited them. */
  points: GraphPoint[]
  /** The trail's own name, for the sentence the shell prints. Null for a
   *  piece nobody named. */
  name: string | null
  blaze_color: string | null
  source: string | null
  /**
   * Other trails this stretch could have been, when the stroke was genuinely
   * ambiguous about it - #935's ask. Empty when it was not.
   *
   * The alternatives are held here rather than resolved, because resolving
   * them is the hiker's to do. A shell that ignored this field would be
   * choosing between two real trails on a margin of metres and saying
   * nothing, which is the failure #935 exists to prevent.
   */
  alternatives: GraphPoint[]
  /**
   * The other trails running on THIS SAME TREAD, named rather than discarded.
   *
   * NOT an ambiguity, which is why it is a separate field from
   * `alternatives`: these are trails the hiker is on at the same time, not
   * trails they might be on instead. Through Harriman the A.T. runs
   * concurrently with Ramapo-Dunderberg (red), 1777 East (white) and the Long
   * Path (aqua), and OPRHP publishes its own line over ground ATC's
   * centerline already covers.
   *
   * WHY IT IS WORTH CARRYING. Measured over 300 synthetic strokes drawn along
   * real Harriman trails with 8 m of jitter (2026-08-27), 41.7% came back
   * naming a trail other than the one drawn on - and the examples are almost
   * all this: a stroke down the A.T. labelled Ramapo-Dunderberg because
   * OPRHP's line happened to be a metre nearer. Neither label is wrong, and
   * picking one and hiding the other is the app choosing which blaze a hiker
   * should be looking for on ground that carries both. Naming both is the
   * honest answer and the more useful one.
   *
   * Re-measured over the same 300 strokes with this field carried: 83.0%
   * name the trail that was drawn on, against 58.3% without it. The 17% that
   * still do not are strokes that genuinely brushed a different trail
   * somewhere along their length, which is what `alternatives` is for.
   *
   * The honesty ceiling on all of these figures: a perturbation model is not
   * a hand. 8 m of jitter along a published centerline is a stand-in for a
   * drawn line, chosen because nobody has a real one - which is exactly what
   * #935 says would settle the tolerances.
   */
  alsoKnownAs: Array<{
    name: string | null
    blaze_color: string | null
    source: string | null
  }>
}

/**
 * What a drawn stroke came to.
 *
 * `stretches` are the runs of real trail, in order. `droppedMetres` is what
 * was drawn over ground with no maintained trail under it - the gaps, summed,
 * measured along the STROKE rather than as the straight line between
 * stretches, because that is what the hiker actually drew and the straight
 * line is a different (shorter) claim.
 */
export interface StrokeMatch {
  stretches: StrokeStretch[]
  droppedMetres: number
}

/** Every `STROKE_SAMPLE_METRES` along the stroke, plus its last point. */
function decimate(stroke: readonly LonLat[]): LonLat[] {
  if (stroke.length === 0) return []
  const kept: LonLat[] = [stroke[0]]
  for (const point of stroke.slice(1)) {
    if (metresBetween(kept[kept.length - 1], point) >= STROKE_SAMPLE_METRES) {
      kept.push(point)
    }
  }
  const last = stroke[stroke.length - 1]
  if (kept[kept.length - 1] !== last) kept.push(last)
  return kept
}

/**
 * Put a drawn line on the trails, and say what was dropped.
 *
 * The continuity rule in one loop: hold the current trail while it is still
 * within {@link STROKE_HOLD_METRES}; otherwise take the nearest trail within
 * {@link DRAWN_SNAP_METRES}; otherwise end the stretch and start counting
 * dropped ground.
 */
export function matchStroke(
  index: TrailGraphIndex,
  stroke: readonly LonLat[],
): StrokeMatch {
  const samples = decimate(stroke)
  const stretches: StrokeStretch[] = []
  let droppedMetres = 0

  let current: StrokeStretch | null = null
  let currentKey: string | null = null

  for (let at = 0; at < samples.length; at += 1) {
    const sample = samples[at]
    const stepMetres = at === 0 ? 0 : metresBetween(samples[at - 1], sample)

    const near = trailsNear(index, sample, DRAWN_SNAP_METRES)

    // The trail already being followed, if it is still in reach. It keeps the
    // stroke unless something else is clearly nearer - see the margin's own
    // note for why "clearly" is relative rather than a wider radius.
    const held =
      currentKey === null
        ? null
        : (near.find((candidate) => trailKeyOf(index, candidate) === currentKey) ?? null)
    const holdMetres = STROKE_HOLD_MARGIN_METRES * FEET_PER_METRE

    if (
      held !== null &&
      current !== null &&
      held.offNetworkFeet <= near[0].offNetworkFeet + holdMetres
    ) {
      current.points.push(held)
      continue
    }

    if (near.length === 0) {
      // Off every maintained line. The stretch ends here and the ground from
      // the previous sample to this one is the hiker's own.
      current = null
      currentKey = null
      droppedMetres += stepMetres
      continue
    }

    const chosen = near[0]
    const edge = index.graph.edges[chosen.edgeIndex]
    // The rest of the candidates split two ways, and the split is the point:
    // a trail on the SAME tread is something the hiker is also on, and a trail
    // somewhere else is something they might be on instead. One gets named,
    // the other gets asked about.
    const rest = near.slice(1)
    const sameTread = rest.filter(
      (other) => metresBetween(chosen.at, other.at) <= SAME_TREAD_METRES,
    )
    current = {
      points: [chosen],
      // `askableName` rather than `edge.name`, so this field's own contract -
      // "Null for a piece nobody named" - is true of a blank name as well as
      // an absent one (#1444). The shell prints this in a sentence.
      name: askableName(edge.name),
      blaze_color: edge.blaze_color,
      source: edge.source,
      alternatives: rest.filter(
        (other) => metresBetween(chosen.at, other.at) > SAME_TREAD_METRES,
      ),
      alsoKnownAs: sameTread.map((other) => {
        const also = index.graph.edges[other.edgeIndex]
        return {
          name: askableName(also.name),
          blaze_color: also.blaze_color,
          source: also.source,
        }
      }),
    }
    currentKey = trailKeyOf(index, chosen)
    stretches.push(current)
  }

  return {
    // A stretch of one point is a place the stroke brushed, not a piece of it
    // walked. Dropping it here rather than in the shell keeps the rule with
    // the arithmetic that produced it.
    stretches: stretches.filter((stretch) => stretch.points.length >= 2),
    droppedMetres,
  }
}

/**
 * A matched stroke as draft stretches - the ends a `DayHikeDraft` holds.
 *
 * WHY IT KEEPS ONE POINT PER EDGE RUN, AND WHY THAT IS EXACT RATHER THAN A
 * SIMPLIFICATION. `routeThrough` routes shortest-path between consecutive
 * points, so handing it only a stretch's two ENDS would let it find a way
 * between them that is not the way the hiker drew - the app substituting its
 * own route for theirs, on the screen where they decide where to walk. Keeping
 * every decimated sample avoids that and stores hundreds of ends per walk.
 *
 * One point per RUN of the same edge is the middle that loses nothing:
 * consecutive kept points then sit on edges that share a node, so the shortest
 * path between them IS the edge the stroke ran along, and the reconstructed
 * route follows the drawn line by construction. A run rather than a set,
 * because an out-and-back visits one edge twice and those are two different
 * places in the walk.
 */
export function strokeToStretches(match: StrokeMatch): GraphPoint[][] {
  const stretches: GraphPoint[][] = []

  for (const stretch of match.stretches) {
    const kept: GraphPoint[] = []
    let lastEdge: number | null = null
    for (const point of stretch.points) {
      if (point.edgeIndex !== lastEdge) {
        kept.push(point)
        lastEdge = point.edgeIndex
      }
    }
    // The stroke's own last point, when the run it belongs to is already
    // represented: without it a stretch ends wherever it entered its final
    // edge rather than where the finger came up, which shortens the walk.
    const last = stretch.points[stretch.points.length - 1]
    if (kept[kept.length - 1] !== last) kept.push(last)
    if (kept.length >= 2) stretches.push(kept)
  }

  return stretches
}
