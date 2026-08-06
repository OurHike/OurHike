import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { get, set, del } from 'idb-keyval'
import { useArchiveDownloads } from './useArchiveDownload'
import { partialKeyFor, progressKeyFor, sourceKeyFor } from './archiveDownload'

// #192's acceptance, as tests: two packages downloaded, one deleted, one
// resumed after an interrupted download - every state correct and reported
// against the package it belongs to.
//
// The single-package view of this hook has its own files
// (useArchiveDownload.test.ts and .status.test.ts); what is worth testing
// here is only what plurality adds - that one package's progress, failure,
// deletion and resume are its own, and that holding several does not make
// them interfere.

vi.mock('idb-keyval', () => ({ get: vi.fn(), set: vi.fn(), del: vi.fn() }))

const SHEET = {
  packageKey: 'ourhike:sheet',
  url: 'https://cdn.example.org/sheet.pmtiles',
}
const TERRAIN = { packageKey: 'ourhike:dem', url: 'https://cdn.example.org/dem.pmtiles' }
const BOTH = [SHEET, TERRAIN]

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

/** Bytes per URL. A URL with no entry 404s, which is how a package that is
 *  published nowhere behaves. Honours `Range`, so a resume gets a 206 and
 *  the remainder rather than the whole file again. */
function mockFetch(bodies: Record<string, Uint8Array>) {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init?: RequestInit) => {
    const body = bodies[String(input)]
    if (body === undefined) {
      return {
        ok: false,
        status: 404,
        statusText: 'Not Found',
        headers: new Headers(),
      } as Response
    }

    const range = new Headers(init?.headers).get('Range')
    const from = range === null ? 0 : Number(/bytes=(\d+)-/.exec(range)?.[1] ?? 0)
    const sent = body.slice(from)

    return {
      ok: true,
      status: from > 0 ? 206 : 200,
      statusText: 'OK',
      headers: new Headers({ 'content-length': String(sent.length) }),
      body: new ReadableStream<Uint8Array>({
        start(controller) {
          controller.enqueue(sent)
          controller.close()
        },
      }),
    } as unknown as Response
  })
}

const SHEET_BYTES = new Uint8Array(8).fill(1)
const TERRAIN_BYTES = new Uint8Array(6).fill(2)

beforeEach(() => {
  localStorage.clear()
})

afterEach(() => {
  vi.restoreAllMocks()
  vi.clearAllMocks()
})

