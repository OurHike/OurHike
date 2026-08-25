// Putting a route being built on the map: the source, the layers, and the
// pokes at a live map (#755).
//
// Same division of labour as closureLayers.ts, which this copies rather than
// riffs on: lib/route.ts is the arithmetic and knows nothing about MapLibre,
// lib/trailPosition.ts turns miles into coordinates and knows nothing about
// either, and this is the module that knows about MapLibre. The shell
// (App.tsx) does the joining.
//
// The route is drawn from `trailSlice` output, so it follows the centerline's
// real geometry and never draws across a part gap - a straight chord between
// two dropped points would be a picture of a trail that does not exist.

import type {
  GeoJSONSourceSpecification,
  LayerSpecification,
} from '@maplibre/maplibre-gl-style-spec'
import type { GeoJSONSource, Map as MapLibreMap, MapMouseEvent } from 'maplibre-gl'
import { whenStyleReady } from './styleReady'

export const ROUTE_SOURCE_ID = 'route'
export const ROUTE_CASING_LAYER_ID = 'route-casing'
export const ROUTE_LINE_LAYER_ID = 'route-line'
export const ROUTE_POINT_LAYER_ID = 'route-points'
export const ROUTE_LABEL_LAYER_ID = 'route-point-labels'

/** Which end of the route a dropped point is, for the paint below. Travels as
 *  a property, not the feature id - MapLibre parseInts string feature ids
 *  (see closureLayers.ts's CLOSURE_ID_PROPERTY). */
export const ROUTE_POINT_ROLE_PROPERTY = 'route_point_role'

/** The mile a dropped point sits at, already formatted (#973) - the frame's
 *  `MI 470.8`. Formatted in the shell rather than by a MapLibre expression,
 *  because the hiker's unit system decides it and `formatDistance` is the one
 *  place that knows: a label reading "MI 470.8" to somebody whose whole app
 *  is in kilometres is a second scale nobody asked for. */
export const ROUTE_POINT_LABEL_PROPERTY = 'route_point_label'

/** What the canvas needs to draw a route: where the line runs and where the
 *  dropped points sit. Coordinates, not miles - turning miles into geometry
 *  needs the centerline index, which the shell holds (same division as
 *  MapViewProps.closures). */
export interface RouteDrawing {
  /** One entry per leg, each multi-part where the centerline is - straight
   *  from trailSlice. */
  legs: Array<Array<Array<[number, number]>>>
  points: Array<{
    lon: number
    lat: number
    role: 'start' | 'via' | 'end'
    /** Already in the hiker's units - see ROUTE_POINT_LABEL_PROPERTY. */
    label: string
  }>
}

// Fixed ink, both themes, like the closure bands and the warning pins: an
// overlay that carries a decision keeps one identity everywhere. The green is
// the brand primary's own value; the casing is the paper tone that gives it
// an edge against both the light sheet and the dark one - the same job the
// trail casing does for the blaze.
const ROUTE_INK = '#355c3a'
const ROUTE_CASING = '#fffdf7'

export function buildRouteSource(): GeoJSONSourceSpecification {
  // Empty for the reason every runtime source is (buildClosureSource): the
  // route exists only once a hiker starts dropping points, and re-reading a
  // style to add a source would drop the WebGL context.
  return { type: 'geojson', data: { type: 'FeatureCollection', features: [] } }
}

