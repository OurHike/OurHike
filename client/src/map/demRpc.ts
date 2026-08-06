// The message protocol between contours.ts and the app's DEM worker - both
// sides in one module, so the two ends cannot drift apart in separate files.
//
// WHY THE APP OWNS THIS WORKER AT ALL
//
// maplibre-contour's stock worker cannot be taught to read the downloaded
// DEM package: its worker is a blob built from the library's own chunks,
// its tile fetch is a plain fetch(url) in that worker, and the one seam the
// library exposes for replacing the fetch - LocalDemManager's `getTile`
// init option - is a function, which cannot cross a postMessage boundary
// into a worker the library constructed. So the app constructs the worker
// instead (demWorker.ts), builds the SAME exported LocalDemManager inside
// it with demTiles.ts's local-first getTile, and speaks this protocol to
// it. Everything heavy stays where it is today - fetch, image decode and
// isoline generation all in the worker, one decoded-tile cache shared by
// the hillshade and the contour generator - which is the property the
// stock worker existed for, kept rather than traded away for offline.
//
// The protocol is three requests and an abort, mirroring maplibre-contour's
// own DemManager interface so WorkerDemManager below can stand in for the
// manager a DemSource constructs. Aborts travel as their own message: the
// main side rejects locally at once (a cancelled pan must not wait on a
// worker round trip), the worker aborts the underlying controller so the
// work actually stops, and a late reply to an aborted id falls into the
// void by design.

/** Contour options travel opaquely: DemSource computes them on the main
 *  thread and LocalDemManager consumes them in the worker; this protocol
 *  only carries them, and typing them structurally here would be a second
 *  copy of upstream's type to keep in sync. */
export type ContourOptions = object

export type DemRequest =
  | { id: number; kind: 'fetchTile'; z: number; x: number; y: number }
  | { id: number; kind: 'fetchAndParseTile'; z: number; x: number; y: number }
  | {
      id: number
      kind: 'fetchContourTile'
      z: number
      x: number
      y: number
      options: ContourOptions
    }
  | { id: number; kind: 'abort' }

export type DemResponse =
  | {
      id: number
      ok: true
      kind: 'fetchTile'
      data: Blob
      cacheControl?: string
      expires?: string
    }
  | {
      id: number
      ok: true
      kind: 'fetchAndParseTile'
      width: number
      height: number
      data: Float32Array
    }
  | { id: number; ok: true; kind: 'fetchContourTile'; arrayBuffer: ArrayBuffer }
  | { id: number; ok: false; message: string }

/** The slice of maplibre-contour's DemManager both sides agree on, spelled
 *  structurally for the same reason as demTiles.ts's DemFetchResponse: the
 *  package entry exports no named types. LocalDemManager satisfies this on
 *  the worker side; WorkerDemManager implements it on the main side; tsc
 *  checks the real compatibility at the `DemSource.manager` assignment. */
export interface DemManagerLike {
  loaded: Promise<void>
  fetchTile(
    z: number,
    x: number,
    y: number,
    abortController: AbortController,
  ): Promise<{ data: Blob; cacheControl?: string; expires?: string }>
  fetchAndParseTile(
    z: number,
    x: number,
    y: number,
    abortController: AbortController,
  ): Promise<{ width: number; height: number; data: Float32Array }>
  fetchContourTile(
    z: number,
    x: number,
    y: number,
    options: ContourOptions,
    abortController: AbortController,
  ): Promise<{ arrayBuffer: ArrayBuffer }>
}

/**
 * The worker side: turns requests into manager calls and posts the answers
 * back. A factory over the manager and the post function rather than code
 * in the worker entry, so jsdom tests can drive it with a stub manager and
 * a recording post - the worker entry itself is three lines of glue.
 */
