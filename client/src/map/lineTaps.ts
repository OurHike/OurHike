// Tapping a trail line: turning a point on the canvas back into the line's
// published facts, for the line-detail sheet (#134).
//
// Modelled on poiTaps.ts, and like it this module deliberately does NOT know
// what a sheet is - it answers "which line did that touch land on", and the
// shell decides what to show. WIREFRAMES.md §3's blaze rules are the
// requirement: "tapping any line opens a sheet naming the blaze and its
// source, and says plainly when it's unknown."
//
// Two rules of its own, both about what a line tap must yield to:
//
// **Anything tappable that is not a line wins.** A pin, a dot or an ATC
// notice under the thumb is a smaller, aimed-at target sitting ON a line -
// spurs exist to lead to shelters, so a shelter pin almost always has a blue
// line under it. A tap those handlers claim reports null here, which is also
// what dismisses an open line sheet when the hiker moves on to a pin.
//
// **Among lines, a side trail beats the through-route.** The AT is on screen
// almost everywhere, drawn wider, and sorted above side trails - so a raw
// topmost-first query answers "the AT" for every tap near a junction, which
// is exactly where a hiker is asking about the spur. The narrow line is the
// deliberate target; the wide one is the ambient one.

import type { Map as MapLibreMap, MapMouseEvent, PointLike } from 'maplibre-gl'
import { atcBandIdAt } from './atcUpdateLayers'
import { poiIdAt } from './poiTaps'
import { BLAZE_LAYER_ID, PRIMARY_TRAIL_SOURCES, PRIMARY_TRAIL_WIDTH } from './style'

/** `--min-touch-target` (chrome/chrome.css), same as every other control. */
const MIN_TOUCH_TARGET_PX = 44

/**
 * How far off a line a touch may land and still open it, in CSS pixels.
 *
 * Derived from the widest line the layer draws, the way POI_TAP_SLOP_PX is
 * derived from the pin size - the through-route is PRIMARY_TRAIL_WIDTH and
 * everything else is narrower, so this rounds the hit area UP for the thin
 * lines, which is the direction a gloved thumb needs.
 */
export const LINE_TAP_SLOP_PX = Math.max(
  0,
  (MIN_TOUCH_TARGET_PX - PRIMARY_TRAIL_WIDTH) / 2,
)

/** What the shell learns about a tapped line: the feature's own published
 *  properties, verbatim. `id` joins spurs.json; `source` and `blazeColor`
 *  are what the sheet names; `name` is ATC's, where they gave one. */
export interface TappedLine {
  id: string | null
  source: string | null
  name: string | null
  blazeColor: string | null
  /**
   * A point ON the tapped line, nearest the touch - not the touch itself.
   *
   * For callers that need a MILE rather than a feature: the corridor view's
   * club sheet (#598) turns this into one through lib/trailPosition.ts's
   * `mileOnTrail`, which refuses anything further than MAX_OFF_TRAIL_MILES
   * from the centerline.
   *
   * Snapped rather than unprojected, and the seam is why. LINE_TAP_SLOP_PX is
   * ~20 px, which is a thumb's width at any zoom - but in GROUND terms it is
   * about 90 miles at the corridor view's opening camera (z4.87, where a pixel
   * spans some 4.6 miles). The raw touch would sit far outside that 3-mile
   * tolerance for a tap the map had already decided landed on the trail, so
   * the sheet would refuse to open on most of the taps it exists for.
   */
  at: [number, number]
}

/** The touch, as the box that is actually queried. */
export function lineTapBox(point: { x: number; y: number }): [PointLike, PointLike] {
  return [
    [point.x - LINE_TAP_SLOP_PX, point.y - LINE_TAP_SLOP_PX],
    [point.x + LINE_TAP_SLOP_PX, point.y + LINE_TAP_SLOP_PX],
  ]
}

function stringProp(
  properties: Record<string, unknown> | null | undefined,
  key: string,
): string | null {
  const value = properties?.[key]
  return typeof value === 'string' && value !== '' ? value : null
}

/** Every coordinate of a LineString or MultiLineString, flat. Both shapes are
 *  real here for the reason export_trails.py's geometry_to_wkt gives: treating
 *  them as one type is how trail mileage gets silently dropped. */
