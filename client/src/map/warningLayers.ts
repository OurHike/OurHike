// Putting serious warnings on the map: the source, the one symbol layer that
// draws them, and the two imperative pokes the shell makes at a live map.
//
// The same shape as poiLayers.ts, with two deliberate differences.
//
//  1. THE PINS' OWN MINZOOM, since 2026-09-08 (#1292). This layer had none:
//     serious warnings are moderator-escalated and rare - a handful on 2,197
//     miles - and the argument was that zoomed out to plan a week is exactly
//     when someone wants to see where they are. The maintainer's call that
//     the opening camera shows trail lines only reverses that, and the honest
//     half of the old argument survives it: below the seam a 44 px pin covers
//     on the order of a hundred trail miles, so it said "somewhere here" and
//     nothing a hiker could act on. From the seam up it draws exactly as
//     before, and the route banner (lib/seriousWarnings.ts) still counts
//     warnings at every zoom. Written out at this length because it sits on
//     HIKER_SAFETY.md's "in front of something dangerous" path, where a mark
//     withdrawn has to say so.
//  2. `icon-allow-overlap: true`. Every other symbol on this map submits to
//     the collision engine. This one must not: a warning dropped because a
//     shelter pin got there first is a warning nobody was shown, and the
//     hiker cannot tell that from there being none. It still takes part in
//     placement for everything else (`icon-ignore-placement` stays false), so
//     it pushes waypoints aside rather than being pushed.
//
// NOTHING HERE PUSHES, and that is a rule rather than an omission.
// OurHike sends no push notifications at all, and warningLayers.test.ts
// scans this file's own source to keep it that way, so the module that
// finally mounts the warning path does not become the exception.
// HIKER_SAFETY.md §1 is where the reasoning lives: a warning about a named
// person arriving as a phone notification is a different and much worse
// thing than the same words on a map a hiker chose to open.

import type {
  GeoJSONSourceSpecification,
  LayerSpecification,
} from '@maplibre/maplibre-gl-style-spec'
import type {
  GeoJSONSource,
  Map as MapLibreMap,
  MapMouseEvent,
  PointLike,
} from 'maplibre-gl'
import { POI_PIN_PIXEL_RATIO } from './poiIcons'
import { POI_PIN_MIN_ZOOM } from './poiLayers'
import { buildWarningIcon, WARNING_ICON_ID } from './warningPin'
import { whenStyleReady } from './styleReady'

export const WARNING_SOURCE_ID = 'serious-warnings'
export const WARNING_LAYER_ID = 'serious-warning-pins'

/** Where a pin carries its report id - a property rather than the feature id,
 *  for the reason poiLayers.ts's POI_ID_PROPERTY gives. Nothing reads it yet;
 *  the tap that would opens a sheet nothing can honestly fill (#292). */
export const WARNING_ID_PROPERTY = 'report_id'

/** A serious warning reduced to what the canvas needs. */
export interface WarningPoint {
  id: string
  lon: number
  lat: number
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
    minzoom: POI_PIN_MIN_ZOOM,
    layout: {
      'icon-image': WARNING_ICON_ID,
      // One size at every zoom, unlike the waypoints, which interpolate down
      // to 0.6 as they approach their minzoom. A warning drawn small is a
      // warning that has stopped outranking the pins around it, and the size
      // ceiling in lib/seriousWarnings.ts is the whole point of this pin.
      'icon-size': 1,
      'icon-allow-overlap': true,
      'icon-padding': 2,
    },
  }
}

/** Registers the warning pin image on a live map, and returns a detach. */
/** The pin's own hit box: the pin is 44px on the map (lib/seriousWarnings.ts's
 *  size ceiling) and is hit like every other 44px control. */
const WARNING_TAP_SLOP_PX = 22

export function warningTapBox(point: { x: number; y: number }): [PointLike, PointLike] {
  return [
    [point.x - WARNING_TAP_SLOP_PX, point.y - WARNING_TAP_SLOP_PX],
    [point.x + WARNING_TAP_SLOP_PX, point.y + WARNING_TAP_SLOP_PX],
  ]
}

/**
 * Which warning's pin a touch landed on, or null (#1373, F12 - "the tap
 * that would (#292) opens a sheet nothing can honestly fill" was true until
 * #292 emptied the sheet of what nothing could fill; what is left is what
 * the wire carries, and the tap can open it now).
 */
export function warningIdAt(
  map: MapLibreMap,
  point: { x: number; y: number },
): string | null {
  if (map.getLayer(WARNING_LAYER_ID) === undefined) return null
  const [feature] = map.queryRenderedFeatures(warningTapBox(point), {
    layers: [WARNING_LAYER_ID],
  })
  if (feature === undefined) return null
  const id = feature.properties?.[WARNING_ID_PROPERTY]
  return typeof id === 'string' && id !== '' ? id : null
}

/** Wires taps on the warning pins to `onSelect`; hits only, like the
 *  closure tape's. The POI and line handlers yield to this pin, so one
 *  touch has one interpreter. */
export function attachWarningTaps(
  map: MapLibreMap,
  onSelect: (reportId: string) => void,
): () => void {
  const onClick = (event: MapMouseEvent) => {
    const id = warningIdAt(map, event.point)
    if (id !== null) onSelect(id)
  }
  map.on('click', onClick)
  return () => {
    map.off('click', onClick)
  }
}

export function attachWarningIcon(map: MapLibreMap): () => void {
  return whenStyleReady(
    map,
    // The layer existing proves the style spec is parsed, which is the
    // condition addImage actually requires - same question attachPoiIcons asks.
    () => map.getLayer(WARNING_LAYER_ID) !== undefined,
    () => {
      // Images outlive a style reload, and re-adding one throws.
      if (!map.hasImage(WARNING_ICON_ID)) {
        map.addImage(WARNING_ICON_ID, buildWarningIcon(), {
          pixelRatio: POI_PIN_PIXEL_RATIO,
        })
      }
    },
    'serious-warning pin image',
  )
}

/** Pushes serious warnings onto the live map's source, and returns a detach. */
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
    'serious warnings',
  )
}
