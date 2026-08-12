// The header banner for a closure ahead (WIREFRAMES.md §7).
//
// "Ahead" is direction-dependent, and that is the part worth care. A NOBO
// hiker at mile 1,407 has a closure at 1,408.6 in front of them; a SOBO hiker
// standing in the same spot has already walked through it. Getting this
// backwards is not merely noisy - it means staying silent about the closure
// someone is actually walking into.

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

  // Standing inside needs no direction: whichever way this hiker is walking,
  // they are already in it. Said in those words rather than as "0.0 mi ahead",
  // which is a distance pretending to be a place.
  if (inside) {
    return (
      `Trail closed here · ${closureReasonLabel(closure.reason_type)}` +
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

  return (
    `Trail closed ${mile(distanceAhead)} mi ahead · ${closureReasonLabel(closure.reason_type)}` +
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

/**
 * The closure a hiker is about to walk into, and how far ahead it is.
 *
 * Nearest wins, and a closure the hiker is standing in wins outright. The
 * header has room for one line, and the closure two hundred miles north is
 * not the one that changes what they do next - showing it instead of the one
 * at mile 3 would be actively worse than showing nothing.
 *
 * The distance rides out with the closure because that one line now has two
 * sources competing for it: OurHike's verified closures and the ATC's own
 * notices (lib/atcUpdates.ts, #461). Neither source outranks the other -
 * an ATC notice is authoritative, a verified closure was checked by a
 * moderator - so the tie is broken the same way it is broken *within* this
 * list, by which one the hiker reaches first. Returning only a string would
 * have meant inventing a precedence rule instead.
 */
export function nearestClosure(
  closures: readonly Closure[],
  currentMile: number,
  direction: HikeDirection | undefined,
): { closure: Closure; distance: number } | null {
  let best: { closure: Closure; distance: number } | null = null

  for (const closure of closures) {
    const ahead = distanceAhead(closure, currentMile, direction)
    if (ahead === null) continue
    if (best === null || ahead < best.distance) best = { closure, distance: ahead }
  }

  return best
}

/**
 * One banner for a whole trail's worth of closures, or null if the way ahead
 * is clear.
 */
export function nearestClosureBanner(
  closures: readonly Closure[],
  currentMile: number,
  direction: HikeDirection | undefined,
): string | null {
  const best = nearestClosure(closures, currentMile, direction)
  return best === null ? null : closureBanner(best.closure, currentMile, direction)
}
