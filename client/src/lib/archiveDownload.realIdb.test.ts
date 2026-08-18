// The archive download engine against a REAL IndexedDB (#318).
//
// Everything else in the suite mocks idb-keyval outright, so the storage
// coverage of the app's headline feature - up to 1.18 GB on a hiker's phone -
// was 100% simulated: every quota error, every transaction, every read-back
// existed only as a hand-written mock rejection. This file runs the real
// idb-keyval against fake-indexeddb's real IndexedDB implementation, so the
// engine's writes go through actual object stores and transactions, and what
// the tests read back is what a phone would hold.
//
// NO vi.mock('idb-keyval') here, on purpose - that absence is this file's
// subject. The published-hash lookup stays mocked for the reason the sibling
// file gives: what it reads is dataManifest.ts's own subject, tested there.
//
// What stays with the real-browser smoke layer (client/scripts/storage-probe/
// and TESTING.md's Platforms section): WebKit's actual eviction policy,
// per-platform quotas, and the Blob-vs-quota accounting that found #544.
// fake-indexeddb enforces no quota, so the quota case below injects the
// DOMException at the object-store boundary - the engine's response to it is
// real; the browser's decision to raise it is not simulated here.

import 'fake-indexeddb/auto'

import { Blob as NodeBlob } from 'node:buffer'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { clear, get } from 'idb-keyval'

// jsdom's Blob is opaque to structuredClone - fake-indexeddb clones it into
// an empty object, silently (measured writing this file: a stored segment
// read back as the string "[object Blob]"). Node's own Blob IS in the
// structured-clone algorithm node implements, so the engine's Blobs are
// node's for this file - same interface, and the bytes actually round-trip.
vi.stubGlobal('Blob', NodeBlob)

import { downloadArchive, partialKeyFor, progressKeyFor } from './archiveDownload'
import { readArchive, readComplete } from './archiveStore'
import { publishedHash } from './dataManifest'

vi.mock('./dataManifest', () => ({ publishedHash: vi.fn() }))

const URL_ = 'https://cdn.example.org/background.pmtiles'
const ARTIFACT = 'background.pmtiles'
const KEY = 'ourhike:archive:test'

function bytes(length: number, seed = 0) {
  return Uint8Array.from({ length }, (_, i) => (i + seed) % 251)
}

/** A fetch serving `body`, honouring a `Range: bytes=N-` request with a 206. */
function serveRanges(body: Uint8Array, { failAfter }: { failAfter?: number } = {}) {
  return vi.spyOn(globalThis, 'fetch').mockImplementation(async (_url, init) => {
    const range = new Headers(init?.headers).get('range')
    const start = range ? Number(/bytes=(\d+)-/.exec(range)![1]) : 0
    const served = body.slice(start)

    let sent = 0
    const stream = new ReadableStream<Uint8Array>({
      pull(controller) {
        if (failAfter !== undefined && sent >= failAfter) {
          controller.error(new TypeError('network dropped'))
          return
        }
        if (sent >= served.length) {
          controller.close()
          return
        }
        const chunk = served.slice(sent, sent + 16)
        controller.enqueue(chunk)
        sent += chunk.length
      },
    })

    const headers = new Headers({ 'content-length': String(served.length), etag: '"v1"' })
    if (range)
      headers.set('content-range', `bytes ${start}-${body.length - 1}/${body.length}`)
    return new Response(stream, { status: range ? 206 : 200, headers })
  })
}

beforeEach(async () => {
  vi.mocked(publishedHash).mockResolvedValue(null)
  // idb-keyval caches its database connection across tests, so the store is
  // emptied through it rather than by replacing the IDBFactory under it.
  await clear()
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('against a real IndexedDB', () => {
  it('stores a download the map can read back, byte for byte', async () => {
    const body = bytes(200)
    serveRanges(body)

    await downloadArchive(KEY, URL_, { artifactKey: ARTIFACT, segmentBytes: 64 })

    const stored = await readArchive(KEY)
    expect(stored).toBeDefined()
    expect(new Uint8Array(await stored!.arrayBuffer())).toEqual(body)
    // The bookkeeping cleaned up after itself in the real store too.
    expect(await get(progressKeyFor(KEY))).toBeUndefined()
    expect(await get(partialKeyFor(KEY))).toBeUndefined()
  })

  it('resumes from really-persisted segments after a dropped connection', async () => {
    const body = bytes(200)
    serveRanges(body, { failAfter: 96 })
    await expect(
      downloadArchive(KEY, URL_, { artifactKey: ARTIFACT, segmentBytes: 32 }),
    ).rejects.toThrow()

    // The checkpointed segments survived in the real store - this is the
    // property #553 exists for, exercised through real transactions.
    const fetchSpy = serveRanges(body)
    await downloadArchive(KEY, URL_, { artifactKey: ARTIFACT, segmentBytes: 32 })

    // 96 bytes were flushed before the drop (three 32-byte segments), and
    // the engine asks for exactly the remainder. The attempt makes more than
    // one request (a probe precedes the ranged read), so the claim is that
    // the ranged read happened - not that it came first.
    const requests = fetchSpy.mock.calls.map(([, init]) =>
      new Headers(init?.headers).get('range'),
    )
    expect(requests).toContain('bytes=96-')
    const stored = await readArchive(KEY)
    expect(new Uint8Array(await stored!.arrayBuffer())).toEqual(body)
  })

  it('survives quota exhaustion mid-write with the finished archive intact', async () => {
    // A hiker with a good map taps re-download on a full phone. The write
    // that hits the wall must fail the ATTEMPT, not the map they have.
    const good = bytes(120, 7)
    serveRanges(good)
    await downloadArchive(KEY, URL_, { artifactKey: ARTIFACT, segmentBytes: 64 })
    const before = await readComplete(KEY)
    expect(before).not.toBeNull()

    // From here, every object-store write is refused the way a full phone
    // refuses it. The DOMException is injected at the store boundary because
    // fake-indexeddb enforces no quota; everything downstream of the throw -
    // the engine's handling, the store's state - is real.
    const put = vi.spyOn(IDBObjectStore.prototype, 'put').mockImplementation(() => {
      throw new DOMException('', 'QuotaExceededError')
    })
    serveRanges(bytes(120, 11))
    await expect(
      downloadArchive(KEY, URL_, { artifactKey: ARTIFACT, segmentBytes: 32 }),
    ).rejects.toThrow()
    put.mockRestore()

    // The archive written before the quota hit is still there, still whole.
    const stored = await readArchive(KEY)
    expect(new Uint8Array(await stored!.arrayBuffer())).toEqual(good)
    // And the map still reads from the generation the finished archive is in.
    expect((await readComplete(KEY))?.generation).toBe(before!.generation)
  })
})
