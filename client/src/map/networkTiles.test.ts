// The other organizations' lines as tiles (#1257): what answers a network://
// request, in what order, and what is never kept.
//
// Mocked at the pmtiles seam, exactly as basemap.test.ts is: under test is the
// RESOLUTION - the manifest before the bucket, the archive by range, empty for
// a miss, a dropped handle on failure - not pmtiles' directory walking, which
// is upstream's to test.

import { describe, it, expect, vi, beforeEach, afterEach, type Mock } from 'vitest'
import { addProtocol } from 'maplibre-gl'

vi.mock('maplibre-gl', () => import('../test/mocks/maplibre-gl'))

const config = vi.hoisted(() => ({ configured: true }))
vi.mock('../lib/config', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../lib/config')>()),
  DATA_BASE_URL: 'https://data.example',
  get DATA_CONFIGURED() {
    return config.configured
  },
  dataUrl: (key: string) => `https://data.example/${key}`,
}))

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

const publishedSnapshot = vi.hoisted(() => vi.fn())
vi.mock('../lib/dataManifest', () => ({ publishedSnapshot }))

const {
  loadNetworkTile,
  NETWORK_SCHEME,
  NETWORK_TILES_LAYER,
  NETWORK_TILES_URL,
  registerNetworkProtocol,
  resetNetworkTilesForTests,
  setNetworkCells,
} = await import('./networkTiles')
const { NEARBY_TRAILS_TILES_KEY } = await import('../lib/config')
const { cellPackageKey, NETWORK_CELLS, parseCellIndex } =
  await import('../lib/coverageCells')

const ARCHIVE_URL = `https://data.example/${NEARBY_TRAILS_TILES_KEY}`
const A_TILE = `${NETWORK_SCHEME}://12/1198/1540`

/** latest.json naming the archive, or a manifest naming other things only. */
function manifestNaming(...keys: string[]) {
  publishedSnapshot.mockResolvedValue({
    hashes: Object.fromEntries(keys.map((key) => [key, `hash-of-${key}`])),
  })
}

function request(url = A_TILE, signal = new AbortController().signal) {
  return loadNetworkTile(url, signal)
}

