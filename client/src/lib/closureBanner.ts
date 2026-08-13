// The header banner for a closure ahead (WIREFRAMES.md §7).
//
// "Ahead" is direction-dependent, and that is the part worth care. A NOBO
// hiker at mile 1,407 has a closure at 1,408.6 in front of them; a SOBO hiker
// standing in the same spot has already walked through it. Getting this
// backwards is not merely noisy - it means staying silent about the closure
// someone is actually walking into.
//
// TWO LANES, NOT ONE RANKING (#485). Ranking by distance is right for closures
// that are stretches of trail and wrong the moment one of them is a region.
// Standing inside scores 0 and wins outright, so a hiker inside ATC's 398-mile
// Hurricane Helene advisory read `Trail closed here` for 398 miles of walking
// while the nine-mile Creeper Trail closure three miles ahead never reached the
// banner at all - the more urgent warning buried under the broader one, which is
// the same sentence features/ATC_TRAIL_UPDATES.md and #462 use about the map.
//
// The fix is not a better comparison. A specific closure answers "what do I do
// next"; a broad advisory answers "what country am I in", and those are not the
// same question, so they do not compete for one line. `closureLanes` returns one
// of each and the header stacks them.
//
// WHY NOT THE OBVIOUS ALTERNATIVES, both weighed on #485:
//
//  - Rank a broad advisory by its nearer edge instead of 0. Arithmetically
//    silent, not merely quieter: NOBO at mile 400 inside 239.4-637.8 computes
//    239.4 - 400 = -160.6, which is behind, so the advisory disappears entirely
//    while the hiker stands in it.
//  - Break ties toward the shorter closure. Does not touch the case - the
//    Creeper is 0 against 3, not a tie.
//
// The breadth predicate is `isBroadAdvisory`, so this reads MAX_BAND_MILES from
// lib/closureSpan.ts rather than introducing a second number. One constant
// decides both what gets a band and what gets the quiet line.

import { closureSpanMiles, isBroadAdvisory } from './closureSpan'

export type HikeDirection = 'NOBO' | 'SOBO'

export type ClosureReason =
  'storm_damage' | 'flooding' | 'maintenance' | 'relocation' | 'other'

export type ClosureStatus = 'open' | 'closed' | 'reroute_available'

export interface Closure {
  id: string
  reason_type: ClosureReason
  note: string | null
  status: ClosureStatus
  start_mile_marker: number
  end_mile_marker: number
}

const REASON_LABELS: Record<ClosureReason, string> = {
  storm_damage: 'Storm damage',
  flooding: 'Flooding',
  maintenance: 'Maintenance',
  relocation: 'Trail relocation',
  // Never surface a raw enum value; "other" tells a hiker nothing.
  other: 'Closed',
}

export function closureReasonLabel(reason: ClosureReason): string {
  return REASON_LABELS[reason]
}

function mile(value: number): string {
  return value.toLocaleString('en-US', {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })
}

export function closureBanner(
  closure: Closure,
  currentMile: number,
  direction: HikeDirection | undefined,
): string | null {
  // A reopened closure is not a warning. A reroute is - having somewhere else
  // to walk does not make the trail itself passable.
  if (closure.status === 'open') return null

  const { start_mile_marker: start, end_mile_marker: end } = closure
  const inside = currentMile >= start && currentMile <= end
  const broad = isBroadAdvisory(closure)

  // Standing inside needs no direction: whichever way this hiker is walking,
  // they are already in it. Said in those words rather than as "0.0 mi ahead",
  // which is a distance pretending to be a place.
  if (inside) {
    // Except when "inside" spans a fifth of the trail, and then "Trail closed
    // here" is simply false - #485's second complaint, and true regardless of
    // which line this ends up on. The trail is not closed at this hiker's feet;
    // a region has damage in it, and ATC's own text for the case that prompted
    // this says the damage is patchy. So the position clause carries the extent
    // instead, which is the fact that makes the sentence honest AND the fact
    // that explains why this is not the urgent line.
    //
    // Whole miles: a span this size does not need tenths, and 398 reads where
    // 398.4 invites a precision the underlying advisory does not have.
    const where = broad
      ? `Advisory along ${Math.round(closureSpanMiles(closure)).toLocaleString('en-US')} mi of trail`
      : 'Trail closed here'

    return (
      `${where} · ${closureReasonLabel(closure.reason_type)}` +
      ` · mi ${mile(start)} – ${mile(end)}`
    )
  }

  // Not inside it, and no direction yet - "ahead" does not exist. Direction
  // takes a quarter mile of walking to establish (lib/hikeDirection.ts), and
  // guessing here would warn half of all hikers about the closure behind them
  // while staying silent about the one in front.
  if (direction === undefined) return null

  // Whichever end of the closure this hiker reaches first.
  const nearEdge = direction === 'NOBO' ? start : end
  const distanceAhead =
    direction === 'NOBO' ? nearEdge - currentMile : currentMile - nearEdge

  if (distanceAhead < 0) return null

  // Ahead of a broad advisory, "Trail closed" is the same overclaim in the
  // future tense - the hiker is walking toward a region with damage in it, not
  // toward a barrier across the treadway.
  const what = broad ? 'Advisory' : 'Trail closed'

  return (
    `${what} ${mile(distanceAhead)} mi ahead · ${closureReasonLabel(closure.reason_type)}` +
    ` · mi ${mile(start)} – ${mile(end)}`
  )
}

