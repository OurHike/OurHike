import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { act, renderHook, waitFor } from '@testing-library/react'
import { get } from 'idb-keyval'
import { useArchiveDownload } from './useArchiveDownload'
import { recordCompleted } from './storageHealth'
import {
  deleteArchive,
  downloadArchive,
  readDownloadProgress,
  ArchiveSizeMismatchError,
  ArchiveHashMismatchError,
} from './archiveDownload'
import { CORRIDOR_ARCHIVE_KEY } from '../map/pmtilesSource'

// The status the hook hands the Downloads screen, and the reason it gives when
// a transfer fails.
//
// Split from useArchiveDownload.test.ts rather than merged into it, because
// the two need opposite setups and a Vitest module registry is per-file:
// that file drives the REAL downloadArchive over a mocked fetch, which is what
// makes its abort/delete race meaningful. These cases need downloadArchive
// itself stubbed, so a 404, a non-Error rejection and a size mismatch can each
// be produced on demand.
//
// The failure worth the most here: the archive 404'd, the hook's catch
// swallowed the reason, and the screen went back to "Download the map" with
// nothing said. "Nothing happened" leaves someone with no idea whether to
// retry, wait, or check their signal - and it is invisible unless something
// asserts on the message.

vi.mock('idb-keyval', () => ({ get: vi.fn(), set: vi.fn(), del: vi.fn() }))
vi.mock('./archiveDownload', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./archiveDownload')>()
  return {
    ...actual,
    downloadArchive: vi.fn(),
    deleteArchive: vi.fn(),
    readDownloadProgress: vi.fn(),
  }
})

const URL_ = 'https://cdn.example.org/background_z12.pmtiles'
const ARTIFACT = 'background_z12.pmtiles'

beforeEach(() => {
  vi.mocked(get).mockResolvedValue(undefined)
  vi.mocked(readDownloadProgress).mockResolvedValue(null)
  vi.mocked(downloadArchive).mockResolvedValue(undefined)
  vi.mocked(deleteArchive).mockResolvedValue(undefined)
})

afterEach(() => {
  vi.clearAllMocks()
})

/**
 * Runs `body` while watching Node for unhandled rejections.
 *
 * Listens on `process`, not on window's `unhandledrejection`: jsdom does not
 * dispatch that event for rejections originating in test code, so a window
 * listener sees nothing and passes whether the bug is there or not. This is
 * what Vitest's own "Unhandled Errors" section reads, and a process listener
 * observes without suppressing.
 */
async function rejectionsWhile(body: () => Promise<void>): Promise<unknown[]> {
  const seen: unknown[] = []
  const onUnhandled = (reason: unknown) => seen.push(reason)
  process.on('unhandledRejection', onUnhandled)
  try {
    await body()
    await new Promise((resolve) => setTimeout(resolve, 50))
  } finally {
    process.off('unhandledRejection', onUnhandled)
  }
  return seen
}

