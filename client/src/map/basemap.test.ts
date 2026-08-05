import { describe, it, expect, vi, beforeEach, afterEach, type Mock } from 'vitest'
import { addProtocol } from 'maplibre-gl'
import { registerBasemapProtocol, resetBasemapForTests } from './basemap'
import { BASEMAP_SCHEME, OPENFREEMAP_TILEJSON } from './liveTopo'
import { ArchiveNotDownloadedError } from './pmtilesSource'
import { BASEMAP_PACKAGE } from '../lib/packages'

vi.mock('maplibre-gl', () => import('../test/mocks/maplibre-gl'))

// The archive read, mocked at the pmtiles seam: what is under test is the
// RESOLUTION - local first, network fallthrough, recovery after a download -
// not pmtiles' directory walking, which is upstream's to test. One shared
// getZxy across instances, because the module under test is allowed to
// discard and recreate its PMTiles (that recreation is itself asserted, via
// the constructor log).
const { getZxy, constructed } = vi.hoisted(() => ({
  getZxy: vi.fn(),
  constructed: [] as unknown[],
}))

vi.mock('pmtiles', () => ({
  PMTiles: class {
    getZxy = getZxy
    constructor(source: unknown) {
      constructed.push(source)
    }
  },
}))

const TILE_TEMPLATE = 'https://tiles.openfreemap.org/planet/20260801/{z}/{x}/{y}.pbf'

function jsonResponse(body: unknown): Response {
  return {
    ok: true,
    status: 200,
    json: () => Promise.resolve(body),
  } as unknown as Response
}

function tileResponse(bytes: number[], status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    arrayBuffer: () => Promise.resolve(new Uint8Array(bytes).buffer),
    headers: new Headers(),
  } as unknown as Response
}

const fetchMock = vi.fn()

/** Registers (idempotently) and returns the handler MapLibre would hold. */
function tileHandler() {
  registerBasemapProtocol()
  const call = (addProtocol as unknown as Mock).mock.calls.find(
    ([scheme]) => scheme === BASEMAP_SCHEME,
  )
  expect(call).toBeDefined()
  return call![1] as (
    params: { url: string },
    abort: AbortController,
  ) => Promise<{ data: Uint8Array }>
}

function requestTile(url = `${BASEMAP_SCHEME}://12/1198/1540`) {
  return tileHandler()({ url }, new AbortController())
}

