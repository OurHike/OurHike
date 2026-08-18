import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { get, set, del } from 'idb-keyval'
import { useArchiveDownload } from './useArchiveDownload'
import {
  ARCHIVE_PARTIAL_KEY,
  ARCHIVE_PROGRESS_KEY,
  ARCHIVE_SOURCE_KEY,
} from './archiveDownload'
import { segmentKeyFor } from './archiveStore'
import { CORRIDOR_ARCHIVE_KEY } from '../map/pmtilesSource'

/** Every Blob byte the store holds, across however many records. What "the
 *  space was really freed" means once an archive is a run of segments (#553). */
function storedBytes(store: Record<string, unknown>): number {
  return Object.values(store).reduce<number>(
    (total, value) => total + (value instanceof Blob ? value.size : 0),
    0,
  )
}

// The hook exists to keep Downloads.tsx a pure render of the status it is
// handed, so what is worth testing here is the part the screen cannot see: the
// ordering between an in-flight download and the buttons that interrupt it.
//
// Aborting an attempt does not stop it at once, and on its way out it SAVES -
// downloadArchive keeps whatever arrived so the next attempt can resume. That
// is right when the app is closing and wrong when someone has just asked for
// the space back, which is the race these cover.

vi.mock('idb-keyval', () => ({
  get: vi.fn(),
  set: vi.fn(),
  del: vi.fn(),
  update: vi.fn(),
}))

const URL_ = 'https://cdn.example.org/background.pmtiles'
const ARTIFACT = 'background.pmtiles'

function withStore(initial: Record<string, unknown> = {}) {
  const store: Record<string, unknown> = { ...initial }
  vi.mocked(get).mockImplementation(async (key) => store[key as string])
  vi.mocked(set).mockImplementation(async (key, value) => {
    store[key as string] = value
  })
  vi.mocked(del).mockImplementation(async (key) => {
    delete store[key as string]
  })
  return store
}

/**
 * A download that delivers one chunk and then hangs, so a test can interrupt
 * it at a known point. Resolves `streaming` once the first chunk is out.
 */
function mockHangingFetch() {
  let releaseStreaming: () => void
  const streaming = new Promise<void>((resolve) => {
    releaseStreaming = resolve
  })

  vi.spyOn(globalThis, 'fetch').mockImplementation(
    async (_input, init?: RequestInit) =>
      ({
        ok: true,
        status: 200,
        statusText: 'OK',
        headers: new Headers({ 'content-length': '4096' }),
        body: new ReadableStream<Uint8Array>({
          start(controller) {
            controller.enqueue(new Uint8Array([1, 2, 3, 4]))
            // Never closed: the transfer is still in flight until the signal
            // aborts it, which is the state the buttons act on.
            init?.signal?.addEventListener('abort', () =>
              controller.error(new DOMException('Aborted', 'AbortError')),
            )
          },
          // Released here rather than in `start`, because `pull` is called only
          // once the consumer has TAKEN the chunk. Releasing on enqueue let the
          // interruption land before the download had read a single byte, and
          // "keeps what arrived" was then satisfied by an empty partial.
          pull() {
            releaseStreaming()
          },
        }),
      }) as unknown as Response,
  )

  return streaming
}

beforeEach(() => {
  vi.clearAllMocks()
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('useArchiveDownload', () => {
  it('really frees the space when a download is deleted mid-transfer', async () => {
    // The bug: remove() aborted and then deleted immediately, while the
    // aborted attempt was still writing its partial bytes back. The writes
    // landed after the deletes, so tapping Delete on a running download left
    // the partial in IndexedDB - several hundred megabytes still held on a
    // phone that had just been told they were gone.
    const store = withStore()
    const streaming = mockHangingFetch()

    const { result } = renderHook(() =>
      useArchiveDownload(CORRIDOR_ARCHIVE_KEY, URL_, ARTIFACT),
    )

    act(() => void result.current.start())
    await streaming

    await act(async () => {
      await result.current.remove()
    })

    // Not a key-by-key check: the bytes are what the hiker asked to get back,
    // and they are spread over segment records now. A partial left behind under
    // any name is several hundred megabytes still held on a phone that was just
    // told they were gone.
    expect(storedBytes(store)).toBe(0)
    expect(store[ARCHIVE_PARTIAL_KEY]).toBeUndefined()
    expect(store[ARCHIVE_PROGRESS_KEY]).toBeUndefined()
    expect(store[ARCHIVE_SOURCE_KEY]).toBeUndefined()
    expect(store[CORRIDOR_ARCHIVE_KEY]).toBeUndefined()
  })

  it('says the map is not downloaded after deleting one mid-transfer', async () => {
    // The same race seen from the screen: the interrupted attempt's own catch
    // set "failed, resumable" after the delete had set "not downloaded", so
    // the button someone had just tapped appeared not to have worked.
    withStore()
    const streaming = mockHangingFetch()

    const { result } = renderHook(() =>
      useArchiveDownload(CORRIDOR_ARCHIVE_KEY, URL_, ARTIFACT),
    )

    act(() => void result.current.start())
    await streaming

    await act(async () => {
      await result.current.remove()
    })

    await waitFor(() => {
      expect(result.current.status.state).toBe('not-downloaded')
    })
  })

  it('keeps the partial bytes when an attempt is interrupted any other way', async () => {
    // The counterpart the fix must not break: an attempt cut short by the app
    // closing, or by signal dropping, has to leave what arrived behind. That
    // is the whole promise of a resumable download.
    const store = withStore()
    const streaming = mockHangingFetch()

    const { result, unmount } = renderHook(() =>
      useArchiveDownload(CORRIDOR_ARCHIVE_KEY, URL_, ARTIFACT),
    )

    const attempt = result.current.start()
    await streaming
    unmount()
    await attempt.catch(() => undefined)

    await waitFor(() => {
      // Checkpointed into a segment record on the way out, which is where an
      // interrupted transfer's bytes live since #553.
      expect(store[segmentKeyFor(CORRIDOR_ARCHIVE_KEY, 0, 0)]).toBeInstanceOf(Blob)
    })
    expect(store[ARCHIVE_SOURCE_KEY]).toEqual({
      url: URL_,
      etag: undefined,
      generation: 0,
      segments: 1,
    })
  })
})
