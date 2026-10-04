// Putting decision 67's hazard areas on the map (#1805): the source, the
// layers, and the two imperative pokes the shell makes at a live map.
//
// The drawing is the one the maintainer chose (decisions-64-67-mock.html §4,
// option A): the area washed in blaze orange at low opacity with a dashed
// edge in the same orange, UNDER the trail, so the line a hiker follows is
// drawn over it whole and in its own colour. Nothing about it says closed:
// no barrier tape, no red, no hatching - lib/closureStyle.ts owns those, and
// a hunting area drawn in a closure's register would tell a hiker the trail
// is shut when the land manager says it is open (lib/hazardAreas.ts).
//
// A shooting site is a point, drawn as a dot in the same orange with a dashed
// ring, at the same place in the stack.
//
// ONE HONEST WEAKNESS, as lib/droughtStyle.ts states its own: the area leans
// on hue and a dashed edge, two channels, and the card carries the words.
// The dash is what separates it from the drought wash under it, which has no
// edge at all.
//
// Only the style half lives here, because the style is built at launch. The
// data and the taps are map/hazardAreaTaps.ts, loaded the first time there is
// an area to draw: a phone with no hazard area on its trails never parses
// them (features/LAUNCH_BUDGET.md §3).

import type {
  GeoJSONSourceSpecification,
  LayerSpecification,
} from '@maplibre/maplibre-gl-style-spec'

export const HAZARD_SOURCE_ID = 'hazard-areas'
export const HAZARD_FILL_LAYER_ID = 'hazard-area-fill'
export const HAZARD_EDGE_LAYER_ID = 'hazard-area-edge'
export const HAZARD_POINT_LAYER_ID = 'hazard-area-point'

/** The mock's blaze orange (`--blaze-orange`, #c1611a), a step lighter on a
 *  dark sheet so the dashed edge reads against it. */
export function hazardColor(dark: boolean): string {
  return dark ? '#de8a47' : '#c1611a'
}

/** The mock's `opacity: .18` on the wash: enough to see the area, little
 *  enough that contours and the trail casing read straight through it. */
export const HAZARD_FILL_OPACITY = 0.18

/** An empty source, filled once the notices land - `buildDroughtSource`'s
 *  reason: a style naming a source it does not have drops the WebGL context. */
export function buildHazardSource(): GeoJSONSourceSpecification {
  return { type: 'geojson', data: { type: 'FeatureCollection', features: [] } }
}

/** The three layers, in stack order: wash, edge, point. */
export function buildHazardLayers(sourceId: string, dark: boolean): LayerSpecification[] {
  const color = hazardColor(dark)
  return [
    {
      id: HAZARD_FILL_LAYER_ID,
      type: 'fill',
      source: sourceId,
      filter: ['==', ['geometry-type'], 'Polygon'],
      paint: { 'fill-color': color, 'fill-opacity': HAZARD_FILL_OPACITY },
    },
    {
      id: HAZARD_EDGE_LAYER_ID,
      type: 'line',
      source: sourceId,
      filter: ['==', ['geometry-type'], 'Polygon'],
      paint: { 'line-color': color, 'line-width': 1.5, 'line-dasharray': [4, 3] },
    },
    {
      id: HAZARD_POINT_LAYER_ID,
      type: 'circle',
      source: sourceId,
      filter: ['==', ['geometry-type'], 'Point'],
      paint: {
        'circle-radius': 7,
        'circle-color': color,
        'circle-opacity': 0.35,
        'circle-stroke-color': color,
        'circle-stroke-width': 1.5,
      },
    },
  ]
}
