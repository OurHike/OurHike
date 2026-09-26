// How a closure is drawn (WIREFRAMES.md §7): CROSSED OUT (#1677).
//
// A closure is a LINE, not a pin: the closed trail itself, drawn so it
// cannot be read as a trail somebody may walk. Four layers per feed, bottom
// to top:
//
//  1. THE PAPER - an opaque line of the sheet's paper along the closed run,
//     wide enough to cover the trail line under it. It takes the trail's red
//     off the map for the length of the closure.
//  2. THE TRACE - a fine dotted line in the closure ink on that paper, so the
//     path stays traceable ("there is a trail here") without being drawn in
//     any trail's voice.
//  3. THE CROSSES - a chain of small ✕ marks along the trace, from
//     CLOSURE_NEAR_MIN_ZOOM in. Each is a symbol placed along the line, not
//     a texture mapped onto it.
//  4. THE MARK - one larger ✕ per closed run below CLOSURE_NEAR_MIN_ZOOM,
//     where the run is too short on screen to carry a chain.
//
// THE MAINTAINER'S CHOICE OF 2026-09-26, after four earlier spellings of the
// band had failed: "The route closure is not readable. The alternating colors
// just aren't working." Shown four treatments rendered at z9, z12 and z15 over
// Bear Mountain - no-entry signs along the line, a black band lettered CLOSED,
// signs at the ends only, and this one - they answered "I prefer crossed out
// design wise. I'm curious if it will work well or not." The last sentence is
// the honest status: @unvalidated beyond those renders, and what would settle
// it is a hiker spotting a closure on a phone in sun without being told to
// look.
//
// WHAT EVERY EARLIER BAND HAD IN COMMON, which is the part to keep reading
// before anybody reaches for red again. All four were red marks alternating
// with something else along the line: red dashes over a dark casing (a
// railway, to 2026-08-27), red diagonal tape on the sheet's paper (tore at
// every bend - MapLibre maps a `line-pattern` by distance, and the outside of
// a wide band travels farther than the inside), then red square ticks on the
// paper inside a dark outline (#1599). And since #1575 every trail line is
// that same red by default (lib/blaze.ts's PLAIN_TRAIL_COLOR), so each band
// was red on red: rendered 2026-09-26 in MapLibre 6.7.0 over the pinned
// release 2026-09-24-2, the closures at Bear Mountain merged into one red blob
// at z9 and read as candy-cane ropes at z12. None of that was a wrong number;
// the colour was doing the work and the colour was shared.
//
// SO THIS MARK DOES NOT USE THE CLOSURE RED AT ALL. The distinction is
// structural, which has been this file's rule since it was written: colour
// vanishes in greyscale, in direct sun and for a red-green colour-blind hiker.
// A ✕ is a shape no trail line has, and a trail that has lost its colour to a
// dotted grey trace is a texture no open trail has.
//
// WHY A SYMBOL AND NOT A PATTERN, which is what lets it survive a bend. A
// symbol placed along a line (`symbol-placement: line`) is a whole image put
// down at an anchor; nothing is stretched between anchors, so there is no
// shear to tear it. The trace is a `line-dasharray`, which MapLibre draws from
// distance in the shader and cannot shear either - the reason #1599 moved to a
// dash, and still true.
//
// WHY THE FAR MARK EXISTS, in one measurement. A 1.1 km closure (OPRHP's
// shortest runs are 1.1 to 1.9 km, measured for
// client/preview-shots/long-term-closures.mjs) is 4.8 px long at z9. No mark
// ALONG the line can be read at that length, so below CLOSURE_NEAR_MIN_ZOOM a
// closure is one ✕ at the middle of its run instead.
//
// ONE TREATMENT, FOUR FEEDS, AND THE ATC'S. map/style.ts calls
// buildClosureLayers once per source that can carry a closed line - the
// closures feed, the A.T.'s long-term-closed lines, the nearby network's, and
// the corridor sketch's - and lib/atcUpdateStyle.ts calls it for the ATC's
// band at twice the spacing. Only the id, the source, the filter and the
// spacing may differ.

