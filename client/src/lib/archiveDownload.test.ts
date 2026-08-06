import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { get, set, del } from 'idb-keyval'
import {
  downloadArchive,
  deleteArchive,
  ARCHIVE_PARTIAL_KEY,
  ARCHIVE_PROGRESS_KEY,
  ARCHIVE_SOURCE_KEY,
  ArchiveSizeMismatchError,
  ArchiveHashMismatchError,
} from './archiveDownload'
import { CORRIDOR_ARCHIVE_KEY } from '../map/pmtilesSource'
import { completedMarker, recordCompleted } from './storageHealth'
import { publishedHash } from './dataManifest'
import { Sha256, sha256Hex, type Sha256State } from './sha256'

// The download behind Downloads.tsx's buttons. WIREFRAMES.md `7a` requires a
// failed transfer to RESUME rather than restart, and that promise is the
// whole reason this module is more than a fetch call: re-pulling 300 MB from
// zero because a connection dropped at 90% is exactly the failure someone on
// trailhead wifi cannot afford.
//
// Two traps get specific attention below.
//
// **A server that ignores Range.** Ask for `bytes=N-` and a compliant server
// answers 206 with the remainder. A server that does not support ranges
// answers 200 with the WHOLE file - and appending that to the bytes already
// held produces a corrupt archive of exactly the right length, which passes
// every size check and then renders a broken map. The status code has to be
// checked, not assumed.
//
// **Never destroying a good archive.** Partial bytes live under their own
// key. A failed or aborted attempt must leave both the partial progress and
// any previously-completed archive intact.

vi.mock('idb-keyval', () => ({ get: vi.fn(), set: vi.fn(), del: vi.fn() }))

// The published-hash lookup is mocked rather than served through the fetch
// stub above: what it reads (latest.json under VITE_DATA_BASE_URL, which is
// unset under test) is dataManifest.ts's own subject, tested there. Here the
// interesting variable is only what the bucket claims - a hash, a different
// hash, or no answer at all.
vi.mock('./dataManifest', () => ({ publishedHash: vi.fn() }))

const mockedGet = vi.mocked(get)
const mockedSet = vi.mocked(set)
const mockedDel = vi.mocked(del)
const mockedPublishedHash = vi.mocked(publishedHash)

const URL_ = 'https://cdn.example.org/background.pmtiles'

/** In-memory stand-in for IndexedDB. */
function withStore(initial: Record<string, unknown> = {}) {
  const store: Record<string, unknown> = { ...initial }
  mockedGet.mockImplementation(async (key) => store[key as string])
  mockedSet.mockImplementation(async (key, value) => {
    store[key as string] = value
  })
  mockedDel.mockImplementation(async (key) => {
    delete store[key as string]
  })
  return store
}

function bytes(...values: number[]) {
  return new Uint8Array(values)
}

/** A fetch returning `chunks` as a stream, with the given status/headers. */
function mockFetch({
  chunks,
  status = 200,
  totalBytes,
  contentRange,
  etag,
}: {
  chunks: Uint8Array[]
  status?: number
  totalBytes?: number
  contentRange?: string
  etag?: string
}) {
  return vi.spyOn(globalThis, 'fetch').mockImplementation(async () => {
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        for (const chunk of chunks) controller.enqueue(chunk)
        controller.close()
      },
    })
    const headers = new Headers()
    const declared = totalBytes ?? chunks.reduce((n, c) => n + c.length, 0)
    headers.set('content-length', String(declared))
    if (contentRange) headers.set('content-range', contentRange)
    if (etag) headers.set('etag', etag)

    return new Response(body, { status, headers })
  })
}

