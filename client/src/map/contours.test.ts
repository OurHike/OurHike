import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { MockMap, MockVectorSource, resetMapLibreMock } from '../test/mocks/maplibre-gl'
import { CONTOUR_SOURCE_ID, CONTOUR_THRESHOLDS, DEM_MAX_ZOOM } from './terrain'
import { demGetTile } from './demTiles'
import { WorkerDemManager } from './demRpc'
import { setDemCells } from './demTiles'
import type { CellIndex } from '../lib/coverageCells'

vi.mock('maplibre-gl', () => import('../test/mocks/maplibre-gl'))

// demTiles is a seam here rather than a subject: what these tests assert is
// that contours.ts hands the local-first getTile to whichever manager it
// built, and that the shell's cells reach the no-Worker path. Both are
// identity questions, and mocking keeps the answer to the second observable
// without reaching into another module's state.
vi.mock('./demTiles', () => ({
  demGetTile: vi.fn(),
  setDemCells: vi.fn(),
}))

// maplibre-contour is stubbed rather than run: the real DemSource opens a Web
// Worker, which jsdom does not have, and what is worth asserting here is not
// its isoline maths but OUR wiring - that one source is shared, that its
// elevation reads go through the local-first seam, that the interval follows
// the unit, and that switching units re-points the existing source instead
// of rebuilding the map.
const constructed: Array<Record<string, unknown>> = []
const instances: Array<{ manager: unknown }> = []
const contourOptions: Array<Record<string, unknown>> = []

vi.mock('maplibre-contour', () => {
  class FakeDemSource {
    sharedDemProtocolUrl = 'dem://shared/{z}/{x}/{y}'
    // The manager the real DemSource would build with `worker: false` - the
    // field contours.ts either swaps out (Worker available) or reaches into
    // to replace `getTile` (no Worker).
    manager: Record<string, unknown> = {}
    constructor(options: Record<string, unknown>) {
      constructed.push(options)
      instances.push(this)
    }
    setupMaplibre() {}
    contourProtocolUrl(options: Record<string, unknown>) {
      contourOptions.push(options)
      return `contour://${JSON.stringify(options.multiplier)}/{z}/{x}/{y}`
    }
  }
  return { default: { DemSource: FakeDemSource, LocalDemManager: class {} } }
})

const { attachContourUnits, registerTerrain, resetTerrainForTests } =
  await import('./contours')
const { setTerrainCells, resetDemCellsForTests } = await import('./demCells')

/** A cell index in the published shape - two squares over the Hudson
 *  Highlands, enough to be recognisable on the other side of a postMessage. */
const DEM_INDEX: CellIndex = {
  cellDegrees: 1,
  seamMarginKm: 3,
  contextZoom: 9,
  context: 'dem_context.pmtiles',
  cells: [
    {
      name: 'n41w075',
      key: 'dem_cell_n41w075.pmtiles',
      bounds: [-75, 41, -74, 42],
      covered: [-75, 41, -74, 42],
    },
  ],
}

/** A Worker that records what it was posted, so the notification can be read
 *  where a real page would have a thread. */
function stubWorker(posted: unknown[]): void {
  vi.stubGlobal(
    'Worker',
    class {
      postMessage(message: unknown) {
        posted.push(message)
      }
      addEventListener() {}
    },
  )
}

beforeEach(() => {
  constructed.length = 0
  instances.length = 0
  contourOptions.length = 0
  resetTerrainForTests()
  resetDemCellsForTests()
  resetMapLibreMock()
  vi.mocked(setDemCells).mockClear()
})

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

function map(): MockMap {
  return new MockMap({}) as unknown as MockMap
}

describe('registerTerrain', () => {
  it('reads elevation once for both the hillshade and the contours', () => {
    // The reason a single DemSource is worth the singleton: it owns the
    // decoded-tile cache, so the two consumers share one download per screen
    // rather than each pulling its own copy of the DEM.
    const first = registerTerrain('imperial')
    const second = registerTerrain('imperial')

    expect(constructed).toHaveLength(1)
    expect(first.demUrl).toBe(second.demUrl)
  })

  it('does not re-register the protocol on a second call', () => {
    registerTerrain()
    registerTerrain()

    expect(constructed).toHaveLength(1)
  })

  it('asks for terrarium tiles no deeper than the DEM really resolves', () => {
    registerTerrain()

    expect(constructed[0]).toMatchObject({
      encoding: 'terrarium',
      maxzoom: DEM_MAX_ZOOM,
    })
  })

  it('converts to feet for an imperial reader and leaves metres alone', () => {
    registerTerrain('imperial')
    resetTerrainForTests()
    registerTerrain('metric')

    expect(contourOptions[0].multiplier).toBeCloseTo(3.28084)
    expect(contourOptions[1].multiplier).toBe(1)
  })

  it('carries the zoom-varying interval through, rather than one baked value', () => {
    // A single interval is unreadable at one end of the zoom range or the
    // other; this is the thing a pre-rendered contour layer cannot do.
    registerTerrain('imperial')

    expect(contourOptions[0].thresholds).toBe(CONTOUR_THRESHOLDS.imperial)
  })
})

