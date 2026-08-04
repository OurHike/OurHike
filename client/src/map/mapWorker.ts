// Ships MapLibre's web worker as an asset this app actually serves.
//
// WHY THIS FILE HAS TO EXIST
//
// maplibre-gl 6 stopped inlining its worker. It now works out where to fetch
// one from at runtime, from its own module URL:
//
//   new URL('./maplibre-gl-worker.mjs', import.meta.url)
//
// That is correct for a page loading MapLibre from a CDN or from an unbundled
// node_modules, and wrong for every bundler, because after bundling
// `import.meta.url` is the app chunk - so the worker is looked for next to
// `assets/index-<hash>.js`, where nothing ever emitted it. The request 404s.
//
// Nothing about that failure is loud. MapLibre reports no error event, the
// style still parses, every layer is still in it, and `getStyle()` looks
// exactly right. But the worker is where MapLibre parses vector tiles, decodes
// rasters, cuts GeoJSON into tiles and lays out symbols - so with no worker the
// map draws NOTHING: no basemap, no contours, no trail line, no pins. Just the
// paper background layer, which is painted on the main thread and is the only
// thing left.
//
// It is worse than an empty map, because the emptiness is silent and total:
// `map.isStyleLoaded()` stays false forever, so `load` never fires, and every
// attach-on-ready helper in this directory (poiLayers.ts's pins and data,
// contours.ts's interval) waits for a moment that never comes.
//
// So: `?worker&url` hands the worker to Vite, which bundles it with the shared
// chunk it imports, emits it as a hashed asset, and gives back the URL it was
// really published at. `setWorkerUrl` then points MapLibre at that instead of
// at its own guess. Being a real emitted asset is also what gets it into the
// service worker's precache, which is the difference between a map that works
// on a ridge and one that only works in town.

import { getWorkerUrl, setWorkerUrl } from 'maplibre-gl'
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url'

/**
 * Points MapLibre at the worker Vite emitted, and answers where that is.
 *
 * Idempotent and safe to call before every map build - MapView does exactly
 * that, the same way it calls registerPMTilesProtocol(). MapLibre keeps one
 * worker pool per page, so the URL only has to be right before the first map
 * is constructed; setting it again with the same value is free.
 */
export function registerMapWorker(): string {
  if (getWorkerUrl() !== workerUrl) setWorkerUrl(workerUrl)

  return workerUrl
}
