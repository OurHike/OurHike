import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { StrictMode } from 'react'
import { render, cleanup, screen, waitFor } from '@testing-library/react'
import { MockMap, resetMapLibreMock } from '../test/mocks/maplibre-gl'
import { MapView } from './MapView'
import { poiIconId } from './poiIcons'
import {
  poiFeatureCollection,
  poiTypeFilter,
  POI_ID_PROPERTY,
  POI_LAYER_ID,
  POI_SOURCE_ID,
} from './poiLayers'
import {
  closureFeatureCollection,
  CLOSURE_SOURCE_ID,
  type ClosureBand,
} from './closureLayers'
import {
  warningFeatureCollection,
  WARNING_LAYER_ID,
  WARNING_SOURCE_ID,
  type WarningPoint,
} from './warningLayers'
import { WARNING_ICON_ID } from './warningPin'
import type { MapPoint } from '../lib/legendContents'

// Lifecycle is the whole risk surface here. A map that gets built twice means
// two WebGL contexts, two GPS watchers and doubled tile reads off a 314 MB
// on-device archive; a map that never gets torn down leaks all of the same.
// React StrictMode deliberately mounts -> unmounts -> remounts in development
// precisely to expose that class of bug, so these tests run under it.

const { registrationOrder, basemapOrder, workerOrder } = vi.hoisted(() => ({
  registrationOrder: [] as number[],
  basemapOrder: [] as number[],
  workerOrder: [] as number[],
}))

vi.mock('maplibre-gl', () => import('../test/mocks/maplibre-gl'))

// Records how many maps existed at the moment the protocol was registered.
// A 0 proves registration happened BEFORE any map was constructed - which it
// must, or the map cannot resolve its own pmtiles:// style URL.
vi.mock('./protocol', async () => {
  const { MockMap: Recorded } = await import('../test/mocks/maplibre-gl')
  return {
    PMTILES_SCHEME: 'pmtiles',
    registerPMTilesProtocol: vi.fn(() => {
      registrationOrder.push(Recorded.instances.length)
    }),
  }
})

// The basemap:// scheme has the same before-any-map requirement: the live
// style's osm source declares a basemap:// tiles template, and a map built
// first would ask for tiles through a scheme nothing answers.
vi.mock('./basemap', async () => {
  const { MockMap: Recorded } = await import('../test/mocks/maplibre-gl')
  return {
    registerBasemapProtocol: vi.fn(() => {
      basemapOrder.push(Recorded.instances.length)
    }),
  }
})

// The same recording for the worker, which has the same before-any-map
// requirement and a much quieter failure: MapLibre keeps ONE worker pool per
// page and builds it for the first map, so a URL set after that is a URL the
// pool never reads. The map then parses no tiles at all and draws nothing but
// its background colour, with no error anywhere - see mapWorker.ts.
vi.mock('./mapWorker', async () => {
  const { MockMap: Recorded } = await import('../test/mocks/maplibre-gl')
  return {
    registerMapWorker: vi.fn(() => {
      workerOrder.push(Recorded.instances.length)
      return '/assets/maplibre-gl-worker-test.js'
    }),
  }
})

const PROPS = {
  topoArchiveUrl: 'pmtiles://ourhike-corridor',
  trailsUrl: '/data/trails.geojson',
}

// Already in map coordinates, which is the contract: turning a mile marker
// into a line needs the centerline index, and that is the shell's job.
const CLOSURES: readonly ClosureBand[] = [
  {
    id: 'c1',
    lines: [
      [
        [-77.1, 39.3],
        [-77.1, 39.32],
      ],
    ],
  },
]

const WARNINGS: readonly WarningPoint[] = [{ id: 'r1', lon: -77.2, lat: 39.4 }]

beforeEach(() => {
  resetMapLibreMock()
  registrationOrder.length = 0
  basemapOrder.length = 0
  workerOrder.length = 0
})

afterEach(() => {
  cleanup()
})

