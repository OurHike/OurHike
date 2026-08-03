// Turns terrain.ts's numbers into live tiles: registers maplibre-contour's two
// protocols and hands back the URLs a style points its terrain sources at.
//
// The runtime half of the pair - see terrain.ts for what the constants mean
// and why the DEM is where it is. The split exists so that building a style
// costs nothing but arithmetic; only a real map ever loads this file.
//
// Both protocols come off ONE DemSource on purpose. It owns the decoded-tile
// cache, so the hillshade and the contour generator read the same elevation
// tiles out of one place rather than each fetching its own copy - which is the
// difference between one DEM download and two for the same screen.

// Named import rather than a default: maplibre-gl v6 ships no default export,
// and `setupMaplibre` only ever calls `addProtocol` off whatever it is handed.
// Handing it exactly that one function is both honest about what is used and
// what the test double already provides.
import { addProtocol, type Map as MapLibreMap, type VectorTileSource } from 'maplibre-gl'
import mlcontour from 'maplibre-contour'
import {
  CONTOUR_ELEVATION_KEY,
  CONTOUR_LAYER,
  CONTOUR_LEVEL_KEY,
  CONTOUR_SOURCE_ID,
  CONTOUR_THRESHOLDS,
  DEM_MAX_ZOOM,
  DEM_TILE_URL,
  METRES_TO_FEET,
  type ContourUnits,
  type TerrainUrls,
} from './terrain'
import { whenStyleReady } from './styleReady'

/**
 * jsdom has no `Worker`, and neither would a browser old enough to be worth
 * guessing about. Feature-detected rather than branched on the environment, so
 * the same line is honest in both: where a worker exists, contour generation
 * stays off the UI thread (it is marching squares over a quarter-million
 * samples per tile, which visibly janks a pan if run inline), and where it does
 * not, the work still happens, just on the main thread.
 */
function workerAvailable(): boolean {
  return typeof Worker === 'function'
}

// One DemSource per page, for the same reason protocol.ts keeps one PMTiles
// protocol: the instance owns both the cache and the protocol registration, so
// a second would double the memory and leave MapLibre holding a handler whose
// cache the other one had already warmed.
let source: InstanceType<typeof mlcontour.DemSource> | null = null

function demSource(): InstanceType<typeof mlcontour.DemSource> {
  if (source !== null) return source

  const created = new mlcontour.DemSource({
    url: DEM_TILE_URL,
    encoding: 'terrarium',
    maxzoom: DEM_MAX_ZOOM,
    worker: workerAvailable(),
  })
  created.setupMaplibre({ addProtocol } as Parameters<typeof created.setupMaplibre>[0])
  source = created

  return created
}

/**
 * Registers the DEM and contour protocols and returns the URLs to point a
 * style's terrain sources at.
 *
 * Idempotent, and safe to call before every map build - MapView does exactly
 * that, the same way it calls registerPMTilesProtocol().
 */
export function registerTerrain(units: ContourUnits = 'imperial'): TerrainUrls {
  const dem = demSource()

  return {
    demUrl: dem.sharedDemProtocolUrl,
    contourTilesUrl: dem.contourProtocolUrl({
      // The DEM is in metres whoever is reading it, so the conversion happens
      // here, once - every threshold and every label downstream is already in
      // the unit that will be shown.
      multiplier: units === 'imperial' ? METRES_TO_FEET : 1,
      thresholds: CONTOUR_THRESHOLDS[units],
      elevationKey: CONTOUR_ELEVATION_KEY,
      levelKey: CONTOUR_LEVEL_KEY,
      contourLayer: CONTOUR_LAYER,
      // Read one zoom out and use a quadrant of it: fewer, larger reads for the
      // same coverage, and smoother lines where the DEM is overzoomed.
      overzoom: 1,
    }),
  }
}

/**
 * Switches the contour interval between feet and metres on a LIVE map, without
 * rebuilding it.
 *
 * The interval is encoded in the contour source's own tile URL, so 40ft lines
 * and 10m lines really are different tiles rather than a repaint - which makes
 * the obvious implementation (put `units` in the map-building effect's
 * dependencies) tear down the WebGL context and rebuild the whole map when
 * someone toggles metric. MapView deliberately keeps display preferences out
 * of that effect so a settings change never pulls the map out from under a
 * hiker, and this is what lets the contours honour it too: `setTiles` re-points
 * the existing source in place.
 *
 * A no-op when the URL has not actually changed, so mounting does not
 * immediately invalidate the tiles the style just asked for.
 *
 * Best-effort in the same way and for the same reason as backdrop.ts: it needs
 * a loaded style, which is a later and more fragile moment than construction,
 * and the cost of failing is contours at the previous interval - never a
 * broken map.
 */
export function attachContourUnits(map: MapLibreMap, units: ContourUnits): () => void {
  return whenStyleReady(
    map,
    // The contour source is both the precondition and the target. It is also
    // legitimately absent whenever the style's background is not the live one
    // - see below - so this waits for a style that has it, and the detach ends
    // the wait if none ever does.
    () => map.getSource(CONTOUR_SOURCE_ID) !== undefined,
    () => {
      const contours = map.getSource(CONTOUR_SOURCE_ID) as VectorTileSource | undefined
      // Absent whenever the background in the style is not the live one, which
      // is a normal state rather than a failure - nothing to retune.
      //
      // `setTiles` is feature-checked as well as the source, because getSource
      // answers with the union of every source kind and only a vector one can
      // be re-pointed. Same guard poiLayers.ts makes before calling setData,
      // and for the same reason: the id is ours, but the shape behind it is
      // whatever the current style put there.
      if (contours === undefined || typeof contours.setTiles !== 'function') return

      const wanted = registerTerrain(units).contourTilesUrl
      if (contours.tiles?.length === 1 && contours.tiles[0] === wanted) return

      contours.setTiles([wanted])
    },
    'Contour interval',
  )
}

/** Test seam only - drops the cached source so a test can observe a fresh
 *  registration. Production never needs it; a page has one map. */
export function resetTerrainForTests(): void {
  source = null
}
