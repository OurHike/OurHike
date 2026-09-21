// How a closure is drawn (WIREFRAMES.md §7).
//
// A closure is a LINE, not a pin: a barred band laid along the closed
// geometry - red ticks across an opaque band of the sheet's own paper, inside
// a dark edge. Its whole job is to be unmistakable for a red blaze, which is
// a thinner SOLID line with a hairline casing.
//
// That distinction is safety-critical and is deliberately structural rather
// than chromatic. Colour alone vanishes in greyscale, in direct sun on a
// phone screen, and for a red-green colour-blind hiker - between them, a
// large share of the moments when "do not walk down there" most needs to
// land. So a closure differs in width and in texture, and tests hold both.
//
// THE PAPER UNDER-BAND IS THE MAINTAINER'S CHOICE OF 2026-09-17 (#1575), and
// it is the one thing here that has survived every rebuild. From 2026-08-27
// there was nothing at all between the marks, so the trail stayed visible
// through its own closure. Then every trail line became one red by default
// (lib/blaze.ts's PLAIN_TRAIL_COLOR - the same hex as CLOSURE_COLOR), and a
// red line showing through the gaps read as more of the same red. Shown five
// rendered treatments, the maintainer chose this one: "I think I like option
// E the best". The ground is the paper map/style.ts's closureTapeGround picks
// for the sheet, and it is swapped with the sheet: the sheet's own by day, so
// on parchment it is parchment - and, since 2026-09-18, the field day sheet's
// white on every dark sheet but red light's, because "the sheet's paper"
// built for night_hike put red on near-black ink over a near-black map ("it's
// really hard to tell it's a closure when the background is black"). Red
// light keeps its ink, and closureTapeGround's docstring says why that is a
// question left open rather than answered. What option E costs is the
// sentence it replaced: the trail is not visible through its closure any
// more.
//
// THREE SPELLINGS OF THAT BAND, AND THE THIRD IS THIS ONE. Reading them in
// order is the fastest way to understand why the code looks like this:
//
//  1. A BARRED BAND, to 2026-08-27. A dashed 10px red line over a SOLID 14px
//     casing, so the casing showed through every gap: 5px of red, then 3.5px
//     of #14130f, the whole way along. 41% of the band's length was the
//     darkest ink on a sheet whose contours are hairlines, and what it drew
//     was a black rope with red ticks - the standard cartographic mark for a
//     railway. Measured off the shipped constants, rendered 2026-08-27 in
//     MapLibre 6.4.1.
//
//  2. BARRIER TAPE, to 2026-09-21. One `line-pattern` layer: red diagonals at
//     55 degrees, each carrying its own dark edge, on the paper. That fixed
//     the railway by construction - there was no casing under a gap to show
//     through, because the edge was on the marks themselves - and #1598 gave
//     it an outline, more red, and a width that grows with the zoom.
//
//  3. A BARRED BAND AGAIN, from 2026-09-21 (#1599) - but with the paper in
//     it, which is the whole difference from (1). The maintainer, on the
//     frame CI photographed at Bear Mountain: "The closure lines still look
//     horrible when going around turns."
//
// WHY THE TAPE HAD TO GO, which is the part worth keeping. MapLibre maps a
// `line-pattern` along a line BY DISTANCE, and at a bend the outer side of a
// wide band travels farther than the inner side - so the image is sheared
// across the join. A mark running DIAGONALLY across that shear breaks: every
// white stripe arrived at a bend straight and left it as a zigzag, and the
// 1.25px dark edge each stripe carried, being a diagonal mark too, smeared
// into dark bars across the red. Both faults a hiker could see were that one
// cause. OPRHP's closed geometry bends constantly, so this was not an edge
// case; it was most of the mark.
//
// A DASH CANNOT DO THAT. MapLibre computes `line-dasharray` from distance
// along the line in the shader and draws each tick square to it, so there is
// no diagonal for the shear to break and no image to keep in register across
// a join. The map's own context trails are dashed through the same bends
// without a mark out of place, which is the evidence this was chosen on.
//
// WHAT THAT COSTS, named rather than glossed: the 55-degree lean is gone, and
// with it the read of hazard tape. A barred band is a weaker metaphor. What
// it is not is (1): the gaps here hold the SHEET'S PAPER, opaque, so the
// darkest ink on the map appears only at the band's two edges and never
// between the ticks. The railway came from what filled the gaps, not from the
// ticks being square.
//
// SO EVERY LAYER IS A PLAIN LINE and there is no generated image anywhere in
// this treatment. map/closureTape.ts - the rasteriser, its pixel ratio, the
// per-paper image registration and the stripe geometry - was deleted with the
// tape, and the sheet's paper is a `line-color` a sheet change repaints
// rather than an image it re-points.