beforeEach(() => {
  resetBasemapForTests()
  ;(addProtocol as unknown as Mock).mockClear()
  getZxy.mockReset()
  constructed.length = 0
  fetchMock.mockReset()
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('registerBasemapProtocol', () => {
  it('registers the scheme once, however many components ask', () => {
    registerBasemapProtocol()
    registerBasemapProtocol()
    registerBasemapProtocol()

    const calls = (addProtocol as unknown as Mock).mock.calls.filter(
      ([scheme]) => scheme === BASEMAP_SCHEME,
    )
    expect(calls).toHaveLength(1)
  })
})

describe('local-first tile resolution (#189)', () => {
  it('serves a tile the downloaded package holds without touching the network', () => {
    getZxy.mockResolvedValue({ data: new Uint8Array([1, 2, 3]).buffer })

    return requestTile().then((result) => {
      expect(Array.from(result.data)).toEqual([1, 2, 3])
      expect(fetchMock).not.toHaveBeenCalled()
      // Reading the package the catalog names, not a second key someone
      // else would have to keep in sync.
      expect(constructed).toHaveLength(1)
      expect((constructed[0] as { getKey(): string }).getKey()).toBe(
        BASEMAP_PACKAGE.idbKey,
      )
    })
  })

  it('parses the z/x/y it was asked for, not a hardcoded coordinate', async () => {
    getZxy.mockResolvedValue({ data: new Uint8Array([9]).buffer })

    await requestTile(`${BASEMAP_SCHEME}://14/4823/6160`)

    expect(getZxy).toHaveBeenCalledWith(14, 4823, 6160, expect.anything())
  })

  it('falls through to the live source for a tile beyond the package footprint', async () => {
    // undefined is pmtiles' answer for "this archive never held that tile" -
    // the per-tile miss that makes beyond-the-package ground live rather
    // than blank when there is signal.
    getZxy.mockResolvedValue(undefined)
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ tiles: [TILE_TEMPLATE] }))
      .mockResolvedValueOnce(tileResponse([7, 8]))

    const result = await requestTile(`${BASEMAP_SCHEME}://12/1198/1540`)

    expect(Array.from(result.data)).toEqual([7, 8])
    expect(fetchMock).toHaveBeenNthCalledWith(1, OPENFREEMAP_TILEJSON)
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      'https://tiles.openfreemap.org/planet/20260801/12/1198/1540.pbf',
      expect.objectContaining({ signal: expect.anything() }),
    )
  })

  it('learns the network template once, not once per tile', async () => {
    getZxy.mockResolvedValue(undefined)
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ tiles: [TILE_TEMPLATE] }))
      .mockResolvedValue(tileResponse([0]))

    await requestTile(`${BASEMAP_SCHEME}://12/1/2`)
    await requestTile(`${BASEMAP_SCHEME}://12/1/3`)

    const tilejsonFetches = fetchMock.mock.calls.filter(
      ([url]) => url === OPENFREEMAP_TILEJSON,
    )
    expect(tilejsonFetches).toHaveLength(1)
  })

  it('resolves over the network while the package is not downloaded yet', async () => {
    getZxy.mockRejectedValue(new ArchiveNotDownloadedError(BASEMAP_PACKAGE.idbKey))
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ tiles: [TILE_TEMPLATE] }))
      .mockResolvedValueOnce(tileResponse([5]))

    const result = await requestTile()

    expect(Array.from(result.data)).toEqual([5])
  })

  it('serves locally on the first tile after a download completes', async () => {
    // The recovery pmtilesSource.ts's "never memoise a failure" rule exists
    // for, asserted one layer up because pmtiles itself caches a rejected
    // header promise forever: without discarding the instance, a download
    // that finishes mid-session would never be read from.
    getZxy.mockRejectedValueOnce(new ArchiveNotDownloadedError(BASEMAP_PACKAGE.idbKey))
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ tiles: [TILE_TEMPLATE] }))
      .mockResolvedValueOnce(tileResponse([1]))
    await requestTile()

    getZxy.mockResolvedValue({ data: new Uint8Array([42]).buffer })
    const result = await requestTile()

    expect(Array.from(result.data)).toEqual([42])
    // A fresh PMTiles per failed attempt is the mechanism: the second read
    // must not go through the instance that cached the failure.
    expect(constructed).toHaveLength(2)
  })

  it('does not memoise a network template failure either', async () => {
    getZxy.mockResolvedValue(undefined)
    fetchMock.mockRejectedValueOnce(new TypeError('Failed to fetch'))
    await expect(requestTile()).rejects.toThrow()

    fetchMock
      .mockResolvedValueOnce(jsonResponse({ tiles: [TILE_TEMPLATE] }))
      .mockResolvedValueOnce(tileResponse([6]))
    const result = await requestTile()

    expect(Array.from(result.data)).toEqual([6])
  })

  it('treats a 404 from the live source as an empty tile, not an error', async () => {
    // Sparse tilesets answer "no such tile" for open ocean; erroring there
    // would light liveSourceHealth's warning over a map that is fine.
    getZxy.mockResolvedValue(undefined)
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ tiles: [TILE_TEMPLATE] }))
      .mockResolvedValueOnce(tileResponse([], 404))

    const result = await requestTile()

    expect(result.data).toHaveLength(0)
  })

  it('lets an abort propagate as an abort, not as an archive miss', async () => {
    const abort = new DOMException('Aborted', 'AbortError')
    getZxy.mockRejectedValue(abort)

    await expect(requestTile()).rejects.toBe(abort)
    expect(fetchMock).not.toHaveBeenCalled()

    // An abort says nothing about the archive, so the instance survives it -
    // discarding it would re-read the header on every cancelled pan.
    getZxy.mockResolvedValue({ data: new Uint8Array([1]).buffer })
    await requestTile()
    expect(constructed).toHaveLength(1)
  })

  it('rejects a URL that is not a basemap tile', async () => {
    await expect(requestTile(`${BASEMAP_SCHEME}://not/a/tile/url`)).rejects.toThrow(
      /tile URL/,
    )
  })
})
