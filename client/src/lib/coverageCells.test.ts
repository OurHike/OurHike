import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { get, set } from 'idb-keyval'
import {
  BASEMAP_CELLS,
  CELL_INDEX_STORE_KEY,
  cellDownloadRequests,
  cellPackageKey,
  cellsAlong,
  cellsAt,
  cellsForTile,
  CONTEXT_PACKAGE_KEY,
  fetchCellIndex,
  NETWORK_CELLS,
  parseCellIndex,
  priceStretch,
  priceStretches,
  readStoredCellIndex,
  seamEdges,
  tileBounds,
  widen,
  type CellIndex,
  type CoverageCell,
} from './coverageCells'
import { publishedHash } from './dataManifest'
import { sha256Of } from './trailData'
import { BASEMAP_CELLS_KEY, NEARBY_TRAILS_CELLS_KEY } from './config'

// The hiking sheet in pieces (#557/#558). What is under test is the client's
// half of the contract with pipeline/cut_cells.py: that a tile the cutter put
// in a cell is a tile the phone looks for there, that the stretch under a hike
// is derived from the hike and never picked, that a price is the price of what
// is missing, and that the edge drawn on the map is the OUTER edge of what is
// held. The fixtures are three real cells off the published index, measured
// 2026-09-02 against UA release `2026-09-02`.

vi.mock('idb-keyval', () => ({ get: vi.fn(), set: vi.fn(), del: vi.fn() }))
vi.mock('./dataManifest', () => ({ publishedHash: vi.fn() }))
vi.mock('./trailData', () => ({ sha256Of: vi.fn() }))
vi.mock('./useOnline', () => ({ useOnline: () => true }))
// A build with a bucket. Without one the fetch never starts, which is the
// right behaviour and not the one under test here.
vi.mock('./config', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./config')>()),
  DATA_CONFIGURED: true,
  dataUrl: (key: string) => `https://data.test/${key}`,
}))

/** The published shape, as cut_cells.py writes it. */
const PUBLISHED = {
  cell_degrees: 1.0,
  seam_margin_km: 3.0,
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
}

const INDEX = parseCellIndex(PUBLISHED) as CellIndex
const [N34W085, N35W085, N34W084] = INDEX.cells as [
  CoverageCell,
  CoverageCell,
  CoverageCell,
]

/** The slippy tile a point falls in at a zoom - the arithmetic the map does
 *  before it asks basemap.ts for `z/x/y`, so a test can name ground rather
 *  than tile numbers. */
function tileAt(z: number, lon: number, lat: number): [number, number, number] {
  const tiles = 2 ** z
  const x = Math.floor(((lon + 180) / 360) * tiles)
  const rad = (lat * Math.PI) / 180
  const y = Math.floor(
    ((1 - Math.log(Math.tan(rad) + 1 / Math.cos(rad)) / Math.PI) / 2) * tiles,
  )
  return [z, x, y]
}

const names = (cells: readonly CoverageCell[]) => cells.map((cell) => cell.name)

const fetchMock = vi.fn()