describe('useArchiveDownload on mount', () => {
  it('starts at not-downloaded when the phone holds nothing', async () => {
    const { result } = renderHook(() =>
      useArchiveDownload(CORRIDOR_ARCHIVE_KEY, URL_, ARTIFACT),
    )

    await waitFor(() =>
      expect(result.current.status).toEqual({ state: 'not-downloaded' }),
    )
  })

  it('reflects an archive already on the phone', async () => {
    vi.mocked(get).mockResolvedValue(new Blob(['x'.repeat(120)]))

    const { result } = renderHook(() =>
      useArchiveDownload(CORRIDOR_ARCHIVE_KEY, URL_, ARTIFACT),
    )

    await waitFor(() => {
      expect(result.current.status).toMatchObject({
        state: 'downloaded',
        totalBytes: 120,
      })
    })
  })

  it('offers to resume an interrupted one rather than starting it over', async () => {
    // WIREFRAMES.md 7a: a transfer interrupted by the app closing is resumable
    // on the next launch, not just within one session.
    vi.mocked(readDownloadProgress).mockResolvedValue({
      receivedBytes: 40,
      totalBytes: 100,
    })

    const { result } = renderHook(() =>
      useArchiveDownload(CORRIDOR_ARCHIVE_KEY, URL_, ARTIFACT),
    )

    await waitFor(() => {
      expect(result.current.status).toEqual({
        state: 'failed',
        receivedBytes: 40,
        totalBytes: 100,
      })
    })
  })

  it('falls back to not-downloaded when the phone cannot say what it holds', async () => {
    // IndexedDB can fail outright - storage evicted under pressure, a corrupt
    // database, private browsing. This runs on mount, before the hiker has
    // asked for anything, so the failure has nowhere useful to go: it must not
    // become an unhandled rejection on app start, and the honest state is the
    // one that offers the download.
    vi.mocked(get).mockRejectedValue(new Error('IndexedDB is gone'))

    let hook: ReturnType<
      typeof renderHook<ReturnType<typeof useArchiveDownload>, unknown>
    >
    const rejections = await rejectionsWhile(async () => {
      await act(async () => {
        hook = renderHook(() => useArchiveDownload(CORRIDOR_ARCHIVE_KEY, URL_, ARTIFACT))
      })
    })

    expect(rejections).toEqual([])
    expect(hook!.result.current.status).toEqual({ state: 'not-downloaded' })
  })

  it('survives the progress read failing after the archive read succeeded', async () => {
    vi.mocked(readDownloadProgress).mockRejectedValue(new Error('IndexedDB is gone'))

    let hook: ReturnType<
      typeof renderHook<ReturnType<typeof useArchiveDownload>, unknown>
    >
    const rejections = await rejectionsWhile(async () => {
      await act(async () => {
        hook = renderHook(() => useArchiveDownload(CORRIDOR_ARCHIVE_KEY, URL_, ARTIFACT))
      })
    })

    expect(rejections).toEqual([])
    expect(hook!.result.current.status).toEqual({ state: 'not-downloaded' })
  })

  it('does not write state into a screen that has already gone away', async () => {
    // The mount read is async; unmounting before it lands must not set state
    // on an unmounted hook.
    let release: (value: undefined) => void = () => {}
    vi.mocked(get).mockReturnValue(
      new Promise((resolve) => {
        release = resolve
      }),
    )

    const { unmount } = renderHook(() =>
      useArchiveDownload(CORRIDOR_ARCHIVE_KEY, URL_, ARTIFACT),
    )
    unmount()
    await act(async () => {
      release(undefined)
    })

    expect(vi.mocked(readDownloadProgress)).not.toHaveBeenCalled()
  })
})

describe('useArchiveDownload running a download', () => {
  it('reports progress while the bytes arrive', async () => {
    vi.mocked(downloadArchive).mockImplementation(async (_key, _url, options) => {
      options?.onProgress?.({ receivedBytes: 50, totalBytes: 200 })
    })

    const { result } = renderHook(() =>
      useArchiveDownload(CORRIDOR_ARCHIVE_KEY, URL_, ARTIFACT),
    )
    await waitFor(() => expect(result.current.status.state).toBe('not-downloaded'))
    await act(async () => {
      await result.current.start()
    })

    expect(vi.mocked(downloadArchive).mock.calls[0][1]).toBe(URL_)
  })

  it('ends at downloaded, carrying the finished size', async () => {
    const { result } = renderHook(() =>
      useArchiveDownload(CORRIDOR_ARCHIVE_KEY, URL_, ARTIFACT),
    )
    await waitFor(() => expect(result.current.status.state).toBe('not-downloaded'))

    vi.mocked(get).mockImplementation((key) =>
      Promise.resolve(
        key === CORRIDOR_ARCHIVE_KEY ? new Blob(['y'.repeat(64)]) : undefined,
      ),
    )
    await act(async () => {
      await result.current.start()
    })

    expect(result.current.status).toMatchObject({ state: 'downloaded', totalBytes: 64 })
    expect(result.current.error).toBeNull()
  })

  it('reports zero bytes rather than crashing if the finished archive cannot be read back', async () => {
    const { result } = renderHook(() =>
      useArchiveDownload(CORRIDOR_ARCHIVE_KEY, URL_, ARTIFACT),
    )
    await waitFor(() => expect(result.current.status.state).toBe('not-downloaded'))

    await act(async () => {
      await result.current.start()
    })

    expect(result.current.status).toMatchObject({ state: 'downloaded', totalBytes: 0 })
  })

  it('resumes through the same path as a fresh start', async () => {
    const { result } = renderHook(() =>
      useArchiveDownload(CORRIDOR_ARCHIVE_KEY, URL_, ARTIFACT),
    )
    await waitFor(() => expect(result.current.status.state).toBe('not-downloaded'))

    await act(async () => {
      await result.current.resume()
    })

    expect(downloadArchive).toHaveBeenCalledTimes(1)
  })
})