export function buildRouteLayers(): LayerSpecification[] {
  return [
    {
      id: ROUTE_CASING_LAYER_ID,
      type: 'line',
      source: ROUTE_SOURCE_ID,
      filter: ['==', ['geometry-type'], 'LineString'],
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: {
        'line-color': ROUTE_CASING,
        'line-width': 7,
        'line-opacity': 0.85,
      },
    },
    {
      // Solid, not dashed - WIREFRAMES.md reserves dashes for closures, and a
      // route is a statement about trail, not about a barrier.
      id: ROUTE_LINE_LAYER_ID,
      type: 'line',
      source: ROUTE_SOURCE_ID,
      filter: ['==', ['geometry-type'], 'LineString'],
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: {
        'line-color': ROUTE_INK,
        'line-width': 3.5,
      },
    },
    {
      id: ROUTE_POINT_LAYER_ID,
      type: 'circle',
      source: ROUTE_SOURCE_ID,
      filter: ['==', ['geometry-type'], 'Point'],
      paint: {
        'circle-radius': 6,
        // The end is filled ink, start and intermediates are paper with an
        // ink ring - wireframe 2a's marks, and the one visual answer to
        // "which way does this run" a glance can get.
        'circle-color': [
          'case',
          ['==', ['get', ROUTE_POINT_ROLE_PROPERTY], 'end'],
          ROUTE_INK,
          ROUTE_CASING,
        ] as unknown as string,
        'circle-stroke-color': ROUTE_INK,
        'circle-stroke-width': 2.5,
      },
    },
    {
      // The frame labels every dropped point with its mile, and the reason is
      // not decoration: a route is a list of miles everywhere else in this
      // app - the stop rows, the legs, the plan it becomes - and a map that
      // draws the same points as unlabelled dots makes the hiker hold the
      // correspondence in their head.
      id: ROUTE_LABEL_LAYER_ID,
      type: 'symbol',
      source: ROUTE_SOURCE_ID,
      filter: ['==', ['geometry-type'], 'Point'],
      layout: {
        'text-field': ['get', ROUTE_POINT_LABEL_PROPERTY] as unknown as string,
        'text-size': 11,
        // The one fontstack bundled under public/glyphs (#986). 'Noto Sans
        // Bold' ships no glyphs, so the label rendered nothing at all - and
        // offline, where this app lives, there is nowhere to fetch it from.
        'text-font': ['Noto Sans Regular'],
        'text-offset': [0, -1.35],
        'text-anchor': 'bottom',
        // Never dropped for collision. A route's points are few and every one
        // of them is a thing the hiker put there deliberately; hiding one
        // because a trail label got there first would be the map editing the
        // hiker's own work.
        'text-allow-overlap': true,
        'text-ignore-placement': true,
      },
      paint: {
        'text-color': ROUTE_INK,
        // The paper tone as a halo, the same edge the line's casing gives it,
        // so the label holds on both sheets without a second colour.
        'text-halo-color': ROUTE_CASING,
        'text-halo-width': 1.6,
      },
    },
  ]
}

interface RouteFeatureCollection {
  type: 'FeatureCollection'
  features: Array<
    | {
        type: 'Feature'
        geometry: { type: 'MultiLineString'; coordinates: Array<Array<[number, number]>> }
        properties: Record<string, never>
      }
    | {
        type: 'Feature'
        geometry: { type: 'Point'; coordinates: [number, number] }
        properties: {
          [ROUTE_POINT_ROLE_PROPERTY]: 'start' | 'via' | 'end'
          [ROUTE_POINT_LABEL_PROPERTY]: string
        }
      }
  >
}

export function routeFeatureCollection(drawing: RouteDrawing): RouteFeatureCollection {
  return {
    type: 'FeatureCollection',
    features: [
      ...drawing.legs.map((lines) => ({
        type: 'Feature' as const,
        geometry: { type: 'MultiLineString' as const, coordinates: lines },
        properties: {},
      })),
      ...drawing.points.map((point) => ({
        type: 'Feature' as const,
        geometry: {
          type: 'Point' as const,
          coordinates: [point.lon, point.lat] as [number, number],
        },
        properties: {
          [ROUTE_POINT_ROLE_PROPERTY]: point.role,
          [ROUTE_POINT_LABEL_PROPERTY]: point.label,
        },
      })),
    ],
  }
}

const EMPTY: RouteDrawing = { legs: [], points: [] }

/** Pushes the route onto the live map's source, and returns a detach. Null
 *  clears it - leaving the builder empties the source rather than leaving a
 *  stale route drawn under nothing. */
export function attachRouteData(
  map: MapLibreMap,
  drawing: RouteDrawing | null,
): () => void {
  return whenStyleReady(
    map,
    () => map.getSource(ROUTE_SOURCE_ID) !== undefined,
    () => {
      const source = map.getSource<GeoJSONSource>(ROUTE_SOURCE_ID)
      if (source === undefined || typeof source.setData !== 'function') return

      source.setData(routeFeatureCollection(drawing ?? EMPTY) as never)
    },
    'route',
  )
}

/**
 * While the builder is active, a tap means "drop a point here" - and nothing
 * else. Attached INSTEAD of attachPoiTaps, never alongside it (MapView owns
 * that exclusivity): atcUpdateLayers.ts's own comment records why two
 * handlers racing to interpret one touch on bare ground is the failure mode,
 * and a third interpreter would be that failure squared.
 *
 * The raw coordinate is reported, not a mile: snapping is
 * lib/trailPosition.ts's job and refusing an off-corridor tap is the
 * shell's, since the shell owns what to tell the hiker about it.
 */
export function attachRouteTaps(
  map: MapLibreMap,
  onTap: (at: { lon: number; lat: number }) => void,
): () => void {
  const onClick = (event: MapMouseEvent) => {
    onTap({ lon: event.lngLat.lng, lat: event.lngLat.lat })
  }

  map.on('click', onClick)
  const canvas = map.getCanvas()
  const previousCursor = canvas.style.cursor
  canvas.style.cursor = 'crosshair'

  return () => {
    map.off('click', onClick)
    canvas.style.cursor = previousCursor
  }
}
