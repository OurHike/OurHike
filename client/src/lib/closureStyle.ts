// How a closure is drawn (WIREFRAMES.md §7).
//
// A closure is a LINE, not a pin: barrier tape laid along the closed geometry -
// red diagonals with a dark edge, on an opaque band of the sheet's own paper.
// Its whole job is to be unmistakable for a red blaze, which is a thinner
// SOLID line with a hairline casing.
//
// THE PAPER UNDER-BAND IS THE MAINTAINER'S CHOICE OF 2026-09-17 (#1575). From
// 2026-08-27 there was nothing at all between the stripes, so the trail stayed
// visible through its own closure. Then every trail line became one red by
// default (lib/blaze.ts's PLAIN_TRAIL_COLOR - the same hex as CLOSURE_COLOR),
// and a red line showing through the gaps read as more of the same red. Shown
// five rendered treatments - the tape as it was, orange stripes, yellow and
// black, a monochrome barrier, and this - the maintainer chose this one: "I
// think I like option E the best". The ground is the paper map/style.ts's
// closureTapeGround picks for the sheet, baked into the image per paper by
// map/closureTape.ts and swapped with the sheet: the sheet's own by day, so
// on parchment it is parchment - and, since 2026-09-18, the field day sheet's
// white on every dark sheet but red light's. The five treatments were
// rendered on the day sheet, and "the sheet's paper" built for night_hike
// put red stripes on near-black ink over a near-black map: "it's really hard
// to tell it's a closure when the background is black, with black & red
// alternating for the closure. Maybe that should be red & white just for
// dark mode." Red light keeps its ink, and closureTapeGround's docstring
// says why that is a question left open rather than answered. What option E
// costs is exactly the sentence it replaced: the trail is not visible
// through its closure any more. The stripes, their cadence, their edges and
// the tape's width did not move THEN; #1598 moved all four, and its own
// paragraph below says by how much.
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
// The tape fixes that by construction rather than by tuning. No casing under
// a TRANSPARENT gap to show through anything - because the dark edge every
// stripe carries IS the casing. That edge is thinner than the overhang it
// replaces and CLOSURE_STRIPE_EDGE says so; what it buys is that the casing
// can only ever be an edge, since there is nothing under a gap to fill it
// with.
//
// THE BAND GREW AN OUTLINE AND A TAPER ON 2026-09-20 (#1598), and neither
// reopens that. The gaps stopped being transparent at #1575, so a line under
// the band shows only at its two edges - which is what CLOSURE_OUTLINE_WIDTH
// draws, and it is the edge the old casing was always meant to be. The
// maintainer: "The trail closures are not easily visible. Adjust the settings
// so that the closures are readily apparent at all the zoom levels." Shown
// four treatments drawn at z8, z13 and z16, they took the outlined one, "the
// only one whose shape survives being 4 px long". So the band is now two
// layers, carries 51% red rather than 28%, grows from CLOSURE_TAPE_FAR_WIDTH
// to CLOSURE_TAPE_WIDTH across z11 to z13, and steps to a half-scale cadence
// below z11 - the zoom at which the shortest closure this map draws first
// clears a whole pitch. Each of those constants says what it rests on.

import type { LayerSpecification } from '@maplibre/maplibre-gl-style-spec'

export const CLOSURE_LAYER_ID = 'closure-band'

/** The stem of the image ids the band's `line-pattern` points at - one image
 *  per sheet paper since #1575, named by `closureTapeImageId` below.
 *  Registered on the live map by map/closureTape.ts, which owns the pixels;
 *  this module owns only the spec they are drawn from. */
export const CLOSURE_TAPE_IMAGE_ID = 'closure-tape'

/**
 * Which of the tape's two cadences an image carries (#1598).
 *
 * `near` is the tape at the zooms a hiker navigates by. `overview` is the
 * same tape at half scale, for the zooms where a whole closure is a few
 * pixels long - see CLOSURE_TAPE_OVERVIEW_SCALE for why the second one has
 * to exist at all.
 */
export type TapeRange = 'near' | 'overview'

