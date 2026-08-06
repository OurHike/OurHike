// Putting the POIs on the map: the source, the one symbol layer that draws
// them, and the three imperative pokes the shell makes at a live map.
//
// poiIcons.ts is pure pixel maths and knows nothing about MapLibre; this is
// the module that knows about MapLibre and nothing about pixels.
//
// Everything here is ONE layer. Not one per category, which is the obvious
// shape and the wrong one:
//
//  - Density is MapLibre's own collision engine (`icon-allow-overlap: false`),
//    and it can only declutter symbols it places together. Five layers means
//    five independent placements, and five pins stacked on the same shelter.
//  - Hiding a category is therefore a FILTER, not a per-layer `visibility`.
//    Same visible result, one code path, and no way for the legend to get out
//    of step with a layer list.
//
// What survives from that choice: which pin wins a collision is a decision
// someone has to make rather than an accident of layer order. It is
// {@link POI_PRIORITY}, and water is first in it.

import type {
  GeoJSONSourceSpecification,
  LayerSpecification,
} from '@maplibre/maplibre-gl-style-spec'
import type { GeoJSONSource, Map as MapLibreMap } from 'maplibre-gl'
import { POI_TYPES } from '../lib/config'
// The legend's own point type, deliberately. The map and the legend read the
// same array, which is what makes "the legend names exactly what is drawn"
// structural instead of a convention two call sites have to keep.
import type { MapPoint } from '../lib/legendContents'
import {
  buildPoiIcons,
  poiIconId,
  UNKNOWN_POI_TYPE,
  type PoiConfidence,
} from './poiIcons'
import { whenStyleReady } from './styleReady'

export const POI_SOURCE_ID = 'pois'
export const POI_LAYER_ID = 'poi-pins'

/**
 * Where a pin carries its POI id, so a tap on it can be turned back into the
 * POI the app holds (taps.ts).
 *
 * A property rather than the GeoJSON feature id, which is where an id belongs
 * and which cannot hold this one: MapLibre runs a string feature id through
 * `parseInt` (FeatureWrapper, maplibre-gl 6), and every id the pipeline
 * publishes - "atc_shelters:<guid>", "opentrail_at:1234" - comes back NaN. The
 * feature id below is still set, because it is the honest place for it and
 * because a numeric-id release would then work; nothing reads it.
 */
export const POI_ID_PROPERTY = 'poi_id'

/**
 * Below this, no pins at all.
 *
 * The opening view is the whole 2,197-mile corridor. Eight hundred POIs on it
 * is not a map, it is a texture - and the collision engine would answer the
 * question "which of these do I keep" by geometry, when the honest answer at
 * that zoom is "none, you are not looking at a place yet".
 */
export const POI_MIN_ZOOM = 9

/**
 * Who wins a collision, best first.
 *
 * This is a safety ordering, not a visual one. When two pins cannot both be
 * placed, the one that stays is the one a hiker most needs: water, then
 * somewhere to sleep, then supplies. WIREFRAMES.md's lanes make the same call
 * in the same order.
 */
export const POI_PRIORITY: readonly string[] = [
  'water',
  'shelter',
  'campsite',
  'resupply',
  'crossing',
]

function iconMatch(confidence: PoiConfidence): unknown[] {
  return [
    'match',
    ['get', 'poi_type'],
    ...POI_TYPES.flatMap((type) => [type, poiIconId(type, confidence)]),
    // Every arm above is a type this build knows; anything else lands on the
    // neutral pin rather than on a missing image, which MapLibre draws as
    // nothing at all while logging about it once per tile.
    poiIconId(UNKNOWN_POI_TYPE, confidence),
  ]
}

/**
 * One expression picks every pin image, from the two attributes the pipeline
 * publishes - exactly as BLAZE_MATCH_EXPRESSION does for line colour.
 *
 * The alternative, computing an icon id per feature on the way into the
 * source, would work and would move a rendering rule into data preparation,
 * where the next person to add a category would not find it.
 */
export const POI_ICON_EXPRESSION: unknown[] = [
  'case',
  ['==', ['get', 'confidence'], 'high'],
  iconMatch('high'),
  iconMatch('low'),
]

/** Water first, unknown types last. */
export const POI_SORT_KEY_EXPRESSION: unknown[] = [
  'match',
  ['get', 'poi_type'],
  ...POI_PRIORITY.flatMap((type, index) => [type, index]),
  POI_PRIORITY.length,
]

/**
 * Pins grow with zoom rather than sitting at one size.
 *
 * At the far end of {@link POI_MIN_ZOOM} they are markers saying something is
 * there; by the zoom a hiker actually walks at they are full size and their
 * glyph is legible. One interpolation covers both without a second layer.
 */
export const POI_ICON_SIZE_EXPRESSION: unknown[] = [
  'interpolate',
  ['linear'],
  ['zoom'],
  POI_MIN_ZOOM,
  0.6,
  13,
  1,
]

