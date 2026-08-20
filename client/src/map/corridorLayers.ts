// The corridor view's own geometry: the miles ATC's centerline cannot
// attribute, and the places responsibility changes hands (#598,
// features/CORRIDOR_VIEW.md).
//
// Structured exactly like closureLayers.ts, which solves the same problem one
// step earlier: lib/clubSections.ts is the data and knows nothing about
// MapLibre, lib/trailPosition.ts turns mile numbers into coordinates and knows
// nothing about either, and this is the module that knows about MapLibre. The
// published artifact carries mile ranges and no geometry, so `trailSlice` is
// what makes it drawable - and its MultiLineString result is why the runs
// below are multi-part rather than one line each.
//
// TWO COLOURS, AND BOTH ALREADY EXISTED
//
// The maintainer's 2026-08-19 decision: the corridor draws in the blaze's own
// colour and one neutral grey, and nothing else. Those are lib/blaze.ts's
// `BLAZE_COLORS.White` and its `NEUTRAL_FALLBACK` - so this module introduces
// no colour at all. The white is not drawn here: it is already on screen, from
// the blaze layer, and leaving it alone is the point. What this adds is the
// grey, over the miles the fresh source cannot name.
//
// Grey is not a new meaning either. WIREFRAMES.md §3 already spends it on "we
// do not know this": an undecoded blaze "is still the neutral grey, and the tap
// sheet still says so in words". A mile with no recorded club is the same
// sentence about a different question, and gets the same answer.
//
// WHY THESE LAYERS STOP AT THE SEAM
//
// `maxzoom: POI_PIN_MIN_ZOOM` on every one of them. Above the seam a hiker is
// navigating by the line, and map/style.test.ts's "a blaze never changes colour
// where a hiker is navigating by it" is the assertion that keeps this layer out
// of that. Below it the line is representational - 2.5 px standing for 2,197
// miles - which is the ground the maintainer scoped the dash rule to on
// 2026-08-19.
//
// WHY THE GREY CARRIES ITS OWN CASING
//
// It is drawn OVER the blaze, so a dashed grey line alone would show the white
// blaze through every gap - which is precisely the "dotted grey-and-white
// thread" WIREFRAMES.md §3's superseded note records failing. A solid casing
// under the dash covers the blaze first, so the gaps show the casing the way
// they do on every other trail line in this app rather than the trail
// underneath.
//
// NO TEXT, DELIBERATELY
//
// The club's name is not drawn on the map. The offline style declares no
// `glyphs` endpoint - map/style.test.ts asserts it, and asserts that no layer
// asks for text - so a symbol layer here would render nothing on a downloaded
// map, which is the map this app exists for. Who maintains a stretch is
// answered in the chrome instead, where it is DOM text: the tap sheet, and the
// legend's own line. Putting acronyms on the canvas means giving the offline
// style glyphs, which is a decision with its own reasons and is not this one.

import type {
  FilterSpecification,
  GeoJSONSourceSpecification,
  LayerSpecification,
} from '@maplibre/maplibre-gl-style-spec'
import type {
  GeoJSONSource,
  Map as MapLibreMap,
  MapMouseEvent,
  PointLike,
} from 'maplibre-gl'
import { NEUTRAL_BLAZE_COLOR } from '../lib/blaze'
import { clubBoundaryMiles, clubTimeline, type ClubSections } from '../lib/clubSections'
import { PROFILED_TRAIL } from '../lib/highlightDetail'
import type { Highlight } from '../lib/highlights'
import { trailPointAtMile, trailSlice, type TrailIndex } from '../lib/trailPosition'
import { POI_PIN_MIN_ZOOM } from './poiLayers'
import { whenStyleReady } from './styleReady'

export const CORRIDOR_SOURCE_ID = 'corridor'

