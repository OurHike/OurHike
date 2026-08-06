// Tapping the map: turning a point on the canvas back into the thing that
// was touched - a POI pin, a serious-warning pin, or a closure band.
//
// This is the whole of the map's side of every sheet and card. It
// deliberately does NOT know what a sheet is - it answers "what did that
// touch land on", and the shell decides what to show.
//
// Three things here are not incidental.
//
// **The hit area is a box, not a pixel.** MapLibre will happily answer a
// single-point query, and on a desktop with a mouse that is exactly right.
// This app is used with a gloved thumb, in rain, on a screen someone is
// squinting at in the sun, and a pin that only opens when hit dead centre
// reads as a pin that does not open at all - which is the state this
// replaces. So each query is a small box around the touch, sized per layer to
// bring its target up to one full touch target, and a near miss still counts.
//
// **One touch answers once.** The three tappable layers overlap - a warning
// pin sits over the pins, the pins sit over a closure band - and a touch that
// opened two sheets at once would put a screen-reader user inside a dialog
// with another announcing itself. So a single click handler asks in priority
// order (warning, then pin, then band: top of the draw order first, which is
// also what somebody could see well enough to aim at) and the losers are told
// null, the same dismissal every card already understands.
//
// **The ids travel in `properties`, not as feature ids.** See poiLayers.ts's
// `poiFeatureCollection`: MapLibre parses a string feature id with
// `parseInt`, and every id this app holds ("atc_shelters:<guid>", a UUID)
// parses to NaN. Reading `feature.id` here would have looked right and
// identified nothing.

import type { Map as MapLibreMap, MapMouseEvent, PointLike } from 'maplibre-gl'
import { POI_PIN_SIZE } from './poiIcons'
import { POI_LAYER_ID, POI_ID_PROPERTY } from './poiLayers'
import { WARNING_LAYER_ID, WARNING_ID_PROPERTY } from './warningLayers'
import { CLOSURE_ID_PROPERTY } from './closureLayers'
import { CLOSURE_LAYER_ID, CLOSURE_LINE_WIDTH } from '../lib/closureStyle'

/** `--min-touch-target` (chrome/chrome.css), which every other control on the
 *  map screen already meets. */
const MIN_TOUCH_TARGET_PX = 44

/**
 * How far off a target a touch may land and still open it, in CSS pixels.
 *
 * Derived rather than chosen: it is exactly what the target needs to reach
 * the minimum touch target above. Written down as numbers these would be a
 * second thing to remember the day a size moves, which is the mistake
 * lib/seriousWarnings.ts already made once with the pin size.
 *
 * Zero-floored because a target bigger than a touch target needs no help,
 * and a negative slop would query an inside-out box.
 */
function tapSlop(targetPx: number): number {
  return Math.max(0, (MIN_TOUCH_TARGET_PX - targetPx) / 2)
}

export const POI_TAP_SLOP_PX = tapSlop(POI_PIN_SIZE)

/** The band is ten pixels of line; the slop is what makes it tappable. */
export const CLOSURE_TAP_SLOP_PX = tapSlop(CLOSURE_LINE_WIDTH)

/** The touch, as the box that is actually queried. */
export function tapBox(
  point: { x: number; y: number },
  slop: number,
): [PointLike, PointLike] {
  return [
    [point.x - slop, point.y - slop],
    [point.x + slop, point.y + slop],
  ]
}

/** The id property of the topmost feature of `layerId` under a touch, or
 *  null for a miss - which includes a style that has no such layer yet. */
function featureIdAt(
  map: MapLibreMap,
  point: { x: number; y: number },
  layerId: string,
  idProperty: string,
  slop: number,
): string | null {
  // Before the style has parsed, querying a layer it does not hold fires an
  // error event rather than throwing - a touch on a map with nothing on it
  // yet should be silent, not a warning in the console.
  if (map.getLayer(layerId) === undefined) return null

  // First, because MapLibre returns what is drawn on top first - and what is
  // drawn on top is what somebody could see well enough to aim at.
  const [feature] = map.queryRenderedFeatures(tapBox(point, slop), {
    layers: [layerId],
  })
  if (feature === undefined) return null

  const id = feature.properties?.[idProperty]
  return typeof id === 'string' && id !== '' ? id : null
}

