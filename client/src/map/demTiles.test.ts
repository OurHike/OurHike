import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { demGetTile, resetDemTilesForTests, setDemCells } from './demTiles'
import { cellPackageKey, DEM_CELLS, type CellIndex } from '../lib/coverageCells'
import { ArchiveNotDownloadedError } from './pmtilesSource'
import { DEM_PACKAGE } from '../lib/packages'
import { DEM_TILE_URL } from './terrain'

// The archive read, mocked at the pmtiles seam - the same reasoning as
// basemap.test.ts, whose local-first shape this module shares: under test is
// the resolution and its recovery behavior, not pmtiles' directory walking.
const { getZxy, constructed } = vi.hoisted(() => ({
  getZxy: vi.fn(),
  constructed: [] as unknown[],
}))

vi.mock('pmtiles', () => ({
  PMTiles: class {
    // The source is kept on the instance as well as in `constructed`, so a
    // test with more than one archive open can answer per archive: `getZxy`
    // is one shared mock, and `this.source` is the only thing that says which
    // reader asked. Tests that only ever open one keep working unchanged.
    source: unknown
    getZxy = getZxy
    constructor(source: unknown) {
      this.source = source
      constructed.push(source)
    }
  },
}))

const fetchMock = vi.fn()

function tileUrl(z: number, x: number, y: number): string {
  return DEM_TILE_URL.replace('{z}', String(z))
    .replace('{x}', String(x))
    .replace('{y}', String(y))
}

function pngResponse(bytes: number[], status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    blob: () => Promise.resolve(new Blob([new Uint8Array(bytes)])),
    headers: new Headers(),
  } as unknown as Response
}

/** A cell index in the published shape, small enough to reason about: two
 *  adjacent one-degree squares over the Hudson Highlands, and a context
 *  through z9 the way `dem_cells.json` publishes one. */
function demIndex(context: string | null = 'dem_context.pmtiles'): CellIndex {
  return {
    cellDegrees: 1,
    seamMarginKm: 3,
    contextZoom: 9,
    context,
    cells: [
      {
        name: 'n41w075',
        key: 'dem_cell_n41w075.pmtiles',
        bounds: [-75, 41, -74, 42],
        covered: [-75, 41, -74, 42],
      },
      {
        name: 'n41w074',
        key: 'dem_cell_n41w074.pmtiles',
        bounds: [-74, 41, -73, 42],
        covered: [-74, 41, -73, 42],
      },
    ],
  }
}

/** Which archive a read is against, for a `getZxy` shared by every reader. */
function askedKey(context: unknown): string {
  return (context as { source: { getKey(): string } }).source.getKey()
}

/** The canvas machinery the ancestor upscale needs, which jsdom does not
 *  have. Module scope since #1475, because the cell tests below need it too. */
function stubImageBitmap(): void {
  const bitmap = { width: 256, height: 256, close: vi.fn() }
  vi.stubGlobal('createImageBitmap', vi.fn().mockResolvedValue(bitmap))
  vi.stubGlobal(
    'OffscreenCanvas',
    class {
      width: number
      height: number
      constructor(width: number, height: number) {
        this.width = width
        this.height = height
      }
      getContext() {
        return { drawImage: vi.fn(), imageSmoothingEnabled: true }
      }
      convertToBlob() {
        return Promise.resolve(new Blob([new Uint8Array([9, 9])]))
      }
    },
  )
}