function* coordinatesOf(geometry: unknown): Generator<[number, number]> {
  const shape = geometry as { type?: string; coordinates?: unknown } | null | undefined
  const coordinates = shape?.coordinates
  if (!Array.isArray(coordinates)) return
  if (shape?.type === 'LineString') {
    for (const point of coordinates) {
      if (Array.isArray(point) && point.length >= 2)
        yield [point[0] as number, point[1] as number]
    }
  } else if (shape?.type === 'MultiLineString') {
    for (const part of coordinates) {
      if (!Array.isArray(part)) continue
      for (const point of part) {
        if (Array.isArray(point) && point.length >= 2)
          yield [point[0] as number, point[1] as number]
      }
    }
  }
}

/**
 * The vertex of `geometry` closest to `near`, or `near` itself when the
 * feature carries no usable coordinates.
 *
 * Squared degrees rather than great-circle metres, deliberately: this is
 * picking the nearest of a handful of candidates on one screen, where the two
 * orderings agree, and lib/trailPosition.ts does the real distance work
 * afterwards.
 */
function nearestVertex(geometry: unknown, near: [number, number]): [number, number] {
  let best = near
  let bestDistance = Infinity
  for (const [lon, lat] of coordinatesOf(geometry)) {
    const dLon = lon - near[0]
    const dLat = lat - near[1]
    const distance = dLon * dLon + dLat * dLat
    if (distance < bestDistance) {
      bestDistance = distance
      best = [lon, lat]
    }
  }
  return best
}

function asTappedLine(
  feature: { properties?: Record<string, unknown> | null; geometry?: unknown },
  near: [number, number],
): TappedLine {
  return {
    id: stringProp(feature.properties, 'id'),
    source: stringProp(feature.properties, 'source'),
    name: stringProp(feature.properties, 'name'),
    blazeColor: stringProp(feature.properties, 'blaze_color'),
    at: nearestVertex(feature.geometry, near),
  }
}

/**
 * The line under a point on the canvas, or null for bare map and for
 * anything a more specific handler already answers.
 */
export function tappedLineAt(
  map: MapLibreMap,
  point: { x: number; y: number },
): TappedLine | null {
  // Before the style has parsed, querying a layer it does not hold fires an
  // error event rather than throwing - same guard as poiTaps.ts.
  if (map.getLayer(BLAZE_LAYER_ID) === undefined) return null

  // Rule 1: a pin, dot or ATC notice under the thumb is what the hiker
  // aimed at, and their handlers will act on this same click.
  if (poiIdAt(map, point) !== null) return null
  if (atcBandIdAt(map, point) !== null) return null

  const features = map.queryRenderedFeatures(lineTapBox(point), {
    layers: [BLAZE_LAYER_ID],
  })
  if (features.length === 0) return null

  // Rule 2: the narrow, specific line over the wide, ambient one. Among
  // several side trails (a genuinely crowded junction) the topmost wins,
  // which MapLibre already puts first.
  const sideTrail = features.find(
    (feature) =>
      !PRIMARY_TRAIL_SOURCES.includes(stringProp(feature.properties, 'source') ?? ''),
  )
  const touch = map.unproject([point.x, point.y])
  return asTappedLine(sideTrail ?? features[0], [touch.lng, touch.lat])
}

/**
 * Wires taps on the trail lines to `onSelect`, and returns a detach function.
 *
 * Every tap reports, including the misses: the line's facts when the touch
 * lands on one, null otherwise - which is how the sheet closes on a tap
 * elsewhere, the gesture every map card teaches. MapLibre withholds the
 * click when the gesture was a pan, so riding the map with the sheet open
 * never throws it away.
 *
 * No cursor handling here, deliberately: poiTaps.ts already owns the
 * canvas cursor, and a second writer would fight it on every mousemove.
 */
export function attachLineTaps(
  map: MapLibreMap,
  onSelect: (line: TappedLine | null) => void,
): () => void {
  const onClick = (event: MapMouseEvent) => {
    onSelect(tappedLineAt(map, event.point))
  }

  map.on('click', onClick)
  return () => {
    map.off('click', onClick)
  }
}