describe('useArchiveDownload when the download fails', () => {
  it('says why, instead of quietly returning to the button', async () => {
    // The production failure: the archive 404'd, the catch swallowed the
    // reason, and the screen went back to "Download the map" with nothing
    // said. "Nothing happened" leaves someone with no idea whether to retry,
    // wait, or check their signal.
    vi.mocked(downloadArchive).mockRejectedValue(
      new Error('Archive download failed: 404 Not Found'),
    )

    const { result } = renderHook(() =>
      useArchiveDownload(CORRIDOR_ARCHIVE_KEY, URL_, ARTIFACT),
    )
    await waitFor(() => expect(result.current.status.state).toBe('not-downloaded'))
    await act(async () => {
      await result.current.start()
    })

    expect(result.current.error).toBe('Archive download failed: 404 Not Found')
  })

  it('still has something to say when what was thrown was not an Error', async () => {
    vi.mocked(downloadArchive).mockRejectedValue('a bare string')

    const { result } = renderHook(() =>
      useArchiveDownload(CORRIDOR_ARCHIVE_KEY, URL_, ARTIFACT),
    )
    await waitFor(() => expect(result.current.status.state).toBe('not-downloaded'))
    await act(async () => {
      await result.current.start()
    })

    expect(result.current.error).toBe('The map download failed.')
  })

  it('keeps the partial bytes visible as resumable', async () => {
    vi.mocked(downloadArchive).mockRejectedValue(new ArchiveSizeMismatchError(100, 60))
    vi.mocked(readDownloadProgress)
      .mockResolvedValueOnce(null) // the mount read
      .mockResolvedValue({ receivedBytes: 60, totalBytes: 100 })

    const { result } = renderHook(() =>
      useArchiveDownload(CORRIDOR_ARCHIVE_KEY, URL_, ARTIFACT),
    )
    await waitFor(() => expect(result.current.status.state).toBe('not-downloaded'))
    await act(async () => {
      await result.current.start()
    })

    expect(result.current.status).toEqual({
      state: 'failed',
      receivedBytes: 60,
      totalBytes: 100,
    })
  })

  it('falls back to not-downloaded when nothing at all was kept', async () => {
    vi.mocked(downloadArchive).mockRejectedValue(new Error('Failed to fetch'))

    const { result } = renderHook(() =>
      useArchiveDownload(CORRIDOR_ARCHIVE_KEY, URL_, ARTIFACT),
    )
    await waitFor(() => expect(result.current.status.state).toBe('not-downloaded'))
    await act(async () => {
      await result.current.start()
    })

    expect(result.current.status).toEqual({ state: 'not-downloaded' })
  })

  it('clears the old message when a retry begins, so a stale 404 is not still on screen', async () => {
    vi.mocked(downloadArchive).mockRejectedValueOnce(
      new Error('Archive download failed: 404'),
    )

    const { result } = renderHook(() =>
      useArchiveDownload(CORRIDOR_ARCHIVE_KEY, URL_, ARTIFACT),
    )
    await waitFor(() => expect(result.current.status.state).toBe('not-downloaded'))
    await act(async () => {
      await result.current.start()
    })
    expect(result.current.error).not.toBeNull()

    await act(async () => {
      await result.current.start()
    })

    expect(result.current.error).toBeNull()
  })
})

