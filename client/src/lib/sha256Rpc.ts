// The message protocol between archiveDownload.ts and the hashing worker -
// both sides in one module, so the two ends cannot drift apart in separate
// files. The same shape as map/demRpc.ts, for the same reason.
//
// WHY THE FOLD LEAVES THE MAIN THREAD (#448)
//
// lib/sha256.ts folds the download's chunks as they arrive, and it used to do
// so on the main thread. Measured in this repo's test environment (Node +
// jsdom, container CPU), the fold runs at ~25 MB/s - so the first sheet a
// newcomer downloads (789,552,460 bytes, basemap plus DEM) is ~32 seconds of
// solid main-thread CPU there, and a mid-range phone is several times slower.
// On any connection faster than the fold, the read loop is CPU-bound, React
// cannot repaint between chunks, and the progress bar the hiker is watching
// is frozen by the very work that verifies what it reports. The resume path
// paid the same cost in one lump: re-reading a held partial to catch its
// hash up (the `checking` state, #197) was seconds of local work with the
// screen unable to draw them.
//
// So the fold runs in a dedicated worker where one exists, and inline where
// one does not - jsdom, where the suite runs, and any browser refused a
// worker by CSP. That is map/poiIconImages.ts's posture, kept because its
// reasoning transfers whole: the fallback is not a browser story (MapLibre
// draws nothing at all without workers), it is a test-environment and
// degraded-page story, and it must still verify rather than quietly skip.
//
// WHAT CROSSES THE BOUNDARY, AND HOW IT STAYS BOUNDED
//
// Chunks are structured-CLONED to the worker, never transferred: the read
// loop also pushes each chunk into the pending segment blob, and transferring
// would detach the buffer under it. The copy is ~64 KB per message against
// the milliseconds of fold it moves off the thread.
//
// Cloned chunks queue in the worker while it folds, and nothing here asks it
// to acknowledge each one - the bound comes from the caller's own cadence.
// archiveDownload.ts checkpoints every SEGMENT_BYTES (32 MiB), and each
// checkpoint awaits `state()`, which the worker can only answer after every
// chunk posted before it (messages arrive in order). So the queue drains at
// least once per segment, and the unfolded backlog is bounded by one segment
// plus whatever is in flight - the same order of memory the pending segment
// itself holds on the main side.
//
// WHAT A DEAD WORKER MAY AND MAY NOT COST
//
// A hashing failure must never store an archive unverified - that is the
// check this whole seam exists to run - but it also must not cost the bytes.
// So a worker that errors mid-transfer downgrades exactly as far as a
// missing persisted hash state always has: `state()` answers undefined (a
// resume re-reads the held bytes and re-hashes, which resumeHash already
// treats as routine), and `digest()` refuses with a sentence for the card.
// The bytes stay on disk either way; the next attempt finishes the check.

import { Sha256, type Sha256State } from './sha256'

/** How much of a held partial is read at a time when its hash has to be
 *  recomputed. Big enough that a gigabyte is not ten thousand reads, small
 *  enough that it is never one gigabyte-sized ArrayBuffer. */
export const HASH_READ_BYTES = 4 * 1024 * 1024

export type HashRequest =
  /** Start (or restart) the fold, from a persisted state where one is usable.
   *  Sent once, first; sending it again resets the fold, which no caller
   *  does - the shape exists so the worker owns no state a message did not
   *  give it. */
  | { kind: 'init'; state?: Sha256State }
  /** The next bytes of the stream. Fire-and-forget: the answer is the effect
   *  on every later `state`/`digest`, and acking 12,000 chunks would be
   *  12,000 messages saying nothing. */
  | { kind: 'chunk'; bytes: Uint8Array }
  /** Fold `blob` from byte `from` to its end - the catch-up read over a held
   *  partial, moved off the main thread whole rather than windowed across
   *  the boundary. The worker reads the windows itself and reports each. */
  | { kind: 'blob'; id: number; blob: Blob; from: number }
  /** The fold's working memory, after everything posted before this. */
  | { kind: 'state'; id: number }
  /** The digest of everything posted before this. Non-destructive, like the
   *  Sha256 it wraps. */
  | { kind: 'digest'; id: number }

export type HashResponse =
  /** One window of a `blob` request folded; `bytesHashed` is the fold's total,
   *  which is what the checking bar renders. */
  | { kind: 'progress'; id: number; bytesHashed: number }
  | { kind: 'done'; id: number }
  | { kind: 'state'; id: number; state: Sha256State }
  | { kind: 'digest'; id: number; digest: string }
  | { kind: 'error'; id: number; message: string }

/**
 * The worker side: one fold, driven by requests, answers posted back.
 *
 * A factory over the post function rather than code in the worker entry, so
 * jsdom tests can drive it with a recording post - the worker entry itself
 * is three lines of glue (sha256Worker.ts).
 *
 * Requests are handled strictly in arrival order through a promise chain,
 * because `blob` is the one asynchronous request: a `chunk` arriving while a
 * blob window was still being read would otherwise fold out of order and
 * produce a digest of bytes in an order the archive is not in.
 */
