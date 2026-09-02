// Switching label layers on and off on a live map (#1194).
//
// Takes layer ids rather than the toggle model, so this module knows nothing
// about which classes exist or what they are called - lib/mapLabelLayers.ts
// owns that, and a second copy of the mapping here would be a second thing to
// keep in step.
//
// PURE LAYER VISIBILITY, never a style rebuild. map/mapDetail.ts states the
// rule and the cost it avoids - a rebuild drops the WebGL context a hiker is
// holding - and this is the same mechanism applied to a different question.
//
// A LAYER THAT IS NOT ON THIS MAP IS NOT AN ERROR. The downloaded raster
// background has no vector layers at all, so every id here is absent on it;
// `getLayer` returning undefined is the normal case offline rather than a
// failure, and it is skipped in silence exactly as attachSheetAppearance
// treats the same absence.

import type { Map as MapLibreMap } from 'maplibre-gl'
import { whenStyleReady } from './styleReady'

export function attachLabelVisibility(
  map: MapLibreMap,
  shownIds: readonly string[],
  hiddenIds: readonly string[],
): () => void {
  return whenStyleReady(
    map,
    // No single layer to wait for - the ids span the sheet, the trails and
    // the waypoints, and which of them exist depends on the background. Ready
    // is when the style is.
    () => true,
    () => {
      // Both lists, applied literally. A layer named in neither is not this
      // module's - lib/mapLabelLayers.ts decides which are, and an id it
      // leaves out must keep whatever visibility something else gave it.
      for (const id of shownIds) {
        if (map.getLayer(id) === undefined) continue
        map.setLayoutProperty(id, 'visibility', 'visible')
      }
      for (const id of hiddenIds) {
        if (map.getLayer(id) === undefined) continue
        map.setLayoutProperty(id, 'visibility', 'none')
      }
    },
    'label-visibility',
  )
}
