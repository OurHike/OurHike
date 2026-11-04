// A place a hiker said an earned item happened (#1963), as it is kept beside
// the tag in `ourhike:challenge-state` - the type and its parser, alone.
//
// ITS OWN MODULE FOR THE LAUNCH BUDGET. lib/challengeProgress.ts reads the
// saved state on every launch, so whatever this parser imports is in the
// first frame (features/LAUNCH_BUDGET.md). Here it needs the fourteen
// states' codes and nothing else; their names, the Where sheet's rules and
// its options stay in lib/wherePlace.ts, which only the challenge screens
// load.

/** The fourteen trail states' codes, south to north. lib/wherePlace.ts
 *  pairs each with its name, in this order. */
export const TRAIL_STATE_CODES = [
  'GA',
  'NC',
  'TN',
  'VA',
  'WV',
  'MD',
  'PA',
  'NJ',
  'NY',
  'CT',
  'MA',
  'VT',
  'NH',
  'ME',
] as const

export type TrailStateCode = (typeof TRAIL_STATE_CODES)[number]

export function isTrailStateCode(value: unknown): value is TrailStateCode {
  return (TRAIL_STATE_CODES as readonly unknown[]).includes(value)
}

/** Where an earned item happened, as the hiker said. Device-only. */
export type TagPlace =
  /** The fix's snapped mile when it was earned. */
  | { kind: 'here'; mile: number }
  /** Somewhere in the miles walked today - the day's extent, no finer. */
  | { kind: 'walked'; fromMile: number; toMile: number }
  /** A place picked by name from the phone's own waypoints. */
  | { kind: 'poi'; poi: string; name: string; mile: number | null }
  /** On the trail, somewhere in one state. */
  | { kind: 'state'; state: TrailStateCode }
  /** At home, in town, on another trail. */
  | { kind: 'off' }

/** A stored place, or null for anything that is not one - a malformed
 *  place costs the place, never the tag (lib/challengeProgress.ts). */
export function readTagPlace(value: unknown): TagPlace | null {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) return null
  const place = value as Record<string, unknown>
  switch (place.kind) {
    case 'here':
      return Number.isFinite(place.mile)
        ? { kind: 'here', mile: place.mile as number }
        : null
    case 'walked':
      return Number.isFinite(place.fromMile) && Number.isFinite(place.toMile)
        ? {
            kind: 'walked',
            fromMile: place.fromMile as number,
            toMile: place.toMile as number,
          }
        : null
    case 'poi':
      return typeof place.poi === 'string' && typeof place.name === 'string'
        ? {
            kind: 'poi',
            poi: place.poi,
            name: place.name,
            mile: Number.isFinite(place.mile) ? (place.mile as number) : null,
          }
        : null
    case 'state':
      return isTrailStateCode(place.state) ? { kind: 'state', state: place.state } : null
    case 'off':
      return { kind: 'off' }
    default:
      return null
  }
}
