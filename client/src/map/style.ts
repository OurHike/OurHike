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
// Not handled here: blaze "Black" (code 8). WIREFRAMES.md's table describes it
// as "wide casing, no fill — drawn by absence," but the real data has zero
// Black features today and lib/blaze.ts has no colour for it, so it falls to
// the neutral-grey defensive fallback and logs a warning. Giving it a real
// treatment needs a design decision and at least one real feature to look at.

import type { StyleSpecification } from '@maplibre/maplibre-gl-style-spec'
import { BLAZE_MATCH_EXPRESSION } from '../lib/blaze'

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
}

export function buildMapStyle({
  topoArchiveUrl,
  trailsUrl,
}: MapStyleOptions): StyleSpecification {
  return {
    version: 8,
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
    ],
  }
}
