import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { demGetTile, resetDemTilesForTests } from './demTiles'
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
    getZxy = getZxy
    constructor(source: unknown) {
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
})