/**
 * The id of the closure tape drawn on `ground` - the sheet's paper as a
 * `#rrggbb` hex (#1575, option E) - at `range`'s cadence (#1598).
 *
 * One image per paper rather than one image and a second layer under it: a
 * `line-pattern` layer ignores `line-color`, so the ground can only be in the
 * pixels, and a separate under-band layer per tape layer would double the
 * five tape layers for a colour the image can simply carry. map/closureTape.ts
 * registers the image for every paper the sheet table can produce, and
 * map/style.ts's attachMapAppearance points each tape layer at the current
 * one - both through this function, so the two agree by construction.
 *
 * `near` is the default so that every existing caller and every test that
 * names an image without a range still names the tape a hiker navigating
 * sees, which is the one the id `closure-tape-ffffff` has always meant.
 */
export function closureTapeImageId(ground: string, range: TapeRange = 'near'): string {
  const stem =
    range === 'near' ? CLOSURE_TAPE_IMAGE_ID : `${CLOSURE_TAPE_IMAGE_ID}-overview`
  return `${stem}-${ground.replace('#', '').toLowerCase()}`
}

/** Drawn at 2x, like every other generated image on this map
 *  (map/poiIcons.ts's POI_PIN_PIXEL_RATIO), so the stripes stay crisp on a
 *  phone. */
export const CLOSURE_TAPE_PIXEL_RATIO = 2

/**
 * How wide the tape is drawn where a hiker is navigating by it, in CSS
 * pixels - the top of the taper closureTapeWidth builds (#1598).
 *
 * It was 14 and flat at every zoom from 2026-08-27, which was exactly the
 * ink the barred band before it occupied - its 10px line plus the 2px casing
 * showing past each side - so that replacement moved no pixel outward or
 * inward and changed only what was inside them. The maintainer read the
 * result on 2026-09-20: *"The trail closures are not easily visible. Adjust
 * the settings so that the closures are readily apparent at all the zoom
 * levels."* One flat number is the half of that complaint this constant
 * owns: the same band over a 1.5 px sketch line at the opening camera and
 * over a 4.5 px A.T. at navigation zoom, saying nothing about how close the
 * hiker is looking.
 *
 * Wide enough that the tape reads as a barrier rather than a route, which
 * means comfortably more than twice the widest blaze on the map: 17 against
 * BLAZE_LINE_WIDTH's 4.5 is 3.8x, where the band's own line was 2.2x.
 * closureStyle.test.ts holds that ratio against map/style.ts rather than
 * against a number restated here, so widening a through-route still has to
 * widen this with it.
 *
 * `@unvalidated` as a number. 17 came off the frames of the 2026-09-20 poll
 * and nobody has watched it on a phone. What would settle it is what would
 * settle CLOSURE_STRIPE_ANGLE_DEG: whether a closure gets spotted on a
 * screen somebody was not told to search.
 */
export const CLOSURE_TAPE_WIDTH = 17

/**
 * How wide the tape is drawn at and below CLOSURE_TAPE_NEAR_MIN_ZOOM, in CSS
 * pixels - the bottom of the taper (#1598).
 *
 * Narrower than the navigation weight rather than wider, which is the
 * opposite of what "make it more visible" sounds like and is the point: down
 * here the trail lines themselves taper to 1.5 px
 * (map/style.ts's NETWORK_OVERVIEW_FAR_WIDTH), and a band three times the
 * navigation line's width over a sketch line would be a blob whose LENGTH
 * still says nothing. What makes a closure findable at this camera is the
 * outline below, not more fill.
 *
 * Still wider than the navigation-zoom BLAZE_LINE_WIDTH, so the "markedly
 * wider than any blaze" rule holds at the bottom of the taper too, which is
 * what closureStyle.test.ts asserts.
 */
