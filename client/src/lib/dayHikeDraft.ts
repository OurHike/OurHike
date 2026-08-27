// The day hike a hiker is building, before it is saved (#978, #976, wireframe
// frame `1j`, features/HIKE_PLANNING.md "The day hike on a network").
//
// Frame `1j` is a map, a bar and four controls, and everything the bar prints
// is derived from one list of tapped points. This module is that list and the
// derivations, with no React in it, so the rules below are testable without
// rendering anything and cannot drift into a component.
//
// WHY A REFUSAL IS PART OF THE STATE
//
// A tap that lands on no maintained line does not silently do nothing. Frame
// `1j` shows a sentence:
//
//   "That tap isn't on a marked hiking route. OurHike only builds routes on
//    trails an organization maintains."
//
// Doing nothing would read as a broken map. Placing the point anyway would be
// the app deciding which trail somebody meant, which #934 forbids in as many
// words for POIs and which #771's measurement makes worse here: 48% of sampled
// A.T. points through Harriman sit within 150 m of a different marked trail.
// So the refusal is a value this module returns, and the bar prints it.
//
// IT IS NOT THE SAME SENTENCE EVERY TIME, AND #1093 IS WHY
//
// It used to be, and that was a bug rather than a simplification. A phone
// holding the routing artifact but not yet the geometry one cannot answer any
// tap at all, and it used to answer them all with the sentence above - telling
// a hiker their finger was off the trail when their finger was fine and the
// download was not finished. Two situations, two sentences; see
// NETWORK_STILL_ARRIVING.
//
// A DRAFT IS SEVERAL STRETCHES
//
// #935's answer - "users should be able to have multiple segments to a day
// hike (>1 start/stop)" - means the finished thing is an ORDERED LIST of routed
// segments, not one route. The store has held that shape since #976; this
// module held ONE segment until 2026-08-27, so every multi-segment path in the
// client was exercised by fixtures alone and nothing a hiker could do produced
// a second stretch. It now builds them.
//
// THE GAP BETWEEN TWO STRETCHES IS NOT A ROUTE AND MUST NEVER BECOME ONE.
// That is the whole point of the model: a hiker who means to bushwhack, or to
// walk a road shoulder (#931), says so by starting a new stretch, and the app
// never claims the ground between. So {@link DraftStatus} deliberately does
// NOT hand back one combined `GraphRoute` with its `sections` concatenated -
// `sections` is what drawing follows, and a concatenated one draws a line
// across the gap. The totals a bar prints are summed here; the geometry stays
// per stretch, where it is true.
//
// WHAT IT WILL NOT DO
//
// Nothing here scores a walk, compares it to another, or estimates when
// somebody gets back. `Plan.test.tsx` carries a standing negative assertion -
// no "behind", no "ahead", no score - and this is a new surface where that
// would creep in.

import { straightLineMiles } from './dayHikeShelf'
import {
  canSnapToGraph,
  closeTheLoop,
  nearestPointOnGraph,
  routeThrough,
  type GraphPoint,
  type GraphRoute,
  type LonLat,
  type RouteClimb,
  type RouteLeg,
  type TrailGraphIndex,
} from './trailGraph'

/**
 * Frame `1j`'s refusal, verbatim.
 *
 * A constant rather than a string in a component because it is the one thing
 * this flow says that a hiker might act on - it tells them the app has a rule,
 * not a bug - and it should be identical wherever it appears.
 */
export const OFF_NETWORK_REFUSAL =
  "That tap isn't on a marked hiking route. OurHike only builds routes on trails an organization maintains."

