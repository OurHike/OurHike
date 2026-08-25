// What the map is drawing on its trail-line layer, for the legend (#782, #783).
//
// This module counted blazes per colour as well, for the legend's blaze rows.
// Those rows were removed at the maintainer's request on 2026-08-25 ("the
// legend doesn't need the color of the blaze included... it's too cluttered"),
// and `drawnBlazeCounts` went with them rather than staying as a measurement
// nothing reads — chrome/Legend.tsx's header carries the decision and what it
// costs. `drawsNearbyTrails` is what is left, and its sentence is now the only
// thing this panel says about the lines.
//
// SHAPED ON map/drawnPois.ts DELIBERATELY, including its trap:
// `queryRenderedFeatures` reflects the LAST RENDERED FRAME, so callers
// recompute on `idle` rather than on `move`.
//
// The other trap that module documents — a GeoJSON source is tiled internally,
// so one trail crossing a tile boundary comes back once per tile — cost the
// blaze counts a de-duplication pass by feature id. It costs the survivor
// nothing: `drawsNearbyTrails` stops at the first match, and one nearby trail
// counted twice is still one nearby trail. That is why the de-duplication left
// with the counting rather than being kept "just in case".

import type { Map as MapLibreMap } from 'maplibre-gl'
import { BLAZE_LAYER_ID } from './style'
import { isNearbyTrail } from './nearbyTrails'

/** The real MapLibre map — see map/drawnPois.ts for why not a structural
 *  stand-in. */
export type DrawnBlazeMap = MapLibreMap

/** The pipeline's own source key, published on every trail feature by
 *  export_trails.py - what width, sort order and ghosting all key off. */
export const TRAIL_SOURCE_PROPERTY = 'source'

/**
 * Whether the map is currently drawing any trail that is not the chosen
 * system's (#783, features/NEARBY_TRAILS.md §1).
 *
 * The legend's ghosting sentence is the only caller, and it is why this
 * returns a boolean rather than a count: the sentence explains a state
 * ("other trails are dimmed"), it does not report a quantity, and a number
 * nobody renders is a number that goes wrong unnoticed.
 *
 * Asked of the last rendered frame, with that trap handled the way this
 * module's header describes. It does NOT de-duplicate by feature id, because
 * it stops at the first nearby trail it finds: one is as true as forty for the
 * sentence this answers.
 *
 * False where the layer is not in the style yet, which is the honest answer on
 * a cold start: the legend says nothing about ghosting rather than explaining
 * a state the map has not drawn.
 */
export function drawsNearbyTrails(map: DrawnBlazeMap): boolean {
  if (map.getLayer(BLAZE_LAYER_ID) === undefined) return false

  const features = map.queryRenderedFeatures(undefined, { layers: [BLAZE_LAYER_ID] })
  return features.some((feature) =>
    isNearbyTrail((feature.properties ?? {})[TRAIL_SOURCE_PROPERTY] as string | null),
  )
}
