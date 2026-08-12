// How an ATC trail update is drawn, and why it is not a second colour.
//
// The band's job is identical to a closure's - "do not walk down there, go
// around" - so it is drawn with identical weight: the same width, the same
// hard casing, the same colour. Only the RHYTHM differs, longer bars with
// longer gaps, so that the two read as the same kind of thing from the same
// distance while still being distinguishable side by side.
//
// THE COLOUR IS DELIBERATELY NOT DIFFERENT, and this is the decision worth
// recording because the obvious move is to make it different. #461 asks that
// an ATC update "must not look like an OurHike closure", and the temptation
// is to answer that on the canvas. It would be the wrong place. A second
// barrier colour on a safety map does not read as "a different organisation
// said this" - it reads as "a different severity", and a hiker who learns
// that one shade of barrier is softer than the other has learned something
// false. Both mean the trail is shut. Provenance is a question about WHO
// says so, and it is answered where a hiker can actually read an answer: the
// banner names the ATC first (lib/atcUpdates.ts) and the sheet carries their
// name, their date and a link to their page (chrome/AtcUpdateSheet.tsx).
//
// The same reasoning lib/closureStyle.ts applies to blazes applies here in
// miniature: the distinction that matters is structural rather than
// chromatic, because colour is the first thing to go in greyscale, in direct
// sun, and for a red-green colour-blind hiker.

import type { LayerSpecification } from '@maplibre/maplibre-gl-style-spec'
import {
  CLOSURE_CASING_COLOR,
  CLOSURE_CASING_WIDTH,
  CLOSURE_COLOR,
  CLOSURE_LINE_WIDTH,
} from './closureStyle'

export const ATC_UPDATE_LAYER_ID = 'atc-update-band'
export const ATC_UPDATE_CASING_LAYER_ID = 'atc-update-casing'

/**
 * Long bars, long gaps - the same barrier tape at a slower cadence.
 *
 * In line-width units, like every MapLibre dasharray, and deliberately a
 * multiple of the closure rhythm's scale rather than an unrelated pattern: at
 * a glance the two are the same treatment, and only a close look separates
 * them. That is the intended reading order, since what a hiker must register
 * instantly is "barrier", and only then "whose".
 */
export const ATC_UPDATE_BAR_RHYTHM: [number, number] = [1.5, 0.75]

/** Re-exported so a test can hold the equality rather than the numbers, and
 *  so the coupling to lib/closureStyle.ts is visible from this file. An ATC
 *  band that quietly drifted narrower than a closure band would be exactly
 *  the severity distinction this module refuses to draw. */
export const ATC_UPDATE_LINE_WIDTH = CLOSURE_LINE_WIDTH
export const ATC_UPDATE_CASING_WIDTH = CLOSURE_CASING_WIDTH
export const ATC_UPDATE_COLOR = CLOSURE_COLOR
export const ATC_UPDATE_CASING_COLOR = CLOSURE_CASING_COLOR

export function buildAtcUpdateLayers(sourceId: string): LayerSpecification[] {
  return [
    {
      id: ATC_UPDATE_CASING_LAYER_ID,
      type: 'line',
      source: sourceId,
      layout: { 'line-cap': 'butt', 'line-join': 'round' },
      paint: {
        'line-color': ATC_UPDATE_CASING_COLOR,
        'line-width': ATC_UPDATE_LINE_WIDTH + ATC_UPDATE_CASING_WIDTH * 2,
      },
    },
    {
      id: ATC_UPDATE_LAYER_ID,
      type: 'line',
      source: sourceId,
      layout: { 'line-cap': 'butt', 'line-join': 'round' },
      paint: {
        'line-color': ATC_UPDATE_COLOR,
        'line-width': ATC_UPDATE_LINE_WIDTH,
        'line-dasharray': ATC_UPDATE_BAR_RHYTHM,
      },
    },
  ]
}
