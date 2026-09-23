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
  composeSites,
  SITE_MEMBERS_PROPERTY,
  siteMembersKey,
  type SiteVisibility,
} from './poiSites'
import { POI_PRIORITY } from './poiPriority'

import { poiIconImages } from './poiIconImages'
import {
  PIN_HALO_COLOR,
  POI_PIN_SIZE,
  poiColor,
  poiIconId,
  siteMemberCombinations,
  sitePinPadding,
  UNKNOWN_POI_TYPE,
  type PoiConfidence,
} from './poiIcons'
import { buildStalenessRingImage, STALENESS_RING_PIXEL_RATIO } from './stalenessRing'
import {
  RING_GONE_NEIGHBOURS,
  CROWDING_PROPERTY,
  POI_ICON_PADDING_EXPRESSION,
  QUIET_NEIGHBOURS,
  crowdingByPoi,
} from './poiCrowding'
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
 * The waypoint's name, carried on the feature so a label layer can draw it
 * (#1194).
 *
 * It was deliberately absent until now, and {@link buildPoiLayer}'s own note
 * said why: "Names are not here because nothing draws them." That stopped
 * being true when the day-hike builder needed to answer "which shelter is
 * that" without a tap. What has NOT changed is that the pin layer still draws
 * no text - see map/poiLabels.ts for the separate layer that does, and for
 * why it is separate.
 */
export const POI_NAME_PROPERTY = 'poi_name'

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
export const POI_PIN_MIN_ZOOM = 7

// IT IS 7.5 SINCE 2026-09-18 (#1585), AND THE DOCSTRING ABOVE IS KEPT WHOLE
// BECAUSE ITS ARGUMENT IS STILL THE ONE THAT DECIDES THIS NUMBER - the seam is
// the widest view that is still about a walk rather than about a region. What
// changed is which walk. A day is 16-24 miles and z9 fits it doubled; a
// thru-hiker plans one RESUPPLY at a time, five or six days at twenty miles,
// and that is 100-120 trail miles.
//
// MEASURED 2026-09-17 on the calibrated mile axis the app's own mile numbers
// come from (pipeline/export_elevation.py's calibrated_trail_axis, ATC's
// centerline and half-mile markers): every window of 100, 110 and 120 trail
// miles from Springer to Katahdin, stepped every two miles, fitted the way
// App.tsx fits a stretch (fitBounds into a 390x700 map, FIT_PADDING 24).
//
//     window   phone fit zoom p10 / median / p90   straight-line span, median
//     100 mi   7.82 / 8.39 / 8.95                  54 mi
//     110 mi   7.73 / 8.26 / 8.77                  59 mi
//     120 mi   7.61 / 8.14 / 8.59                  65 mi
//
// The median carry fits at z8.1-8.4 and fewer than one window in ten fits at
// z9, so z9 was a seam a section hiker could never see their section from.
// (On a desktop the map tab frames the same section at z9.6 and needed
// nothing; this is a phone answer.)
//
// 7.5 RATHER THAN THE MEDIAN 8, on the maintainer's pick of 2026-09-18 from
// three drawn options: nine in ten 120-mile windows fit at z7.61 or nearer, so
// 7.5 is the floor at which essentially EVERY carry fits rather than half of
// them. The cost was drawn beside it and taken knowingly - a z7.5 screen is
// 80 x 144 miles and holds a median 64 waypoints against room for about 26
// pins, so a smaller share of them wear one and the rest are dots. Which is
// exactly what the dot rank is for, and why the floor could move at all.
//
// THE PIN'S SIZE DID NOT MOVE WITH IT, also the maintainer's pick from the
// same three options: POI_PIN_MIN_SCALE stays 0.8, the value #617 measured as
// the difference between a mark you can identify and one you can only locate.
// A 0.6 ramp was drawn and offered - it fits about a quarter more pins - and
// was not taken.
//
// IT IS 7 SINCE 2026-09-20, AND THE SEAM IS A SEAM AGAIN. The maintainer,
// having seen the z7.8 carry frames drawn from the live preview: "We can keep
// a seam, and make it at zoom 7. Yes the POI's can be hidden above there" -
// above meaning further out, which they confirmed against two drawn frames
// before any of this was written. So below z7 the map carries no waypoints at
// all, and 7 rather than 7.5 is their number rather than a derivation: the
// measured table above says nine in ten 120-mile windows fit at z7.61 or
// nearer, so 7 clears every carry with room to spare.
//
// WHAT THE SEAM STILL NEVER DECIDES IS *WHICH*, and the first attempt at
// #1585 got exactly that wrong: it put a type gate below the seam - shelters,
// water and towns only - and a hiker at z8 saw no campsite, no privy, no
// parking and no crossing, with nothing on the screen to say they existed.
// The maintainer's rule of 2026-09-18 stands unchanged over the top of the
// new seam: "Don't auto hide the POIs ever. It's a safety thing, hikers need
// to know that info." So from z7 up, every category the hiker has switched on
// is drawn, and {@link poiFilter} carries no zoom term at all.
// poiLayers.test.ts's "the map never hides a category of its own accord"
// block is that rule, pinned, and it now runs at every zoom from the seam up.
//
// AND THE HIKER CAN SEE THE SEAM WORKING, which is what makes it a seam
// rather than a silence: the legend's Showing picker runs from "All types"
// down to "None", and that gate turns itself on the first time a hiker
// crosses z7 inward in a given map view, never again overriding a state they
// chose themselves (lib/showPoints.ts). It floated over the map as a "Show
// points" pill for one day before the maintainer moved it into the picker.

/**
 * The closest one tap of the map's locate button brings the camera from
 * below the seam (#1581).
 *
 * The seam itself, so "where am I" from the corridor view lands on the
 * closest view that also shows what is around the hiker. Derived rather than
 * chosen, which is why it is this constant and not a number - and the same
 * cap the old GeolocateControl carried as its `fitBoundsOptions.maxZoom`
 * (#315). From above the seam the camera keeps the zoom it has, the way
 * App.tsx's handleBackToMe already leaves it alone: locate is a claim about
 * where the map is centred, not about how far in the hiker wanted to be.
 *
 * HERE, AND NOT BESIDE THE BUTTON. App.tsx reads it, and map/mapChrome.ts
 * imports maplibre-gl - a shell import reaching the engine statically puts
 * a megabyte of MapLibre into the eager chunk (map/mapEngineLoader.ts,
 * #1300), which scripts/check-build-output.mjs caught on this constant's
 * first draft. A second draft in map/positionLayers.ts kept the engine out
 * and pulled the mark's rasteriser in instead, for 626 bytes of headroom
 * under features/LAUNCH_BUDGET.md's 256,000. This module is already in the
 * eager chunk for POI_PIN_MIN_ZOOM's sake, so a constant here costs it
 * nothing.
 */
export const LOCATE_MIN_ZOOM = 9

// 9 IS NOW ITS OWN NUMBER, AND THAT IS THE CHANGE (#1585). It was
// POI_PIN_MIN_ZOOM, on the reasoning above: "the closest view that also shows
// what is around the hiker". That reasoning held while the seam was the zoom a
// DAY fits. The seam is a planning number now - the zoom a five-day resupply
// carry fits, 80 x 144 miles of ground - and "where am I" is not a planning
// question. Following it would have answered a hiker's tap with a screen a
// hundred and forty miles tall.
//
// So this keeps the value it has always had, for the reason it always had it:
// 28 x 51 miles is a day's ground with the waypoints around it, which is what
// somebody asking where they are wants to see. It is a camera choice and never
// a filter - every waypoint is drawn at every zoom either way.

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
 * The categories drawn at full size, and it is POI_PRIORITY's own top rather
 * than a second opinion about what matters (#1585).
 *
 * That list is already the repository's argued ordering of what a hiker
 * reaches for - water and a roof first, then the ways off the trail, with the
 * privies, fords and overlooks behind them - and it carries the reasoning at
 * each step. Taking the size tiers from it means there is one ordering here
 * rather than two that can disagree, and the boundary falls where its own
 * comments stop talking about getting somebody off a mountain.
 *
 * The maintainer, 2026-09-18: "the warnings needs to stay large as well as
 * the other important classes." The warning pin was already exempt from all
 * of this - map/warningLayers.ts draws it at one size at every zoom and
 * never lets it be culled - so this is the same rule reaching the waypoints
 * that sit beside it.
 */
export const FULL_SIZE_POI_TYPES: readonly string[] = POI_PRIORITY.slice(
  0,
  POI_PRIORITY.indexOf('privy'),
)

/**
 * What the rest are drawn at, as a fraction of a full-size pin.
 *
 * NOT A WAY OF HIDING THEM, and the difference is the whole point: a vista at
 * 0.72 is 27 px carrying a 13 px glyph, which is a mark a hiker can see, name
 * and tap. It is smaller than a spring because a spring is the one somebody
 * is looking for when the weather turns, and with nothing culled any more
 * size is the only channel left that can say so.
 *
 * @unvalidated 0.72 is picked. It is the largest fraction at which a
 * viewpoint reads as secondary to a water pin beside it on this screen, by
 * eye in a browser, and nobody has looked at the pair on a phone in sunlight
 * - the outdoor pass #105 closed without giving these two marks a side-by-side.
 * What would settle it: which of the two a hiker reaches for first when both
 * are under the thumb.
 */
export const SECONDARY_POI_SCALE = 0.72

/** A pin's size at one zoom stop: full for the categories above, reduced for
 *  the tail. `icon-size` is data-driven, and a zoom `interpolate` may carry a
 *  data expression in each OUTPUT but never in its input - so the tier goes
 *  here, per stop, rather than multiplying the ramp from outside. */
function sizeAtStop(base: number): unknown[] {
  return [
    'match',
    ['get', 'poi_type'],
    [...FULL_SIZE_POI_TYPES],
    base,
    base * SECONDARY_POI_SCALE,
  ]
}

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
  sizeAtStop(POI_PIN_MIN_SCALE),
  13,
  sizeAtStop(1),
]

/**
 * The stale fade, on the pin itself (lib/stalenessDisplay.ts's `opacity:
 * 0.5` for the stale tier, applied where the pin is actually drawn). Every
 * other state - fresh, ageing, never - draws at full strength; the ring
 * layer below carries the rest of the treatment.
 */
export const POI_ICON_OPACITY_EXPRESSION: unknown[] = [
  'case',
  ['==', ['get', 'staleness_faded'], true],
  0.5,
  1,
]

export function buildPoiLayer(sourceId: string = POI_SOURCE_ID): LayerSpecification {
  return {
    id: POI_LAYER_ID,
    type: 'symbol',
    source: sourceId,
    minzoom: POI_PIN_MIN_ZOOM,
    paint: {
      'icon-opacity': POI_ICON_OPACITY_EXPRESSION as unknown as number,
    },
    layout: {
      'icon-image': POI_ICON_EXPRESSION as unknown as string,
      'icon-size': POI_ICON_SIZE_EXPRESSION as unknown as number,
      'symbol-sort-key': POI_SORT_KEY_EXPRESSION as unknown as number,
      // NOTHING IS EVER CULLED (#1585, 2026-09-18). This was `false` - the
      // spec default, left explicit because it was "the entire density
      // story" - and the story it told was that MapLibre dropped every pin
      // that would have overlapped one already placed. Measured against the
      // identity ledger that day: at z9, 59% of the waypoints reaching this
      // layer were dropped; at the seam, 81%. They kept a 2.5 px dot, which
      // is what the two ranks bought (#597), and a dot is not the pin a
      // hiker scans for.
      //
      // The maintainer, 2026-09-18: "never hide anything!!!!!!! ... we had
      // worked so hard to get the small pins to show. always show the pins."
      //
      // features/POI_VISIBILITY.md had already written the release note for
      // this line: "a setting that only governs legibility can be revisited
      // ... without anything true or false hanging on it". This is that
      // revision. What replaces culling as the density answer is SIZE -
      // POI_ICON_SIZE_EXPRESSION draws the categories a hiker's day depends
      // on at full size and the tail smaller - and the honest cost is stated
      // where it belongs, in that doc: at planning zooms this is a dense
      // screen, and at the zooms somebody walks at it is four to ten marks.
      'icon-allow-overlap': true,
      // AND IT EVICTS NOTHING EITHER. With overlap allowed, a pin that still
      // took part in placement would be drawn and would go on displacing the
      // symbols around it - the trail names, the waypoint labels, the trail
      // badges - so "hide nothing" would have held for pins by taking the
      // names off the map instead. Ignoring placement is what makes this
      // layer neither hidden nor hiding.
      'icon-ignore-placement': true,
      // Padding is inert while nothing collides (#1585) and is kept rather
      // than deleted, because what it encodes is a measurement - how crowded
      // the ground under each waypoint is (#1536, map/poiCrowding.ts) - and
      // the staleness ring still reads that same property to fade itself on
      // crowded ground. A future change that reinstates any placement pass
      // finds the air it needs already computed.
      // THE JIGGER (2026-09-20). The maintainer put the trail line over the
      // waypoints - "The Trail line should sit over the POI's" - and asked
      // what stops the line swallowing a pin that sits on it: "If that would
      // hide the POI, maybe we should jigger." They chose the pin stepping
      // aside over a translucent line or a plain swap, from three drawn
      // frames.
      //
      // ANCHORED RATHER THAN OFFSET, and that is what keeps this honest. An
      // `icon-offset` would draw the pin somewhere the place is not, which is
      // the thing map/poiSites.ts refuses in as many words: "drawing a privy
      // 80 px from where it is, is the same refusal" as drawing a stale GPS
      // fix like a live one. `icon-anchor: 'bottom'` moves no coordinate - it
      // says which part of the artwork lands ON the coordinate, and the part
      // that lands on it is the pin's bottom edge. The place is still exactly
      // where the pin touches down.
      //
      // WHAT IT BUYS: the trail line is at most CASING_LINE_WIDTH wide - 6.5
      // px, so 3.25 either side of a centreline running through the point -
      // and the pin body is now entirely above that, whatever the zoom,
      // because the anchor scales with the icon rather than being a constant
      // in pixels.
      //
      // `@unvalidated` on the READING, not on the arithmetic: nobody has
      // looked at a bottom-anchored circular pin on a phone, and a circle
      // with no stem sitting above its point may read as floating rather than
      // as marking. What would settle it is one look at the carry and walking
      // zooms on a real screen - the preview recipe
      // client/preview-shots/waypoints-at-the-carry-zoom.mjs points the
      // camera at exactly that, which is why it exists. If it reads as
      // floating, the fix is a stem on the artwork rather than a different
      // anchor.
      'icon-anchor': 'bottom',
      'icon-padding': POI_ICON_PADDING_EXPRESSION as unknown as number,
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
 * The staleness ring: DATA_NUDGES.md's passive prominence, drawn (#759).
 *
 * A `circle` layer under the pins, for exactly the reason the dot rank is
 * one: circles join no collision pass, so a ring can never cost a
 * neighbouring pin its placement. It reads the same source as both other
 * ranks and takes the same legend filter, so a hidden category's rings go
 * with its pins.
 *
 * WHICH RING A WAYPOINT WEARS IS NOT DECIDED HERE. lib/stalenessDisplay.ts
 * owns the whole policy - the tier treatments, and the maintainer's
 * day-one decision (2026-08-20, #256) that never-confirmed water alone
 * carries a faint invite while everything else unconfirmed stays neutral.
 * The shell precomputes `staleness_ring` and `staleness_faded` per feature
 * through that module ({@link poiFeatureCollection}), and this layer just
 * draws what the property says: policy in one home, paint in another.
 */
export const POI_STALENESS_LAYER_ID = 'poi-staleness-rings'

/** No ring - the property value that filters a feature out of the ring
 *  layer entirely. Ageing and never-confirmed both land here on purpose:
 *  the absence IS the middle state (stalenessDisplay.ts). */
export const NO_RING = 'none'

// The ring colours, one per stalenessDisplay ring name. Green reads as
// "somebody said fine, recently" against every sheet; the stale grey is the
// treatment's fade taken to the rim; the invite is water's own accent worn
// faintly, so the nudge points at the category it is about.
const RING_COLORS: Record<string, string> = {
  green: '#2e7d32',
  'grey-dotted': '#757575',
  'faint-invite': poiColor('water'),
}

const RING_OPACITIES: Record<string, number> = {
  green: 0.9,
  'grey-dotted': 0.55,
  // Subtle is the decision, not a compromise: on day one this is most of
  // the water on the map, and a loud ring on all of it would be the
  // "nothing here is trustworthy" opening #256 warns about, one channel
  // over.
  'faint-invite': 0.35,
}

/** The image id the ring layer asks for, one per ring colour. */
export function stalenessRingImageId(ring: string): string {
  return `poi-staleness-ring-${ring}`
}

/** Every ring image the layer can ask for, for {@link attachPoiIcons}. */
export function stalenessRingImages(): Array<{
  id: string
  image: ReturnType<typeof buildStalenessRingImage>
  pixelRatio: number
}> {
  return Object.entries(RING_COLORS).map(([ring, color]) => ({
    id: stalenessRingImageId(ring),
    image: buildStalenessRingImage(color),
    pixelRatio: STALENESS_RING_PIXEL_RATIO,
  }))
}

/**
 * How far above its coordinate a waypoint's pin disc is centred, in CSS px at
 * icon-size 1 - what the ring is lifted by so it goes round the pin rather
 * than through it (map/stalenessRing.ts has the history).
 *
 * The pin is bottom-anchored (the jigger, in {@link buildPoiLayer}), so its
 * disc centre sits half its image's height above the coordinate. That image
 * is the 38 px pin plus, for a site pin, `sitePinPadding` on every side for
 * its badges - so a site pin's disc is lifted by that padding too.
 */
export const RING_LIFT_PROPERTY = 'ring_lift'

export function ringLift(memberCount: number): number {
  return POI_PIN_SIZE / 2 + sitePinPadding(memberCount)
}

/** Member counts up to this get an exact lift; past it (no site carries
 *  this many today - siteMemberCombinations) the ring falls back to the
 *  largest. */
const MAX_LIFTED_MEMBERS = 8

/**
 * `icon-offset` per lift. A `match` over the handful of values
 * {@link ringLift} can produce, because an expression cannot build an array
 * from a number - each output is a literal pair. Multiplied by `icon-size`
 * by MapLibre, so the lift scales with the pin it is measured from.
 */
const RING_OFFSET_EXPRESSION: unknown[] = (() => {
  const lifts = [
    ...new Set(Array.from({ length: MAX_LIFTED_MEMBERS + 1 }, (_, n) => ringLift(n))),
  ]
  return [
    'match',
    ['get', RING_LIFT_PROPERTY],
    ...lifts.flatMap((lift) => [lift, ['literal', [0, -lift]]]),
    ['literal', [0, -Math.max(...lifts)]],
  ]
})()

/**
 * The ring fades out on ground too crowded for it to be telling the truth
 * (#1536).
 *
 * THE LAYER ALREADY STATED THIS RULE AND ONLY HALF-KEPT IT. Its own comment
 * reads "rings exist to invite a tap, and only a pin can be tapped - so they
 * start where the pins do, not where the dots do", and the `minzoom` below is
 * the zoom half of that. The other half - WHICH waypoints - was never
 * enforceable, because a circle layer joins no placement pass and cannot ask
 * MapLibre which symbols won. On the corridor that never showed: almost every
 * waypoint above the seam IS a pin, so ringing them all was very nearly
 * ringing the pins.
 *
 * New York City is where it shows. Photographed from the preview on
 * 2026-09-17 (client/preview-shots/city-waypoints-crowded.mjs), the z12 frame
 * over Brooklyn holds 660 waypoints and draws 24 pins - and all 660 wore a
 * 42 px ring. Every New York fountain is unconfirmed, so every one of them
 * takes the `faint-invite`, and the result is the exact failure
 * {@link RING_OPACITIES} is written to avoid: "a loud ring on all of it would
 * be the 'nothing here is trustworthy' opening #256 warns about". Subtle per
 * ring is not subtle six hundred times over.
 *
 * So the ring rides the same measurement the pins do, and the two stay in
 * step by construction: full strength where a waypoint is drawn as a pin, out
 * by the count at which the ground is crowded enough that it is almost
 * certainly a dot. A ramp rather than a switch, because that is what passive
 * prominence means and because a cliff would put a hard edge across a park.
 *
 * WHAT IT COSTS, and it is a real cost rather than a free win: a pin that IS
 * drawn on crowded ground loses its invitation to confirm along with its
 * neighbours' - the property cannot tell them apart. That is accepted against
 * six hundred rings nobody can read. If MapLibre ever exposes placement
 * results per feature, this is the expression that should be replaced by the
 * real question.
 */
const RING_CROWDING_FADE: unknown[] = [
  'interpolate',
  ['linear'],
  ['coalesce', ['get', CROWDING_PROPERTY], QUIET_NEIGHBOURS],
  QUIET_NEIGHBOURS,
  1,
  // RING_GONE_NEIGHBOURS rather than CROWDED_NEIGHBOURS since 2026-09-20:
  // the padding ramp and this one answer different questions, and reusing
  // one number for both left the median New York City mark drawing three
  // quarters of a ring it shared with hundreds of others. See that
  // constant's docstring for the frame this was measured on.
  RING_GONE_NEIGHBOURS,
  0,
]

export function buildPoiStalenessLayer(
  sourceId: string = POI_SOURCE_ID,
): LayerSpecification {
  return {
    id: POI_STALENESS_LAYER_ID,
    type: 'symbol',
    source: sourceId,
    // Rings exist to invite a tap, and only a pin can be tapped - so they
    // start where the pins do, not where the dots do. See
    // RING_CROWDING_FADE above for the half of that rule this `minzoom`
    // cannot express.
    minzoom: POI_PIN_MIN_ZOOM,
    filter: ['!=', ['get', 'staleness_ring'], NO_RING] as never,
    layout: {
      // The ring is a rim, not a disc: the image is transparent inside it, so
      // the map underneath stays readable.
      'icon-image': [
        'match',
        ['get', 'staleness_ring'],
        ...Object.keys(RING_COLORS).flatMap((ring) => [ring, stalenessRingImageId(ring)]),
        stalenessRingImageId('green'),
      ] as unknown as string,
      // THE PIN'S OWN SIZE AND THE PIN'S OWN LIFT, so the ring goes round the
      // pin at every zoom and for every tier - see map/stalenessRing.ts for
      // why this stopped being a circle layer.
      'icon-size': POI_ICON_SIZE_EXPRESSION as unknown as number,
      'icon-offset': RING_OFFSET_EXPRESSION as unknown as [number, number],
      // A ring is never culled and culls nothing, for the pins' own reasons
      // (#1585): it is part of the pin it surrounds.
      'icon-allow-overlap': true,
      'icon-ignore-placement': true,
    },
    paint: {
      // The ring's own opacity, scaled by how crowded its ground is. A
      // product rather than a second `match`, so the per-tier values above
      // stay the one home for "how loud is this tier" and this only ever
      // turns them down.
      'icon-opacity': [
        '*',
        ['match', ['get', 'staleness_ring'], ...Object.entries(RING_OPACITIES).flat(), 0],
        RING_CROWDING_FADE,
      ] as unknown as number,
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
 * How far down the dot rank goes: all the way, again (#1585, 2026-09-18).
 *
 * THIS IS #603's FLOOR, REINSTATED, AND THE OBJECTION THAT REMOVED IT IS
 * ANSWERED RATHER THAN OVERRULED. #1135 took the stipple off because #1097 had
 * joined 8,480 network waypoints to this source while their trails' lines drew
 * only from the seam up - so the dots had quietly become "mostly places on
 * trails the view refuses to draw". That is no longer true of this view: #1135
 * itself put every organization's trails on the corridor camera as the 255 KB
 * overview sketch (pipeline/export_nearby_trails.py's write_overview), so a
 * network waypoint down here now sits on a line the map is drawing.
 *
 * IT IS THE SEAM AGAIN SINCE 2026-09-20, which is the fourth position this
 * floor has held and the second time it has landed here. The maintainer, shown
 * the z7.8 carry frames off the live preview: "We can keep a seam, and make it
 * at zoom 7. Yes the POI's can be hidden above there." So the corridor view
 * carries no waypoint marks of any kind again, in either rank.
 *
 * THIS IS NOT THE 2026-09-18 RULE BEING WOUND BACK, and the distinction is the
 * whole of why both can stand. That rule - "Don't auto hide the POIs ever.
 * It's a safety thing, hikers need to know that info" - is about the map
 * choosing WHICH categories a hiker may see, and it is untouched: from the
 * seam up every category draws, {@link poiFilter} carries no zoom term, and
 * poiLayers.test.ts's "the map never hides a category of its own accord"
 * block still runs at every zoom the marks exist at. What the maintainer
 * reversed is the CAMERA half - whether a continental view is a waypoint map
 * at all - and they reversed it having seen what it drew, which is the
 * strongest evidence any of these four positions has had.
 *
 * And the hiker is told, rather than left to wonder: below the seam the
 * legend says so in a sentence of its own - "Waypoints appear from a closer
 * zoom." - so the absence down here reads as a state rather than as a map
 * with nothing on it.
 *
 * The record of what it replaced, kept because the third reversal is only
 * defensible against the first two: how far down the dot rank went from
 * 2026-08-27 to 2026-09-18 - to the seam, with the pins (#1135).
 *
 * It was 0 from #603 to 2026-08-27, and the maintainer reversed that
 * below-seam half deliberately: *"The opening map probably just needs to be
 * all the trails that we have mapped. Not including the POIs."* Two things
 * had changed since #603 put a stipple on the corridor view to answer an
 * empty screen:
 *
 *  - The subject #603 was standing in for exists now. The corridor view
 *    carries the thirty club sections (#594) and the named highlights (#595),
 *    and with #1135 it carries every organization's trails - so "the trail
 *    line and nothing else", the emptiness the stipple was the answer to, is
 *    not what removing it restores.
 *  - #1097 joined 8,480 network waypoints to this source, and their trails'
 *    lines draw only from the seam up. Below it the stipple stopped being
 *    "every waypoint on the trail you see" and became mostly places on
 *    trails the view refuses to draw - a texture that had quietly started
 *    lying about where the trails are.
 *
 * WHAT IS NOT REOPENED: everything from the seam up. "A pin or a dot and
 *  never as neither" stands untouched - this floor moves, the rank's whole
 * argument does not. And the 1.2 px corridor stipple this retires carried its
 * own @unvalidated: nobody ever looked at it on a phone in sunlight.
 *
 * The same constant as the pins' rather than a second number that happens to
 * agree, so the corridor view has ONE seam for waypoints again - which is
 * what lets features/POI_VISIBILITY.md's "below the seam the map is a
 * complete map of something else" read unqualified once more.
 */
export const POI_DOT_MIN_ZOOM = POI_PIN_MIN_ZOOM

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
 * THE 1.2 px CORRIDOR STOP IS GONE AGAIN (2026-09-20), because the band it
 * sized no longer exists: both ranks floor at the seam, so there is no zoom
 * below it at which a dot is drawn and needs a size. Two stops at one zoom is
 * not a harmless leftover either - MapLibre requires an interpolate's stops to
 * ascend strictly, and leaving it would have been a style the engine refuses
 * rather than a number nobody reads.
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
      /** The waypoint's name, for map/poiLabels.ts. See {@link POI_NAME_PROPERTY}. */
      [POI_NAME_PROPERTY]: string
      [POI_ID_PROPERTY]: string
      [SITE_MEMBERS_PROPERTY]: string
      staleness_ring: string
      staleness_faded: boolean
      /** How many other drawn marks sit within map/poiCrowding.ts's radius -
       *  what `icon-padding` interpolates on (#1536). */
      [CROWDING_PROPERTY]: number
      /** How far above the coordinate the pin's disc is centred - what the
       *  staleness ring is lifted by. See {@link RING_LIFT_PROPERTY}. */
      [RING_LIFT_PROPERTY]: number
    }
  }>
}

/**
 * Which ring a waypoint wears and whether its pin fades - precomputed by the
 * shell through lib/stalenessDisplay.ts, which owns the policy. The default
 * is the day-one truth for a build with no notes at all: no ring, no fade.
 */
export type PinCondition = { ring: string; faded: boolean }

const NO_CONDITION: PinCondition = { ring: NO_RING, faded: false }

/**
 * Carries what the style reads - the two attributes the expressions above
 * match on - and the id to find the rest by, which rides in the properties for
 * the reason {@link POI_ID_PROPERTY} gives. Names are not here because nothing
 * draws them - see the note about `glyphs` in {@link buildPoiLayer}.
 */
export function poiFeatureCollection(
  pois: readonly MapPoint[],
  visibility: SiteVisibility = {},
  pinCondition: (poiId: string, poiType: string) => PinCondition = () => NO_CONDITION,
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
  //
  // The staleness pair rides the same rebuild: notes arrive at most hourly
  // (lib/useConditions.ts) plus once per submitted confirmation, so the
  // rebuild cadence is the legend tap's plus that - the same cost, paid a
  // little more often, for the map's only freshness channel. A site anchor
  // wears ITS OWN notes' condition; a folded member's notes reach the card
  // (per-part reads) but not the shared pin, which is a known simplification
  // rather than a rule.
  // THE FOLD IS BACK (2026-09-20). It was removed on 2026-09-18 under "never
  // hide anything", and the maintainer put it back in as many words: "The
  // grouping of locations was working before. You need to nest the Shelters,
  // Campsites, Privies & Water as we did before this PR."
  //
  // What the unfolded build actually drew is why: four pins stacked on one
  // shelter - the shelter, its privy, its water and its campsite, a median
  // 42 m apart and therefore on top of each other at every zoom a hiker
  // walks at. Measured against the identity ledger, 2026-09-18: the fold
  // removes 634 of 1,387 marks, which unfolded is 634 pins piled on the 753
  // that anchor them.
  //
  // AND IT IS NOT THE CULLING COMING BACK WITH IT, which is the distinction
  // that lets this sit beside the 2026-09-18 rule rather than against it.
  // `icon-allow-overlap` stays `true`: nothing is dropped by the collision
  // engine, and nothing is dropped for being the loser of anything. A folded
  // member is not deleted - it rides its anchor's pin as a badge, it is
  // listed on the card behind that pin, and the hiker steps between the
  // parts from there. The one mechanism that removed a place with no way
  // back is still gone.
  //
  // WHICH IS WHY `visibility` IS READ AGAIN (#607): the removal is only safe
  // while the pin that replaces the member is on the map, so a site whose
  // anchor the legend hid falls back to its highest-priority drawn member,
  // and goes dark only when the hiker has hidden every part of it.
  const { drawn, membersFor } = composeSites(pois, visibility)

  // AFTER the fold, and that is the point of where this sits: what competes
  // for a pin is the drawn mark, so a shelter riding one pin with its privy
  // and two campsites is one neighbour to the marks around it rather than
  // four. Counting before folding would report ground as crowded that the
  // fold had already uncrowded, and buy air nobody needed.
  const crowding = crowdingByPoi(drawn)

  return {
    type: 'FeatureCollection',
    features: drawn.map((poi) => {
      const condition = pinCondition(poi.id, poi.type)
      return {
        type: 'Feature',
        id: poi.id,
        geometry: { type: 'Point', coordinates: [poi.lon, poi.lat] },
        properties: {
          poi_type: poi.type,
          confidence: poi.confidence,
          // Always a string, empty where the caller had none, so the label
          // layer's filter is one comparison rather than a `coalesce` - the
          // same always-present rule SITE_MEMBERS_PROPERTY follows below.
          [POI_NAME_PROPERTY]: poi.name ?? '',
          [POI_ID_PROPERTY]: poi.id,
          // Always present, empty where the pin carries nothing, so the style's
          // `match` needs no `coalesce` and a pin with no site is not a separate
          // expression path that could drift from the one with.
          [SITE_MEMBERS_PROPERTY]: siteMembersKey(membersFor.get(poi.id)),
          staleness_ring: condition.ring,
          staleness_faded: condition.faded,
          [CROWDING_PROPERTY]: crowding.get(poi.id) ?? 0,
          [RING_LIFT_PROPERTY]: ringLift(membersFor.get(poi.id)?.length ?? 0),
        },
      }
    }),
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

/**
 * Registers every pin image on a live map, and returns a detach function.
 *
 * TWO WAITS, NOT ONE, AND THE NEW ONE IS THE IMAGES THEMSELVES (#857). They
 * are rasterised off the main thread now (map/poiIconImages.ts), so they
 * arrive a beat after this is called rather than inside it - which is why the
 * style wait is set up in a `then` rather than returned directly. MapLibre
 * handles the late arrival: a tile that asked for an image it did not have is
 * re-laid out when one is added (`_updateTilesForChangedImages`), so a pin
 * whose artwork lands second is drawn rather than lost.
 *
 * The detach has to cover both waits, because either can be outstanding when
 * the map screen goes away: the images may still be building, or they may
 * have arrived and be waiting on a style that is mid tile fetch.
 */
export function attachPoiIcons(map: MapLibreMap): () => void {
  let detached = false
  let stopWaitingForStyle: (() => void) | null = null

  void poiIconImages().then((icons) => {
    if (detached) return

    stopWaitingForStyle = whenStyleReady(
      map,
      // The pin layer existing proves the style spec carrying it is parsed,
      // which is the condition addImage actually requires. There is no narrower
      // question to ask: an image is not addressable until it has been added.
      () => map.getLayer(POI_LAYER_ID) !== undefined,
      () => {
        for (const { id, image, pixelRatio } of [...icons, ...stalenessRingImages()]) {
          // Images outlive a style reload, and re-adding one throws.
          if (!map.hasImage(id)) map.addImage(id, image, { pixelRatio })
        }
      },
      'POI pin images',
    )
  })

  return () => {
    detached = true
    stopWaitingForStyle?.()
  }
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
  pinCondition?: (poiId: string, poiType: string) => PinCondition,
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

      source.setData(poiFeatureCollection(pois, visibility, pinCondition) as never)
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
  const layers = [POI_LAYER_ID, POI_DOT_LAYER_ID, POI_STALENESS_LAYER_ID]
  return whenStyleReady(
    map,
    // setFilter throws outright on a layer the style does not hold, so the
    // layers' presence is exactly the precondition. All three, because a
    // style mid-reload can hold some and not the rest.
    () => layers.every((layer) => map.getLayer(layer) !== undefined),
    () => {
      const filter = poiFilter(hiddenTypes, verifiedOnly)
      map.setFilter(POI_LAYER_ID, filter as never)
      map.setFilter(POI_DOT_LAYER_ID, filter as never)
      // The ring rank keeps its own membership clause AND takes the legend's:
      // a hidden category's rings must go with its pins, and a shown one must
      // still only ring what has a ring to wear.
      map.setFilter(POI_STALENESS_LAYER_ID, [
        'all',
        filter,
        ['!=', ['get', 'staleness_ring'], NO_RING],
      ] as never)
    },
    'POI visibility',
  )
}