export const CORRIDOR_UNATTRIBUTED_CASING_LAYER_ID = 'corridor-unattributed-casing'
export const CORRIDOR_UNATTRIBUTED_LAYER_ID = 'corridor-unattributed'
export const CORRIDOR_BOUNDARY_LAYER_ID = 'corridor-boundary'
export const CORRIDOR_HIGHLIGHT_LAYER_ID = 'corridor-highlight'

/** Which of this source's two kinds of feature a layer wants. Both ride in one
 *  source because they are one answer - the corridor read end to end - and a
 *  second source would be a second thing to keep in step. */
export const CORRIDOR_KIND_PROPERTY = 'corridor_kind'
export const UNATTRIBUTED_KIND = 'unattributed'
export const BOUNDARY_KIND = 'boundary'
export const HIGHLIGHT_KIND = 'highlight'

/** Where a highlight marker carries its id, so a tap resolves to a record.
 *  A property rather than the GeoJSON feature id, for the reason
 *  CLOSURE_ID_PROPERTY gives: MapLibre runs a string feature id through
 *  parseInt, and a highlight id is a slug. */
export const HIGHLIGHT_ID_PROPERTY = 'highlight_id'

/**
 * Where the corridor view gives way to the waypoint map.
 *
 * Its own name rather than POI_PIN_MIN_ZOOM inline, because the two are the
 * same number for one reason and could stop being: the seam is where the map
 * changes subject (features/POI_VISIBILITY.md), and both halves are keyed to
 * it so neither can drift alone.
 */
export const CORRIDOR_MAX_ZOOM = POI_PIN_MIN_ZOOM

/**
 * The dash rhythm on an unattributed run, in multiples of the line's width -
 * which is what MapLibre's `line-dasharray` counts in.
 *
 * @unvalidated Picked to sit near the 10/6 pixel rhythm WIREFRAMES.md §3
 * records the white blaze having used before dashes were dropped: on the
 * 4.5 px through-route width that is 9 px on and 5.9 px off. Nobody has looked
 * at it on a phone in daylight. What would settle it is the outdoor pass #105
 * already owes the rest of the map chrome.
 */
export const UNATTRIBUTED_DASH: readonly [number, number] = [2, 1.3]

export const BOUNDARY_RADIUS = 2.6

/**
 * A highlight's mark, in pixels.
 *
 * Bigger than a boundary tick and smaller than a waypoint pin: it is the one
 * thing on this map a hiker is meant to want to tap, and it competes with
 * nothing - the pins do not draw down here at all (POI_PIN_MIN_ZOOM).
 *
 * @unvalidated Picked against the approved mock-up rather than measured. What
 * would settle it is the same outdoor pass #105 owes the rest of the chrome.
 */
export const HIGHLIGHT_RADIUS = 5

/**
 * What the corridor has to know about the trail it is drawn over.
 *
 * Passed in rather than imported, and the widths are here for a stronger
 * reason than the colour is: the grey has to COVER the blaze, so the moment
 * the through-route gets wider and this does not, a white hairline reappears
 * down both sides of every unattributed run. Taking style.ts's own numbers
 * makes that impossible rather than unlikely. (Importing them would close a
 * cycle - style.ts is what builds these layers in.)
 */
export interface CorridorTrailPaint {
  casingColor: string
  /** What a selected or reachable thing is drawn in - the sheet's own blaze
   *  orange. Passed in for the reason the casing is: style.ts builds these. */
  selectionColor: string
  /** The blaze layer's width for the through-route. */
  blazeWidth: number
  /** The casing under it, already including its overhang. */
  casingWidth: number
}

interface CorridorProperties {
  [CORRIDOR_KIND_PROPERTY]: string
  /** Present only on a highlight mark. */
  [HIGHLIGHT_ID_PROPERTY]?: string
}

export interface CorridorFeatureCollection {
  type: 'FeatureCollection'
  features: Array<{
    type: 'Feature'
    geometry:
      | { type: 'MultiLineString'; coordinates: Array<Array<[number, number]>> }
      | { type: 'Point'; coordinates: [number, number] }
    properties: CorridorProperties
  }>
}