describe('MapView', () => {
  it('leaves exactly one LIVE map after StrictMode’s deliberate double-invoke', () => {
    render(
      <StrictMode>
        <MapView {...PROPS} />
      </StrictMode>,
    )

    // React mounts, tears down, and remounts on purpose here, so more than one
    // map may have been CONSTRUCTED over the render's lifetime. What must never
    // happen is two of them being alive at once - that is the actual leak.
    expect(MockMap.live).toHaveLength(1)
  })

  it('tears the map down on unmount, leaving nothing live', () => {
    const { unmount } = render(
      <StrictMode>
        <MapView {...PROPS} />
      </StrictMode>,
    )

    unmount()

    expect(MockMap.live).toHaveLength(0)
    expect(MockMap.instances.every((m) => m.removed)).toBe(true)
  })

  it('does not rebuild the map when re-rendered with a fresh center array identity', () => {
    // A parent passing center={[x, y]} inline hands over a new array every
    // render. If that landed in the effect's dependencies the map would be
    // destroyed and rebuilt on every parent render - catastrophic, and easy to
    // do by accident.
    const { rerender } = render(<MapView {...PROPS} center={[-77.1, 39.3]} zoom={12} />)
    const afterFirstRender = MockMap.instances.length

    rerender(<MapView {...PROPS} center={[-77.1, 39.3]} zoom={12} />)
    rerender(<MapView {...PROPS} center={[-77.1, 39.3]} zoom={12} />)

    expect(MockMap.instances).toHaveLength(afterFirstRender)
    expect(MockMap.live).toHaveLength(1)
  })

  it('registers the pmtiles protocol before constructing any map', () => {
    render(<MapView {...PROPS} />)

    expect(registrationOrder.length).toBeGreaterThan(0)
    expect(registrationOrder[0]).toBe(0)
  })

  it('registers the basemap protocol before constructing any map', () => {
    render(<MapView {...PROPS} />)

    expect(basemapOrder.length).toBeGreaterThan(0)
    expect(basemapOrder[0]).toBe(0)
  })

  it('points MapLibre at its bundled worker before constructing any map', () => {
    // Not a detail of setup order: with no worker MapLibre parses no tiles of
    // any kind, so the basemap, the contours, the trail line and the pins all
    // draw nothing and the map is a blank sheet of paper. It shipped that way.
    render(<MapView {...PROPS} />)

    expect(workerOrder.length).toBeGreaterThan(0)
    expect(workerOrder[0]).toBe(0)
  })

  it('builds the map against the container it rendered, using the style URLs it was given', () => {
    render(<MapView {...PROPS} />)
    const [map] = MockMap.live

    expect(map.options.container).toBeInstanceOf(HTMLElement)
    expect(map.options.style).toBeTypeOf('object')
  })

  it('exposes the map canvas as a labelled region rather than an unnamed div', () => {
    render(<MapView {...PROPS} />)

    expect(screen.getByRole('region', { name: /trail map/i })).toBeInTheDocument()
  })

  it('attaches the map chrome once the map exists', () => {
    render(<MapView {...PROPS} />)
    const [map] = MockMap.live

    expect(map.controls.length).toBeGreaterThan(0)
  })

  it('re-attaches chrome for a units change without rebuilding the map underneath the hiker', () => {
    // Switching the scale bar to metric is a display preference. Rebuilding the
    // whole map for it would drop the WebGL context and re-read tiles - a
    // visible flash mid-walk for what should be a three-control swap.
    const { rerender } = render(<MapView {...PROPS} units="imperial" />)
    const builtInitially = MockMap.instances.length

    rerender(<MapView {...PROPS} units="metric" />)

    expect(MockMap.instances).toHaveLength(builtInitially)
    expect(MockMap.live).toHaveLength(1)
  })

  it('leaves no load listener behind after unmount', () => {
    const { unmount } = render(<MapView {...PROPS} />)
    const [map] = MockMap.live

    unmount()

    expect(map.listenerCount('load')).toBe(0)
  })

  it('leaves no controls attached after unmount', () => {
    const { unmount } = render(<MapView {...PROPS} />)
    const [map] = MockMap.live

    unmount()

    expect(map.controls).toHaveLength(0)
  })

  // Unmounting runs the effect cleanups in the order the effects were declared,
  // and the map-building one is first - so `map.remove()` happens, and every
  // cleanup after it is handed a map that no longer exists. Anything that
  // throws there escapes React's commit phase, and with no error boundary in
  // the tree that unmounts the whole root: the screen the hiker was switching
  // TO never renders at all.
  it('unmounts without throwing, even though its own cleanup removes the map first', () => {
    const { unmount } = render(<MapView {...PROPS} />)

    expect(() => unmount()).not.toThrow()
  })

  // The same teardown, on the path that does not end the screen. `background`
  // is a dependency of the map-building effect, so switching to the offline
  // archive removes one map and builds another - and the chrome cleanup that
  // follows still holds the map that was just removed.
  it('switches background without throwing on the map it just tore down', () => {
    const { rerender } = render(<MapView {...PROPS} background="hiking_topo_live" />)

    expect(() =>
      rerender(<MapView {...PROPS} background="usgs_topo_offline" />),
    ).not.toThrow()
    expect(MockMap.live).toHaveLength(1)
  })
})