beforeEach(() => {
  resetDemTilesForTests()
  getZxy.mockReset()
  constructed.length = 0
  fetchMock.mockReset()
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('demGetTile (#187)', () => {
  it('serves a tile the downloaded DEM package holds without touching the network', async () => {
    getZxy.mockResolvedValue({ data: new Uint8Array([1, 2, 3]).buffer })

    const result = await demGetTile(tileUrl(12, 1198, 1540), new AbortController())

    expect(new Uint8Array(await result.data.arrayBuffer())).toEqual(
      new Uint8Array([1, 2, 3]),
    )
    expect(fetchMock).not.toHaveBeenCalled()
    expect(getZxy).toHaveBeenCalledWith(12, 1198, 1540, expect.anything())
    // Reading the package the catalog names.
    expect((constructed[0] as { getKey(): string }).getKey()).toBe(DEM_PACKAGE.idbKey)
  })

  it('falls through to AWS for a tile beyond the package footprint', async () => {
    getZxy.mockResolvedValue(undefined)
    fetchMock.mockResolvedValue(pngResponse([9, 9]))

    const result = await demGetTile(tileUrl(11, 500, 600), new AbortController())

    expect(new Uint8Array(await result.data.arrayBuffer())).toEqual(
      new Uint8Array([9, 9]),
    )
    expect(fetchMock).toHaveBeenCalledWith(
      tileUrl(11, 500, 600),
      expect.objectContaining({ signal: expect.anything() }),
    )
  })

  it('resolves over the network while the package is not downloaded yet', async () => {
    getZxy.mockRejectedValue(new ArchiveNotDownloadedError(DEM_PACKAGE.idbKey))
    fetchMock.mockResolvedValue(pngResponse([5]))

    const result = await demGetTile(tileUrl(10, 1, 2), new AbortController())

    expect(new Uint8Array(await result.data.arrayBuffer())).toEqual(new Uint8Array([5]))
  })

  it('serves locally on the first tile after a download completes', async () => {
    // pmtiles caches a rejected header promise forever, so the instance must
    // be discarded on failure - the same recovery basemap.test.ts pins.
    getZxy.mockRejectedValueOnce(new ArchiveNotDownloadedError(DEM_PACKAGE.idbKey))
    fetchMock.mockResolvedValue(pngResponse([1]))
    await demGetTile(tileUrl(13, 1, 1), new AbortController())

    getZxy.mockResolvedValue({ data: new Uint8Array([42]).buffer })
    const result = await demGetTile(tileUrl(13, 1, 2), new AbortController())

    expect(new Uint8Array(await result.data.arrayBuffer())).toEqual(new Uint8Array([42]))
    expect(constructed).toHaveLength(2)
  })

  it('fails a bad network status rather than inventing an empty tile', async () => {
    // AWS Terrain Tiles is globally complete - a missing DEM tile is a
    // failure to report (a missing hillshade tile), never flat ground.
    getZxy.mockResolvedValue(undefined)
    fetchMock.mockResolvedValue(pngResponse([], 503))

    await expect(demGetTile(tileUrl(9, 3, 4), new AbortController())).rejects.toThrow(
      /HTTP 503/,
    )
  })

  it('lets an abort propagate as an abort, keeping the archive handle', async () => {
    const abort = new DOMException('Aborted', 'AbortError')
    getZxy.mockRejectedValue(abort)

    await expect(demGetTile(tileUrl(12, 0, 0), new AbortController())).rejects.toBe(abort)
    expect(fetchMock).not.toHaveBeenCalled()

    getZxy.mockResolvedValue({ data: new Uint8Array([1]).buffer })
    await demGetTile(tileUrl(12, 0, 1), new AbortController())
    expect(constructed).toHaveLength(1)
  })

  it('rejects a URL that is not the DEM template', async () => {
    await expect(
      demGetTile('https://example.com/not-a-dem/1/2/3.png', new AbortController()),
    ).rejects.toThrow(/DEM tile URL/)
  })

  // The tapered corridor (#1088): the archive carries z13 only near the trail,
  // so a deep-zoom miss out on the flank is now an ORDINARY state rather than
  // a sign something is wrong - and it must not become a network call that a
  // hiker with no signal pays for in a blank hillshade.
  describe('falling back to a coarser tile the hiker already has', () => {
    it('reads the ancestor out of the archive when the network cannot answer', async () => {
      stubImageBitmap()
      // z13 absent (past the taper's narrow band), z12 present.
      getZxy.mockImplementation((z: number) =>
        Promise.resolve(
          z === 12 ? { data: new Uint8Array([1, 2, 3]).buffer } : undefined,
        ),
      )
      fetchMock.mockRejectedValue(new TypeError('Failed to fetch'))

      const tile = await demGetTile(tileUrl(13, 2410, 3080), new AbortController())

      expect(await tile.data.size).toBeGreaterThan(0)
      expect(getZxy).toHaveBeenCalledWith(12, 1205, 1540, expect.anything())
    })

    it('still prefers the network when it can answer, so a hiker with signal gets the sharp tile', async () => {
      stubImageBitmap()
      getZxy.mockImplementation((z: number) =>
        Promise.resolve(
          z === 12 ? { data: new Uint8Array([1, 2, 3]).buffer } : undefined,
        ),
      )
      fetchMock.mockResolvedValue(pngResponse([7, 7, 7]))

      await demGetTile(tileUrl(13, 2410, 3080), new AbortController())

      expect(fetchMock).toHaveBeenCalled()
      expect(getZxy).toHaveBeenCalledTimes(1)
      expect(getZxy).not.toHaveBeenCalledWith(12, 1205, 1540, expect.anything())
    })

    it('rethrows the original failure when the archive holds no usable ancestor', async () => {
      stubImageBitmap()
      getZxy.mockResolvedValue(undefined)
      fetchMock.mockResolvedValue(pngResponse([], 503))

      await expect(
        demGetTile(tileUrl(13, 2410, 3080), new AbortController()),
      ).rejects.toThrow(/HTTP 503/)
    })

    it('degrades to the old throw where the runtime has no image decoder', async () => {
      // The guard, not a nicety: a runtime without createImageBitmap cannot
      // crop an ancestor, and inventing one would be worse than the hole.
      vi.stubGlobal('createImageBitmap', undefined)
      getZxy.mockImplementation((z: number) =>
        Promise.resolve(
          z === 12 ? { data: new Uint8Array([1, 2, 3]).buffer } : undefined,
        ),
      )
      fetchMock.mockRejectedValue(new TypeError('Failed to fetch'))

      await expect(
        demGetTile(tileUrl(13, 2410, 3080), new AbortController()),
      ).rejects.toThrow(/Failed to fetch/)
    })

    it('lets an abort during the fallback stay an abort', async () => {
      stubImageBitmap()
      getZxy.mockResolvedValue(undefined)
      fetchMock.mockRejectedValue(new DOMException('Aborted', 'AbortError'))

      await expect(
        demGetTile(tileUrl(13, 2410, 3080), new AbortController()),
      ).rejects.toMatchObject({ name: 'AbortError' })
    })
  })
})

describe('the stretch\u2019s own terrain (#1475)', () => {
  const CELL_KEY = cellPackageKey('n41w075', DEM_CELLS)

  it('serves a tile from a held cell without opening the whole package or the network', async () => {
    setDemCells(demIndex(), new Set([CELL_KEY]))
    getZxy.mockImplementation(function (this: unknown) {
      return Promise.resolve(
        askedKey(this) === CELL_KEY ? { data: new Uint8Array([4, 5]).buffer } : undefined,
      )
    })

    const result = await demGetTile(tileUrl(12, 1200, 1528), new AbortController())

    expect(new Uint8Array(await result.data.arrayBuffer())).toEqual(
      new Uint8Array([4, 5]),
    )
    expect(fetchMock).not.toHaveBeenCalled()
    // The cell answered first, so the whole package was never even opened -
    // which is the point on a phone that took a stretch and holds no package.
    expect(
      constructed.map((source) => (source as { getKey(): string }).getKey()),
    ).toEqual([CELL_KEY])
  })

  it('never asks a cell this phone does not hold', async () => {
    // The index lists both squares; only the western one is downloaded.
    setDemCells(demIndex(), new Set([CELL_KEY]))
    getZxy.mockResolvedValue(undefined)
    fetchMock.mockResolvedValue(pngResponse([7]))

    // A tile in the EASTERN square, which the index names and the phone lacks.
    await demGetTile(tileUrl(12, 1210, 1528), new AbortController())

    const opened = constructed.map((source) => (source as { getKey(): string }).getKey())
    expect(opened).not.toContain(cellPackageKey('n41w074', DEM_CELLS))
    expect(opened).toContain(DEM_PACKAGE.idbKey)
  })

  it('answers a panned-out tile from the shared context archive', async () => {
    setDemCells(demIndex(), new Set([DEM_CELLS.contextPackageKey]))
    getZxy.mockImplementation(function (this: unknown) {
      return Promise.resolve(
        askedKey(this) === DEM_CELLS.contextPackageKey
          ? { data: new Uint8Array([8]).buffer }
          : undefined,
      )
    })

    // z9 is the index\u2019s contextZoom: the pyramid published once per sheet
    // is what a hiker sees when they zoom out past the piece they hold.
    const result = await demGetTile(tileUrl(9, 150, 191), new AbortController())

    expect(new Uint8Array(await result.data.arrayBuffer())).toEqual(new Uint8Array([8]))
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('leaves the context alone below its own zoom', async () => {
    setDemCells(demIndex(), new Set([DEM_CELLS.contextPackageKey]))
    getZxy.mockResolvedValue(undefined)
    fetchMock.mockResolvedValue(pngResponse([7]))

    await demGetTile(tileUrl(12, 1200, 1528), new AbortController())

    // A z12 tile is deeper than contextZoom 9, so the context cannot hold it
    // and reading it would be a wasted IndexedDB round trip per tile.
    expect(
      constructed.map((source) => (source as { getKey(): string }).getKey()),
    ).not.toContain(DEM_CELLS.contextPackageKey)
  })

  it('finds the coarser ancestor in a held cell when the network is gone', async () => {
    stubImageBitmap()
    setDemCells(demIndex(null), new Set([CELL_KEY]))
    // The cell carries z12 and not z13 - the taper\u2019s narrow band, in a cell
    // rather than in the whole package.
    getZxy.mockImplementation(function (this: unknown, z: number) {
      return Promise.resolve(
        askedKey(this) === CELL_KEY && z === 12
          ? { data: new Uint8Array([1]).buffer }
          : undefined,
      )
    })
    fetchMock.mockRejectedValue(new TypeError('Failed to fetch'))

    const result = await demGetTile(tileUrl(13, 2400, 3056), new AbortController())

    // Without this the offline miss is a blank square, which is what
    // export_dem.py\u2019s publish gate calls "found at the worst possible moment".
    expect(new Uint8Array(await result.data.arrayBuffer())).toEqual(
      new Uint8Array([9, 9]),
    )
  })

  it('stops reading a cell the hiker has removed', async () => {
    setDemCells(demIndex(), new Set([CELL_KEY]))
    getZxy.mockImplementation(function (this: unknown) {
      return Promise.resolve(
        askedKey(this) === CELL_KEY ? { data: new Uint8Array([4]).buffer } : undefined,
      )
    })
    await demGetTile(tileUrl(12, 1200, 1528), new AbortController())
    expect(constructed).toHaveLength(1)

    // Dropped from the held set: the reader goes too, so nothing answers from
    // bytes that are no longer there or from a directory cached before them.
    setDemCells(demIndex(), new Set())
    fetchMock.mockResolvedValue(pngResponse([7]))
    await demGetTile(tileUrl(12, 1200, 1528), new AbortController())

    expect(
      constructed.map((source) => (source as { getKey(): string }).getKey()),
    ).toEqual([CELL_KEY, DEM_PACKAGE.idbKey])
  })

  it('reads the whole package exactly as before when no cells are declared', async () => {
    getZxy.mockResolvedValue({ data: new Uint8Array([1, 2, 3]).buffer })

    const result = await demGetTile(tileUrl(12, 1200, 1528), new AbortController())

    expect(new Uint8Array(await result.data.arrayBuffer())).toEqual(
      new Uint8Array([1, 2, 3]),
    )
    expect(
      constructed.map((source) => (source as { getKey(): string }).getKey()),
    ).toEqual([DEM_PACKAGE.idbKey])
  })
})