describe('useArchiveDownload removing the archive', () => {
  it('deletes it and returns to not-downloaded', async () => {
    vi.mocked(get).mockResolvedValue(new Blob(['z']))

    const { result } = renderHook(() =>
      useArchiveDownload(CORRIDOR_ARCHIVE_KEY, URL_, ARTIFACT),
    )
    await waitFor(() => expect(result.current.status.state).toBe('downloaded'))
    await act(async () => {
      await result.current.remove()
    })

    expect(deleteArchive).toHaveBeenCalledTimes(1)
    expect(result.current.status).toEqual({ state: 'not-downloaded' })
  })

  it('clears any error message along with the archive', async () => {
    vi.mocked(downloadArchive).mockRejectedValue(
      new Error('Archive download failed: 404'),
    )

    const { result } = renderHook(() =>
      useArchiveDownload(CORRIDOR_ARCHIVE_KEY, URL_, ARTIFACT),
    )
    await waitFor(() => expect(result.current.status.state).toBe('not-downloaded'))
    await act(async () => {
      await result.current.start()
    })
    expect(result.current.error).not.toBeNull()

    await act(async () => {
      await result.current.remove()
    })

    expect(result.current.error).toBeNull()
  })

  it('does not leave a "download failed" alert after deleting mid-transfer', async () => {
    // The abort remove() issues rejects the in-flight attempt DURING
    // remove()'s await - after its setError(null) has already run. The
    // hook's catch used to surface that rejection like any other failure,
    // so a successful delete ended with role="alert" telling the hiker
    // their download had failed. An abort the hook itself asked for is not
    // news.
    vi.mocked(downloadArchive).mockImplementation(
      (_key, _url, options) =>
        new Promise((_resolve, reject) =>
          options?.signal?.addEventListener('abort', () =>
            reject(new DOMException('Aborted', 'AbortError')),
          ),
        ),
    )

    const { result } = renderHook(() =>
      useArchiveDownload(CORRIDOR_ARCHIVE_KEY, URL_, ARTIFACT),
    )
    await waitFor(() => expect(result.current.status.state).toBe('not-downloaded'))
    let attempt: Promise<void> | undefined
    act(() => {
      attempt = result.current.start()
    })
    await act(async () => {
      await result.current.remove()
    })

    expect(result.current.error).toBeNull()
    expect(result.current.status).toEqual({ state: 'not-downloaded' })
    await attempt
  })

  it('ignores a second start while an attempt is already in flight', async () => {
    // There is an async gap between the tap and status becoming
    // 'downloading' (two IndexedDB reads) in which the screen still offers
    // the button. A second run() would overwrite abortRef and runningRef,
    // so remove() would abort only the newest attempt while the orphan
    // kept streaming and persisted its partial after the delete.
    vi.mocked(downloadArchive).mockImplementation(
      (_key, _url, options) =>
        new Promise((_resolve, reject) =>
          options?.signal?.addEventListener('abort', () =>
            reject(new DOMException('Aborted', 'AbortError')),
          ),
        ),
    )

    const { result } = renderHook(() =>
      useArchiveDownload(CORRIDOR_ARCHIVE_KEY, URL_, ARTIFACT),
    )
    await waitFor(() => expect(result.current.status.state).toBe('not-downloaded'))
    let first: Promise<void> | undefined
    let second: Promise<void> | undefined
    act(() => {
      first = result.current.start()
      second = result.current.start()
    })

    expect(second).toBe(first)
    expect(downloadArchive).toHaveBeenCalledTimes(1)

    await act(async () => {
      await result.current.remove()
    })
  })

  it('still allows a retry once the failed attempt has settled', async () => {
    // The one-attempt guard must clear when the attempt settles, or the
    // retry button would silently hand back the corpse of the failure it
    // exists to retry.
    vi.mocked(downloadArchive).mockRejectedValueOnce(new Error('Failed to fetch'))
    vi.mocked(downloadArchive).mockResolvedValueOnce(undefined)

    const { result } = renderHook(() =>
      useArchiveDownload(CORRIDOR_ARCHIVE_KEY, URL_, ARTIFACT),
    )
    await waitFor(() => expect(result.current.status.state).toBe('not-downloaded'))
    await act(async () => {
      await result.current.start()
    })
    expect(result.current.error).not.toBeNull()

    await act(async () => {
      await result.current.start()
    })

    expect(downloadArchive).toHaveBeenCalledTimes(2)
    expect(result.current.status.state).toBe('downloaded')
  })

  it('aborts a transfer that is still running, rather than deleting underneath it', async () => {
    let seen: AbortSignal | undefined
    vi.mocked(downloadArchive).mockImplementation(async (_key, _url, options) => {
      seen = options?.signal
      await new Promise((resolve) => setTimeout(resolve, 0))
    })

    const { result } = renderHook(() =>
      useArchiveDownload(CORRIDOR_ARCHIVE_KEY, URL_, ARTIFACT),
    )
    await waitFor(() => expect(result.current.status.state).toBe('not-downloaded'))
    await act(async () => {
      await result.current.start()
    })
    await act(async () => {
      await result.current.remove()
    })

    expect(seen?.aborted).toBe(true)
  })
})

