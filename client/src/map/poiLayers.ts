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
 * A DAY'S HIKE, AND THE GROUND EITHER SIDE OF IT, HAS TO FIT ON THE SCREEN.
 * That is the whole criterion. A day on the A.T. is 16-24 miles; a 390x700
 * phone map covers 50.9 miles of ground at z9 and 25.5 at z10. So z9 is the
 * tightest zoom that shows a hiker the day they are about to walk AND where
 * it sits, which is the moment this map is for.
 *
 * The doubling is the point rather than slack. z10 fits a 24-mile day edge to
 * edge and nothing else, so every question that starts "and then what" costs
 * a pan. z9 puts the day in the middle of as much ground again.
 *
 * MEASURED at that zoom rather than hoped for - pipeline/spike_poi_seam.py,
 * 2026-08-13, against the live ATC service with lib/poi_sites.py's own folding
 * applied. What reaches a PIN at z9: shelters 83%, privies 69%, campsites 59%,
 * parking 14%, viewpoints 2%. The things a day is planned around are mostly
 * pins; the vistas are almost entirely dots, which is the right way round and
 * is what the dot rank is for.
 *
 * IT WAS z12, THEN z10, BOTH ON THE SAME DAY, and both corrections are worth
 * recording because the arithmetic was never what was wrong.
 *
 * z12 came from asking "at what zoom does the screen stop being oversubscribed
 * with pins" - a pin-legibility test, when under two ranks an overfull screen
 * costs DOTS rather than deletions and legibility is a comfort question.
 *
 * z10 came from fixing that and then sizing the window to exactly one day,
 * which is a day with no context around it.
 *
 * It replaces a floor of 9 - the same number, reached from the opposite
 * direction. That floor's docstring argued that eight hundred POIs on a
 * corridor view "is not a map, it is a texture", and it was right about the
 * texture and wrong about what to do: it drew nothing rather than drawing the
 * texture honestly. The dot rank is that texture, labelled.
 */
export const POI_PIN_MIN_ZOOM = 9

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
 * How small a pin gets at the seam, as a fraction of {@link POI_PIN_SIZE}.
 *
 * 0.8, raised from 0.6 when the seam moved out to z9 (#617). A pin at 0.6 is
 * 22.8 px carrying a 10.6 px glyph; at 0.8 it is 30.4 px carrying 14.2 px,
 * which is the difference between a mark you can identify and one you can only
 * locate. `poiIcons.test.ts` holds a 7 px floor on a glyph and neither figure
 * is near it - this is about comfort at arm's length in sun, not about a
 * minimum.
 *
 * MEASURED, because bigger pins collide more and the fear was that raising it
 * would cost coverage. It barely does. At z9, per pipeline/spike_poi_seam.py:
 *
 *     scale   pin     shelter  privy  campsite
 *     0.6     22.8px  88%      74%    68%
 *     0.8     30.4px  83%      69%    59%
 *     1.0     38.0px  73%      60%    52%
 *
 * A third more pin costs shelters five points, because what actually binds at
 * z9 is the trail's own density rather than the box - and every waypoint that
 * loses becomes a dot rather than an absence, which is what makes spending the
 * coverage affordable at all.
 */
export const POI_PIN_MIN_SCALE = 0.8

/**
 * Pins grow with zoom rather than sitting at one size.
 *
 * At the far end of {@link POI_PIN_MIN_ZOOM} they are markers saying something
 * is there; by the zoom a hiker actually walks at they are full size and their
 * glyph is legible. One interpolation covers both.
 *
 * Both anchors are named constants rather than literals, because
 * spike_poi_seam.py models this exact ramp to compute the seam - a 0.6 left
 * behind here would silently make the measurement describe a different map
 * from the one that ships.
 */
export const POI_ICON_SIZE_EXPRESSION: unknown[] = [
  'interpolate',
  ['linear'],
  ['zoom'],
  POI_PIN_MIN_ZOOM,
  POI_PIN_MIN_SCALE,
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
 * How far down the dot rank goes - and it goes all the way (#603).
 *
 * The pin seam is a claim about legibility: below {@link POI_PIN_MIN_ZOOM} a
 * pin cannot say what it is without colliding with its neighbours. A DOT MAKES
 * NO SUCH CLAIM. It says something is here and nothing more, so the argument
 * that stops pins never applied to it, and stopping both at one seam meant the
 * opening view of the whole corridor - which lands near z4 on a phone - drew
 * the trail line and nothing else.
 *
 * This is features/POI_VISIBILITY.md's own open question ("whether the dot rank
 * should extend below the seam"), answered yes by the maintainer on #603.
 *
 * IT IS THE ANSWER THAT ADDS RATHER THAN REVERSES, which is why it is this one
 * and not a tighter opening camera. `App.tsx`'s CORRIDOR_BOUNDS argues that any
 * camera naming a place is "a confident-looking answer that is wrong for
 * everyone not standing" there, and `lib/cameraMemory.ts` argues that a camera
 * surviving the tab closing would restore "last Tuesday's view over Georgia to
 * someone starting in Maine". Both stand. The camera does not move here; what
 * changes is that there is now something on it.
 *
 * Zero rather than a floor near the opening view, because there is no zoom at
 * which "something is here" becomes false. The radius below carries the
 * honesty instead: at z4 these are 1.2 px, a stipple along the corridor rather
 * than a map of places.
 *
 * What it costs, stated rather than glossed: ~2,837 circles at z4. They are a
 * `circle` layer, so no collision pass and no per-feature layout - the cost is
 * one draw call's worth of geometry, not 2,837 decisions. And it softens
 * features/POI_VISIBILITY.md's "below the seam the map is a complete map of
 * something else" - the corridor view now carries a second thing. See
 * features/CORRIDOR_VIEW.md, which owns that view.
 */
export const POI_DOT_MIN_ZOOM = 0

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
 *
 * The corridor end of the ramp is 1.2 px at {@link POI_DOT_MIN_ZOOM}, and it is
 * doing the work the seam used to do (#603). At z4 the corridor's 2,837
 * waypoints sit within a few hundred pixels of trail line, so a dot sized for
 * the seam would draw a solid bar and claim the trail is one continuous place.
 * At 1.2 px they read as what they are - texture, denser where the places are.
 *
 * @unvalidated 1.2 px is picked, not measured. What would settle it is the same
 * outdoor pass #105 already owes the 2.5 px above: whether a corridor-view
 * stipple is legible in sunlight, or whether it wants 1.5 px and a lighter
 * halo. Nobody has looked at this on a phone.
 */
export const POI_DOT_RADIUS_EXPRESSION: unknown[] = [
  'interpolate',
  ['linear'],
  ['zoom'],
  POI_DOT_MIN_ZOOM,
  1.2,
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
 *
 * Its floor is {@link POI_DOT_MIN_ZOOM} and NOT the pin seam (#603). The two
 * ranks answer different questions, so they stop at different places - see
 * POI_DOT_MIN_ZOOM for why the seam was never the dot's to share.
 */
export function buildPoiDotLayer(sourceId: string = POI_SOURCE_ID): LayerSpecification {
  return {
    id: POI_DOT_LAYER_ID,
    type: 'circle',
    source: sourceId,
    minzoom: POI_DOT_MIN_ZOOM,
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