/**
 * The other thing a tap can be answered with, and it is NOT a refusal (#1093).
 *
 * The routing artifact (`trail_graph.json` - nodes, lengths, attribution)
 * arrives at launch; the lines themselves (`trail_graph_geometry.json`) are
 * fetched only when this builder opens, because they are much the heavier
 * half. In between, this phone knows the shape of the network and not where
 * any of it runs, and `nearestPointOnGraph` declines every tap rather than
 * measuring it against the straight chord between two junctions - measured on
 * the published artifact at 11.3% of on-trail taps refused and 19.7% placed on
 * a different trail than the one tapped, see its own note.
 *
 * Saying {@link OFF_NETWORK_REFUSAL} in that window would be the app telling a
 * hiker their aim was wrong when the aim was fine and the app was not ready -
 * a false statement about the hiker, on the screen where they are learning
 * what this tool will and will not do. So it is its own sentence, it names
 * what is happening, and it tells them the thing worth knowing: try again.
 *
 * It is deliberately NOT phrased as a failure. Nothing has gone wrong, and
 * the ordinary outcome a second later is that the same tap works.
 *
 * WHERE IT OVER-PROMISES, AND IT DOES. "Try again in a moment" is true for
 * the window this sentence exists for, and false for the one case where the
 * geometry artifact never arrives at all - a release that published the
 * routing half without the lines, a hash the manifest disagrees with, an edge
 * count that does not match. `fetchTrailGraphGeometry` collapses all of those
 * to `null`, so nothing here can tell them apart from a fetch still in
 * flight; lib/trailGraphData.ts's own header records that collapse as the bug
 * #1049 fixed for the ROUTING half and left standing for this one. A hiker in
 * that state is told to wait for something that is not coming.
 *
 * It is still the better sentence than the one it replaced, which told them
 * their finger was in the wrong place. Telling the two apart needs the
 * geometry fetch to carry its reason the way `loadTrailGraph` now does, which
 * is a change to a different module than this one.
 */
export const NETWORK_STILL_ARRIVING =
  "OurHike hasn't got this area's trail lines yet, so it can't tell what you tapped. Try again in a moment."

export interface DayHikeDraft {
  /**
   * The stretches, in order, each one the taps that make it.
   *
   * INVARIANT: never empty. There is always a last stretch and it is the one
   * being built, so `tapAt` never has to decide whether to create one. A
   * brand-new draft is `[[]]` - one stretch with nothing in it yet - not `[]`.
   */
  segments: GraphPoint[][]
  /** Why the last tap did not land, or null when it did. */
  refusal: string | null
  /** Whether the hiker asked to walk back to the first tap. */
  looped: boolean
}

export const EMPTY_DRAFT: DayHikeDraft = { segments: [[]], refusal: null, looped: false }

/** The stretch being built - the invariant above is what makes this total. */
function currentStretch(draft: DayHikeDraft): GraphPoint[] {
  return draft.segments[draft.segments.length - 1]
}

/**
 * Every tap in the draft, in walking order, flattened across stretches.
 *
 * For counting and for drawing the taps themselves, which is honest across a
 * gap - a tap is a place the hiker pointed at either way. NOT for routing:
 * routing across a stretch boundary is exactly what this model exists to
 * prevent, and {@link draftStatus} routes each stretch separately.
 */
export function draftPoints(draft: DayHikeDraft): GraphPoint[] {
  return draft.segments.flat()
}

/**
 * A tap on the map.
 *
 * Returns a new draft either way: with the point added, or with the refusal
 * set and the points untouched.
 */
export function tapAt(
  index: TrailGraphIndex,
  draft: DayHikeDraft,
  at: LonLat,
): DayHikeDraft {
  // Asked BEFORE the tap is projected, not after it comes back null: the two
  // nulls are indistinguishable at the call site and only one of them is
  // about where the finger went.
  // Asked BEFORE the tap is projected, not after it comes back null: the two
  // nulls are indistinguishable at the call site and only one of them is
  // about where the finger went.
  if (!canSnapToGraph(index)) {
    return { ...draft, refusal: NETWORK_STILL_ARRIVING }
  }
  const found = nearestPointOnGraph(index, at)
  if (found === null) {
    return { ...draft, refusal: OFF_NETWORK_REFUSAL }
  }
  // A new tap reopens a closed loop rather than being appended after the
  // return leg, which would be a walk nobody described.
  const segments = draft.segments.map((stretch, at) =>
    at === draft.segments.length - 1 ? [...stretch, found] : stretch,
  )
  return { segments, refusal: null, looped: false }
}

/**
 * Frame `1k`'s other half: end this stretch, and start the next one.
 *
 * What the hiker is saying is "the walk continues, and OurHike does not know
 * the bit in between" - a bushwhack, a road shoulder (#931), a herd path.
 * The app records the gap and never routes it, which is
 * features/NEARBY_TRAILS.md's omit-rather-than-guess rule applied to a walk
 * rather than to a published line.
 */
export function startStretch(draft: DayHikeDraft): DayHikeDraft {
  if (!canStartStretch(draft)) return draft
  return { segments: [...draft.segments, []], refusal: null, looped: false }
}

