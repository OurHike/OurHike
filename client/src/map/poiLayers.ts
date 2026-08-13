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
// THE SECOND LAYER, WHICH IS NOT A SECOND PLACEMENT PASS (#597)
//
// {@link buildPoiDotLayer} adds a `circle` layer under the pins, and it does
// not weaken any of the above - because the argument above is about COLLISION,
// and a circle layer does not collide. MapLibre's collision engine is a
// property of symbol layers only; every feature in a circle layer renders, at
// every camera, whatever else is on the screen.
//
// So the two are ranks rather than rivals. A waypoint above the seam draws as
// a pin or as a dot and never as neither, which is what stops the collision
// engine deciding which waypoints EXIST and confines it to deciding which get
// the big treatment. The legend's "names exactly what is drawn" property is
// strengthened by that, not broken: at the zooms where a category used to be
// silently absent it is now present as dots.
//
// The two ranks read the SAME source and the SAME filter, and both of those
// are load-bearing rather than tidy. One source is what makes a dot and its
// pin the same waypoint; one filter is what stops a hidden category leaving
// its dots behind.

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

/** The dot rank (#597). Under {@link POI_LAYER_ID}, same source, same filter. */
export const POI_DOT_LAYER_ID = 'poi-dots'

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
 * The seam: below this the map is a corridor view and draws no waypoints at
 * all; above it, every waypoint draws as a pin or as a dot.
 *
 * The opening view is the whole 2,197-mile corridor. Eight hundred POIs on it
 * is not a map, it is a texture - and the collision engine would answer the
 * question "which of these do I keep" by geometry, when the honest answer at
 * that zoom is "none, you are not looking at a place yet".
 *
 * **12 is measured, not argued** (#593, landed 2026-08-13).
 * `pipeline/spike_poi_seam.py` simulates MapLibre's placement over the
 * site-folded corridor at z10-z17 and reports viewport load centred on a
 * waypoint: a median of 35 pins wanted at z10, 18 at z11, **9 at z12** on a
 * 390x700 screen that holds about 16. z12 is the first zoom that is not
 * oversubscribed. It replaced a z12-z13 bracket this file had reached by
 * arithmetic, and 9 before that.
 *
 * Chosen on the median rather than the p90 deliberately, and the dot rank is
 * what makes that affordable: above the seam an overfull screen costs dots
 * rather than deletions, so the question is "is the usual screen readable"
 * rather than "is every screen guaranteed to fit".
 */
export const POI_PIN_MIN_ZOOM = 12

/**
 * The old name for {@link POI_PIN_MIN_ZOOM}.
 *
 * features/POI_VISIBILITY.md now says `POI_PIN_MIN_ZOOM` replaces this outright,
 * and the rename is deferred rather than skipped: #528 is in flight against
 * `map/drawnPois.ts` and `lib/useDrawnPoiCounts.ts`, both of which import the
 * old name, and renaming under a live branch on this file buys a conflict and
 * no behaviour. The alias carries the measured value, so nothing reading it is
 * wrong meanwhile - only old-fashioned. Delete it once #528 has landed.
 */
export const POI_MIN_ZOOM = POI_PIN_MIN_ZOOM

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
 * glyph is legible. One interpolation covers both without a second layer.
 *
 * **The lower stop is 0.75 rather than 0.6**, which is where "make the pins
 * slightly bigger" landed. The pin's full size cannot move: 38 px is
 * `--space-9`, and it sits in a deliberate three-mark ladder with the ATC's
 * notice dot at 40 (`--space-10`, the smallest step that clears a pin) and the
 * serious-warning pin at 44 (WIREFRAMES.md §8, one full touch target and the
 * biggest thing on the map). Raising 38 would push a maintainer's own notice
 * below OurHike's pin for the same shelter, which is the fault #591 spent
 * three commits fixing.
 *
 * What could move is where the ramp STARTS, and that is the half a hiker
 * actually sees - z9 to z12 is a quarter bigger, and it is the band anyone
 * looking at this map is in, because #603 means they had to zoom past the seam
 * to see a waypoint at all. `lib/atcUpdateStyle.ts` takes the same stops, in
 * the same commit, so the dot keeps its clearance at every zoom rather than
 * only at the top - src/test/atcAlertProminence.test.ts asserts that pairing.
 */
export const POI_ICON_SIZE_EXPRESSION: unknown[] = [
  'interpolate',
  ['linear'],
  ['zoom'],
  POI_PIN_MIN_ZOOM,
  0.75,
  13,
  1,
]

/**
 * A dot in its type's accent - the same accent its pin is drawn in, from the
 * same function, so the two ranks of one waypoint cannot disagree about colour.
 *
 * No confidence channel here, and that is deliberate rather than an omission.
 * A pin says "unconfirmed" on its rim (poiIcons.ts), which is a detail a 4 px
 * disc has nowhere to put; a dot's whole claim is "something is here", and at
 * this size that is the most it can honestly make. The rim is waiting at the
 * zoom the dot becomes a pin.
 */
export const POI_DOT_COLOR_EXPRESSION: unknown[] = [
  'match',
  ['get', 'poi_type'],
  ...POI_TYPES.flatMap((type) => [type, poiColor(type)]),
  poiColor(UNKNOWN_POI_TYPE),
]

/**
 * 3 px at the seam, 4 px by the zoom a hiker walks at.
 *
 * Small on purpose: a dot is a second rank, and one drawn large enough to
 * compete with a pin would take the pin's job while carrying none of its
 * information. features/POI_VISIBILITY.md holds the open question about the
 * exact size, which wants #105's real screen in real sun rather than a number
 * argued at a desk.
 */
export const POI_DOT_RADIUS_MAX_PX = 2

/**
 * The dot at its largest, as a diameter.
 *
 * Derived from the radius above rather than written down, because poiTaps.ts
 * sizes the dot's hit area from it and a second number to keep in step is the
 * mistake this file has already watched POI_PIN_SIZE make once.
 */
export const POI_DOT_SIZE_PX = POI_DOT_RADIUS_MAX_PX * 2

export const POI_DOT_RADIUS_EXPRESSION: unknown[] = [
  'interpolate',
  ['linear'],
  ['zoom'],
  POI_PIN_MIN_ZOOM,
  POI_DOT_RADIUS_MAX_PX * 0.75,
  13,
  POI_DOT_RADIUS_MAX_PX,
]

/**
 * The dot rank: every waypoint in the source, at every camera above the seam.
 *
 * A `circle` layer and not a smaller symbol layer, and that is the entire
 * mechanism rather than a styling preference. MapLibre's collision engine
 * places SYMBOLS; a circle takes no part in it, so there is no box to lose and
 * no ordering to lose it to. See this file's header.
 */
export function buildPoiDotLayer(sourceId: string = POI_SOURCE_ID): LayerSpecification {
  return {
    id: POI_DOT_LAYER_ID,
    type: 'circle',
    source: sourceId,
    minzoom: POI_PIN_MIN_ZOOM,
    paint: {
      'circle-color': POI_DOT_COLOR_EXPRESSION as unknown as string,
      'circle-radius': POI_DOT_RADIUS_EXPRESSION as unknown as number,
      // A hairline of paper around each dot, for the same reason the pins
      // carry PIN_HALO_COLOR: two dots 40 m apart at z11 are touching, and
      // without a break between them they read as one larger smudge.
      'circle-stroke-color': PIN_HALO_COLOR,
      'circle-stroke-width': 0.5,
    },
  }
}

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
 * Both, and it is written as one loop over a list rather than two calls,
 * because "hiding a type leaves its dots on the map" is exactly the half-done
 * shipment #597 warned about. One expression, applied everywhere the source is
 * drawn, is the shape that cannot be half-applied.
 */
export const POI_FILTERED_LAYER_IDS: readonly string[] = [POI_DOT_LAYER_ID, POI_LAYER_ID]

export function attachPoiFilter(
  map: MapLibreMap,
  hiddenTypes: ReadonlySet<string>,
  verifiedOnly = false,
): () => void {
  return whenStyleReady(
    map,
    // setFilter throws outright on a layer the style does not hold, so the
    // layers' presence is exactly the precondition. Both are added by the same
    // buildMapStyle call, so this is one question rather than two.
    () => POI_FILTERED_LAYER_IDS.every((id) => map.getLayer(id) !== undefined),
    () => {
      const filter = poiFilter(hiddenTypes, verifiedOnly)
      for (const id of POI_FILTERED_LAYER_IDS) map.setFilter(id, filter as never)
    },
    'POI visibility',
  )
}
