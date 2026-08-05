// Builds the MapLibre style for the trail map.
//
// Two rules from WIREFRAMES.md's "Trail line rendering — blazes" are
// load-bearing rather than cosmetic:
//
//  1. ONE `match` expression drives line-color across every trail source, so a
//     source imported later inherits the rule instead of needing its own layer.
//     That expression lives in lib/blaze.ts and is imported, never re-spelled.
//
//  2. Every trail line is SOLID and one colour end to end. It used to be
//     dashed, on a per-blaze rhythm, and the rhythm was the map's second
//     hue-independent channel. What that actually produced on screen was a
//     line alternating between its blaze colour and the dark casing showing
//     through each gap - and on the AT centerline, whose blaze is very nearly
//     white, the gaps read as the line. A hiker looking for the trail they are
//     standing on found a dotted grey-and-white thread through the contours.
//     A solid line over a casing is the older, plainer cartographic answer and
//     it is legible at a glance, which is the property that matters most.
//
//     WIDTH carries the hue-independent channel instead, and carries more than
//     the rhythm did: a system's through-route is drawn markedly wider than the
//     side trails hanging off it, so the line the map is about is findable with
//     colour removed entirely - by glare, by greyscale (WIREFRAMES.md `9d`), or
//     by colour vision deficiency. Width is keyed off the pipeline's own
//     `source` attribute, in one data-driven expression, for the same reason
//     the colour is keyed off `blaze_color` in one expression.
//
//     Through-route is a role, not a name: today the AT holds it alone, so the
//     widest line on the map is the AT, but the map is not promised one
//     system (the NYNJTC maintains several). See PRIMARY_TRAIL_SOURCES for
//     what a second one costs this channel.
//
//     What this gives up is real and worth naming: yellow, orange and red side
//     trails were separable by rhythm and are now separable by hue alone, and
//     an undecoded blaze no longer reads as uncertain from its dotted rhythm.
//     Closures are unaffected - lib/closureStyle.ts keeps its barred band, and
//     with every blaze now solid that band is a stronger distinction than it
//     was, not a weaker one.
//
//  3. A side trail is never drawn over the through-route it hangs off. One
//     layer means one painter's order, and where two features share geometry
//     that order decides which colour a hiker sees - so it is decided here, by
//     `line-sort-key`, rather than by whichever feature the export wrote last.
//     See TRAIL_SORT_KEY_EXPRESSION.
//
// Not handled here: the POI pins, which are their own two modules -
// poiLayers.ts for the source, layer and density rules, poiIcons.ts for the
// pin images themselves. This file composes them in rather than spelling them
// out, for the same reason the blaze expression is imported: the rendering
// rule for a category should live in one place.
//
// Nor the background cartography, on the same principle - liveTopo.ts owns the
// hiking sheet's layers and terrain.ts the contour intervals. What this file
// does own is the ORDER, which is where the map's real guarantees live and the
// one thing no single module can enforce alone. Bottom to top: paper backdrop,
// downloaded archive, live sheet, trail, pins. Each step of that is load-
// bearing and commented at the layer it applies to.
//
// Not handled here either: blaze "Black" (code 8). WIREFRAMES.md's table describes it
// as "wide casing, no fill — drawn by absence," but the real data has zero
// Black features today and lib/blaze.ts has no colour for it, so it falls to
// the neutral-grey defensive fallback and logs a warning. Giving it a real
// treatment needs a design decision and at least one real feature to look at.

import type { StyleSpecification } from '@maplibre/maplibre-gl-style-spec'
import { BLAZE_MATCH_EXPRESSION } from '../lib/blaze'
import { buildPoiLayer, buildPoiSource, POI_SOURCE_ID } from './poiLayers'
import type { BackgroundSource } from '../lib/userPreferences'
import {
  BUNDLED_GLYPHS,
  LIVE_TOPO_ATTRIBUTION,
  liveTopoLayers,
  liveTopoSources,
} from './liveTopo'
import { ELEVATION_ATTRIBUTION, type ContourUnits, type TerrainUrls } from './terrain'

export const TOPO_SOURCE_ID = 'usgs-topo'
export const TRAILS_SOURCE_ID = 'trails'

export const BACKDROP_LAYER_ID = 'backdrop'
export const TOPO_LAYER_ID = 'topo'
export const TRAIL_CASING_LAYER_ID = 'trail-casing'
export const BLAZE_LAYER_ID = 'trail-blaze'

