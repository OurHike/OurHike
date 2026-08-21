// Volunteer workdays on the canvas: the source, the one symbol layer that
// draws them, and the tap that turns a pin back into a project id (#760,
// features/VOLUNTEERING.md Phase B).
//
// warningLayers.ts's shape, with the differences a workday actually has.
//
// **THE STALENESS CEILING IS ENFORCED BY DRAWING NOTHING.** lib/workProjects.ts
// replaces the Volunteer tab's list with an out-of-date notice past
// OPPORTUNITIES_STALE_MS, on the grounds that "a hedged invitation still reads
// as an invitation". A pin has no hedged form at all - it is a dot on a map
// that a hiker walks to - so past the ceiling the shell passes an empty set
// and this layer draws nothing. That is not a degraded state to apologise for:
// the tab still says, in words, that the feed is out of date, and a hiker who
// sees no pins and reads that sentence has been told the truth. Sending
// somebody to a trailhead for a workday cancelled on Thursday is this
// feature's own failure mode.
//
// **NO MINZOOM, LIKE THE WARNING PINS AND UNLIKE THE WAYPOINTS.** The POI layer
// starts at z9 because eight hundred pins on the whole corridor is a texture
// rather than a map. There will be a handful of workdays on 2,197 miles, and
// zoomed out to plan a weekend is precisely when somebody wants to see where
// they are.
//
// **THE COLLISION ENGINE DECIDES, unlike the warning pins.** A serious warning
// sets `icon-allow-overlap` because a warning dropped is a warning nobody was
// shown. A workday is an invitation, and one hidden behind a shelter pin costs
// a hiker nothing they were relying on - the Volunteer tab lists every one of
// them, sorted by distance, which is the surface that promises completeness.
// Letting a workday shove a waypoint aside would be this feature pressing on
// the map, which is the thing VOLUNTEERING.md §5 keeps saying not to do.

import type {
  GeoJSONSourceSpecification,
  LayerSpecification,
} from '@maplibre/maplibre-gl-style-spec'
import type {
  GeoJSONSource,
  Map as MapLibreMap,
  MapMouseEvent,
  PointLike,
} from 'maplibre-gl'
import { POI_PIN_PIXEL_RATIO, POI_PIN_SIZE } from './poiIcons'
import { buildWorkdayIcon, WORKDAY_ICON_ID } from './workdayPin'
import { whenStyleReady } from './styleReady'

export const WORKDAY_SOURCE_ID = 'work-projects'
export const WORKDAY_LAYER_ID = 'work-project-pins'

/** Where a pin carries its project id - a property rather than the feature
 *  id, for poiLayers.ts's reason: MapLibre runs a string feature id through
 *  `parseInt`, and a reviewed row's id is not a number. */
export const WORKDAY_ID_PROPERTY = 'project_id'

/** A workday reduced to what the canvas needs. The shell does the windowing,
 *  the staleness check and the placement; this draws points. */
export interface WorkdayPoint {
  id: string
  lon: number
  lat: number
}

export interface WorkdayFeatureCollection {
  type: 'FeatureCollection'
  features: Array<{
    type: 'Feature'
    id: string
    geometry: { type: 'Point'; coordinates: [number, number] }
    properties: { [WORKDAY_ID_PROPERTY]: string }
  }>
}

export function workdayFeatureCollection(
  workdays: readonly WorkdayPoint[],
): WorkdayFeatureCollection {
  return {
    type: 'FeatureCollection',
    features: workdays.map((workday) => ({
      type: 'Feature',
      id: workday.id,
      geometry: { type: 'Point', coordinates: [workday.lon, workday.lat] },
      properties: { [WORKDAY_ID_PROPERTY]: workday.id },
    })),
  }
}

export function buildWorkdaySource(): GeoJSONSourceSpecification {
  return { type: 'geojson', data: { type: 'FeatureCollection', features: [] } }
}

export function buildWorkdayLayer(
  sourceId: string = WORKDAY_SOURCE_ID,
): LayerSpecification {
  return {
    id: WORKDAY_LAYER_ID,
    type: 'symbol',
    source: sourceId,
    layout: {
      'icon-image': WORKDAY_ICON_ID,
      'icon-size': 1,
      'icon-padding': 2,
    },
  }
}

/** Registers the workday pin image on a live map, and returns a detach. */
export function attachWorkdayIcon(map: MapLibreMap): () => void {
  return whenStyleReady(
    map,
    // The layer existing proves the style spec is parsed, which is the
    // condition addImage actually requires - the question attachWarningIcon
    // and attachPoiIcons both ask.
    () => map.getLayer(WORKDAY_LAYER_ID) !== undefined,
    () => {
      // Images outlive a style reload, and re-adding one throws.
      if (!map.hasImage(WORKDAY_ICON_ID)) {
        map.addImage(WORKDAY_ICON_ID, buildWorkdayIcon(POI_PIN_SIZE), {
          pixelRatio: POI_PIN_PIXEL_RATIO,
        })
      }
    },
    'workday pin image',
  )
}

/** Pushes the workdays onto the live map's source, and returns a detach.
 *
 *  An empty array is a legitimate and frequent argument: it is what the shell
 *  passes when the feed is stale, when nothing falls inside the fourteen-day
 *  window, and when no club has posted anything. All three draw the same empty
 *  map, and the Volunteer tab is where the three are told apart in words. */
export function attachWorkdayData(
  map: MapLibreMap,
  workdays: readonly WorkdayPoint[],
): () => void {
  return whenStyleReady(
    map,
    () => map.getSource(WORKDAY_SOURCE_ID) !== undefined,
    () => {
      const source = map.getSource<GeoJSONSource>(WORKDAY_SOURCE_ID)
      if (source === undefined || typeof source.setData !== 'function') return

      source.setData(workdayFeatureCollection(workdays) as never)
    },
    'work projects',
  )
}

/** `--min-touch-target` (chrome/chrome.css), the same one poiTaps.ts derives
 *  its slop from - and derived the same way rather than restated, so the two
 *  cannot drift apart the day the pin size moves. */
const MIN_TOUCH_TARGET_PX = 44
export const WORKDAY_TAP_SLOP_PX = Math.max(0, (MIN_TOUCH_TARGET_PX - POI_PIN_SIZE) / 2)

/** Which workday that touch landed on, or null. A box rather than a point,
 *  for poiTaps.ts's reason: this app is used with a gloved thumb in rain, and
 *  a pin that only opens when hit dead centre reads as one that does not
 *  open. */
export function workdayIdAt(
  map: MapLibreMap,
  point: { x: number; y: number },
): string | null {
  if (map.getLayer(WORKDAY_LAYER_ID) === undefined) return null

  const box: [PointLike, PointLike] = [
    [point.x - WORKDAY_TAP_SLOP_PX, point.y - WORKDAY_TAP_SLOP_PX],
    [point.x + WORKDAY_TAP_SLOP_PX, point.y + WORKDAY_TAP_SLOP_PX],
  ]

  const hits = map.queryRenderedFeatures(box, { layers: [WORKDAY_LAYER_ID] })
  const id = hits[0]?.properties?.[WORKDAY_ID_PROPERTY]
  return typeof id === 'string' && id !== '' ? id : null
}

/** Reports the workday under each tap. Returns a detach. */
export function attachWorkdayTaps(
  map: MapLibreMap,
  onSelect: (projectId: string) => void,
): () => void {
  const onClick = (event: MapMouseEvent) => {
    const id = workdayIdAt(map, event.point)
    if (id !== null) onSelect(id)
  }

  map.on('click', onClick)
  return () => {
    map.off('click', onClick)
  }
}
