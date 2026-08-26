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

/**
 * THE PALETTE IS CLOSED, AND THIS IS WHERE SPRAWL STOPS (#782).
 *
 * The maintainer's decision, verbatim (features/NEARBY_TRAILS.md §4,
 * 2026-08-18): *"we will need to bring in more colors for the blazes. Long
 * [Path] is indeed aqua. Some way to stop sprawl is needed, but the color of
 * the trail blazes should be the color on the map."*
 *
 * Both halves of that are load-bearing. The paint on the tree is what a hiker
 * navigates by, so a map that flattens it is lying about the ground — and a
 * palette that grows every time a new source arrives ends up with forty hues
 * nobody can tell apart, which lies about it differently. So this object is
 * the ENTIRE set of hues this map will ever paint, and it grows by review
 * rather than by data arrival.
 *
 * **A new member needs three things, and the third is the one that gets
 * skipped:**
 *
 *   1. a real trail wearing it — measured on a real source, not anticipated;
 *   2. a hex that stays separable from its nearest palette neighbour and
 *      readable on both the day and the night sheet, with the numbers written
 *      down here rather than asserted;
 *   3. no change to the red-light collapse. That one is free by construction
 *      and worth knowing why: `map/style.ts`'s `blazeLineColor` replaces this
 *      whole expression with `RED_LIGHT_BLAZE_COLOR` under red light, so a
 *      member added here cannot reach that mode at all. Blaze identity moves
 *      to the tapped trail's sheet there, honestly, rather than pretending to
 *      survive on the line.
 *
 * **The bar, measured against the palette itself rather than picked** (all
 * figures 2026-08-22, CIE76 ΔE in Lab and WCAG contrast ratio):
 *
 *   - **Separation ≥ 24.178.** That is Blue/Purple, the closest pair already
 *     shipping. A new hue at least as separable as the worst pair a hiker
 *     already reads is not a regression; a tighter one is.
 *   - **Day contrast ≥ 2.076** against `#ffffff`, the field sheet's paper —
 *     Yellow's, the lowest of any hue that is not White. (White itself is
 *     1.02 and stays: the AT's centerline is white paint, and its width and
 *     casing are what carry it.)
 *   - **Night contrast ≥ 2.66** against `#0c1410`, night_hike's ink —
 *     Purple's, the lowest shipping.
 *
 * These are arithmetic, and arithmetic is not the whole of legibility:
 * `@unvalidated` — nothing here has been read on a real phone in real
 * sunlight, which is **#105 — Outdoor usability pass** and the thing that
 * would actually settle a hex. What would change a number is that pass
 * reporting a hue that washes out, not a nicer figure in this comment.
 */
const BLAZE_COLORS: Record<string, string> = {
  White: '#fffdf7',
  Blue: '#1f5fa8',
  Yellow: '#dcae1b',
  Orange: '#d2721c',
  Red: '#b2321f',
  Green: '#2f7a44',
  Purple: '#6a4a8f',
  // FIRST ADMISSION UNDER THE RULE ABOVE (#782), and the Long Path forces it:
  // 107 Aqua + 28 Teal rows on OPRHP's own Long Path segments, agreeing with
  // NYNJTC's separate layer (measured 2026-08-18, #771). Aqua is real paint on
  // real trees, not a source's idiosyncratic spelling.
  //
  // Measured 2026-08-22 against the three bars above: nearest neighbour is the
  // neutral grey at ΔE 36.6 (Green 37.3, Blue 49.9), against a 24.178 bar;
  // day contrast 3.90 against a 2.076 bar; night contrast 4.80 against 2.66.
  // Chosen over #00a0a8, which separates slightly better (ΔE 39.9) and reads
  // worse where it matters more — 3.18 on the day sheet, which is the one a
  // hiker holds in the sun.
  Aqua: '#0d8f96',
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

/**
 * The values that mean "no hue to draw" rather than naming one.
 *
 * All three are real pipeline output, not error states: "None" is a confirmed
 * unblazed trail, "Other" is a real domain value with no dedicated paint, and
 * "Unknown" is what `lib/blaze.py` emits by contract for every value it could
 * not decode.
 */
export const NEUTRAL_BLAZE_MEMBERS = ['None', 'Other', 'Unknown'] as const

/**
 * Every hue the palette admits, in declaration order.
 *
 * Derived rather than listed, so that admitting a member reaches everything
 * that enumerates the palette — the legend's rows, the style tests, and the
 * governance check in blaze.test.ts — without anybody remembering to add it
 * in a second place. #782 makes that a requirement rather than a nicety:
 * *"the legend's blaze rows pick up new members automatically or this issue
 * is not done."*
 */
export const BLAZE_PALETTE_MEMBERS = Object.keys(BLAZE_COLORS).filter(
  (name) => !(NEUTRAL_BLAZE_MEMBERS as readonly string[]).includes(name),
)

/** Every blaze_color string this module answers for, hues and neutrals alike. */
export const BLAZE_MEMBERS = Object.keys(BLAZE_COLORS)

/**
 * One palette member's hex, by name.
 *
 * NO PRODUCTION CALLER SINCE 2026-08-25, and that is worth knowing before
 * reading this as live rendering code. The map has never painted through it -
 * `BLAZE_MATCH_EXPRESSION` below is what `map/style.ts` hands MapLibre - and
 * its one caller was the legend's blaze swatch, removed with those rows
 * (chrome/Legend.tsx's header has the decision).
 *
 * It stays because `BLAZE_COLORS` is not exported, so this is the only way to
 * read a member's hex, and `lib/blazeGovernance.test.ts` reads every member
 * through it to hold #782's admission bar - the ΔE separation and the day and
 * night contrast ratios. Deleting it would mean opening the table up to
 * exactly the sprawl that issue closed off.
 */
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

/**
 * How each `blaze_color` is NAMED, wherever a surface says one out loud.
 *
 * The pipeline's contract above is what makes this more than a capitalisation
 * helper: "None" is a CONFIRMED unblazed trail while "Unknown" is a value
 * that failed to decode, and the two are different claims. WIREFRAMES.md §3
 * requires saying plainly when a blaze is unknown, and "Unblazed" in that
 * slot would be a confident statement nobody made.
 *
 * Lifted here from lib/lineDetail.ts when the turn card (#1041) became the
 * second surface naming a blaze. It is the same rule in both places by
 * construction now: a hiker who reads "Blaze not recorded" on a tapped line
 * and "Unblazed" at the junction it leads to has been told two different
 * things about one piece of tread.
 */
export function blazeLabel(blazeColor: string | null): string {
  if (blazeColor === null || blazeColor === 'Unknown') return 'Blaze not recorded'
  if (blazeColor === 'None') return 'Unblazed'
  if (blazeColor === 'Other') return 'Other blaze'
  return `${blazeColor} blaze`
}