describe('useArchiveDownload on unmount', () => {
  it('aborts a transfer in flight, so a closed app is not still pulling a gigabyte', async () => {
    let seen: AbortSignal | undefined
    vi.mocked(downloadArchive).mockImplementation(async (_key, _url, options) => {
      seen = options?.signal
    })

    const { result, unmount } = renderHook(() =>
      useArchiveDownload(CORRIDOR_ARCHIVE_KEY, URL_, ARTIFACT),
    )
    await waitFor(() => expect(result.current.status.state).toBe('not-downloaded'))
    await act(async () => {
      await result.current.start()
    })

    unmount()

    expect(seen?.aborted).toBe(true)
  })

  describe('useArchiveDownload deleting while an attempt is failing', () => {
    it('still frees the space when the failing attempt cannot even read its own progress', async () => {
      // remove() waits out the in-flight attempt before deleting, because an
      // aborted attempt SAVES on its way out and would otherwise write the
      // partial bytes back after the delete. That wait has to survive the
      // attempt rejecting rather than resolving - here readDownloadProgress
      // itself fails inside the hook's own catch, so run() rejects outright.
      vi.mocked(downloadArchive).mockRejectedValue(new Error('Failed to fetch'))
      vi.mocked(readDownloadProgress).mockRejectedValue(new Error('IndexedDB is gone'))

      const { result } = renderHook(() =>
        useArchiveDownload(CORRIDOR_ARCHIVE_KEY, URL_, ARTIFACT),
      )

      await act(async () => {
        await result.current.start().catch(() => undefined)
      })
      await act(async () => {
        await result.current.remove()
      })

      expect(deleteArchive).toHaveBeenCalledTimes(1)
      expect(result.current.status).toEqual({ state: 'not-downloaded' })
    })
  })
})