export function createDemRequestHandler(
  manager: DemManagerLike,
  post: (message: DemResponse) => void,
): (request: DemRequest) => void {
  const inflight = new Map<number, AbortController>()

  const respond = (id: number, work: Promise<DemResponse>) => {
    work
      .then((message) => {
        // An id no longer inflight was aborted; its requester already
        // rejected and a reply would be answering nobody.
        if (!inflight.has(id)) return
        post(message)
      })
      .catch((error: unknown) => {
        if (!inflight.has(id)) return
        post({
          id,
          ok: false,
          message: error instanceof Error ? error.message : String(error),
        })
      })
      .finally(() => inflight.delete(id))
  }

  return (request: DemRequest) => {
    if (request.kind === 'abort') {
      inflight.get(request.id)?.abort()
      inflight.delete(request.id)
      return
    }

    const abortController = new AbortController()
    inflight.set(request.id, abortController)
    const { id, z, x, y } = request

    if (request.kind === 'fetchTile') {
      respond(
        id,
        manager.fetchTile(z, x, y, abortController).then((tile) => ({
          id,
          ok: true,
          kind: 'fetchTile',
          data: tile.data,
          cacheControl: tile.cacheControl,
          expires: tile.expires,
        })),
      )
    } else if (request.kind === 'fetchAndParseTile') {
      // Everything below is structured-CLONED, never transferred.
      // LocalDemManager serves parsed and contour tiles through AsyncCaches
      // that hand the SAME object to every later caller, so transferring
      // would detach a buffer the cache is still holding and poison every
      // subsequent read of that tile. The copy is the price of the cache
      // staying warm, and the cheaper side of the trade: one clone per
      // tile against re-fetching and re-decoding it.
      respond(
        id,
        manager.fetchAndParseTile(z, x, y, abortController).then((tile) => ({
          id,
          ok: true,
          kind: 'fetchAndParseTile',
          ...tile,
        })),
      )
    } else {
      respond(
        id,
        manager
          .fetchContourTile(z, x, y, request.options, abortController)
          .then((tile) => ({
            id,
            ok: true,
            kind: 'fetchContourTile',
            arrayBuffer: tile.arrayBuffer,
          })),
      )
    }
  }
}

/** What WorkerDemManager needs from a Worker - structural, so tests can
 *  hand over one half of a MessageChannel instead of a real thread. */
export interface WorkerLike {
  postMessage(message: DemRequest): void
  addEventListener(type: 'message', listener: (event: MessageEvent) => void): void
}

interface Pending {
  resolve: (response: DemResponse & { ok: true }) => void
  reject: (error: Error) => void
  cleanup: () => void
}

/**
 * The main-thread side: maplibre-contour's DemManager interface over the
 * app's DEM worker. Assigned to `DemSource.manager` (a public, typed field)
 * in contours.ts, which is what routes the hillshade's `dem://` reads and
 * the contour generator's tiles through the worker - and through the
 * local-first getTile living inside it.
 */
export class WorkerDemManager implements DemManagerLike {
  loaded = Promise.resolve()
  private readonly worker: WorkerLike
  private readonly pending = new Map<number, Pending>()
  private nextId = 0

  constructor(worker: WorkerLike) {
    this.worker = worker
    worker.addEventListener('message', (event) => {
      const response = event.data as DemResponse
      const waiter = this.pending.get(response.id)
      if (waiter === undefined) return
      this.pending.delete(response.id)
      waiter.cleanup()
      if (response.ok) waiter.resolve(response)
      else waiter.reject(new Error(response.message))
    })
  }

  private request<K extends DemRequest['kind']>(
    message: DemRequest & { kind: K },
    abortController: AbortController,
  ): Promise<DemResponse & { ok: true; kind: K }> {
    return new Promise((resolve, reject) => {
      const { id } = message
      const onAbort = () => {
        // Reject locally first - a cancelled pan must not wait a worker
        // round trip - then tell the worker so the work really stops.
        this.pending.delete(id)
        this.worker.postMessage({ id, kind: 'abort' })
        reject(new DOMException('The operation was aborted.', 'AbortError'))
      }
      this.pending.set(id, {
        resolve: resolve as Pending['resolve'],
        reject,
        cleanup: () => abortController.signal.removeEventListener('abort', onAbort),
      })
      abortController.signal.addEventListener('abort', onAbort)
      this.worker.postMessage(message)
    })
  }

  fetchTile(z: number, x: number, y: number, abortController: AbortController) {
    return this.request(
      { id: this.nextId++, kind: 'fetchTile' as const, z, x, y },
      abortController,
    )
  }

  fetchAndParseTile(z: number, x: number, y: number, abortController: AbortController) {
    return this.request(
      { id: this.nextId++, kind: 'fetchAndParseTile' as const, z, x, y },
      abortController,
    ).then(({ width, height, data }) => ({ width, height, data }))
  }

  fetchContourTile(
    z: number,
    x: number,
    y: number,
    options: ContourOptions,
    abortController: AbortController,
  ) {
    return this.request(
      { id: this.nextId++, kind: 'fetchContourTile' as const, z, x, y, options },
      abortController,
    ).then(({ arrayBuffer }) => ({ arrayBuffer }))
  }
}
