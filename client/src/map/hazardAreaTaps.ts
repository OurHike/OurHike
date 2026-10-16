// The hazard areas on a live map (#1805): pushing the drawn areas
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
import { hazardFeatureCollection, type HazardArea } from '../lib/hazardAreas'
import { atcBandIdAt } from './atcUpdateLayers'
import { closureIdAt, clubClosureIdAt } from './closureLayers'
import { clubClosureShadeIdAt } from './clubClosureLayers'
import {
  HAZARD_FILL_LAYER_ID,
  HAZARD_ID_PROPERTY,
  HAZARD_POINT_LAYER_ID,
  HAZARD_SOURCE_ID,
  hazardPointIdAt,
  hazardTapBox,
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
 * waypoint pin, the closure tape, a club's closure, an ATC band, and above
 * all the trail line
 * itself, whose card carries this area's advisory for the stretch inside it
 * (chrome/tappedLinePanel.tsx). Only a touch on the area and nothing else
 * opens the area's own card - nothing else but a club's shaded closure,
 * the other area last in line, which wins where the two
 * overlap: a closure outranks an advisory on the same ground
 * (map/clubClosureTaps.ts).
 *
 * A SHOOTING SITE'S DOT IS A MARK, NOT AN AREA: it waits for the same marks
 * above it - the two pins, the tape, a club's closure, an ATC band and the
 * trail line - and then wins over both kinds of area it can sit in, the
 * shaded closure included (map/hazardAreaLayers.ts's `hazardPointIdAt`,
 * which the shade's tap asks too).
 */
export function attachHazardTaps(
  map: MapLibreMap,
  onSelect: (noticeId: string) => void,
): () => void {
  const onClick = (event: MapMouseEvent) => {
    if (warningIdAt(map, event.point) !== null) return
    if (poiPinAt(map, event.point) !== undefined) return
    if (closureIdAt(map, event.point) !== null) return
    if (clubClosureIdAt(map, event.point) !== null) return
    if (atcBandIdAt(map, event.point) !== null) return
    if (tappedLineAt(map, event.point) !== null) return
    const site = hazardPointIdAt(map, event.point)
    if (site !== null) {
      onSelect(site)
      return
    }
    if (clubClosureShadeIdAt(map, event.point) !== null) return
    const id = hazardIdAt(map, event.point)
    if (id !== null) onSelect(id)
  }
  map.on('click', onClick)
  return () => {
    map.off('click', onClick)
  }
}
