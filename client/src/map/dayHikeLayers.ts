// Putting a day hike being built on the map (#978, wireframe frame `1j`).
//
// Same division of labour as routeLayers.ts, which this copies rather than
// riffs on: lib/trailGraph.ts is the arithmetic and knows nothing about
// MapLibre, lib/dayHikeDraft.ts holds the taps, and this is the module that
// knows about MapLibre. The shell (App.tsx) does the joining.
//
// THE CASING GOES UNDER THE TRAIL LINES, AND THAT IS THE WHOLE DESIGN
//
// The A.T. builder's route draws ABOVE the centerline (buildRouteLayers,
// spliced late), and there it is safe: every line under it is white-blazed.
// A day hike crosses a NETWORK, where the blaze is how a hiker at a junction
// tells Seven Hills from Pine Meadow - so frame `1j`'s annotation is a rule,
// not a style: "The route highlight is a translucent casing UNDER the line so
// blaze hue is never recoloured." A green route drawn over a yellow trail is
// a map lying about which blaze somebody is following at exactly the moment
// they are looking for the next one. Same reasoning as style.ts's sort-key
// rule and lib/closureStyle.ts's flat literal.
//
// WHAT "UNDER" COSTS, STATED RATHER THAN HIDDEN. The routable lines are
// ghosted - drawn at NEARBY_TRAIL_OPACITY (0.45), casing at 0.315 - so a band
// beneath them composites through: what a hiker sees on the route is
// 0.45 x blaze + 0.55 x (band over basemap). The blaze's own paint is
// untouched (that is the rule), but the ground behind it warms toward the
// ink. @unvalidated that the shift stays legible-and-honest at these
// opacities; what would settle it is the same instrument as every other blaze
// question - a phone outdoors, red-light mode included.
//
// ONE INK, SHARED WITH THE A.T. BUILDER - the maintainer's call, 2026-08-25.
// Two greens meaning "your route" with opposite draw orders would be the app
// saying two things with one colour. ROUTE_INK stays fixed in both themes and
// under red light, the same identity-keeping rule the closure bands follow.

import type {
  GeoJSONSourceSpecification,
  LayerSpecification,
} from '@maplibre/maplibre-gl-style-spec'
import type { GeoJSONSource, Map as MapLibreMap } from 'maplibre-gl'
import { ROUTE_INK } from './routeLayers'
import { whenStyleReady } from './styleReady'

export const DAY_HIKE_SOURCE_ID = 'day-hike-route'
export const DAY_HIKE_CASING_LAYER_ID = 'day-hike-route-casing'
export const DAY_HIKE_GAP_LAYER_ID = 'day-hike-route-gap'
export const DAY_HIKE_POINT_LAYER_ID = 'day-hike-route-points'
/** Flags a feature as a gap rather than a routed stretch. A property rather
 *  than a second source, so the gap and the route cannot get out of step. */
export const DAY_HIKE_GAP_PROPERTY = 'day_hike_gap'
/** Stone. Not the brand green, which means "your route", and not a blaze or a
 *  warning colour - a gap is the absence of a claim. */
const DAY_HIKE_GAP_INK = '#8a8271'
export const DAY_HIKE_POINT_LABEL_LAYER_ID = 'day-hike-route-point-labels'

/** The tap's ordinal, already a string - frame `1j`'s numbered marks. A
 *  property, not the feature id, for closureLayers.ts's parseInt reason. */
export const DAY_HIKE_POINT_LABEL_PROPERTY = 'day_hike_point_label'

/** What the canvas needs: the routed lines (one per edge, from
 *  lib/trailGraph.ts's routeGeometry) and the tapped points in order. */
export interface DayHikeDrawing {
  lines: Array<Array<[number, number]>>
  points: Array<{ lon: number; lat: number; label: string }>
  /**
   * The gaps between stretches (#935/#983): ground the app declined to route,
   * drawn so a hiker can see WHERE it declined rather than only that it did.
   *
   * DRAWN AS NEITHER A ROUTE NOR A CLOSURE, and that is the whole of its
   * styling. The route is a solid casing under the blaze because it is a
   * statement about trail; a dash is the map's word for a barrier. A gap is
   * neither - it is the app saying it has no evidence about this ground - so
   * it may not borrow either vocabulary. What it gets is a DOT rhythm in
   * stone: about 1 px on and 6 px off at 2 px wide, against corridorLayers.ts's
   * 2/1.3 dashes for an unattributed run and the long dashes a closure wears.
   *
   * A solid line here would be the app drawing a way across ground it has
   * just told the hiker it will not guess at.
   *
   * @unvalidated, like every dash rhythm in this codebase and for the same
   * reason: nobody has looked at it on a phone in daylight. The outdoor pass
   * #105 owes the rest of the chrome owes this too.
   */
  gaps?: Array<Array<[number, number]>>
}

const CASING_WIDTH = 11
const CASING_OPACITY = 0.35

export function buildDayHikeSource(): GeoJSONSourceSpecification {
  // Empty for the reason every runtime source is (buildRouteSource): the
  // draft exists only once a hiker starts tapping, and re-reading a style to
  // add a source would drop the WebGL context.
  return { type: 'geojson', data: { type: 'FeatureCollection', features: [] } }
}

/**
 * The casing alone. Spliced into the style BEFORE both trail-line stacks -
 * that placement is the rule this module exists for, and style.test.ts pins
 * it by index rather than trusting this comment.
 */