beforeEach(() => {
  vi.clearAllMocks()
  // The default for every test that is not about verification: no published
  // answer, which is what a field-test server or an older release gives, and
  // which must leave the download behaving exactly as it did before #197.
  mockedPublishedHash.mockResolvedValue(null)
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('downloadArchive — a clean first run', () => {
  it('stores the finished archive where the map reads it from', async () => {
    const store = withStore()
    mockFetch({ chunks: [bytes(1, 2, 3), bytes(4, 5, 6)] })

    await downloadArchive(CORRIDOR_ARCHIVE_KEY, URL_)

    expect(store[CORRIDOR_ARCHIVE_KEY]).toBeInstanceOf(Blob)
  })

  it('stores every byte it was sent, in order', async () => {
    const store = withStore()
    mockFetch({ chunks: [bytes(1, 2, 3), bytes(4, 5, 6)] })

    await downloadArchive(CORRIDOR_ARCHIVE_KEY, URL_)
    const stored = new Uint8Array(
      await (store[CORRIDOR_ARCHIVE_KEY] as Blob).arrayBuffer(),
    )

    expect([...stored]).toEqual([1, 2, 3, 4, 5, 6])
  })

  it('reports progress as chunks arrive, not only at the end', async () => {
    withStore()
    mockFetch({ chunks: [bytes(1, 2, 3), bytes(4, 5, 6)] })
    const onProgress = vi.fn()

    await downloadArchive(CORRIDOR_ARCHIVE_KEY, URL_, { onProgress })

    expect(onProgress.mock.calls.length).toBeGreaterThan(1)
    expect(onProgress).toHaveBeenLastCalledWith({ receivedBytes: 6, totalBytes: 6 })
  })

  it('clears the partial state once the archive is complete', async () => {
    const store = withStore()
    mockFetch({ chunks: [bytes(1, 2, 3)] })

    await downloadArchive(CORRIDOR_ARCHIVE_KEY, URL_)

    expect(store[ARCHIVE_PARTIAL_KEY]).toBeUndefined()
    expect(store[ARCHIVE_PROGRESS_KEY]).toBeUndefined()
  })

  it('asks for the whole file when nothing is held yet', async () => {
    withStore()
    const spy = mockFetch({ chunks: [bytes(1, 2, 3)] })

    await downloadArchive(CORRIDOR_ARCHIVE_KEY, URL_)
    const init = spy.mock.calls[0][1] as RequestInit | undefined

    expect(new Headers(init?.headers).get('range')).toBeNull()
  })
})

describe('downloadArchive — resuming', () => {
  it('asks only for the bytes it does not already have', async () => {
    withStore({
      [ARCHIVE_PARTIAL_KEY]: new Blob([bytes(1, 2, 3)]),
      [ARCHIVE_PROGRESS_KEY]: { receivedBytes: 3, totalBytes: 6 },
      // A partial written by this module always records where it came from;
      // one without it is deliberately discarded rather than resumed onto.
      [ARCHIVE_SOURCE_KEY]: { url: URL_ },
    })
    const spy = mockFetch({
      chunks: [bytes(4, 5, 6)],
      status: 206,
      totalBytes: 3,
      contentRange: 'bytes 3-5/6',
    })

    await downloadArchive(CORRIDOR_ARCHIVE_KEY, URL_)
    const init = spy.mock.calls[0][1] as RequestInit | undefined

    expect(new Headers(init?.headers).get('range')).toBe('bytes=3-')
  })

  it('joins the resumed bytes onto what it already had', async () => {
    const store = withStore({
      [ARCHIVE_PARTIAL_KEY]: new Blob([bytes(1, 2, 3)]),
      [ARCHIVE_PROGRESS_KEY]: { receivedBytes: 3, totalBytes: 6 },
      // A partial written by this module always records where it came from;
      // one without it is deliberately discarded rather than resumed onto.
      [ARCHIVE_SOURCE_KEY]: { url: URL_ },
    })
    mockFetch({
      chunks: [bytes(4, 5, 6)],
      status: 206,
      totalBytes: 3,
      contentRange: 'bytes 3-5/6',
    })

    await downloadArchive(CORRIDOR_ARCHIVE_KEY, URL_)
    const stored = new Uint8Array(
      await (store[CORRIDOR_ARCHIVE_KEY] as Blob).arrayBuffer(),
    )

    expect([...stored]).toEqual([1, 2, 3, 4, 5, 6])
  })

  it('counts resumed progress from what was already held, not from zero', async () => {
    withStore({
      [ARCHIVE_PARTIAL_KEY]: new Blob([bytes(1, 2, 3)]),
      [ARCHIVE_PROGRESS_KEY]: { receivedBytes: 3, totalBytes: 6 },
      // A partial written by this module always records where it came from;
      // one without it is deliberately discarded rather than resumed onto.
      [ARCHIVE_SOURCE_KEY]: { url: URL_ },
    })
    const onProgress = vi.fn()
    mockFetch({
      chunks: [bytes(4, 5, 6)],
      status: 206,
      totalBytes: 3,
      contentRange: 'bytes 3-5/6',
    })

    await downloadArchive(CORRIDOR_ARCHIVE_KEY, URL_, { onProgress })

    expect(onProgress).toHaveBeenLastCalledWith({ receivedBytes: 6, totalBytes: 6 })
  })

  it('starts over safely when the server ignores Range and sends the whole file', async () => {
    // The silent-corruption trap: appending a full 200 body to existing
    // partial bytes yields a file of plausible length that is entirely wrong.
    const store = withStore({
      [ARCHIVE_PARTIAL_KEY]: new Blob([bytes(1, 2, 3)]),
      [ARCHIVE_PROGRESS_KEY]: { receivedBytes: 3, totalBytes: 6 },
      // A partial written by this module always records where it came from;
      // one without it is deliberately discarded rather than resumed onto.
      [ARCHIVE_SOURCE_KEY]: { url: URL_ },
    })
    mockFetch({ chunks: [bytes(9, 9, 9, 9, 9, 9)], status: 200, totalBytes: 6 })

    await downloadArchive(CORRIDOR_ARCHIVE_KEY, URL_)
    const stored = new Uint8Array(
      await (store[CORRIDOR_ARCHIVE_KEY] as Blob).arrayBuffer(),
    )

    expect([...stored]).toEqual([9, 9, 9, 9, 9, 9])
  })
})

describe('downloadArchive — failure', () => {
  it('keeps what it received when the connection drops', async () => {
    const store = withStore()
    vi.spyOn(globalThis, 'fetch').mockImplementation(async () => {
      // Pull-based, so the first read genuinely delivers a chunk and the
      // SECOND one fails. Calling controller.error() straight after an
      // enqueue in start() discards the queued chunk instead, which models a
      // connection that died before delivering anything - a different case,
      // and not the one this test is about.
      let pulls = 0
      const body = new ReadableStream<Uint8Array>({
        pull(controller) {
          if (pulls === 0) controller.enqueue(bytes(1, 2, 3))
          else controller.error(new TypeError('network error'))
          pulls += 1
        },
      })
      const headers = new Headers({ 'content-length': '6' })
      return new Response(body, { status: 200, headers })
    })

    await expect(downloadArchive(CORRIDOR_ARCHIVE_KEY, URL_)).rejects.toThrow()

    expect(store[ARCHIVE_PARTIAL_KEY]).toBeInstanceOf(Blob)
    expect(store[ARCHIVE_PROGRESS_KEY]).toMatchObject({ receivedBytes: 3 })
  })

  it('leaves a previously-downloaded archive untouched when a new attempt fails', async () => {
    const good = new Blob([bytes(7, 7, 7)])
    const store = withStore({ [CORRIDOR_ARCHIVE_KEY]: good })
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('offline'))

    await expect(downloadArchive(CORRIDOR_ARCHIVE_KEY, URL_)).rejects.toThrow()

    expect(store[CORRIDOR_ARCHIVE_KEY]).toBe(good)
  })

  it('refuses to store an archive shorter than the server said it would be', async () => {
    // Truncation is the failure a size check exists to catch: a short PMTiles
    // archive opens fine and then returns nothing for tiles past the cut.
    const store = withStore()
    mockFetch({ chunks: [bytes(1, 2, 3)], totalBytes: 99 })

    await expect(downloadArchive(CORRIDOR_ARCHIVE_KEY, URL_)).rejects.toBeInstanceOf(
      ArchiveSizeMismatchError,
    )
    expect(store[CORRIDOR_ARCHIVE_KEY]).toBeUndefined()
  })

  it('keeps the partial bytes after a size mismatch, so a resume can finish it', async () => {
    const store = withStore()
    mockFetch({ chunks: [bytes(1, 2, 3)], totalBytes: 99 })

    await expect(downloadArchive(CORRIDOR_ARCHIVE_KEY, URL_)).rejects.toThrow()

    expect(store[ARCHIVE_PARTIAL_KEY]).toBeInstanceOf(Blob)
  })

  it('stops when aborted, keeping what it has', async () => {
    const store = withStore()
    const controller = new AbortController()
    vi.spyOn(globalThis, 'fetch').mockImplementation(async () => {
      const body = new ReadableStream<Uint8Array>({
        start(streamController) {
          streamController.enqueue(bytes(1, 2, 3))
          controller.abort()
          streamController.enqueue(bytes(4, 5, 6))
          streamController.close()
        },
      })
      return new Response(body, {
        status: 200,
        headers: new Headers({ 'content-length': '6' }),
      })
    })

    await expect(
      downloadArchive(CORRIDOR_ARCHIVE_KEY, URL_, { signal: controller.signal }),
    ).rejects.toThrow()

    expect(store[ARCHIVE_PARTIAL_KEY]).toBeInstanceOf(Blob)
    expect(store[CORRIDOR_ARCHIVE_KEY]).toBeUndefined()
  })

  it('rejects a non-OK response without touching stored state', async () => {
    const store = withStore()
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(null, { status: 404, statusText: 'Not Found' }),
    )

    await expect(downloadArchive(CORRIDOR_ARCHIVE_KEY, URL_)).rejects.toThrow(/404/)
    expect(store[ARCHIVE_PARTIAL_KEY]).toBeUndefined()
  })
})

