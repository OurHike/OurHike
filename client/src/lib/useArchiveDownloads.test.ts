import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { del, get, getMany, keys, set } from 'idb-keyval'
import { useArchiveDownloads } from './useArchiveDownload'
import { progressKeyFor, sourceKeyFor } from './archiveDownload'
import { readArchive, segmentKeyFor } from './archiveStore'

// #192's acceptance, as tests: two packages downloaded, one deleted, one
// resumed after an interrupted download - every state correct and reported
// against the package it belongs to.
//
// The single-package view of this hook has its own files
// (useArchiveDownload.test.ts and .status.test.ts); what is worth testing
// here is only what plurality adds - that one package's progress, failure,
// deletion and resume are its own, and that holding several does not make
// them interfere.

vi.mock('idb-keyval', () => ({
  get: vi.fn(),
  getMany: vi.fn(),
  keys: vi.fn(),
  set: vi.fn(),
  del: vi.fn(),
  update: vi.fn(),
}))

const SHEET = {
  packageKey: 'ourhike:sheet',
  url: 'https://cdn.example.org/sheet.pmtiles',
  artifactKey: 'sheet.pmtiles',
}
const TERRAIN = {
  packageKey: 'ourhike:dem',
  url: 'https://cdn.example.org/dem.pmtiles',
  artifactKey: 'dem.pmtiles',
}
const BOTH = [SHEET, TERRAIN]

function withStore(initial: Record<string, unknown> = {}) {
  const store: Record<string, unknown> = { ...initial }
  vi.mocked(get).mockImplementation(async (key) => store[key as string])
  // `getMany` follows whatever `get` is doing right now, so #1303's one
  // transaction in lib/trailData.ts reads this file's store like every other
  // read, and a test that re-points `get` need not re-point both.
  vi.mocked(getMany).mockImplementation((keys) =>
    Promise.all(keys.map((key) => vi.mocked(get)(key))),
  )
  // The store's own key list, as the launch sweep reads it first (#1726).
  vi.mocked(keys).mockImplementation(async () => Object.keys(store))
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
  it('reads the key list once and nothing else for packages the phone holds no record of (#1726)', async () => {
    withStore()
    let renders = 0

    const { result } = renderHook(() => {
      renders += 1
      return useArchiveDownloads(BOTH)
    })
    await waitFor(() => expect(result.current.statusesKnown).toBe(true))

    // One `keys()` for the whole set, and no `getMany` at all: neither
    // package has a marker, a legacy record or a partial under its key, so
    // there is nothing to read - the same answer 800 registered cells get.
    expect(vi.mocked(keys)).toHaveBeenCalledTimes(1)
    expect(vi.mocked(getMany)).not.toHaveBeenCalled()
    // The mount render, the persistence answer, and the one sweep update -
    // never one render per package.
    expect(renders).toBeLessThanOrEqual(3)
    expect(result.current.statusFor(SHEET.packageKey)).toEqual({
      state: 'not-downloaded',
    })
    expect(result.current.statusFor(TERRAIN.packageKey)).toEqual({
      state: 'not-downloaded',
    })
  })

  it('reads only the packages the key list names: a marker, a legacy blob, or a partial (#1726)', async () => {
    withStore({
      [`${SHEET.packageKey}:complete`]: { generation: 0, segments: 1, totalBytes: 8 },
      [progressKeyFor(TERRAIN.packageKey)]: { receivedBytes: 3, totalBytes: 6 },
    })

    const { result } = renderHook(() => useArchiveDownloads(BOTH))
    await waitFor(() => expect(result.current.statusesKnown).toBe(true))

    expect(result.current.statusFor(SHEET.packageKey)).toMatchObject({
      state: 'downloaded',
      totalBytes: 8,
    })
    expect(result.current.statusFor(TERRAIN.packageKey)).toEqual({
      state: 'failed',
      receivedBytes: 3,
      totalBytes: 6,
    })
    // The sheet's marker in one transaction, the terrain's partial in
    // another - and the terrain was never asked for a marker it has no key for.
    const asked = vi.mocked(getMany).mock.calls.map((call) => call[0])
    expect(asked).toEqual([
      [`${SHEET.packageKey}:complete`],
      [progressKeyFor(TERRAIN.packageKey)],
    ])
  })

  it('reads every package the slow way when the store cannot list its keys', async () => {
    withStore({
      [`${SHEET.packageKey}:complete`]: { generation: 0, segments: 1, totalBytes: 8 },
    })
    vi.mocked(keys).mockRejectedValue(new Error('IndexedDB is gone'))

    const { result } = renderHook(() => useArchiveDownloads(BOTH))
    await waitFor(() => expect(result.current.statusesKnown).toBe(true))

    expect(result.current.statusFor(SHEET.packageKey)).toMatchObject({
      state: 'downloaded',
    })
    expect(result.current.statusFor(TERRAIN.packageKey)).toEqual({
      state: 'not-downloaded',
    })
    // Markers for both, legacy for the unmarked, partials for the rest.
    expect(vi.mocked(getMany)).toHaveBeenCalledTimes(3)
  })

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
    withStore()
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

    expect(await readArchive(SHEET.packageKey)).toBeUndefined()
    expect(await readArchive(TERRAIN.packageKey)).toBeInstanceOf(Blob)
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
    // Held as a segment record, which is where an interrupted transfer leaves
    // its bytes since #553 - the checkpoints it wrote as they arrived.
    const store = withStore({
      [segmentKeyFor(TERRAIN.packageKey, 0, 0)]: held,
      [progressKeyFor(TERRAIN.packageKey)]: { receivedBytes: 2, totalBytes: 6 },
      [sourceKeyFor(TERRAIN.packageKey)]: {
        url: TERRAIN.url,
        generation: 0,
        segments: 1,
      },
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

    // The finished archive is the full six bytes: the four requested, appended
    // to the two that were already here. Read through the accessor the map uses,
    // because the archive is a run of segments named by a marker rather than one
    // record.
    const finished = await readArchive(TERRAIN.packageKey)
    expect(finished?.size).toBe(TERRAIN_BYTES.length)
    expect(new Uint8Array(await (finished as Blob).arrayBuffer())).toEqual(TERRAIN_BYTES)
    // Nothing is left describing an in-flight transfer.
    expect(store[progressKeyFor(TERRAIN.packageKey)]).toBeUndefined()
    expect(store[sourceKeyFor(TERRAIN.packageKey)]).toBeUndefined()
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
    // A re-keyed mount effect issues its reads in the effect flush the
    // rerender itself performs; draining the microtask queue lets any async
    // read chain surface too. Deterministic under load, where the 20 ms
    // real-clock sleep this replaces was not (#323).
    await act(async () => {})

    expect(vi.mocked(get).mock.calls.length).toBe(afterMount)
  })
})