export function buildDayHikeCasingLayers(): LayerSpecification[] {
  return [
    {
      id: DAY_HIKE_CASING_LAYER_ID,
      type: 'line',
      source: DAY_HIKE_SOURCE_ID,
      // The gap is excluded EXPLICITLY rather than by geometry: MapLibre's
      // `geometry-type` reports a MultiLineString as 'LineString', so a filter
      // on shape alone would give the gap the route's own casing - a solid
      // band under ground the app has just declined to route.
      filter: [
        'all',
        ['==', ['geometry-type'], 'LineString'],
        ['!', ['to-boolean', ['get', DAY_HIKE_GAP_PROPERTY]]],
      ],
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: {
        'line-color': ROUTE_INK,
        'line-width': CASING_WIDTH,
        'line-opacity': CASING_OPACITY,
      },
    },
  ]
}

/**
 * The tapped points, drawn ABOVE the lines like every marker is - a point
 * under a trail line would be invisible, and the numbers are the hiker's own
 * work. Same never-collided rule as the A.T. builder's labels: hiding a tap
 * because a trail label got there first would be the map editing the hiker.
 */
export function buildDayHikePointLayers(): LayerSpecification[] {
  return [
    {
      // The gap sits with the POINTS rather than with the casing, and that is
      // the placement rather than an accident of ordering: the casing goes
      // UNDER the trail lines so a blaze is never recoloured, and there is no
      // trail line under a gap to go under. Drawn over the basemap where a
      // hiker can see it.
      id: DAY_HIKE_GAP_LAYER_ID,
      type: 'line',
      source: DAY_HIKE_SOURCE_ID,
      filter: ['==', ['get', DAY_HIKE_GAP_PROPERTY], true],
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: {
        'line-color': DAY_HIKE_GAP_INK,
        'line-width': 2,
        'line-dasharray': [0.5, 3] as unknown as number[],
      },
    },
    {
      id: DAY_HIKE_POINT_LAYER_ID,
      type: 'circle',
      source: DAY_HIKE_SOURCE_ID,
      filter: ['==', ['geometry-type'], 'Point'],
      paint: {
        'circle-radius': 9,
        'circle-color': ROUTE_INK,
        'circle-stroke-color': '#fffdf7',
        'circle-stroke-width': 2,
      },
    },
    {
      id: DAY_HIKE_POINT_LABEL_LAYER_ID,
      type: 'symbol',
      source: DAY_HIKE_SOURCE_ID,
      filter: ['==', ['geometry-type'], 'Point'],
      layout: {
        'text-field': ['get', DAY_HIKE_POINT_LABEL_PROPERTY] as unknown as string,
        'text-size': 11,
        'text-font': ['Noto Sans Bold'],
        'text-allow-overlap': true,
        'text-ignore-placement': true,
      },
      paint: {
        'text-color': '#fffdf7',
      },
    },
  ]
}

interface DayHikeFeatureCollection {
  type: 'FeatureCollection'
  features: Array<
    | {
        type: 'Feature'
        geometry: { type: 'MultiLineString'; coordinates: Array<Array<[number, number]>> }
        properties: Record<string, never> | { [DAY_HIKE_GAP_PROPERTY]: true }
      }
    | {
        type: 'Feature'
        geometry: { type: 'Point'; coordinates: [number, number] }
        properties: { [DAY_HIKE_POINT_LABEL_PROPERTY]: string }
      }
  >
}

export function dayHikeFeatureCollection(
  drawing: DayHikeDrawing,
): DayHikeFeatureCollection {
  return {
    type: 'FeatureCollection',
    features: [
      // One MultiLineString, not a concatenation: the lines come one per
      // edge, and at an endpoint-welded junction the published gap between
      // two stewards' surveys stays visible, which is true.
      ...(drawing.lines.length > 0
        ? [
            {
              type: 'Feature' as const,
              geometry: { type: 'MultiLineString' as const, coordinates: drawing.lines },
              properties: {},
            },
          ]
        : []),
      // One feature per gap rather than one MultiLineString holding them all,
      // so a gap is a thing on the map with its own extent rather than a part
      // of a shape that also spans the walk.
      ...(drawing.gaps ?? []).map((line) => ({
        type: 'Feature' as const,
        geometry: { type: 'MultiLineString' as const, coordinates: [line] },
        properties: { [DAY_HIKE_GAP_PROPERTY]: true as const },
      })),
      ...drawing.points.map((point) => ({
        type: 'Feature' as const,
        geometry: {
          type: 'Point' as const,
          coordinates: [point.lon, point.lat] as [number, number],
        },
        properties: { [DAY_HIKE_POINT_LABEL_PROPERTY]: point.label },
      })),
    ],
  }
}

const EMPTY: DayHikeDrawing = { lines: [], points: [] }

/** Pushes the draft onto the live map's source, and returns a detach. Null
 *  clears it - leaving the builder empties the source rather than leaving a
 *  stale route drawn under nothing. */
export function attachDayHikeData(
  map: MapLibreMap,
  drawing: DayHikeDrawing | null,
): () => void {
  return whenStyleReady(
    map,
    () => map.getSource(DAY_HIKE_SOURCE_ID) !== undefined,
    () => {
      const source = map.getSource<GeoJSONSource>(DAY_HIKE_SOURCE_ID)
      if (source === undefined || typeof source.setData !== 'function') return

      source.setData(dayHikeFeatureCollection(drawing ?? EMPTY) as never)
    },
    'day-hike',
  )
}
