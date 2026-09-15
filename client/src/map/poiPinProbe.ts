// Is there a waypoint PIN under this touch? — the one question two tap
// interpreters both have to ask, in one place so they cannot answer it
// differently (#1419).
//
// WHY THIS IS ITS OWN FILE. map/poiTaps.ts owns "which POI did that touch
// land on" and already imports map/closureLayers.ts to yield to the tape, so
// closureLayers cannot import poiTaps back. But once the tape yields to a
// waypoint pin as well — the maintainer's call, 2026-09-14 — closureLayers
// needs exactly this question, and the alternatives were both worse:
//
//   - duplicating POI_TAP_SLOP_PX into closureLayers, which poiTaps.ts argues
//     against at the constant itself ("written down as a number it would be a
//     second thing to remember the day POI_PIN_SIZE moves, which is the
//     mistake lib/seriousWarnings.ts already made once with the same
//     constant"); or
//   - having one module decide for both, which is what the yield being
//     asymmetric caused in the first place.
//
// So the slop, the box and the probe live in a leaf both import, and
// poiTaps.ts re-exports the first two so every existing caller and
// poiTaps.test.ts keep working unchanged.
//
// THE PIN RANK ONLY, deliberately. A waypoint drawn as a DOT is not asked
// about here and keeps yielding to the tape, because the argument that moved
// the pin does not reach it: POI_DOT_TAP_SLOP_PX is about 20 px against the
// tape's 22, so both are ambient and there is no "narrow beats wide" case to
// make. See poiTaps.ts's rule and #1419's closing note.

import type { Map as MapLibreMap, MapGeoJSONFeature, PointLike } from 'maplibre-gl'
import { POI_PIN_SIZE } from './poiIcons'
import { POI_ID_PROPERTY, POI_LAYER_ID } from './poiLayers'

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

/**
 * The waypoint pin under `point` that a card could actually be opened for,
 * or undefined for none.
 *
 * THE ID IS PART OF "IS THERE A PIN", not a separate question, and an
 * earlier cut of this had it as one. `poiTaps.ts` resolves a touch to
 * `idOf(pin)`, which is null when the feature carries no usable
 * POI_ID_PROPERTY; `closureLayers.ts` yielded on the FEATURE being present.
 * Those two predicates disagree for exactly one population - a published pin
 * whose id did not survive - and where they disagree the touch does nothing
 * at all: the tape yields to a pin that then opens no card, and lineTaps.ts
 * still yields to the tape, so a hiker gets silence where before #1419 they
 * got the closure sheet. So the probe answers the question the yield is
 * actually asking, and a pin that cannot be opened is not one.
 *
 * The FEATURE rather than the id, because poiTaps.ts reads other properties
 * off it; that it has a usable id is guaranteed by the time it is returned.
 *
 * Guarded on the layer existing, for poiTaps.ts's reason: before the style
 * has parsed, querying a layer it does not hold fires an error event rather
 * than throwing, and a touch on a map with no pins on it yet should be
 * silent rather than a warning in the console.
 *
 * The collision engine (`icon-allow-overlap: false`) means two pins this
 * close are adjacent rather than stacked, so taking the first is rarely even
 * a choice — which is why the pin box, unlike the dot box, does not need a
 * nearest-wins rule.
 */
export function poiPinAt(
  map: MapLibreMap,
  point: { x: number; y: number },
): MapGeoJSONFeature | undefined {
  if (map.getLayer(POI_LAYER_ID) === undefined) return undefined
  const [pin] = map.queryRenderedFeatures(poiTapBox(point), { layers: [POI_LAYER_ID] })
  if (pin === undefined) return undefined
  const id = pin.properties?.[POI_ID_PROPERTY]
  return typeof id === 'string' && id !== '' ? pin : undefined
}
