// Builds the MapLibre style for the trail map.
//
// Two rules from WIREFRAMES.md's "Trail line rendering — blazes" are
// load-bearing rather than cosmetic:
//
//  1. ONE `match` expression drives line-color across every trail source, so a
//     source imported later inherits the rule instead of needing its own layer.
//     That expression lives in lib/blaze.ts and is imported, never re-spelled.
//
//  2. Dash rhythm is a SECOND, hue-independent channel. Yellow, orange and red
//     are nearly indistinguishable once desaturated by glare or a greyscale
//     pass (WIREFRAMES.md `9d`), so rhythm - not hue - is what keeps them
//     apart. MapLibre v6 types `line-dasharray` as `cross-faded-data-driven`,
//     which means one data-driven expression covers every blaze in a single
//     layer; this needs no per-blaze layer fan-out.
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

export const BLAZE_LINE_WIDTH = 2
export const CASING_LINE_WIDTH = BLAZE_LINE_WIDTH + 1.5

/**
 * Dash rhythms exactly as WIREFRAMES.md specifies them, in PIXELS.
 *
 * MapLibre measures `line-dasharray` in multiples of the line's own width, not
 * pixels, so these are divided by {@link BLAZE_LINE_WIDTH} on the way into the
 * style. Keeping the table in the spec's own units is what lets it be checked
 * against WIREFRAMES.md by eye.
 */
export const BLAZE_DASH_RHYTHMS: Record<string, [number, number]> = {
  White: [10, 6],
  Blue: [10, 6],
  Yellow: [6, 5],
  Orange: [10, 5],
  Red: [15, 5],
  Green: [13, 5],
  Purple: [10, 6],
  // Sparse dotted: undecoded lines should read as uncertain at a glance.
  None: [4, 6],
  Other: [4, 6],
}

const NEUTRAL_RHYTHM: [number, number] = [4, 6]

function toLineWidthUnits([on, off]: [number, number]): [number, number] {
  return [on / BLAZE_LINE_WIDTH, off / BLAZE_LINE_WIDTH]
}

export const BLAZE_DASH_MATCH_EXPRESSION = [
  'match',
  ['get', 'blaze_color'],
  ...Object.entries(BLAZE_DASH_RHYTHMS).flatMap(([blaze, rhythm]) => [
    blaze,
    ['literal', toLineWidthUnits(rhythm)],
  ]),
  ['literal', toLineWidthUnits(NEUTRAL_RHYTHM)],
]

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
        // readable over busy topo contours.
        id: TRAIL_CASING_LAYER_ID,
        type: 'line',
        source: TRAILS_SOURCE_ID,
        layout: { 'line-cap': 'round', 'line-join': 'round' },
        paint: {
          'line-color': '#2b2620',
          'line-width': CASING_LINE_WIDTH,
          'line-opacity': 0.55,
        },
      },
      {
        id: BLAZE_LAYER_ID,
        type: 'line',
        source: TRAILS_SOURCE_ID,
        layout: { 'line-cap': 'butt', 'line-join': 'round' },
        paint: {
          'line-color': BLAZE_MATCH_EXPRESSION as unknown as string,
          'line-dasharray': BLAZE_DASH_MATCH_EXPRESSION as unknown as number[],
          'line-width': BLAZE_LINE_WIDTH,
        },
      },
      // Last, so a pin is never buried under the trail line it sits on. See
      // poiLayers.ts for why this is one layer rather than one per category.
      buildPoiLayer(),
    ],
  }
}
