// The laptop layout and the phone layout draw waypoints the same way (#1688).
//
// The maintainer, 2026-09-26, once #1681 had put the small pins back: "the
// look and feel needs to be aligned between the two. make a test to keep both
// aligned." Asked which two, with frames of each, they chose the app on a
// phone and the app in a laptop browser - ourhike.org/app above
// lib/useDesktop.ts's DESKTOP_MIN_WIDTH. (The iOS and Android shells load the
// same client/dist, capacitor.config.ts's `webDir`, so the phone half covers
// them too.)
//
// TODAY THEY MATCH BY CONSTRUCTION, and this file is what keeps it that way.
// buildMapStyle takes no layout input, and MapScreen hands <MapView> the same
// waypoint props in both layouts; the only layout-dependent inputs to the map
// are camera ones (`chromeInsets`, `boundsPadding`). Nothing checked any of
// that. A desktop-only pin size, filter, collision setting or pin artwork
// behind `useDesktop()` would have shipped with every waypoint test green,
// because every one of them builds the layers directly and never asks which
// layout it is in.
//
// Two halves:
//
//  1. RENDER BOTH LAYOUTS AND COMPARE WHAT THE MAP WAS GIVEN - the waypoint
//     layers' specs, the filters and layout writes made to them, the data in
//     the waypoint source, and the pin images registered. Everything that
//     decides how a waypoint is drawn, taken from one MapScreen render per
//     layout, so a fork anywhere between the shell and the map shows up.
//  2. KEEP THE LAYOUT OUT OF client/src/map/. A module there that reads the
//     breakpoint is exactly how the two would drift, and it would be a fork
//     half 1 only catches for the props this fixture happens to pass.

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join, relative } from 'node:path'
import { act, cleanup, render } from '@testing-library/react'
import type {
  LayerSpecification,
  StyleSpecification,
} from '@maplibre/maplibre-gl-style-spec'
import { MockMap, resetMapLibreMock } from '../test/mocks/maplibre-gl'
import { stubDesktop } from '../test/appHarness'
import { loadMapEngine } from '../map/mapEngineLoader'
import { poiIconImages } from '../map/poiIconImages'
import { POI_LAYER_ID, POI_DOT_LAYER_ID, POI_SOURCE_ID } from '../map/poiLayers'
import { WAYPOINT_LAYER_IDS } from '../map/waypointLayerVisibility'
import { DESKTOP_MEDIA_QUERY } from '../lib/useDesktop'
import { MapScreen } from './MapScreen'

vi.mock('maplibre-gl', () => import('../test/mocks/maplibre-gl'))
vi.mock('../map/protocol', () => ({
  PMTILES_SCHEME: 'pmtiles',
  registerPMTilesProtocol: vi.fn(),
}))

/** Every category, a low-confidence pin and a ringed spring, so the
 *  comparison covers the size tiers, both rims, the ring and the priority
 *  order rather than one water point. */
const WAYPOINTS = [
  { id: 'shelter', type: 'shelter', lat: 39.5, lon: -77.5, confidence: 'high' as const },
  {
    id: 'privy',
    type: 'privy',
    lat: 39.5001,
    lon: -77.5001,
    confidence: 'high' as const,
  },
  {
    id: 'campsite',
    type: 'campsite',
    lat: 39.52,
    lon: -77.52,
    confidence: 'low' as const,
  },
  { id: 'spring', type: 'water', lat: 39.54, lon: -77.54, confidence: 'high' as const },
  {
    id: 'trailhead',
    type: 'trailhead',
    lat: 39.56,
    lon: -77.56,
    confidence: 'high' as const,
  },
  { id: 'lot', type: 'parking', lat: 39.58, lon: -77.58, confidence: 'high' as const },
  { id: 'town', type: 'resupply', lat: 39.6, lon: -77.6, confidence: 'high' as const },
  { id: 'vista', type: 'viewpoint', lat: 39.62, lon: -77.62, confidence: 'low' as const },
]

const PROPS = {
  topoArchiveUrl: 'pmtiles://ourhike-corridor',
  trailsUrl: '/data/trails.geojson',
  trailName: 'Appalachian Trail',
  state: 'Virginia',
  position: 'mi 1,407.2 · NOBO',
  time: new Date('2026-07-29T12:00:00'),
  online: false,
  hasGpsFix: true,
  lastSyncedAt: new Date('2026-07-29T09:00:00'),
  activeTab: 'map' as const,
  onSelectTab: vi.fn(),
  onOpenLegend: vi.fn(),
  onOpenSearch: vi.fn(),
  legendOpen: false,
  onCloseLegend: vi.fn(),
  bbox: { west: -78, south: 39, east: -77, north: 40 },
  viewportPoints: WAYPOINTS,
  // The never-confirmed spring wears the water invite, the one ring a map
  // carries on day one (lib/stalenessDisplay.ts, #256).
  pinCondition: (poiId: string) =>
    poiId === 'spring'
      ? { ring: 'faint-invite', faded: false }
      : { ring: 'none', faded: false },
  hiddenTypes: new Set<string>(['viewpoint']),
  onToggleType: vi.fn(),
  verifiedOnly: false,
  onToggleVerifiedOnly: vi.fn(),
  searchOpen: false,
  onCloseSearch: vi.fn(),
  searchablePois: [],
  onSelectSearchResult: vi.fn(),
  selectedPoi: null,
  onSelectPoi: vi.fn(),
  onClosePoi: vi.fn(),
}

