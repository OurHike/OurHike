// Every club closure on a live map (the maintainer's S6, 2026-10-11): pushing
// the closures onto the source map/clubClosureLayers.ts declares, and the tap
// that opens a closure's sheet. Loaded by MapView the first time there is a
// closure to draw, as map/hazardAreaTaps.ts is for the hazard areas, so the
// launch parses none of it (features/LAUNCH_BUDGET.md §3).

import type { GeoJSONSource, Map as MapLibreMap, MapMouseEvent } from 'maplibre-gl'
import type { TrailClosure } from '../lib/publishedConditions'
import { atcBandIdAt } from './atcUpdateLayers'
import { addClosureShadeImages } from './closureShade'
import {
  CLUB_CLOSURE_CHAIN_FROM_PROPERTY,
  CLUB_CLOSURE_SOURCE_ID,
  clubClosureChainFrom,
  clubClosureShadeIdAt,
} from './clubClosureLayers'
import { closureIdAt, clubClosureIdAt, CLUB_CLOSURE_ID_PROPERTY } from './closureLayers'
import { tappedLineAt } from './lineTaps'
import { poiPinAt } from './poiPinProbe'
import { poiIdAt } from './poiTaps'
import { whenStyleReady } from './styleReady'
import { warningIdAt } from './warningLayers'

export interface ClubClosureFeatureCollection {
  type: 'FeatureCollection'
  features: Array<{
    type: 'Feature'
    geometry: TrailClosure['place']['geometry']
    properties: {
      [CLUB_CLOSURE_ID_PROPERTY]: string
      [CLUB_CLOSURE_CHAIN_FROM_PROPERTY]?: number
    }
  }>
}

/**
 * The closures as GeoJSON, one feature per closure, each on its own geometry
 * and keyed by its notice id - a property rather than the feature id, for
 * map/closureLayers.ts's CLOSURE_ID_PROPERTY reason: MapLibre runs a string
 * feature id through `parseInt`. Which layer draws a feature is its geometry's
 * (map/clubClosureLayers.ts): a line or an area's cut stretches along the
 * crossed-out mark, a point as one cross, a shade's polygon as the hatch.
 * A line closure also carries the zoom its chain takes over from its far
 * mark (decision 198), worked out from its geometry alone.
 */
export function clubClosureFeatureCollection(
  closures: readonly TrailClosure[],
): ClubClosureFeatureCollection {
  return {
    type: 'FeatureCollection',
    features: closures.map((closure) => {
      const chainFrom = clubClosureChainFrom(closure.place.geometry)
      return {
        type: 'Feature',
        geometry: closure.place.geometry,
        properties: {
          [CLUB_CLOSURE_ID_PROPERTY]: closure.notice_id,
          ...(chainFrom === null
            ? {}
            : { [CLUB_CLOSURE_CHAIN_FROM_PROPERTY]: chainFrom }),
        },
      }
    }),
  }
}

/** Pushes the closures onto the live map's source, and returns a detach.
 *  The shade's hatch images go first (map/closureShade.ts), so no shaded
 *  area reaches the source before its pattern does. */
export function attachClubClosureData(
  map: MapLibreMap,
  closures: readonly TrailClosure[],
): () => void {
  return whenStyleReady(
    map,
    () => map.getSource(CLUB_CLOSURE_SOURCE_ID) !== undefined,
    () => {
      const source = map.getSource<GeoJSONSource>(CLUB_CLOSURE_SOURCE_ID)
      if (source === undefined || typeof source.setData !== 'function') return
      addClosureShadeImages(map)
      source.setData(clubClosureFeatureCollection(closures) as never)
    },
    'club closures',
  )
}

/**
 * Wires taps on a club closure to `onSelect`, by notice id, and returns a
 * detach.
 *
 * Hits only, like the tape's handler, in map/closureLayers.ts's ONE TOUCH,
 * ONE INTERPRETER order: the warning pin, then a waypoint pin, then the
 * tape of a hiker-reported closure, then this. Everything below - an ATC
 * band, a waypoint dot, a trail line, a hazard area - asks `clubClosureIdAt`
 * and yields, so a touch on a crossed-out stretch opens the closure's sheet
 * and not the trail's.
 *
 * A SHADED AREA IS LAST IN LINE (decision 191), as a hazard area is
 * (map/hazardAreaTaps.ts) and for its reason: an area is the largest thing
 * on the map and the least specific, so every mark drawn on it wins first,
 * the ATC band, a waypoint dot and a trail line included. Only a touch on
 * the hatch and nothing else opens the closure's sheet, the same sheet its
 * list row opens. Between the two areas the shade wins, and the hazard
 * area's handler yields to it: a closure outranks an advisory on the same
 * ground.
 */
export function attachClubClosureTaps(
  map: MapLibreMap,
  onSelect: (noticeId: string) => void,
): () => void {
  const onClick = (event: MapMouseEvent) => {
    if (warningIdAt(map, event.point) !== null) return
    if (poiPinAt(map, event.point) !== undefined) return
    if (closureIdAt(map, event.point) !== null) return
    const id = clubClosureIdAt(map, event.point)
    if (id !== null) {
      onSelect(id)
      return
    }
    if (atcBandIdAt(map, event.point) !== null) return
    if (poiIdAt(map, event.point) !== null) return
    if (tappedLineAt(map, event.point) !== null) return
    const shaded = clubClosureShadeIdAt(map, event.point)
    if (shaded !== null) onSelect(shaded)
  }
  map.on('click', onClick)
  return () => {
    map.off('click', onClick)
  }
}