export const EMPTY_CORRIDOR: CorridorFeatureCollection = {
  type: 'FeatureCollection',
  features: [],
}

/**
 * The published attribution, in map coordinates.
 *
 * A run or a boundary the centerline index cannot place yields no coordinates
 * and is dropped. That is a gap in what this build knows rather than a
 * decision, and it is safe to drop for the reason closureBands gives about its
 * own: the words are elsewhere. A hiker who taps a stretch this declines to
 * draw still gets the club from lib/clubSections.ts, which never needed
 * geometry to answer.
 */
export function corridorFeatures(
  sections: ClubSections,
  index: TrailIndex,
): CorridorFeatureCollection {
  const timeline = clubTimeline(sections)

  const unattributed = sections.unattributed.flatMap((range) => {
    const lines = trailSlice(index, range.startMile, range.endMile)
    if (lines.length === 0) return []
    return [
      {
        type: 'Feature' as const,
        geometry: { type: 'MultiLineString' as const, coordinates: lines },
        properties: { [CORRIDOR_KIND_PROPERTY]: UNATTRIBUTED_KIND },
      },
    ]
  })

  const boundaries = clubBoundaryMiles(timeline).flatMap((mile) => {
    const point = trailPointAtMile(index, mile)
    if (point === null) return []
    return [
      {
        type: 'Feature' as const,
        geometry: { type: 'Point' as const, coordinates: point },
        properties: { [CORRIDOR_KIND_PROPERTY]: BOUNDARY_KIND },
      },
    ]
  })

  return { type: 'FeatureCollection', features: [...unattributed, ...boundaries] }
}

/**
 * The highlights, as one mark each at the start of the first A.T. leg (#858).
 *
 * A POINT rather than a line along the walk, and that is the two-colour
 * decision showing through: the trail's own colour means `blaze_color`, so a
 * highlight cannot recolour the ground it covers. It marks where the walk
 * BEGINS and the sheet says how far it runs - which is also the only thing
 * that stays true for a highlight whose other legs are on trails this map may
 * not be drawing (features/NEARBY_TRAILS.md: one chosen trail at a time).
 *
 * One mark, not every leg: a loop that leaves the A.T. and comes back is one
 * place on the corridor, and three marks for it would read as three walks.
 *
 * The FIRST leg that is on the A.T., rather than the first leg outright. All
 * ten entries published today are single-leg A.T. highlights, so nothing
 * exercises the difference yet - but a loop is naturally written in walking
 * order, and Franconia Ridge's is `[Falling Waters, A.T., Old Bridle Path]`.
 * Keyed off leg zero, that record would draw no mark at all and simply not be
 * on the map, which is the silent absence rather than the honest one.
 */
export function highlightFeatures(
  highlights: readonly Highlight[],
  index: TrailIndex,
): CorridorFeatureCollection {
  const features = highlights.flatMap((highlight) => {
    const leg = highlight.legs.find((candidate) => candidate.trail === PROFILED_TRAIL)
    // A highlight entirely off the A.T. has no place on this map to mark. It
    // still exists as a record; features/NEARBY_TRAILS.md's one-trail-at-a-time
    // rule is what would eventually draw it.
    if (leg === undefined) return []
    const point = trailPointAtMile(index, leg.startMile)
    if (point === null) return []
    return [
      {
        type: 'Feature' as const,
        geometry: { type: 'Point' as const, coordinates: point },
        properties: {
          [CORRIDOR_KIND_PROPERTY]: HIGHLIGHT_KIND,
          [HIGHLIGHT_ID_PROPERTY]: highlight.id,
        },
      },
    ]
  })
  return { type: 'FeatureCollection', features }
}

/** The corridor and the highlights in one collection - one source, because
 *  they are one answer about the same stretch of map. */
