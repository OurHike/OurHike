// How a closure is drawn (WIREFRAMES.md §7).
//
// A closure is a LINE, not a pin: barrier tape laid along the closed geometry -
// red diagonals with a dark edge, and nothing at all between them, so the trail
// underneath stays visible through its own closure. Its whole job is to be
// unmistakable for a red blaze, which is a thinner SOLID line with a hairline
// casing.
//
// That distinction is safety-critical and is deliberately structural rather
// than chromatic. Colour alone vanishes in greyscale, in direct sun on a
// phone screen, and for a red-green colour-blind hiker - between them, a
// large share of the moments when "do not walk down there" most needs to
// land. So a closure differs in width and in texture, and tests hold both.
//
// WHY IT IS TAPE, AND NOT THE BARRED BAND §7 DESCRIBES. The band was a 10px
// dashed red line drawn over a SOLID 14px casing, so the casing showed through
// every gap: 5px of red, then 3.5px of #14130f, the whole way along. Read off
// the shipped constants, 41% of the band's length was near-black - the darkest
// ink on a sheet whose contours are hairlines - and what it drew was a black
// rope with red ticks, which is the standard cartographic mark for a railway.
// Rendered 2026-08-27 in MapLibre 6.4.1 over synthetic geometry; the frames are
// in the pull request that replaced it.
//
// The tape fixes that by construction rather than by tuning. One layer, one
// image, and no casing underneath to show through anything - because the dark
// edge every stripe carries IS the casing now. That edge is thinner than the
// overhang it replaces and CLOSURE_STRIPE_EDGE says so; what it buys is that
// the casing can only ever be an edge, since there is no longer anything under
// a gap to fill it with.

import type { LayerSpecification } from '@maplibre/maplibre-gl-style-spec'

export const CLOSURE_LAYER_ID = 'closure-band'

/** The image id the band's `line-pattern` points at. Registered on the live
 *  map by map/closureTape.ts, which owns the pixels; this module owns only
 *  the spec they are drawn from. */
export const CLOSURE_TAPE_IMAGE_ID = 'closure-tape'

/** Drawn at 2x, like every other generated image on this map
 *  (map/poiIcons.ts's POI_PIN_PIXEL_RATIO), so the stripes stay crisp on a
 *  phone. */
export const CLOSURE_TAPE_PIXEL_RATIO = 2

/**
 * How wide the tape is drawn, in CSS pixels.
 *
 * Exactly the ink the barred band already occupied - its 10px line plus the
 * 2px casing showing past each side - so replacing one with the other moved no
 * pixel outward or inward. It changed only what is inside them.
 *
 * Wide enough that the tape reads as a barrier rather than a route, which
 * means comfortably more than twice the widest blaze on the map: 14 against
 * BLAZE_LINE_WIDTH's 4.5 is 3.1x, where the band's own line was 2.2x.
 * closureStyle.test.ts holds that ratio against map/style.ts rather than
 * against a number restated here, so widening a through-route still has to
 * widen this with it.
 */
export const CLOSURE_TAPE_WIDTH = 14

/**
 * The casing weight the band used to carry, in CSS pixels.
 *
 * NOTHING PAINTS WITH THIS ANY MORE, and saying so is the point of keeping it.
 * The band's casing became the edge on each stripe (CLOSURE_STRIPE_EDGE), and
 * #1071 took the ATC point notice off the disc that was the other consumer -
 * so what survives here is a REFERENCE WEIGHT rather than a paint value: the
 * 2px this map used to outline a safety mark with, and which both of its
 * successors are held to be lighter than.
 *
 * lib/atcUpdateStyle.ts's `atcNoticeRimWidths` names it as the failure case in
 * so many words - "put `CLOSURE_CASING_WIDTH` back and the test goes red on
 * 2.9px" - and its ATC_NOTICE_CASING_WIDTH is asserted under it. Deleting the
 * constant would delete the thing those two comparisons are against.
 */
export const CLOSURE_CASING_WIDTH = 2

