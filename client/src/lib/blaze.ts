// Client's half of blaze rendering (see pipeline/lib/blaze.py for the other
// half - decoding raw ArcGIS codes into a normalized `blaze_color` string,
// done during pipeline export, not here). This module's only job: map an
// already-normalized blaze_color to a paint color, with a defensive
// fallback + warning for anything unexpected - belt-and-suspenders, since a
// rendering layer shouldn't blindly trust upstream data. See WIREFRAMES.md's
// "Trail line rendering — blazes" section for the exact hex values, which
// are load-bearing, not decorative.

const NEUTRAL_FALLBACK = '#8a8271'

const BLAZE_COLORS: Record<string, string> = {
  White: '#fffdf7',
  Blue: '#1f5fa8',
  Yellow: '#dcae1b',
  Orange: '#d2721c',
  Red: '#b2321f',
  Green: '#2f7a44',
  Purple: '#6a4a8f',
  // Both are real, successful decodes from the pipeline (see
  // pipeline/lib/blaze.py) - "None" means confirmed unblazed, "Other" is a
  // real domain value with no dedicated paint style. Neither should warn.
  None: NEUTRAL_FALLBACK,
  Other: NEUTRAL_FALLBACK,
}

export function blazePaintColor(blazeColor: string): string {
  if (typeof blazeColor === 'string' && blazeColor in BLAZE_COLORS) {
    return BLAZE_COLORS[blazeColor]
  }
  console.warn(`Unrecognized blaze_color "${blazeColor}" - rendering as neutral grey.`)
  return NEUTRAL_FALLBACK
}

// One MapLibre `match` expression for `line-color`, not per-layer hardcoding
// - centerline, side_trails, and anything imported later all share this one
// rendering rule (TRAIL_BLAZE_COLORS.md).
export const BLAZE_MATCH_EXPRESSION = [
  'match',
  ['get', 'blaze_color'],
  ...Object.entries(BLAZE_COLORS)
    .filter(([color]) => color !== 'None' && color !== 'Other')
    .flatMap(([color, hex]) => [color, hex]),
  'None',
  NEUTRAL_FALLBACK,
  'Other',
  NEUTRAL_FALLBACK,
  NEUTRAL_FALLBACK, // fallback for anything else (Unknown, Gold, etc.)
] as const
