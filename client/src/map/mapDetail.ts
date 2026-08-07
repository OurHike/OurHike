// The detail level: how much of the live sheet is drawn (MAP_STYLE_SPEC.md).
//
// The complaint this answers is "too much detail" - a sheet that draws
// everything it knows is a sheet a hiker has to read past to find the trail.
// The fix is PURE LAYER VISIBILITY, the same displayed-only rule every other
// map preference on this screen keeps (`attachContourUnits`,
// `attachMapAppearance`): `setLayoutProperty(id, 'visibility', ...)` on a
// live map, never a style rebuild, so thinning the sheet costs nothing a
// hiker is holding - not the camera, not the tiles in flight, not the WebGL
// context.
//
// What each level means is a judgement about hiker signal, not a percentage:
//
//  - `full` draws the whole sheet, admin borders included.
//  - `standard` (the default) drops only the borders: wanted sometimes,
//    distracting mostly - a state line is the rare fact a hiker plans around,
//    and it is one tap away.
//  - `minimal` keeps what terrain and navigation need and drops the rest.
//    Index contours STAY, so the shape of the land still reads - dropping
//    every contour turns a topo sheet into a road map. Paths STAY, because a
//    side trail is hiker signal, not clutter - it is the thing the live sheet
//    exists to show. What goes is the fine grain: minor contours and their
//    labels, tracks and minor roads, water labels, and the scrub overprint.
//
// The downloaded raster background has no layers to thin; on it the probe
// below never resolves and detach ends the wait, exactly as
// attachSheetAppearance treats the same absence.

import type { Map as MapLibreMap } from 'maplibre-gl'
import type { LayerDetailLevel } from '../lib/userPreferences'
import { LIVE_TOPO_LAYER_IDS } from './liveTopo'
import { whenStyleReady } from './styleReady'

/**
 * The layers each level hides. Spelled as what is HIDDEN rather than what is
 * shown, because the sheet's layer stack is liveTopo.ts's to own and grow -
 * a new layer added there is visible at every level until a line here says
 * otherwise, which is the right default for a map that must not silently
 * lose information.
 *
 * `minimal` is a superset of `standard` by construction rather than by
 * discipline: the spec's matrix is cumulative, and building it that way here
 * means a layer demoted out of `standard` cannot accidentally survive in
 * `minimal`.
 */
const STANDARD_HIDES: readonly string[] = [LIVE_TOPO_LAYER_IDS.boundary]

const MINIMAL_HIDES: readonly string[] = [
  ...STANDARD_HIDES,
  LIVE_TOPO_LAYER_IDS.track,
  LIVE_TOPO_LAYER_IDS.roadMinor,
  LIVE_TOPO_LAYER_IDS.contour,
  LIVE_TOPO_LAYER_IDS.contourLabel,
  LIVE_TOPO_LAYER_IDS.waterLabel,
  LIVE_TOPO_LAYER_IDS.scrub,
]

export const DETAIL_HIDDEN_LAYERS: Record<LayerDetailLevel, readonly string[]> = {
  full: [],
  standard: STANDARD_HIDES,
  minimal: MINIMAL_HIDES,
}

/** Every layer any level manages - the set the attach below has to write, so
 *  that raising the level back up restores what a lower one hid. */
export const DETAIL_MANAGED_LAYERS: readonly string[] = MINIMAL_HIDES

/**
 * Applies a detail level to a live map, and hands back a detach.
 *
 * Writes every managed layer, not only the hidden ones: `visibility` is
 * sticky, so moving from `minimal` back to `full` is six layers turning
 * `visible` again, and a loop that only wrote `none` would be a one-way
 * ratchet. Each write is guarded on its own layer for the reason
 * attachSheetAppearance's are - the probe (the wood layer, present whenever
 * the live sheet is) proves the style takes writes, not that any particular
 * layer survived the no-terrain filter.
 */
export function attachMapDetail(map: MapLibreMap, level: LayerDetailLevel): () => void {
  const hidden = new Set(DETAIL_HIDDEN_LAYERS[level])

  return whenStyleReady(
    map,
    () => map.getLayer(LIVE_TOPO_LAYER_IDS.wood) !== undefined,
    () => {
      for (const layer of DETAIL_MANAGED_LAYERS) {
        if (map.getLayer(layer) === undefined) continue
        map.setLayoutProperty(layer, 'visibility', hidden.has(layer) ? 'none' : 'visible')
      }
    },
    'Map detail',
  )
}