export const CLOSURE_COLOR = '#b2321f'
export const CLOSURE_CASING_COLOR = '#14130f'

/**
 * The dark edge each stripe carries, in CSS pixels per side.
 *
 * This is the casing, moved off the layer underneath and onto the marks
 * themselves, and it is THINNER than the 2px overhang it replaces. That is a
 * real reduction rather than a wash, and naming it here is the honest way to
 * carry it: the old casing was heavier and mostly invisible AS an edge,
 * because it spent itself filling the gaps.
 *
 * 1.25 rather than 1 so it still clears the blaze's hairline - CASING_OVERHANG
 * is 1 in map/style.ts - which is the weight distinction §7 asks for and
 * closureStyle.test.ts holds. At 1 a closure's edge would be exactly as heavy
 * as a side trail's, and that channel would stop saying anything.
 */
export const CLOSURE_STRIPE_EDGE = 1.25

/**
 * The angle a stripe makes with the line it is drawn on, in degrees.
 *
 * 55 rather than 45, picked by eye off the renders in the pull request: the
 * steeper the stripe, the more it reads as CROSSING the trail rather than
 * running along it, and crossing is the entire message.
 *
 * @unvalidated - nobody has tested any angle against a hiker. What would
 * settle it: whether a closure gets spotted on a screen somebody was not told
 * to search.
 */
export const CLOSURE_STRIPE_ANGLE_DEG = 55

/** How a tape's stripes are spaced. Both in CSS pixels. */
export interface TapeCadence {
  /** Thickness of one red stripe, measured ACROSS the stripe. */
  stripe: number
  /** Distance between stripe centres, measured ALONG the line. */
  pitch: number
}

/**
 * The closure's own cadence.
 *
 * `pitch` is measured along the line rather than across the stripes because
 * that is the axis the image tiles on, and a pitch that is not a whole number
 * of image pixels tiles with a seam - map/closureTape.ts depends on this
 * landing exactly on its pixel ratio.
 *
 * Red covers 28% of the tape's length here and ink of any kind about half of
 * it, the rest being nothing at all (tapeRedFraction computes the first of
 * those rather than this comment asserting it). Against roughly 60% red and
 * 100% opaque for the band's first hazard-tape pass, which drew pale stripes
 * on a solid red ground.
 *
 * Less red and real transparency between the marks was the direction asked
 * for, and the pitch is where it landed by eye: at 13 the tape was tighter and
 * showed less ground, and past about 17 the stripes stop reading as tape and
 * start reading as separate ticks. Both were rendered; the frames are in the
 * pull request. @unvalidated as a threshold - "reads as tape" is nobody's
 * measurement yet.
 */
export const CLOSURE_TAPE_CADENCE: TapeCadence = { stripe: 3.5, pitch: 15 }

/**
 * What fraction of the tape's length is red, for a given cadence.
 *
 * A stripe of thickness `w` set at `CLOSURE_STRIPE_ANGLE_DEG` to the line
 * covers `w / sin(angle)` of that line's length, so the answer is that over
 * the pitch. Derived rather than eyeballed because it is the claim this
 * treatment is actually judged on - "less red than the band it replaces" is a
 * number, and closureStyle.test.ts holds it as one.
 */
export function tapeRedFraction(cadence: TapeCadence): number {
  const along = cadence.stripe / Math.sin((CLOSURE_STRIPE_ANGLE_DEG * Math.PI) / 180)
  return along / cadence.pitch
}

/**
 * The layer id for a SECOND instance of the closure treatment, drawn over the
 * trails source rather than the closures source.
 *
 * features/NEARBY_TRAILS.md §3: OPRHP marks 125 trails `Closed` long-term, and
 * those are a different FEED from the live temporary-closures layer - the
 * geometry is the trail line itself, carrying a status, not a closure record
 * with its own extent. Two feeds, and deliberately ONE treatment: "one
 * vocabulary for 'do not walk this', which is the argument that won: a hiker
 * learns one mark."
 *
 * What keeps the two kinds apart is the SHEET, never the line - lib/
 * lineDetail.ts's closureLine says "Closed by NYS OPRHP" with the layer's own
 * edit date, where a temporary closure's sheet gives its reason and reporting
 * date. A hiker who cannot tell them apart on the map has lost nothing,
 * because the instruction is identical.
 */