import type { LayerSpecification } from '@maplibre/maplibre-gl-style-spec'

/**
 * The paper layer's id, and the layer a tap on a closure is tested against
 * (map/closureLayers.ts's closureIdAt). The paper is the one layer that covers
 * the whole closed run at a width, so it is the one a finger can hit anywhere
 * along it. The other three layers' ids are derived from it.
 */
export const CLOSURE_LAYER_ID = 'closure-band'

/**
 * The closure red. THE CROSSED-OUT MARK DOES NOT PAINT WITH IT (#1677), and
 * the header says why: every trail is this red by default. It stays exported
 * because other marks are held against it - the ATC notice triangle is drawn
 * in it (lib/atcUpdateStyle.ts), and the drought and pin suites assert their
 * own colours differ from it.
 */
export const CLOSURE_COLOR = '#b2321f'

/**
 * The ink the trace and the crosses are drawn in, on every sheet but red
 * light (map/style.ts's closureInk swaps it there). The darkest ink on the
 * map, on the sheet's paper, which is the highest contrast the map can make
 * and does not depend on hue.
 */
export const CLOSURE_INK = '#14130f'

/**
 * The casing weight the 2026-08-27 band carried, in CSS pixels.
 *
 * NOTHING PAINTS WITH THIS, and saying so is the point of keeping it. What
 * survives here is a REFERENCE WEIGHT rather than a paint value: the 2px this
 * map used to outline a safety mark with, and which its successors are held
 * to be lighter than. lib/atcUpdateStyle.ts's `atcNoticeRimWidths` names it
 * as the failure case in so many words - "put `CLOSURE_CASING_WIDTH` back and
 * the test goes red on 2.9px" - and its ATC_NOTICE_CASING_WIDTH is asserted
 * under it.
 */
export const CLOSURE_CASING_WIDTH = 2

/**
 * The pin seam: the zoom the far mark first draws at, going in.
 *
 * map/poiLayers.ts's POI_PIN_MIN_ZOOM, repeated as a literal because `lib/`
 * does not import from `map/` (lib/atcUpdateStyle.ts's
 * ATC_UPDATE_POINT_MIN_ZOOM makes the same trade), and closureStyle.test.ts
 * holds the two equal. Below the seam the map draws trail lines only - the
 * maintainer's call of 2026-09-08 (#1292), after two dozen point marks along
 * the corridor read as a rash. A closure there is still knocked out of the
 * trail and traced, which is the most that can be said about a run a pixel
 * or two long.
 */
export const CLOSURE_MARK_MIN_ZOOM = 7

/**
 * The zoom the chain of crosses takes over from the far mark, going in.
 *
 * DERIVED FROM THE SHORTEST CLOSURE AND THE CROSS'S OWN SIZE. MapLibre puts a
 * symbol on a line only where the line is at least as long as the symbol's
 * image, so the question is: at what zoom is the shortest closure on this map
 * longer than one cross? OPRHP's closed runs are 1.1 to 1.9 km, and at
 * latitude 41 a zoom's metres per pixel is 117,610 / 2^z - so 1.1 km spans
 * 9.6 px at z10 and 19.2 px at z11. The cross's image is
 * closureCrossImageSize() = 14 CSS px at full size and CLOSURE_CROSS_SIZE's
 * 0.8 of that here, 11.2 px. z10 is short of it and z11 clears it, so z11 is
 * the first zoom at which every closure on the map is guaranteed a cross.
 *
 * The same 11 the #1598 band stepped its rhythm at, by the same argument
 * (does the shortest closure hold one pitch), which is why it is the same
 * number and not a coincidence.
 */
export const CLOSURE_NEAR_MIN_ZOOM = 11

/**
 * How wide the paper is where a hiker navigates by it, in CSS pixels, reached
 * at CLOSURE_FULL_WIDTH_ZOOM.
 *
 * DERIVED, NOT PICKED: the widest trail line the map draws with its casing
 * (map/style.ts's CASING_LINE_WIDTH, 6.5 - the A.T. at 4.5 plus a 1 px
 * hairline each side, drawn when blaze colours are on) plus half a pixel
 * each side, so no red or casing shows past the paper's edge.
 * closureStyle.test.ts holds this against map/style.ts rather than against a
 * number restated here, so widening a through-route widens the paper with it.
 */
