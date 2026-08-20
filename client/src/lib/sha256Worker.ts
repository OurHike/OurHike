// The hashing worker: the archive-verification fold, off the thread a hiker
// is watching a progress bar on.
//
// Glue only, like map/demWorker.ts and map/poiIconWorker.ts: the protocol and
// the fold live in sha256Rpc.ts and sha256.ts, both tested in jsdom, where a
// real worker cannot run. What this file adds is the one thing only a worker
// entry can - being the module Vite emits as the asset sha256Rpc.ts's
// createArchiveHasher constructs (`new Worker(new URL('./sha256Worker.ts',
// ...`). Why there is a worker at all is measured in sha256Rpc.ts's header.

import { createHashRequestHandler, type HashRequest } from './sha256Rpc'

/** This file only ever runs as a dedicated worker, where `self` posts to the
 *  page - spelled structurally because the DOM lib types `self` as Window.
 *  The same shape map/demWorker.ts declares, for the same reason. */
const workerSelf = self as unknown as {
  postMessage(message: unknown): void
  onmessage: ((event: MessageEvent) => void) | null
}

const handle = createHashRequestHandler((message) => workerSelf.postMessage(message))

workerSelf.onmessage = (event: MessageEvent) => handle(event.data as HashRequest)