describe('POI pins', () => {
  const POIS: MapPoint[] = [
    { id: 'w1', type: 'water', lat: 39.3, lon: -77.1, confidence: 'high' },
    { id: 's1', type: 'shelter', lat: 40.1, lon: -76.4, confidence: 'low' },
  ]

  /** Real MapLibre has its layers and sources by the time `load` fires. */
  function loadStyle(map: MockMap): void {
    map.layerIds = [POI_LAYER_ID, WARNING_LAYER_ID]
    map.sourceIds = [POI_SOURCE_ID, CLOSURE_SOURCE_ID, WARNING_SOURCE_ID]
    map.emit('load')
  }

  it('registers the pin images once the style is up', () => {
    render(<MapView {...PROPS} pois={POIS} />)
    const [map] = MockMap.live

    loadStyle(map)

    expect(map.images.has(poiIconId('water', 'high'))).toBe(true)
  })

  it('pushes the POIs it was given into the source', () => {
    render(<MapView {...PROPS} pois={POIS} />)
    const [map] = MockMap.live

    loadStyle(map)

    expect(map.sourceData.get(POI_SOURCE_ID)).toEqual(poiFeatureCollection(POIS))
  })

  it('filters out the categories the hiker hid from the legend', () => {
    render(<MapView {...PROPS} pois={POIS} hiddenTypes={new Set(['water'])} />)
    const [map] = MockMap.live

    loadStyle(map)

    expect(map.filters.get(POI_LAYER_ID)).toEqual(poiTypeFilter(new Set(['water'])))
  })

  it('hides a category without rebuilding the map underneath the hiker', () => {
    // Tapping a legend row is a filter change. Rebuilding the map for it would
    // drop the WebGL context and re-read tiles off a 1.18 GB archive - a
    // visible stall mid-walk for what should be one paint.
    const { rerender } = render(
      <MapView {...PROPS} pois={POIS} hiddenTypes={new Set()} />,
    )
    const [map] = MockMap.live
    loadStyle(map)
    const builtInitially = MockMap.instances.length

    rerender(<MapView {...PROPS} pois={POIS} hiddenTypes={new Set(['water'])} />)

    expect(MockMap.instances).toHaveLength(builtInitially)
    expect(MockMap.live).toHaveLength(1)
    expect(map.filters.get(POI_LAYER_ID)).toEqual(poiTypeFilter(new Set(['water'])))
  })

  it('takes POIs arriving after the map was built, which is the normal case', () => {
    // The map screen renders before the download finishes and before
    // IndexedDB has been read, so an empty first render is the rule rather
    // than the exception.
    const { rerender } = render(<MapView {...PROPS} />)
    const [map] = MockMap.live
    loadStyle(map)

    rerender(<MapView {...PROPS} pois={POIS} />)

    expect(MockMap.instances).toHaveLength(1)
    expect(map.sourceData.get(POI_SOURCE_ID)).toEqual(poiFeatureCollection(POIS))
  })

  it('draws the closures it was given as bands along the trail', () => {
    render(<MapView {...PROPS} closures={CLOSURES} />)
    const [map] = MockMap.live

    loadStyle(map)

    expect(map.sourceData.get(CLOSURE_SOURCE_ID)).toEqual(
      closureFeatureCollection(CLOSURES),
    )
  })

  it('draws the serious warnings it was given as pins', () => {
    render(<MapView {...PROPS} warnings={WARNINGS} />)
    const [map] = MockMap.live

    loadStyle(map)

    expect(map.images.has(WARNING_ICON_ID)).toBe(true)
    expect(map.sourceData.get(WARNING_SOURCE_ID)).toEqual(
      warningFeatureCollection(WARNINGS),
    )
  })

  it('takes closures and warnings arriving long after the map was built', () => {
    // The normal case, and more so than for the POIs: these come over the
    // network from a backend that is unreachable on most of the trail, so the
    // first render is empty and the data lands whenever signal does.
    const { rerender } = render(<MapView {...PROPS} />)
    const [map] = MockMap.live
    loadStyle(map)

    rerender(<MapView {...PROPS} closures={CLOSURES} warnings={WARNINGS} />)

    expect(MockMap.instances).toHaveLength(1)
    expect(map.sourceData.get(CLOSURE_SOURCE_ID)).toEqual(
      closureFeatureCollection(CLOSURES),
    )
    expect(map.sourceData.get(WARNING_SOURCE_ID)).toEqual(
      warningFeatureCollection(WARNINGS),
    )
  })

  it('does not rebuild the map when a closure clears', () => {
    // A closure being lifted is a data change like any other. Rebuilding for
    // it would drop the WebGL context and re-read tiles off a 1.18 GB archive.
    const { rerender } = render(<MapView {...PROPS} closures={CLOSURES} />)
    const [map] = MockMap.live
    loadStyle(map)

    rerender(<MapView {...PROPS} closures={[]} />)

    expect(MockMap.instances).toHaveLength(1)
    expect(map.sourceData.get(CLOSURE_SOURCE_ID)).toEqual(closureFeatureCollection([]))
  })

  it('leaves no load listeners behind after unmount', () => {
    const { unmount } = render(<MapView {...PROPS} pois={POIS} />)
    const [map] = MockMap.live

    unmount()

    expect(map.listenerCount('load')).toBe(0)
  })

  it('reports which pin was tapped, so the shell can describe it', () => {
    const onSelectPoi = vi.fn()
    render(<MapView {...PROPS} pois={POIS} onSelectPoi={onSelectPoi} />)
    const [map] = MockMap.live
    loadStyle(map)
    map.renderedFeatures.set(POI_LAYER_ID, [
      { properties: { [POI_ID_PROPERTY]: 's1', poi_type: 'shelter' } },
    ])

    map.emit('click', { point: { x: 120, y: 240 } })

    expect(onSelectPoi).toHaveBeenCalledWith('s1')
  })

  it('re-binds taps for a new handler without rebuilding the map', () => {
    // The shell's handler identity changes for reasons that have nothing to do
    // with the pins. Folding this into the POI-data effect would re-serialise
    // every pin on the trail whenever it did.
    const { rerender } = render(<MapView {...PROPS} pois={POIS} onSelectPoi={vi.fn()} />)
    const [map] = MockMap.live
    loadStyle(map)
    map.renderedFeatures.set(POI_LAYER_ID, [
      { properties: { [POI_ID_PROPERTY]: 'w1', poi_type: 'water' } },
    ])
    const second = vi.fn()

    rerender(<MapView {...PROPS} pois={POIS} onSelectPoi={second} />)
    map.emit('click', { point: { x: 10, y: 10 } })

    expect(MockMap.instances).toHaveLength(1)
    expect(second).toHaveBeenCalledWith('w1')
    expect(map.listenerCount('click')).toBe(1)
  })

  it('leaves no tap listeners behind after unmount', () => {
    const { unmount } = render(<MapView {...PROPS} pois={POIS} onSelectPoi={vi.fn()} />)
    const [map] = MockMap.live
    loadStyle(map)

    unmount()

    expect(map.listenerCount('click')).toBe(0)
    expect(map.listenerCount('mousemove')).toBe(0)
  })
})

