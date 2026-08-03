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
//     the rhythm did: the AT centerline is drawn markedly wider than every
//     other trail, so the through-line of the map is findable with colour
//     removed entirely - by glare, by greyscale (WIREFRAMES.md `9d`), or by
//     colour vision deficiency. Width is keyed off the pipeline's own `source`
//     attribute, in one data-driven expression, for the same reason the colour
//     is keyed off `blaze_color` in one expression.
//
//     What this gives up is real and worth naming: yellow, orange and red side
//     trails were separable by rhythm and are now separable by hue alone, and
//     an undecoded blaze no longer reads as uncertain from its dotted rhythm.
//     Closures are unaffected - lib/closureStyle.ts keeps its barred band, and
//     with every blaze now solid that band is a stronger distinction than it
//     was, not a weaker one.
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
  LIVE_TOPO_ATTRIBUTION,
  OPENFREEMAP_GLYPHS,
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
 * because backdrop.ts reads it: whichever of the two is showing, the paper has
 * to be the same paper.
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

/** The pipeline's own key for the AT itself (pipeline/sources.json). */
export const CENTERLINE_SOURCE = 'centerline'

/**
 * Line width in CSS pixels, per trail source.
 *
 * The AT is the subject of this map and everything else is context, so the
 * centerline is drawn close to twice the width of a side trail. That is the
 * hierarchy a paper trail map has always drawn, and it is also the map's
 * hue-independent channel now that the dash rhythms are gone: the widest line
 * on screen is the AT, whatever the light is doing to the colours.
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
  [CENTERLINE_SOURCE]: 4.5,
  side_trails: 2.5,
}

/**
 * What a source this build has never heard of is drawn at.
 *
 * The side-trail width deliberately, not the centerline's: a later import
 * should reach the map rather than be invisible, and should not outrank the AT
 * on its way there.
 */
export const DEFAULT_TRAIL_LINE_WIDTH = 2.5

/** How far the dark casing shows past each side of the line it sits under. */
export const CASING_OVERHANG = 1

/**
 * The widest a blaze is ever drawn, and the width a closure has to stay
 * markedly clear of (lib/closureStyle.ts and its tests read this).
 *
 * Derived from the table rather than written down twice, so widening the
 * centerline cannot quietly narrow the gap that keeps a closure from reading
 * as a trail.
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
 * hairline on a 2.5px side trail and on a 4.5px centerline alike - a casing
 * scaled proportionally would be twice as heavy under the AT as under
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
   * DEM and contour URLs from `registerTerrain()`. Omitting them drops the
   * live background even when it is asked for, which is what keeps
   * `buildMapStyle` a pure function that tests and callers can build without
   * registering a protocol first.
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
  // Asked for AND buildable. A live background with no terrain URLs would be
  // a style referencing sources that resolve to nothing, so the two are
  // decided together, once, and every use below reads this one answer.
  const live = background === 'hiking_topo_live' && terrain !== undefined
  const liveOptions = live ? { terrain: terrain as TerrainUrls, units } : null

  return {
    version: 8,
    // Only set when something needs glyphs; a style declaring a font endpoint
    // it never asks for would make the offline-only map depend on a host it
    // has no reason to contact.
    ...(live ? { glyphs: OPENFREEMAP_GLYPHS } : {}),
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
      // keeps going past its edge, where there used to be nothing but hatched
      // paper. Without signal, these layers simply draw nothing, the archive
      // shows through underneath exactly as it always has, and the hatch still
      // marks where the download does not reach. Every state is at least as
      // good as it was before, and none of them needs to be detected.
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
        layout: { 'line-cap': 'round', 'line-join': 'round' },
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
        layout: { 'line-cap': 'round', 'line-join': 'round' },
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
