import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { get, set, del } from 'idb-keyval'
import {
  downloadArchive,
  ARCHIVE_PARTIAL_KEY,
  ARCHIVE_PROGRESS_KEY,
  ARCHIVE_SOURCE_KEY,
  ArchiveSizeMismatchError,
} from './archiveDownload'
import { CORRIDOR_ARCHIVE_KEY } from '../map/pmtilesSource'

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

const mockedGet = vi.mocked(get)
const mockedSet = vi.mocked(set)
const mockedDel = vi.mocked(del)

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
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('downloadArchive — a clean first run', () => {
  it('stores the finished archive where the map reads it from', async () => {
    const store = withStore()
    mockFetch({ chunks: [bytes(1, 2, 3), bytes(4, 5, 6)] })

    await downloadArchive(URL_)

    expect(store[CORRIDOR_ARCHIVE_KEY]).toBeInstanceOf(Blob)
  })

  it('stores every byte it was sent, in order', async () => {
    const store = withStore()
    mockFetch({ chunks: [bytes(1, 2, 3), bytes(4, 5, 6)] })

    await downloadArchive(URL_)
    const stored = new Uint8Array(
      await (store[CORRIDOR_ARCHIVE_KEY] as Blob).arrayBuffer(),
    )

    expect([...stored]).toEqual([1, 2, 3, 4, 5, 6])
  })

  it('reports progress as chunks arrive, not only at the end', async () => {
    withStore()
    mockFetch({ chunks: [bytes(1, 2, 3), bytes(4, 5, 6)] })
    const onProgress = vi.fn()

    await downloadArchive(URL_, { onProgress })

    expect(onProgress.mock.calls.length).toBeGreaterThan(1)
    expect(onProgress).toHaveBeenLastCalledWith({ receivedBytes: 6, totalBytes: 6 })
  })

  it('clears the partial state once the archive is complete', async () => {
    const store = withStore()
    mockFetch({ chunks: [bytes(1, 2, 3)] })

    await downloadArchive(URL_)

    expect(store[ARCHIVE_PARTIAL_KEY]).toBeUndefined()
    expect(store[ARCHIVE_PROGRESS_KEY]).toBeUndefined()
  })

  it('asks for the whole file when nothing is held yet', async () => {
    withStore()
    const spy = mockFetch({ chunks: [bytes(1, 2, 3)] })

    await downloadArchive(URL_)
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

    await downloadArchive(URL_)
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

    await downloadArchive(URL_)
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

    await downloadArchive(URL_, { onProgress })

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

    await downloadArchive(URL_)
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

    await expect(downloadArchive(URL_)).rejects.toThrow()

    expect(store[ARCHIVE_PARTIAL_KEY]).toBeInstanceOf(Blob)
    expect(store[ARCHIVE_PROGRESS_KEY]).toMatchObject({ receivedBytes: 3 })
  })

  it('leaves a previously-downloaded archive untouched when a new attempt fails', async () => {
    const good = new Blob([bytes(7, 7, 7)])
    const store = withStore({ [CORRIDOR_ARCHIVE_KEY]: good })
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('offline'))

    await expect(downloadArchive(URL_)).rejects.toThrow()

    expect(store[CORRIDOR_ARCHIVE_KEY]).toBe(good)
  })

  it('refuses to store an archive shorter than the server said it would be', async () => {
    // Truncation is the failure a size check exists to catch: a short PMTiles
    // archive opens fine and then returns nothing for tiles past the cut.
    const store = withStore()
    mockFetch({ chunks: [bytes(1, 2, 3)], totalBytes: 99 })

    await expect(downloadArchive(URL_)).rejects.toBeInstanceOf(ArchiveSizeMismatchError)
    expect(store[CORRIDOR_ARCHIVE_KEY]).toBeUndefined()
  })

  it('keeps the partial bytes after a size mismatch, so a resume can finish it', async () => {
    const store = withStore()
    mockFetch({ chunks: [bytes(1, 2, 3)], totalBytes: 99 })

    await expect(downloadArchive(URL_)).rejects.toThrow()

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

    await expect(downloadArchive(URL_, { signal: controller.signal })).rejects.toThrow()

    expect(store[ARCHIVE_PARTIAL_KEY]).toBeInstanceOf(Blob)
    expect(store[CORRIDOR_ARCHIVE_KEY]).toBeUndefined()
  })

  it('rejects a non-OK response without touching stored state', async () => {
    const store = withStore()
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(null, { status: 404, statusText: 'Not Found' }),
    )

    await expect(downloadArchive(URL_)).rejects.toThrow(/404/)
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

    await downloadArchive(URL_)

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

    await downloadArchive(URL_)

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

    await downloadArchive(URL_)

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

    await downloadArchive(URL_)

    const stored = store[CORRIDOR_ARCHIVE_KEY] as Blob
    expect(stored.size).toBe(4)
    expect(new Uint8Array(await stored.arrayBuffer())).toEqual(bytes(1, 2, 3, 4))
  })

  it('records the source alongside the bytes when a transfer is interrupted', async () => {
    const store = withStore()
    mockFetch({ chunks: [bytes(1, 2)], totalBytes: 99, etag: '"v1"' })

    await expect(downloadArchive(URL_)).rejects.toThrow(ArchiveSizeMismatchError)

    expect(store[ARCHIVE_SOURCE_KEY]).toEqual({ url: URL_, etag: '"v1"' })
  })

  it('ignores a weak ETag, which does not promise the byte identity a resume needs', async () => {
    const store = withStore()
    mockFetch({ chunks: [bytes(1, 2)], totalBytes: 99, etag: 'W/"v1"' })

    await expect(downloadArchive(URL_)).rejects.toThrow(ArchiveSizeMismatchError)

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

      await expect(downloadArchive(URL_)).rejects.toThrow(/no response body/)
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

      await downloadArchive(URL_)

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

      await downloadArchive(URL_, { onProgress })

      expect(onProgress).toHaveBeenCalledWith({ receivedBytes: 2, totalBytes: 0 })
    })
  })
})