/**
 * What the map paints wherever it has no topo ink to paint.
 *
 * `--paper-100`, the same tone as USGS topo's own paper, so uncovered ground
 * belongs to the same map as the covered parts. Named rather than inlined
 * because poiIcons.ts and chrome.css's pre-WebGL fallback read it too: every
 * one of them has to agree on the same paper.
 *
 * Uncovered ground is not an edge case, and reaching it does not need the
 * pipeline's transparent-nodata tiles to be involved at all - the corridor
 * archive is a 30-mile strip, so panning off it, zooming out below the
 * archive's own minzoom, opening the app before the download finishes, or
 * simply moving faster than tiles decode each leave a hole too.
 */
export const MAP_BACKGROUND_COLOR = '#f7f3e9'

// ODbL requires a visible "© OpenStreetMap". WIREFRAMES.md's map-corner mockup
// shows the shorthand "© OSM", but its own Assets section states the full form
// is required - the abbreviation does not satisfy the licence, so the full
// form is what ships.
export const ATTRIBUTION = 'USGS US Topo · © OpenStreetMap contributors'

/**
 * What the corner has to say once the live background is on.
 *
 * Every clause is a licence or terms condition rather than a courtesy - ODbL
 * for the OSM data, OpenFreeMap's own terms for hosting it, and the AWS
 * Terrain Tiles attribution requirement for the elevation the hillshade and
 * contours are derived from. Composed from each module's own constant so a
 * source cannot be added in one file and go uncredited in another.
 */
export const LIVE_ATTRIBUTION = [
  ATTRIBUTION,
  LIVE_TOPO_ATTRIBUTION,
  ELEVATION_ATTRIBUTION,
].join(' · ')

export function attributionFor(background: BackgroundSource): string {
  return background === 'hiking_topo_live' ? LIVE_ATTRIBUTION : ATTRIBUTION
}

/** The pipeline's own key for ATC's trail-centerline feed (pipeline/sources.json). */
export const CENTERLINE_SOURCE = 'centerline'

/**
 * Trail sources drawn at the primary width: the through-route of a trail
 * system, as against the side trails and spurs hanging off it.
 *
 * This is a ROLE, and deliberately a list rather than a single source. Its one
 * member today is ATC's `centerline`, whose key reads like a proper noun
 * because that feed is the AT - but nothing here is promised only one
 * through-route. The NYNJTC alone maintains several trail systems, so a Long
 * Path or Highlands Trail import joins this tier beside the AT rather than
 * displacing it, and a `centerline` feed that itself grows past the AT needs
 * no change here at all.
 *
 * What that costs is named where the claim is made (WIREFRAMES.md §3): with
 * one through-route on the map, the widest line IS the AT. With two, width
 * answers "through-route or spur" and stops answering "which trail is this" -
 * still a hue-independent channel, but a coarser one.
 */
export const PRIMARY_TRAIL_SOURCES: readonly string[] = [CENTERLINE_SOURCE]

/** The two width tiers, in CSS pixels. */
export const PRIMARY_TRAIL_WIDTH = 4.5
export const SIDE_TRAIL_WIDTH = 2.5

/**
 * Line width in CSS pixels, per trail source.
 *
 * A through-route is the subject of this map and everything else is context,
 * so it is drawn close to twice the width of a side trail. That is the
 * hierarchy a paper trail map has always drawn, and it is also the map's
 * hue-independent channel now that the dash rhythms are gone: the widest lines
 * on screen are the trails the map is about, whatever the light is doing to
 * the colours.
 *
 * Keyed off `source` - the attribute export_trails.py already publishes on
 * every feature - rather than off `blaze_color`, because this is a question
 * about which trail a line IS, not about how it is blazed. (Those two nearly
 * coincide today, since the centerline is flat-defaulted to White, but only
 * nearly: WIREFRAMES.md's own table notes centerline features carrying Purple
 * and Other, and a White-blazed side trail should still be drawn as a side
 * trail.)
 */
export const TRAIL_LINE_WIDTHS: Record<string, number> = {
  ...Object.fromEntries(
    PRIMARY_TRAIL_SOURCES.map((source) => [source, PRIMARY_TRAIL_WIDTH]),
  ),
  side_trails: SIDE_TRAIL_WIDTH,
}

