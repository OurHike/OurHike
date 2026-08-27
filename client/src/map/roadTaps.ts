// What a tap in the day-hike builder landed on when it did not land on a
// trail (#931).
//
// THE ISSUE'S PREMISE TURNED OUT TO BE FALSE, AND THAT IS THE WHOLE REASON
// THIS MODULE IS SMALL.
//
// #931 says: *"a hiker still cannot SEE that the road is there, which is the
// whole point of its LATER row."* Measured 2026-08-27, that is not what ships.
// `map/liveTopo.ts` draws four transportation classes on the live vector
// sheet - `topo-road-major`, `topo-road-minor`, `topo-track` and `topo-path` -
// and its own comment says why tracks get their own weight: *"Tracks are how
// you reach most trailheads, and forest roads are a real bail-out option."*
// The road under a Harriman loop is on the map already, in the hiker's hand,
// today.
//
// So the maintainer's decision - *draw connectors as context a hiker can see
// and decide about, and never let the router choose one* - is half built and
// nobody had noticed. The half that is missing is not cartography. It is that
// the builder answers a tap on a clearly-drawn road with:
//
//   "That tap isn't on a marked hiking route."
//
// which is true and reads as *there is nothing there*, when the hiker is
// pointing at a line the app drew for them. That sentence is the failure this
// module fixes, and it is a copy problem wearing a cartography problem's
// clothes.
//
// WHAT IT DOES NOT DO, DELIBERATELY
//
// No walkability judgement. MAP_OPTIONS.md §2's tiers - `confirmed_sidewalk`,
// `no_sidewalk_low_traffic`, `no_sidewalk_high_speed` - stay unbuilt, because
// a road with a shoulder and a road with a guardrail at 55 mph are the same
// OSM line class and nobody has evidence to tell them apart. This module reads
// what OSM says is there and makes no claim about whether anybody can walk it.
// The sentence it produces says exactly that.
//
// And nothing here reaches the router. A road is never a candidate, never an
// edge, never part of a route. What the hiker can do with it is what #935's
// segments model already allows: end a stretch, walk the road themselves, and
// start the next stretch on the far side.

import type { Map as MapLibreMap } from 'maplibre-gl'

import { LIVE_TOPO_LAYER_IDS } from './liveTopo'

/** The transportation layers the live sheet draws, in the order a tap should
 *  prefer them: the specific, named thing over the ambient one. */
const ROAD_LAYERS: readonly string[] = [
  LIVE_TOPO_LAYER_IDS.track,
  LIVE_TOPO_LAYER_IDS.roadMinor,
  LIVE_TOPO_LAYER_IDS.roadMajor,
]

/** How far from the touch to look, in CSS pixels - the same slop
 *  map/lineTaps.ts gives a trail line, because a thumb is the same size
 *  whatever it is aimed at. */
const ROAD_TAP_SLOP_PX = 8

/** What a tap found where there was no trail. */
export interface TappedRoad {
  /** OSM's name for it, where it has one. Null is ordinary - most forest
   *  roads and tracks are unnamed, and inventing "Unnamed road" would read as
   *  a data error rather than the normal state it is. */
  name: string | null
  /** `track` reads differently from `road` to a hiker and the sentence says
   *  so: one is how you reach most trailheads, the other has traffic on it. */
  kind: 'road' | 'track'
}

function stringProp(properties: unknown, key: string): string | null {
  if (typeof properties !== 'object' || properties === null) return null
  const value = (properties as Record<string, unknown>)[key]
  return typeof value === 'string' && value !== '' ? value : null
}

/**
 * The road or track under a point on the canvas, or null.
 *
 * Null covers two situations this module does not distinguish, because the
 * caller's answer is the same for both: there is genuinely nothing there, and
 * the hiker is on a sheet that draws no roads (the downloaded raster, or a
 * style with the live layers off). Both end with the builder's existing
 * off-network refusal, which is the honest sentence when the app cannot see
 * what the hiker is pointing at either.
 */
export function tappedRoadAt(
  map: MapLibreMap,
  point: { x: number; y: number },
): TappedRoad | null {
  // Querying a layer the style does not hold fires an error event rather than
  // throwing - the guard poiTaps.ts states and lineTaps.ts repeats.
  const layers = ROAD_LAYERS.filter((layer) => map.getLayer(layer) !== undefined)
  if (layers.length === 0) return null

  const box: [[number, number], [number, number]] = [
    [point.x - ROAD_TAP_SLOP_PX, point.y - ROAD_TAP_SLOP_PX],
    [point.x + ROAD_TAP_SLOP_PX, point.y + ROAD_TAP_SLOP_PX],
  ]
  const features = map.queryRenderedFeatures(box, { layers })
  if (features.length === 0) return null

  // A named feature wins over an unnamed one at the same touch, because the
  // sentence is worth much more with a name in it - "Seven Lakes Drive is a
  // road" tells a hiker where they are; "that's a road" tells them what they
  // could already see.
  const named = features.find(
    (feature) => stringProp(feature.properties, 'name') !== null,
  )
  const chosen = named ?? features[0]
  const layerId = chosen.layer?.id

  return {
    name: stringProp(chosen.properties, 'name'),
    kind: layerId === LIVE_TOPO_LAYER_IDS.track ? 'track' : 'road',
  }
}

/**
 * What the builder says about a tap that landed on a road.
 *
 * THE THREE THINGS THIS SENTENCE HAS TO DO, and it is worth being explicit
 * because the sentence it replaces failed the second one:
 *
 * 1. Say what the hiker tapped, so they know the app saw it.
 * 2. Say why it is not a route - which is about EVIDENCE, not about the road
 *    being unimportant. Nobody walks a road for us to check it.
 * 3. Say what they can do instead, which is #935's segments model: the walk
 *    carries on past ground OurHike will not claim to know.
 *
 * No judgement about whether the road is safe to walk. That is the tiers
 * MAP_OPTIONS.md §2 leaves unbuilt for want of evidence, and a sentence here
 * implying either way would be exactly the claim this module refuses to make.
 */
export function roadRefusal(road: TappedRoad): string {
  const what =
    road.name !== null
      ? `${road.name} is a ${road.kind}`
      : road.kind === 'track'
        ? "That's a track"
        : "That's a road"
  return `${what}, and no organization maintains it for walking — so OurHike won't route you along it. If you're walking it anyway, start a new stretch on the far side.`
}