export const LONG_TERM_CLOSURE_LAYER_ID = 'long-term-closure-band'

/** The status value §3 admits, normalized by the pipeline. Compared
 *  lower-case, because a steward's casing is not a decision this map should
 *  depend on. */
export const LONG_TERM_CLOSED_STATUS = 'closed'

/**
 * The filter selecting long-term-closed trail lines out of the trails source.
 *
 * `downcase` on the property rather than a list of spellings, so a layer that
 * starts publishing `CLOSED` keeps drawing its barrier. `to-string` first, so
 * a missing status is `""` and matches nothing rather than throwing on null.
 *
 * §3 is explicit that `Proposed` (19 segments) and blank/Unknown (24) never
 * ship AT ALL - that exclusion belongs to the pipeline, not here. This filter
 * only decides which of the lines that DID ship wear the barrier, and it errs
 * toward drawing none: an unrecognised status draws no barrier, which is the
 * safe direction only because the pipeline has already refused to publish the
 * statuses nobody stands behind.
 */
export const LONG_TERM_CLOSED_FILTER: unknown[] = [
  '==',
  ['downcase', ['to-string', ['get', 'trail_status']]],
  LONG_TERM_CLOSED_STATUS,
]

export interface ClosureLayerOptions {
  /** A distinct id, for a second instance over a different source. Defaults
   *  to the temporary-closure layer's own. */
  bandId?: string
  /** Restricts the layer to part of its source. Omitted for the closures
   *  feed, where every feature IS a closure. */
  filter?: unknown[]
}

/**
 * ONE LAYER, WHICH IS THE POINT RATHER THAN A SIMPLIFICATION. A casing drawn
 * as a second line beneath this one would show through every transparent gap
 * in the tape, which is exactly the defect the tape exists to end - so the
 * casing lives in the image instead, where it can only ever edge a stripe.
 *
 * Still an array, and still built by one function for every source that needs
 * it: ONE TREATMENT, NOT TWO THAT CURRENTLY AGREE. map/style.ts calls this
 * once per source that can carry a closed line - four today: the closures
 * feed, the A.T.'s long-term-closed lines, the nearby network's, and the
 * corridor-view sketch's below the seam (#869) - and the only things that may
 * differ between them are the id, the source and the filter.
 *
 * The count is the part of this sentence that rots; the fourth call arrived
 * and it still read "three times". Nothing here needs the number, so a fifth
 * source is a call site and not an edit to this comment - what holds the
 * guarantee is the byte-identical construction below, which the tests assert
 * as a property rather than by counting layers.
 */
export function buildClosureLayers(
  sourceId: string,
  options: ClosureLayerOptions = {},
): LayerSpecification[] {
  const { bandId = CLOSURE_LAYER_ID, filter } = options
  // Spread rather than a conditional key so the instances produce byte-
  // identical layer objects apart from id, source and filter - the property
  // that lets the tests assert "one treatment" rather than "two that currently
  // agree".
  const restrict = filter === undefined ? {} : { filter: filter as never }
  return [
    {
      id: bandId,
      type: 'line',
      source: sourceId,
      ...restrict,
      layout: { 'line-cap': 'butt', 'line-join': 'round' },
      paint: {
        // The image, never a flat colour and never an expression off
        // blaze_color - a closure must not inherit the hue of the trail it
        // sits on. Baking the red into the pixels is a stronger form of that
        // guarantee than the flat literal it replaces: there is no colour
        // property left here for anyone to data-drive by accident.
        'line-pattern': CLOSURE_TAPE_IMAGE_ID,
        'line-width': CLOSURE_TAPE_WIDTH,
      },
    },
  ]
}