export function buildPoiLayer(sourceId: string = POI_SOURCE_ID): LayerSpecification {
  return {
    id: POI_LAYER_ID,
    type: 'symbol',
    source: sourceId,
    minzoom: POI_MIN_ZOOM,
    layout: {
      'icon-image': POI_ICON_EXPRESSION as unknown as string,
      'icon-size': POI_ICON_SIZE_EXPRESSION as unknown as number,
      'symbol-sort-key': POI_SORT_KEY_EXPRESSION as unknown as number,
      // The declutter. Left at the spec default deliberately rather than
      // omitted: it is the entire density story, and an `icon-allow-overlap:
      // true` added later for one screenshot would silently undo it.
      'icon-allow-overlap': false,
      // A little air, so two pins that merely touch are treated as colliding.
      'icon-padding': 2,
      // No `text-field` anywhere in this layer, and the reason has shifted
      // slightly rather than gone away. It used to be that the style had no
      // `glyphs` URL at all; the live background added one (map/style.ts), so
      // a font is now fetchable - but only with signal, and only on that
      // background. A pin label that appears in town and vanishes on the ridge
      // is worse than no pin label: it would be missing exactly when the map
      // is the only thing a hiker has. Names stay in search and the legend,
      // which work the same either way.
    },
  }
}

/**
 * The POI source, empty.
 *
 * Empty until the shell pushes real data in: POIs arrive from IndexedDB after
 * the map is built, and re-reading a style to add them would tear down the
 * WebGL context underneath the hiker.
 *
 * A function rather than a shared constant, so each style gets its own
 * `features` array instead of every map ever built pointing at one - the same
 * care buildMapStyle takes with the two sources it spells out inline.
 */
export function buildPoiSource(): GeoJSONSourceSpecification {
  return { type: 'geojson', data: { type: 'FeatureCollection', features: [] } }
}

export interface PoiFeatureCollection {
  type: 'FeatureCollection'
  features: Array<{
    type: 'Feature'
    id: string
    geometry: { type: 'Point'; coordinates: [number, number] }
    properties: { poi_type: string; confidence: string; [POI_ID_PROPERTY]: string }
  }>
}

/**
 * Carries what the style reads - the two attributes the expressions above
 * match on - and the id to find the rest by, which rides in the properties for
 * the reason {@link POI_ID_PROPERTY} gives. Names are not here because nothing
 * draws them - see the note about `glyphs` in {@link buildPoiLayer}.
 */
export function poiFeatureCollection(pois: readonly MapPoint[]): PoiFeatureCollection {
  return {
    type: 'FeatureCollection',
    features: pois.map((poi) => ({
      type: 'Feature',
      id: poi.id,
      geometry: { type: 'Point', coordinates: [poi.lon, poi.lat] },
      properties: {
        poi_type: poi.type,
        confidence: poi.confidence,
        [POI_ID_PROPERTY]: poi.id,
      },
    })),
  }
}

/**
 * The legend's hide toggles, as a layer filter.
 *
 * Always the same expression shape, with an empty list when nothing is hidden,
 * so "showing everything" is not a separate code path that could drift from
 * the one that does the hiding.
 */
export function poiTypeFilter(hiddenTypes: ReadonlySet<string>): unknown[] {
  return ['!', ['in', ['get', 'poi_type'], ['literal', [...hiddenTypes].sort()]]]
}

/** Registers every pin image on a live map, and returns a detach function. */
export function attachPoiIcons(map: MapLibreMap): () => void {
  return whenStyleReady(
    map,
    // The pin layer existing proves the style spec carrying it is parsed,
    // which is the condition addImage actually requires. There is no narrower
    // question to ask: an image is not addressable until it has been added.
    () => map.getLayer(POI_LAYER_ID) !== undefined,
    () => {
      for (const { id, image, pixelRatio } of buildPoiIcons()) {
        // Images outlive a style reload, and re-adding one throws.
        if (!map.hasImage(id)) map.addImage(id, image, { pixelRatio })
      }
    },
    'POI pin images',
  )
}

/** Pushes POIs onto the live map's source, and returns a detach function. */
export function attachPoiData(map: MapLibreMap, pois: readonly MapPoint[]): () => void {
  return whenStyleReady(
    map,
    // The source itself is the readiness question. This is the write that used
    // to be lost for good: the POIs arrive from IndexedDB exactly once, so an
    // attempt that landed while a tile was in flight never got a second turn.
    () => map.getSource(POI_SOURCE_ID) !== undefined,
    () => {
      // `getSource` answers with the union of every source kind, and only the
      // GeoJSON one can be handed new data. The `setData` check is what makes
      // the assertion above safe rather than hopeful.
      const source = map.getSource<GeoJSONSource>(POI_SOURCE_ID)
      if (source === undefined || typeof source.setData !== 'function') return

      source.setData(poiFeatureCollection(pois) as never)
    },
    'POI data',
  )
}

/** Applies the legend's hidden set to the pin layer, and returns a detach. */
export function attachHiddenPoiTypes(
  map: MapLibreMap,
  hiddenTypes: ReadonlySet<string>,
): () => void {
  return whenStyleReady(
    map,
    // setFilter throws outright on a layer the style does not hold, so the
    // layer's presence is exactly the precondition.
    () => map.getLayer(POI_LAYER_ID) !== undefined,
    () => map.setFilter(POI_LAYER_ID, poiTypeFilter(hiddenTypes) as never),
    'POI visibility',
  )
}
