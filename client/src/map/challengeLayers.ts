// Challenge places on the canvas: the source, the one symbol layer that draws
// them, and the switch (#1780 — Let a club publish a challenge — places on
// its own trails that hikers opt into and tag at camp — starting with the
// ATC's A.T. Summer Bucket List; features/CHALLENGES.md, frame #1).
//
// workdayLayers.ts's shape, with drought's switch (droughtLayers.ts) and
// with the differences a challenge place actually has. Which places, and
// which are drawn filled, is map/challengePins.ts's.
//
// **OFF UNTIL THE HIKER ASKS, AND NOTHING ELSE CHANGES WHEN THEY DO.** The
// design's principle 2 is "the walking view does not change": the layer is
// built hidden, `setChallengeVisible` is the only thing that shows it, and
// showing it draws pins and nothing more - no label, no count, no live
// region, no notification (chrome/MapScreen.test.tsx holds that last half).
//
// **DRAWN OVER THE PLACE'S OWN WAYPOINT PIN, AND WHAT THAT COVERS.** Every
// challenge place is a published POI (lib/challenges.ts's ChallengePlace
// carries the POI's own coordinate), so its waypoint pin is already on the
// map at the same point. The diamond is drawn concentric with that pin and
// just big enough to cover it (map/challengePin.ts), so with the layer on the
// place reads as a diamond, which is what the handoff's frame draws. The
// cost, stated rather than smoothed over: with the layer on, that place's
// category glyph, its hollow-if-unverified fill, its staleness ring and any
// dispute mark (map/disputeLayers.ts, drawn on the pin's edge) are under the
// diamond. A site's member badges fan out past it and stay visible. In the
// ATC draft (pipeline/reference/challenges/atc/, 2026-09-30) the pinned places
// are viewpoints, communities and one shelter (The Priest) - no water - and
// a tap still opens that waypoint's card, which carries every one of those
// facts in words. `@unvalidated` whether hikers read the swap correctly;
// what would settle it is somebody with the layer on being asked what is at
// a diamond, which nobody has tried.
//
// **IT TAKES NO PART IN PLACEMENT**, unlike the workday pin. The workday
// submits to the collision engine so an invitation never shoves a waypoint
// aside. A challenge diamond shoving anything aside - a neighbour's pin to a
// dot, a trail name off the map - would be the walking view changing because
// a hiker joined a challenge, so it both allows overlap and ignores
// placement: it always draws, and it claims no space. It sits on a pin that
// is already there; it never needs space of its own.
//
// **NO TAP OF ITS OWN.** A tap on a diamond lands on the waypoint pin under
// it, which map/poiTaps.ts already turns into that POI's id - the card opens
// through MapView's `onSelectPoi`, the seam the waypoint itself uses. A
// second handler reporting the same id would break the rule poiTaps.ts,
// closureLayers.ts, atcUpdateLayers.ts and lineTaps.ts each keep ("one touch,
// one interpreter"): all four arbitrate against the POI pin layer by name,
// and a new layer would have to be taught to all four. THE GAP: where the
// hiker has hidden that waypoint's category, chosen "None", or filtered it
// out with Verified?, no waypoint pin is under the diamond and a tap opens
// nothing. Search, In view and the challenge's own page still reach it.

import type {
  GeoJSONSourceSpecification,
  LayerSpecification,
} from '@maplibre/maplibre-gl-style-spec'
import type { FeatureCollection, Point } from 'geojson'
import type { GeoJSONSource, Map as MapLibreMap } from 'maplibre-gl'
import {
  buildChallengeIcon,
  CHALLENGE_ICON_ID,
  CHALLENGE_TAGGED_ICON_ID,
} from './challengePin'
import { POI_PIN_INK_SIZE, POI_PIN_PIXEL_RATIO, POI_PIN_SIZE } from './poiIcons'
import { POI_PIN_MIN_ZOOM } from './poiLayers'
import { whenStyleReady } from './styleReady'

export const CHALLENGE_SOURCE_ID = 'challenge-places'
export const CHALLENGE_LAYER_ID = 'challenge-place-pins'

/** Where a pin says whether it is drawn filled. */
export const CHALLENGE_TAGGED_PROPERTY = 'tagged'