export const CLOSURE_PAPER_WIDTH = 7.5

/**
 * How wide the paper is at CLOSURE_MARK_MIN_ZOOM, in CSS pixels - the bottom
 * of the taper.
 *
 * Out there the trail lines themselves are 1.2 to 3 px (map/style.ts's
 * overview widths), so 4 covers any of them. A full-width paper at the seam
 * would draw every closure as a white worm wider than the trail it closes,
 * and the far mark is what carries the closure at that zoom anyway.
 * @unvalidated as a number: picked off the 2026-09-26 renders.
 */
export const CLOSURE_PAPER_FAR_WIDTH = 4

/** The zoom the paper and the trace reach full width at. z13 is the park
 *  frame the closure recipe photographs, where the #1598 band also reached
 *  full weight. */
export const CLOSURE_FULL_WIDTH_ZOOM = 13

/** The trace's width at the seam and at full zoom, in CSS pixels. With round
 *  caps this is also the diameter of each dot. @unvalidated: the 2026-09-26
 *  renders. */
export const CLOSURE_TRACE_FAR_WIDTH = 1.4
export const CLOSURE_TRACE_WIDTH = 2.2

/**
 * The trace's rhythm, in line widths as `line-dasharray` counts them: a
 * near-zero dash with round caps is a dot one width across, and the gap puts
 * the next one a little over two widths on.
 */
export const CLOSURE_TRACE_DASH: readonly [number, number] = [0.1, 2.2]

/**
 * How much of the ink the trace carries. Less than the crosses, so the
 * crosses read first and the trace reads as the path they sit on. On the
 * field sheet's white this puts the dots at about #6b6a67, a mid grey.
 */
export const CLOSURE_TRACE_OPACITY = 0.65

/**
 * The cross, in CSS pixels at full size: each stroke runs from the centre
 * CLOSURE_CROSS_ARM along both diagonals, is CLOSURE_CROSS_STROKE wide with
 * round ends, and the image carries CLOSURE_CROSS_PADDING of room past the ink
 * for the paper-coloured halo. map/closureCross.ts turns these into pixels.
 *
 * The image is a signed distance field (`sdf: true`) rather than coloured
 * pixels, so the ink and the halo are paint properties and a sheet change
 * repaints them in place - the same thing the paper's `line-color` gets.
 */
export const CLOSURE_CROSS_ICON_ID = 'closure-cross'
export const CLOSURE_CROSS_ARM = 2.5
export const CLOSURE_CROSS_STROKE = 2.2
export const CLOSURE_CROSS_PADDING = 3

/** The image's side in CSS pixels: the ink's reach plus the padding, rounded
 *  up to a whole pixel so it rasterises onto a whole number of device
 *  pixels. */
export function closureCrossImageSize(): number {
  const reach = CLOSURE_CROSS_ARM + CLOSURE_CROSS_STROKE / 2
  return Math.ceil(2 * (reach + CLOSURE_CROSS_PADDING))
}

/** The paper-coloured ring round each cross in the chain, in CSS pixels. It
 *  sits on the paper already, so this only has to part a cross from the
 *  trace's dots either side of it. */
export const CLOSURE_CROSS_HALO_WIDTH = 1.2

/** The chain's `icon-size`: a little smaller where it first draws, full size
 *  from CLOSURE_FULL_WIDTH_ZOOM in. */
export const CLOSURE_CROSS_SIZE: ReadonlyArray<[zoom: number, scale: number]> = [
  [CLOSURE_NEAR_MIN_ZOOM, 0.8],
  [CLOSURE_FULL_WIDTH_ZOOM, 1],
]

/**
 * Where the next cross goes along the line, in CSS pixels between anchors.
 *
 * MapLibre will not space symbols closer than 1.25 of their own length, so
 * the floor here is about 14 px at z11 and 17.5 px at full size; these sit a
 * little above it, so the chain reads as a run of separate marks rather than
 * a rope. `@unvalidated`: picked off the 2026-09-26 renders, where the
 * maintainer chose this look.
 */
