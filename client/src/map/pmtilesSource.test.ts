import { describe, it, expect, vi, beforeEach } from 'vitest'
import { get } from 'idb-keyval'
import {
  IndexedDbArchiveSource,
  ArchiveNotDownloadedError,
  CORRIDOR_ARCHIVE_KEY,
} from './pmtilesSource'

// The downloaded whole-corridor archive (WIREFRAMES.md Known Deviations #1 -
// one package, not per-section) lives as a Blob in IndexedDB. pmtiles reads it
// through its `Source` interface as byte ranges, so this adapter's whole job is
// range reads against that Blob - never the network. TECHNICAL_ARCHITECTURE.md's
// offline-first rule means a missing archive must fail LOUDLY rather than
// resolve to empty bytes, which would paint a convincingly blank map.

vi.mock('idb-keyval', () => ({ get: vi.fn() }))

const mockedGet = vi.mocked(get)

/** A Blob whose bytes are 0,1,2,...,length-1 so a slice is self-describing. */
function countingBlob(length: number): Blob {
  return new Blob([new Uint8Array(Array.from({ length }, (_, i) => i % 256))])
}

describe('IndexedDbArchiveSource', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('reads exactly the requested byte range out of the stored archive', async () => {
    mockedGet.mockResolvedValue(countingBlob(1000))
    const source = new IndexedDbArchiveSource()

    const { data } = await source.getBytes(10, 5)

    expect(new Uint8Array(data)).toEqual(new Uint8Array([10, 11, 12, 13, 14]))
  })

  it('reads a range at the very start of the archive (the pmtiles header lives there)', async () => {
    mockedGet.mockResolvedValue(countingBlob(1000))
    const source = new IndexedDbArchiveSource()

    const { data } = await source.getBytes(0, 3)

    expect(new Uint8Array(data)).toEqual(new Uint8Array([0, 1, 2]))
  })

  it('throws a named, actionable error when no archive has been downloaded yet - never empty bytes', async () => {
    mockedGet.mockResolvedValue(undefined)
    const source = new IndexedDbArchiveSource()

    await expect(source.getBytes(0, 16)).rejects.toBeInstanceOf(ArchiveNotDownloadedError)
  })

  it('does not cache the not-downloaded failure - a read after the download finishes succeeds', async () => {
    const source = new IndexedDbArchiveSource()

    mockedGet.mockResolvedValue(undefined)
    await expect(source.getBytes(0, 4)).rejects.toBeInstanceOf(ArchiveNotDownloadedError)

    // The download completes between the two reads. A naively memoised handle
    // would have cached the rejected promise and stayed broken for the session.
    mockedGet.mockResolvedValue(countingBlob(100))
    const { data } = await source.getBytes(0, 4)

    expect(new Uint8Array(data)).toEqual(new Uint8Array([0, 1, 2, 3]))
  })

  it('looks the archive up in IndexedDB once and reuses the handle across many range reads', async () => {
    mockedGet.mockResolvedValue(countingBlob(1000))
    const source = new IndexedDbArchiveSource()

    await source.getBytes(0, 4)
    // What one lookup costs is archiveStore.ts's business - since #553 it reads
    // the completion marker and may fall through to the legacy whole-archive
    // record. What matters here is that it does not happen again per range read:
    // pmtiles issues one of these for every tile, and a re-read per tile would
    // put an IndexedDB round trip in the middle of every camera move.
    const afterFirstRead = mockedGet.mock.calls.length

    await source.getBytes(100, 4)
    await source.getBytes(500, 4)

    expect(mockedGet.mock.calls.length).toBe(afterFirstRead)
  })

  it('exposes a stable key, which is what pmtiles caches decoded directories against', () => {
    const source = new IndexedDbArchiveSource()

    expect(source.getKey()).toBe(source.getKey())
    expect(source.getKey()).toBe(CORRIDOR_ARCHIVE_KEY)
  })

  it('never touches the network - the archive is on-device by definition', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch')
    mockedGet.mockResolvedValue(countingBlob(100))
    const source = new IndexedDbArchiveSource()

    await source.getBytes(0, 8)

    expect(fetchSpy).not.toHaveBeenCalled()
    fetchSpy.mockRestore()
  })
})
