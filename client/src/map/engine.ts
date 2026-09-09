// Everything that touches `maplibre-gl` at runtime, behind one module (#722).
//
// WHY THIS FILE EXISTS
//
// Measured on Chromium 390x844 at 4x CPU throttle, over loopback:
//
//   style-*.js transfer                    269,259 B
//   network + decode                          131 ms
//   parse + compile + evaluate, in isolation  860 ms
//
// The CPU cost is 6.5x the network cost and all of it is on the main thread,
// in front of the first paint - because `main.tsx` imports `App.tsx`, which
// imports `MapView.tsx`, which imported `maplibre-gl` statically. On a first
// run, what a hiker is waiting for behind that parse is a card with four
// sentences on it.
//
// Breaking that needs EVERY static path from `main.tsx` to `maplibre-gl`
// broken, not just the obvious one, which is what this module is for: the
// modules that import the library for its values (`Map`, `setWorkerUrl`, the
// three controls, the contour protocol) are all imported here, and `MapView`
// reaches this through `import()`.
//
// AND IT BROKE ANYWAY, WHICH IS WHY `addProtocol` IS PASSED DOWN (#1300).
// map/protocol.ts, map/basemap.ts and map/networkTiles.ts each imported
// `addProtocol` for the one call that registers their handler - and each is
// also imported by `App.tsx` for something that needs no library at all: a
// string (`CORRIDOR_ARCHIVE_URL`) and two setters (`setBasemapCells`,
// `setNetworkCells`). Rollup did the only thing it could and put the engine
// in a chunk both the shell and this module reach, which Vite then
// modulepreloaded from the document head: 406 KB of `maplibre-gl-shared.mjs`
// parsed on every launch, including the Today launch that mounts no map. The
// first of those imports landed in the same commit as this seam. So the three
// modules now take `addProtocol` as an argument, this file hands it over, and
// scripts/check-build-output.mjs fails the build if any chunk the document
// loads eagerly carries MapLibre - the guard that was missing the first time.
//
// THE TRADE, WHICH IS REAL AND WAS CHOSEN
//
// The first frame becomes the onboarding card over an empty backdrop, with
// the map fading in behind it a beat later. That reverses the emphasis
// App.tsx's onboarding argument rests on - "a claim about a thing that is
// right there and was being described rather than shown". The maintainer
// chose it anyway (recorded on #722: "defer it - card first"), because what
// it replaces is not the card over a map. It is nothing at all, for the
// length of that parse.
//
// WHY THE SECOND MAP IS NOT DEFERRED
//
// The module memoises its own promise, so the cost is paid once per session.
// A hiker returning to the map from the More tab gets `loadedEngine()`
// synchronously, and `MapView` builds without an await at all - which also
// keeps every test that renders a map and reaches straight for it working
// unchanged, once something has primed the engine.

import { addProtocol, Map as MapLibreMap } from 'maplibre-gl'
import { attachContourUnits, registerTerrain } from './contours'
import { attachMapChrome } from './mapChrome'
import { registerBasemapProtocol } from './basemap'
import { registerNetworkProtocol } from './networkTiles'
import { registerMapWorker } from './mapWorker'
import { registerPMTilesProtocol } from './protocol'

/** What `MapView` needs from the library, and nothing else. Narrow on
 *  purpose: anything added here is another reason the chunk cannot be
 *  deferred later. */
export interface MapEngine {
  createMap(options: ConstructorParameters<typeof MapLibreMap>[0]): MapLibreMap
  registerMapWorker: typeof registerMapWorker
  /** Each registers its scheme with MapLibre's `addProtocol`, which this seam
   *  supplies - the callers never touch the library (#1300). */
  registerPMTilesProtocol: () => ReturnType<typeof registerPMTilesProtocol>
  registerBasemapProtocol: () => void
  registerNetworkProtocol: () => void
  registerTerrain: typeof registerTerrain
  attachMapChrome: typeof attachMapChrome
  attachContourUnits: typeof attachContourUnits
}

/**
 * The engine, with every member dereferenced when it is CALLED rather than
 * when this module is evaluated.
 *
 * That distinction is not style. `App.test.tsx` proves the map screen's error
 * boundary by spying on `Map` and throwing "WebGL context could not be
 * created" - the failure #131 is about, where a throw under the root takes the
 * tab bar with it. A snapshot taken at module scope would hold the constructor
 * from before the spy, so the map would build happily and the test would be
 * asserting nothing while passing.
 */
export function mapEngine(): MapEngine {
  return {
    createMap: (options) => new MapLibreMap(options),
    registerMapWorker: (...args) => registerMapWorker(...args),
    registerPMTilesProtocol: () => registerPMTilesProtocol(addProtocol),
    registerBasemapProtocol: () => registerBasemapProtocol(addProtocol),
    registerNetworkProtocol: () => registerNetworkProtocol(addProtocol),
    registerTerrain: (...args) => registerTerrain(...args),
    attachMapChrome: (...args) => attachMapChrome(...args),
    attachContourUnits: (...args) => attachContourUnits(...args),
  }
}