beforeEach(() => {
  vi.mocked(get).mockReset()
  vi.mocked(set).mockReset()
  vi.mocked(publishedHash).mockReset()
  vi.mocked(sha256Of).mockReset()
  fetchMock.mockReset()
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('parseCellIndex', () => {
  it('reads the published shape into cells with bounds', () => {
    expect(INDEX.cellDegrees).toBe(1)
    expect(INDEX.seamMarginKm).toBe(3)
    expect(INDEX.contextZoom).toBe(9)
    expect(INDEX.context).toBe('at_basemap_context.pmtiles')
    expect(names(INDEX.cells)).toEqual(['n34w085', 'n35w085', 'n34w084'])
    expect(N34W085.bounds).toEqual([-85, 34, -84, 35])
  })

  it('refuses the whole index over one row it cannot place', () => {
    // A partial index would price a stretch against pieces it cannot name
    // and call it complete - so one bad row is no index, not a shorter one.
    const noBounds = {
      ...PUBLISHED,
      cells: [...PUBLISHED.cells, { name: 'n36w085', key: 'x.pmtiles' }],
    }
    expect(parseCellIndex(noBounds)).toBeNull()

    const inverted = {
      ...PUBLISHED,
      cells: [{ name: 'n34w085', key: 'x.pmtiles', bounds: [-84, 34, -85, 35] }],
    }
    expect(parseCellIndex(inverted)).toBeNull()

    const noKey = {
      ...PUBLISHED,
      cells: [{ name: 'n34w085', key: '', bounds: [-85, 34, -84, 35] }],
    }
    expect(parseCellIndex(noKey)).toBeNull()
  })

  it('refuses anything that is not an index at all', () => {
    expect(parseCellIndex(null)).toBeNull()
    expect(parseCellIndex('cells')).toBeNull()
    expect(parseCellIndex({ ...PUBLISHED, cells: 'many' })).toBeNull()
    expect(parseCellIndex({ ...PUBLISHED, cell_degrees: 0 })).toBeNull()
  })

  it('reads a cut with no context as having none, never as a key', () => {
    // cut_cells.py writes null when the source held nothing at or under the
    // context zoom; an empty string is the same fact spelled by a hand.
    expect(parseCellIndex({ ...PUBLISHED, context: null })?.context).toBeNull()
    expect(parseCellIndex({ ...PUBLISHED, context: '' })?.context).toBeNull()
    expect(parseCellIndex({ ...PUBLISHED, context: 7 })).toBeNull()
  })
})

describe('tileBounds', () => {
  it('gives the whole world for the root tile', () => {
    const [west, south, east, north] = tileBounds(0, 0, 0)
    expect(west).toBe(-180)
    expect(east).toBe(180)
    expect(north).toBeCloseTo(85.0511, 3)
    expect(south).toBeCloseTo(-85.0511, 3)
  })

  it('places a tile exactly where its point is', () => {
    // A tile's rectangle holds the point it was computed from - the
    // round-trip that makes every routing test below a statement about
    // ground rather than about tile numbers.
    const [z, x, y] = tileAt(12, -84.5, 34.5)
    const [west, south, east, north] = tileBounds(z, x, y)
    expect(west).toBeLessThanOrEqual(-84.5)
    expect(east).toBeGreaterThan(-84.5)
    expect(south).toBeLessThanOrEqual(34.5)
    expect(north).toBeGreaterThan(34.5)
  })
})

describe('cellsForTile', () => {
  it('routes a tile in the middle of a cell to that cell alone', () => {
    const [z, x, y] = tileAt(12, -84.5, 34.5)
    expect(names(cellsForTile(INDEX.cells, z, x, y, INDEX.seamMarginKm))).toEqual([
      'n34w085',
    ])
  })

  it('routes a tile straddling a seam to both cells', () => {
    // The cutter wrote this tile into both archives (rectangle overlap), so
    // whichever the hiker holds has to be asked.
    const [z, x, y] = tileAt(12, -84.001, 34.5)
    expect(names(cellsForTile(INDEX.cells, z, x, y, INDEX.seamMarginKm))).toEqual([
      'n34w085',
      'n34w084',
    ])
  })

  it('routes a tile inside the seam margin to the neighbour too, as the cutter did', () => {
    // 3 km at 34.5° N is about 0.033° of longitude. A z14 tile there is
    // about 2 km wide, and the one holding 83.97° W spans 83.980-83.958° W:
    // its western edge is 1.8 km east of the seam, clear of -84 and inside
    // the margin. The cutter wrote it into n34w085's archive too, and this
    // is the routing that finds it there when only n34w085 is held.
    const [z, x, y] = tileAt(14, -83.97, 34.5)
    expect(names(cellsForTile(INDEX.cells, z, x, y, INDEX.seamMarginKm))).toEqual([
      'n34w085',
      'n34w084',
    ])
    // Without the margin the same tile is one cell's, which is what proves
    // the margin did the work above.
    expect(names(cellsForTile(INDEX.cells, z, x, y, 0))).toEqual(['n34w084'])
  })

  it('routes a tile off the cut to nothing', () => {
    const [z, x, y] = tileAt(12, -77.1, 39.3)
    expect(cellsForTile(INDEX.cells, z, x, y, INDEX.seamMarginKm)).toEqual([])
  })
})

describe('cellsAt', () => {
  it('finds the one cell whose core holds a point', () => {
    expect(names(cellsAt(INDEX.cells, -84.5, 35.5))).toEqual(['n35w085'])
  })

  it('gives a point on a shared edge to exactly one cell', () => {
    expect(names(cellsAt(INDEX.cells, -84, 34.5))).toEqual(['n34w084'])
  })

  it('finds nothing off the cut, and says so with an empty list', () => {
    expect(cellsAt(INDEX.cells, -77.1, 39.3)).toEqual([])
  })
})

describe('cellsAlong', () => {
  it('takes the cells a walk crosses, in the index order', () => {
    const run: Array<[number, number]> = [
      [-84.9, 34.5],
      [-84.5, 34.6],
      [-83.9, 34.5],
    ]
    expect(names(cellsAlong(INDEX.cells, [run], 0))).toEqual(['n34w085', 'n34w084'])
  })

  it('takes a cell the walk passes within the margin of, without crossing into it', () => {
    // A hike ending 1 km short of the seam at -84° W. Without the margin it
    // is one cell's; with it the neighbour comes too, so a hiker who walks
    // past their planned end is still on ground they hold.
    const run: Array<[number, number]> = [
      [-84.5, 34.5],
      [-84.011, 34.5],
    ]
    expect(names(cellsAlong(INDEX.cells, [run], 0))).toEqual(['n34w085'])
    expect(names(cellsAlong(INDEX.cells, [run], 3))).toEqual(['n34w085', 'n34w084'])
  })

  it('measures several runs as one walk', () => {
    // trailSlice hands back one run per centerline piece; a hike spanning a
    // gap between pieces is the union of what exists, not a chord across it.
    const runs: Array<Array<[number, number]>> = [
      [
        [-84.5, 34.5],
        [-84.4, 34.5],
      ],
      [
        [-84.5, 35.5],
        [-84.4, 35.5],
      ],
    ]
    expect(names(cellsAlong(INDEX.cells, runs, 0))).toEqual(['n34w085', 'n35w085'])
  })

  it('takes nothing for a walk off the cut', () => {
    expect(cellsAlong(INDEX.cells, [[[-77.1, 39.3]]], 3)).toEqual([])
  })
})

describe('widen', () => {
  it('widens by more degrees of longitude the further from the equator', () => {
    const equator = widen([0, 0, 1, 1], 3)
    const maine = widen([-70, 45, -69, 46], 3)
    expect(0 - equator[0]).toBeLessThan(-70 - maine[0])
    // Latitude degrees do not shrink, so that side is the same at both.
    expect(0 - equator[1]).toBeCloseTo(45 - maine[1], 10)
  })
})

describe('priceStretch', () => {
  const SIZES = {
    'at_basemap_cell_n34w085.pmtiles': 9_131_273,
    'at_basemap_cell_n35w085.pmtiles': 5_000_000,
    'at_basemap_cell_n34w084.pmtiles': 7_000_000,
    'at_basemap_context.pmtiles': 5_710_000,
  }
  const nothingHeld = () => false

  it('prices every piece and the context when nothing is held', () => {
    expect(priceStretch([N34W085, N34W084], INDEX.context, nothingHeld, SIZES)).toEqual({
      pieces: 2,
      missing: 2,
      bytes: 9_131_273 + 7_000_000 + 5_710_000,
    })
  })

  it('prices only what is missing, so extending a stretch never pays for held ground', () => {
    const held = (key: string) =>
      key === cellPackageKey('n34w085') || key === CONTEXT_PACKAGE_KEY
    expect(priceStretch([N34W085, N34W084], INDEX.context, held, SIZES)).toEqual({
      pieces: 2,
      missing: 1,
      bytes: 7_000_000,
    })
  })

  it('withholds the figure rather than understating it when a piece is unpriced', () => {
    // lib/packages.ts's all-or-nothing rule: a total missing the piece
    // nobody measured strands whoever freed exactly enough room.
    const { 'at_basemap_cell_n34w084.pmtiles': _unpriced, ...partial } = SIZES
    expect(
      priceStretch([N34W085, N34W084], INDEX.context, nothingHeld, partial).bytes,
    ).toBeNull()
  })

  it('prices nothing for a cut with no context', () => {
    expect(priceStretch([N35W085], null, nothingHeld, SIZES)).toEqual({
      pieces: 1,
      missing: 1,
      bytes: 5_000_000,
    })
  })
})

describe('seamEdges', () => {
  it('draws all four edges of a lone cell', () => {
    expect(seamEdges([N34W085], 1)).toHaveLength(4)
  })

  it('leaves out the edge two held cells share - the map is continuous across it', () => {
    const edges = seamEdges([N34W085, N34W084], 1)
    expect(edges).toHaveLength(6)
    const onTheSeam = edges.filter(([from, to]) => from[0] === -84 && to[0] === -84)
    expect(onTheSeam).toEqual([])
  })

  it('leaves out the shared edge when the two held cells are stacked north-south', () => {
    const edges = seamEdges([N34W085, N35W085], 1)
    // Stacked north-south: the shared parallel at 35° N goes, the rest stay.
    expect(edges).toHaveLength(6)
    // The seam runs west-east along 35° N, so both its endpoints sit at that
    // latitude and its longitudes differ. Filtering on a constant longitude
    // instead - which this assertion used to do - can only ever select a
    // meridian, so it matched each cell's own east edge and never the seam.
    const onTheSeam = edges.filter(([from, to]) => from[1] === 35 && to[1] === 35)
    expect(onTheSeam).toEqual([])
  })

  it('keeps the seam between a held cell and one that is not', () => {
    // Only the southern cell is held, so 35° N is a real boundary of the
    // downloaded area rather than an internal join, and has to be drawn. This
    // is the direction the assertion above cannot check, and the case the
    // test that now sits above it was named for while checking the other one.
    const edges = seamEdges([N34W085], 1)
    const onTheSeam = edges.filter(([from, to]) => from[1] === 35 && to[1] === 35)
    expect(onTheSeam).toEqual([
      [
        [-85, 35],
        [-84, 35],
      ],
    ])
  })

  it('draws nothing for nothing', () => {
    expect(seamEdges([], 1)).toEqual([])
  })
})

describe('readStoredCellIndex', () => {
  it('re-validates what an earlier launch stored', async () => {
    vi.mocked(get).mockResolvedValue({ index: PUBLISHED, hash: 'abc' })

    expect(names((await readStoredCellIndex())?.cells ?? [])).toEqual([
      'n34w085',
      'n35w085',
      'n34w084',
    ])
    expect(get).toHaveBeenCalledWith(CELL_INDEX_STORE_KEY)
  })

  it('reads a stored copy it can no longer parse as no index', async () => {
    vi.mocked(get).mockResolvedValue({ index: { cells: 'gone' }, hash: null })
    expect(await readStoredCellIndex()).toBeNull()
  })

  it('reads an unreadable store as no index rather than throwing', async () => {
    vi.mocked(get).mockRejectedValue(new Error('InvalidStateError'))
    expect(await readStoredCellIndex()).toBeNull()
  })
})

describe('fetchCellIndex', () => {
  const body = JSON.stringify(PUBLISHED)
  const response = (status: number) =>
    ({
      ok: status >= 200 && status < 300,
      status,
      arrayBuffer: () => Promise.resolve(new TextEncoder().encode(body).buffer),
    }) as unknown as Response

  it('holds the index to its published hash and stores it', async () => {
    vi.mocked(publishedHash).mockResolvedValue('feed')
    vi.mocked(sha256Of).mockResolvedValue('feed')
    fetchMock.mockResolvedValue(response(200))

    const fetched = await fetchCellIndex()

    expect(names(fetched?.cells ?? [])).toEqual(['n34w085', 'n35w085', 'n34w084'])
    expect(publishedHash).toHaveBeenCalledWith(BASEMAP_CELLS_KEY, expect.anything())
    expect(set).toHaveBeenCalledWith(CELL_INDEX_STORE_KEY, {
      index: PUBLISHED,
      hash: 'feed',
    })
  })

  it('refuses bytes that are not what was published, and keeps the store as it was', async () => {
    // A corrupt index is a stretch priced against pieces that do not exist;
    // nothing verified is replaced by something that is not.
    vi.mocked(publishedHash).mockResolvedValue('feed')
    vi.mocked(sha256Of).mockResolvedValue('dead')
    fetchMock.mockResolvedValue(response(200))

    expect(await fetchCellIndex()).toBeNull()
    expect(set).not.toHaveBeenCalled()
  })

  it('reads a release with no cells as no index', async () => {
    vi.mocked(publishedHash).mockResolvedValue(null)
    fetchMock.mockResolvedValue(response(404))

    expect(await fetchCellIndex()).toBeNull()
    expect(set).not.toHaveBeenCalled()
  })

  it('accepts an index the manifest names no hash for, on the archives’ own downgrade', async () => {
    vi.mocked(publishedHash).mockResolvedValue(null)
    fetchMock.mockResolvedValue(response(200))

    expect(names((await fetchCellIndex())?.cells ?? [])).toHaveLength(3)
    expect(sha256Of).not.toHaveBeenCalled()
  })

  it('reads no signal as no index', async () => {
    vi.mocked(publishedHash).mockResolvedValue(null)
    fetchMock.mockRejectedValue(new TypeError('Failed to fetch'))

    expect(await fetchCellIndex()).toBeNull()
  })
})

describe('a second family of cells (#1257 stage 2)', () => {
  // The network's tiles, cut on the same graticule: the same geometry, a
  // different index, and different keys for the same square of ground.
  const NETWORK_PUBLISHED = {
    cell_degrees: 1.0,
    seam_margin_km: 3.0,
    context_zoom: 8,
    context: null,
    cells: [
      {
        name: 'n34w085',
        key: 'nearby_trails_cell_n34w085.pmtiles',
        bounds: [-85, 34, -84, 35],
      },
      {
        name: 'n34w084',
        key: 'nearby_trails_cell_n34w084.pmtiles',
        bounds: [-84, 34, -83, 35],
      },
    ],
  }
  const NETWORK_INDEX = parseCellIndex(NETWORK_PUBLISHED) as CellIndex

  it('keeps the two families under different keys for the same ground', () => {
    // Both hold n34w085. One key space would let the basemap's Georgia
    // overwrite the network's, and a marker for one read as the other's.
    expect(cellPackageKey('n34w085', NETWORK_CELLS)).not.toBe(cellPackageKey('n34w085'))
    expect(cellPackageKey('n34w085', BASEMAP_CELLS)).toBe(cellPackageKey('n34w085'))
    expect(NETWORK_CELLS.contextPackageKey).not.toBe(BASEMAP_CELLS.contextPackageKey)
    expect(NETWORK_CELLS.indexStoreKey).not.toBe(BASEMAP_CELLS.indexStoreKey)
    expect(NETWORK_CELLS.indexKey).toBe(NEARBY_TRAILS_CELLS_KEY)
  })

  it('registers a family as download requests - every cell, the context if there is one, nothing for no index', () => {
    expect(cellDownloadRequests(NETWORK_INDEX, NETWORK_CELLS)).toEqual([
      {
        packageKey: cellPackageKey('n34w085', NETWORK_CELLS),
        url: 'https://data.test/nearby_trails_cell_n34w085.pmtiles',
        artifactKey: 'nearby_trails_cell_n34w085.pmtiles',
      },
      {
        packageKey: cellPackageKey('n34w084', NETWORK_CELLS),
        url: 'https://data.test/nearby_trails_cell_n34w084.pmtiles',
        artifactKey: 'nearby_trails_cell_n34w084.pmtiles',
      },
    ])
    expect(cellDownloadRequests(INDEX, BASEMAP_CELLS).at(-1)).toEqual({
      packageKey: CONTEXT_PACKAGE_KEY,
      url: 'https://data.test/at_basemap_context.pmtiles',
      artifactKey: 'at_basemap_context.pmtiles',
    })
    expect(cellDownloadRequests(null, NETWORK_CELLS)).toEqual([])
  })

  it('fetches a family’s own index and stores it under its own record', async () => {
    vi.mocked(publishedHash).mockResolvedValue('feed')
    vi.mocked(sha256Of).mockResolvedValue('feed')
    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      arrayBuffer: () =>
        Promise.resolve(
          new TextEncoder().encode(JSON.stringify(NETWORK_PUBLISHED)).buffer,
        ),
    } as unknown as Response)

    const fetched = await fetchCellIndex({ family: NETWORK_CELLS })

    expect(names(fetched?.cells ?? [])).toEqual(['n34w085', 'n34w084'])
    expect(fetched?.context).toBeNull()
    expect(publishedHash).toHaveBeenCalledWith(NEARBY_TRAILS_CELLS_KEY, expect.anything())
    expect(fetchMock).toHaveBeenCalledWith(
      `https://data.test/${NEARBY_TRAILS_CELLS_KEY}`,
      expect.anything(),
    )
    expect(set).toHaveBeenCalledWith(NETWORK_CELLS.indexStoreKey, {
      index: NETWORK_PUBLISHED,
      hash: 'feed',
    })
  })

  it('reads a family’s stored index from its own record', async () => {
    vi.mocked(get).mockImplementation((key) =>
      Promise.resolve(
        key === NETWORK_CELLS.indexStoreKey
          ? { index: NETWORK_PUBLISHED, hash: null }
          : undefined,
      ),
    )

    expect(names((await readStoredCellIndex(NETWORK_CELLS))?.cells ?? [])).toEqual([
      'n34w085',
      'n34w084',
    ])
    expect(await readStoredCellIndex()).toBeNull()
  })

  describe('priceStretches - one price for both families', () => {
    const SIZES = {
      'at_basemap_cell_n34w085.pmtiles': 9_000_000,
      'at_basemap_cell_n34w084.pmtiles': 7_000_000,
      'at_basemap_context.pmtiles': 5_710_000,
      'nearby_trails_cell_n34w085.pmtiles': 1_468_402,
      'nearby_trails_cell_n34w084.pmtiles': 87_729,
    }
    const [NET_N34W085, NET_N34W084] = NETWORK_INDEX.cells as [CoverageCell, CoverageCell]
    const parts = (basemap: CoverageCell[], network: CoverageCell[]) => [
      { cells: basemap, context: INDEX.context, family: BASEMAP_CELLS },
      { cells: network, context: NETWORK_INDEX.context, family: NETWORK_CELLS },
    ]

    it('counts a square of ground once, whatever is published for it', () => {
      // Two archives over n34w085 and two over n34w084 are two pieces to a
      // hiker, not four - and the bytes are all four plus the context.
      expect(
        priceStretches(
          parts([N34W085, N34W084], [NET_N34W085, NET_N34W084]),
          () => false,
          SIZES,
        ),
      ).toEqual({
        pieces: 2,
        missing: 2,
        bytes: 9_000_000 + 7_000_000 + 5_710_000 + 1_468_402 + 87_729,
      })
    })

    it('calls a piece missing while any family’s cell for it is', () => {
      // The basemap of n34w085 is here and the network is not: the ground is
      // held, the trails on it are not, and the card must still offer it.
      const held = (key: string) =>
        key === cellPackageKey('n34w085') || key === CONTEXT_PACKAGE_KEY
      expect(priceStretches(parts([N34W085], [NET_N34W085]), held, SIZES)).toEqual({
        pieces: 1,
        missing: 1,
        bytes: 1_468_402,
      })
    })

    it('prices nothing for a piece both families hold, and counts it', () => {
      const held = (key: string) =>
        key === cellPackageKey('n34w085') ||
        key === cellPackageKey('n34w085', NETWORK_CELLS) ||
        key === CONTEXT_PACKAGE_KEY
      expect(priceStretches(parts([N34W085], [NET_N34W085]), held, SIZES)).toEqual({
        pieces: 1,
        missing: 0,
        bytes: 0,
      })
    })

    it('withholds the total when either family has an unpriced archive', () => {
      const { 'nearby_trails_cell_n34w084.pmtiles': _unpriced, ...partial } = SIZES
      expect(
        priceStretches(parts([N34W084], [NET_N34W084]), () => false, partial).bytes,
      ).toBeNull()
    })

    it('is priceStretch for a single family', () => {
      expect(priceStretches(parts([N34W085, N34W084], []), () => false, SIZES)).toEqual(
        priceStretch([N34W085, N34W084], INDEX.context, () => false, SIZES),
      )
    })
  })
})
