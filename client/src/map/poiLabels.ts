// Waypoint names on the map, while a day hike is being built (#1194).
//
// The design handoff's complaint #2 - "locations were hard to find" - is
// mostly this. Checked 2026-09-02: `text-field` appears in map/ on the
// contour, peak, water and place layers of the live sheet, on trail names
// (map/trailLabels.ts, #930), and on the builder's own tap numbers. Not one
// waypoint on this map has ever carried its name. A hiker looking for the
// shelter has a green pin among forty green pins and no way to tell which,
// short of tapping each in turn.
//
// WHY A SEPARATE LAYER AND NOT A `text-field` ON THE PINS
//
// Because they must be allowed to lose independently. `map/poiLayers.ts`
// places pins with `icon-allow-overlap: false`, and a pin that loses is
// demoted to a dot rather than removed (#597) - the map keeps saying
// something is there. A name has no such fallback: half a name is not a
// shorter name, it is a different place. So names join the collision pass as
// their own symbols, and a crowded junction sheds names while keeping every
// pin, which is the trade a hiker wants in both directions.
//
// It is also the only arrangement in which the ladder works at all. A name's
// priority is not its pin's priority: map/labelLadder.ts ranks a PARKING
// label above a WATER label because that is what a hiker choosing a start
// point needs, while map/poiPriority.ts ranks the water PIN above the parking
// pin because that is what a hiker on the trail needs. Both are right, and
// one `symbol-sort-key` cannot hold both.
//
// WHY IT IS THE BUILDER'S LAYER RATHER THAN THE MAP'S
//
// It draws only while the day-hike builder is open. Names are what this
// screen was missing; the walking map is a different screen with a different
// density budget, and #1135's decision about what the opening map draws was
// taken without this layer in it. Turning it on everywhere is a design
// question somebody should answer deliberately rather than a side effect of
// fixing the builder - so `visibility` is the shell's to set, and the default
// is off.

import type { LayerSpecification } from '@maplibre/maplibre-gl-style-spec'
import type { Map as MapLibreMap } from 'maplibre-gl'
import { POI_ID_PROPERTY, POI_NAME_PROPERTY, POI_SOURCE_ID } from './poiLayers'
import { LABEL_TIER, TIER_MIN_ZOOM } from './labelLadder'
import { whenStyleReady } from './styleReady'

export const POI_LABEL_LAYER_ID = 'poi-labels'

/** The one bundled face - see map/liveTopo.ts's BUNDLED_GLYPHS. */
const FONT = ['Noto Sans Regular']

/**
 * Which waypoints get a name, and which rung each sits on.
 *
 * `parking` is tier 1 with the roads, which is the handoff's central claim
 * about this screen and worth restating where somebody might "tidy" it into
 * poiPriority.ts's order: a lot is how a hiker reaches the trail, so on a
 * PLANNING map its name outranks a spring's. On the walking map it does not,
 * and that map does not draw this layer.
 *
 * The rest are landmarks. A chosen stop is lifted out of this table
 * altogether by {@link poiLabelSortKey} - it is tier 2, above every trail
 * name, because the handoff's rule is that "a stop the user chose always
 * keeps its name" and a name that vanishes when the map gets busy is not a
 * kept one.
 *
 * TYPES NOT LISTED DRAW NO NAME. Privies, crossings and resupply points keep
 * their pins and stay anonymous, which is deliberate rather than an oversight:
 * this layer exists to answer "where do I start" and "which shelter is that",
 * and a privy label at every shelter is the clutter complaint #2 was about.
 */
const LABELLED_TYPES: Record<string, number> = {
  parking: LABEL_TIER.gateway,
  shelter: LABEL_TIER.landmark,
  campsite: LABEL_TIER.landmark,
  viewpoint: LABEL_TIER.landmark,
  water: LABEL_TIER.landmark + 1,
}

/** Every type this layer will draw a name for. */
export const LABELLED_POI_TYPES: readonly string[] = Object.keys(LABELLED_TYPES)

/**
 * The sort key, with the chosen stops lifted to tier 2.
 *
 * An EXPRESSION over a literal id list rather than a property on the feature,
 * and the reason is cost. `poiFeatureCollection` rebuilds ~2,800 points, and
 * its own note weighs that against a legend tap; adding a `stop_chosen`
 * property would pay it again on every stop a hiker adds or removes. A layout
 * property is one `setLayoutProperty` on a live map - map/mapDetail.ts's
 * pattern, and the same reason that module never rebuilds a style either.
 */
export function poiLabelSortKey(chosenStopIds: readonly string[]): unknown[] {
  return [
    'case',
    ['in', ['get', POI_ID_PROPERTY], ['literal', [...chosenStopIds]]],
    LABEL_TIER.route,
    [
      'match',
      ['get', 'poi_type'],
      ...Object.entries(LABELLED_TYPES).flatMap(([type, tier]) => [type, tier]),
      LABEL_TIER.rest,
    ],
  ]
}

/**
 * The zoom a name starts drawing at, per rung.
 *
 * Parking arrives with the pins; everything else waits for the landmark tier,
 * so the wide view is the handoff's "park" band - parking, roads and the
 * route - rather than every shelter in Harriman at once. A chosen stop is the
 * exception and appears as soon as any label does: the hiker put it there.
 */