export function createHashRequestHandler(
  post: (message: HashResponse) => void,
): (request: HashRequest) => void {
  let hash = new Sha256()
  let queue: Promise<void> = Promise.resolve()

  async function handle(request: HashRequest): Promise<void> {
    switch (request.kind) {
      case 'init':
        hash =
          request.state === undefined ? new Sha256() : Sha256.fromState(request.state)
        return
      case 'chunk':
        hash.update(request.bytes)
        return
      case 'blob':
        try {
          for (let at = request.from; at < request.blob.size; at += HASH_READ_BYTES) {
            const window = request.blob.slice(
              at,
              Math.min(at + HASH_READ_BYTES, request.blob.size),
            )
            hash.update(new Uint8Array(await window.arrayBuffer()))
            post({ kind: 'progress', id: request.id, bytesHashed: hash.bytesHashed })
          }
          post({ kind: 'done', id: request.id })
        } catch (error) {
          post({
            kind: 'error',
            id: request.id,
            message: error instanceof Error ? error.message : String(error),
          })
        }
        return
      case 'state':
        post({ kind: 'state', id: request.id, state: hash.toState() })
        return
      case 'digest':
        post({ kind: 'digest', id: request.id, digest: hash.digest() })
        return
    }
  }

  return (request) => {
    queue = queue.then(() => handle(request))
  }
}

/**
 * What archiveDownload.ts holds instead of a Sha256: the same fold, behind
 * promises, on whichever thread the environment affords.
 *
 * `update` stays fire-and-forget so the read loop never awaits the fold -
 * that await IS the freeze #448 is about. Everything that reads the fold's
 * result is a promise, ordered after every update posted before it.
 */
export interface ArchiveHasher {
  /** Bytes fed so far - initial state plus every update and catch-up window.
   *  Counted on the caller's side of the boundary, so it is knowable without
   *  a round trip. */
  readonly bytesHashed: number
  update(chunk: Uint8Array): void
  /** Catches the fold up over `blob` from byte `from`, reporting the fold's
   *  running total after each window - the re-read the `checking` state
   *  narrates (#197). */
  hashBlob(
    blob: Blob,
    from: number,
    onProgress?: (bytesHashed: number) => void,
  ): Promise<void>
  /** The fold's working memory, for the `:source` record - or undefined when
   *  the fold is lost (a dead worker), which a resume already treats as
   *  "re-read the held bytes": strictly a slower next attempt, never a
   *  weaker check. */
  state(): Promise<Sha256State | undefined>
  /** The digest. Rejects when the fold is lost, because the one thing this
   *  seam may never do is answer with a hash it did not compute. */
  digest(): Promise<string>
  /** Lets the worker go. Idempotent; the inline fold has nothing to let go. */
  dispose(): void
}

/** What the main side needs from a Worker - structural, so tests can hand
 *  over a fake channel instead of a real thread, exactly as demRpc.ts's
 *  WorkerLike does. */
export interface HashWorkerLike {
  postMessage(message: HashRequest): void
  addEventListener(type: 'message', listener: (event: MessageEvent) => void): void
  addEventListener(type: 'error', listener: () => void): void
  terminate(): void
}

/** The sentence a lost fold surfaces on the download card. The bytes are
 *  kept and identified by then - every flush wrote them down - so "try
 *  again" is a true promise: the next attempt re-reads and re-checks
 *  without re-downloading. */
const FOLD_LOST_MESSAGE =
  'This phone could not finish checking the downloaded map against what was ' +
  'published, so the download was not completed. Everything that arrived is ' +
  'kept — trying again finishes the check without re-downloading it.'

class WorkerHasher implements ArchiveHasher {
  private readonly worker: HashWorkerLike
  private fed: number
  /** Set once by the error listener; every later ask gets the degraded
   *  answer instead of hanging on a reply that will never come. */
  private lost = false
  private readonly pending = new Map<
    number,
    { resolve: (response: HashResponse) => void; reject: (error: Error) => void }
  >()
  private readonly progressListeners = new Map<number, (bytesHashed: number) => void>()
  private nextId = 0

  constructor(worker: HashWorkerLike, state?: Sha256State) {
    this.worker = worker
    this.fed = state?.byteLength ?? 0
    worker.addEventListener('message', (event) => {
      const response = event.data as HashResponse
      if (response.kind === 'progress') {
        this.progressListeners.get(response.id)?.(response.bytesHashed)
        return
      }
      const waiter = this.pending.get(response.id)
      if (waiter === undefined) return
      this.pending.delete(response.id)
      if (response.kind === 'error') waiter.reject(new Error(response.message))
      else waiter.resolve(response)
    })
    worker.addEventListener('error', () => {
      this.lost = true
      const error = new Error(FOLD_LOST_MESSAGE)
      for (const waiter of this.pending.values()) waiter.reject(error)
      this.pending.clear()
      this.progressListeners.clear()
    })
    worker.postMessage({ kind: 'init', state })
  }

