// Decision 67's hazard areas on a live map (#1805): pushing the drawn areas
// onto the source map/hazardAreaLayers.ts declares, and the tap that opens an
// area's card. Loaded by MapView the first time there is an area to draw,
// so a phone whose trails cross none never parses it (features/LAUNCH_BUDGET.md
// §3).

import type {
  GeoJSONSource,
  Map as MapLibreMap,
  MapMouseEvent,
  PointLike,
} from 'maplibre-gl'
import {
  hazardFeatureCollection,
  HAZARD_ID_PROPERTY,
  type HazardArea,
} from '../lib/hazardAreas'
import { atcBandIdAt } from './atcUpdateLayers'
import { closureIdAt } from './closureLayers'
import {
  HAZARD_FILL_LAYER_ID,
  HAZARD_POINT_LAYER_ID,
  HAZARD_SOURCE_ID,
} from './hazardAreaLayers'
import { tappedLineAt } from './lineTaps'
import { poiPinAt } from './poiPinProbe'
import { whenStyleReady } from './styleReady'
import { warningIdAt } from './warningLayers'

/** Pushes the drawn areas onto the live map's source, and returns a detach. */
export function attachHazardData(
  map: MapLibreMap,
  areas: readonly HazardArea[],
): () => void {
  return whenStyleReady(
    map,
    () => map.getSource(HAZARD_SOURCE_ID) !== undefined,
    () => {
      const source = map.getSource<GeoJSONSource>(HAZARD_SOURCE_ID)
      if (source === undefined || typeof source.setData !== 'function') return
      source.setData(hazardFeatureCollection(areas) as never)
    },
    'hazard areas',
  )
}

/** The touch-target floor every map mark meets (atcUpdateLayers.ts). */
const HAZARD_TAP_SLOP_PX = 22

function hazardTapBox(point: { x: number; y: number }): [PointLike, PointLike] {
  return [
    [point.x - HAZARD_TAP_SLOP_PX, point.y - HAZARD_TAP_SLOP_PX],
    [point.x + HAZARD_TAP_SLOP_PX, point.y + HAZARD_TAP_SLOP_PX],
  ]
}

/** The hazard area under a point on the canvas, by notice id, or null. */
export function hazardIdAt(
  map: MapLibreMap,
  point: { x: number; y: number },
): string | null {
  const layers = [HAZARD_FILL_LAYER_ID, HAZARD_POINT_LAYER_ID].filter(
    (layer) => map.getLayer(layer) !== undefined,
  )
  if (layers.length === 0) return null
  const box: PointLike | [PointLike, PointLike] = layers.includes(HAZARD_POINT_LAYER_ID)
    ? hazardTapBox(point)
    : [point.x, point.y]
  const [feature] = map.queryRenderedFeatures(box, { layers })
  const id = feature?.properties?.[HAZARD_ID_PROPERTY]
  return typeof id === 'string' && id !== '' ? id : null
}

/**
 * Wires taps on the drawn areas to `onSelect`, and returns a detach.
 *
 * LAST IN LINE. An area is the largest thing on the map and the least
 * specific, so every mark drawn on it wins the touch first: a warning pin, a
 * waypoint pin, the closure tape, an ATC band, and above all the trail line
 * itself, whose card carries this area's advisory for the stretch inside it
 * (chrome/tappedLinePanel.tsx). Only a touch on the area and nothing else
 * opens the area's own card.
 */
export function attachHazardTaps(
  map: MapLibreMap,
  onSelect: (noticeId: string) => void,
): () => void {
  const onClick = (event: MapMouseEvent) => {
    if (warningIdAt(map, event.point) !== null) return
    if (poiPinAt(map, event.point) !== undefined) return
    if (closureIdAt(map, event.point) !== null) return
    if (atcBandIdAt(map, event.point) !== null) return
    if (tappedLineAt(map, event.point) !== null) return
    const id = hazardIdAt(map, event.point)
    if (id !== null) onSelect(id)
  }
  map.on('click', onClick)
  return () => {
    map.off('click', onClick)
  }
}