/** A matchMedia that answers the desktop breakpoint `desktop` and every
 *  other question no - so the phone run goes through the same code path as
 *  the laptop run rather than through jsdom's missing matchMedia. */
function stubPhone(): void {
  vi.stubGlobal(
    'matchMedia',
    vi.fn((query: string) => ({
      matches: false,
      media: query,
      addEventListener: () => {},
      removeEventListener: () => {},
    })),
  )
}

interface DrawnWaypoints {
  layers: LayerSpecification[]
  source: unknown
  filters: Record<string, unknown>
  layoutWrites: Array<[string, unknown]>
  paintWrites: Array<[string, unknown]>
  data: unknown
  images: Array<[string, unknown]>
}

const isWaypointKey = (key: string) =>
  WAYPOINT_LAYER_IDS.some((id) => key.startsWith(`${id}/`))

/** Everything that decides how a waypoint is drawn, read off one render. */
async function drawnIn(layout: 'phone' | 'laptop'): Promise<DrawnWaypoints> {
  if (layout === 'laptop') stubDesktop()
  else stubPhone()
  expect(window.matchMedia(DESKTOP_MEDIA_QUERY).matches).toBe(layout === 'laptop')

  render(<MapScreen {...PROPS} />)
  const [map] = MockMap.live
  map.styleLoaded = true
  map.emit('load')
  // The pins are rasterised through a promise (#857) and registered once it
  // resolves; wait for that rather than for a timer.
  await act(async () => {
    await poiIconImages()
  })

  const style = map.options.style as StyleSpecification
  const drawn: DrawnWaypoints = {
    layers: style.layers.filter((layer) => WAYPOINT_LAYER_IDS.includes(layer.id)),
    source: style.sources[POI_SOURCE_ID],
    filters: Object.fromEntries(
      WAYPOINT_LAYER_IDS.map((id) => [id, map.filters.get(id)]),
    ),
    layoutWrites: [...map.layoutProperties].filter(([key]) => isWaypointKey(key)),
    paintWrites: [...map.paintProperties].filter(([key]) => isWaypointKey(key)),
    data: map.sourceData.get(POI_SOURCE_ID),
    images: [...map.imageOptions]
      .filter(([id]) => id.startsWith('poi-'))
      .sort(([a], [b]) => a.localeCompare(b)),
  }
  cleanup()
  vi.unstubAllGlobals()
  return drawn
}

beforeEach(async () => {
  resetMapLibreMock()
  await loadMapEngine()
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  vi.clearAllMocks()
})

describe('the laptop layout draws waypoints exactly as the phone does (#1688)', () => {
  it('gives the map the same waypoint layers, filters, data and pin images in both layouts', async () => {
    const phone = await drawnIn('phone')
    resetMapLibreMock()
    const laptop = await drawnIn('laptop')

    expect(laptop).toEqual(phone)
  })

  it('compares something real, not two empty maps', async () => {
    // The equality above passes just as well if neither render reached the
    // map. So the phone's half is held to what #1681 shipped: both ranks, the
    // collision engine on, the legend's hidden set applied, every waypoint in
    // the source and the pins registered.
    const phone = await drawnIn('phone')
    const ids = phone.layers.map((layer) => layer.id)
    expect(ids).toContain(POI_LAYER_ID)
    expect(ids).toContain(POI_DOT_LAYER_ID)

    const pins = phone.layers.find((layer) => layer.id === POI_LAYER_ID)
    expect((pins?.layout ?? {}) as Record<string, unknown>).toMatchObject({
      'icon-allow-overlap': false,
    })
    expect(JSON.stringify(phone.filters[POI_LAYER_ID])).toContain('viewpoint')

    const features = (
      phone.data as { features: Array<{ properties: Record<string, unknown> }> }
    ).features
    // One feature per waypoint (none carries a site id, so nothing folds),
    // the hidden viewpoint included: hiding is the filter's job, not the
    // data's.
    expect(features).toHaveLength(WAYPOINTS.length)
    expect(features.some((f) => f.properties.staleness_ring === 'faint-invite')).toBe(
      true,
    )
    expect(phone.images.length).toBeGreaterThan(0)
  })
})

describe('the waypoint layers never ask which layout they are in (#1688)', () => {
  /** Every non-test source file under client/src/map/. */
  function mapModules(dir = join(__dirname, '..', 'map')): string[] {
    return readdirSync(dir).flatMap((name) => {
      const path = join(dir, name)
      if (statSync(path).isDirectory()) return mapModules(path)
      if (!/\.(ts|tsx)$/.test(name) || /\.test\.tsx?$/.test(name)) return []
      return [path]
    })
  }

  it('keeps the desktop breakpoint out of client/src/map/', () => {
    // A layout fork inside the map is the one the render comparison above
    // would only catch for the props its fixture passes. So the map does not
    // get to ask: layout lives in the shell (lib/useDesktop.ts, MapScreen),
    // which may move the camera and the chrome but hands the map the same
    // waypoints either way.
    const readsLayout =
      /\buseDesktop\b|\bDESKTOP_MEDIA_QUERY\b|\bDESKTOP_MIN_WIDTH\b|min-width:\s*900px/
    const modules = mapModules()
    expect(modules.length).toBeGreaterThan(20)

    const offenders = modules
      .filter((path) => readsLayout.test(readFileSync(path, 'utf8')))
      .map((path) => relative(join(__dirname, '..'), path))
    expect(offenders).toEqual([])
  })
})