export const CLOSURE_CROSS_SPACING: ReadonlyArray<[zoom: number, spacing: number]> = [
  [CLOSURE_NEAR_MIN_ZOOM, 18],
  [CLOSURE_FULL_WIDTH_ZOOM, 24],
]

/**
 * The far mark's `icon-size` - the same cross image, 2.2 times over, so the
 * mark a hiker learns from far out is the mark the chain is made of when they
 * zoom in. About 16 px of ink (the cross's 7.2 px reach, 2.2 times).
 */
export const CLOSURE_MARK_SIZE = 2.2

/** The far mark's paper ring, in CSS pixels. Wider than the chain's, because
 *  far out the mark sits on the map rather than on the paper, often over the
 *  red of the very trails it closes. */
export const CLOSURE_MARK_HALO_WIDTH = 2.5

/**
 * The far mark's collision padding, in CSS pixels.
 *
 * THE FAR MARK IS THE ONE CLOSURE LAYER THAT TAKES PART IN COLLISION, and on
 * purpose: a closed network like Bear Mountain's is a hundred line parts, and
 * each part's middle is a candidate. Placed with `icon-allow-overlap: false`,
 * the first mark in an area keeps it and the rest are dropped, so the area
 * reads as a few crosses rather than a scribble. It cannot hide a waypoint:
 * the far marks draw above the pins and so are placed first, and a pin that
 * loses its place to one falls back to its 2.5 px dot, the `circle` layer
 * under the pins that takes no part in collision (map/poiLayers.ts, #597 and
 * #1676). That is the standing a serious-warning pin already has over a
 * waypoint.
 */
export const CLOSURE_MARK_PADDING = 6

/** A list of [zoom, value] stops as a linear `interpolate` on zoom. */
function zoomRamp(stops: ReadonlyArray<readonly [number, number]>): unknown[] {
  return ['interpolate', ['linear'], ['zoom'], ...stops.flat()]
}

/** The paper's `line-width`: CLOSURE_PAPER_FAR_WIDTH at the seam,
 *  CLOSURE_PAPER_WIDTH from CLOSURE_FULL_WIDTH_ZOOM in. */
export function closurePaperWidth(): unknown[] {
  return zoomRamp([
    [CLOSURE_MARK_MIN_ZOOM, CLOSURE_PAPER_FAR_WIDTH],
    [CLOSURE_FULL_WIDTH_ZOOM, CLOSURE_PAPER_WIDTH],
  ])
}

/** The trace's `line-width`, on the paper's schedule. */
export function closureTraceWidth(): unknown[] {
  return zoomRamp([
    [CLOSURE_MARK_MIN_ZOOM, CLOSURE_TRACE_FAR_WIDTH],
    [CLOSURE_FULL_WIDTH_ZOOM, CLOSURE_TRACE_WIDTH],
  ])
}

/** The chain's `symbol-spacing`, every stop multiplied by `scale` - the ATC
 *  band's slower cadence is this at 2. */
export function closureCrossSpacing(scale = 1): unknown[] {
  return zoomRamp(CLOSURE_CROSS_SPACING.map(([zoom, spacing]) => [zoom, spacing * scale]))
}

/** The id of the dotted trace drawn over the paper `bandId`. Derived rather
 *  than spelled per call site, so a fifth feed cannot end up with a paper and
 *  no trace. */
export function closureTraceId(bandId: string): string {
  return `${bandId}-trace`
}

/** The id of the chain of crosses along `bandId`. */
export function closureCrossesId(bandId: string): string {
  return `${bandId}-crosses`
}

/** The id of the one far-out cross per run of `bandId`. */
export function closureMarkId(bandId: string): string {
  return `${bandId}-mark`
}

/** Every layer id one feed's closure draws with, bottom to top - what
 *  map/style.ts repaints on a sheet change and what the tests walk. */
export function closureLayerIds(bandId: string): string[] {
  return [bandId, closureTraceId(bandId), closureCrossesId(bandId), closureMarkId(bandId)]
}

