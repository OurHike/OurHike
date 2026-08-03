import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { MockMap, MockVectorSource, resetMapLibreMock } from '../test/mocks/maplibre-gl'
import { CONTOUR_SOURCE_ID, CONTOUR_THRESHOLDS, DEM_MAX_ZOOM } from './terrain'

vi.mock('maplibre-gl', () => import('../test/mocks/maplibre-gl'))

// maplibre-contour is stubbed rather than run: the real DemSource opens a Web
// Worker from a blob URL, which jsdom has neither of, and what is worth
// asserting here is not its isoline maths but OUR wiring - that one source is
// shared, that the interval follows the unit, and that switching units
// re-points the existing source instead of rebuilding the map.
const constructed: Array<Record<string, unknown>> = []
const contourOptions: Array<Record<string, unknown>> = []

vi.mock('maplibre-contour', () => {
  class FakeDemSource {
    sharedDemProtocolUrl = 'dem://shared/{z}/{x}/{y}'
    constructor(options: Record<string, unknown>) {
      constructed.push(options)
    }
    setupMaplibre() {}
    contourProtocolUrl(options: Record<string, unknown>) {
      contourOptions.push(options)
      return `contour://${JSON.stringify(options.multiplier)}/{z}/{x}/{y}`
    }
  }
  return { default: { DemSource: FakeDemSource } }
})

const { attachContourUnits, registerTerrain, resetTerrainForTests } =
  await import('./contours')

beforeEach(() => {
  constructed.length = 0
  contourOptions.length = 0
  resetTerrainForTests()
  resetMapLibreMock()
})

afterEach(() => {
  vi.restoreAllMocks()
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
    // Best-effort in the same way as backdrop.ts: the cost of failing is
    // contours at the old interval, never a broken map.
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