export const CLOSURE_TAPE_FAR_WIDTH = 11

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
 * The first zoom the near cadence draws at, below which the tape steps to
 * CLOSURE_TAPE_OVERVIEW_CADENCE (#1598).
 *
 * DERIVED FROM THE CLOSURES' OWN LENGTHS, not from the seam. A pattern says
 * nothing about a line shorter than one of its pitches, so the question this
 * answers is: at what zoom is the SHORTEST closure on this map longer than
 * the near cadence's 12 px? OPRHP's closed runs are 1.1 to 1.9 km (measured
 * for `client/preview-shots/long-term-closures.mjs` against the pinned
 * release's network overview), and at latitude 41 a zoom's metres per pixel
 * is 117,610 / 2^z - so 1.1 km spans 2.4 px at z8, 4.8 at z9, 9.6 at z10 and
 * 19.2 at z11. It first clears a whole pitch between z10 and z11, so z11 is
 * the first zoom at which the near cadence is guaranteed to say something on
 * every closure the map draws.
 *
 * THIS WAS THE SEAM UNTIL THE SEAM MOVED, and the move is why it is derived
 * now. The first version of this constant was POI_PIN_MIN_ZOOM's 9, on the
 * argument that a cadence change is cheapest where the map's own layers are
 * already handing over. Then #1590 put the seam at 7 (`poiLayers.ts`), which
 * would have left z8 to z10 drawing the near cadence over closures 2 to 10
 * px long - the exact defect this constant exists to prevent. The tie to the
 * seam was a convenience and the arithmetic is the reason, so the arithmetic
 * is what the number follows.
 */
export const CLOSURE_TAPE_NEAR_MIN_ZOOM = 11

/**
 * The zoom the band reaches CLOSURE_TAPE_WIDTH at (#1598).
 *
 * Two zooms above the cadence step, so the band grows across the band of
 * zooms where a hiker moves from "which park is this" to "which side of the
 * brook am I on", and is at full weight for every zoom closer than that. z13
 * is the park frame the closure recipe photographs and the frame the
 * treatment was chosen on, which is the only claim behind the number:
 * `@unvalidated`, and what would settle it is the same field look every
 * other constant here is waiting on.
 */
export const CLOSURE_TAPE_FULL_WIDTH_ZOOM = 13

/**
 * The dark outline the whole band carries, in CSS pixels per side (#1598).
 *
 * THE MAINTAINER'S CHOICE OF 2026-09-20, off four treatments drawn at z8, z13
 * and z16: *"the only one whose shape survives being 4 px long"*, which is
 * the poll option they took. A closure at the opening camera is a handful of
 * pixels long, and at that size a texture is not resolvable by anybody -
 * what is left to recognise is a silhouette, and a band with a hard edge has
 * one where a band without one does not.
 *
 * WHY THIS IS NOT THE CASING THIS FILE SPENDS A PARAGRAPH REFUSING. That
 * refusal was right and is about a different band: a casing under tape whose
 * gaps were TRANSPARENT showed through every gap, which is what drew the
 * black rope with red ticks. #1575 made the tape opaque, so a casing under
 * it can only ever appear at its two edges - the objection does not reach
 * the band that ships now, and the outline is the edge the old casing was
 * always meant to be.
 *
 * 1.5 rather than 2: lighter than CLOSURE_CASING_WIDTH, the reference weight
 * this map used to outline a safety mark with, which both of its successors
 * are held under. Heavier than CLOSURE_STRIPE_EDGE, because the outline has
 * to read at a zoom where a stripe's edge does not.
 */
export const CLOSURE_OUTLINE_WIDTH = 1.5

/**
 * The band's `line-width`, in CSS pixels, `outset` px wider on each side.
 *
 * CLOSURE_TAPE_FAR_WIDTH at and below CLOSURE_TAPE_NEAR_MIN_ZOOM,
 * CLOSURE_TAPE_WIDTH from CLOSURE_TAPE_FULL_WIDTH_ZOOM in, linear between -
 * the shape map/style.ts's overviewTaper gives every line on this map, so
 * the closure band grows on the same schedule the lines under it do. One
 * lower stop shared with the cadence step, so a closure at an overview
 * camera changes weight and texture at one zoom rather than two.
 *
 * `outset` is what makes the outline one function rather than two that agree
 * today: the casing layer asks for the same taper CLOSURE_OUTLINE_WIDTH
 * wider on each side, so a change to either stop cannot move the band
 * without moving its edge with it.
 */
export function closureTapeWidth(outset = 0): unknown[] {
  return [
    'interpolate',
    ['linear'],
    ['zoom'],
    CLOSURE_TAPE_NEAR_MIN_ZOOM,
    CLOSURE_TAPE_FAR_WIDTH + outset * 2,
    CLOSURE_TAPE_FULL_WIDTH_ZOOM,
    CLOSURE_TAPE_WIDTH + outset * 2,
  ]
}

/**
 * The band's `line-pattern` on `ground`: the overview tape below the seam,
 * the near tape from it in (#1598).
 *
 * A `step` rather than an `interpolate` because `line-pattern` is
 * zoom-dependent and NOT interpolatable - the style spec says so, and
 * style.test.ts validates the built style against it. `imageId` is a
 * parameter rather than closureTapeImageId itself so lib/atcUpdateStyle.ts
 * can hand in its own naming and get the same switch at the same zoom: one
 * treatment, two feeds, which is the guarantee that file exists to keep.
 */
export function tapePattern(
  ground: string,
  imageId: (ground: string, range: TapeRange) => string = closureTapeImageId,
): unknown[] {
  return [
    'step',
    ['zoom'],
    imageId(ground, 'overview'),
    CLOSURE_TAPE_NEAR_MIN_ZOOM,
    imageId(ground, 'near'),
  ]
}

/** The id of the outline drawn under the band `bandId` - derived rather
 *  than spelled per call site, so a fifth closure source cannot end up with
 *  a band and no edge. */
export function closureCasingId(bandId: string): string {
  return `${bandId}-casing`
}

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
 * The closure's own cadence, at the zooms a hiker navigates by.
 *
 * `pitch` is measured along the line rather than across the stripes because
 * that is the axis the image tiles on, and a pitch that is not a whole number
 * of image pixels tiles with a seam - map/closureTape.ts depends on this
 * landing exactly on its pixel ratio.
 *
 * MORE RED THAN IT CARRIED, AND THIS IS A REVERSAL (#1598). From 2026-08-27
 * this was `{ stripe: 3.5, pitch: 15 }`, which puts red at 28% of the tape's
 * length, and the reversed direction was written into the constant: "less red
 * and real transparency between the marks was the direction asked for",
 * against the first hazard-tape pass's roughly 60% red on a solid red ground.
 * The maintainer read 28% on the map and asked for the opposite on 2026-09-20
 * - *"the closures are not easily visible"* - and chose, off four rendered
 * treatments at z8, z13 and z16, the one that raises red to 51% and puts a
 * hard outline round the band.
 *
 * The two directions are not actually in conflict, and the reason is the
 * change #1575 made in between. What the August direction was refusing was
 * ink over a TRANSPARENT band, where the non-red half of the tape's length
 * was the near-black casing showing through - the black rope with red ticks
 * this file's header measures. Since #1575 the non-red half is the sheet's
 * own paper (option E), so 51% red on white is a different mark from 59% red
 * on black, not more of it.
 *
 * `{ stripe: 5, pitch: 12 }` rather than a rounder pair because both have to
 * be whole numbers of image pixels at CLOSURE_TAPE_PIXEL_RATIO - 10 and 24 -
 * and because halving them for the overview cadence has to leave that true
 * as well. @unvalidated as a threshold: "reads as tape" is still nobody's
 * measurement, and 51% is a pick off a drawn frame.
 */
export const CLOSURE_TAPE_CADENCE: TapeCadence = { stripe: 5, pitch: 12 }

/**
 * What the overview tape scales the near one by, on both axes (#1598).
 *
 * WHY A SECOND CADENCE EXISTS AT ALL, in one measurement. OPRHP's closed
 * runs are 1.1 to 1.9 km long (measured for
 * `client/preview-shots/long-term-closures.mjs` against the pinned release's
 * network overview). At latitude 41 that is 3 to 7 pixels at z8 and 7 to 13
 * at z9, against a pattern that repeats every `pitch` pixels along the line -
 * so at the near cadence a whole closure fits inside one tile, and which tile
 * it happens to land on decides whether a hiker sees red diagonals or a blank
 * slab of paper. Halving the pitch halves the length a closure has to reach
 * before it is guaranteed to cross a stripe.
 *
 * BOTH AXES BY THE SAME FACTOR, which is lib/atcUpdateStyle.ts's
 * ATC_UPDATE_TAPE_SCALE argument run the other way and for the same reason:
 * scaling only the pitch would change how much of the tape is red, and the
 * overview tape must be the same mark at a smaller size rather than a
 * different claim. tapeRedFraction is identical for the two by construction,
 * and closureStyle.test.ts holds that equality rather than these numbers.
 */
export const CLOSURE_TAPE_OVERVIEW_SCALE = 0.5

/** The closure's cadence at and below the seam: the near cadence at
 *  CLOSURE_TAPE_OVERVIEW_SCALE. Whole image pixels at the ratio, 5 and 12,
 *  for the reason the near cadence is. */
export const CLOSURE_TAPE_OVERVIEW_CADENCE: TapeCadence = {
  stripe: CLOSURE_TAPE_CADENCE.stripe * CLOSURE_TAPE_OVERVIEW_SCALE,
  pitch: CLOSURE_TAPE_CADENCE.pitch * CLOSURE_TAPE_OVERVIEW_SCALE,
}

/**
 * The same edge on the overview tape, scaled with the cadence (#1598).
 *
 * SCALED, WHERE THE ATC's DOUBLED TAPE LEAVES ITS EDGE ALONE, and the
 * difference is arithmetic rather than taste. An unscaled 1.25 px edge on
 * each side of a 2.5 px stripe at a 6 px pitch puts ink on
 * (2.5 + 2 x 1.25) / sin(55 degrees) / 6 = 102% of the tape's length: the
 * edges of neighbouring stripes meet, the paper between them disappears, and
 * the overview tape would draw as one flat dark-red band. Scaled, the ink is
 * 76% - exactly the near cadence's, which is what "the same tape, smaller"
 * has to mean.
 *
 * The ATC's tape goes the other way, doubling the cadence and keeping the
 * edge, where merging is impossible and a thinner-looking edge is the whole
 * softer claim it is allowed to make.
 */
export const CLOSURE_TAPE_OVERVIEW_EDGE =
  CLOSURE_STRIPE_EDGE * CLOSURE_TAPE_OVERVIEW_SCALE

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
  /** The paper the tape lies on, as a `#rrggbb` hex - what map/style.ts's
   *  closureTapeGround picks for the appearance the style is built for.
   *  Required rather than defaulted, because this module cannot know which
   *  sheet a caller is drawing, and a tape on the wrong paper is the wrong
   *  band on every closure. */
  ground: string
  /** A distinct id, for a second instance over a different source. Defaults
   *  to the temporary-closure layer's own. */
  bandId?: string
  /** Restricts the layer to part of its source. Omitted for the closures
   *  feed, where every feature IS a closure. */
  filter?: unknown[]
}

/**
 * TWO LAYERS SINCE #1598, AND THE SECOND ONE IS THE EDGE. The tape's own
 * paragraph above this file used to end "one layer, which is the point
 * rather than a simplification", and the argument behind it was that a
 * casing drawn beneath tape whose gaps were TRANSPARENT showed through every
 * gap - the defect the tape was built to end. #1575 filled the gaps with the
 * sheet's paper, and a casing under an opaque band can only appear at its two
 * edges, so the objection stopped reaching this band a month before the
 * maintainer asked for an outline. What still holds from that paragraph is
 * where the ground lives: a `line-pattern` layer has no colour of its own, so
 * the paper is in the pixels and always will be.
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
  options: ClosureLayerOptions,
): LayerSpecification[] {
  const { ground, bandId = CLOSURE_LAYER_ID, filter } = options
  // Spread rather than a conditional key so the instances produce byte-
  // identical layer objects apart from id, source and filter - the property
  // that lets the tests assert "one treatment" rather than "two that currently
  // agree".
  const restrict = filter === undefined ? {} : { filter: filter as never }
  const layout = { 'line-cap': 'butt', 'line-join': 'round' } as const
  return [
    {
      // The outline, FIRST so it is underneath (#1598). A flat colour and a
      // wider taper: the band above covers all of it but the
      // CLOSURE_OUTLINE_WIDTH showing past each side, which is what a hiker
      // sees as the edge. Its width comes from the same closureTapeWidth the
      // band's does, so the two cannot drift.
      id: closureCasingId(bandId),
      type: 'line',
      source: sourceId,
      ...restrict,
      layout,
      paint: {
        'line-color': CLOSURE_CASING_COLOR,
        'line-width': closureTapeWidth(CLOSURE_OUTLINE_WIDTH) as never,
      },
    },
    {
      id: bandId,
      type: 'line',
      source: sourceId,
      ...restrict,
      layout,
      paint: {
        // The image, never a flat colour and never an expression off
        // blaze_color - a closure must not inherit the hue of the trail it
        // sits on. Baking the red into the pixels is a stronger form of that
        // guarantee than the flat literal it replaces: there is no colour
        // property left here for anyone to data-drive by accident. Which
        // image is the sheet's AND the zoom's since #1598: the tape drawn on
        // this sheet's paper (#1575), at the cadence this zoom can resolve.
        'line-pattern': tapePattern(ground) as never,
        'line-width': closureTapeWidth() as never,
      },
    },
  ]
}
