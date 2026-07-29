// How a closure is drawn (WIREFRAMES.md §7).
//
// A closure is a LINE, not a pin: a wide barred red band with a hard casing
// along the closed geometry. Its whole job is to be unmistakable for a red
// blaze, which is a thin dash with a hairline casing.
//
// That distinction is safety-critical and is deliberately structural rather
// than chromatic. Colour alone vanishes in greyscale, in direct sun on a
// phone screen, and for a red-green colour-blind hiker - between them, a
// large share of the moments when "do not walk down there" most needs to
// land. So a closure differs in width, in rhythm, and in casing weight, and
// tests hold all three.

import type { LayerSpecification } from '@maplibre/maplibre-gl-style-spec'

export const CLOSURE_LAYER_ID = 'closure-band'
export const CLOSURE_CASING_LAYER_ID = 'closure-casing'

/** Wide enough that the band reads as a barrier, not a route. */
export const CLOSURE_LINE_WIDTH = 6
/** Hard casing, per WIREFRAMES.md - not the blaze's hairline. */
export const CLOSURE_CASING_WIDTH = 1.5
export const CLOSURE_COLOR = '#b2321f'
export const CLOSURE_CASING_COLOR = '#14130f'

/**
 * Short, even bars - visually a barrier tape rather than a trail rhythm, and
 * deliberately not a value any blaze uses (see BLAZE_DASH_RHYTHMS).
 * In line-width units, like every MapLibre dasharray.
 */
export const CLOSURE_BAR_RHYTHM: [number, number] = [0.5, 0.35]

export function buildClosureLayers(sourceId: string): LayerSpecification[] {
  return [
    {
      id: CLOSURE_CASING_LAYER_ID,
      type: 'line',
      source: sourceId,
      layout: { 'line-cap': 'butt', 'line-join': 'round' },
      paint: {
        'line-color': CLOSURE_CASING_COLOR,
        'line-width': CLOSURE_LINE_WIDTH + CLOSURE_CASING_WIDTH * 2,
      },
    },
    {
      id: CLOSURE_LAYER_ID,
      type: 'line',
      source: sourceId,
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
