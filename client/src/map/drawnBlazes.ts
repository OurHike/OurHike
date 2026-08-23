// Which blazes the map is actually drawing, for the legend's blaze rows (#782).
//
// The Legend has had a blaze list since it was built and has never rendered
// one, because nothing computed the counts — `App.tsx`'s `NO_BLAZE_COUNTS`,
// named as staged-not-shipped by #657. This is the missing half.
//
// WHAT #657 GOT WRONG, RECORDED BECAUSE THE COMMENT SAID OTHERWISE
//
// That constant's docstring said the counts "need the reviewed colour mapping
// #782 is deciding — so this waits on that". Checked while building #782 and
// it is not true: a trail feature already carries `blaze_color` on every
// source shipping today, and counting what MapLibre drew reads that property
// off the rendered features. The mapping table decides what a NEW source's
// raw value normalizes to; it has nothing to say about counting a normalized
// one. The list was waiting on nothing. Fixed here rather than left, since
// the two issues landed close enough together for the stale claim to survive
// unread otherwise.
//
// SHAPED ON map/drawnPois.ts DELIBERATELY, including its two traps:
//
//   - `queryRenderedFeatures` reflects the LAST RENDERED FRAME, so callers
//     recompute on `idle` rather than on `move`;
//   - a GeoJSON source is tiled internally, so one trail crossing a tile
//     boundary comes back once per tile. Counting features would report more
//     blazes than there are trails. This counts DISTINCT trails, by feature
//     id, for the same reason `drawnPoiCounts` de-duplicates by POI id.
//
// One difference from that module, and it is the interesting one: a waypoint
// is a point and a trail is a line, so a single trail can be drawn across
// many tiles rather than incidentally in two. De-duplication is load-bearing
// here rather than defensive.

import type { Map as MapLibreMap } from 'maplibre-gl'
import { BLAZE_LAYER_ID } from './style'
import { isNearbyTrail } from './nearbyTrails'

/** The real MapLibre map — see map/drawnPois.ts for why not a structural
 *  stand-in. */
export type DrawnBlazeMap = MapLibreMap

/** The property `lib/blaze.py` normalizes every trail-line source into. */
export const BLAZE_COLOR_PROPERTY = 'blaze_color'

/** The pipeline's own source key, published on every trail feature by
 *  export_trails.py - what width, sort order and ghosting all key off. */
export const TRAIL_SOURCE_PROPERTY = 'source'

/**
 * How many distinct trails of each blaze the map is drawing right now.
 *
 * Keyed by the normalized `blaze_color` string, which is exactly what
 * `blazePaintColor` takes — so the legend joins these to paints with no
 * translation step, and a palette member admitted under #782's rule appears
 * the moment a trail wearing it is drawn. That is the "picks up new members
 * automatically" the issue makes a completion condition.
 *
 * Empty where the layer is not in the style yet, which is a real state on a
 * cold start and reads correctly downstream as "nothing to say" rather than
 * as "no blazes here".
 */
export function drawnBlazeCounts(map: DrawnBlazeMap): Map<string, number> {
  const counts = new Map<string, number>()
  // Asked before querying: a query for a layer the style does not hold fires
  // an error event rather than throwing, so skipping this buys a console
  // warning and an answer that looks like zero.
  if (map.getLayer(BLAZE_LAYER_ID) === undefined) return counts

  const features = map.queryRenderedFeatures(undefined, { layers: [BLAZE_LAYER_ID] })
  const seen = new Set<string>()

  for (const feature of features) {
    const blaze = (feature.properties ?? {})[BLAZE_COLOR_PROPERTY]
    if (typeof blaze !== 'string' || blaze === '') continue

    // `id` is MapLibre's own feature id, stable across the tiles one line is
    // split over. A feature without one is counted rather than dropped: an
    // over-count is a wrong number, and dropping the trail entirely is a
    // missing row, which is the worse of the two on a legend.
    const id = feature.id
    if (id !== undefined && id !== null) {
      const key = String(id)
      if (seen.has(key)) continue
      seen.add(key)
    }

    counts.set(blaze, (counts.get(blaze) ?? 0) + 1)
  }

  return counts
}

/**
 * Whether the map is currently drawing any trail that is not the chosen
 * system's (#783, features/NEARBY_TRAILS.md §1).
 *
 * The legend's ghosting sentence is the only caller, and it is why this
 * returns a boolean rather than a count: the sentence explains a state
 * ("other trails are dimmed"), it does not report a quantity, and a number
 * nobody renders is a number that goes wrong unnoticed.
 *
 * Asked of the same rendered frame the blaze counts come from, with the same
 * two traps handled the same way - see this module's header. It does NOT
 * de-duplicate by feature id, because it stops at the first nearby trail it
 * finds: one is as true as forty for the sentence this answers.
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