export function corridorWithHighlights(
  sections: ClubSections,
  highlights: readonly Highlight[],
  index: TrailIndex,
): CorridorFeatureCollection {
  const corridor = corridorFeatures(sections, index)
  return {
    type: 'FeatureCollection',
    features: [...corridor.features, ...highlightFeatures(highlights, index).features],
  }
}

/**
 * The corridor source, empty.
 *
 * Empty for the reason buildClosureSource is: the attribution is read out of
 * IndexedDB well after the map is built, and re-reading a style to add it would
 * drop the WebGL context underneath the hiker.
 */
export function buildCorridorSource(): GeoJSONSourceSpecification {
  return { type: 'geojson', data: { type: 'FeatureCollection', features: [] } }
}

const isKind = (kind: string): FilterSpecification => [
  '==',
  ['get', CORRIDOR_KIND_PROPERTY],
  kind,
]

/**
 * The layers, in draw order, given the trail's own paint.
 */
export function buildCorridorLayers({
  casingColor,
  selectionColor,
  blazeWidth,
  casingWidth,
}: CorridorTrailPaint): LayerSpecification[] {
  return [
    {
      id: CORRIDOR_UNATTRIBUTED_CASING_LAYER_ID,
      type: 'line' as const,
      source: CORRIDOR_SOURCE_ID,
      maxzoom: CORRIDOR_MAX_ZOOM,
      filter: isKind(UNATTRIBUTED_KIND),
      layout: { 'line-cap': 'butt' as const, 'line-join': 'round' as const },
      paint: {
        'line-color': casingColor,
        'line-width': casingWidth,
      },
    },
    {
      id: CORRIDOR_UNATTRIBUTED_LAYER_ID,
      type: 'line' as const,
      source: CORRIDOR_SOURCE_ID,
      maxzoom: CORRIDOR_MAX_ZOOM,
      filter: isKind(UNATTRIBUTED_KIND),
      // Butt caps, which is what a measured dash rhythm needs: round caps add
      // half a width at each end of every dash and quietly close the gaps the
      // rhythm is made of. WIREFRAMES.md §3 records the same reasoning from
      // when the blazes themselves were dashed.
      layout: { 'line-cap': 'butt' as const, 'line-join': 'round' as const },
      paint: {
        'line-color': NEUTRAL_BLAZE_COLOR,
        'line-width': blazeWidth,
        'line-dasharray': [...UNATTRIBUTED_DASH],
      },
    },
    {
      id: CORRIDOR_BOUNDARY_LAYER_ID,
      type: 'circle' as const,
      source: CORRIDOR_SOURCE_ID,
      maxzoom: CORRIDOR_MAX_ZOOM,
      filter: isKind(BOUNDARY_KIND),
      paint: {
        // Ringed rather than plain, so one mark reads on the pale sheet and on
        // ink without being two marks. The ring is the casing colour and the
        // fill is the blaze's, which keeps this inside the two colours the
        // corridor view is allowed.
        'circle-radius': BOUNDARY_RADIUS,
        'circle-color': NEUTRAL_BLAZE_COLOR,
        'circle-stroke-color': casingColor,
        'circle-stroke-width': 1,
      },
    },
    // LAST, over the boundary ticks - because at these zooms the two collide
    // often, not rarely. Reasoned from the projection and the club count
    // rather than measured off a render: at z5 Web Mercator gives 29.7 px per
    // degree of latitude at 40 degrees N, so a pixel is ~2.3 straight-line
    // miles, and the A.T.'s 2,197 miles fit inside ~780 straight-line ones -
    // call it 6 trail miles to the pixel. HIGHLIGHT_RADIUS is 5 px, so a mark
    // covers tens of trail miles, against an average gap between club
    // boundaries of 2,197 / ~30 = ~73 miles. Drawn the other way round a
    // neutral tick punches a hole through the one thing on this map a hiker is
    // meant to tap.
    {
      id: CORRIDOR_HIGHLIGHT_LAYER_ID,
      type: 'circle' as const,
      source: CORRIDOR_SOURCE_ID,
      maxzoom: CORRIDOR_MAX_ZOOM,
      filter: isKind(HIGHLIGHT_KIND),
      paint: {
        // The selection colour, which is the one hue this view has beyond the
        // blaze and the neutral - and it is spent here because a highlight is
        // the thing on this map a hiker is meant to reach for.
        'circle-radius': HIGHLIGHT_RADIUS,
        'circle-color': selectionColor,
        'circle-stroke-color': casingColor,
        'circle-stroke-width': 1.5,
      },
    },
  ]
}

