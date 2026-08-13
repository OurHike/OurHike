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
// **There are two ranks to hit, and they need different boxes** (#597). A pin
// is 38 px and needs 3 px of help to reach a touch target; a dot is 4 px and
// needs 20. The second box is big enough to hold more than one waypoint, which
// is why what used to be `queryRenderedFeatures(...)[0]` is now a stated rule -
// a pin beats a dot, and among dots the nearest to the centre of the touch
// wins. See {@link poiIdAt}.
//
// **The POI id travels in `properties`, not as the feature id.** See
// poiLayers.ts's `poiFeatureCollection`: MapLibre parses a string feature id
// with `parseInt`, and every id the pipeline publishes ("atc_shelters:<guid>")
// parses to NaN. Reading `feature.id` here would have looked right and
// identified nothing.

import type { Map as MapLibreMap, MapMouseEvent, PointLike } from 'maplibre-gl'
import { POI_PIN_SIZE } from './poiIcons'
import {
  POI_DOT_LAYER_ID,
  POI_DOT_SIZE_PX,
  POI_LAYER_ID,
  POI_ID_PROPERTY,
} from './poiLayers'

/** `--min-touch-target` (chrome/chrome.css), which every other control on the
 *  map screen already meets. */
const MIN_TOUCH_TARGET_PX = 44

/** What a mark of this drawn size needs around it to be reachable by a thumb.
 *  Zero-floored: a mark bigger than a touch target needs no help, and a
 *  negative slop would query an inside-out box. */
function slopFor(drawnSizePx: number): number {
  return Math.max(0, (MIN_TOUCH_TARGET_PX - drawnSizePx) / 2)
}

/**
 * How far off a pin a touch may land and still open it, in CSS pixels.
 *
 * Derived rather than chosen: it is exactly what a pin drawn at full size
 * needs to reach the minimum touch target above. Written down as a number it
 * would be a second thing to remember the day POI_PIN_SIZE moves, which is the
 * mistake lib/seriousWarnings.ts already made once with the same constant.
 */
export const POI_TAP_SLOP_PX = slopFor(POI_PIN_SIZE)

/**
 * The same question asked of a dot, which is 4 px rather than 38 - so the box
 * is about 20 px, and it will ROUTINELY hold more than one waypoint.
 *
 * That is the whole reason {@link poiIdAt} needs a stated rule below rather
 * than the `[0]` it used to take. A box this size around a shelter at z11 has
 * its campsite in it too, and "whichever MapLibre listed first" is not an
 * answer anybody could predict from looking at the screen.
 */
export const POI_DOT_TAP_SLOP_PX = slopFor(POI_DOT_SIZE_PX)

/** A touch, as the box that is actually queried, at a given slop. */
function tapBox(point: { x: number; y: number }, slop: number): [PointLike, PointLike] {
  return [
    [point.x - slop, point.y - slop],
    [point.x + slop, point.y + slop],
  ]
}

/** The touch, as the box that is actually queried for pins. */
export function poiTapBox(point: { x: number; y: number }): [PointLike, PointLike] {
  return tapBox(point, POI_TAP_SLOP_PX)
}

/** The id a queried feature carries, or null where it carries none. */
function featureId(feature: {
  properties?: Record<string, unknown> | null
}): string | null {
  const id = feature.properties?.[POI_ID_PROPERTY]
  return typeof id === 'string' && id !== '' ? id : null
}

/** Where a queried point feature sits on the canvas, or null if it has no
 *  point geometry to project. */
function screenPosition(
  map: MapLibreMap,
  feature: { geometry?: { type?: string; coordinates?: unknown } },
): { x: number; y: number } | null {
  const geometry = feature.geometry
  if (geometry?.type !== 'Point') return null
  const coordinates = geometry.coordinates
  if (!Array.isArray(coordinates) || coordinates.length < 2) return null
  const [lng, lat] = coordinates as [number, number]
  if (typeof lng !== 'number' || typeof lat !== 'number') return null
  if (!Number.isFinite(lng) || !Number.isFinite(lat)) return null
  return map.project([lng, lat])
}

/**
 * The dot nearest the centre of the touch.
 *
 * Nearest rather than first, and it is the half of #597's tap rule that costs
 * something to get wrong: at 20 px of slop the "first" dot is whichever the
 * renderer happened to list, which on a shelter-and-campsite pair is a coin
 * toss the hiker cannot see. Nearest-to-the-thumb is the only rule that agrees
 * with what they were aiming at.
 *
 * A dot with no projectable geometry does not lose to one that has it - it
 * simply cannot be measured, so it is kept as a fallback in draw order and
 * used only if nothing else can be.
 */
function nearestDotId(
  map: MapLibreMap,
  point: { x: number; y: number },
  features: readonly {
    properties?: Record<string, unknown> | null
    geometry?: { type?: string; coordinates?: unknown }
  }[],
): string | null {
  let best: string | null = null
  let bestDistance = Number.POSITIVE_INFINITY
  let fallback: string | null = null

  for (const feature of features) {
    const id = featureId(feature)
    if (id === null) continue
    fallback ??= id

    const position = screenPosition(map, feature)
    if (position === null) continue

    const distance = Math.hypot(position.x - point.x, position.y - point.y)
    if (distance < bestDistance) {
      bestDistance = distance
      best = id
    }
  }

  return best ?? fallback
}

/**
 * The POI under a point on the canvas, or null for bare map.
 *
 * **A pin under the thumb beats a dot under the thumb** (#597). Not a
 * tie-break for its own sake: a pin is the rank a hiker can see and aim at, so
 * a touch that reaches one was almost certainly meant for it, and a 20 px dot
 * box that quietly out-voted a pin the hiker was looking straight at would be
 * the tap doing something other than what the screen invited.
 *
 * Two dots genuinely at one place is not this function's problem to solve -
 * that is features/POI_SITES.md §5's site card, reached through #526.
 */
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
  const [pin] = map.queryRenderedFeatures(poiTapBox(point), {
    layers: [POI_LAYER_ID],
  })

  // A pin was hit. Its id, or null where it carries none - and deliberately NOT
  // a fall-through to the dot rank, which would answer a touch on a malformed
  // pin with a NEIGHBOURING waypoint's id. Landing somebody on a waypoint they
  // did not touch is worse than opening nothing.
  if (pin !== undefined) return featureId(pin)

  if (map.getLayer(POI_DOT_LAYER_ID) === undefined) return null

  return nearestDotId(
    map,
    point,
    map.queryRenderedFeatures(tapBox(point, POI_DOT_TAP_SLOP_PX), {
      layers: [POI_DOT_LAYER_ID],
    }),
  )
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