/**
 * How far ahead a closure is, or null if it is behind and irrelevant.
 *
 * Zero means standing inside it, which is why this is not simply a distance:
 * "inside" has to sort ahead of every closure further up the trail, and a
 * plain subtraction would put it at a negative number and lose it.
 */
function distanceAhead(
  closure: Closure,
  currentMile: number,
  direction: HikeDirection | undefined,
): number | null {
  if (closure.status === 'open') return null

  const { start_mile_marker: start, end_mile_marker: end } = closure
  if (currentMile >= start && currentMile <= end) return 0

  // Without a direction there is no "ahead" - only the inside case above can
  // qualify.
  if (direction === undefined) return null

  const nearEdge = direction === 'NOBO' ? start : end
  const ahead = direction === 'NOBO' ? nearEdge - currentMile : currentMile - nearEdge

  return ahead < 0 ? null : ahead
}

/** A closure and how far ahead of the hiker it is. */
export interface RankedClosure {
  closure: Closure
  distance: number
}

/**
 * The nearest closure matching `wanted`, and how far ahead it is.
 *
 * Nearest wins, and a closure the hiker is standing in wins outright: the
 * closure two hundred miles north is not the one that changes what they do next,
 * and showing it instead of the one at mile 3 would be actively worse than
 * showing nothing.
 *
 * The distance rides out with the closure because each line has two sources
 * competing for it: OurHike's verified closures and the ATC's own notices
 * (lib/atcUpdates.ts, #461). Neither source outranks the other - an ATC notice
 * is authoritative, a verified closure was checked by a moderator - so the tie
 * is broken the same way it is broken *within* this list, by which one the hiker
 * reaches first. Returning only a string would have meant inventing a precedence
 * rule between two organisations instead of reading a fact about the trail.
 */
function nearestWhere(
  closures: readonly Closure[],
  currentMile: number,
  direction: HikeDirection | undefined,
  wanted: (closure: Closure) => boolean,
): RankedClosure | null {
  let best: RankedClosure | null = null

  for (const closure of closures) {
    if (!wanted(closure)) continue
    const ahead = distanceAhead(closure, currentMile, direction)
    if (ahead === null) continue
    if (best === null || ahead < best.distance) best = { closure, distance: ahead }
  }

  return best
}

/**
 * The two closures that matter right now, one per line of the header.
 *
 * `specific` is the one that changes what a hiker does next - a stretch of trail
 * somebody walks around, ranked by which one they reach first. `broad` is the
 * region they are standing in or heading toward, which is a standing condition
 * rather than a next action.
 *
 * Two fields rather than one winner because ranking them against each other is
 * a category error, and every way of doing it loses something a hiker needed -
 * see the header of this file for the two that were tried on #485. Splitting the
 * lanes costs the header a second line, and that is affordable for a reason
 * worth checking rather than assuming: `chrome/MapScreen.tsx` already stacks the
 * closure banner and the serious-warning banner in one `map-screen__alerts`
 * column, and WIREFRAMES.md §7 and §8 each specify their own. The one-line rule
 * this module was written around governed *one banner among many closures*, not
 * how many lines the region may hold.
 *
 * Either field can be null, including both. A broad advisory with a specific
 * closure inside it produces both, which is exactly the case #485 is about.
 */
export function closureLanes(
  closures: readonly Closure[],
  currentMile: number,
  direction: HikeDirection | undefined,
): { specific: RankedClosure | null; broad: RankedClosure | null } {
  return {
    specific: nearestWhere(
      closures,
      currentMile,
      direction,
      (closure) => !isBroadAdvisory(closure),
    ),
    broad: nearestWhere(closures, currentMile, direction, isBroadAdvisory),
  }
}