// The failure mode the size check is structurally unable to catch. totalBytes is
// DEFINED as heldBytes + declared, and a completed resume accumulates exactly
// heldBytes + declared - both sides of that comparison are the same expression.
// So a spliced archive always passes it, and the result is a PMTiles file whose
// directory and tile offsets disagree: a map that reports itself downloaded and
// renders wrong past the seam, offline, with no network to correct it.
describe('downloadArchive — refusing to splice two different archives', () => {
  it('discards partial bytes that came from a different URL', async () => {
    // A hiker who starts Standard, fails, then picks Light. Appending z12 bytes
    // onto z11 bytes would produce exactly the right length and a broken map.
    const store = withStore({
      [ARCHIVE_PARTIAL_KEY]: new Blob([bytes(9, 9, 9)]),
      [ARCHIVE_PROGRESS_KEY]: { receivedBytes: 3, totalBytes: 6 },
      [ARCHIVE_SOURCE_KEY]: { url: 'https://cdn.example.org/background_z13.pmtiles' },
    })
    const fetchSpy = mockFetch({ chunks: [bytes(1, 2, 3)] })

    await downloadArchive(CORRIDOR_ARCHIVE_KEY, URL_)

    // No Range header at all: this is a fresh start, not a resume.
    expect(fetchSpy.mock.calls[0][1]).toMatchObject({ headers: undefined })
    const stored = store[CORRIDOR_ARCHIVE_KEY] as Blob
    expect(stored.size).toBe(3)
  })

  it('discards a partial with no source record, rather than resuming onto it blindly', async () => {
    // Written by a build before the source record existed, or left behind when
    // a quota failure interrupted persistPartial partway through.
    const store = withStore({
      [ARCHIVE_PARTIAL_KEY]: new Blob([bytes(9, 9, 9)]),
      [ARCHIVE_PROGRESS_KEY]: { receivedBytes: 3, totalBytes: 6 },
    })
    mockFetch({ chunks: [bytes(1, 2, 3)] })

    await downloadArchive(CORRIDOR_ARCHIVE_KEY, URL_)

    expect((store[CORRIDOR_ARCHIVE_KEY] as Blob).size).toBe(3)
  })

  it('sends If-Range so the server itself refuses a stale resume', async () => {
    const store = withStore({
      [ARCHIVE_PARTIAL_KEY]: new Blob([bytes(1, 2, 3)]),
      [ARCHIVE_PROGRESS_KEY]: { receivedBytes: 3, totalBytes: 6 },
      [ARCHIVE_SOURCE_KEY]: { url: URL_, etag: '"v1"' },
    })
    const fetchSpy = mockFetch({
      chunks: [bytes(4, 5, 6)],
      status: 206,
      etag: '"v1"',
    })

    await downloadArchive(CORRIDOR_ARCHIVE_KEY, URL_)

    expect(fetchSpy.mock.calls[0][1]).toMatchObject({
      headers: { Range: 'bytes=3-', 'If-Range': '"v1"' },
    })
    expect((store[CORRIDOR_ARCHIVE_KEY] as Blob).size).toBe(6)
  })

  it('starts clean when the archive was republished mid-download', async () => {
    // If-Range makes the server arbitrate: a changed object comes back 200 with
    // the whole body instead of 206, and the existing status check treats that
    // as "start clean". The held bytes must NOT survive into the result.
    const store = withStore({
      [ARCHIVE_PARTIAL_KEY]: new Blob([bytes(9, 9, 9)]),
      [ARCHIVE_PROGRESS_KEY]: { receivedBytes: 3, totalBytes: 6 },
      [ARCHIVE_SOURCE_KEY]: { url: URL_, etag: '"v1"' },
    })
    mockFetch({ chunks: [bytes(1, 2, 3, 4)], status: 200, etag: '"v2"' })

    await downloadArchive(CORRIDOR_ARCHIVE_KEY, URL_)

    const stored = store[CORRIDOR_ARCHIVE_KEY] as Blob
    expect(stored.size).toBe(4)
    expect(new Uint8Array(await stored.arrayBuffer())).toEqual(bytes(1, 2, 3, 4))
  })

  it('records the source alongside the bytes when a transfer is interrupted', async () => {
    const store = withStore()
    mockFetch({ chunks: [bytes(1, 2)], totalBytes: 99, etag: '"v1"' })

    await expect(downloadArchive(CORRIDOR_ARCHIVE_KEY, URL_)).rejects.toThrow(
      ArchiveSizeMismatchError,
    )

    expect(store[ARCHIVE_SOURCE_KEY]).toEqual({ url: URL_, etag: '"v1"' })
  })

  it('ignores a weak ETag, which does not promise the byte identity a resume needs', async () => {
    const store = withStore()
    mockFetch({ chunks: [bytes(1, 2)], totalBytes: 99, etag: 'W/"v1"' })

    await expect(downloadArchive(CORRIDOR_ARCHIVE_KEY, URL_)).rejects.toThrow(
      ArchiveSizeMismatchError,
    )

    expect(store[ARCHIVE_SOURCE_KEY]).toEqual({ url: URL_, etag: undefined })
  })

  describe('downloadArchive — a response with nothing to read', () => {
    it('fails loudly rather than storing an empty archive', async () => {
      // A 200 with a null body is not a zero-byte map, it is a broken response.
      // Writing it to CORRIDOR_ARCHIVE_KEY would leave the app convinced it has
      // a map, offline, with no way to find out otherwise.
      const store = withStore()
      vi.spyOn(globalThis, 'fetch').mockResolvedValue(
        new Response(null, { status: 200, headers: { 'content-length': '3' } }),
      )

      await expect(downloadArchive(CORRIDOR_ARCHIVE_KEY, URL_)).rejects.toThrow(
        /no response body/,
      )
      expect(store[CORRIDOR_ARCHIVE_KEY]).toBeUndefined()
    })
  })

  describe('downloadArchive — a server that never says how big the file is', () => {
    it('still stores what arrived, rather than treating no length as zero length', async () => {
      // A chunked response carries no content-length. There is nothing to check
      // the size against, so the length check has to stand down instead of
      // deciding the archive is short - refusing a complete download over a
      // header the server was never obliged to send would be its own bug.
      const store = withStore()
      vi.spyOn(globalThis, 'fetch').mockImplementation(
        async () =>
          new Response(
            new ReadableStream<Uint8Array>({
              start(controller) {
                controller.enqueue(bytes(1, 2, 3, 4))
                controller.close()
              },
            }),
            { status: 200 },
          ),
      )

      await downloadArchive(CORRIDOR_ARCHIVE_KEY, URL_)

      const stored = store[CORRIDOR_ARCHIVE_KEY] as Blob
      expect(stored.size).toBe(4)
      expect(store[ARCHIVE_PARTIAL_KEY]).toBeUndefined()
    })

    it('reports progress against an unknown total rather than a made-up one', async () => {
      withStore()
      vi.spyOn(globalThis, 'fetch').mockImplementation(
        async () =>
          new Response(
            new ReadableStream<Uint8Array>({
              start(controller) {
                controller.enqueue(bytes(1, 2))
                controller.close()
              },
            }),
            { status: 200 },
          ),
      )
      const onProgress = vi.fn()

      await downloadArchive(CORRIDOR_ARCHIVE_KEY, URL_, { onProgress })

      expect(onProgress).toHaveBeenCalledWith({ receivedBytes: 2, totalBytes: 0 })
    })
  })
})