export function poiLabelMinZoom(chosenStopIds: readonly string[]): unknown[] {
  return [
    'case',
    ['in', ['get', POI_ID_PROPERTY], ['literal', [...chosenStopIds]]],
    TIER_MIN_ZOOM.route,
    ['==', ['get', 'poi_type'], 'parking'],
    TIER_MIN_ZOOM.gateway,
    TIER_MIN_ZOOM.landmark,
  ]
}

/**
 * Names for the waypoints worth naming.
 *
 * `hiddenTypes` is the builder's own label toggles (lib/mapLabelLayers.ts),
 * NOT the legend's waypoint filters - those take pins off the map and these
 * take only names off, and a hiker who turned off "campsites" in the label
 * row still wants to see campsite pins. Two controls, two effects, and
 * conflating them would make the label row feel like it was deleting the map.
 */
export function buildPoiLabelLayer(
  chosenStopIds: readonly string[] = [],
  sourceId: string = POI_SOURCE_ID,
): LayerSpecification {
  return {
    id: POI_LABEL_LAYER_ID,
    type: 'symbol',
    source: sourceId,
    // The floor for the whole layer; the per-rung gate is in the filter,
    // because a layer has one `minzoom` and the ladder has several.
    minzoom: TIER_MIN_ZOOM.gateway,
    filter: poiLabelFilter([], chosenStopIds) as never,
    layout: {
      visibility: 'none',
      'text-field': ['get', POI_NAME_PROPERTY] as never,
      'text-font': FONT,
      // The handoff asks for 12-15px rendered and caps phones at 13. One
      // size, stepped by zoom rather than by viewport: a label sized off the
      // container is the bug its own "Label sizing rule" section is about,
      // and in a real engine text is already screen-space so the problem
      // does not arise.
      'text-size': ['interpolate', ['linear'], ['zoom'], 9, 12, 14, 13.5] as never,
      // Beside the pin, not over it. The pin is 30-38px and centred on the
      // waypoint, so an anchored label would sit on its own glyph.
      'text-variable-anchor': ['left', 'right', 'top', 'bottom'],
      'text-radial-offset': 1.1,
      'text-justify': 'auto',
      'text-max-width': 9,
      'text-padding': 3,
      'symbol-sort-key': poiLabelSortKey(chosenStopIds) as never,
      // Left at the spec default (false) - the declutter, and the whole point
      // of the ladder above. See map/poiLayers.ts's note on the same default.
    },
    paint: {
      'text-color': '#2b2620',
      'text-halo-color': '#fffdf7',
      'text-halo-width': 1.5,
    },
  }
}

/**
 * Which names are drawn: a named waypoint of a labelled type, minus the
 * classes the hiker has switched off.
 *
 * The empty-name clause is map/trailLabels.ts's restraint applied to
 * waypoints - "absent, never 'Unnamed'". lib/trailData.ts fills a missing
 * name with the literal string `Unnamed`, so without this every anonymous
 * spring in the park would print that word at 13px, which is worse than
 * silence in exactly the way a fabricated figure is.
 */
export function poiLabelFilter(
  hiddenTypes: readonly string[],
  chosenStopIds: readonly string[] = [],
): unknown[] {
  const shown = LABELLED_POI_TYPES.filter((type) => !hiddenTypes.includes(type))
  return [
    'all',
    ['in', ['get', 'poi_type'], ['literal', shown]],
    ['!=', ['get', POI_NAME_PROPERTY], ''],
    ['!=', ['get', POI_NAME_PROPERTY], 'Unnamed'],
    // THE ZOOM LADDER, and it is a filter rather than a `minzoom` because a
    // layer has one of those and the ladder has three rungs. MapLibre
    // re-evaluates a filter's `zoom` at each integer zoom level, which is the
    // granularity a tier boundary needs.
    //
    // A filter rather than `text-opacity`, which was the other candidate and
    // is wrong: a symbol at opacity 0 still takes part in placement, so
    // fading a landmark name out would go on costing a parking label its
    // space at exactly the zoom where parking is the only thing that matters.
    ['>=', ['zoom'], poiLabelMinZoom(chosenStopIds)],
  ]
}

/**
 * Keeps the label layer in step with the hiker's toggles and chosen stops.
 *
 * Pure layer properties on a live map, never a style rebuild - map/mapDetail.ts
 * states the rule and the cost it avoids: a rebuild drops the WebGL context a
 * hiker is holding.
 */
export function attachPoiLabels(
  map: MapLibreMap,
  options: {
    shown: boolean
    hiddenTypes: readonly string[]
    chosenStopIds: readonly string[]
  },
): () => void {
  return whenStyleReady(
    map,
    () => map.getLayer(POI_LABEL_LAYER_ID) !== undefined,
    () => {
      map.setLayoutProperty(
        POI_LABEL_LAYER_ID,
        'visibility',
        options.shown ? 'visible' : 'none',
      )
      map.setFilter(
        POI_LABEL_LAYER_ID,
        poiLabelFilter(options.hiddenTypes, options.chosenStopIds) as never,
      )
      map.setLayoutProperty(
        POI_LABEL_LAYER_ID,
        'symbol-sort-key',
        poiLabelSortKey(options.chosenStopIds) as never,
      )
    },
    'poi-labels',
  )
}