/**
 * Whether starting a new stretch is worth offering.
 *
 * The stretch in hand has to be a walk already - two taps - because a stretch
 * of one tap is a start with no finish, and a draft holding two of those is a
 * pair of pins rather than a hike. Not while a loop is closed either: a loop
 * is a walk that comes back, and "comes back, then continues elsewhere" is not
 * a thing this model can describe.
 */
export function canStartStretch(draft: DayHikeDraft): boolean {
  return currentStretch(draft).length >= 2 && !draft.looped
}

/**
 * Undo the last tap.
 *
 * Clears any refusal too: the hiker's next action after a refused tap is
 * usually to undo, and leaving the sentence up would make it look as though
 * the undo had also been refused.
 */
export function undoTap(draft: DayHikeDraft): DayHikeDraft {
  if (draft.refusal !== null) return { ...draft, refusal: null }
  // Closing the loop was one action, so undoing it is one action too. Slicing
  // a point at the same time would silently take back two edits, and the
  // second one is a tap the hiker placed on purpose.
  if (draft.looped) return { ...draft, looped: false }

  // Starting a stretch is one action too, and this is the same rule one level
  // up: an empty last stretch is a "start a new stretch" the hiker has not
  // typed into yet, so undo takes back THAT and leaves the tap before it
  // alone.
  if (currentStretch(draft).length === 0) {
    if (draft.segments.length === 1) return draft
    return { segments: draft.segments.slice(0, -1), refusal: null, looped: false }
  }

  return {
    segments: draft.segments.map((stretch, at) =>
      at === draft.segments.length - 1 ? stretch.slice(0, -1) : stretch,
    ),
    refusal: null,
    looped: false,
  }
}

/** Frame `1j`'s "Close the loop". */
export function loopDraft(draft: DayHikeDraft): DayHikeDraft {
  if (!canCloseLoop(draft)) return draft
  return { ...draft, looped: true, refusal: null }
}

export function clearDraft(): DayHikeDraft {
  return EMPTY_DRAFT
}

/**
 * One stretch of the draft, routed.
 *
 * Its `route` carries that stretch's own `sections`, which is what drawing
 * follows - so a caller physically cannot draw across the gap to the next
 * stretch, because there is no geometry here that spans one.
 */
export interface DraftStretch {
  points: GraphPoint[]
  route: GraphRoute
}

/**
 * The route ONE stretch describes, or null.
 *
 * Null covers two different things and the caller has to tell them apart,
 * which is why {@link draftStatus} exists: a stretch with one tap has nothing
 * to route YET, and a stretch whose taps the network cannot connect has
 * nothing to route AT ALL. The first is a normal moment in building a hike;
 * the second is a thing the hiker needs told.
 */
export function stretchRoute(
  index: TrailGraphIndex,
  points: readonly GraphPoint[],
  looped: boolean,
): GraphRoute | null {
  if (points.length < 2) return null
  return looped ? closeTheLoop(index, [...points]) : routeThrough(index, [...points])
}

export type DraftStatus =
  | { kind: 'empty' }
  | { kind: 'started' }
  | {
      kind: 'routed'
      /** Each stretch with its own geometry. Drawing reads THIS. */
      stretches: DraftStretch[]
      /** Trail miles, summed across the stretches. Excludes every gap. */
      miles: number
      legs: RouteLeg[]
      legsBySource: Array<{ source: string | null; legs: number }>
      /**
       * Ascent and descent across the whole walk, or null when any stretch of
       * it cannot be priced - the same all-or-nothing rule one stretch's own
       * climb already follows, applied one level up. A total that skipped an
       * unpriceable stretch would understate, with a number attached.
       */
      climb: RouteClimb | null
      /**
       * Straight-line miles the hiker crosses on their own, summed across the
       * gaps. Zero for a single-stretch walk.
       *
       * Never added to `miles`, and the two are printed apart for the reason
       * the whole model exists: one is ground an organization maintains and
       * the other is ground nobody has walked for us.
       */
      gapMiles: number
    }
  | { kind: 'unroutable' }

