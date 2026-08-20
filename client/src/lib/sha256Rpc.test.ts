// The hashing seam (#448): the same fold, either side of a worker boundary.
//
// jsdom cannot run a real worker, so the boundary is exercised the way
// map/demRpc.test.ts exercises its own: the worker-side handler and the
// main-side hasher wired together through a fake channel. What matters here
// is not that SHA-256 is right - sha256.test.ts pins that against the NIST
// vectors - but that the boundary preserves it: order, resume state, the
// catch-up read, and what a dead worker may and may not cost. The inline
// shape runs the same assertions, because it is the same contract and the
// suite itself is its main habitat.

import { describe, expect, it, vi, afterEach } from 'vitest'
import { Sha256, sha256Hex, type Sha256State } from './sha256'
import {
  createArchiveHasher,
  createHashRequestHandler,
  createInlineHasher,
  createWorkerHasher,
  type ArchiveHasher,
  type HashRequest,
  type HashWorkerLike,
} from './sha256Rpc'

const bytes = (...values: number[]) => Uint8Array.from(values)

/** The two ends joined in-process: postMessage feeds the real handler, and
 *  the handler's posts come back as message events. Errors are fired by the
 *  test, since nothing in a fake channel crashes on its own. */
function fakeChannel() {
  const messageListeners: ((event: MessageEvent) => void)[] = []
  const errorListeners: (() => void)[] = []
  let terminated = false
  const handle = createHashRequestHandler((response) => {
    for (const listener of messageListeners) listener({ data: response } as MessageEvent)
  })
  const worker: HashWorkerLike = {
    postMessage(message: HashRequest) {
      if (!terminated) handle(message)
    },
    addEventListener(
      type: 'message' | 'error',
      listener: ((event: MessageEvent) => void) | (() => void),
    ) {
      if (type === 'message')
        messageListeners.push(listener as (event: MessageEvent) => void)
      else errorListeners.push(listener as () => void)
    },
    terminate() {
      terminated = true
    },
  }
  return {
    worker,
    fireError: () => {
      for (const listener of errorListeners) listener()
    },
    isTerminated: () => terminated,
  }
}

/** Both shapes of the contract, so every behavioural assertion runs against
 *  each - a fallback that behaves differently is two hashers wearing one
 *  interface. */
const SHAPES: [string, (state?: Sha256State) => ArchiveHasher][] = [
  [
    'across the worker boundary',
    (state) => createWorkerHasher(fakeChannel().worker, state),
  ],
  ['inline', (state) => createInlineHasher(state)],
]

describe.each(SHAPES)('the fold %s', (_shape, create) => {
  it('digests what it is fed, matching the vendored fold', async () => {
    const hasher = create()
    hasher.update(bytes(1, 2, 3))
    hasher.update(bytes(4, 5))

    expect(await hasher.digest()).toBe(sha256Hex(bytes(1, 2, 3, 4, 5)))
    expect(hasher.bytesHashed).toBe(5)
  })

  it('resumes from a persisted state instead of starting over', async () => {
    const state = new Sha256().update(bytes(1, 2, 3)).toState()
    const hasher = create(state)

    expect(hasher.bytesHashed).toBe(3)
    hasher.update(bytes(4, 5))

    expect(await hasher.digest()).toBe(sha256Hex(bytes(1, 2, 3, 4, 5)))
  })

  it('catches up over a blob from an offset, reporting as it goes', async () => {
    const hasher = create()
    const reported: number[] = []

    await hasher.hashBlob(new Blob([bytes(9, 9, 1, 2, 3)]), 2, (bytesHashed) =>
      reported.push(bytesHashed),
    )

    // From byte 2: the discarded prefix is not part of the fold.
    expect(await hasher.digest()).toBe(sha256Hex(bytes(1, 2, 3)))
    expect(hasher.bytesHashed).toBe(3)
    // One window here, so one report, of the fold's running total.
    expect(reported).toEqual([3])
  })

  it('answers state() covering exactly what was posted before the ask', async () => {
    const hasher = create()
    hasher.update(bytes(1, 2, 3))
    const midway = await hasher.state()
    hasher.update(bytes(4, 5))

    expect(midway).toBeDefined()
    expect(midway?.byteLength).toBe(3)
    // The snapshot is a real fold: finishing it from here digests the prefix.
    expect(Sha256.fromState(midway as Sha256State).digest()).toBe(
      sha256Hex(bytes(1, 2, 3)),
    )
    // And the snapshot did not consume the stream - the full digest stands.
    expect(await hasher.digest()).toBe(sha256Hex(bytes(1, 2, 3, 4, 5)))
  })

  it('keeps its digest non-destructive, like the Sha256 underneath', async () => {
    const hasher = create()
    hasher.update(bytes(1, 2, 3))

    expect(await hasher.digest()).toBe(sha256Hex(bytes(1, 2, 3)))
    hasher.update(bytes(4))
    expect(await hasher.digest()).toBe(sha256Hex(bytes(1, 2, 3, 4)))
  })
})