describe('when the package set grows after mount (#1301)', () => {
  it('reads the packages it already knows once, and only the new one again', async () => {
    // App.tsx registers every coverage cell the moment a cell index arrives,
    // so the set grows from the offered sheets to several dozen packages,
    // twice, on a launch with signal. Re-reading the sheets each time was
    // three IndexedDB round trips per known package on the thread the first
    // frame was waiting for.
    // Both packages hold a marker, so each is a record the sweep reads when
    // it is new - and the sheet's must be read once, on mount, never again.
    withStore({
      [`${SHEET.packageKey}:complete`]: { generation: 0, segments: 1, totalBytes: 8 },
      [`${TERRAIN.packageKey}:complete`]: { generation: 0, segments: 1, totalBytes: 6 },
    })
    mockFetch({})
    const recordsRead = () => vi.mocked(getMany).mock.calls.flatMap((call) => call[0])

    const { result, rerender } = renderHook(
      ({ requests }: { requests: typeof BOTH }) => useArchiveDownloads(requests),
      { initialProps: { requests: [SHEET] } },
    )
    await waitFor(() => expect(result.current.statusesKnown).toBe(true))
    expect(recordsRead()).toEqual([`${SHEET.packageKey}:complete`])

    rerender({ requests: BOTH })
    await waitFor(() => expect(result.current.statusesKnown).toBe(true))

    // The terrain's marker joins the list; the sheet's is not read a second
    // time. The key list itself is re-read per run, which is one request.
    expect(recordsRead()).toEqual([
      `${SHEET.packageKey}:complete`,
      `${TERRAIN.packageKey}:complete`,
    ])
    expect(vi.mocked(keys)).toHaveBeenCalledTimes(2)
    expect(result.current.statusFor(TERRAIN.packageKey)).toMatchObject({
      state: 'downloaded',
    })
  })
})