  get bytesHashed(): number {
    return this.fed
  }

  private request(message: HashRequest & { id: number }): Promise<HashResponse> {
    if (this.lost) return Promise.reject(new Error(FOLD_LOST_MESSAGE))
    return new Promise((resolve, reject) => {
      this.pending.set(message.id, { resolve, reject })
      this.worker.postMessage(message)
    })
  }

  update(chunk: Uint8Array): void {
    // Counted whether or not the worker is lost, so the caller's arithmetic
    // over "how far the fold got" stays consistent with the bytes it fed -
    // a lost fold is discovered at state()/digest(), not by a count that
    // silently stopped moving.
    this.fed += chunk.byteLength
    if (this.lost) return
    this.worker.postMessage({ kind: 'chunk', bytes: chunk })
  }

  async hashBlob(
    blob: Blob,
    from: number,
    onProgress?: (bytesHashed: number) => void,
  ): Promise<void> {
    const id = this.nextId++
    if (onProgress !== undefined) this.progressListeners.set(id, onProgress)
    try {
      await this.request({ kind: 'blob', id, blob, from })
      this.fed += blob.size - from
    } finally {
      this.progressListeners.delete(id)
    }
  }

  async state(): Promise<Sha256State | undefined> {
    try {
      const response = await this.request({ kind: 'state', id: this.nextId++ })
      return response.kind === 'state' ? response.state : undefined
    } catch {
      // The degraded answer, not a swallowed failure: an absent state is a
      // shape resumeHash has always handled by re-reading the held bytes.
      return undefined
    }
  }

  async digest(): Promise<string> {
    const response = await this.request({ kind: 'digest', id: this.nextId++ })
    if (response.kind !== 'digest') throw new Error(FOLD_LOST_MESSAGE)
    return response.digest
  }

  dispose(): void {
    this.worker.terminate()
  }
}

/** The fold where no worker can run: the same Sha256, on the calling thread,
 *  behind the same promises. This is what the whole app used before #448 and
 *  what the suite runs under jsdom - slower to scroll past, identical in
 *  what it accepts and refuses. */
class InlineHasher implements ArchiveHasher {
  private readonly hash: Sha256

  constructor(state?: Sha256State) {
    this.hash = state === undefined ? new Sha256() : Sha256.fromState(state)
  }

  get bytesHashed(): number {
    return this.hash.bytesHashed
  }

  update(chunk: Uint8Array): void {
    this.hash.update(chunk)
  }

  async hashBlob(
    blob: Blob,
    from: number,
    onProgress?: (bytesHashed: number) => void,
  ): Promise<void> {
    for (let at = from; at < blob.size; at += HASH_READ_BYTES) {
      const window = blob.slice(at, Math.min(at + HASH_READ_BYTES, blob.size))
      this.hash.update(new Uint8Array(await window.arrayBuffer()))
      onProgress?.(this.hash.bytesHashed)
    }
  }

  async state(): Promise<Sha256State | undefined> {
    return this.hash.toState()
  }

  async digest(): Promise<string> {
    return this.hash.digest()
  }

  dispose(): void {}
}

/** The worker-backed shape over any HashWorkerLike - which is how the tests
 *  drive it through a fake channel, and how createArchiveHasher wraps the
 *  real thread. */
export function createWorkerHasher(
  worker: HashWorkerLike,
  state?: Sha256State,
): ArchiveHasher {
  return new WorkerHasher(worker, state)
}

/** The inline shape by name, for the construction-failure fallback below and
 *  for tests; the app reaches it through createArchiveHasher. */
export function createInlineHasher(state?: Sha256State): ArchiveHasher {
  return new InlineHasher(state)
}

/** jsdom has no Worker, and neither does a browser old enough that MapLibre
 *  cannot draw for it either. Asked as a capability rather than assumed
 *  (map/poiIconImages.ts). */
function workerAvailable(): boolean {
  return typeof Worker !== 'undefined'
}

/**
 * The fold for one download attempt: in a worker where the environment
 * affords one, inline where it does not or where construction is refused
 * (a Content-Security-Policy, an asset that did not ship). Callers own the
 * lifetime - one hasher per attempt, disposed when the attempt ends.
 */
export function createArchiveHasher(state?: Sha256State): ArchiveHasher {
  if (!workerAvailable()) return createInlineHasher(state)
  try {
    const worker = new Worker(new URL('./sha256Worker.ts', import.meta.url), {
      type: 'module',
    })
    return createWorkerHasher(worker, state)
  } catch {
    return createInlineHasher(state)
  }
}