import type { LayerSpecification } from '@maplibre/maplibre-gl-style-spec'

export const CLOSURE_LAYER_ID = 'closure-band'

/**
 * How wide the band is drawn where a hiker is navigating by it, in CSS
 * pixels - the top of the taper closureTapeWidth builds (#1598).
 *
 * It was 14 and flat at every zoom from 2026-08-27. The maintainer read the
 * result on 2026-09-20: *"The trail closures are not easily visible. Adjust
 * the settings so that the closures are readily apparent at all the zoom
 * levels."* One flat number is the half of that complaint this constant
 * owns: the same band over a 1.5 px sketch line at the opening camera and
 * over a 4.5 px A.T. at navigation zoom, saying nothing about how close the
 * hiker is looking.
 *
 * IT WENT TO 17 AND CAME BACK, which is the useful part of this note. The
 * first cut of #1598 raised it, and the frame CI photographed - Bear
 * Mountain, the densest closure cell in the release - showed what 17 plus a
 * 1.5 px outline plus half its length in red actually draws at z13: ropes,
 * with the trails under them gone. The maintainer, 2026-09-21, off that
 * frame: take the navigation band back, keep the outline and the overview
 * rhythm. So the zoom that was broken (z8, CLOSURE_TAPE_FAR_WIDTH) keeps
 * every part of the fix and the zoom that was not goes back to the width it
 * had, carrying only the edge.
 *
 * Wide enough that the band reads as a barrier rather than a route, which
 * means comfortably more than twice the widest blaze on the map: 14 against
 * BLAZE_LINE_WIDTH's 4.5 is 3.1x, where the 2026-08-27 band's own line was
 * 2.2x - and the outline puts 3 px more on top of that, which the blaze has
 * no answer to at all. closureStyle.test.ts holds that ratio against
 * map/style.ts rather than against a number restated here, so widening a
 * through-route still has to widen this with it.
 *
 * `@unvalidated` as a number: 14 is where it was before any of this, and
 * what would settle it is a closure getting spotted on a screen somebody was
 * not told to search.
 */
export const CLOSURE_TAPE_WIDTH = 14

/**
 * How wide the band is drawn at and below CLOSURE_TAPE_NEAR_MIN_ZOOM, in CSS
 * pixels - the bottom of the taper (#1598).
 *
 * Narrower than the navigation weight rather than wider, which is the
 * opposite of what "make it more visible" sounds like and is the point: down
 * here the trail lines themselves taper to 1.5 px (map/style.ts's
 * NETWORK_OVERVIEW_FAR_WIDTH), and a band three times the navigation line's
 * width over a sketch line would be a blob whose LENGTH still says nothing.
 * What makes a closure findable at this camera is the outline below, not
 * more fill.
 *
 * Still wider than the navigation-zoom BLAZE_LINE_WIDTH, so the "markedly
 * wider than any blaze" rule holds at the bottom of the taper too, which is
 * what closureStyle.test.ts asserts.
 */
export const CLOSURE_TAPE_FAR_WIDTH = 11

/**
 * The casing weight the 2026-08-27 band carried, in CSS pixels.
 *
 * NOTHING PAINTS WITH THIS, and saying so is the point of keeping it. What
 * survives here is a REFERENCE WEIGHT rather than a paint value: the 2px this
 * map used to outline a safety mark with, and which its successors are held
 * to be lighter than. lib/atcUpdateStyle.ts's `atcNoticeRimWidths` names it
 * as the failure case in so many words - "put `CLOSURE_CASING_WIDTH` back and
 * the test goes red on 2.9px" - and its ATC_NOTICE_CASING_WIDTH is asserted
 * under it, as CLOSURE_OUTLINE_WIDTH is.
 */
