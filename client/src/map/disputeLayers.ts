// The dispute mark on the canvas (#876, features/FIELD_NOTES.md §4).
//
// workdayLayers.ts's shape, with three differences that all come from what a
// dispute IS:
//
//  1. **It never collides away.** `icon-allow-overlap` is on, like the
//     serious-warning pins and unlike everything else. §4's rule is that the
//     pin is never suppressed - "a POI that vanishes is indistinguishable
//     from one that never existed" - and a mark the collision engine drops
//     is a suppression the hiker cannot tell from an absence.
//  2. **It ignores placement too**, which the warning pins deliberately do
//     NOT. A warning should push a waypoint aside; this must not, because it
//     is drawn ON one. Pushing the pin it annotates out of the way would be
//     a footnote shoving its own sentence off the page.
//  3. **It is offset**, to the pin's upper right, so the waypoint's own
//     glyph stays readable underneath.
//
// Its own source rather than a property on the POI source, and that is the
// load-bearing decision here: the POI features' `confidence` is what the
// legend's "Verified?" toggle filters on, so a dispute expressed there would
// let a filter delete the pin §4 says must never be suppressed. See
// map/disputeMark.ts.

import type {
  GeoJSONSourceSpecification,
  LayerSpecification,
} from '@maplibre/maplibre-gl-style-spec'
import type { GeoJSONSource, Map as MapLibreMap } from 'maplibre-gl'
import { buildDisputeMark, DISPUTE_MARK_ID, DISPUTE_MARK_SIZE } from './disputeMark'
import { POI_PIN_SIZE } from './poiIcons'
import { whenStyleReady } from './styleReady'

export const DISPUTE_SOURCE_ID = 'poi-disputes'
export const DISPUTE_LAYER_ID = 'poi-dispute-marks'

/** Where a mark carries the id of the place it annotates - a property rather
 *  than a feature id, for poiLayers.ts's reason: MapLibre runs a string
 *  feature id through `parseInt`, and `atc_shelters:<guid>` is not a number. */
export const DISPUTE_ID_PROPERTY = 'poi_id'

/** A disputed place, reduced to what the canvas needs. The shell does the
 *  joining: the verdict comes from the server and the coordinates from the
 *  POI export, and neither knows about the other. */
export interface DisputePoint {
  poiId: string
  lon: number
  lat: number
}

export interface DisputeFeatureCollection {
  type: 'FeatureCollection'
  features: Array<{
    type: 'Feature'
    id: string
    geometry: { type: 'Point'; coordinates: [number, number] }
    properties: { [DISPUTE_ID_PROPERTY]: string }
  }>
}

export function disputeFeatureCollection(
  disputes: readonly DisputePoint[],
): DisputeFeatureCollection {
  return {
    type: 'FeatureCollection',
    features: disputes.map((dispute) => ({
      type: 'Feature',
      id: dispute.poiId,
      geometry: { type: 'Point', coordinates: [dispute.lon, dispute.lat] },
      properties: { [DISPUTE_ID_PROPERTY]: dispute.poiId },
    })),
  }
}

export function buildDisputeSource(): GeoJSONSourceSpecification {
  return { type: 'geojson', data: { type: 'FeatureCollection', features: [] } }
}

export function buildDisputeLayer(
  sourceId: string = DISPUTE_SOURCE_ID,
): LayerSpecification {
  return {
    id: DISPUTE_LAYER_ID,
    type: 'symbol',
    source: sourceId,
    layout: {
      'icon-image': DISPUTE_MARK_ID,
      'icon-size': 1,
      // Up and right of the pin's centre, in the icon's own pixels. A quarter
      // of the pin either way puts the mark on the shoulder of the disc
      // rather than over the glyph a hiker is trying to read.
      'icon-offset': [POI_PIN_SIZE / 4, -POI_PIN_SIZE / 4],
      // See the header: never dropped, and never pushes anything.
      'icon-allow-overlap': true,
      'icon-ignore-placement': true,
    },
  }
}

/** Registers the mark image on a live map, and returns a detach. */
export function attachDisputeIcon(map: MapLibreMap): () => void {
  return whenStyleReady(
    map,
    () => map.getLayer(DISPUTE_LAYER_ID) !== undefined,
    () => {
      if (!map.hasImage(DISPUTE_MARK_ID)) {
        map.addImage(DISPUTE_MARK_ID, buildDisputeMark(DISPUTE_MARK_SIZE), {
          pixelRatio: 2,
        })
      }
    },
    'dispute mark image',
  )
}

/** Pushes the disputed places onto the live map, and returns a detach.
 *
 *  An empty array is ordinary: it is what the shell passes when nothing is
 *  disputed AND when the disputes could not be read at all. Those are
 *  different claims, and the card is where they are told apart in words -
 *  a map cannot draw "we could not ask". */
export function attachDisputeData(
  map: MapLibreMap,
  disputes: readonly DisputePoint[],
): () => void {
  return whenStyleReady(
    map,
    () => map.getSource(DISPUTE_SOURCE_ID) !== undefined,
    () => {
      const source = map.getSource<GeoJSONSource>(DISPUTE_SOURCE_ID)
      if (source === undefined || typeof source.setData !== 'function') return

      source.setData(disputeFeatureCollection(disputes) as never)
    },
    'disputed waypoints',
  )
}