/**
 * What the bar should be saying, as one value.
 *
 * `unroutable` is the case worth naming: the taps are all on real trails and
 * the network still holds no way between them. That happens for honest reasons
 * - two parks can be genuinely unconnected by maintained trail, and
 * build_trail_graph.py rounds toward leaving a junction unmade rather than
 * inventing one. Drawing a straight line between them instead would be the app
 * claiming ground it has no evidence for.
 *
 * A stretch that cannot be routed makes the WHOLE draft unroutable rather than
 * being quietly dropped. Dropping it would turn a walk the hiker described
 * into a shorter one they did not, and the totals would be right about a
 * different walk.
 */
export function draftStatus(index: TrailGraphIndex, draft: DayHikeDraft): DraftStatus {
  const total = draftPoints(draft).length
  if (total === 0) return { kind: 'empty' }
  // One tap anywhere, or a final stretch just begun: there is a walk being
  // built and nothing yet to route. `started` is the bar's "tap again further
  // along" state and it is right for both.
  if (total === 1) return { kind: 'started' }

  const stretches: DraftStretch[] = []
  for (const points of draft.segments) {
    // A stretch with one tap is the one being built. It is not an error and
    // not a route - the walk so far is the stretches behind it.
    if (points.length === 0) continue
    if (points.length === 1) {
      if (points === draft.segments[draft.segments.length - 1]) continue
      return { kind: 'unroutable' }
    }
    const route = stretchRoute(index, points, draft.looped)
    if (route === null) return { kind: 'unroutable' }
    stretches.push({ points, route })
  }
  if (stretches.length === 0) return { kind: 'started' }

  const legs = stretches.flatMap((stretch) => stretch.route.legs)
  return {
    kind: 'routed',
    stretches,
    miles: stretches.reduce((sum, stretch) => sum + stretch.route.miles, 0),
    legs,
    legsBySource: tallyLegsBySource(legs),
    climb: climbAcrossStretches(stretches),
    gapMiles: gapMilesAcross(draft),
  }
}

/** Legs per organization, in first-seen order - the bar's live tally. The
 *  same shape one stretch's own `legsBySource` has, summed across stretches
 *  rather than recomputed from a concatenation that would double-count a
 *  source appearing in two of them. */
function tallyLegsBySource(
  legs: readonly RouteLeg[],
): Array<{ source: string | null; legs: number }> {
  const order: Array<string | null> = []
  const counts = new Map<string | null, number>()
  for (const leg of legs) {
    const seen = counts.get(leg.source)
    if (seen === undefined) {
      order.push(leg.source)
      counts.set(leg.source, 1)
    } else {
      counts.set(leg.source, seen + 1)
    }
  }
  return order.map((source) => ({ source, legs: counts.get(source) as number }))
}

/** Null the moment any stretch is unpriced - see the field's own note. */
function climbAcrossStretches(stretches: readonly DraftStretch[]): RouteClimb | null {
  let gainFt = 0
  let lossFt = 0
  for (const stretch of stretches) {
    if (stretch.route.climb === null) return null
    gainFt += stretch.route.climb.gainFt
    lossFt += stretch.route.climb.lossFt
  }
  return { gainFt, lossFt }
}

/**
 * The gaps, measured the one way a gap can be measured.
 *
 * Straight-line from the last tap of one stretch to the first of the next -
 * `lib/dayHikeShelf.ts`'s `straightLineMiles`, shared rather than copied, so
 * the figure the builder prints and the figure the saved card prints for the
 * same gap cannot drift apart.
 */
function gapMilesAcross(draft: DayHikeDraft): number {
  let miles = 0
  for (let at = 0; at + 1 < draft.segments.length; at += 1) {
    const before = draft.segments[at]
    const after = draft.segments[at + 1]
    const from = before[before.length - 1]
    const to = after[0]
    if (from === undefined || to === undefined) continue
    miles += straightLineMiles(from.at, to.at)
  }
  return miles
}

/**
 * Whether "Close the loop" is worth offering.
 *
 * Two taps minimum, because a loop from one point is not a walk, and not while
 * the draft is already closed.
 *
 * AND NOT ACROSS A GAP. A loop is a walk that comes back to where it started;
 * with two stretches there is no defined way back across the ground the app
 * declined to route, and `lib/dayHikeCard.ts` already refuses to resolve such
 * a hike - so offering the control here would let a hiker save a walk that can
 * never be re-resolved and falls back to its cache for ever.
 */
export function canCloseLoop(draft: DayHikeDraft): boolean {
  return draft.segments.length === 1 && currentStretch(draft).length >= 2 && !draft.looped
}
