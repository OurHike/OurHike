// The app's DEM worker: maplibre-contour's own exported LocalDemManager,
// constructed with the local-first getTile the stock worker cannot carry.
//
// Glue only, and deliberately so - the resolution logic lives in
// demTiles.ts and the message protocol in demRpc.ts, both testable in
// jsdom, where a real worker cannot run. What this file adds is the one
// thing only a worker entry can: being the module Vite emits as the worker
// asset contours.ts constructs (`new Worker(new URL('./demWorker.ts', ...`).
//
// Config is compile-time constants rather than an init message on purpose:
// upstream's worker takes its parameters over postMessage because the
// library cannot know them; this worker is the app's own, and terrain.ts
// already IS the one home those numbers live in.

import mlcontour from 'maplibre-contour'
import { demGetTile } from './demTiles'
import { DEM_MAX_ZOOM, DEM_TILE_URL } from './terrain'
import { createDemRequestHandler, type DemRequest } from './demRpc'

// The same cacheSize/timeoutMs DemSource would have passed to the manager it
// constructs - its own documented defaults, restated because this manager is
// built directly.
const manager = new mlcontour.LocalDemManager({
  demUrlPattern: DEM_TILE_URL,
  cacheSize: 100,
  encoding: 'terrarium',
  maxzoom: DEM_MAX_ZOOM,
  timeoutMs: 10_000,
  getTile: demGetTile,
})

/** This file only ever runs as a dedicated worker, where `self` posts to the
 *  page - spelled structurally because the DOM lib types `self` as Window. */
const workerSelf = self as unknown as {
  postMessage(message: unknown): void
  onmessage: ((event: MessageEvent) => void) | null
}

const handle = createDemRequestHandler(manager, (message) =>
  workerSelf.postMessage(message),
)

workerSelf.onmessage = (event: MessageEvent) => handle(event.data as DemRequest)
