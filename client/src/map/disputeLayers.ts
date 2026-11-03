// The dispute mark on the canvas (#876, features/FIELD_NOTES.md §4).
//
// workdayLayers.ts's shape, with three differences that all come from what a
// dispute IS:
//
//  1. **It never collides away.** `icon-allow-overlap` is on, like the
//     serious-warning pins and unlike everything else. §4's rule is that the
//     pin is never suppressed - "a POI that vanishes is indistinguishable
//     from one that never existed" - and a mark the collision engine drops
//     is a suppression the hiker cannot tell from an absence.
//  2. **It ignores placement too**, which the warning pins deliberately do
//     NOT. A warning should push a waypoint aside; this must not, because it
//     is drawn ON one. Pushing the pin it annotates out of the way would be
//     a footnote shoving its own sentence off the page.
//  3. **It is offset** onto the drawn pin's upper-left edge (#1687), so
//     most of the waypoint's glyph stays readable underneath. See
//     DISPUTE_MARK_OFFSET_EXPRESSION for where exactly, and what it covers.
//
// Its own source rather than a property on the POI source, and that is the
// load-bearing decision here: the POI features' `confidence` is what the
// legend's "Verified?" toggle filters on, so a dispute expressed there would
// let a filter delete the pin §4 says must never be suppressed. See
// map/disputeMark.ts.

import type {
  GeoJSONSourceSpecification,
  LayerSpecification,
} from '@maplibre/maplibre-gl-style-spec'
import type { GeoJSONSource, Map as MapLibreMap } from 'maplibre-gl'
import { buildDisputeMark, DISPUTE_MARK_ID, DISPUTE_MARK_SIZE } from './disputeMark'
import { POI_PIN_INK_SIZE } from './poiIcons'
import { POI_ICON_SIZE_EXPRESSION, POI_PIN_MIN_ZOOM } from './poiLayers'
import { whenStyleReady } from './styleReady'

export const DISPUTE_SOURCE_ID = 'poi-disputes'
export const DISPUTE_LAYER_ID = 'poi-dispute-marks'

/** Where a mark carries the id of the place it annotates - a property rather
 *  than a feature id, for poiLayers.ts's reason: MapLibre runs a string
 *  feature id through `parseInt`, and `atc_shelters:<guid>` is not a number. */
export const DISPUTE_ID_PROPERTY = 'poi_id'

/** Where a mark carries the type of the place it annotates, which decides
 *  how big that place's pin is drawn and so where its edge is (#1687). */
export const DISPUTE_TYPE_PROPERTY = 'poi_type'

/** A disputed place, reduced to what the canvas needs. The shell does the
 *  joining: the verdict comes from the server and the coordinates and type
 *  from the POI export, and neither knows about the other. */
export interface DisputePoint {
  poiId: string
  poiType: string
  lon: number
  lat: number
}

export interface DisputeFeatureCollection {
  type: 'FeatureCollection'
  features: Array<{
    type: 'Feature'
    id: string
    geometry: { type: 'Point'; coordinates: [number, number] }
    properties: { [DISPUTE_ID_PROPERTY]: string; [DISPUTE_TYPE_PROPERTY]: string }
  }>
}

export function disputeFeatureCollection(
  disputes: readonly DisputePoint[],
): DisputeFeatureCollection {
  return {
    type: 'FeatureCollection',
    features: disputes.map((dispute) => ({
      type: 'Feature',
      id: dispute.poiId,
      geometry: { type: 'Point', coordinates: [dispute.lon, dispute.lat] },
      properties: {
        [DISPUTE_ID_PROPERTY]: dispute.poiId,
        [DISPUTE_TYPE_PROPERTY]: dispute.poiType,
      },
    })),
  }
}

/**
 * Where the mark's centre sits from the waypoint's coordinate, in CSS px, for
 * a pin drawn at `scale`: ON the drawn pin's edge, 45 degrees up and to the
 * left of its centre.
 *
 * The drawn pin's centre is `POI_PIN_INK_SIZE / 2` times its scale above the
 * coordinate at every scale: the pin stands on its point (poiLayers.ts's
 * `icon-anchor: 'bottom'` and PIN_OFFSET_EXPRESSION), and both of those
 * scale with its `icon-size`. So the edge is one more radius out along the
 * diagonal.
 *
 * UPPER LEFT, not the upper right this used to aim for, because a site pin's
 * member badges fan out on the upper right (poiIcons.ts's badgeCenters) and
 * the mark would sit on a badge. ON THE EDGE rather than just outside the
 * coloured disc, which would clear every glyph: the maintainer chose it from
 * both drawn on five real pins (poll, 2026-09-26, #1687), knowing that at the
 * edge the 18 px mark hides the viewpoint's sun and clips the top-left of
 * the parking P and the privy's roof. Every glyph still shows most of its
 * shape, and the mark sits tight to the pin it annotates.
 */