describe('downloadArchive — packages are independent (issue #200)', () => {
  // The multi-package guarantee in one sentence: every record a download
  // touches derives from its own package key, so nothing one package does -
  // succeed, fail mid-stream, or get deleted - can reach another package's
  // bytes. These tests run two packages through exactly those lifecycles.
  const OTHER_KEY = 'ourhike:test-dem'
  const OTHER_URL = 'https://cdn.example.org/dem.pmtiles'

  it("downloading one package leaves another package's archive and partial untouched", async () => {
    const corridorPartial = new Blob(['corridor partial'])
    const store = withStore({
      [ARCHIVE_PARTIAL_KEY]: corridorPartial,
      [ARCHIVE_SOURCE_KEY]: { url: URL_ },
      [ARCHIVE_PROGRESS_KEY]: { receivedBytes: 16, totalBytes: 100 },
    })
    mockFetch({ chunks: [bytes(9, 9, 9)] })

    await downloadArchive(OTHER_KEY, OTHER_URL)

    expect(store[OTHER_KEY]).toBeInstanceOf(Blob)
    // The corridor package's resumable state survives, byte for byte.
    expect(store[ARCHIVE_PARTIAL_KEY]).toBe(corridorPartial)
    expect(store[ARCHIVE_SOURCE_KEY]).toEqual({ url: URL_ })
    expect(store[ARCHIVE_PROGRESS_KEY]).toEqual({ receivedBytes: 16, totalBytes: 100 })
  })

  it("a failed download persists its partial under its own package, not another's", async () => {
    const store = withStore()
    mockFetch({ chunks: [bytes(1, 2)], totalBytes: 10 })

    await expect(downloadArchive(OTHER_KEY, OTHER_URL)).rejects.toThrow()

    expect(store[`${OTHER_KEY}:partial`]).toBeInstanceOf(Blob)
    expect(store[ARCHIVE_PARTIAL_KEY]).toBeUndefined()
  })

  it("deleting one package keeps every other package's archive", async () => {
    const corridorArchive = new Blob(['corridor'])
    const store = withStore({
      [CORRIDOR_ARCHIVE_KEY]: corridorArchive,
      [OTHER_KEY]: new Blob(['dem']),
      [`${OTHER_KEY}:partial`]: new Blob(['stale attempt']),
    })

    await deleteArchive(OTHER_KEY)

    expect(store[OTHER_KEY]).toBeUndefined()
    expect(store[`${OTHER_KEY}:partial`]).toBeUndefined()
    expect(store[CORRIDOR_ARCHIVE_KEY]).toBe(corridorArchive)
  })

  it('resume identity is judged per package: the same URL on another package starts clean', async () => {
    // A partial held by the corridor package must not be resumed onto by a
    // different package downloading from the same URL - the records simply
    // never meet, because the keys differ.
    const store = withStore({
      [ARCHIVE_PARTIAL_KEY]: new Blob(['held']),
      [ARCHIVE_SOURCE_KEY]: { url: URL_ },
    })
    const spy = mockFetch({ chunks: [bytes(5)] })

    await downloadArchive(OTHER_KEY, URL_)

    const init = spy.mock.calls[0][1] as RequestInit | undefined
    expect(init?.headers).toBeUndefined()
    expect(store[ARCHIVE_PARTIAL_KEY]).toBeInstanceOf(Blob)
  })
})

