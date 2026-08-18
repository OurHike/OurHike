// What a hiker still owes, and how they might take it (#791).
//
// The screen behind this is the one a section hiker or flip-flopper arrives
// with every spring: what is left, and where do I start next? Everything
// here is derived from the trip store on read and stored nowhere - a gap
// that could go stale against the record it describes would be worse than
// no gap at all.
//
// GAPS ARE A SET, NOT A QUEUE. Nothing in this file orders the pieces by
// what the hiker "should" do. `sortGaps` offers three orderings and they
// are peers: trail order is a sort, not the truth. Flip-floppers walk the
// trail in whatever order suits them, and both ends of every gap are start
// candidates - which is why a gap carries two references rather than a
// direction.

import { hikePieces, MIN_GAP_MI, type Hike, type PlaceRef, type Span } from './hikes'
import type { StoredPoi } from './trailData'
import type { Trip } from './trips'

export interface Gap {
  id: string
  span: Span
  /** The low-mile end and the high-mile end. NOT "start" and "end": which
   *  one is the start is the hiker's choice, and the direction falls out of
   *  it. */
  low: PlaceRef
  high: PlaceRef
  lengthMi: number
}

export interface WhatsLeft {
  gaps: Gap[]
  /** Everything left to walk, including the slivers below. */
  totalMi: number
  /**
   * The stretches too short to be worth a card, and what they add up to.
   *
   * #791 asked for "a stated threshold with the remainder still visible
   * somewhere, rather than either extreme chosen silently", and this is
   * that remainder. Showing 0.1-mile gaps as cards makes the screen look
   * broken; dropping them without a word lets the app call a hike finished
   * that is not. A line saying how many there are and how far they run is
   * the version that is neither.
   */
  slivers: { count: number; miles: number }
}

export function whatsLeft(
  hike: Hike,
  trips: readonly Trip[],
  pois: readonly StoredPoi[],
): WhatsLeft {
  // Everything, at no threshold at all - then split by the threshold, so
  // the two halves cannot disagree about what the whole is.
  const all = hikePieces(hike, trips, pois, 0)
    .filter((piece) => piece.kind === 'gap')
    .map((piece) => ({
      id: piece.id,
      span: piece.span,
      low: piece.from,
      high: piece.to,
      lengthMi: piece.span.to - piece.span.from,
    }))

  const gaps = all.filter((gap) => gap.lengthMi >= MIN_GAP_MI)
  const slivers = all.filter((gap) => gap.lengthMi < MIN_GAP_MI)

  return {
    gaps,
    totalMi: all.reduce((sum, gap) => sum + gap.lengthMi, 0),
    slivers: {
      count: slivers.length,
      miles: slivers.reduce((sum, gap) => sum + gap.lengthMi, 0),
    },
  }
}

export type GapSort = 'trail' | 'near' | 'fits'

export interface SortContext {
  /** Where the hiker is on the pipeline's mile axis, or null. Without it
   *  "nearest me" is not offered rather than quietly falling back. */
  gpsMile: number | null
  /** How far the days they have would reach, or null without enough log to
   *  say. Without it "fits my days" is not offered, for the same reason. */
  reachMi: number | null
}

/**
 * One ordering of the gaps. A SORT, never a recommendation: no caller may
 * label the first card "next", number the cards, or draw them as steps.
 *
 * - `trail` - low mile first. The order the trail runs in, which is not the
 *   order anybody has to walk it.
 * - `near` - by how far the hiker is from the piece, a piece they are
 *   standing in being nearest of all.
 * - `fits` - the pieces their days could finish first, shortest shortfall
 *   after that. Never "you should do this one": it answers a question the
 *   hiker asked by setting a number of days.
 */
export function sortGaps(
  gaps: readonly Gap[],
  sort: GapSort,
  context: SortContext,
): Gap[] {
  const ordered = [...gaps]
  if (sort === 'near' && context.gpsMile !== null) {
    const here = context.gpsMile
    return ordered.sort((a, b) => distanceTo(a, here) - distanceTo(b, here))
  }
  if (sort === 'fits' && context.reachMi !== null) {
    const reach = context.reachMi
    return ordered.sort(
      (a, b) => shortfall(a, reach) - shortfall(b, reach) || a.lengthMi - b.lengthMi,
    )
  }
  return ordered.sort((a, b) => a.span.from - b.span.from)
}

/** Zero inside the gap, otherwise the distance to its nearer end. */
function distanceTo(gap: Gap, mile: number): number {
  if (mile >= gap.span.from && mile <= gap.span.to) return 0
  return Math.min(Math.abs(gap.span.from - mile), Math.abs(gap.span.to - mile))
}

/** How much of a gap the hiker's days would NOT reach - zero for anything
 *  they could finish, which is what puts those first. */
function shortfall(gap: Gap, reachMi: number): number {
  return Math.max(0, gap.lengthMi - reachMi)
}

/** The sliver threshold, re-exported from where the gaps themselves are
 *  derived so a screen quoting the number in words cannot drift from the
 *  one the arithmetic used. */
export { MIN_GAP_MI }