/** The POI under a point on the canvas, or null for bare map. */
export function poiIdAt(
  map: MapLibreMap,
  point: { x: number; y: number },
): string | null {
  return featureIdAt(map, point, POI_LAYER_ID, POI_ID_PROPERTY, POI_TAP_SLOP_PX)
}

/** The serious warning under a point, or null. Slop-free: the warning pin is
 *  already one full touch target by design (lib/seriousWarnings.ts). */
export function warningIdAt(
  map: MapLibreMap,
  point: { x: number; y: number },
): string | null {
  return featureIdAt(map, point, WARNING_LAYER_ID, WARNING_ID_PROPERTY, 0)
}

/** The closure band under a point, or null. */
export function closureIdAt(
  map: MapLibreMap,
  point: { x: number; y: number },
): string | null {
  return featureIdAt(
    map,
    point,
    CLOSURE_LAYER_ID,
    CLOSURE_ID_PROPERTY,
    CLOSURE_TAP_SLOP_PX,
  )
}

export interface MapTapHandlers {
  /** A POI pin was tapped, by id - null for a tap that landed elsewhere,
   *  which is how the floating card dismisses. */
  onSelectPoi?: (id: string | null) => void
  /** A serious-warning pin was tapped, by report id - or null. */
  onSelectWarning?: (id: string | null) => void
  /** A closure band was tapped, by closure id - or null. */
  onSelectClosure?: (id: string | null) => void
}

/**
 * Wires taps on every tappable layer to the handlers, and returns a detach
 * function.
 *
 * Every tap reports to every handler, one winner and the rest null: the null
 * is load-bearing - it is how a floating card closes without hunting for its
 * × button, the gesture every map card teaches (tap elsewhere to put it
 * away). Dragging does not dismiss: MapLibre withholds the click event when
 * the gesture was a pan, so riding the map around with a card open never
 * throws the card away.
 *
 * The pointer cursor is part of the same job rather than a separate concern:
 * on the web, something that opens when clicked has to look like it will, and
 * it is answered by the same "is there anything here" questions the tap uses.
 */
export function attachMapTaps(map: MapLibreMap, handlers: MapTapHandlers): () => void {
  const { onSelectPoi, onSelectWarning, onSelectClosure } = handlers

  /** Priority order is draw order, top first - see the module header. A
   *  layer nobody is handling is skipped entirely rather than asked and
   *  discarded. */
  const hits = (point: { x: number; y: number }) => {
    const warning = onSelectWarning === undefined ? null : warningIdAt(map, point)
    const poi = onSelectPoi === undefined || warning !== null ? null : poiIdAt(map, point)
    const closure =
      onSelectClosure === undefined || warning !== null || poi !== null
        ? null
        : closureIdAt(map, point)
    return { warning, poi, closure }
  }

  const onClick = (event: MapMouseEvent) => {
    const { warning, poi, closure } = hits(event.point)
    onSelectWarning?.(warning)
    onSelectPoi?.(poi)
    onSelectClosure?.(closure)
  }

  // A layer-scoped `mouseenter`/`mouseleave` pair would be the usual way to
  // do this, and would ask a different question than the tap does - MapLibre's
  // delegated listeners query the exact point, with none of the slop above. A
  // cursor that turns into a pointer over a slightly different area than the
  // one that actually opens the sheet is worse than no cursor change at all.
  const onMouseMove = (event: MapMouseEvent) => {
    const { warning, poi, closure } = hits(event.point)
    map.getCanvas().style.cursor =
      warning === null && poi === null && closure === null ? '' : 'pointer'
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