beforeEach(() => {
  resetNetworkTilesForTests()
  ;(addProtocol as unknown as Mock).mockClear()
  getZxy.mockReset()
  publishedSnapshot.mockReset()
  constructed.length = 0
  config.configured = true
  manifestNaming(NEARBY_TRAILS_TILES_KEY, 'trails.geojson')
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('registration', () => {
  it('registers the network scheme once, however many maps are built', () => {
    registerNetworkProtocol()
    registerNetworkProtocol()

    const calls = (addProtocol as unknown as Mock).mock.calls.filter(
      ([scheme]) => scheme === NETWORK_SCHEME,
    )
    expect(calls).toHaveLength(1)
  })

  it('hands MapLibre a handler that answers through loadNetworkTile', async () => {
    getZxy.mockResolvedValue({ data: new Uint8Array([7, 7]).buffer })
    registerNetworkProtocol()
    const [, handler] = (addProtocol as unknown as Mock).mock.calls.find(
      ([scheme]) => scheme === NETWORK_SCHEME,
    )!

    const tile = await (
      handler as (p: { url: string }, a: AbortController) => Promise<{ data: Uint8Array }>
    )({ url: A_TILE }, new AbortController())

    expect([...tile.data]).toEqual([7, 7])
  })

  it('declares the template and the inner layer the style builds its source from', () => {
    // The two strings map/style.ts reads: a template in the scheme this
    // module registers, and the layer name export_nearby_trails.py writes
    // (TILES_LAYER), which pipeline/tests/test_export_nearby_trails.py holds
    // from its side.
    expect(NETWORK_TILES_URL).toBe(`${NETWORK_SCHEME}://{z}/{x}/{y}`)
    expect(NETWORK_TILES_LAYER).toBe('trails')
  })
})

describe('a tile, in the order the header gives', () => {
  it('reads it out of the published archive by its z/x/y', async () => {
    getZxy.mockResolvedValue({ data: new Uint8Array([1, 2, 3]).buffer })
    const signal = new AbortController().signal

    const tile = await request(A_TILE, signal)

    expect([...tile.data]).toEqual([1, 2, 3])
    expect(constructed).toEqual([ARCHIVE_URL])
    expect(getZxy).toHaveBeenCalledWith(12, 1198, 1540, signal)
  })

  it('answers empty where the archive never held a tile', async () => {
    // pmtiles' undefined: ground with no organization's trail on it, which
    // is most of the country. A normal answer, not an error.
    getZxy.mockResolvedValue(undefined)

    const tile = await request()

    expect(tile.data).toHaveLength(0)
  })

  it('opens the archive once and reads every tile through it', async () => {
    getZxy.mockResolvedValue(undefined)

    await request(`${NETWORK_SCHEME}://9/150/192`)
    await request(`${NETWORK_SCHEME}://9/151/192`)

    expect(constructed).toHaveLength(1)
    expect(getZxy).toHaveBeenCalledTimes(2)
  })

  it('never asks the bucket when the manifest names no archive', async () => {
    // A release exported before write_tiles existed, or one held back with
    // its parent on a steward's reaches_hikers. Absent means none, decided
    // off latest.json the way every optional artifact's absence is - and
    // decided once, not once per tile.
    manifestNaming('trails.geojson', 'network_overview.geojson')

    const first = await request()
    const second = await request(`${NETWORK_SCHEME}://13/2396/3080`)

    expect(first.data).toHaveLength(0)
    expect(second.data).toHaveLength(0)
    expect(constructed).toHaveLength(0)
    expect(getZxy).not.toHaveBeenCalled()
    expect(publishedSnapshot).toHaveBeenCalledTimes(1)
  })

  it('asks the manifest again when it could not be read, rather than remembering a blank', async () => {
    // An unreadable manifest - offline, a 404, a refused origin - is a
    // snapshot that knows nothing, and knowing nothing is not "not
    // published". The first answer is still an empty tile, because nothing
    // verifiable can be drawn; the second asks afresh and draws.
    publishedSnapshot.mockResolvedValueOnce({ hashes: {} })
    getZxy.mockResolvedValue({ data: new Uint8Array([9]).buffer })

    const blank = await request()
    const drawn = await request()

    expect(blank.data).toHaveLength(0)
    expect([...drawn.data]).toEqual([9])
    expect(publishedSnapshot).toHaveBeenCalledTimes(2)
  })

  it('reads the manifest without the asking tile signal, so one cancelled tile cancels nobody else', async () => {
    getZxy.mockResolvedValue(undefined)

    await request()

    expect(publishedSnapshot).toHaveBeenCalledWith()
  })

  it('answers empty with no bucket configured, and asks nothing of anybody', async () => {
    config.configured = false

    const tile = await request()

    expect(tile.data).toHaveLength(0)
    expect(publishedSnapshot).not.toHaveBeenCalled()
    expect(constructed).toHaveLength(0)
  })

  it('rejects a URL that is not its own', async () => {
    await expect(request('basemap://12/1198/1540')).rejects.toThrow(/network:\/\//)
  })
})

describe('failure, and what is never memoised', () => {
  it('rethrows a failed read and drops the archive, so the next tile opens it afresh', async () => {
    // pmtiles caches a rejected header promise for the life of the instance;
    // keeping the instance would keep answering from a dead radio after the
    // signal came back. MapLibre gets the error, marks the tile, and asks
    // again on the next view change.
    getZxy.mockRejectedValueOnce(new Error('Bad response code: 503'))
    getZxy.mockResolvedValueOnce({ data: new Uint8Array([4]).buffer })

    await expect(request()).rejects.toThrow('503')
    const recovered = await request()

    expect([...recovered.data]).toEqual([4])
    expect(constructed).toEqual([ARCHIVE_URL, ARCHIVE_URL])
  })

  it('lets an abort through as itself, and keeps the archive', async () => {
    // The map cancelling a tile it panned away from is not a failed archive,
    // and a handle dropped for it would re-read the header on every fast pan.
    const abort = Object.assign(new Error('aborted'), { name: 'AbortError' })
    getZxy.mockRejectedValueOnce(abort)
    getZxy.mockResolvedValueOnce(undefined)

    await expect(request()).rejects.toBe(abort)
    await request()

    expect(constructed).toHaveLength(1)
  })

  it('forgets a failed manifest read too, so the asking resumes', async () => {
    publishedSnapshot.mockRejectedValueOnce(new Error('offline'))
    getZxy.mockResolvedValue(undefined)

    await expect(request()).rejects.toThrow('offline')
    await request()

    expect(publishedSnapshot).toHaveBeenCalledTimes(2)
    expect(getZxy).toHaveBeenCalledTimes(1)
  })
})

describe('reading from the network cells a phone holds (#1257 stage 2)', () => {
  // Two cells of the nearby_trails family over Harriman, as cut_cells.py
  // would index them with --context-zoom 8: no context, z9 in the cells. The
  // tile under test - z12 x 1200 y 1531, 74.53-74.44° W, 41.24-41.31° N -
  // sits half a degree clear of every seam, inside n41w075 alone.
  const INDEX = parseCellIndex({
    cell_degrees: 1,
    seam_margin_km: 3,
    context_zoom: 8,
    context: null,
    cells: [
      {
        name: 'n41w075',
        key: 'nearby_trails_cell_n41w075.pmtiles',
        bounds: [-75, 41, -74, 42],
      },
      {
        name: 'n41w074',
        key: 'nearby_trails_cell_n41w074.pmtiles',
        bounds: [-74, 41, -73, 42],
      },
    ],
  })!
  const HARRIMAN = cellPackageKey('n41w075', NETWORK_CELLS)
  const IN_HARRIMAN = `${NETWORK_SCHEME}://12/1200/1531`

  /** The archives every reader constructed so far was pointed at: a package
   *  key for a cell, the bucket URL for the published archive. */
  const askedArchives = () =>
    constructed.map((source) =>
      typeof source === 'string' ? source : (source as { getKey(): string }).getKey(),
    )

  /** Answers per archive: each held cell holds one recognisable tile, the
   *  bucket another. */
  function answersByArchive(tiles: Record<string, number[]>) {
    getZxy.mockImplementation(function (this: { source: unknown }) {
      const source = this.source
      const key =
        typeof source === 'string' ? source : (source as { getKey(): string }).getKey()
      const bytes = tiles[key]
      return Promise.resolve(
        bytes === undefined ? undefined : { data: new Uint8Array(bytes).buffer },
      )
    })
  }

  it('serves a tile from the held cell it sits in, before the manifest or the bucket', async () => {
    setNetworkCells(INDEX, new Set([HARRIMAN]))
    answersByArchive({ [HARRIMAN]: [3, 4] })

    const tile = await request(IN_HARRIMAN)

    expect([...tile.data]).toEqual([3, 4])
    expect(askedArchives()).toEqual([HARRIMAN])
    expect(publishedSnapshot).not.toHaveBeenCalled()
  })

  it('answers from a held cell with no bucket and no manifest at all - the trailhead', async () => {
    config.configured = false
    publishedSnapshot.mockRejectedValue(new Error('offline'))
    setNetworkCells(INDEX, new Set([HARRIMAN]))
    answersByArchive({ [HARRIMAN]: [1] })

    expect([...(await request(IN_HARRIMAN)).data]).toEqual([1])
  })

  it('never asks a cell the phone does not hold', async () => {
    // Not "tried and found absent" - not tried, so a hiker with one stretch
    // does not pay five hundred failed reads per tile.
    setNetworkCells(INDEX, new Set([cellPackageKey('n41w074', NETWORK_CELLS)]))
    answersByArchive({ [ARCHIVE_URL]: [7] })

    const tile = await request(IN_HARRIMAN)

    expect([...tile.data]).toEqual([7])
    expect(askedArchives()).toEqual([ARCHIVE_URL])
  })

  it('falls through to the bucket when the held cell has no such tile', async () => {
    // A held cell answering undefined is ground with no trail on it - the
    // same miss the bucket would report, asked anyway on basemap.ts's terms.
    setNetworkCells(INDEX, new Set([HARRIMAN]))
    answersByArchive({ [ARCHIVE_URL]: [9] })

    const tile = await request(IN_HARRIMAN)

    expect([...tile.data]).toEqual([9])
    expect(askedArchives()).toEqual([HARRIMAN, ARCHIVE_URL])
  })

  it('serves from a cell the moment the shell says it landed', async () => {
    setNetworkCells(INDEX, new Set())
    answersByArchive({ [HARRIMAN]: [1], [ARCHIVE_URL]: [0] })
    expect([...(await request(IN_HARRIMAN)).data]).toEqual([0])

    setNetworkCells(INDEX, new Set([HARRIMAN]))

    expect([...(await request(IN_HARRIMAN)).data]).toEqual([1])
  })

  it('stops reading a cell the shell no longer lists', async () => {
    setNetworkCells(INDEX, new Set([HARRIMAN]))
    answersByArchive({ [HARRIMAN]: [1], [ARCHIVE_URL]: [2] })
    await request(IN_HARRIMAN)

    setNetworkCells(INDEX, new Set())

    expect([...(await request(IN_HARRIMAN)).data]).toEqual([2])
  })

  it('does not memoise a cell read that failed', async () => {
    // pmtilesSource.ts's rule once more: a rejected header promise cached in
    // a reader would keep a resumed cell dark for the session.
    setNetworkCells(INDEX, new Set([HARRIMAN]))
    getZxy.mockImplementation(function (this: { source: unknown }) {
      return typeof this.source === 'string'
        ? Promise.resolve({ data: new Uint8Array([0]).buffer })
        : Promise.reject(new Error('not downloaded'))
    })
    expect([...(await request(IN_HARRIMAN)).data]).toEqual([0])

    answersByArchive({ [HARRIMAN]: [6] })

    expect([...(await request(IN_HARRIMAN)).data]).toEqual([6])
    expect(askedArchives().filter((key) => key === HARRIMAN)).toHaveLength(2)
  })

  it('reads a context archive at and under its zoom, if a cut ever publishes one', async () => {
    const WITH_CONTEXT = parseCellIndex({
      cell_degrees: 1,
      seam_margin_km: 3,
      context_zoom: 9,
      context: 'nearby_trails_context.pmtiles',
      cells: [],
    })!
    setNetworkCells(WITH_CONTEXT, new Set([NETWORK_CELLS.contextPackageKey]))
    answersByArchive({ [NETWORK_CELLS.contextPackageKey]: [5], [ARCHIVE_URL]: [8] })

    expect([...(await request(`${NETWORK_SCHEME}://9/150/191`)).data]).toEqual([5])
    expect([...(await request(IN_HARRIMAN)).data]).toEqual([8])
    expect(
      askedArchives().filter((key) => key === NETWORK_CELLS.contextPackageKey),
    ).toHaveLength(1)
  })
})