export interface ClosureLayerOptions {
  /** The paper under the trace, as a `#rrggbb` hex - what map/style.ts's
   *  closureTapeGround picks for the sheet. Also the crosses' halo. Required,
   *  because this module cannot know which sheet a caller is drawing. */
  ground: string
  /** The trace's and the crosses' ink - map/style.ts's closureInk. */
  ink: string
  /** A distinct id, for a second instance over a different source. Defaults
   *  to the temporary-closure layer's own. */
  bandId?: string
  /** Restricts the layers to part of their source. Omitted for the closures
   *  feed, where every feature IS a closure. */
  filter?: unknown[]
  /** Multiplies the chain's spacing. 1 for a closure; the ATC band's slower
   *  cadence (lib/atcUpdateStyle.ts). */
  spacingScale?: number
}

/**
 * The four layers of one feed's closure, bottom to top: paper, trace, the
 * chain of crosses, the far mark. The header has what each is for.
 *
 * Built by one function for every feed, so the instances are byte-identical
 * apart from id, source, filter and spacing - the property the tests assert,
 * rather than four layer lists that currently agree.
 */
export function buildClosureLayers(
  sourceId: string,
  options: ClosureLayerOptions,
): LayerSpecification[] {
  const { ground, ink, bandId = CLOSURE_LAYER_ID, filter, spacingScale = 1 } = options
  const restrict = filter === undefined ? {} : { filter: filter as never }
  const line = { 'line-cap': 'round', 'line-join': 'round' } as const
  return [
    {
      id: bandId,
      type: 'line',
      source: sourceId,
      ...restrict,
      layout: line,
      paint: { 'line-color': ground, 'line-width': closurePaperWidth() as never },
    },
    {
      id: closureTraceId(bandId),
      type: 'line',
      source: sourceId,
      ...restrict,
      layout: line,
      paint: {
        // A flat colour, never an expression off blaze_color - a closure must
        // not inherit the hue of the trail it sits on.
        'line-color': ink,
        'line-opacity': CLOSURE_TRACE_OPACITY,
        'line-width': closureTraceWidth() as never,
        'line-dasharray': [...CLOSURE_TRACE_DASH],
      },
    },
    {
      id: closureCrossesId(bandId),
      type: 'symbol',
      source: sourceId,
      ...restrict,
      minzoom: CLOSURE_NEAR_MIN_ZOOM,
      layout: {
        'symbol-placement': 'line',
        'symbol-spacing': closureCrossSpacing(spacingScale) as never,
        'icon-image': CLOSURE_CROSS_ICON_ID,
        'icon-size': zoomRamp(CLOSURE_CROSS_SIZE) as never,
        'icon-rotation-alignment': 'map',
        // Drawn wherever the line reaches, and never displacing a trail
        // name or a pin: a chain that took part in collision would lose
        // crosses to every label near it, and a gap in the chain reads as a
        // gap in the closure.
        'icon-allow-overlap': true,
        'icon-ignore-placement': true,
      },
      paint: {
        'icon-color': ink,
        'icon-halo-color': ground,
        'icon-halo-width': CLOSURE_CROSS_HALO_WIDTH,
      },
    },
    {
      id: closureMarkId(bandId),
      type: 'symbol',
      source: sourceId,
      ...restrict,
      minzoom: CLOSURE_MARK_MIN_ZOOM,
      maxzoom: CLOSURE_NEAR_MIN_ZOOM,
      layout: {
        'symbol-placement': 'line-center',
        'icon-image': CLOSURE_CROSS_ICON_ID,
        'icon-size': CLOSURE_MARK_SIZE,
        'icon-rotation-alignment': 'viewport',
        // CLOSURE_MARK_PADDING's docstring: the one closure layer that
        // collides, so a closed network reads as a few marks.
        'icon-allow-overlap': false,
        'icon-padding': CLOSURE_MARK_PADDING,
      },
      paint: {
        'icon-color': ink,
        'icon-halo-color': ground,
        'icon-halo-width': CLOSURE_MARK_HALO_WIDTH,
      },
    },
  ] as LayerSpecification[]
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