describe('the worker boundary itself', () => {
  it('folds a chunk posted during a blob catch-up after the blob, not into it', async () => {
    // The blob request is the one asynchronous one, so this is the ordering
    // a naive handler gets wrong: the chunk's fold landing between two blob
    // windows would digest bytes in an order the archive is not in.
    const { worker } = fakeChannel()
    const hasher = createWorkerHasher(worker)

    const catchUp = hasher.hashBlob(new Blob([bytes(1, 2, 3)]), 0)
    hasher.update(bytes(4, 5))
    await catchUp

    expect(await hasher.digest()).toBe(sha256Hex(bytes(1, 2, 3, 4, 5)))
  })

  it('refuses a digest when the worker died, and keeps counting bytes', async () => {
    const { worker, fireError } = fakeChannel()
    const hasher = createWorkerHasher(worker)
    hasher.update(bytes(1, 2, 3))
    fireError()
    hasher.update(bytes(4, 5))

    // The count the caller's arithmetic runs on stays true to what was fed;
    // the loss surfaces where an answer would have to be invented.
    expect(hasher.bytesHashed).toBe(5)
    await expect(hasher.digest()).rejects.toThrow(/could not finish checking/i)
  })

  it('rejects a digest already in flight when the worker dies', async () => {
    // A channel that never answers: requests vanish, so the pending map is
    // holding a waiter when the error lands.
    const messageListeners: ((event: MessageEvent) => void)[] = []
    const errorListeners: (() => void)[] = []
    const silent: HashWorkerLike = {
      postMessage() {},
      addEventListener(type, listener) {
        if (type === 'message')
          messageListeners.push(listener as (event: MessageEvent) => void)
        else errorListeners.push(listener as () => void)
      },
      terminate() {},
    }
    const hasher = createWorkerHasher(silent)
    const pending = hasher.digest()
    for (const listener of errorListeners) listener()

    await expect(pending).rejects.toThrow(/could not finish checking/i)
  })

  it('answers state() with undefined when the worker died - the shape a resume already re-reads from', async () => {
    const { worker, fireError } = fakeChannel()
    const hasher = createWorkerHasher(worker)
    hasher.update(bytes(1, 2, 3))
    fireError()

    expect(await hasher.state()).toBeUndefined()
  })

  it('lets the worker go on dispose', () => {
    const channel = fakeChannel()
    const hasher = createWorkerHasher(channel.worker)
    hasher.dispose()

    expect(channel.isTerminated()).toBe(true)
  })
})

describe('createArchiveHasher picking a side', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('hashes without any Worker at all - which is this suite, under jsdom', async () => {
    expect(typeof Worker).toBe('undefined')
    const hasher = createArchiveHasher()
    hasher.update(bytes(1, 2, 3))

    expect(await hasher.digest()).toBe(sha256Hex(bytes(1, 2, 3)))
  })

  it('falls back to the inline fold when constructing the worker is refused', async () => {
    // A Content-Security-Policy that forbids workers, or an asset that did
    // not ship, surfaces as a construction throw - and the check this seam
    // runs must survive that, not silently disappear with the thread.
    vi.stubGlobal(
      'Worker',
      class {
        constructor() {
          throw new Error('refused')
        }
      },
    )
    const hasher = createArchiveHasher()
    hasher.update(bytes(1, 2, 3))

    expect(await hasher.digest()).toBe(sha256Hex(bytes(1, 2, 3)))
  })
})