describe('eviction, told apart from absence (#190)', () => {
  // The FarOut failure class: the archive was downloaded, the OS evicted it,
  // and the screen offered a fresh download as if nothing had ever been
  // here. The completion marker (storageHealth.ts, localStorage) is what
  // lets the hook say "your map is gone" instead.

  beforeEach(() => {
    localStorage.clear()
  })

  afterEach(() => {
    localStorage.clear()
  })

  it('reports evicted when a completed archive left its marker but no bytes', async () => {
    const finished = new Date('2026-08-01T09:00:00Z')
    recordCompleted(CORRIDOR_ARCHIVE_KEY, finished)

    const { result } = renderHook(() =>
      useArchiveDownload(CORRIDOR_ARCHIVE_KEY, URL_, ARTIFACT),
    )

    await waitFor(() => {
      expect(result.current.status).toMatchObject({ state: 'evicted' })
    })
    expect(
      (result.current.status as { completedAt: Date }).completedAt.toISOString(),
    ).toBe(finished.toISOString())
  })

  it('still reports evicted when IndexedDB itself cannot be read', async () => {
    // The marker lives in localStorage on purpose: the known real-world
    // incidents broke IndexedDB specifically, and this is the case where
    // the old code silently said not-downloaded.
    vi.mocked(get).mockRejectedValue(new Error('database is broken'))
    recordCompleted(CORRIDOR_ARCHIVE_KEY)

    const { result } = renderHook(() =>
      useArchiveDownload(CORRIDOR_ARCHIVE_KEY, URL_, ARTIFACT),
    )

    await waitFor(() => {
      expect(result.current.status).toMatchObject({ state: 'evicted' })
    })
  })

  it('a resumable partial outranks the marker - resume is the better offer', async () => {
    recordCompleted(CORRIDOR_ARCHIVE_KEY)
    vi.mocked(readDownloadProgress).mockResolvedValue({
      receivedBytes: 40,
      totalBytes: 100,
    })

    const { result } = renderHook(() =>
      useArchiveDownload(CORRIDOR_ARCHIVE_KEY, URL_, ARTIFACT),
    )

    await waitFor(() => {
      expect(result.current.status).toMatchObject({ state: 'failed' })
    })
  })

  it('an intact archive outranks the marker, which merely describes it', async () => {
    recordCompleted(CORRIDOR_ARCHIVE_KEY)
    vi.mocked(get).mockResolvedValue(new Blob(['x']))

    const { result } = renderHook(() =>
      useArchiveDownload(CORRIDOR_ARCHIVE_KEY, URL_, ARTIFACT),
    )

    await waitFor(() => {
      expect(result.current.status).toMatchObject({ state: 'downloaded' })
    })
  })

  it('keeps saying evicted after a failed re-download that saved nothing', async () => {
    recordCompleted(CORRIDOR_ARCHIVE_KEY)
    vi.mocked(downloadArchive).mockRejectedValue(new Error('HTTP 503'))

    const { result } = renderHook(() =>
      useArchiveDownload(CORRIDOR_ARCHIVE_KEY, URL_, ARTIFACT),
    )
    await waitFor(() => {
      expect(result.current.status).toMatchObject({ state: 'evicted' })
    })

    await act(async () => {
      await result.current.start()
    })

    expect(result.current.status).toMatchObject({ state: 'evicted' })
    expect(result.current.error).toContain('HTTP 503')
  })
})

describe('durable storage (#190)', () => {
  it('asks the browser for persistence when a download starts, and reports the answer', async () => {
    const persist = vi.fn().mockResolvedValue(true)
    vi.stubGlobal('navigator', { ...globalThis.navigator, storage: { persist } })

    const { result } = renderHook(() =>
      useArchiveDownload(CORRIDOR_ARCHIVE_KEY, URL_, ARTIFACT),
    )
    await act(async () => {
      await result.current.start()
    })

    expect(persist).toHaveBeenCalled()
    await waitFor(() => expect(result.current.persistence).toBe('granted'))
    vi.unstubAllGlobals()
  })

  it('reflects the standing answer on mount, without prompting', async () => {
    const persist = vi.fn()
    const persisted = vi.fn().mockResolvedValue(true)
    vi.stubGlobal('navigator', {
      ...globalThis.navigator,
      storage: { persist, persisted },
    })

    const { result } = renderHook(() =>
      useArchiveDownload(CORRIDOR_ARCHIVE_KEY, URL_, ARTIFACT),
    )

    await waitFor(() => expect(result.current.persistence).toBe('granted'))
    expect(persist).not.toHaveBeenCalled()
    vi.unstubAllGlobals()
  })
})

