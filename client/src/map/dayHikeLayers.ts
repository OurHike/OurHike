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
import type { MileTick } from '../lib/dayHikeCourse'

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

/**
 * The selection, made legible without recolouring a blaze (#1194).
 *
 * THE COMPLAINT AND THE CONSTRAINT, TOGETHER. A design pass found the
 * highlight hard to pick out, and it was right: this module's own header does
 * the arithmetic - a hiker sees `0.45 x blaze + 0.55 x (band over basemap)`
 * where the band was ROUTE_INK at 0.35, which is a wash. The design's fix was
 * a `--blaze-yellow` core drawn OVER the line, and that fix is not available
 * here for the reason the header states at length: yellow is a real blaze in
 * Harriman, and repainting a trail's blaze on the screen a hiker uses to
 * choose which blaze to follow is the failure this module was built to avoid.
 *
 * So the contrast comes from everything except hue:
 *
 *  - A SECOND, WIDER CASING IN PINE-900 under the first. Wider than any trail
 *    line on the sheet (the through-route is 4.5 px), so what a hiker
 *    actually sees is a dark fringe on both sides of the route - ground that
 *    no line covers, and therefore the one part of the highlight whose
 *    contrast is not divided by the ghost. It is the design's `--pine-900`
 *    casing at the design's job, moved to the only side of the line it can
 *    honestly sit on.
 *  - THE GREEN BAND RAISED from 0.35 to 0.6. Still under, still translucent,
 *    so the blaze above it still composites - but the body of the route now
 *    reads as coloured rather than as a smudge.
 *
 * @unvalidated, and in the specific way this whole file is: nobody has looked
 * at it on a phone in daylight, which is the only instrument that settles a
 * contrast question. What would settle it is the outdoor pass #105 owes the
 * rest of the chrome. What can be said without that: the fringe is opaque
 * ink on basemap, so it is strictly more visible than the 0.35 band was, and
 * no blaze hue anywhere on the sheet changed.
 */
const CASING_WIDTH = 11
const CASING_OPACITY = 0.6

/** Pine-900 - the app's dark chrome ink, and the design's casing colour. */
const OUTER_CASING_INK = '#122016'
const OUTER_CASING_WIDTH = 17
const OUTER_CASING_OPACITY = 0.85

export const DAY_HIKE_OUTER_CASING_LAYER_ID = 'day-hike-route-outer-casing'

/** The mile ticks and their numbers (#1194). Two layers over one source. */
export const DAY_HIKE_TICK_LAYER_ID = 'day-hike-mile-ticks'
export const DAY_HIKE_TICK_LABEL_LAYER_ID = 'day-hike-mile-tick-labels'
export const DAY_HIKE_TICK_SOURCE_ID = 'day-hike-mile-ticks'
/** The whole-mile number this tick marks, already a string. */
export const DAY_HIKE_TICK_LABEL_PROPERTY = 'day_hike_mile'
/** Degrees clockwise from north along the trail, for the crossbar's rotation. */
export const DAY_HIKE_TICK_BEARING_PROPERTY = 'day_hike_bearing'

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
      // FIRST, so it sits under the green band as well as under the trails.
      // Its whole job is the fringe either side of both.
      id: DAY_HIKE_OUTER_CASING_LAYER_ID,
      type: 'line',
      source: DAY_HIKE_SOURCE_ID,
      filter: [
        'all',
        ['==', ['geometry-type'], 'LineString'],
        ['!', ['to-boolean', ['get', DAY_HIKE_GAP_PROPERTY]]],
      ],
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: {
        'line-color': OUTER_CASING_INK,
        'line-width': OUTER_CASING_WIDTH,
        'line-opacity': OUTER_CASING_OPACITY,
      },
    },
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
        // THE ONE BUNDLED FACE, and this used to say 'Noto Sans Bold' - a
        // fontstack that does not exist. map/liveTopo.ts ships exactly one
        // under public/glyphs/ (Noto Sans Regular, all 256 ranges, precached),
        // and map/style.ts points `glyphs` at this app's own origin, so a
        // request for any other stack 404s and MapLibre draws NO TEXT AT ALL.
        // The numbered marks a hiker taps have therefore been blank circles
        // since #978 - silently, because a missing glyph range is not an
        // error anything surfaces.
        //
        // #986 made this exact fix in map/routeLayers.ts, whose comment names
        // the constraint; this layer was written after it and did not get the
        // memo. Anything adding a symbol layer here reads that comment first.
        'text-font': ['Noto Sans Regular'],
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

export function buildDayHikeTickSource(): GeoJSONSourceSpecification {
  return { type: 'geojson', data: { type: 'FeatureCollection', features: [] } }
}

