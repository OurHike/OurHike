import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { act, renderHook, waitFor } from '@testing-library/react'
import { get } from 'idb-keyval'
import { useArchiveDownload } from './useArchiveDownload'
import {
  deleteArchive,
  downloadArchive,
  readDownloadProgress,
  ArchiveSizeMismatchError,
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

beforeEach(() => {
  vi.mocked(get).mockResolvedValue(undefined)
  vi.mocked(readDownloadProgress).mockResolvedValue(null)
  vi.mocked(downloadArchive).mockResolvedValue(undefined)
  vi.mocked(deleteArchive).mockResolvedValue(undefined)
})

afterEach(() => {
  vi.clearAllMocks()
})

describe('useArchiveDownload on mount', () => {
  it('starts at not-downloaded when the phone holds nothing', async () => {
    const { result } = renderHook(() => useArchiveDownload(URL_))

    await waitFor(() =>
      expect(result.current.status).toEqual({ state: 'not-downloaded' }),
    )
  })

  it('reflects an archive already on the phone', async () => {
    vi.mocked(get).mockResolvedValue(new Blob(['x'.repeat(120)]))

    const { result } = renderHook(() => useArchiveDownload(URL_))

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

    const { result } = renderHook(() => useArchiveDownload(URL_))

    await waitFor(() => {
      expect(result.current.status).toEqual({
        state: 'failed',
        receivedBytes: 40,
        totalBytes: 100,
      })
    })
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

    const { unmount } = renderHook(() => useArchiveDownload(URL_))
    unmount()
    await act(async () => {
      release(undefined)
    })

    expect(vi.mocked(readDownloadProgress)).not.toHaveBeenCalled()
  })
})

describe('useArchiveDownload running a download', () => {
  it('reports progress while the bytes arrive', async () => {
    vi.mocked(downloadArchive).mockImplementation(async (_url, options) => {
      options?.onProgress?.({ receivedBytes: 50, totalBytes: 200 })
    })

    const { result } = renderHook(() => useArchiveDownload(URL_))
    await waitFor(() => expect(result.current.status.state).toBe('not-downloaded'))
    await act(async () => {
      await result.current.start()
    })

    expect(vi.mocked(downloadArchive).mock.calls[0][0]).toBe(URL_)
  })

  it('ends at downloaded, carrying the finished size', async () => {
    const { result } = renderHook(() => useArchiveDownload(URL_))
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
    const { result } = renderHook(() => useArchiveDownload(URL_))
    await waitFor(() => expect(result.current.status.state).toBe('not-downloaded'))

    await act(async () => {
      await result.current.start()
    })

    expect(result.current.status).toMatchObject({ state: 'downloaded', totalBytes: 0 })
  })

  it('resumes through the same path as a fresh start', async () => {
    const { result } = renderHook(() => useArchiveDownload(URL_))
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

    const { result } = renderHook(() => useArchiveDownload(URL_))
    await waitFor(() => expect(result.current.status.state).toBe('not-downloaded'))
    await act(async () => {
      await result.current.start()
    })

    expect(result.current.error).toBe('Archive download failed: 404 Not Found')
  })

  it('still has something to say when what was thrown was not an Error', async () => {
    vi.mocked(downloadArchive).mockRejectedValue('a bare string')

    const { result } = renderHook(() => useArchiveDownload(URL_))
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

    const { result } = renderHook(() => useArchiveDownload(URL_))
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

    const { result } = renderHook(() => useArchiveDownload(URL_))
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

    const { result } = renderHook(() => useArchiveDownload(URL_))
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

    const { result } = renderHook(() => useArchiveDownload(URL_))
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

    const { result } = renderHook(() => useArchiveDownload(URL_))
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

  it('aborts a transfer that is still running, rather than deleting underneath it', async () => {
    let seen: AbortSignal | undefined
    vi.mocked(downloadArchive).mockImplementation(async (_url, options) => {
      seen = options?.signal
      await new Promise((resolve) => setTimeout(resolve, 0))
    })

    const { result } = renderHook(() => useArchiveDownload(URL_))
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
    vi.mocked(downloadArchive).mockImplementation(async (_url, options) => {
      seen = options?.signal
    })

    const { result, unmount } = renderHook(() => useArchiveDownload(URL_))
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

      const { result } = renderHook(() => useArchiveDownload(URL_))

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