export const CLOSURE_CASING_WIDTH = 2

export const CLOSURE_COLOR = '#b2321f'
export const CLOSURE_CASING_COLOR = '#14130f'

/**
 * The first zoom the near rhythm draws at, below which the band steps to
 * CLOSURE_OVERVIEW_DASH (#1598).
 *
 * DERIVED FROM THE CLOSURES' OWN LENGTHS, not from the seam. A rhythm says
 * nothing about a line shorter than one of its pitches, so the question this
 * answers is: at what zoom is the SHORTEST closure on this map longer than
 * the near rhythm's pitch? OPRHP's closed runs are 1.1 to 1.9 km (measured
 * for `client/preview-shots/long-term-closures.mjs` against the pinned
 * release's network overview), and at latitude 41 a zoom's metres per pixel
 * is 117,610 / 2^z - so 1.1 km spans 2.4 px at z8, 4.8 at z9, 9.6 at z10 and
 * 19.2 at z11. It first clears a whole pitch between z10 and z11, so z11 is
 * the first zoom at which the near rhythm is guaranteed to say something on
 * every closure the map draws.
 *
 * THIS WAS THE SEAM UNTIL THE SEAM MOVED, and the move is why it is derived
 * now. The first version of this constant was POI_PIN_MIN_ZOOM's 9, on the
 * argument that a texture change is cheapest where the map's own layers are
 * already handing over. Then #1590 put the seam at 7 (`poiLayers.ts`), which
 * would have left z8 to z10 drawing the near rhythm over closures 2 to 10 px
 * long - the exact defect this constant exists to prevent. The tie to the
 * seam was a convenience and the arithmetic is the reason, so the arithmetic
 * is what the number follows.
 */
export const CLOSURE_TAPE_NEAR_MIN_ZOOM = 11

/**
 * The zoom the band reaches CLOSURE_TAPE_WIDTH at (#1598).
 *
 * Two zooms above the rhythm step, so the band grows across the band of
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
 * and z16: *"the only one whose shape survives being 4 px long"*. A closure
 * at the opening camera is a handful of pixels long, and at that size a
 * texture is not resolvable by anybody - what is left to recognise is a
 * silhouette, and a band with a hard edge has one where a band without one
 * does not.
 *
 * IT IS A REAL LINE UNDER A REAL LINE NOW, which is what the 2026-09-21
 * rebuild bought. Under the tape it was a wider layer beneath a `line-pattern`
 * one, and at a bend the sheared image let it read as bars ACROSS the band
 * rather than an edge along it. Two opaque solid lines cannot do that: the
 * band covers every pixel of the casing but the overhang, at a join as
 * anywhere else, because coverage is a union and neither is a texture.
 *
 * 1.5 rather than 2: lighter than CLOSURE_CASING_WIDTH, the reference weight
 * this map used to outline a safety mark with, which both of its successors
 * are held under.
 */
export const CLOSURE_OUTLINE_WIDTH = 1.5

/** A band's rhythm: how long a red tick is and how long the gap after it,
 *  both in LINE WIDTHS, which is what MapLibre's `line-dasharray` counts in.
 *  Measuring in widths rather than pixels is what makes the rhythm scale
 *  with closureTapeWidth's taper, so the mark is one shape at every zoom
 *  rather than a rhythm that drifts against its own band. */
export interface BandDash {
  /** The red tick, across the band. */
  tick: number
  /** The paper after it. */
  gap: number
}

/** `dash` with both numbers multiplied, which keeps dashRedFraction exactly
 *  where it was - the property both the overview rhythm and the ATC's
 *  slower one are built on. */
export function scaleDash(dash: BandDash, scale: number): BandDash {
  return { tick: dash.tick * scale, gap: dash.gap * scale }
}