/**
 * The mile marks: a number every whole mile of the walk (#1194).
 *
 * ONE LAYER, AND IT IS THE NUMBER - NOT A CROSSBAR WITH A NUMBER BESIDE IT.
 * The design handoff draws a 20-unit perpendicular tick with the mile printed
 * next to it, and then states the rule that matters as something it learned
 * the hard way: "The number is the readout, not the crossbar... only draw the
 * tick line if its number was successfully placed - a bare crossbar with no
 * number is meaningless."
 *
 * Taking that rule seriously deletes the crossbar. A separate line or circle
 * layer cannot honour it, because neither joins MapLibre's symbol collision
 * pass - a tick drawn that way is placed unconditionally and would survive
 * exactly when its number is dropped, which is the failure the rule names.
 * Folding both into one symbol makes "no number, no mark" structural instead
 * of something a second layer has to remember.
 *
 * What is lost is the crossbar's precision about WHERE the mile falls, and
 * the halo buys most of it back: a haloed numeral on the line reads as a mark
 * on the line. What is gained is that a crowded stretch of a switchbacking
 * route drops whole marks rather than accumulating bare ticks.
 *
 * `text-allow-overlap` is left at the spec default (false) deliberately, for
 * the reason map/poiLayers.ts states about `icon-allow-overlap`: it is the
 * entire density story, and a `true` added later for one screenshot would
 * silently undo it.
 */
export function buildDayHikeTickLayers(): LayerSpecification[] {
  return [
    {
      id: DAY_HIKE_TICK_LABEL_LAYER_ID,
      type: 'symbol',
      source: DAY_HIKE_TICK_SOURCE_ID,
      layout: {
        'text-field': ['get', DAY_HIKE_TICK_LABEL_PROPERTY] as unknown as string,
        // The one bundled face - see the note on the point labels above.
        'text-font': ['Noto Sans Regular'],
        'text-size': 12,
        // Mile numbers outrank trail names and every unselected waypoint, and
        // sit just under a chosen stop's own name: tier 2 of the handoff's
        // ladder. map/labelLadder.ts owns the scale; this is its entry.
        'symbol-sort-key': MILE_TICK_SORT_KEY,
        'text-padding': 4,
      },
      paint: {
        'text-color': OUTER_CASING_INK,
        // Paper, and wide - the numeral sits ON the route's own dark casing,
        // where ink on ink would be unreadable without it. The design's ratio
        // is ~0.34 x font size, which at 12px is 4; MapLibre's halo is a
        // radius rather than a stroke width, so half of that is the same mark.
        'text-halo-color': '#fffdf7',
        'text-halo-width': 2,
      },
    },
  ]
}

/** Tier 2 of the label ladder - see map/labelLadder.ts. */
const MILE_TICK_SORT_KEY = 20

interface TickFeatureCollection {
  type: 'FeatureCollection'
  features: Array<{
    type: 'Feature'
    geometry: { type: 'Point'; coordinates: [number, number] }
    properties: {
      [DAY_HIKE_TICK_LABEL_PROPERTY]: string
      [DAY_HIKE_TICK_BEARING_PROPERTY]: number
    }
  }>
}

export function tickFeatureCollection(ticks: readonly MileTick[]): TickFeatureCollection {
  return {
    type: 'FeatureCollection',
    features: ticks.map((tick) => ({
      type: 'Feature' as const,
      geometry: {
        type: 'Point' as const,
        coordinates: [tick.lon, tick.lat] as [number, number],
      },
      properties: {
        // Whole miles, so no decimal point: `mileTicks` only emits integers
        // and a "3.0" here would look like a measured figure rather than a
        // scale mark.
        [DAY_HIKE_TICK_LABEL_PROPERTY]: String(Math.round(tick.mile)),
        // Carried even though no layer reads it yet: it is the one thing a
        // crossbar would need, and recovering it later means recomputing the
        // course. Cheap to keep, expensive to re-derive.
        [DAY_HIKE_TICK_BEARING_PROPERTY]: tick.bearing,
      },
    })),
  }
}

/** Pushes the mile marks onto the live map. An empty list clears them. */
export function attachDayHikeTicks(
  map: MapLibreMap,
  ticks: readonly MileTick[],
): () => void {
  return whenStyleReady(
    map,
    () => map.getSource(DAY_HIKE_TICK_SOURCE_ID) !== undefined,
    () => {
      const source = map.getSource<GeoJSONSource>(DAY_HIKE_TICK_SOURCE_ID)
      if (source === undefined || typeof source.setData !== 'function') return

      source.setData(tickFeatureCollection(ticks) as never)
    },
    'day-hike-ticks',
  )
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
