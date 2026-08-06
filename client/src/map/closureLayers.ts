// Closures on the map (WIREFRAMES.md §7): turning a closure's mile range
// into geometry along the centerline, and pushing it onto the live map.
//
// A closure arrives from the backend as two mile markers, not as a line -
// the backend has no geometry at all (backend/app/models/closure.py). The
// centerline the phone already holds is what places it: lib/trailPosition.ts
// indexes every centerline vertex by its mile, so the band is the run of
// vertices between the two markers. That makes the drawn band exactly as
// accurate as the mile index itself, which is the same arithmetic that puts
// the hiker's own mile in the header - the band and the "you are here" agree
// about where a mile is, which is the agreement that matters.
//
// How it is DRAWN - widths, colour, the barred rhythm - is lib/closureStyle.ts
// and is not restated here.

import type { GeoJSONSourceSpecification } from '@maplibre/maplibre-gl-style-spec'
import type { GeoJSONSource, Map as MapLibreMap } from 'maplibre-gl'
import type { Closure } from '../lib/closureBanner'
import type { TrailIndex } from '../lib/trailPosition'
import { whenStyleReady } from './styleReady'

export const CLOSURE_SOURCE_ID = 'closures'

/** Where a band carries its closure id - a property, not the feature id, for
 *  the same parseInt reason poiLayers.ts documents. */
export const CLOSURE_ID_PROPERTY = 'closure_id'

export function buildClosureSource(): GeoJSONSourceSpecification {
  return { type: 'geojson', data: { type: 'FeatureCollection', features: [] } }
}

export interface ClosureFeatureCollection {
  type: 'FeatureCollection'
  features: Array<{
    type: 'Feature'
    geometry: { type: 'LineString'; coordinates: Array<[number, number]> }
    properties: { [CLOSURE_ID_PROPERTY]: string }
  }>
}

/**
 * The closures as drawable lines: for each closure still standing, the
 * centerline vertices between its mile markers.
 *
 * A closure whose `status` is 'open' draws nothing - the trail reopened, and
 * a barrier over walkable trail is the false alarm this feature's credibility
 * cannot afford. A reroute is still a closure: having somewhere else to walk
 * does not make the trail itself passable (lib/closureBanner.ts makes the
 * same call for the banner).
 *
 * The index's flat arrays are ordered along the trail, but consecutive
 * vertices are not always joined trail: where one surveyed piece ends and the
 * next begins, buildTrailIndex adds no distance, so the two vertices carry
 * the SAME mile. A band must split there rather than draw the straight jump
 * across the gap - that jump is not trail, and a red barrier across ground
 * the trail never touches is a claim about the wrong place.
 */
export function closureFeatureCollection(
  closures: readonly Closure[],
  index: TrailIndex | null,
): ClosureFeatureCollection {
  const features: ClosureFeatureCollection['features'] = []

  if (index !== null) {
    for (const closure of closures) {
      if (closure.status === 'open') continue

      const low = Math.min(closure.start_mile_marker, closure.end_mile_marker)
      const high = Math.max(closure.start_mile_marker, closure.end_mile_marker)

      let run: Array<[number, number]> = []
      const flush = () => {
        if (run.length >= 2) {
          features.push({
            type: 'Feature',
            geometry: { type: 'LineString', coordinates: run },
            properties: { [CLOSURE_ID_PROPERTY]: closure.id },
          })
        }
        run = []
      }

      for (let i = 0; i < index.miles.length; i += 1) {
        const mile = index.miles[i]
        if (mile < low) continue
        if (mile > high) break

        // A vertex adding no distance over its predecessor is the seam
        // between two surveyed pieces - see above.
        if (i > 0 && mile === index.miles[i - 1]) flush()
        run.push([index.lons[i], index.lats[i]])
      }
      flush()
    }
  }

  return { type: 'FeatureCollection', features }
}

/** Pushes the closure bands onto the live map's source, and returns a detach. */
export function attachClosureData(
  map: MapLibreMap,
  closures: readonly Closure[],
  index: TrailIndex | null,
): () => void {
  return whenStyleReady(
    map,
    () => map.getSource(CLOSURE_SOURCE_ID) !== undefined,
    () => {
      const source = map.getSource<GeoJSONSource>(CLOSURE_SOURCE_ID)
      if (source === undefined || typeof source.setData !== 'function') return

      source.setData(closureFeatureCollection(closures, index) as never)
    },
    'Closure data',
  )
}