describe('the completion marker (#190)', () => {
  // Written on success, cleared on delete, and in localStorage rather than
  // IndexedDB - the whole point is surviving the store the archive did not.

  beforeEach(() => {
    localStorage.clear()
  })

  afterEach(() => {
    localStorage.clear()
  })

  it('records a completed download, after the bytes are really stored', async () => {
    withStore()
    mockFetch({ chunks: [bytes(1, 2, 3)] })

    expect(completedMarker(CORRIDOR_ARCHIVE_KEY)).toBeNull()
    await downloadArchive(CORRIDOR_ARCHIVE_KEY, URL_)

    expect(completedMarker(CORRIDOR_ARCHIVE_KEY)).toBeInstanceOf(Date)
  })

  it('does not record an attempt that failed short', async () => {
    // A marker without a completed archive is exactly the false eviction
    // claim the marker must never produce.
    withStore()
    mockFetch({ chunks: [bytes(1)], totalBytes: 3 })

    await expect(downloadArchive(CORRIDOR_ARCHIVE_KEY, URL_)).rejects.toThrow()

    expect(completedMarker(CORRIDOR_ARCHIVE_KEY)).toBeNull()
  })

  it('clears the marker when the hiker deletes the archive', async () => {
    // "The phone removed your map" about a deletion they performed would be
    // the marker lying in the other direction.
    withStore({ [CORRIDOR_ARCHIVE_KEY]: new Blob(['x']) })
    recordCompleted(CORRIDOR_ARCHIVE_KEY)

    await deleteArchive(CORRIDOR_ARCHIVE_KEY)

    expect(completedMarker(CORRIDOR_ARCHIVE_KEY)).toBeNull()
  })
})