/**
 * The closure's own rhythm, at the zooms a hiker navigates by.
 *
 * RED COVERS 41% OF THE BAND'S LENGTH here, and that number has a history
 * worth reading before anybody moves it. The tape carried 28% from
 * 2026-08-27, and the direction was written into the constant: less red was
 * the answer to the railway, where the non-red half of the band's length was
 * the darkest ink on the sheet. The maintainer read 28% on the map and asked
 * for the opposite on 2026-09-20 - *"the closures are not easily visible"* -
 * and it went to 51%; photographed at Bear Mountain the band read as a rope,
 * and the navigation weight came back on 2026-09-21. 41% is where it landed:
 * half again what it carried, rather than nearly double.
 *
 * The two directions are not in conflict, and #1575 is what separates them.
 * What August was refusing was ink over a TRANSPARENT band. Here the gap is
 * the sheet's own paper, so 41% red on white is a different mark from 41%
 * red on black rather than more of it.
 *
 * `0.35` and `0.51` rather than a rounder pair because the tick lands on
 * 4.9 px at the full width - which is what the tape's own 4 px stripe
 * covered ALONG the line once its 55-degree lean was accounted for, so the
 * rebuild changed the mark's angle and not its weight. `@unvalidated` as a
 * threshold: "reads as a barrier" is nobody's measurement yet.
 */
export const CLOSURE_DASH: BandDash = { tick: 0.35, gap: 0.51 }

/**
 * What the overview rhythm scales the near one by, on both numbers (#1598).
 *
 * WHY A SECOND RHYTHM EXISTS AT ALL, in one measurement, is
 * CLOSURE_TAPE_NEAR_MIN_ZOOM's docstring: below z11 a closed run is shorter
 * than one near pitch, so which part of the rhythm it lands on decides
 * whether a hiker sees a red tick or a blank slab of paper. Halving the
 * pitch halves the length a closure has to reach before it is guaranteed to
 * carry one.
 *
 * BOTH NUMBERS BY THE SAME FACTOR, which is lib/atcUpdateStyle.ts's
 * ATC_UPDATE_DASH_SCALE argument run the other way and for the same reason:
 * scaling only the gap would change how much of the band is red, and the
 * overview band must be the same mark at a smaller size rather than a
 * different claim. dashRedFraction is identical for the two by construction,
 * and closureStyle.test.ts holds that equality rather than these numbers.
 */
export const CLOSURE_DASH_OVERVIEW_SCALE = 0.5

/** The closure's rhythm below CLOSURE_TAPE_NEAR_MIN_ZOOM: the near one at
 *  CLOSURE_DASH_OVERVIEW_SCALE. */
export const CLOSURE_OVERVIEW_DASH: BandDash = scaleDash(
  CLOSURE_DASH,
  CLOSURE_DASH_OVERVIEW_SCALE,
)

/**
 * What fraction of the band's length is red, for a given rhythm.
 *
 * A tick square to the line covers exactly its own length, so this is the
 * tick over the pitch and nothing else - where the tape's own
 * `tapeRedFraction` had to divide by the sine of the stripe's lean first.
 * That simplification is the rebuild in one function: the mark stopped being
 * something whose coverage depended on its angle.
 */
export function dashRedFraction(dash: BandDash): number {
  return dash.tick / (dash.tick + dash.gap)
}

/** A rhythm as MapLibre's `line-dasharray` wants it. */
export function dashArray(dash: BandDash): [number, number] {
  return [dash.tick, dash.gap]
}

/**
 * The band's `line-dasharray`: the overview rhythm below
 * CLOSURE_TAPE_NEAR_MIN_ZOOM, the near one from it in (#1598).
 *
 * A `step` rather than an `interpolate` because a dash array is not
 * interpolatable - the style spec says so, and style.test.ts validates the
 * built style against it. `near` is a parameter so lib/atcUpdateStyle.ts can
 * hand in its own slower rhythm and get the same step at the same zoom: one
 * treatment, two feeds, which is the guarantee that file exists to keep.
 */
export function closureDashExpression(
  near: BandDash = CLOSURE_DASH,
  overview: BandDash = CLOSURE_OVERVIEW_DASH,
): unknown[] {
  return [
    'step',
    ['zoom'],
    ['literal', dashArray(overview)],
    CLOSURE_TAPE_NEAR_MIN_ZOOM,
    ['literal', dashArray(near)],
  ]
}

