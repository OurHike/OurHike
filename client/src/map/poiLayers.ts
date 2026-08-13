// Putting the POIs on the map: the source, the one symbol layer that draws
// them, and the three imperative pokes the shell makes at a live map.
//
// poiIcons.ts is pure pixel maths and knows nothing about MapLibre; this is
// the module that knows about MapLibre and nothing about pixels.
//
// There is ONE SYMBOL layer. Not one per category, which is the obvious shape
// and the wrong one:
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
//
// THE SECOND LAYER, AND WHY IT DOES NOT BREAK THE ARGUMENT ABOVE (#597)
//
// {@link POI_DOT_LAYER_ID} is a `circle` layer under the pins, drawing every
// waypoint in the source. The argument above is entirely about COLLISION, and
// collision in MapLibre is a property of SYMBOL layers - a circle layer does
// not participate in placement at all, so it cannot fragment a placement pass
// and cannot stack a second pin on a shelter. Adding it costs the argument
// nothing; a second symbol layer would have cost it everything.
//
// What it buys: above {@link POI_PIN_MIN_ZOOM} a waypoint draws as a pin OR as
// a dot and never as neither. The collision engine stops deciding which
// waypoints EXIST and starts deciding which get the big treatment. Both layers
// read the same source and take the same filter, so the legend cannot get out
// of step with either.
//
// features/POI_VISIBILITY.md is the design.

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
  SITE_ANCHOR_TYPES,
  SITE_MEMBERS_PROPERTY,
  composeSites,
  siteMembersKey,
  type SiteVisibility,
} from './poiSites'
import { POI_PRIORITY } from './poiPriority'
import {
  buildPoiIcons,
  PIN_HALO_COLOR,
  poiColor,
  poiIconId,
  siteMemberCombinations,
  UNKNOWN_POI_TYPE,
  type PoiConfidence,
} from './poiIcons'
import { whenStyleReady } from './styleReady'

export const POI_SOURCE_ID = 'pois'
export const POI_LAYER_ID = 'poi-pins'

/**
 * Where a pin carries its POI id, so a tap on it can be turned back into the
 * POI the app holds (poiTaps.ts).
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
 * The seam. Below this the map is the corridor view and carries no waypoints
 * at all; above it every waypoint draws, as a pin or as a dot.
 *
 * A DAY'S HIKE HAS TO FIT ON THE SCREEN, and that is the whole criterion.
 * A day on the A.T. is 16-24 miles; a 390x700 phone map covers 25.5 miles of
 * ground at z10 and 12.7 at z11. So z10 is the tightest zoom that still shows
 * a hiker the day they are about to walk, waypoints and all, which is the
 * moment this map is for.
 *
 * MEASURED at that zoom rather than hoped for -
 * pipeline/spike_poi_seam.py, 2026-08-13, against the live ATC service with
 * lib/poi_sites.py's own folding applied. What reaches a PIN at z10: shelters
 * 95%, privies 82%, campsites 76%, parking 51%, viewpoints 15%. The things a
 * day is planned around are nearly all pins; the vistas are nearly all dots,
 * which is the right way round and is what the dot rank is for.
 *
 * THIS WAS z12 FOR AN AFTERNOON, and the mistake is worth recording because
 * the arithmetic was right and the question was wrong. The first pass chose
 * the seam as "the tightest zoom where the screen is not oversubscribed with
 * pins" - a pin-legibility test. Under two ranks an overfull screen costs
 * DOTS, not deletions, so legibility is a comfort criterion and truth is not
 * at stake. z12 showed 6.4 miles: a quarter of a day, and a hiker planning one
 * would have had to pan four times to see it.
 *
 * It replaces a floor of 9, whose docstring argued - rightly - that eight
 * hundred POIs on a corridor view "is not a map, it is a texture". That
 * argument was never wrong; what changed is that the corridor view now has
 * something else to show (features/CORRIDOR_VIEW.md), so the floor no longer
 * has to choose between a texture and an empty screen.
 */
export const POI_PIN_MIN_ZOOM = 10

// {@link POI_PRIORITY} lives in poiPriority.ts and is imported above. It moved
// there when site composition needed the same ordering to decide which member
// carries a pin whose anchor has been filtered out (#607) - one home, and not
// re-exported from here, so there is one path to it rather than two.

