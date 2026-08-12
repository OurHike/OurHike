// How many waypoints the map is actually DRAWING, as against how many are in
// the viewport (#528).
//
// Both numbers already existed and had never been compared. `computeLegendContents`
// counts what is present - every waypoint inside the viewport rectangle. This
// counts what survived placement, and the gap between them is what the legend has
// been quietly not saying since collision culling arrived.
//
// The gap is not small. `icon-allow-overlap: false` means MapLibre draws no two
// colliding pins - it drops the one that loses POI_PRIORITY - and simulating that
// over the whole corridor (features/POI_SITES.md) puts a z9 viewport at ~70-90
// waypoints present against room for about 26. Per category at z14 it is starker
// still: 95% of water drawn, 3% of privies. A hiker reading `Privy · 6` on a map
// with no privy pin has been told something false by omission.
//
// WHY `queryRenderedFeatures` AND NOT ARITHMETIC. Its documented behaviour is to
// exclude "symbol features that have been hidden due to text or icon collision" -
// checked against maplibre-gl 6.0.0's own `.d.ts` rather than assumed. So it
// answers for THIS phone, at THIS camera, with the hiker's own hidden types
// applied, which is a different and more useful number than any simulation: it is
// the one that makes hiding a category visibly buy something (#530).
//
// IT REFLECTS THE LAST RENDERED FRAME, so callers recompute on `idle` rather than
// `move` - see App.tsx. A count that lags a fling by one frame is fine; a count
// recomputed mid-fling is a query per frame for a number nobody can read yet.

import type { Map as MapLibreMap } from 'maplibre-gl'
import { POI_ID_PROPERTY, POI_LAYER_ID } from './poiLayers'

/** The real MapLibre map, as map/poiTaps.ts and map/poiLayers.ts also take it.
 *  A structural stand-in was tried and does not work: `queryRenderedFeatures`
 *  is overloaded, and a parameter typed loosely enough to describe it is one
 *  the real type cannot satisfy under `strictFunctionTypes`. Tests supply the
 *  suite's own MockMap, which is what every other map module's tests use. */
export type DrawnPoiMap = MapLibreMap

/**
 * Drawn waypoints per category, keyed exactly as `computeLegendContents` keys its
 * rows - by TYPE ALONE - so the two join without a translation step in between.
 *
 * Type alone rather than `type::confidence` because #580 folded the confidence
 * split out of the legend: a verified and an unverified spring are two springs
 * rather than two rows. Keying this the old way would have produced counts that
 * never matched a row, which reads as "0 shown" on a map drawing them all.
 *
 * Empty where the layer is not in the style yet - which is a real state on a
 * cold start, and reads correctly downstream as "not measured" rather than as
 * "nothing is drawn".
 */
export function drawnPoiCounts(map: DrawnPoiMap): Map<string, number> {
  const counts = new Map<string, number>()
  // Asked before querying, because a query for a layer the style does not hold
  // fires an error event rather than throwing - so skipping the check buys a
  // warning in the console and an answer that looks like zero.
  if (map.getLayer(POI_LAYER_ID) === undefined) return counts

  // No geometry argument: the whole viewport, which is the rectangle the legend
  // is counting against.
  const features = map.queryRenderedFeatures(undefined, { layers: [POI_LAYER_ID] })

  // One waypoint can come back more than once - MapLibre tiles even a GeoJSON
  // source internally, and a point near a tile boundary is returned per tile it
  // appears in. Counted naively, that reports MORE drawn than present, and a row
  // reading `Water · 14 · 17 shown` would discredit the whole feature.
  const seen = new Set<string>()

  for (const feature of features) {
    const properties = feature.properties ?? {}
    const type = properties.poi_type
    if (typeof type !== 'string' || type === '') continue

    const id = properties[POI_ID_PROPERTY]
    if (typeof id === 'string' && id !== '') {
      if (seen.has(id)) continue
      seen.add(id)
    }

    counts.set(type, (counts.get(type) ?? 0) + 1)
  }

  return counts
}
