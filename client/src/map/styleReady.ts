// Waiting for the piece of style an imperative write actually needs.
//
// Three modules used to gate their writes the same way:
//
//     if (map.isStyleLoaded()) apply()
//     else map.on('load', apply)
//
// which is only correct if `isStyleLoaded() === false` means `load` is still
// coming. In maplibre-gl 6 it does not, and the two halves fail together:
//
//  - `isStyleLoaded()` is `Style.loaded()`, which goes false again whenever a
//    source is marked for reload, a GeoJSON `setData` is mid worker round
//    trip, or ANY in-view tile is still loading. On the live background -
//    OSM vector, DEM and contour tiles, all over the network - that is most
//    of the time, not a moment at startup.
//  - `load` fires exactly once. `_loaded` is set true and never reset.
//
// So an attach landing in one of those windows registers a listener for an
// event that has already happened, and the write is dropped forever. That is
// how POI pins went permanently missing: `attachPoiData` runs when the POIs
// land from IndexedDB, once, and if that single write met a tile in flight
// the map drew no pins while the legend went on listing them.
//
// The gate was also stricter than the API it was protecting. `Style` guards
// these calls on `_loaded` - the style spec finished parsing - not on
// `loaded()`, so `setData`, `setFilter`, `addImage` and `setPaintProperty`
// were all perfectly legal in exactly the window the old gate refused.
//
// Hence both halves of the fix below: ask whether the specific source or
// layer being written to is there yet, and if it is not, wait on `styledata`,
// which keeps firing, rather than `load`, which does not.

import type { Map as MapLibreMap } from 'maplibre-gl'

/**
 * Runs `apply` as soon as `ready` says the style can take it, and returns a
 * detach function.
 *
 * `ready` should probe the thing being written to - `map.getSource(id)`,
 * `map.getLayer(id)` - rather than the map's global loadedness. Getting
 * something back already proves the style spec is parsed and the write is
 * legal, and it is the narrowest question that answers "can this write land".
 *
 * Failure is warned about, never thrown. These run inside React effects on the
 * map screen, where an exception would take the whole map down over a pin.
 */
export function whenStyleReady(
  map: MapLibreMap,
  ready: () => boolean,
  apply: () => void,
  what: string,
): () => void {
  let detached = false
  let applied = false

  /** True once there is nothing left to wait for - applied, or given up on. */
  const attempt = (): boolean => {
    if (detached || applied) return true
    if (!ready()) return false

    // Set before the call, not after: a write that throws has had its one
    // chance. Retrying it on every subsequent styledata would turn one warning
    // into a stream of them for the life of the map.
    applied = true
    try {
      apply()
    } catch (error) {
      console.warn(`${what} failed; the map is drawn without it.`, error)
    }
    return true
  }

  const onStyleData = () => {
    if (attempt()) map.off('styledata', onStyleData)
  }

  // Tried immediately, so a style that is already holding what this needs -
  // the common case for anything attaching to a live map - costs no event.
  if (!attempt()) map.on('styledata', onStyleData)

  return () => {
    detached = true
    map.off('styledata', onStyleData)
  }
}
