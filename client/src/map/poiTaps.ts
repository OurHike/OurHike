// Tapping a pin: turning a point on the canvas back into a POI id.
//
// This is the whole of the map's side of the detail sheet. It deliberately
// does NOT know what a sheet is - it answers "which POI did that touch land
// on", and the shell decides what to show.
//
// Two things here are not incidental.
//
// **The hit area is a box, not a pixel.** MapLibre will happily answer a
// single-point query, and on a desktop with a mouse that is exactly right. This
// app is used with a gloved thumb, in rain, on a screen someone is squinting at
// in the sun, and a pin that only opens when hit dead centre reads as a pin
// that does not open at all - which is the state this replaces. So the query is
// a small box around the touch and a near miss still counts.
//
// **The POI id travels in `properties`, not as the feature id.** See
// poiLayers.ts's `poiFeatureCollection`: MapLibre parses a string feature id
// with `parseInt`, and every id the pipeline publishes ("atc_shelters:<guid>")
// parses to NaN. Reading `feature.id` here would have looked right and
// identified nothing.

import type { Map as MapLibreMap, MapMouseEvent, PointLike } from 'maplibre-gl'
import { POI_PIN_SIZE } from './poiIcons'
import { POI_LAYER_ID, POI_ID_PROPERTY } from './poiLayers'

/** `--min-touch-target` (chrome/chrome.css), which every other control on the
 *  map screen already meets. */
const MIN_TOUCH_TARGET_PX = 44

/**
 * How far off a pin a touch may land and still open it, in CSS pixels.
 *
 * Derived rather than chosen: it is exactly what a pin drawn at full size
 * needs to reach the minimum touch target above. Written down as a number it
 * would be a second thing to remember the day POI_PIN_SIZE moves, which is the
 * mistake lib/seriousWarnings.ts already made once with the same constant.
 *
 * Zero-floored because a pin bigger than a touch target needs no help, and a
 * negative slop would query an inside-out box.
 */
export const POI_TAP_SLOP_PX = Math.max(0, (MIN_TOUCH_TARGET_PX - POI_PIN_SIZE) / 2)

/** The touch, as the box that is actually queried. */
export function poiTapBox(point: { x: number; y: number }): [PointLike, PointLike] {
  return [
    [point.x - POI_TAP_SLOP_PX, point.y - POI_TAP_SLOP_PX],
    [point.x + POI_TAP_SLOP_PX, point.y + POI_TAP_SLOP_PX],
  ]
}

/** The POI under a point on the canvas, or null for bare map. */
export function poiIdAt(
  map: MapLibreMap,
  point: { x: number; y: number },
): string | null {
  // Before the style has parsed, querying a layer it does not hold fires an
  // error event rather than throwing - a touch on a map with no pins on it yet
  // should be silent, not a warning in the console.
  if (map.getLayer(POI_LAYER_ID) === undefined) return null

  // First, because MapLibre returns what is drawn on top first - and the pin
  // drawn on top is the one somebody could see well enough to aim at. The
  // collision engine (`icon-allow-overlap: false`) means two pins this close
  // are adjacent rather than stacked, so this is rarely even a choice.
  const [feature] = map.queryRenderedFeatures(poiTapBox(point), {
    layers: [POI_LAYER_ID],
  })
  if (feature === undefined) return null

  const id = feature.properties?.[POI_ID_PROPERTY]
  return typeof id === 'string' && id !== '' ? id : null
}

/**
 * Wires taps on the pin layer to `onSelect`, and returns a detach function.
 *
 * Every tap reports, including the misses: a pin's id when the touch lands on
 * one, null for bare map. The null is load-bearing - it is how the floating
 * waypoint card closes without hunting for its × button, the gesture every
 * map card teaches (tap elsewhere to put it away). Dragging does not dismiss:
 * MapLibre withholds the click event when the gesture was a pan, so riding
 * the map around with a card open never throws the card away.
 *
 * The pointer cursor is part of the same job rather than a separate concern:
 * on the web, something that opens when clicked has to look like it will, and
 * it is answered by the same "is there a pin here" question the tap uses.
 */
export function attachPoiTaps(
  map: MapLibreMap,
  onSelect: (id: string | null) => void,
): () => void {
  const onClick = (event: MapMouseEvent) => {
    onSelect(poiIdAt(map, event.point))
  }

  // A layer-scoped `mouseenter`/`mouseleave` pair would be the usual way to do
  // this, and would ask a different question than the tap does - MapLibre's
  // delegated listeners query the exact point, with none of the slop above. A
  // cursor that turns into a pointer over a slightly different area than the
  // one that actually opens the sheet is worse than no cursor change at all.
  const onMouseMove = (event: MapMouseEvent) => {
    map.getCanvas().style.cursor = poiIdAt(map, event.point) === null ? '' : 'pointer'
  }

  map.on('click', onClick)
  map.on('mousemove', onMouseMove)

  return () => {
    map.off('click', onClick)
    map.off('mousemove', onMouseMove)
    // Left behind, a pointer cursor outlives the thing it was pointing at.
    map.getCanvas().style.cursor = ''
  }
}
