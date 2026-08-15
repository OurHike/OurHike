// Putting the drought bands on the map: the source, and the two imperative
// pokes the shell makes at a live map (#720).
//
// The same split closureLayers.ts makes against lib/closureStyle.ts:
// lib/droughtStyle.ts is the drawing spec and knows nothing about MapLibre,
// and this is the module that knows about MapLibre.
//
// Simpler than the closures in one way and harder in another. Simpler because
// the pipeline ships real polygons - there is no mile marker to turn into
// coordinates, so `lib/trailPosition.ts` is not involved and the features go
// on the source exactly as published. Harder because this layer has a switch,
// and a switch has to be instant: `setDroughtVisible` sets `visibility` on a
// layer that is always present rather than adding and removing it, so flipping
// it costs no source re-parse and no flicker.

import type { GeoJSONSourceSpecification } from '@maplibre/maplibre-gl-style-spec'
import type { GeoJSONSource, Map as MapLibreMap } from 'maplibre-gl'
import { DROUGHT_LAYER_ID } from '../lib/droughtStyle'
import { whenStyleReady } from './styleReady'

export const DROUGHT_SOURCE_ID = 'drought'

/**
 * One published band: a class, its label, the trail miles at that class, and
 * where it is.
 *
 * `trailMiles` is the mileage at EXACTLY this class rather than "this class
 * or worse" - NDMC's polygons are mutually exclusive, measured, and
 * pipeline/export_drought.py refuses to publish a release where they are not.
 * The distinction is worth carrying into the type name's neighbourhood
 * because reading it the other way overstated the trail under drought by 511
 * miles the first time round.
 */
export interface DroughtBand {
  dm: number
  label: string
  trailMiles: number
  geometry: unknown
}

export interface DroughtFeatureCollection {
  type: 'FeatureCollection'
  features: Array<{
    type: 'Feature'
    geometry: unknown
    properties: { dm: number; label: string; trail_miles: number }
  }>
}

export function droughtFeatureCollection(
  bands: readonly DroughtBand[],
): DroughtFeatureCollection {
  return {
    type: 'FeatureCollection',
    features: bands.map((band) => ({
      type: 'Feature',
      geometry: band.geometry,
      properties: { dm: band.dm, label: band.label, trail_miles: band.trailMiles },
    })),
  }
}

/** An empty source, filled once the artifact lands - same shape and same
 *  reason as `buildClosureSource`: a style that names a source it does not
 *  have would drop the WebGL context underneath the hiker. */
export function buildDroughtSource(): GeoJSONSourceSpecification {
  return { type: 'geojson', data: { type: 'FeatureCollection', features: [] } }
}

/** Pushes the bands onto the live map's source, and returns a detach. */
export function attachDroughtData(
  map: MapLibreMap,
  bands: readonly DroughtBand[],
): () => void {
  return whenStyleReady(
    map,
    () => map.getSource(DROUGHT_SOURCE_ID) !== undefined,
    () => {
      // `getSource` answers with the union of every source kind, and only the
      // GeoJSON one can be handed new data - same guard as attachClosureData.
      const source = map.getSource<GeoJSONSource>(DROUGHT_SOURCE_ID)
      if (source === undefined || typeof source.setData !== 'function') return

      source.setData(droughtFeatureCollection(bands) as never)
    },
    'drought bands',
  )
}

/** Shows or hides the band layer, and returns a detach.
 *
 *  Separate from `attachDroughtData` because the two carry different rhythms:
 *  the data arrives once when the app comes online, and the switch moves
 *  whenever a hiker taps it. Folding them together would re-push 14 KB of
 *  polygons on every tap. */
export function setDroughtVisible(map: MapLibreMap, visible: boolean): () => void {
  return whenStyleReady(
    map,
    () => map.getLayer(DROUGHT_LAYER_ID) !== undefined,
    () => {
      map.setLayoutProperty(DROUGHT_LAYER_ID, 'visibility', visible ? 'visible' : 'none')
    },
    'drought visibility',
  )
}
