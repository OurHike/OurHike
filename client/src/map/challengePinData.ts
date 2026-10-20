// What a challenge pin carries, apart from how it is drawn - a leaf, so the
// shell can build the pins without loading the layer that draws them.
//
// #1806 — main's eager JavaScript is 245,910 bytes against the 245,760 launch
// budget since the challenges merge, so every PR's preview build fails: the
// shell builds the pins every render (chrome/challengePanel.ts →
// map/challengePins.ts), and while these names lived in map/challengeLayers.ts
// that import pulled the layer builder and the pin rasteriser
// (map/challengePin.ts) in front of the first frame with them. The same cut as
// #1591's leaves (map/styleIds.ts, map/sheetInks.ts): the ids and shapes the
// shell reads here, the layer in the map's own chunk.

import type { FeatureCollection, Point } from 'geojson'

/** Where a pin says whether it is drawn filled. */
export const CHALLENGE_TAGGED_PROPERTY = 'tagged'

export interface ChallengePinProperties {
  /** The published POI id the place is. The feature's identity: one pin per
   *  POI, however many items name it. */
  poi: string
  /** The POI's own published name - not an item title, which for a mystery
   *  item is the thing a pin must not give away. */
  name: string
  /** The POI's own published type, under the key the waypoint layer's size
   *  expression reads, so the diamond takes its pin's size tier. */
  poi_type: string
  /** Filled rather than hollow - see map/challengePins.ts's
   *  `challengePinFeatures`, which decides it. */
  [CHALLENGE_TAGGED_PROPERTY]: boolean
  /** The first joined item naming this POI, in published order. The card is
   *  what lists every item at a place ("On your challenges"); these two are
   *  for a caller that needs one of them to start from. */
  challengeId: string
  itemId: string
}

export type ChallengePinFeatureCollection = FeatureCollection<
  Point,
  ChallengePinProperties
>

/** An empty collection with one identity, for defaults - a fresh literal
 *  would re-run every effect that depends on it on every render. */
export const NO_CHALLENGE_PINS: ChallengePinFeatureCollection = {
  type: 'FeatureCollection',
  features: [],
}
