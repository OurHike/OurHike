// The pin images, rasterised somewhere other than the thread a hiker is
// tapping on.
//
// Glue only, like map/demWorker.ts: every proportion, colour and glyph is
// map/poiIcons.ts's, and this file adds the one thing only a worker entry can
// - being the module Vite emits as the asset map/poiIconImages.ts constructs
// (`new Worker(new URL('./poiIconWorker.ts', ...`).
//
// Why there is a worker at all is measured in map/poiIconImages.ts. The short
// version: building the 46 images is scanline rasterising in plain JavaScript
// with no DOM in it anywhere, which is exactly the kind of work a worker
// exists for, and it was landing on the main thread at the moment of first run
// - where it had a first-run card, a download and three taps to compete with.

import { buildPoiIcons } from './poiIcons'

/** This file only ever runs as a dedicated worker, where `self` posts to the
 *  page - spelled structurally because the DOM lib types `self` as Window.
 *  The same shape map/demWorker.ts declares, for the same reason. */
const workerSelf = self as unknown as {
  postMessage(message: unknown): void
  onmessage: ((event: MessageEvent) => void) | null
}

// Copied rather than transferred, deliberately. Transferring detaches the
// buffers here, and buildPoiIcons() hands back the SAME cached array every
// time it is called - so a second request would post 46 images of nothing.
// The copy is about 1.7 MB of RGBA, which is a few milliseconds against the
// seconds this moves off the UI thread.
workerSelf.onmessage = () => workerSelf.postMessage(buildPoiIcons())