describe('verification against the published hash (#197)', () => {
  // The failure being closed here is not a download that breaks - it is one
  // that succeeds and is wrong. Bytes from two builds spliced at the resume
  // point produce a file of exactly the expected length, so the size check
  // provably cannot see it (totalBytes is DEFINED as heldBytes + declared),
  // and what arrives is a PMTiles archive whose directory disagrees with its
  // tiles: a map that reports itself downloaded and renders wrong past the
  // seam, with no network to correct it.

  const HELD = bytes(1, 2, 3, 4)
  const REST = bytes(5, 6, 7, 8)
  const WHOLE = bytes(1, 2, 3, 4, 5, 6, 7, 8)

  /** The hash of a resume that went right: held bytes then the remainder. */
  const WHOLE_HASH = sha256Hex(WHOLE)

  it('stores an archive whose bytes hash to what was published', async () => {
    const store = withStore()
    mockFetch({ chunks: [bytes(1, 2, 3), bytes(4, 5, 6)] })
    mockedPublishedHash.mockResolvedValue(sha256Hex(bytes(1, 2, 3, 4, 5, 6)))

    await downloadArchive(CORRIDOR_ARCHIVE_KEY, URL_)

    expect(store[CORRIDOR_ARCHIVE_KEY]).toBeInstanceOf(Blob)
  })

  it('keeps nothing when the completed bytes are not what was published', async () => {
    const store = withStore()
    mockFetch({ chunks: [bytes(1, 2, 3)] })
    mockedPublishedHash.mockResolvedValue(sha256Hex(bytes(9, 9, 9)))

    await expect(downloadArchive(CORRIDOR_ARCHIVE_KEY, URL_)).rejects.toThrow(
      ArchiveHashMismatchError,
    )

    // Not stored, and not left resumable either: the bytes are the right
    // length and the wrong file, so resuming onto them would only rebuild
    // the same wrong archive.
    expect(store[CORRIDOR_ARCHIVE_KEY]).toBeUndefined()
    expect(store[ARCHIVE_PARTIAL_KEY]).toBeUndefined()
    expect(store[ARCHIVE_PROGRESS_KEY]).toBeUndefined()
    expect(store[ARCHIVE_SOURCE_KEY]).toBeUndefined()
  })

  it('leaves a working archive alone when an update fails verification', async () => {
    const working = new Blob(['the map that already works'])
    const store = withStore({ [CORRIDOR_ARCHIVE_KEY]: working })
    mockFetch({ chunks: [bytes(1, 2, 3)] })
    mockedPublishedHash.mockResolvedValue(sha256Hex(bytes(9, 9, 9)))

    await expect(downloadArchive(CORRIDOR_ARCHIVE_KEY, URL_)).rejects.toThrow(
      ArchiveHashMismatchError,
    )

    expect(store[CORRIDOR_ARCHIVE_KEY]).toBe(working)
  })

  it('catches a splice that completes to exactly the expected length', async () => {
    // The case the length check cannot reach. Four held bytes from one build,
    // four more from another; the server honours the range (206) and the
    // total is exactly what was promised. Only the digest can tell.
    const store = withStore({
      [ARCHIVE_PARTIAL_KEY]: new Blob([HELD]),
      [ARCHIVE_SOURCE_KEY]: { url: URL_, sha256: WHOLE_HASH },
    })
    mockFetch({ chunks: [bytes(90, 91, 92, 93)], status: 206, totalBytes: 4 })
    mockedPublishedHash.mockResolvedValue(WHOLE_HASH)

    await expect(downloadArchive(CORRIDOR_ARCHIVE_KEY, URL_)).rejects.toThrow(
      ArchiveHashMismatchError,
    )

    expect(store[CORRIDOR_ARCHIVE_KEY]).toBeUndefined()
    expect(store[ARCHIVE_PARTIAL_KEY]).toBeUndefined()
  })

  it('completes a resume whose bytes really do belong together', async () => {
    const store = withStore({
      [ARCHIVE_PARTIAL_KEY]: new Blob([HELD]),
      [ARCHIVE_SOURCE_KEY]: { url: URL_, sha256: WHOLE_HASH },
    })
    mockFetch({ chunks: [REST], status: 206, totalBytes: 4 })
    mockedPublishedHash.mockResolvedValue(WHOLE_HASH)

    await downloadArchive(CORRIDOR_ARCHIVE_KEY, URL_)

    const stored = new Uint8Array(
      await (store[CORRIDOR_ARCHIVE_KEY] as Blob).arrayBuffer(),
    )
    expect([...stored]).toEqual([...WHOLE])
  })

  it('drops a partial the bucket has republished away from, before asking for bytes', async () => {
    // The defence that does not depend on CORS exposing ETag - which is
    // exactly the configuration DATA_RELEASES.md's consequence #1 describes.
    // A published hash that has moved says the archive was rebuilt, so the
    // held bytes are from the previous release and there is no Range to send.
    const store = withStore({
      [ARCHIVE_PARTIAL_KEY]: new Blob([HELD]),
      [ARCHIVE_PROGRESS_KEY]: { receivedBytes: 4, totalBytes: 8 },
      [ARCHIVE_SOURCE_KEY]: { url: URL_, sha256: sha256Hex(bytes(77)) },
    })
    const spy = mockFetch({ chunks: [WHOLE] })
    mockedPublishedHash.mockResolvedValue(WHOLE_HASH)

    await downloadArchive(CORRIDOR_ARCHIVE_KEY, URL_)

    const init = spy.mock.calls[0][1] as RequestInit | undefined
    expect(init?.headers).toBeUndefined()
    const stored = new Uint8Array(
      await (store[CORRIDOR_ARCHIVE_KEY] as Blob).arrayBuffer(),
    )
    expect([...stored]).toEqual([...WHOLE])
  })

  it('resumes onto a partial the bucket still publishes the same hash for', async () => {
    const store = withStore({
      [ARCHIVE_PARTIAL_KEY]: new Blob([HELD]),
      [ARCHIVE_SOURCE_KEY]: { url: URL_, sha256: WHOLE_HASH },
    })
    const spy = mockFetch({ chunks: [REST], status: 206, totalBytes: 4 })
    mockedPublishedHash.mockResolvedValue(WHOLE_HASH)

    await downloadArchive(CORRIDOR_ARCHIVE_KEY, URL_)

    const init = spy.mock.calls[0][1] as RequestInit | undefined
    expect(new Headers(init?.headers).get('range')).toBe('bytes=4-')
    expect(store[CORRIDOR_ARCHIVE_KEY]).toBeInstanceOf(Blob)
  })

  it('carries the hash of held bytes across a failed attempt', async () => {
    // What makes a resume cheap: the next attempt starts from this state
    // rather than re-reading several hundred megabytes of Blob to catch up.
    const store = withStore()
    mockFetch({ chunks: [bytes(1, 2, 3)], totalBytes: 10 })
    mockedPublishedHash.mockResolvedValue(sha256Hex(WHOLE))

    await expect(downloadArchive(CORRIDOR_ARCHIVE_KEY, URL_)).rejects.toThrow(
      ArchiveSizeMismatchError,
    )

    const carried = (store[ARCHIVE_SOURCE_KEY] as { hash?: Sha256State }).hash
    expect(carried?.byteLength).toBe(3)
    expect(Sha256.fromState(carried as Sha256State).digest()).toBe(
      sha256Hex(bytes(1, 2, 3)),
    )
  })

  it('resumes from a carried hash state without re-reading the held bytes', async () => {
    const store = withStore({
      [ARCHIVE_PARTIAL_KEY]: new Blob([HELD]),
      [ARCHIVE_SOURCE_KEY]: {
        url: URL_,
        sha256: WHOLE_HASH,
        hash: new Sha256().update(HELD).toState(),
      },
    })
    mockFetch({ chunks: [REST], status: 206, totalBytes: 4 })
    mockedPublishedHash.mockResolvedValue(WHOLE_HASH)

    await downloadArchive(CORRIDOR_ARCHIVE_KEY, URL_)

    expect(store[CORRIDOR_ARCHIVE_KEY]).toBeInstanceOf(Blob)
  })

  it('re-hashes the held bytes when no state was carried', async () => {
    // A partial written by a build before this existed, or by an attempt
    // that found no published hash to check against. Re-reading is the cost;
    // being unable to verify would be the alternative.
    const store = withStore({
      [ARCHIVE_PARTIAL_KEY]: new Blob([HELD]),
      [ARCHIVE_SOURCE_KEY]: { url: URL_ },
    })
    mockFetch({ chunks: [REST], status: 206, totalBytes: 4 })
    mockedPublishedHash.mockResolvedValue(WHOLE_HASH)

    await downloadArchive(CORRIDOR_ARCHIVE_KEY, URL_)

    expect(store[CORRIDOR_ARCHIVE_KEY]).toBeInstanceOf(Blob)
  })

  it('ignores a carried state that claims more bytes than the partial holds', async () => {
    // Reachable: persistPartial writes the source record BEFORE the blob, on
    // purpose, and the blob write is the one that fails under quota pressure.
    // A state ahead of the bytes must not be trusted - it would digest a file
    // nobody has - and re-hashing from zero is always safe because the
    // partial only ever grows.
    const store = withStore({
      [ARCHIVE_PARTIAL_KEY]: new Blob([HELD]),
      [ARCHIVE_SOURCE_KEY]: {
        url: URL_,
        sha256: WHOLE_HASH,
        hash: new Sha256().update(WHOLE).toState(),
      },
    })
    mockFetch({ chunks: [REST], status: 206, totalBytes: 4 })
    mockedPublishedHash.mockResolvedValue(WHOLE_HASH)

    await downloadArchive(CORRIDOR_ARCHIVE_KEY, URL_)

    expect(store[CORRIDOR_ARCHIVE_KEY]).toBeInstanceOf(Blob)
  })

  it('starts the hash clean when the server ignores the range and resends the file', async () => {
    // A 200 in reply to a Range request means the whole file is coming. The
    // held bytes are not part of it, and hashing as though they were would
    // fail an archive that is perfectly good.
    const store = withStore({
      [ARCHIVE_PARTIAL_KEY]: new Blob([HELD]),
      [ARCHIVE_SOURCE_KEY]: {
        url: URL_,
        sha256: WHOLE_HASH,
        hash: new Sha256().update(HELD).toState(),
      },
    })
    mockFetch({ chunks: [WHOLE], status: 200 })
    mockedPublishedHash.mockResolvedValue(WHOLE_HASH)

    await downloadArchive(CORRIDOR_ARCHIVE_KEY, URL_)

    const stored = new Uint8Array(
      await (store[CORRIDOR_ARCHIVE_KEY] as Blob).arrayBuffer(),
    )
    expect([...stored]).toEqual([...WHOLE])
  })

  it('stores the archive unverified when nothing published a hash for it', async () => {
    // The download must not start failing because a metadata file moved.
    // Absence of an expectation is absence of a check, not a failed one.
    const store = withStore()
    mockFetch({ chunks: [bytes(1, 2, 3)] })
    mockedPublishedHash.mockResolvedValue(null)

    await downloadArchive(CORRIDOR_ARCHIVE_KEY, URL_)

    expect(store[CORRIDOR_ARCHIVE_KEY]).toBeInstanceOf(Blob)
  })

  it('records no hash state when there is nothing to check against', async () => {
    // No expectation, no reason to spend a phone's CPU on a digest nobody
    // will compare.
    const store = withStore()
    mockFetch({ chunks: [bytes(1, 2, 3)], totalBytes: 10 })
    mockedPublishedHash.mockResolvedValue(null)

    await expect(downloadArchive(CORRIDOR_ARCHIVE_KEY, URL_)).rejects.toThrow(
      ArchiveSizeMismatchError,
    )

    expect((store[ARCHIVE_SOURCE_KEY] as { hash?: unknown }).hash).toBeUndefined()
  })

  it('verifies against the hash the bucket publishes now, not the one held', async () => {
    // A partial with no recorded expectation (written before this existed)
    // resumed against a republished archive: the current manifest is what
    // the completed bytes are held to, and they will not match.
    const store = withStore({
      [ARCHIVE_PARTIAL_KEY]: new Blob([HELD]),
      [ARCHIVE_SOURCE_KEY]: { url: URL_ },
    })
    mockFetch({ chunks: [bytes(50, 51, 52, 53)], status: 206, totalBytes: 4 })
    mockedPublishedHash.mockResolvedValue(WHOLE_HASH)

    await expect(downloadArchive(CORRIDOR_ARCHIVE_KEY, URL_)).rejects.toThrow(
      ArchiveHashMismatchError,
    )

    expect(store[CORRIDOR_ARCHIVE_KEY]).toBeUndefined()
  })

  it('says plainly that nothing was kept', async () => {
    // The hiker's next move is a clean re-download, and the message has to
    // be enough to know that without guessing.
    withStore()
    mockFetch({ chunks: [bytes(1, 2, 3)] })
    mockedPublishedHash.mockResolvedValue(sha256Hex(bytes(9)))

    await expect(downloadArchive(CORRIDOR_ARCHIVE_KEY, URL_)).rejects.toThrow(
      /was not kept - please download it again/,
    )
  })
})