function iconMatch(
  confidence: PoiConfidence,
  members: readonly string[] = [],
): unknown[] {
  // Only the anchor types have site variants built, so only they get an arm
  // carrying members - asking for `poi-viewpoint-verified-privy` would resolve
  // to an image nobody registered, which MapLibre draws as nothing at all.
  const sited = new Set<string>(SITE_ANCHOR_TYPES)
  return [
    'match',
    ['get', 'poi_type'],
    ...POI_TYPES.flatMap((type) => [
      type,
      poiIconId(type, confidence, sited.has(type) ? members : []),
    ]),
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
/**
 * The site pin an anchor asks for, by what it carries (#524).
 *
 * A `match` on the whole `site_members` string rather than arithmetic on a list:
 * MapLibre expressions compare scalars, and map/poiSites.ts writes exactly these
 * strings for exactly this reason. The empty arm is the fall-through - a pin
 * carrying nothing, which is every pin that is not a site anchor - so the plain
 * path and the site path are one expression rather than two that could drift.
 */
function siteAwareIconMatch(confidence: PoiConfidence): unknown[] {
  return [
    'match',
    ['get', SITE_MEMBERS_PROPERTY],
    ...siteMemberCombinations().flatMap((members) => [
      siteMembersKey(members),
      iconMatch(confidence, members),
    ]),
    iconMatch(confidence),
  ]
}

export const POI_ICON_EXPRESSION: unknown[] = [
  'case',
  ['==', ['get', 'confidence'], 'high'],
  siteAwareIconMatch('high'),
  siteAwareIconMatch('low'),
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
 * At the far end of {@link POI_PIN_MIN_ZOOM} they are markers saying something
 * is there; by the zoom a hiker actually walks at they are full size and their
 * glyph is legible. One interpolation covers both.
 *
 * The low anchor moved with the seam, which makes the render slightly kinder
 * than the measurement: spike_poi_seam.py simulated full-size 42 px boxes at
 * every zoom, and a pin at 0.6 asks for about 25 px, so z12 fits somewhat more
 * than the run reported. Conservative in the direction that matters.
 */
export const POI_ICON_SIZE_EXPRESSION: unknown[] = [
  'interpolate',
  ['linear'],
  ['zoom'],
  POI_PIN_MIN_ZOOM,
  0.6,
  13,
  1,
]

export function buildPoiLayer(sourceId: string = POI_SOURCE_ID): LayerSpecification {
  return {
    id: POI_LAYER_ID,
    type: 'symbol',
    source: sourceId,
    minzoom: POI_PIN_MIN_ZOOM,
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

/** The dot rank: every waypoint, at its real coordinates, always drawn. */
export const POI_DOT_LAYER_ID = 'poi-dots'

/**
 * A dot's colour is its category's accent - the same one its pin wears.
 *
 * Built from poiIcons.ts's table rather than a second palette, for the reason
 * that file already gives about anything drawn to match a pin: two tables
 * cannot disagree about an accent if there is only one.
 */
export const POI_DOT_COLOR_EXPRESSION: unknown[] = [
  'match',
  ['get', 'poi_type'],
  ...POI_TYPES.flatMap((type) => [type, poiColor(type)]),
  poiColor(UNKNOWN_POI_TYPE),
]

/**
 * Small, and smaller the further out you are.
 *
 * A dot is a claim that something is HERE and nothing else; it is not trying
 * to say what, which is the pin's job. At the seam the trail is a stipple of
 * them and at walking zoom they are mostly hidden under the pins that won.
 *
 * 2.5 px at {@link POI_PIN_MIN_ZOOM} is ink a sighted hiker can see without it
 * competing with a 38 px pin. It wants a look on a real screen in real
 * sunlight (#105) - like the site pin's badge, this is the decision in the
 * design most likely to be wrong in a browser and right on a phone, or the
 * reverse.
 */
export const POI_DOT_RADIUS_EXPRESSION: unknown[] = [
  'interpolate',
  ['linear'],
  ['zoom'],
  POI_PIN_MIN_ZOOM,
  2.5,
  16,
  4,
]

/**
 * The rank that cannot lose.
 *
 * A `circle` layer, and that is the entire mechanism rather than an
 * implementation detail: MapLibre's collision engine is a property of SYMBOL
 * layers, so a circle participates in no placement pass and every feature
 * renders, at any camera. Making this a small symbol layer instead would have
 * put it straight back into the collision it exists to escape.
 *
 * Drawn UNDER the pins (map/style.ts's layer order), so a waypoint that wins
 * its collision shows a pin with its own dot invisible beneath it, and one
 * that loses still shows the dot. No feature is in neither state, which is the
 * whole of features/POI_VISIBILITY.md's "never as neither".
 *
 * Same source and same filter as the pins - see {@link attachPoiFilter}. It
 * therefore inherits site folding for free: poiFeatureCollection already emits
 * one feature per site, so a privy riding its shelter's pin does not also get
 * a dot 40 m away claiming to be a second place.
 */
export function buildPoiDotLayer(sourceId: string = POI_SOURCE_ID): LayerSpecification {
  return {
    id: POI_DOT_LAYER_ID,
    type: 'circle',
    source: sourceId,
    minzoom: POI_PIN_MIN_ZOOM,
    paint: {
      'circle-radius': POI_DOT_RADIUS_EXPRESSION as unknown as number,
      'circle-color': POI_DOT_COLOR_EXPRESSION as unknown as string,
      // The same halo the pins wear, for the same reason poiIcons.ts gives:
      // the accents are legible on cream paper and some of them are not
      // legible on the field sheet's white without an edge.
      'circle-stroke-width': 1,
      'circle-stroke-color': PIN_HALO_COLOR,
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
    properties: {
      poi_type: string
      confidence: string
      [POI_ID_PROPERTY]: string
      [SITE_MEMBERS_PROPERTY]: string
    }
  }>
}

/**
 * Carries what the style reads - the two attributes the expressions above
 * match on - and the id to find the rest by, which rides in the properties for
 * the reason {@link POI_ID_PROPERTY} gives. Names are not here because nothing
 * draws them - see the note about `glyphs` in {@link buildPoiLayer}.
 */
export function poiFeatureCollection(
  pois: readonly MapPoint[],
  visibility: SiteVisibility = {},
): PoiFeatureCollection {
  // ONE FEATURE PER SITE, not per POI (#524). The members are removed here
  // rather than filtered in the style, which is the whole mechanism: a style
  // filter still hands MapLibre a symbol to place and lose, where a source
  // without the member never asks for a box at all. See map/poiSites.ts for why
  // deletion rather than overlap was the problem.
  //
  // WHICH IS WHY THE FILTERS ARE PASSED IN (#607). The removal is only safe
  // while the pin that replaces the member is on the map, and {@link poiFilter}
  // can take that pin off - so this collection has to be rebuilt when the hidden
  // set changes, not merely re-filtered. That is a rebuild of ~2,800 points on a
  // legend tap, which is the cost the design doc weighed and accepted.
  const { drawn, membersFor } = composeSites(pois, visibility)

  return {
    type: 'FeatureCollection',
    features: drawn.map((poi) => ({
      type: 'Feature',
      id: poi.id,
      geometry: { type: 'Point', coordinates: [poi.lon, poi.lat] },
      properties: {
        poi_type: poi.type,
        confidence: poi.confidence,
        [POI_ID_PROPERTY]: poi.id,
        // Always present, empty where the pin carries nothing, so the style's
        // `match` needs no `coalesce` and a pin with no site is not a separate
        // expression path that could drift from the one with.
        [SITE_MEMBERS_PROPERTY]: siteMembersKey(membersFor.get(poi.id)),
      },
    })),
  }
}

/**
 * The legend's filters, as one layer filter.
 *
 * Always the same expression shape - an empty hidden list, and a literal
 * `true` where the confidence clause is not wanted - so "showing everything"
 * is not a separate code path that could drift from the one doing the hiding.
 *
 * `verifiedOnly` is the legend's "Verified?" toggle: waypoints nobody has
 * confirmed exist come off the map entirely. It is a filter and not a
 * restyling because the broken rim already says "unconfirmed" for a hiker who
 * wants to see them; this is for the hiker who does not.
 */
export function poiFilter(
  hiddenTypes: ReadonlySet<string>,
  verifiedOnly = false,
): unknown[] {
  return [
    'all',
    ['!', ['in', ['get', 'poi_type'], ['literal', [...hiddenTypes].sort()]]],
    verifiedOnly ? ['==', ['get', 'confidence'], 'high'] : true,
  ]
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

/**
 * Pushes POIs onto the live map's source, and returns a detach function.
 *
 * `visibility` is the same pair {@link attachPoiFilter} applies, and both are
 * needed: the filter decides which pins are drawn, this decides which POIs get
 * a pin to be drawn at all. Passing it here is what makes a site whose anchor
 * is hidden fall back to a member rather than vanish (#607).
 */
export function attachPoiData(
  map: MapLibreMap,
  pois: readonly MapPoint[],
  visibility: SiteVisibility = {},
): () => void {
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

      source.setData(poiFeatureCollection(pois, visibility) as never)
    },
    'POI data',
  )
}

/**
 * Applies the legend's filters to BOTH ranks, and returns a detach.
 *
 * Both, from one computed filter, in one pass - not because it is tidier but
 * because the alternative fails quietly: a hidden category whose pins go and
 * whose dots stay leaves the legend saying one thing and the map showing
 * another, with no error anywhere. The layer list is local and the expression
 * is computed once, so there is no path on which the two ranks disagree.
 */
export function attachPoiFilter(
  map: MapLibreMap,
  hiddenTypes: ReadonlySet<string>,
  verifiedOnly = false,
): () => void {
  const layers = [POI_LAYER_ID, POI_DOT_LAYER_ID]
  return whenStyleReady(
    map,
    // setFilter throws outright on a layer the style does not hold, so the
    // layers' presence is exactly the precondition. Both, because a style
    // mid-reload can hold one and not the other.
    () => layers.every((layer) => map.getLayer(layer) !== undefined),
    () => {
      const filter = poiFilter(hiddenTypes, verifiedOnly)
      for (const layer of layers) map.setFilter(layer, filter as never)
    },
    'POI visibility',
  )
}
