// How a closure is drawn (WIREFRAMES.md §7).
//
// A closure is a LINE, not a pin: a wide barred red band with a hard casing
// along the closed geometry. Its whole job is to be unmistakable for a red
// blaze, which is a thinner SOLID line with a hairline casing.
//
// That distinction is safety-critical and is deliberately structural rather
// than chromatic. Colour alone vanishes in greyscale, in direct sun on a
// phone screen, and for a red-green colour-blind hiker - between them, a
// large share of the moments when "do not walk down there" most needs to
// land. So a closure differs in width, in rhythm, and in casing weight, and
// tests hold all three.
//
// The rhythm difference got sharper when the blazes went solid (map/style.ts):
// a barred band next to a dashed red blaze was two rhythms to tell apart, and
// a barred band next to a solid red line is barred versus not. The width
// difference had to be re-earned instead - the blazes got wider at the same
// time, so these numbers moved with them to keep the ratio the tests below
// hold. That coupling is the point of importing the blaze widths there rather
// than eyeballing a gap here.

import type { LayerSpecification } from '@maplibre/maplibre-gl-style-spec'

export const CLOSURE_LAYER_ID = 'closure-band'
export const CLOSURE_CASING_LAYER_ID = 'closure-casing'

/** Wide enough that the band reads as a barrier, not a route - which means
 *  comfortably more than twice the widest blaze on the map. */
export const CLOSURE_LINE_WIDTH = 10
/** Hard casing, per WIREFRAMES.md - not the blaze's hairline. */
export const CLOSURE_CASING_WIDTH = 2
export const CLOSURE_COLOR = '#b2321f'
export const CLOSURE_CASING_COLOR = '#14130f'

/**
 * Short, even bars - visually a barrier tape rather than a trail rhythm, and
 * the only dashed trail-line treatment left on the map now that every blaze is
 * drawn solid. In line-width units, like every MapLibre dasharray.
 */
export const CLOSURE_BAR_RHYTHM: [number, number] = [0.5, 0.35]

/**
 * The layer ids for a SECOND instance of the closure treatment, drawn over the
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
export const LONG_TERM_CLOSURE_CASING_LAYER_ID = 'long-term-closure-casing'

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
  /** Distinct ids, for a second instance over a different source. Defaults to
   *  the temporary-closure layer's own. */
  bandId?: string
  casingId?: string
  /** Restricts the layer to part of its source. Omitted for the closures
   *  feed, where every feature IS a closure. */
  filter?: unknown[]
}

export function buildClosureLayers(
  sourceId: string,
  options: ClosureLayerOptions = {},
): LayerSpecification[] {
  const {
    bandId = CLOSURE_LAYER_ID,
    casingId = CLOSURE_CASING_LAYER_ID,
    filter,
  } = options
  // Spread rather than a conditional key so the two instances produce byte-
  // identical layer objects apart from id, source and filter - the property
  // that lets the tests assert "one treatment" rather than "two that currently
  // agree".
  const restrict = filter === undefined ? {} : { filter: filter as never }
  return [
    {
      id: casingId,
      type: 'line',
      source: sourceId,
      ...restrict,
      layout: { 'line-cap': 'butt', 'line-join': 'round' },
      paint: {
        'line-color': CLOSURE_CASING_COLOR,
        'line-width': CLOSURE_LINE_WIDTH + CLOSURE_CASING_WIDTH * 2,
      },
    },
    {
      id: bandId,
      type: 'line',
      source: sourceId,
      ...restrict,
      layout: { 'line-cap': 'butt', 'line-join': 'round' },
      paint: {
        // A flat literal, never a data-driven expression off blaze_color -
        // a closure must not inherit the hue of the trail it sits on.
        'line-color': CLOSURE_COLOR,
        'line-width': CLOSURE_LINE_WIDTH,
        'line-dasharray': CLOSURE_BAR_RHYTHM,
      },
    },
  ]
}
