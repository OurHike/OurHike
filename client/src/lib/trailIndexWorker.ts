// The trail index worker: the parse, the index and the waypoint placement,
// off the thread a hiker is tapping (#1192).
//
// Glue only, like map/demWorker.ts, map/poiIconWorker.ts and
// lib/sha256Worker.ts: the build and the message protocol live in
// trailIndexBuild.ts, tested in jsdom through a fake channel, where a real
// worker cannot run. What this file adds is the one thing only a worker entry
// can - being the module Vite emits as the asset trailIndexBuild.ts constructs
// (`new Worker(new URL('./trailIndexWorker.ts', ...`). Why there is a worker
// at all is measured in that file's header.
//
// The cache read and write happen here too: idb-keyval opens IndexedDB from
// whichever thread asks, and a launch's main thread has no reason to touch
// eleven megabytes of typed arrays it is about to receive by transfer.

import {
  createTrailIndexRequestHandler,
  type TrailIndexWorkerRequest,
} from './trailIndexBuild'

/** This file only ever runs as a dedicated worker, where `self` posts to the
 *  page - spelled structurally because the DOM lib types `self` as Window.
 *  The same shape map/demWorker.ts declares, for the same reason. */
const workerSelf = self as unknown as {
  postMessage(message: unknown, transfer: ArrayBuffer[]): void
  onmessage: ((event: MessageEvent) => void) | null
}

const handle = createTrailIndexRequestHandler((message, transfer) =>
  workerSelf.postMessage(message, transfer),
)

workerSelf.onmessage = (event: MessageEvent) => {
  void handle(event.data as TrailIndexWorkerRequest)
}