/**
 * What a source this build has never heard of is drawn at.
 *
 * The side-trail width deliberately, not a through-route's: a later import
 * should reach the map rather than be invisible, and should not claim the top
 * tier on its way there. Joining PRIMARY_TRAIL_SOURCES is how a trail becomes
 * a through-route, and that is a decision someone makes rather than a default
 * an unrecognised source falls into.
 */
export const DEFAULT_TRAIL_LINE_WIDTH = SIDE_TRAIL_WIDTH

/**
 * Draw order inside a trail layer: through-routes over everything else.
 *
 * Every trail line lives in ONE layer, so within that layer the painter's
 * order is decided by the order the features happen to arrive in - which is
 * export order, which is nobody's decision. Where a side trail shares geometry
 * with the through-route it hangs off (and they share a lot of it: a spur that
 * leaves the AT is digitized from the AT's own vertices, and ATC's side_trails
 * often run coincident with the centerline for a stretch before branching),
 * whichever feature is drawn last wins the pixels.
 *
 * What that looked like on screen is the bug this fixes: the AT, drawn white,
 * with grey and blue stretches punched through it wherever an unblazed or
 * blue-blazed side trail happened to be exported after the centerline. The
 * hiker reads that as "the trail changes blaze here", which is exactly the
 * false statement at a junction that this map exists not to make.
 *
 * `line-sort-key` decides it instead, off the same `source` attribute that
 * decides width - higher sorts on top, so a through-route is painted last and
 * a side trail can never cover it. The two tiers are all that is needed:
 * within a tier, one line covering another is two lines of equal standing
 * overlapping, which is honest.
 */
export const PRIMARY_TRAIL_SORT_KEY = 1
export const SIDE_TRAIL_SORT_KEY = 0

export const TRAIL_SORT_KEY_EXPRESSION = [
  'case',
  ['in', ['get', 'source'], ['literal', [...PRIMARY_TRAIL_SOURCES]]],
  PRIMARY_TRAIL_SORT_KEY,
  SIDE_TRAIL_SORT_KEY,
]

/** How far the dark casing shows past each side of the line it sits under. */
export const CASING_OVERHANG = 1

/**
 * The widest a blaze is ever drawn, and the width a closure has to stay
 * markedly clear of (lib/closureStyle.ts and its tests read this).
 *
 * Derived from the table rather than written down twice, so widening a
 * through-route - or admitting a new one - cannot quietly narrow the gap that
 * keeps a closure from reading as a trail.
 */
export const BLAZE_LINE_WIDTH = Math.max(
  DEFAULT_TRAIL_LINE_WIDTH,
  ...Object.values(TRAIL_LINE_WIDTHS),
)
export const CASING_LINE_WIDTH = BLAZE_LINE_WIDTH + CASING_OVERHANG * 2

/**
 * `line-width` for the blaze layer, and for the casing under it.
 *
 * One expression each, built from the one table above. The casing is the same
 * expression plus a constant overhang, which is what keeps the hairline a
 * hairline on a 2.5px side trail and on a 4.5px through-route alike - a casing
 * scaled proportionally would be twice as heavy under a through-route as under
 * everything else.
 */
function trailWidthExpression(extra: number): unknown[] {
  return [
    'match',
    ['get', 'source'],
    ...Object.entries(TRAIL_LINE_WIDTHS).flatMap(([source, width]) => [
      source,
      width + extra,
    ]),
    DEFAULT_TRAIL_LINE_WIDTH + extra,
  ]
}

export const TRAIL_WIDTH_EXPRESSION = trailWidthExpression(0)
export const TRAIL_CASING_WIDTH_EXPRESSION = trailWidthExpression(CASING_OVERHANG * 2)

export interface MapStyleOptions {
  /** `pmtiles://` URL for the downloaded topo archive. */
  topoArchiveUrl: string
  /** Local URL of the exported trail lines. No network path. */
  trailsUrl: string
  /**
   * Which background to draw. Defaults to the live topographic sheet, which
   * is what someone who has not downloaded anything yet should be looking at.
   */
  background?: BackgroundSource
  /**
   * DEM and contour URLs from `registerTerrain()`.
   *
   * Optional so that `buildMapStyle` stays a pure function tests and callers
   * can build without registering a protocol first. Omitting them costs the
   * hillshade and the contour lines and NOTHING else - the live sheet's OSM
   * half is drawn either way. See liveTopo.ts's LiveTopoOptions for why that
   * split is where it is.
   */
  terrain?: TerrainUrls
  /** Decides whether contours and summit heights are in feet or metres. */
  units?: ContourUnits
}

