// The ATC's trail updates on the canvas: a second band source, and the tap
// that turns one back into an update.
//
// Deliberately a SEPARATE SOURCE from `closures` rather than extra features in
// that one. Two reasons, and the second is the load-bearing one:
//
//  - The two are drawn with different dasharrays (lib/atcUpdateStyle.ts), and
//    a dasharray is a paint property of a layer rather than of a feature, so
//    one source could not carry both rhythms without a data-driven expression
//    MapLibre does not support for `line-dasharray`.
//  - A tap has to be able to answer *which kind of thing* it landed on. With
//    one source, `queryRenderedFeatures` would hand back a band and the shell
//    would have to parse the id to find out whether an ATC sheet or a closure
//    sheet should open. Parsing an id to recover a type is how the wrong sheet
//    eventually opens over the wrong thing.
//
// Everything else is closureLayers.ts's shape, on purpose - the geometry path
// is shared (`trailSlice` -> `closureBands`), and only the source id and the
// layers it is queried against differ.
//
// ONE SOURCE, TWO GEOMETRIES. Within that source a notice is a line or a
// point, because most of what ATC publishes is a single mile marker rather
// than a stretch and `trailSlice` renders those as a few dozen feet of
// invisible line. A `line` layer ignores Point features and a `circle` layer
// ignores lines, so both draw from one source - which is also what keeps the
// tap below asking one question instead of two.

import type { GeoJSONSourceSpecification } from '@maplibre/maplibre-gl-style-spec'
import type {
  GeoJSONSource,
  Map as MapLibreMap,
  MapMouseEvent,
  PointLike,
} from 'maplibre-gl'
import { ATC_UPDATE_LAYER_ID, ATC_UPDATE_POINT_LAYER_ID } from '../lib/atcUpdateStyle'
import { atcBandId, type AtcUpdate } from '../lib/atcUpdates'
import { trailPointAtMile, type TrailIndex } from '../lib/trailPosition'
import { closureFeatureCollection, type ClosureBand } from './closureLayers'
import { whenStyleReady } from './styleReady'

export const ATC_UPDATE_SOURCE_ID = 'atc-updates'

/** Where a band carries its update's id - the same property name and the same
 *  reason as closureLayers.ts's: MapLibre runs a string feature id through
 *  `parseInt`, and `atc:va-creeper-trail-closure-detour` is not a number. */
export const ATC_UPDATE_ID_PROPERTY = 'closure_id'

/**
 * The source, empty.
 *
 * Empty for the same reason the closure and POI sources are: the updates
 * arrive from the network well after the map is built, and re-reading a style
 * to add them would drop the WebGL context underneath the hiker.
 */
export function buildAtcUpdateSource(): GeoJSONSourceSpecification {
  return { type: 'geojson', data: { type: 'FeatureCollection', features: [] } }
}

/** One notice at a single mile, placed on the centerline. */
export interface AtcUpdatePoint {
  id: string
  at: [number, number]
}

/**
 * The point notices that can actually be placed, in map coordinates.
 *
 * An update whose mile falls outside this build's centerline yields nothing -
 * a gap in what the build knows rather than a decision, exactly as
 * `closureBands` treats an unplaceable range. It is still not lost: the banner
 * needs only a mile number, so a hiker is told about it either way.
 */
export function atcUpdatePoints(
  updates: readonly AtcUpdate[],
  index: TrailIndex,
): AtcUpdatePoint[] {
  return updates.flatMap((update) => {
    const at = trailPointAtMile(index, update.start_mile_marker)
    return at === null ? [] : [{ id: atcBandId(update), at }]
  })
}

/**
 * Bands and points as one FeatureCollection.
 *
 * Both geometries in one source, which is what lets a `line` layer and a
 * `circle` layer draw from it without either seeing the other's features -
 * and, more usefully, what lets a tap ask one source what it hit.
 */
export function atcFeatureCollection(
  bands: readonly ClosureBand[],
  points: readonly AtcUpdatePoint[],
) {
  const lines = closureFeatureCollection(bands)
  return {
    type: 'FeatureCollection' as const,
    features: [
      ...lines.features,
      ...points.map((point) => ({
        type: 'Feature' as const,
        id: point.id,
        geometry: { type: 'Point' as const, coordinates: point.at },
        properties: { [ATC_UPDATE_ID_PROPERTY]: point.id },
      })),
    ],
  }
}

/** Pushes ATC bands and points onto the live map's source, and returns a
 *  detach. */
export function attachAtcUpdateData(
  map: MapLibreMap,
  bands: readonly ClosureBand[],
  points: readonly AtcUpdatePoint[] = [],
): () => void {
  return whenStyleReady(
    map,
    () => map.getSource(ATC_UPDATE_SOURCE_ID) !== undefined,
    () => {
      const source = map.getSource<GeoJSONSource>(ATC_UPDATE_SOURCE_ID)
      if (source === undefined || typeof source.setData !== 'function') return

      source.setData(atcFeatureCollection(bands, points) as never)
    },
    'ATC update bands',
  )
}

/** `--min-touch-target` (chrome/chrome.css), the same floor every other
 *  control on the map screen meets. A band is 10px of line on a screen a
 *  hiker is squinting at in the sun; the slop is what makes it tappable. */
const MIN_TOUCH_TARGET_PX = 44

/** Half the shortfall between the band's drawn width and a touch target,
 *  so a near miss on either side still counts. Derived rather than chosen,
 *  for the reason poiTaps.ts gives about the same constant. */
export const ATC_TAP_SLOP_PX = MIN_TOUCH_TARGET_PX / 2

export function atcTapBox(point: { x: number; y: number }): [PointLike, PointLike] {
  return [
    [point.x - ATC_TAP_SLOP_PX, point.y - ATC_TAP_SLOP_PX],
    [point.x + ATC_TAP_SLOP_PX, point.y + ATC_TAP_SLOP_PX],
  ]
}

/** The ATC band under a point on the canvas, by band id, or null. */
export function atcBandIdAt(
  map: MapLibreMap,
  point: { x: number; y: number },
): string | null {
  // Both layers, because both draw ATC notices and a hiker aiming at one does
  // not know which geometry it happens to be. Only the ones the style actually
  // holds are queried: asking for a layer it does not have fires an error
  // event rather than throwing, so a touch on a map whose style has not parsed
  // should be silent rather than a warning in the console.
  const layers = [ATC_UPDATE_LAYER_ID, ATC_UPDATE_POINT_LAYER_ID].filter(
    (layer) => map.getLayer(layer) !== undefined,
  )
  if (layers.length === 0) return null

  const [feature] = map.queryRenderedFeatures(atcTapBox(point), { layers })
  if (feature === undefined) return null

  const id = feature.properties?.[ATC_UPDATE_ID_PROPERTY]
  return typeof id === 'string' && id !== '' ? id : null
}

/**
 * Wires taps on the ATC band layer to `onSelect`, and returns a detach.
 *
 * Only hits report, unlike `attachPoiTaps`, which reports its misses too so
 * that tapping bare map closes the waypoint card. The ATC sheet is dismissed
 * by its own close button and by opening something else; making every tap on
 * the map report here as well would mean two independent handlers racing to
 * decide what a single touch on empty ground means.
 */
export function attachAtcUpdateTaps(
  map: MapLibreMap,
  onSelect: (bandId: string) => void,
): () => void {
  const onClick = (event: MapMouseEvent) => {
    const id = atcBandIdAt(map, event.point)
    if (id !== null) onSelect(id)
  }

  map.on('click', onClick)
  return () => {
    map.off('click', onClick)
  }
}
