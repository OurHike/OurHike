// Putting closures on the map: the source, and the one imperative poke the
// shell makes at a live map.
//
// The same split poiLayers.ts makes against poiIcons.ts, one step further
// along: lib/closureStyle.ts is the drawing spec and knows nothing about
// MapLibre, lib/trailPosition.ts turns mile markers into coordinates and knows
// nothing about either, and this is the module that knows about MapLibre.
//
// A closure is a LINE, not a pin, so unlike the POIs it has no image to
// register and no collision engine to answer to. What it does have is a
// geometry problem the POIs do not: a report says "mile 1,408.2 to 1,408.6"
// and the map needs coordinates, which only the centerline index can supply.
// That is `trailSlice`, and its MultiLineString result is why the features
// below are multi-part rather than a single line each.

import type { GeoJSONSourceSpecification } from '@maplibre/maplibre-gl-style-spec'
import type { GeoJSONSource, Map as MapLibreMap } from 'maplibre-gl'
import type { Closure } from '../lib/closureBanner'
import { isBroadAdvisory } from '../lib/closureSpan'
import { trailSlice, type TrailIndex } from '../lib/trailPosition'
import { whenStyleReady } from './styleReady'

export const CLOSURE_SOURCE_ID = 'closures'

/**
 * Where a band carries its closure id.
 *
 * A property rather than the GeoJSON feature id, for exactly the reason
 * {@link import('./poiLayers').POI_ID_PROPERTY} gives: MapLibre runs a string
 * feature id through `parseInt`, and a closure id is a UUID. Nothing reads it
 * today - the tap that would (#245) is waiting on a sheet that can be filled
 * honestly - and it rides along because a band nobody can identify is a band
 * nobody can ever wire a tap to.
 */
export const CLOSURE_ID_PROPERTY = 'closure_id'

/** A closure reduced to what the canvas needs: an id, and where to draw. */
export interface ClosureBand {
  id: string
  /** One entry per centerline piece the closure spans - see `trailSlice`. */
  lines: Array<Array<[number, number]>>
}

export interface ClosureFeatureCollection {
  type: 'FeatureCollection'
  features: Array<{
    type: 'Feature'
    id: string
    geometry: { type: 'MultiLineString'; coordinates: Array<Array<[number, number]>> }
    properties: { [CLOSURE_ID_PROPERTY]: string }
  }>
}

/**
 * The closures that can actually be drawn, in map coordinates.
 *
 * Three closures are dropped here, and the differences between them matter:
 *
 *  - `status: 'open'` is a REOPENED closure, and drawing a barrier across a
 *    trail somebody has just reopened is the same class of false statement as
 *    not drawing one that is shut. lib/closureBanner.ts makes the identical
 *    call on the identical field, deliberately - the band and the banner must
 *    not disagree about what is closed.
 *  - A closure too long to be a band (lib/closureSpan.ts). A 398-mile advisory
 *    drawn along the centerline paints a fifth of the trail as closed and
 *    buries the nine-mile closure a hiker has to walk around. Unlike the other
 *    two this is a DECISION rather than a limit, and #462 is where the number
 *    it turns on gets settled.
 *  - A range the centerline index cannot place yields no coordinates. That is
 *    a gap in what this build knows, not a decision.
 *
 * All three are safe to drop here for the same reason: the BANNER is the
 * load-bearing warning and needs only a mile number, so a closure this function
 * declines to draw is still one a hiker is told about.
 */
export function closureBands(
  closures: readonly Closure[],
  index: TrailIndex,
): ClosureBand[] {
  return closures.flatMap((closure) => {
    if (closure.status === 'open') return []
    if (isBroadAdvisory(closure)) return []

    const lines = trailSlice(index, closure.start_mile_marker, closure.end_mile_marker)
    if (lines.length === 0) return []

    return [{ id: closure.id, lines }]
  })
}

export function closureFeatureCollection(
  bands: readonly ClosureBand[],
): ClosureFeatureCollection {
  return {
    type: 'FeatureCollection',
    features: bands.map((band) => ({
      type: 'Feature',
      id: band.id,
      geometry: { type: 'MultiLineString', coordinates: band.lines },
      properties: { [CLOSURE_ID_PROPERTY]: band.id },
    })),
  }
}

/**
 * The closure source, empty.
 *
 * Empty for the same reason the POI source is: closures arrive from the
 * network well after the map is built, and re-reading a style to add them
 * would drop the WebGL context underneath the hiker.
 */
export function buildClosureSource(): GeoJSONSourceSpecification {
  return { type: 'geojson', data: { type: 'FeatureCollection', features: [] } }
}

/** Pushes closure bands onto the live map's source, and returns a detach. */
export function attachClosureData(
  map: MapLibreMap,
  bands: readonly ClosureBand[],
): () => void {
  return whenStyleReady(
    map,
    () => map.getSource(CLOSURE_SOURCE_ID) !== undefined,
    () => {
      // `getSource` answers with the union of every source kind, and only the
      // GeoJSON one can be handed new data - same guard as attachPoiData.
      const source = map.getSource<GeoJSONSource>(CLOSURE_SOURCE_ID)
      if (source === undefined || typeof source.setData !== 'function') return

      source.setData(closureFeatureCollection(bands) as never)
    },
    'closure bands',
  )
}