/**
 * The band's `line-width`, in CSS pixels, `outset` px wider on each side.
 *
 * CLOSURE_TAPE_FAR_WIDTH at and below CLOSURE_TAPE_NEAR_MIN_ZOOM,
 * CLOSURE_TAPE_WIDTH from CLOSURE_TAPE_FULL_WIDTH_ZOOM in, linear between -
 * the shape map/style.ts's overviewTaper gives every line on this map, so
 * the closure band grows on the same schedule the lines under it do. One
 * lower stop shared with the rhythm step, so a closure at an overview camera
 * changes weight and texture at one zoom rather than two.
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

/** The id of the outline drawn under the band `bandId` - derived rather
 *  than spelled per call site, so a fifth closure source cannot end up with
 *  a band and no edge. */
export function closureCasingId(bandId: string): string {
  return `${bandId}-casing`
}

/** The id of the sheet's paper drawn between `bandId`'s ticks. Derived for
 *  closureCasingId's reason, and named separately because map/style.ts
 *  repaints exactly these on a sheet change. */
export function closureGroundId(bandId: string): string {
  return `${bandId}-ground`
}

export interface ClosureLayerOptions {
  /** The paper the band's ticks sit on, as a `#rrggbb` hex - what
   *  map/style.ts's closureTapeGround picks for the appearance the style is
   *  built for. Required rather than defaulted, because this module cannot
   *  know which sheet a caller is drawing, and a band on the wrong paper is
   *  the wrong mark on every closure. */
  ground: string
  /** A distinct id, for a second instance over a different source. Defaults
   *  to the temporary-closure layer's own. */
  bandId?: string
  /** Restricts the layer to part of its source. Omitted for the closures
   *  feed, where every feature IS a closure. */
  filter?: unknown[]
}

/**
 * THREE LAYERS, ALL PLAIN LINES, bottom to top: the dark edge, the sheet's
 * paper, the red ticks. The header has why there is no image left in any of
 * them; what matters at the call site is that none of the three carries a
 * texture, so none of them can shear at a join.
 *
 * The paper is a LAYER now rather than pixels baked into an image, and that
 * is #1575's decision read the other way round: it made the ground opaque,
 * and the only reason it lived in the image was that a `line-pattern` layer
 * has no colour of its own. Nothing here is a pattern, so the ground is a
 * `line-color` - which a sheet change repaints in place rather than
 * re-pointing at another image.
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
  const line = (id: string, paint: Record<string, unknown>): LayerSpecification =>
    ({
      id,
      type: 'line',
      source: sourceId,
      ...restrict,
      layout,
      paint,
    }) as LayerSpecification
  return [
    // The outline, FIRST so it is underneath. The band above covers all of
    // it but the CLOSURE_OUTLINE_WIDTH showing past each side, which is what
    // a hiker sees as the edge - and it covers it at a join too, because two
    // opaque solid lines cover by union.
    line(closureCasingId(bandId), {
      'line-color': CLOSURE_CASING_COLOR,
      'line-width': closureTapeWidth(CLOSURE_OUTLINE_WIDTH),
    }),
    // The sheet's paper, opaque along the whole run (#1575, option E). This
    // is the layer that stops the band being the railway the 2026-08-27 one
    // was: without it the casing below would show through every gap between
    // the ticks, which is exactly what that band did.
    line(closureGroundId(bandId), {
      'line-color': ground,
      'line-width': closureTapeWidth(),
    }),
    // The ticks. A flat colour, never an expression off blaze_color - a
    // closure must not inherit the hue of the trail it sits on.
    line(bandId, {
      'line-color': CLOSURE_COLOR,
      'line-width': closureTapeWidth(),
      'line-dasharray': closureDashExpression(),
    }),
  ]
}

/**
 * The layer id for a SECOND instance of the closure treatment, drawn over the
 * trails source rather than the closures source.
 *
 * features/NEARBY_TRAILS.md §3: OPRHP marks 125 trails `Closed` long-term,
 * and those are a different FEED from the live temporary-closures layer - the
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