/**
 * How far off a highlight mark a touch may land and still open it, in CSS
 * pixels.
 *
 * Derived from the mark the same way LINE_TAP_SLOP_PX is derived from the
 * widest line: `--min-touch-target` is 44 px, the mark is a circle of
 * HIGHLIGHT_RADIUS, and the slop is what turns one into the other.
 */
export const HIGHLIGHT_TAP_SLOP_PX = Math.max(0, (44 - HIGHLIGHT_RADIUS * 2) / 2)

function highlightTapBox(point: { x: number; y: number }): [PointLike, PointLike] {
  return [
    [point.x - HIGHLIGHT_TAP_SLOP_PX, point.y - HIGHLIGHT_TAP_SLOP_PX],
    [point.x + HIGHLIGHT_TAP_SLOP_PX, point.y + HIGHLIGHT_TAP_SLOP_PX],
  ]
}

/**
 * The highlight mark under a point, or null.
 *
 * Exported so map/lineTaps.ts can YIELD to it: a mark is a small, aimed-at
 * target sitting on the corridor, and the line under it is the ambient thing.
 * That is the same rule tappedLineAt already applies to pins and ATC notices.
 */
export function highlightIdAt(
  map: MapLibreMap,
  point: { x: number; y: number } | undefined,
): string | null {
  // A click carrying no screen point at all. Real MapLibre always supplies
  // one, but this app's own route-drawing flow emits clicks built by hand, and
  // a tap handler that throws on an event shape it did not expect takes the
  // whole map down with it - which is what this cost before the guard existed.
  if (point === undefined || !Number.isFinite(point.x) || !Number.isFinite(point.y)) {
    return null
  }
  // Querying a layer the style does not hold fires an error event rather than
  // throwing - the guard poiTaps.ts documents.
  if (map.getLayer(CORRIDOR_HIGHLIGHT_LAYER_ID) === undefined) return null
  const features = map.queryRenderedFeatures(highlightTapBox(point), {
    layers: [CORRIDOR_HIGHLIGHT_LAYER_ID],
  })
  for (const feature of features) {
    const id = (feature.properties ?? {})[HIGHLIGHT_ID_PROPERTY]
    if (typeof id === 'string' && id !== '') return id
  }
  return null
}

/** Wires taps on the highlight marks to `onSelect`, and returns a detach.
 *
 *  Every tap reports, misses included, which is how the sheet closes on a tap
 *  elsewhere - the gesture attachLineTaps already teaches. */
export function attachHighlightTaps(
  map: MapLibreMap,
  onSelect: (id: string | null) => void,
): () => void {
  const onClick = (event: MapMouseEvent) => {
    onSelect(highlightIdAt(map, event.point))
  }
  map.on('click', onClick)
  return () => {
    map.off('click', onClick)
  }
}

/** Pushes the drawn corridor onto the live map's source, and returns a detach. */
export function attachCorridorData(
  map: MapLibreMap,
  collection: CorridorFeatureCollection,
): () => void {
  return whenStyleReady(
    map,
    () => map.getSource(CORRIDOR_SOURCE_ID) !== undefined,
    () => {
      // `getSource` answers with the union of every source kind, and only the
      // GeoJSON one can be handed new data - same guard as attachClosureData.
      const source = map.getSource<GeoJSONSource>(CORRIDOR_SOURCE_ID)
      if (source === undefined || typeof source.setData !== 'function') return

      source.setData(collection as never)
    },
    'corridor attribution',
  )
}
