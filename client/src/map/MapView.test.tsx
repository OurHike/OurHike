import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { StrictMode } from 'react'
import { act, render, cleanup, screen, waitFor } from '@testing-library/react'
import { MockMap, resetMapLibreMock } from '../test/mocks/maplibre-gl'
import { MapView } from './MapView'
import {
  BACKDROP_LAYER_ID,
  MAP_BACKDROP,
  TRAIL_OVERVIEW_SOURCE_ID,
  TRAILS_SOURCE_ID,
} from './style'
import { LIVE_TOPO_LAYER_IDS, TOPO_PALETTE_RED } from './liveTopo'
import { poiIconImages } from './poiIconImages'
import { buildPoiIcons, poiIconId } from './poiIcons'
import {
  poiFeatureCollection,
  poiFilter,
  POI_ID_PROPERTY,
  POI_DOT_LAYER_ID,
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
import {
  CORRIDOR_KIND_PROPERTY,
  CORRIDOR_SOURCE_ID,
  EMPTY_CORRIDOR,
  UNATTRIBUTED_KIND,
  type CorridorFeatureCollection,
} from './corridorLayers'
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
  it('frames the opening box against the room the caller says it has', () => {
    // First run draws the steps OVER this map, so the box has to be fitted to
    // the strip they leave rather than to the whole canvas. Without this the
    // corridor was fitted to a full-height map and then three quarters of it
    // was covered, leaving a fragment of Maine in the corner above the card
    // while the sentence beside it said "the whole trail".
    const padding = { top: 24, bottom: 658, left: 24, right: 24 }
    const corridor: [[number, number], [number, number]] = [
      [-84.73, 34.2],
      [-68.3, 46.34],
    ]
    render(<MapView {...PROPS} bounds={corridor} boundsPadding={padding} />)

    expect(MockMap.instances.at(-1)?.options.fitBoundsOptions).toEqual({ padding })
  })

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

  it('repaints for a theme change without rebuilding the map underneath the hiker', () => {
    // The theme is the preference most likely to change mid-walk - a phone on
    // 'auto' flips to dark at sunset, which is when this app is most likely
    // to be out. A rebuild there would take the map from a hiker reading it
    // in fading light. The construction effect omits `theme` on purpose
    // (MapView.tsx); this is that omission's regression test.
    const { rerender } = render(<MapView {...PROPS} theme="light" />)
    const builtInitially = MockMap.instances.length
    const [map] = MockMap.live

    act(() => map.emit('load'))
    rerender(<MapView {...PROPS} theme="dark" />)

    expect(MockMap.instances).toHaveLength(builtInitially)
    expect(MockMap.live).toHaveLength(1)
    // And the repaint really happened - the backdrop took the dark colour in
    // place rather than waiting for some future rebuild to apply it.
    expect(map.paintProperties.get(`${BACKDROP_LAYER_ID}/background-color`)).toBe(
      MAP_BACKDROP.dark,
    )
  })

  it('repaints for a map-style or red-light change without rebuilding the map', () => {
    // MAP_STYLE_SPEC.md spells this as a requirement rather than a nicety:
    // appearance preferences are display-only and never a map rebuild. The
    // construction effect omits `mapStyle` and `redLight` exactly as it omits
    // `theme`; this is that omission's regression test.
    const { rerender } = render(<MapView {...PROPS} mapStyle="field" />)
    const builtInitially = MockMap.instances.length
    const [map] = MockMap.live

    act(() => map.emit('load'))
    rerender(<MapView {...PROPS} mapStyle="night_hike" redLight />)

    expect(MockMap.instances).toHaveLength(builtInitially)
    expect(MockMap.live).toHaveLength(1)
    // And the repaint landed: red light's own ink on the backdrop, in place.
    expect(map.paintProperties.get(`${BACKDROP_LAYER_ID}/background-color`)).toBe(
      TOPO_PALETTE_RED.labelHalo,
    )
  })

  it('rewires visibility for a detail change without rebuilding the map', () => {
    const { rerender } = render(<MapView {...PROPS} detail="standard" />)
    const builtInitially = MockMap.instances.length
    const [map] = MockMap.live

    act(() => map.emit('load'))
    rerender(<MapView {...PROPS} detail="minimal" />)

    expect(MockMap.instances).toHaveLength(builtInitially)
    expect(MockMap.live).toHaveLength(1)
    expect(map.layoutProperties.get(`${LIVE_TOPO_LAYER_IDS.track}/visibility`)).toBe(
      'none',
    )
  })

  it('re-points the trail source for new lines without rebuilding the map', () => {
    // The lines come out of IndexedDB a beat after the map is built, so this
    // omission is the one a cold start actually pays for: depending on the URL
    // meant every launch tore the map down and built a second one a second
    // after the first appeared. They are a GeoJSON source, and a
    // GeoJSON source takes a new URL in place - the same treatment the POIs,
    // closures and warnings have always had.
    const { rerender } = render(<MapView {...PROPS} trailsUrl="/data/empty.geojson" />)
    const builtInitially = MockMap.instances.length
    const [map] = MockMap.live

    act(() => map.emit('load'))
    rerender(<MapView {...PROPS} trailsUrl="/data/trails.geojson" />)

    expect(MockMap.instances).toHaveLength(builtInitially)
    expect(MockMap.live).toHaveLength(1)
    // And the lines really landed, rather than waiting on a rebuild that no
    // longer comes.
    expect(map.sourceData.get(TRAILS_SOURCE_ID)).toBe('/data/trails.geojson')
  })

  it('does not re-push lines the style was built holding', () => {
    // Seeding the style is what puts the trail on the very first frame when
    // the lines are already known. Writing them in again straight afterwards
    // would re-fetch and re-tile twelve megabytes of coordinates for a source
    // that already holds them.
    render(<MapView {...PROPS} trailsUrl="/data/trails.geojson" />)
    const [map] = MockMap.live

    act(() => map.emit('load'))

    expect(map.options.style).toMatchObject({
      sources: { [TRAILS_SOURCE_ID]: { data: '/data/trails.geojson' } },
    })
    expect(map.sourceData.has(TRAILS_SOURCE_ID)).toBe(false)
  })

  it('leaves no style listeners behind after unmount', () => {
    const { unmount } = render(<MapView {...PROPS} />)
    const [map] = MockMap.live

    unmount()

    // 'styledata' is the event production actually listens on
    // (map/styleReady.ts); this used to assert only 'load', which nothing
    // has registered since the whenStyleReady migration - a leak test that
    // could not fail (#175).
    expect(map.listenerCount('styledata')).toBe(0)
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

describe('the corridor-view sketch (#869)', () => {
  it('pushes it onto the map that is already there', async () => {
    render(<MapView {...PROPS} overviewTrailsUrl="blob:sketch" />)
    const [map] = MockMap.live
    map.sourceIds = [TRAIL_OVERVIEW_SOURCE_ID]
    map.emit('styledata')

    expect(map.sourceData.get(TRAIL_OVERVIEW_SOURCE_ID)).toBe('blob:sketch')
  })

  it('clears it the moment there is a real line, rather than leaving it under one', async () => {
    // The sketch is 100 m of tolerance, drawn only below the pin seam
    // (map/style.ts). Leaving it on the map once the surveyed line is there
    // would mean two trails, one of them approximate, and nothing on screen
    // saying which is which.
    const { rerender } = render(<MapView {...PROPS} overviewTrailsUrl="blob:sketch" />)
    const [map] = MockMap.live
    map.sourceIds = [TRAIL_OVERVIEW_SOURCE_ID]
    map.emit('styledata')

    rerender(<MapView {...PROPS} overviewTrailsUrl={null} />)

    expect(map.sourceData.get(TRAIL_OVERVIEW_SOURCE_ID)).toEqual({
      type: 'FeatureCollection',
      features: [],
    })
  })

  it('draws no sketch at all when the shell has none to give it', () => {
    render(<MapView {...PROPS} />)
    const [map] = MockMap.live
    map.sourceIds = [TRAIL_OVERVIEW_SOURCE_ID]
    map.emit('styledata')

    expect(map.sourceData.get(TRAIL_OVERVIEW_SOURCE_ID)).toEqual({
      type: 'FeatureCollection',
      features: [],
    })
  })
})

describe('POI pins', () => {
  const POIS: MapPoint[] = [
    { id: 'w1', type: 'water', lat: 39.3, lon: -77.1, confidence: 'high' },
    { id: 's1', type: 'shelter', lat: 40.1, lon: -76.4, confidence: 'low' },
  ]

  /** One unattributed run, already in map coordinates - what App.tsx's
   *  corridorFeatures() hands down. */
  const CORRIDOR: CorridorFeatureCollection = {
    type: 'FeatureCollection',
    features: [
      {
        type: 'Feature',
        geometry: {
          type: 'MultiLineString',
          coordinates: [
            [
              [-77, 39],
              [-77, 39.1],
            ],
          ],
        },
        properties: { [CORRIDOR_KIND_PROPERTY]: UNATTRIBUTED_KIND },
      },
    ],
  }

  /** Real MapLibre has its layers and sources by the time `load` fires. */
  function loadStyle(map: MockMap): void {
    // Both waypoint ranks (#597): attachPoiFilter waits for the dot layer as
    // well as the pin one, so a stub holding only pins never filters at all.
    map.layerIds = [POI_DOT_LAYER_ID, POI_LAYER_ID, WARNING_LAYER_ID]
    map.sourceIds = [
      POI_SOURCE_ID,
      CLOSURE_SOURCE_ID,
      WARNING_SOURCE_ID,
      CORRIDOR_SOURCE_ID,
    ]
    map.emit('load')
  }

  it('registers the pin images once the style is up', async () => {
    render(<MapView {...PROPS} pois={POIS} />)
    const [map] = MockMap.live

    loadStyle(map)
    // The images are rasterised off the main thread now (#857,
    // map/poiIconImages.ts), so they land a beat after the attach rather than
    // inside it - see poiLayers.test.ts's `iconsBuilt` for why awaiting the
    // module's own promise is enough to order this after the registration.
    await poiIconImages()

    expect(map.images.has(poiIconId('water', 'high'))).toBe(true)
  })

  it('rasterises no pin at all for a map with no waypoints on it', async () => {
    // First run is this map (#857): the entry steps hold the waypoints back
    // (lib/useTrailData.ts), and 46 images nothing can ask for were 2,521 ms
    // of rasterising - measured 2026-08-20 on a 4x CPU throttle - in front of
    // the Skip button. The style's `match` arms are reached by a feature or
    // not at all, so a map with an empty source needs none of them.
    render(<MapView {...PROPS} pois={[]} />)
    const [map] = MockMap.live

    loadStyle(map)
    await poiIconImages()

    // Every pin image, not a sample of them - and not `images.size`, which
    // also counts the serious-warning pin (map/warningPin.ts), a single image
    // on its own clock.
    for (const { id } of buildPoiIcons()) expect(map.images.has(id)).toBe(false)
  })

  it('registers them as soon as the first waypoints arrive', async () => {
    const { rerender } = render(<MapView {...PROPS} pois={[]} />)
    const [map] = MockMap.live
    loadStyle(map)

    rerender(<MapView {...PROPS} pois={POIS} />)
    await poiIconImages()

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

    expect(map.filters.get(POI_LAYER_ID)).toEqual(poiFilter(new Set(['water'])))
  })

  it('filters out unverified pins when the legend asks for verified only', () => {
    render(<MapView {...PROPS} pois={POIS} verifiedOnly />)
    const [map] = MockMap.live

    loadStyle(map)

    expect(map.filters.get(POI_LAYER_ID)).toEqual(poiFilter(new Set(), true))
  })

  it('turns the "Verified?" filter back off without rebuilding the map', () => {
    // Same argument as the category toggle below: it is a filter change, and
    // rebuilding for it would drop the WebGL context mid-walk.
    const { rerender } = render(<MapView {...PROPS} pois={POIS} verifiedOnly />)
    const [map] = MockMap.live
    loadStyle(map)
    const builtInitially = MockMap.instances.length

    rerender(<MapView {...PROPS} pois={POIS} verifiedOnly={false} />)

    expect(MockMap.instances).toHaveLength(builtInitially)
    expect(map.filters.get(POI_LAYER_ID)).toEqual(poiFilter(new Set(), false))
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
    expect(map.filters.get(POI_LAYER_ID)).toEqual(poiFilter(new Set(['water'])))
  })

  it('rebuilds the source when a legend tap hides a site’s anchor', () => {
    // THE WIRING HALF OF #607, and a failure the other two files cannot see.
    // composeSites can be perfectly right about which member carries the pin
    // and the map still draws nothing, because the source is only pushed when
    // `pois` changes - and tapping a legend row does not change `pois`. What
    // this catches is exactly that missing effect dependency: a shelter hidden,
    // and its privy never offered a pin to be filtered.
    const site: MapPoint[] = [
      {
        id: 'shelter',
        type: 'shelter',
        lat: 39,
        lon: -77,
        confidence: 'high',
        siteId: 'site_1',
        siteRole: 'anchor',
      },
      {
        id: 'privy',
        type: 'privy',
        lat: 39.0004,
        lon: -77,
        confidence: 'high',
        siteId: 'site_1',
        siteRole: 'member',
      },
    ]
    const pinnedIds = (map: MockMap): unknown[] => {
      const data = map.sourceData.get(POI_SOURCE_ID) as {
        features: Array<{ id: unknown }>
      }
      return data.features.map((feature) => feature.id)
    }

    const { rerender } = render(
      <MapView {...PROPS} pois={site} hiddenTypes={new Set()} />,
    )
    const [map] = MockMap.live
    loadStyle(map)
    // The precondition, asserted rather than assumed: the privy is folded away
    // and the shelter's pin stands for both. That is #524 working.
    expect(pinnedIds(map)).toEqual(['shelter'])

    rerender(<MapView {...PROPS} pois={site} hiddenTypes={new Set(['shelter'])} />)

    expect(pinnedIds(map)).toEqual(['privy'])
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

  it('draws the corridor attribution it was given (#598)', () => {
    // The proof that the artifact reaches the canvas at all. Everything
    // between the bucket and here is tested on its own; this is the join.
    render(<MapView {...PROPS} corridor={CORRIDOR} />)
    const [map] = MockMap.live

    loadStyle(map)

    expect(map.sourceData.get(CORRIDOR_SOURCE_ID)).toEqual(CORRIDOR)
  })

  it('pushes an empty corridor rather than leaving a stale one drawn', () => {
    // A hiker who re-downloads from a release that publishes no attribution
    // must not keep looking at the previous release's grey runs.
    const { rerender } = render(<MapView {...PROPS} corridor={CORRIDOR} />)
    const [map] = MockMap.live
    loadStyle(map)

    rerender(<MapView {...PROPS} corridor={EMPTY_CORRIDOR} />)

    expect(map.sourceData.get(CORRIDOR_SOURCE_ID)).toEqual(EMPTY_CORRIDOR)
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

  it('leaves no style listeners behind after unmount', () => {
    const { unmount } = render(<MapView {...PROPS} pois={POIS} />)
    const [map] = MockMap.live

    unmount()

    // See the sibling above: 'styledata' is the live event (#175).
    expect(map.listenerCount('styledata')).toBe(0)
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