export function disputeMarkOffset(scale: number): [number, number] {
  const radius = (POI_PIN_INK_SIZE / 2) * scale
  return [-radius * Math.SQRT1_2, -(radius + radius * Math.SQRT1_2)]
}

/** One of POI_ICON_SIZE_EXPRESSION's stops - a `match` on the type, full
 *  size for the loud tiers and reduced for the rest - with each size turned
 *  into the offset for a pin of that size. */
function offsetAtStop(sizeStop: unknown): unknown {
  const [op, input, loudTypes, full, reduced] = sizeStop as [
    string,
    unknown,
    readonly string[],
    number,
    number,
  ]
  return [
    op,
    input,
    loudTypes,
    ['literal', disputeMarkOffset(full)],
    ['literal', disputeMarkOffset(reduced)],
  ]
}

/**
 * `icon-offset` for the mark: {@link disputeMarkOffset} at the size the
 * annotated pin is drawn at, by zoom and by tier (#1687).
 *
 * BUILT FROM THE PIN'S OWN SIZE EXPRESSION, stop for stop, so the two cannot
 * disagree about how big the pin is. The mark itself stays 18 px at every
 * zoom (`icon-size: 1`): it is a footnote a hiker has to be able to see, and
 * shrinking it with a 15 px quiet pin at the seam would make it a speck.
 *
 * It was `[POI_PIN_SIZE / 4, -POI_PIN_SIZE / 4]` from the coordinate, aimed at
 * a 38 px pin centred ON the coordinate. Pins began standing on their point on
 * 2026-09-20 and were drawn 26 px across on 2026-09-26 (#1684), and a
 * constant offset followed neither: by then the mark sat over the edge of the
 * glyph it was placed to leave readable.
 */
export const DISPUTE_MARK_OFFSET_EXPRESSION: unknown[] = POI_ICON_SIZE_EXPRESSION.map(
  (part, index) => (index >= 4 && index % 2 === 0 ? offsetAtStop(part) : part),
)

export function buildDisputeSource(): GeoJSONSourceSpecification {
  return { type: 'geojson', data: { type: 'FeatureCollection', features: [] } }
}

export function buildDisputeLayer(
  sourceId: string = DISPUTE_SOURCE_ID,
): LayerSpecification {
  return {
    id: DISPUTE_LAYER_ID,
    type: 'symbol',
    source: sourceId,
    // The pin this annotates starts at the seam, so this does too (#1292): a
    // footnote with no sentence under it is a mark on nothing.
    minzoom: POI_PIN_MIN_ZOOM,
    layout: {
      'icon-image': DISPUTE_MARK_ID,
      'icon-size': 1,
      // On the drawn pin's upper-left edge, following the pin's size by zoom
      // and tier - see DISPUTE_MARK_OFFSET_EXPRESSION.
      'icon-offset': DISPUTE_MARK_OFFSET_EXPRESSION as unknown as [number, number],
      // See the header: never dropped, and never pushes anything.
      'icon-allow-overlap': true,
      'icon-ignore-placement': true,
    },
  }
}

/** Registers the mark image on a live map, and returns a detach. */
export function attachDisputeIcon(map: MapLibreMap): () => void {
  return whenStyleReady(
    map,
    () => map.getLayer(DISPUTE_LAYER_ID) !== undefined,
    () => {
      if (!map.hasImage(DISPUTE_MARK_ID)) {
        map.addImage(DISPUTE_MARK_ID, buildDisputeMark(DISPUTE_MARK_SIZE), {
          pixelRatio: 2,
        })
      }
    },
    'dispute mark image',
  )
}

/** Pushes the disputed places onto the live map, and returns a detach.
 *
 *  An empty array is ordinary: it is what the shell passes when nothing is
 *  disputed AND when the disputes could not be read at all. Those are
 *  different claims, and the card is where they are told apart in words -
 *  a map cannot draw "we could not ask". */
export function attachDisputeData(
  map: MapLibreMap,
  disputes: readonly DisputePoint[],
): () => void {
  return whenStyleReady(
    map,
    () => map.getSource(DISPUTE_SOURCE_ID) !== undefined,
    () => {
      const source = map.getSource<GeoJSONSource>(DISPUTE_SOURCE_ID)
      if (source === undefined || typeof source.setData !== 'function') return

      source.setData(disputeFeatureCollection(disputes) as never)
    },
    'disputed waypoints',
  )
}