describe('opening view', () => {
  it('fits the whole corridor when given bounds, letting MapLibre pick the zoom', () => {
    // A zoom number cannot express "show all of this" - what fits depends on
    // the screen, so the same number frames it differently on every phone.
    render(
      <MapView
        topoArchiveUrl="pmtiles://archive"
        trailsUrl="/trails.geojson"
        bounds={[
          [-84.73, 34.2],
          [-68.3, 46.34],
        ]}
      />,
    )

    const options = MockMap.instances[0].options
    expect(options.bounds).toEqual([
      [-84.73, 34.2],
      [-68.3, 46.34],
    ])
    // center/zoom must not also be set - MapLibre would have to reconcile two
    // conflicting instructions about the same camera.
    expect(options.center).toBeUndefined()
    expect(options.zoom).toBeUndefined()
  })

  it('still honours center and zoom when no bounds are given', () => {
    render(
      <MapView
        topoArchiveUrl="pmtiles://archive"
        trailsUrl="/trails.geojson"
        center={[-77.1, 39.3]}
        zoom={12}
      />,
    )

    const options = MockMap.instances[0].options
    expect(options.center).toEqual([-77.1, 39.3])
    expect(options.zoom).toBe(12)
    expect(options.bounds).toBeUndefined()
  })

  describe('the opening view, without bounds', () => {
    it('falls back to its own default camera when given neither bounds nor center', () => {
      render(<MapView {...PROPS} />)

      const options = MockMap.instances[0].options
      expect(options.center).toBeDefined()
      expect(options.zoom).toBeDefined()
      expect(options.bounds).toBeUndefined()
    })
  })
})