describe('a hash mismatch becomes its own state, not an error string (#238)', () => {
  // downloadArchive discards everything before throwing this, so the generic
  // catch path would land on absentStatus - "not downloaded", or "evicted"
  // with the marker set - and the card would say nothing about WHY a download
  // that visibly ran produced no map. The type is caught at the one moment it
  // still exists and becomes the state the card renders its own copy from.
  //
  // Every case waits for the mount read to settle before starting: the mount
  // effect's IndexedDB reads resolve on their own clock, and a start()
  // racing them can have its verdict overwritten by the mount's stale answer
  // - which is a fact about test timing, not about a hiker's phone, where
  // the tap comes seconds after launch.

  beforeEach(() => {
    localStorage.clear()
  })

  afterEach(() => {
    localStorage.clear()
  })

  it('reports hash-mismatch after a refused download, with no error string beside it', async () => {
    vi.mocked(downloadArchive).mockRejectedValue(
      new ArchiveHashMismatchError('aa'.repeat(32), 'bb'.repeat(32)),
    )

    const { result } = renderHook(() =>
      useArchiveDownload(CORRIDOR_ARCHIVE_KEY, URL_, ARTIFACT),
    )
    await waitFor(() => {
      expect(result.current.status).toEqual({ state: 'not-downloaded' })
    })
    await act(async () => {
      await result.current.start()
    })

    expect(result.current.status).toEqual({ state: 'hash-mismatch' })
    // The card's own state copy is the message now; an error alert on top of
    // it would tell the same story twice in two registers.
    expect(result.current.error).toBe(null)
  })

  it('outranks the eviction marker - this refusal is newer news', async () => {
    recordCompleted(CORRIDOR_ARCHIVE_KEY)
    vi.mocked(downloadArchive).mockRejectedValue(
      new ArchiveHashMismatchError('aa'.repeat(32), 'bb'.repeat(32)),
    )

    const { result } = renderHook(() =>
      useArchiveDownload(CORRIDOR_ARCHIVE_KEY, URL_, ARTIFACT),
    )
    await waitFor(() => {
      expect(result.current.status).toMatchObject({ state: 'evicted' })
    })

    await act(async () => {
      await result.current.start()
    })

    expect(result.current.status).toEqual({ state: 'hash-mismatch' })
  })

  it('is session-only: a fresh mount reads the store, which holds nothing', async () => {
    // Nothing about a mismatch is persisted - that is the point of the
    // discard - so a reload lawfully reports the store's truth instead.
    vi.mocked(downloadArchive).mockRejectedValue(
      new ArchiveHashMismatchError('aa'.repeat(32), 'bb'.repeat(32)),
    )

    const first = renderHook(() =>
      useArchiveDownload(CORRIDOR_ARCHIVE_KEY, URL_, ARTIFACT),
    )
    await waitFor(() => {
      expect(first.result.current.status).toEqual({ state: 'not-downloaded' })
    })
    await act(async () => {
      await first.result.current.start()
    })
    expect(first.result.current.status).toEqual({ state: 'hash-mismatch' })
    first.unmount()

    const second = renderHook(() =>
      useArchiveDownload(CORRIDOR_ARCHIVE_KEY, URL_, ARTIFACT),
    )
    await waitFor(() => {
      expect(second.result.current.status).toEqual({ state: 'not-downloaded' })
    })
  })

  it('a deliberate delete afterwards still lands on not-downloaded', async () => {
    vi.mocked(downloadArchive).mockRejectedValue(
      new ArchiveHashMismatchError('aa'.repeat(32), 'bb'.repeat(32)),
    )

    const { result } = renderHook(() =>
      useArchiveDownload(CORRIDOR_ARCHIVE_KEY, URL_, ARTIFACT),
    )
    await waitFor(() => {
      expect(result.current.status).toEqual({ state: 'not-downloaded' })
    })
    await act(async () => {
      await result.current.start()
    })
    await act(async () => {
      await result.current.remove()
    })

    expect(result.current.status).toEqual({ state: 'not-downloaded' })
  })
})