describe('the local-first elevation seam (#187)', () => {
  it('never lets the DemSource build its own worker - the manager is decided here', () => {
    // `worker: false` even where a Worker exists: the library's worker
    // fetches with a plain fetch and cannot be handed the local-first
    // getTile, so contours.ts owns the manager decision on both paths.
    registerTerrain()

    expect(constructed[0]).toMatchObject({ worker: false })
  })

  it('replaces the tile fetch with the local-first one where no Worker exists', () => {
    // jsdom's own state - and the real fallback path. The manager the
    // DemSource built stays, so decode and isolines run where they always
    // did; only the fetch seam changes, to archive-first.
    registerTerrain()

    expect(instances[0].manager).toMatchObject({ getTile: demGetTile })
  })

  it('routes through the app’s own DEM worker when Workers exist', () => {
    const workers: unknown[] = []
    vi.stubGlobal(
      'Worker',
      class {
        listeners: unknown[] = []
        constructor(url: unknown) {
          workers.push(url)
        }
        postMessage() {}
        addEventListener(_type: string, listener: unknown) {
          this.listeners.push(listener)
        }
      },
    )

    registerTerrain()

    // One worker for the page, running the app's demWorker entry - the
    // module that constructs LocalDemManager WITH the local-first getTile.
    expect(workers).toHaveLength(1)
    expect(String(workers[0])).toContain('demWorker')
    expect(instances[0].manager).toBeInstanceOf(WorkerDemManager)
  })
})

describe('setTerrainCells (#1475)', () => {
  it('posts the shell\u2019s held cells into the DEM worker', () => {
    const posted: unknown[] = []
    stubWorker(posted)
    registerTerrain()

    setTerrainCells(DEM_INDEX, new Set(['ourhike:dem-cell:n41w075']))

    // An array, not a Set: this crosses a structured clone, and the worker
    // side rebuilds the Set.
    expect(posted).toEqual([
      {
        kind: 'setCells',
        index: DEM_INDEX,
        held: ['ourhike:dem-cell:n41w075'],
      },
    ])
  })

  it('replays the shell\u2019s answer into a source built afterwards', () => {
    const posted: unknown[] = []
    stubWorker(posted)

    // The ordinary order, and the one that would silently lose the answer if
    // this only forwarded: the cell index is fetched at launch, the map is
    // built later.
    setTerrainCells(DEM_INDEX, new Set(['ourhike:dem-cell:n41w075']))
    expect(posted).toEqual([])

    registerTerrain()

    expect(posted).toEqual([
      {
        kind: 'setCells',
        index: DEM_INDEX,
        held: ['ourhike:dem-cell:n41w075'],
      },
    ])
  })

  it('sets the module variable directly where there is no worker to post to', () => {
    const setDemCellsSpy = vi.mocked(setDemCells)
    registerTerrain()

    setTerrainCells(DEM_INDEX, new Set(['ourhike:dem-cell:n41w075']))

    expect(setDemCellsSpy).toHaveBeenCalledWith(
      DEM_INDEX,
      new Set(['ourhike:dem-cell:n41w075']),
    )
  })
})

describe('attachContourUnits', () => {
  it('re-points the existing source instead of rebuilding the map', () => {
    // The invariant MapView already holds for the scale bar: a settings change
    // must never pull the map out from under a hiker.
    const m = map()
    m.styleLoaded = true
    const source = new MockVectorSource(['contour://3.28084/{z}/{x}/{y}'])
    m.sources.set(CONTOUR_SOURCE_ID, source)

    attachContourUnits(m as never, 'metric')

    expect(source.setTilesCalls).toHaveLength(1)
    expect(source.tiles[0]).toContain('contour://1/')
  })

  it('does nothing when the interval already matches', () => {
    // Mounting must not immediately invalidate the tiles the style just asked
    // for, which a naive "always setTiles" would do on every single build.
    const m = map()
    m.styleLoaded = true
    const wanted = registerTerrain('imperial').contourTilesUrl
    const source = new MockVectorSource([wanted])
    m.sources.set(CONTOUR_SOURCE_ID, source)

    attachContourUnits(m as never, 'imperial')

    expect(source.setTilesCalls).toEqual([])
  })

  it('waits for the contour source when the style has not brought it yet', () => {
    const m = map()
    const source = new MockVectorSource(['contour://3.28084/{z}/{x}/{y}'])

    attachContourUnits(m as never, 'metric')
    expect(source.setTilesCalls).toEqual([])

    m.sources.set(CONTOUR_SOURCE_ID, source)
    m.emit('styledata')
    expect(source.setTilesCalls).toHaveLength(1)
  })

  it('does nothing after detach, so a late style event cannot retune a stale map', () => {
    const m = map()
    const source = new MockVectorSource(['contour://3.28084/{z}/{x}/{y}'])

    const detach = attachContourUnits(m as never, 'metric')
    detach()
    m.sources.set(CONTOUR_SOURCE_ID, source)
    m.emit('styledata')

    expect(source.setTilesCalls).toEqual([])
    expect(m.listenerCount('styledata')).toBe(0)
  })

  it('is a no-op on the offline background, where there is no contour source', () => {
    // Not a failure - the style simply has no contours to retune.
    const m = map()
    m.styleLoaded = true
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})

    expect(() => attachContourUnits(m as never, 'metric')).not.toThrow()
    expect(warn).not.toHaveBeenCalled()
  })

  it('warns and leaves the previous interval when the source rejects the change', () => {
    // Best-effort in the same way as poiLayers.ts's attach helpers: the cost
    // of failing is contours at the old interval, never a broken map.
    const m = map()
    m.styleLoaded = true
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    m.sources.set(CONTOUR_SOURCE_ID, {
      tiles: ['contour://3.28084/{z}/{x}/{y}'],
      setTiles() {
        throw new Error('style went away mid-flight')
      },
    })

    expect(() => attachContourUnits(m as never, 'metric')).not.toThrow()
    expect(warn).toHaveBeenCalled()
  })
})
