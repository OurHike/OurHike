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
} = await import('./networkTiles')
const { NEARBY_TRAILS_TILES_KEY } = await import('../lib/config')

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
