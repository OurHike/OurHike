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
  direction: HikeDirection,
): string | null {
  // A reopened closure is not a warning. A reroute is - having somewhere else
  // to walk does not make the trail itself passable.
  if (closure.status === 'open') return null

  const { start_mile_marker: start, end_mile_marker: end } = closure

  // Whichever end of the closure this hiker reaches first.
  const nearEdge = direction === 'NOBO' ? start : end
  const distanceAhead =
    direction === 'NOBO' ? nearEdge - currentMile : currentMile - nearEdge

  const inside = currentMile >= start && currentMile <= end
  if (!inside && distanceAhead < 0) return null

  const ahead = Math.max(distanceAhead, 0)

  return (
    `Trail closed ${mile(ahead)} mi ahead · ${closureReasonLabel(closure.reason_type)}` +
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
  direction: HikeDirection,
): number | null {
  if (closure.status === 'open') return null

  const { start_mile_marker: start, end_mile_marker: end } = closure
  if (currentMile >= start && currentMile <= end) return 0

  const nearEdge = direction === 'NOBO' ? start : end
  const ahead = direction === 'NOBO' ? nearEdge - currentMile : currentMile - nearEdge

  return ahead < 0 ? null : ahead
}

/**
 * One banner for a whole trail's worth of closures: the one a hiker is about
 * to walk into, or null if the way ahead is clear.
 *
 * Nearest wins, and a closure the hiker is standing in wins outright. The
 * header has room for one line, and the closure two hundred miles north is
 * not the one that changes what they do next - showing it instead of the one
 * at mile 3 would be actively worse than showing nothing.
 */
export function nearestClosureBanner(
  closures: readonly Closure[],
  currentMile: number,
  direction: HikeDirection,
): string | null {
  let best: Closure | null = null
  let bestDistance = Infinity

  for (const closure of closures) {
    const ahead = distanceAhead(closure, currentMile, direction)
    if (ahead === null || ahead >= bestDistance) continue
    best = closure
    bestDistance = ahead
  }

  return best === null ? null : closureBanner(best, currentMile, direction)
}