export function buildMapStyle({
  topoArchiveUrl,
  trailsUrl,
  background = 'hiking_topo_live',
  terrain,
  units = 'imperial',
}: MapStyleOptions): StyleSpecification {
  // Asked for, and that is the whole question. Terrain used to be half of it -
  // `background === 'hiking_topo_live' && terrain !== undefined` - on the
  // reasoning that a style must not reference sources resolving to nothing.
  // True of the DEM and the contour tiles, and liveTopo.ts now drops exactly
  // those two sources and the four layers reading them. It was never true of
  // the other seventeen: the OSM vector sheet needs a URL and a schema, not an
  // elevation model.
  //
  // What the old spelling cost is the bug this fixes. An elevation model that
  // would not build took the landcover, the parks, the water, the path and
  // road network, the summits and every place name down with it, leaving the
  // flat paper of BACKDROP_LAYER_ID - and for a hiker who has downloaded
  // nothing, the archive underneath is empty too, so the whole screen is
  // paper. That contradicted what terrain.ts and MapView.tsx each promise in
  // their own words: a failure there costs a layer, never the map.
  const live = background === 'hiking_topo_live'
  const liveOptions = live ? { terrain, units } : null

  return {
    version: 8,
    // Only set when something needs glyphs. The endpoint is the app's own
    // origin now (#188), so this stopped being about a needless host
    // dependency - what survives is the plainer rule that a style declares
    // the endpoints its layers use, and the raster background has no symbol
    // layer to use this one.
    //
    // Keyed on `live` alone, deliberately, now that terrain is no longer part
    // of it: the surviving symbol layers - summits, water names, place names -
    // are all OSM-sourced and outlive a missing DEM. Tying this to terrain
    // instead would leave a style whose labels have no font to render in,
    // which MapLibre reports as a per-glyph load failure rather than anything
    // a reader would connect back to the elevation model.
    ...(live ? { glyphs: BUNDLED_GLYPHS } : {}),
    sources: {
      [TOPO_SOURCE_ID]: {
        type: 'raster',
        url: topoArchiveUrl,
        tileSize: 512,
        attribution: ATTRIBUTION,
      },
      [TRAILS_SOURCE_ID]: {
        type: 'geojson',
        data: trailsUrl,
        attribution: ATTRIBUTION,
        // Never simplify a trail away. MapLibre tiles GeoJSON through
        // geojson-vt, whose per-zoom simplification does two things under
        // this one knob: it thins vertices within a line (harmless - the
        // error is bounded sub-pixel), and it DROPS WHOLE FEATURES whose
        // projected length falls under that same bar - ~1.4 km at z4,
        // ~700 m at z5, ~350 m at z6 with the 0.375 px default.
        //
        // The centerline is not one feature. ATC surveys it as ~3,000
        // segments averaging ~1.2 km, so at corridor zooms much of the
        // trail is under the bar, consecutive short segments vanish
        // TOGETHER, and the AT rendered with miles-long gaps (#160) - on
        // this map, a false statement about where the trail is. Zero is
        // the only value that makes the drop rule structurally impossible,
        // for this data and for anything imported later.
        //
        // The cost lands only below ~z8, where the gaps were: low-zoom
        // tiles keep every vertex the pipeline's own 1 m simplification
        // left in (measured at this density: ~220 ms of worker time across
        // the z4-z6 tiles, once per session). #161 is the durable answer -
        // merge the centerline chains at export, then let this return to
        // the default - and owns the revert.
        tolerance: 0,
      },
      // Declared empty and filled in later - see buildPoiSource. Attributed
      // like the other two: the POIs are ATC and OpenStreetMap-derived, and a
      // source with no attribution is one release away from shipping
      // uncredited.
      [POI_SOURCE_ID]: { ...buildPoiSource(), attribution: ATTRIBUTION },
      // Each of these carries its own credit (OpenFreeMap's terms, the AWS
      // Terrain Tiles requirement) rather than the composed line - a source
      // should name the data IT is, and attributionFor() is what assembles the
      // corner out of whichever ones are actually in the style.
      ...(liveOptions === null ? {} : liveTopoSources(liveOptions)),
    },
    layers: [
      {
        // Under everything, because the topo tiles are transparent outside the
        // corridor (export_pmtiles.py's encode_webp) and a 30-mile ribbon
        // leaves most of a zoomed-out view uncovered. Without this that ground
        // is empty canvas; with it, it reads as unmapped paper - which is what
        // it honestly is. Paper rather than a neutral grey so the uncovered
        // area belongs to the same map as the parts that are covered.
        //
        // First in the list, and the only layer here bound to no source: it
        // covers the whole canvas at every zoom and every camera position, so
        // the "never black" guarantee survives a missing archive and an
        // off-corridor pan as well as the transparent ground it was added for.
        id: BACKDROP_LAYER_ID,
        type: 'background',
        paint: { 'background-color': MAP_BACKGROUND_COLOR },
      },
      {
        id: TOPO_LAYER_ID,
        type: 'raster',
        source: TOPO_SOURCE_ID,
      },
      // The live sheet goes OVER the downloaded raster, and that ordering is
      // the whole offline story rather than a cosmetic preference.
      //
      // Stacked this way, the two never have to be chosen between at runtime
      // and there is no online/offline branch anywhere: with signal, the
      // vector sheet covers the corridor with something sharp and styled and
      // keeps going past its edge, where there used to be nothing but blank
      // paper. Without signal, these layers simply draw nothing, the archive
      // shows through underneath exactly as it always has, and the flat paper
      // colour still marks where the download does not reach. Every state is
      // at least as good as it was before, and none of them needs to be detected.
      //
      // Still true, and worth keeping true: nothing observed at runtime reaches
      // this function. map/liveSourceHealth.ts does watch whether these sources
      // ever load, but only so the status strip can SAY so - what is composed
      // here stays a pure function of the preference, Data Saver, and whether a
      // DEM could be built.
      ...(liveOptions === null ? [] : liveTopoLayers(liveOptions)),
      {
        // Hairline dark casing, drawn under every blaze so the trail stays
        // readable over busy topo contours. It is doing more work than it used
        // to: with the line solid, the casing is the ONLY thing giving the
        // near-white centerline an edge against near-white paper, so it is
        // carried at a firmer opacity than when a gap in the line let it
        // through every few pixels.
        id: TRAIL_CASING_LAYER_ID,
        type: 'line',
        source: TRAILS_SOURCE_ID,
        layout: {
          'line-cap': 'round',
          'line-join': 'round',
          // Sorted like the blaze layer above it, though nothing visible
          // depends on it while every casing is the same colour. It is here so
          // that the day one is not - a heavier casing for a through-route, the
          // "drawn by absence" treatment WIREFRAMES.md reserves for Black - the
          // ordering rule is already in place rather than being a second bug
          // with the same shape as the first.
          'line-sort-key': TRAIL_SORT_KEY_EXPRESSION as unknown as number,
        },
        paint: {
          'line-color': '#2b2620',
          'line-width': TRAIL_CASING_WIDTH_EXPRESSION as unknown as number,
          'line-opacity': 0.7,
        },
      },
      {
        id: BLAZE_LAYER_ID,
        type: 'line',
        source: TRAILS_SOURCE_ID,
        // Round, matching the casing beneath it. Butt caps were what the dash
        // rhythm needed to keep its measured on/off lengths honest; on a solid
        // line they only leave a nick at every joint between two segments of
        // the same trail.
        //
        // The sort key is what keeps a side trail off the through-route it
        // branches from, where the two share geometry - see
        // TRAIL_SORT_KEY_EXPRESSION.
        layout: {
          'line-cap': 'round',
          'line-join': 'round',
          'line-sort-key': TRAIL_SORT_KEY_EXPRESSION as unknown as number,
        },
        paint: {
          'line-color': BLAZE_MATCH_EXPRESSION as unknown as string,
          'line-width': TRAIL_WIDTH_EXPRESSION as unknown as number,
        },
      },
      // Last, so a pin is never buried under the trail line it sits on. See
      // poiLayers.ts for why this is one layer rather than one per category.
      buildPoiLayer(),
    ],
  }
}
