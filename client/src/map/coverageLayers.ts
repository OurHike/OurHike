// Where the downloaded map ends, drawn on the map itself (#557,
// features/OFFLINE_COVERAGE.md §7).
//
// A hiker holding a stretch rather than the whole sheet crosses, at some
// point, from ground they downloaded onto ground they did not - and 1° cells
// make that crossing a dead-straight meridian or parallel, which on a map
// reads as a rendering fault unless it is named. The maintainer's call
// (2026-08-28, in session, reviewing the mock-ups) was a DASHED boundary plus
// a banner on crossing, quiet until it matters - and not permanently-muted
// ground beyond the edge, which also reads as a fault.
//
// The line is the OUTER edge of what is held (lib/coverageCells.ts's
// `seamEdges`): a boundary between two held cells is not a seam, the map is
// continuous across it, and dashing it would draw a wall through somebody's
// own coverage.
//
// UNDER EVERY TRAIL LINE AND EVERY PIN, and that placement is the doc's §8 in
// paint: pieces scope the sheet and never safety. The seam takes away the
// ground, never the trail, the water or the closures, so nothing that carries
// a decision may sit under it. It is over the background and the drought wash
// for the same reason those are under the trail - it annotates the ground.
//
// droughtLayers.ts's split: the layer spec and the imperative poke at a live
// map live here, and the shell hands over edges it has already computed.

import type {
  GeoJSONSourceSpecification,
  LayerSpecification,
} from '@maplibre/maplibre-gl-style-spec'
import type { GeoJSONSource, Map as MapLibreMap } from 'maplibre-gl'
import type { SeamEdge } from '../lib/coverageCells'
import { whenStyleReady } from './styleReady'

export const COVERAGE_SEAM_SOURCE_ID = 'coverage-seams'
export const COVERAGE_SEAM_LAYER_ID = 'coverage-seam'
export const COVERAGE_SEAM_LABEL_LAYER_ID = 'coverage-seam-label'

/** What the edge says, in the mock-ups' own words - coverage, never damage. */
export const COVERAGE_SEAM_LABEL = 'edge of what you downloaded'

/**
 * Where the label starts appearing. The dashed line itself draws at every
 * zoom - at the corridor view a stretch reads as a dashed box around the
 * held ground, which is the honest shape of it - but four words along every
 * edge at z5 is clutter over the very view that shows the whole trail.
 * Picked to match the pin seam's neighbourhood rather than measured.
 */
export const COVERAGE_SEAM_LABEL_MIN_ZOOM = 8

/** The bundled glyphs every line label on this map uses (trailLabels.ts). */
const FONT = ['Noto Sans Regular']

export function seamFeatureCollection(
  edges: readonly SeamEdge[],
): GeoJSON.FeatureCollection {
  return {
    type: 'FeatureCollection',
    features: edges.map(([from, to]) => ({
      type: 'Feature',
      geometry: { type: 'LineString', coordinates: [[...from], [...to]] },
      properties: { label: COVERAGE_SEAM_LABEL },
    })),
  }
}

/** An empty source, filled once the shell knows what is held - same shape
 *  and same reason as `buildDroughtSource`. */
export function buildCoverageSeamSource(): GeoJSONSourceSpecification {
  return { type: 'geojson', data: { type: 'FeatureCollection', features: [] } }
}

/**
 * The dashed edge and its name.
 *
 * Inked in the trail casing's colour rather than a colour of its own, so it
 * belongs to the same sheet in every appearance and so map/style.ts's
 * appearance repaint has one colour to carry rather than a new one.
 */
export function buildCoverageSeamLayers(ink: string, halo: string): LayerSpecification[] {
  return [
    {
      id: COVERAGE_SEAM_LAYER_ID,
      type: 'line',
      source: COVERAGE_SEAM_SOURCE_ID,
      layout: { 'line-cap': 'butt', 'line-join': 'miter' },
      paint: {
        'line-color': ink,
        'line-width': 1.5,
        'line-dasharray': [3, 3],
        'line-opacity': 0.7,
      },
    },
    {
      id: COVERAGE_SEAM_LABEL_LAYER_ID,
      type: 'symbol',
      source: COVERAGE_SEAM_SOURCE_ID,
      minzoom: COVERAGE_SEAM_LABEL_MIN_ZOOM,
      layout: {
        'text-field': ['get', 'label'] as never,
        'text-font': FONT,
        'symbol-placement': 'line',
        'symbol-spacing': 400,
        'text-size': 11,
        'text-letter-spacing': 0.05,
      },
      paint: {
        'text-color': ink,
        'text-halo-color': halo,
        'text-halo-width': 1.5,
      },
    },
  ]
}

/** Pushes the held edges onto the live map's source, and returns a detach.
 *  An empty list is a real answer - nothing held, or the whole sheet held,
 *  both of which have no edge to draw - and clears the line. */
export function attachCoverageSeams(
  map: MapLibreMap,
  edges: readonly SeamEdge[],
): () => void {
  return whenStyleReady(
    map,
    () => map.getSource(COVERAGE_SEAM_SOURCE_ID) !== undefined,
    () => {
      const source = map.getSource<GeoJSONSource>(COVERAGE_SEAM_SOURCE_ID)
      if (source === undefined || typeof source.setData !== 'function') return

      source.setData(seamFeatureCollection(edges) as never)
    },
    'coverage seams',
  )
}