// #216: the archive is a range of scales, not a map of everywhere. The app
// opens on the whole trail (~z3.8 on a phone) and every archive built before
// 2026-08-05 starts at z6, so the opening view had nothing to draw and a
// complete 314 MB download rendered as flat paper on every launch.
//
// MockMap does not implement fitBounds, so a map constructed with `bounds`
// sits at its initial zoom of 0 - which is below any floor worth testing and
// is exactly the state the clamp exists for.
describe('keeping the opening camera inside what the download covers', () => {
  const CORRIDOR: [[number, number], [number, number]] = [
    [-84.73, 34.2],
    [-68.3, 46.34],
  ]

  it('lifts the opening view to the archive floor when it falls under it', async () => {
    render(
      <MapView
        {...PROPS}
        background="usgs_topo_offline"
        bounds={CORRIDOR}
        archiveZooms={{ minZoom: 6, maxZoom: 12 }}
      />,
    )

    // 5, not the header's 6: the @2x tileSize declaration (#191) means
    // camera z5 already draws the archive's z6 tiles.
    await waitFor(() => expect(MockMap.live[0]?.getZoom()).toBe(5))
  })

  it('leaves it alone once the archive reaches every zoom', async () => {
    // What the pipeline builds from now on. The whole-trail opening view is a
    // deliberate decision (App.tsx) and must survive untouched.
    render(
      <MapView
        {...PROPS}
        background="usgs_topo_offline"
        bounds={CORRIDOR}
        archiveZooms={{ minZoom: 0, maxZoom: 12 }}
      />,
    )

    await waitFor(() => expect(MockMap.live.length).toBeGreaterThan(0))
    expect(MockMap.live[0].cameraMoves).toHaveLength(0)
  })

  it('leaves the live background alone, which covers every zoom itself', async () => {
    render(
      <MapView
        {...PROPS}
        background="hiking_topo_live"
        bounds={CORRIDOR}
        archiveZooms={{ minZoom: 6, maxZoom: 12 }}
      />,
    )

    await waitFor(() => expect(MockMap.live.length).toBeGreaterThan(0))
    expect(MockMap.live[0].cameraMoves).toHaveLength(0)
  })

  it('claims nothing while the archive coverage is still unknown', async () => {
    // Not-looked-yet must never be acted on as though the download were known
    // to fall short - that conflation is what made #216 invisible.
    render(<MapView {...PROPS} background="usgs_topo_offline" bounds={CORRIDOR} />)

    await waitFor(() => expect(MockMap.live.length).toBeGreaterThan(0))
    expect(MockMap.live[0].cameraMoves).toHaveLength(0)
  })

  it('does not touch a camera the hiker has already moved', async () => {
    // The shell passes `bounds` only for the very first view; once there is a
    // remembered camera it sends centre and zoom instead. So a hiker who
    // deliberately zoomed out to look at the whole trail is never yanked back.
    render(
      <MapView
        {...PROPS}
        background="usgs_topo_offline"
        center={[-77, 39]}
        zoom={4}
        archiveZooms={{ minZoom: 6, maxZoom: 12 }}
      />,
    )

    await waitFor(() => expect(MockMap.live.length).toBeGreaterThan(0))
    expect(MockMap.live[0].getZoom()).toBe(4)
    expect(MockMap.live[0].cameraMoves).toHaveLength(0)
  })
})
