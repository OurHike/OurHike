import { describe, it, expect, vi, beforeEach, afterEach, type Mock } from 'vitest'
import { addProtocol } from 'maplibre-gl'
import { registerBasemapProtocol, resetBasemapForTests, setBasemapCells } from './basemap'
import { BASEMAP_SCHEME, OPENFREEMAP_TILEJSON } from './liveTopo'
import { ArchiveNotDownloadedError } from './pmtilesSource'
import { BASEMAP_PACKAGE } from '../lib/packages'
import {
  cellPackageKey,
  CONTEXT_PACKAGE_KEY,
  parseCellIndex,
  type CellIndex,
} from '../lib/coverageCells'

vi.mock('maplibre-gl', () => import('../test/mocks/maplibre-gl'))

// The archive read, mocked at the pmtiles seam: what is under test is the
// RESOLUTION - local first, network fallthrough, recovery after a download -
// not pmtiles' directory walking, which is upstream's to test. One shared
// getZxy across instances, because the module under test is allowed to
// discard and recreate its PMTiles (that recreation is itself asserted, via
// the constructor log). Each instance keeps its source, so a test about the
// cells (#557) can answer differently per archive by asking `this.source`.
const { getZxy, constructed } = vi.hoisted(() => ({
  getZxy: vi.fn(),
  constructed: [] as unknown[],
}))

