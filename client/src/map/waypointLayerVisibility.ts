/**
 * Turning every waypoint layer off and on together (2026-09-20).
 *
 * The waypoint master gate the maintainer asked for - *"Add a toggle over the
 * map to 'Show Points'"* - needs one lever that reaches every rank at once:
 * the pins, the dots under them, the staleness rings between the two, the
 * waypoint names and the dispute marks that annotate a pin.
 *
 * A VISIBILITY FLIP RATHER THAN A FILTER, and the difference matters for the
 * reason #607 documented: a filter still leaves the source built and the
 * symbols placed, and map/poiLayers.ts's `poiFilter` is the HIKER's channel -
 * the per-category rows in the legend. Two mechanisms writing one filter would
 * race, and the loser would be whichever wrote last. Visibility is a separate
 * property, so the switch and the legend cannot overwrite each other: a hiker
 * who hid privies and then switched points off and on again gets their privies
 * still hidden.
 *
 * AND IT IS NOT THE SEAM EITHER. Below map/poiLayers.ts's POI_PIN_MIN_ZOOM the
 * layers' own `minzoom` draws nothing whatever this says, so there are two
 * independent reasons a waypoint may be absent and neither can mask a bug in
 * the other. lib/showPoints.ts's `waypointsDrawn` is where the shell asks
 * about both at once.
 */
import type { Map as MapLibreMap } from 'maplibre-gl'
import { whenStyleReady } from './styleReady'
import { POI_DOT_LAYER_ID, POI_LAYER_ID } from './poiLayers'
import { POI_LABEL_LAYER_ID } from './poiLabels'
import { DISPUTE_LAYER_ID } from './disputeLayers'

/**
 * Every layer the switch reaches.
 *
 * Named rather than derived from a prefix, so adding a waypoint layer is a
 * decision somebody makes here instead of something a naming convention does
 * silently - and waypointLayerVisibility.test.ts fails if the style grows one
 * this list does not carry.
 */
export const WAYPOINT_LAYER_IDS: readonly string[] = [
  POI_LABEL_LAYER_ID,
  POI_DOT_LAYER_ID,
  POI_LAYER_ID,
  DISPUTE_LAYER_ID,
]

/** Flip every waypoint layer to match the switch. */
export function attachWaypointVisibility(map: MapLibreMap, shown: boolean): () => void {
  return whenStyleReady(
    map,
    () => map.getLayer(POI_LAYER_ID) !== undefined,
    () => {
      for (const id of WAYPOINT_LAYER_IDS) {
        if (map.getLayer(id) === undefined) continue
        map.setLayoutProperty(id, 'visibility', shown ? 'visible' : 'none')
      }
    },
    'waypoint-visibility',
  )
}