describe('holding several packages at once', () => {
  it('downloads two packages and reports each one’s own size', async () => {
    withStore()
    mockFetch({ [SHEET.url]: SHEET_BYTES, [TERRAIN.url]: TERRAIN_BYTES })

    const { result } = renderHook(() => useArchiveDownloads(BOTH))

    await act(async () => {
      await Promise.all([
        result.current.start(SHEET.packageKey),
        result.current.start(TERRAIN.packageKey),
      ])
    })

    await waitFor(() => {
      expect(result.current.statusFor(SHEET.packageKey)).toEqual({
        state: 'downloaded',
        totalBytes: SHEET_BYTES.length,
        completedAt: expect.any(Date),
      })
      expect(result.current.statusFor(TERRAIN.packageKey)).toEqual({
        state: 'downloaded',
        totalBytes: TERRAIN_BYTES.length,
        completedAt: expect.any(Date),
      })
    })
  })

  it('deletes one package without touching the other’s bytes', async () => {
    const store = withStore()
    mockFetch({ [SHEET.url]: SHEET_BYTES, [TERRAIN.url]: TERRAIN_BYTES })

    const { result } = renderHook(() => useArchiveDownloads(BOTH))

    await act(async () => {
      await Promise.all([
        result.current.start(SHEET.packageKey),
        result.current.start(TERRAIN.packageKey),
      ])
    })
    await act(async () => {
      await result.current.remove(SHEET.packageKey)
    })

    expect(store[SHEET.packageKey]).toBeUndefined()
    expect(store[TERRAIN.packageKey]).toBeInstanceOf(Blob)
    await waitFor(() => {
      expect(result.current.statusFor(SHEET.packageKey)).toEqual({
        state: 'not-downloaded',
      })
      expect(result.current.statusFor(TERRAIN.packageKey).state).toBe('downloaded')
    })
  })

  it('resumes an interrupted package from what it already holds', async () => {
    // Two of the terrain package's six bytes arrived before the transfer
    // dropped. Resuming asks for the rest - it never starts again from zero,
    // which is the whole promise of WIREFRAMES.md `7a`.
    const held = new Blob([TERRAIN_BYTES.slice(0, 2)])
    const store = withStore({
      [partialKeyFor(TERRAIN.packageKey)]: held,
      [progressKeyFor(TERRAIN.packageKey)]: { receivedBytes: 2, totalBytes: 6 },
      [sourceKeyFor(TERRAIN.packageKey)]: { url: TERRAIN.url },
    })
    mockFetch({ [SHEET.url]: SHEET_BYTES, [TERRAIN.url]: TERRAIN_BYTES })

    const { result } = renderHook(() => useArchiveDownloads(BOTH))

    // On mount the interrupted package says how far it got, and the other
    // says nothing is downloaded - two different answers, at once.
    await waitFor(() => {
      expect(result.current.statusFor(TERRAIN.packageKey)).toEqual({
        state: 'failed',
        receivedBytes: 2,
        totalBytes: 6,
      })
      expect(result.current.statusFor(SHEET.packageKey)).toEqual({
        state: 'not-downloaded',
      })
    })

    await act(async () => {
      await result.current.resume(TERRAIN.packageKey)
    })

    // The finished archive is the full six bytes: the four requested,
    // appended to the two that were already here.
    const finished = store[TERRAIN.packageKey] as Blob
    expect(finished.size).toBe(TERRAIN_BYTES.length)
    expect(new Uint8Array(await finished.arrayBuffer())).toEqual(TERRAIN_BYTES)
    expect(store[partialKeyFor(TERRAIN.packageKey)]).toBeUndefined()
  })

  it('reports a failure against the package that failed, and only that one', async () => {
    withStore()
    // Nothing is published at the terrain URL - the 404 a package offered
    // before its artifact exists would give.
    mockFetch({ [SHEET.url]: SHEET_BYTES })

    const { result } = renderHook(() => useArchiveDownloads(BOTH))

    await act(async () => {
      await Promise.all([
        result.current.start(SHEET.packageKey),
        result.current.start(TERRAIN.packageKey),
      ])
    })

    await waitFor(() => {
      expect(result.current.errorFor(TERRAIN.packageKey)).toMatch(/404/)
      expect(result.current.errorFor(SHEET.packageKey)).toBeNull()
      expect(result.current.statusFor(SHEET.packageKey).state).toBe('downloaded')
    })
  })

  it('starts every missing package from one tap', async () => {
    withStore()
    mockFetch({ [SHEET.url]: SHEET_BYTES, [TERRAIN.url]: TERRAIN_BYTES })

    const { result } = renderHook(() => useArchiveDownloads(BOTH))

    await act(async () => {
      await result.current.startAll([SHEET.packageKey, TERRAIN.packageKey])
    })

    await waitFor(() => {
      expect(result.current.statusFor(SHEET.packageKey).state).toBe('downloaded')
      expect(result.current.statusFor(TERRAIN.packageKey).state).toBe('downloaded')
    })
  })

  it('keeps one attempt per package without excluding a different package', async () => {
    withStore()
    mockFetch({ [SHEET.url]: SHEET_BYTES, [TERRAIN.url]: TERRAIN_BYTES })

    const { result } = renderHook(() => useArchiveDownloads(BOTH))

    // Two taps on the same card are one download - a second run() would
    // orphan the first, and the orphan writes its partial after a delete.
    // Two taps on DIFFERENT cards are two downloads, because a hiker who
    // asked for the whole manifest asked for all of it.
    let sameCard: [Promise<void>, Promise<void>]
    let otherCard: Promise<void>
    act(() => {
      sameCard = [
        result.current.start(SHEET.packageKey),
        result.current.start(SHEET.packageKey),
      ]
      otherCard = result.current.start(TERRAIN.packageKey)
    })

    expect(sameCard![0]).toBe(sameCard![1])
    expect(otherCard!).not.toBe(sameCard![0])

    await act(async () => {
      await Promise.all([...sameCard!, otherCard!])
    })
  })

  it('reads the store once per package, however often the caller re-renders', async () => {
    // The request array is rebuilt on every render by every caller. Keying
    // the mount effect on the array itself would set state, get a new array,
    // and run again - a render loop whose body is IndexedDB reads.
    withStore()
    mockFetch({})

    const { result, rerender } = renderHook(() => useArchiveDownloads([...BOTH]))

    await waitFor(() => {
      expect(result.current.statusFor(SHEET.packageKey).state).toBe('not-downloaded')
    })
    const afterMount = vi.mocked(get).mock.calls.length

    rerender()
    rerender()
    await new Promise((resolve) => setTimeout(resolve, 20))

    expect(vi.mocked(get).mock.calls.length).toBe(afterMount)
  })
})
