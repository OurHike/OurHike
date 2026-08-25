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
// `1j` shows a sentence, and it is the same sentence every time:
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
// A DRAFT IS ALREADY SEVERAL SEGMENTS
//
// #935's answer - "users should be able to have multiple segments to a day
// hike (>1 start/stop)" - means the finished thing is an ORDERED LIST of routed
// segments, not one route. This module holds the first case of that: one
// segment being built. The gaps between segments arrive with frame `1k`, and
// the shape here is chosen so they can, rather than assuming a single route
// and having to be unpicked.
//
// WHAT IT WILL NOT DO
//
// Nothing here scores a walk, compares it to another, or estimates when
// somebody gets back. `Plan.test.tsx` carries a standing negative assertion -
// no "behind", no "ahead", no score - and this is a new surface where that
// would creep in.

import {
  closeTheLoop,
  nearestPointOnGraph,
  routeThrough,
  type GraphPoint,
  type GraphRoute,
  type LonLat,
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

export interface DayHikeDraft {
  /** The taps, in the order they were made. */
  points: GraphPoint[]
  /** Why the last tap did not land, or null when it did. */
  refusal: string | null
  /** Whether the hiker asked to walk back to the first tap. */
  looped: boolean
}

export const EMPTY_DRAFT: DayHikeDraft = { points: [], refusal: null, looped: false }

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
  const found = nearestPointOnGraph(index, at)
  if (found === null) {
    return { ...draft, refusal: OFF_NETWORK_REFUSAL }
  }
  // A new tap reopens a closed loop rather than being appended after the
  // return leg, which would be a walk nobody described.
  return { points: [...draft.points, found], refusal: null, looped: false }
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
  if (draft.points.length === 0) return draft
  return { points: draft.points.slice(0, -1), refusal: null, looped: false }
}

/** Frame `1j`'s "Close the loop". */
export function loopDraft(draft: DayHikeDraft): DayHikeDraft {
  if (draft.points.length < 2) return draft
  return { ...draft, looped: true, refusal: null }
}

export function clearDraft(): DayHikeDraft {
  return EMPTY_DRAFT
}

/**
 * The route the draft currently describes, or null.
 *
 * Null covers two different things and the caller has to tell them apart,
 * which is why {@link draftStatus} exists: a draft with one tap has nothing to
 * route YET, and a draft whose taps the network cannot connect has nothing to
 * route AT ALL. The first is a normal moment in building a hike; the second is
 * a thing the hiker needs told.
 */
export function draftRoute(
  index: TrailGraphIndex,
  draft: DayHikeDraft,
): GraphRoute | null {
  if (draft.points.length < 2) return null
  return draft.looped
    ? closeTheLoop(index, draft.points)
    : routeThrough(index, draft.points)
}

export type DraftStatus =
  | { kind: 'empty' }
  | { kind: 'started' }
  | { kind: 'routed'; route: GraphRoute }
  | { kind: 'unroutable' }

/**
 * What the bar should be saying, as one value.
 *
 * `unroutable` is the case worth naming: the taps are all on real trails and
 * the network still holds no way between them. That happens for honest reasons
 * - the published network is clipped to a ring, two parks can be genuinely
 * unconnected by maintained trail, and build_trail_graph.py rounds toward
 * leaving a junction unmade rather than inventing one. Drawing a straight line
 * between them instead would be the app claiming ground it has no evidence for.
 */
export function draftStatus(index: TrailGraphIndex, draft: DayHikeDraft): DraftStatus {
  if (draft.points.length === 0) return { kind: 'empty' }
  if (draft.points.length === 1) return { kind: 'started' }
  const route = draftRoute(index, draft)
  if (route === null) return { kind: 'unroutable' }
  return { kind: 'routed', route }
}

/**
 * Whether "Close the loop" is worth offering.
 *
 * Two taps minimum, because a loop from one point is not a walk, and not while
 * the draft is already closed.
 */
export function canCloseLoop(draft: DayHikeDraft): boolean {
  return draft.points.length >= 2 && !draft.looped
}