export interface ChallengePinProperties {
  /** The published POI id the place is. The feature's identity: one pin per
   *  POI, however many items name it. */
  poi: string
  /** The POI's own published name - not an item title, which for a mystery
   *  item is the thing a pin must not give away. */
  name: string
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

export function buildChallengeSource(): GeoJSONSourceSpecification {
  return { type: 'geojson', data: { type: 'FeatureCollection', features: [] } }
}

/**
 * Where the diamond's centre sits from the place's coordinate, in CSS px: on
 * the centre of the full-size waypoint pin standing on that coordinate.
 *
 * A waypoint pin stands on its point (map/poiLayers.ts: `icon-anchor:
 * 'bottom'` plus PIN_OFFSET_EXPRESSION, so the drawn pin's bottom edge is
 * the coordinate), which puts its centre POI_PIN_INK_SIZE / 2 above the
 * place at full size. Centring the diamond there is what lets it cover the
 * pin exactly, and at every smaller size the zoom shrinks a pin to it still
 * covers it: a smaller pin stands on the same point, lower inside the same
 * diamond. The coordinate itself stays inside the diamond, 13 px below its
 * centre and 5.4 px above its bottom tip - the place is under the mark, not
 * beside it, which is poiLayers.ts's objection to an offset.
 */
export const CHALLENGE_PIN_OFFSET: [number, number] = [0, -POI_PIN_INK_SIZE / 2]

export function buildChallengeLayer(
  sourceId: string = CHALLENGE_SOURCE_ID,
): LayerSpecification {
  return {
    id: CHALLENGE_LAYER_ID,
    type: 'symbol',
    source: sourceId,
    // The waypoints' seam: below it the map is trail lines only (#1292), and
    // a diamond at a place whose own pin is not drawn yet would be the one
    // point mark on the opening view.
    minzoom: POI_PIN_MIN_ZOOM,
    layout: {
      // Hidden in the style, always. The switch is chrome/Legend.tsx's and
      // `setChallengeVisible` flips it on a live map, never through a style
      // rebuild - droughtLayers.ts's reason: a rebuild drops the WebGL
      // context a hiker is holding.
      visibility: 'none',
      'icon-image': [
        'case',
        ['==', ['get', CHALLENGE_TAGGED_PROPERTY], true],
        CHALLENGE_TAGGED_ICON_ID,
        CHALLENGE_ICON_ID,
      ],
      'icon-size': 1,
      'icon-offset': CHALLENGE_PIN_OFFSET,
      // See the header: always drawn, claims no space.
      'icon-allow-overlap': true,
      'icon-ignore-placement': true,
    },
  }
}

/** Registers both pin images on a live map, and returns a detach. */
export function attachChallengeIcons(map: MapLibreMap): () => void {
  return whenStyleReady(
    map,
    // The layer existing proves the style spec is parsed, which is the
    // condition addImage actually requires - attachWorkdayIcon's question.
    () => map.getLayer(CHALLENGE_LAYER_ID) !== undefined,
    () => {
      for (const [id, tagged] of [
        [CHALLENGE_ICON_ID, false],
        [CHALLENGE_TAGGED_ICON_ID, true],
      ] as const) {
        // Images outlive a style reload, and re-adding one throws.
        if (!map.hasImage(id)) {
          map.addImage(id, buildChallengeIcon(tagged, POI_PIN_SIZE), {
            pixelRatio: POI_PIN_PIXEL_RATIO,
          })
        }
      }
    },
    'challenge pin images',
  )
}

/** Pushes the pins onto the live map's source, and returns a detach. An empty
 *  collection is the ordinary argument: nothing joined, or nothing joined
 *  that names a place. */
export function attachChallengeData(
  map: MapLibreMap,
  features: ChallengePinFeatureCollection,
): () => void {
  return whenStyleReady(
    map,
    () => map.getSource(CHALLENGE_SOURCE_ID) !== undefined,
    () => {
      const source = map.getSource<GeoJSONSource>(CHALLENGE_SOURCE_ID)
      if (source === undefined || typeof source.setData !== 'function') return
      source.setData(features as never)
    },
    'challenge places',
  )
}

/**
 * Shows or hides the layer, and returns a detach.
 *
 * Separate from the data for setDroughtVisible's reason: the pins change when
 * a hiker tags or joins, the switch whenever they tap it, and folding the two
 * together would re-push the pins on every tap.
 */
export function setChallengeVisible(map: MapLibreMap, shown: boolean): () => void {
  return whenStyleReady(
    map,
    () => map.getLayer(CHALLENGE_LAYER_ID) !== undefined,
    () => {
      map.setLayoutProperty(CHALLENGE_LAYER_ID, 'visibility', shown ? 'visible' : 'none')
    },
    'challenge places visibility',
  )
}
