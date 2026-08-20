// Client's half of blaze rendering (see pipeline/lib/blaze.py for the other
// half - decoding raw ArcGIS codes into a normalized `blaze_color` string,
// done during pipeline export, not here). This module's only job: map an
// already-normalized blaze_color to a paint color, with a defensive
// fallback + warning for anything unexpected - belt-and-suspenders, since a
// rendering layer shouldn't blindly trust upstream data. See WIREFRAMES.md's
// "Trail line rendering — blazes" section for the exact hex values, which
// are load-bearing, not decorative.

/**
 * The grey a trail line takes when its blaze is not known.
 *
 * Exported since #598. The corridor view spends the same grey on the miles
 * ATC's centerline records no maintaining club for - the same sentence, "we do
 * not know this", about a different question - and sharing the constant is what
 * keeps one sentence one colour. WIREFRAMES.md line 325 pins the value.
 */
export const NEUTRAL_BLAZE_COLOR = '#8a8271'

const NEUTRAL_FALLBACK = NEUTRAL_BLAZE_COLOR

const BLAZE_COLORS: Record<string, string> = {
  White: '#fffdf7',
  Blue: '#1f5fa8',
  Yellow: '#dcae1b',
  Orange: '#d2721c',
  Red: '#b2321f',
  Green: '#2f7a44',
  Purple: '#6a4a8f',
  // All three are real values from the pipeline (see pipeline/lib/blaze.py) -
  // "None" means confirmed unblazed, "Other" is a real domain value with no
  // dedicated paint style, and "Unknown" is what its NEUTRAL_FALLBACK emits
  // for every undecodable blaze, BY CONTRACT. Warning on a value our own
  // upstream guarantees will occur was noise dressed as vigilance (#257);
  // the warning below is kept for genuinely novel values.
  None: NEUTRAL_FALLBACK,
  Other: NEUTRAL_FALLBACK,
  Unknown: NEUTRAL_FALLBACK,
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