vi.mock('pmtiles', () => ({
  PMTiles: class {
    getZxy = getZxy
    source: unknown
    constructor(source: unknown) {
      this.source = source
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

describe('reading from the cells a phone holds (#557)', () => {
  // Three real cells off the published index (UA release 2026-09-02). The
  // tile under test sits in the middle of n34w085 - Georgia, the southern
  // terminus's cell - at z12: x 1086, y 1629 spans 84.55-84.46° W and
  // 34.45-34.52° N, half a degree clear of every seam.
  const INDEX = parseCellIndex({
    cell_degrees: 1,
    seam_margin_km: 3,
    context_zoom: 9,
    context: 'at_basemap_context.pmtiles',
    cells: [
      {
        name: 'n34w085',
        key: 'at_basemap_cell_n34w085.pmtiles',
        bounds: [-85, 34, -84, 35],
      },
      {
        name: 'n35w085',
        key: 'at_basemap_cell_n35w085.pmtiles',
        bounds: [-85, 35, -84, 36],
      },
      {
        name: 'n34w084',
        key: 'at_basemap_cell_n34w084.pmtiles',
        bounds: [-84, 34, -83, 35],
      },
    ],
  }) as CellIndex
  const GEORGIA = cellPackageKey('n34w085')
  const IN_GEORGIA = `${BASEMAP_SCHEME}://12/1086/1629`

  /** The keys every reader constructed so far was pointed at. */
  const askedKeys = () =>
    constructed.map((source) => (source as { getKey(): string }).getKey())

  /** Answers per archive: the package is absent, and each held cell holds
   *  one recognisable tile. */
  function answersByArchive(tiles: Record<string, number[]>) {
    getZxy.mockImplementation(function (this: { source: { getKey(): string } }) {
      const key = this.source.getKey()
      if (key === BASEMAP_PACKAGE.idbKey)
        return Promise.reject(new ArchiveNotDownloadedError(key))
      const bytes = tiles[key]
      return Promise.resolve(
        bytes === undefined ? undefined : { data: new Uint8Array(bytes).buffer },
      )
    })
  }

  it('serves a tile from the held cell it sits in, without touching the network', async () => {
    setBasemapCells(INDEX, new Set([GEORGIA]))
    answersByArchive({ [GEORGIA]: [3, 4] })

    const result = await requestTile(IN_GEORGIA)

    expect(Array.from(result.data)).toEqual([3, 4])
    expect(fetchMock).not.toHaveBeenCalled()
    expect(askedKeys()).toEqual([BASEMAP_PACKAGE.idbKey, GEORGIA])
  })

  it('asks the whole package first, since it holds everything a cell does', async () => {
    setBasemapCells(INDEX, new Set([GEORGIA]))
    getZxy.mockResolvedValue({ data: new Uint8Array([9]).buffer })

    await requestTile(IN_GEORGIA)

    expect(askedKeys()).toEqual([BASEMAP_PACKAGE.idbKey])
  })

  it('never asks a cell the phone does not hold', async () => {
    // The shell's set is the whole of what is asked. A cell that is not in
    // it is not "tried and found absent" - it is not tried, so a hiker with
    // one stretch does not pay sixty-one failed reads per tile.
    setBasemapCells(INDEX, new Set([cellPackageKey('n35w085')]))
    answersByArchive({})
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ tiles: [TILE_TEMPLATE] }))
      .mockResolvedValueOnce(tileResponse([7]))

    const result = await requestTile(IN_GEORGIA)

    expect(Array.from(result.data)).toEqual([7])
    expect(askedKeys()).not.toContain(GEORGIA)
  })

  it('falls through to the context at and under the context zoom, and not above it', async () => {
    const CONTEXT_TILE = `${BASEMAP_SCHEME}://9/136/203`
    setBasemapCells(INDEX, new Set([CONTEXT_PACKAGE_KEY]))
    answersByArchive({ [CONTEXT_PACKAGE_KEY]: [5] })

    const shallow = await requestTile(CONTEXT_TILE)
    expect(Array.from(shallow.data)).toEqual([5])
    expect(fetchMock).not.toHaveBeenCalled()

    // z12 is a cell's to hold; the context is never asked for it.
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ tiles: [TILE_TEMPLATE] }))
      .mockResolvedValueOnce(tileResponse([8]))
    const deep = await requestTile(IN_GEORGIA)
    expect(Array.from(deep.data)).toEqual([8])
    expect(askedKeys().filter((key) => key === CONTEXT_PACKAGE_KEY)).toHaveLength(1)
  })

  it('serves from a cell the moment the shell says it landed', async () => {
    // A stretch finishing mid-session: nothing is rebuilt, the next tile
    // is simply answered from the new archive.
    setBasemapCells(INDEX, new Set())
    answersByArchive({ [GEORGIA]: [1] })
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ tiles: [TILE_TEMPLATE] }))
      .mockResolvedValueOnce(tileResponse([0]))
    await requestTile(IN_GEORGIA)

    setBasemapCells(INDEX, new Set([GEORGIA]))
    const result = await requestTile(IN_GEORGIA)

    expect(Array.from(result.data)).toEqual([1])
  })

  it('stops reading a cell the shell no longer lists', async () => {
    setBasemapCells(INDEX, new Set([GEORGIA]))
    answersByArchive({ [GEORGIA]: [1] })
    await requestTile(IN_GEORGIA)

    setBasemapCells(INDEX, new Set())
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ tiles: [TILE_TEMPLATE] }))
      .mockResolvedValueOnce(tileResponse([2]))
    const result = await requestTile(IN_GEORGIA)

    expect(Array.from(result.data)).toEqual([2])
  })

  it('does not memoise a cell read that failed', async () => {
    // pmtilesSource.ts's rule, once more: a rejected header promise cached
    // in a reader would keep a resumed cell dark for the session.
    setBasemapCells(INDEX, new Set([GEORGIA]))
    getZxy.mockImplementation(function (this: { source: { getKey(): string } }) {
      return Promise.reject(new ArchiveNotDownloadedError(this.source.getKey()))
    })
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ tiles: [TILE_TEMPLATE] }))
      .mockResolvedValue(tileResponse([0]))
    await requestTile(IN_GEORGIA)

    answersByArchive({ [GEORGIA]: [6] })
    const result = await requestTile(IN_GEORGIA)

    expect(Array.from(result.data)).toEqual([6])
    // A fresh reader for the cell after the failure, exactly as the package
    // gets one.
    expect(askedKeys().filter((key) => key === GEORGIA)).toHaveLength(2)
  })
})