describe('a store that refuses a read (#1301)', () => {
  it('asks again on a later run rather than caching the refusal for the session', async () => {
    // A database that refused this read is not the same as one that answered.
    // Marking it answered would make a transient refusal permanent: a
    // downloaded archive reading as absent, and the map rebuilt around the
    // live sheet, until the app is relaunched.
    withStore()
    mockFetch({})
    // A store that refuses a read refuses its key list too, so the sweep is
    // back to asking about each package - and those reads refuse as well.
    vi.mocked(keys).mockRejectedValue(new Error('no IndexedDB here'))
    vi.mocked(get).mockRejectedValue(new Error('no IndexedDB here'))

    const { result, rerender } = renderHook(
      ({ requests }: { requests: typeof BOTH }) => useArchiveDownloads(requests),
      { initialProps: { requests: [SHEET] } },
    )
    await waitFor(() => expect(result.current.statusesKnown).toBe(true))
    const refusedReads = vi
      .mocked(get)
      .mock.calls.filter(([key]) => String(key).includes(SHEET.packageKey)).length
    expect(refusedReads).toBeGreaterThan(0)

    // The set grows, which re-runs the mount effect. A package that never
    // answered is asked again.
    rerender({ requests: BOTH })
    await waitFor(() =>
      expect(
        vi
          .mocked(get)
          .mock.calls.filter(([key]) => String(key).includes(SHEET.packageKey)).length,
      ).toBeGreaterThan(refusedReads),
    )
  })
})

describe('whether the phone has been read yet', () => {
  it('says no until every package has answered, then yes', async () => {
    // `statusFor` answers 'not-downloaded' for a package it has not read yet,
    // which is the same answer it gives for one that genuinely is not there.
    // A caller deciding anything on that answer decides it twice - once
    // wrongly, then again when the read lands - which cost the app a whole
    // extra map build on every launch. This flag is the difference.
    const held: Array<() => void> = []
    // The key list first - the sheet holds a legacy whole-archive record
    // under its bare key - and then the record itself, each held until
    // released, so the gate can be watched between the two.
    vi.mocked(keys).mockImplementation(
      () =>
        new Promise((resolve) => {
          held.push(() => resolve([SHEET.packageKey]))
        }),
    )
    vi.mocked(get).mockImplementation(
      (key) =>
        new Promise((resolve) => {
          held.push(() => resolve(key === SHEET.packageKey ? new Blob(['x']) : undefined))
        }),
    )
    vi.mocked(getMany).mockImplementation((asked) =>
      Promise.all(asked.map((key) => vi.mocked(get)(key))),
    )

    const { result } = renderHook(() => useArchiveDownloads(BOTH))

    // The key list is out. Nothing has come back, and the hook says so rather
    // than answering for the store.
    await waitFor(() => expect(held.length).toBe(1))
    expect(result.current.statusesKnown).toBe(false)

    // Released in rounds, because answering a read is how the next one gets
    // asked: the key list names the sheet's record, which is then read.
    for (let round = 0; round < 4 && held.length > 0; round += 1) {
      const releases = held.splice(0, held.length)
      await act(async () => {
        for (const release of releases) release()
        await new Promise((resolve) => setTimeout(resolve, 0))
      })
    }

    await waitFor(() => expect(result.current.statusesKnown).toBe(true))
    expect(result.current.statusFor(SHEET.packageKey).state).toBe('downloaded')
  })

  it('is read from the start when there is nothing to ask about', async () => {
    // A build with no published archives has no store to consult, so there is
    // nothing to wait for - and a gate that waited anyway would never open.
    withStore()

    const { result } = renderHook(() => useArchiveDownloads([]))

    expect(result.current.statusesKnown).toBe(true)
  })
})
