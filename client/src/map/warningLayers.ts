// Serious warnings on the map (WIREFRAMES.md §8, HIKER_SAFETY.md §1): the
// source, the one symbol layer, and the imperative pokes that fill them on a
// live map - the same shape poiLayers.ts gives the ordinary pins.
//
// Two decisions here are safety decisions rather than style:
//
// **The collision engine is switched OFF for this layer.** The ordinary pins
// let MapLibre thin them out by geometry, with POI_PRIORITY deciding who
// survives. A serious warning must never lose that contest - it is
// deliberately the biggest thing on the map, and a bear-activity warning
// hidden because a water pin got there first would be the map suppressing
// exactly what a moderator escalated it to say.
//
// **No minzoom.** The ordinary pins vanish below POI_MIN_ZOOM because eight
// hundred of them at the corridor view is a texture, not information. There
// are never eight hundred serious warnings - moderators escalate a handful -
// and someone planning tomorrow's miles from the zoomed-out view is exactly
// who a warning is for.
//
// Nothing in here pushes, and nothing may: lib/push.ts is the one publisher
// and push.test.ts scans this tree to keep it so.

import type {
  GeoJSONSourceSpecification,
  LayerSpecification,
} from '@maplibre/maplibre-gl-style-spec'
import type { GeoJSONSource, Map as MapLibreMap } from 'maplibre-gl'
import { WARNING_PIN } from '../lib/seriousWarnings'
import { buildAlertPinIcon, POI_PIN_PIXEL_RATIO } from './poiIcons'
import { whenStyleReady } from './styleReady'

export const WARNING_SOURCE_ID = 'serious-warnings'
export const WARNING_LAYER_ID = 'serious-warning-pins'
export const WARNING_ICON_ID = 'serious-warning-pin'

/** Where a pin carries its report id - a property, not the feature id, for
 *  the same parseInt reason poiLayers.ts documents. */
export const WARNING_ID_PROPERTY = 'report_id'

/** What the map needs to place one warning: the report id to find the rest
 *  by, and where it is. */
export interface WarningPoint {
  id: string
  lon: number
  lat: number
}

export function buildWarningSource(): GeoJSONSourceSpecification {
  return { type: 'geojson', data: { type: 'FeatureCollection', features: [] } }
}

export function buildWarningLayer(
  sourceId: string = WARNING_SOURCE_ID,
): LayerSpecification {
  return {
    id: WARNING_LAYER_ID,
    type: 'symbol',
    source: sourceId,
    layout: {
      'icon-image': WARNING_ICON_ID,
      // Always placed - see the module header. `ignore-placement` is the
      // other half: a warning must not shoulder ordinary pins out of the
      // collision engine's placement either, or a warning would erase the
      // water source beside it.
      'icon-allow-overlap': true,
      'icon-ignore-placement': true,
    },
  }
}

export interface WarningFeatureCollection {
  type: 'FeatureCollection'
  features: Array<{
    type: 'Feature'
    id: string
    geometry: { type: 'Point'; coordinates: [number, number] }
    properties: { [WARNING_ID_PROPERTY]: string }
  }>
}

export function warningFeatureCollection(
  warnings: readonly WarningPoint[],
): WarningFeatureCollection {
  return {
    type: 'FeatureCollection',
    features: warnings.map((warning) => ({
      type: 'Feature',
      id: warning.id,
      geometry: { type: 'Point', coordinates: [warning.lon, warning.lat] },
      properties: { [WARNING_ID_PROPERTY]: warning.id },
    })),
  }
}

/** Registers the warning pin image on a live map, and returns a detach. */
export function attachWarningIcon(map: MapLibreMap): () => void {
  return whenStyleReady(
    map,
    () => map.getLayer(WARNING_LAYER_ID) !== undefined,
    () => {
      if (!map.hasImage(WARNING_ICON_ID)) {
        map.addImage(
          WARNING_ICON_ID,
          buildAlertPinIcon(WARNING_PIN.sizePx, WARNING_PIN.color),
          { pixelRatio: POI_PIN_PIXEL_RATIO },
        )
      }
    },
    'Serious-warning pin image',
  )
}

/** Pushes the warnings onto the live map's source, and returns a detach. */
export function attachWarningData(
  map: MapLibreMap,
  warnings: readonly WarningPoint[],
): () => void {
  return whenStyleReady(
    map,
    () => map.getSource(WARNING_SOURCE_ID) !== undefined,
    () => {
      const source = map.getSource<GeoJSONSource>(WARNING_SOURCE_ID)
      if (source === undefined || typeof source.setData !== 'function') return

      source.setData(warningFeatureCollection(warnings) as never)
    },
    'Serious-warning data',
  )
}
