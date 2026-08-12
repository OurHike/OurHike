import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, act, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MockMap, resetMapLibreMock } from '../test/mocks/maplibre-gl'
import { MapScreen } from './MapScreen'
import {
  mapCredits,
  OPENFREEMAP_CREDIT,
  OSM_CREDIT,
  USGS_TOPO_CREDIT,
} from '../map/credits'
import { closureFeatureCollection, CLOSURE_SOURCE_ID } from '../map/closureLayers'
import { warningFeatureCollection, WARNING_SOURCE_ID } from '../map/warningLayers'
import { HEALTHY, type SourceReport } from '../map/liveSourceHealth'

// WIREFRAMES.md's map screen, top to bottom: status strip, header, elevation
// ribbon, waypoint lanes, map canvas, tab bar - plus the legend sheet over the
// top of it. This covers the shell holding them together and the one thing
// that must be on screen no matter what: attribution. USGS topo is public
// domain, but OSM is ODbL and its credit is a licence condition, not a nicety,
// so it is asserted here rather than left to whichever component renders last.

vi.mock('maplibre-gl', () => import('../test/mocks/maplibre-gl'))
vi.mock('../map/protocol', () => ({
  PMTILES_SCHEME: 'pmtiles',
  registerPMTilesProtocol: vi.fn(),
}))

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
  activeTab: 'trail' as const,
  onSelectTab: vi.fn(),
  onOpenLegend: vi.fn(),
  onOpenSearch: vi.fn(),

  legendOpen: false,
  onCloseLegend: vi.fn(),
  bbox: { west: -78, south: 39, east: -77, north: 40 },
  viewportPoints: [
    { id: 'w1', type: 'water', lat: 39.5, lon: -77.5, confidence: 'high' as const },
  ],
  blazeCounts: [{ blaze: 'White', count: 12 }],
  hiddenTypes: new Set<string>(),
  onToggleType: vi.fn(),
  verifiedOnly: false,
  onToggleVerifiedOnly: vi.fn(),

  searchOpen: false,
  onCloseSearch: vi.fn(),
  searchablePois: [
    { id: 's1', name: 'Rocky Run Shelter', type: 'shelter', mile: 1043.2 },
  ],
  onSelectSearchResult: vi.fn(),

  selectedPoi: null,
  onSelectPoi: vi.fn(),
  onClosePoi: vi.fn(),

  elevation: {
    samples: [
      { mile: 1400, elevationFt: 1200 },
      { mile: 1410, elevationFt: 1800 },
    ],
    currentMile: 1405,
  },
  waypoints: {
    points: [{ id: 'w1', type: 'water', mile: 1402 }],
    startMile: 1400,
    endMile: 1410,
  },
}

beforeEach(() => {
  resetMapLibreMock()
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('MapScreen', () => {
  it('stacks the status strip, header, map and tab bar together', () => {
    render(<MapScreen {...PROPS} />)

    expect(screen.getByText(/12:00/)).toBeInTheDocument()
    expect(screen.getByRole('banner')).toBeInTheDocument()
    expect(screen.getByRole('region', { name: /trail map/i })).toBeInTheDocument()
    expect(screen.getByRole('tablist')).toBeInTheDocument()
  })

  it('always renders the attribution - OSM credit is an ODbL condition, not a nicety', () => {
    render(<MapScreen {...PROPS} background="usgs_topo_offline" />)

    expect(screen.getByText(OSM_CREDIT, { exact: false })).toBeInTheDocument()
  })

  it('credits the extra licences the live background brings with it', () => {
    // The live sheet adds two more conditions of use - OpenFreeMap's terms for
    // the hosting and AWS Terrain Tiles' attribution requirement for the
    // elevation - so the corner has to grow when the background changes. A
    // fixed string here would have gone quietly out of date the day the
    // default flipped.
    render(<MapScreen {...PROPS} background="hiking_topo_live" />)

    for (const credit of mapCredits({ background: 'hiking_topo_live' })) {
      expect(screen.getByText(credit, { exact: false })).toBeInTheDocument()
    }
  })

  it('credits the live sheet by default, because that is the default background', () => {
    render(<MapScreen {...PROPS} />)

    expect(screen.getByText(OPENFREEMAP_CREDIT, { exact: false })).toBeInTheDocument()
  })

  it('does not credit the USGS survey on a phone that has none of it', () => {
    // The corner used to name USGS US Topo unconditionally, because the string
    // was composed from what the app CAN draw. On a fresh install that is a
    // credit for a 314 MB archive nobody has downloaded, printed over a map
    // drawn entirely from other people's tiles.
    render(<MapScreen {...PROPS} hasRasterArchive={false} />)

    expect(screen.queryByText(USGS_TOPO_CREDIT, { exact: false })).not.toBeInTheDocument()
  })

  it('credits the USGS survey once the corridor raster is on the phone', () => {
    render(<MapScreen {...PROPS} hasRasterArchive />)

    expect(screen.getByText(USGS_TOPO_CREDIT, { exact: false })).toBeInTheDocument()
  })

  it('never says one credit twice, however the background and the download line up', () => {
    // The bug in its most visible form: two composed strings each correctly
    // named OpenStreetMap, so the live corner printed it twice.
    render(<MapScreen {...PROPS} background="hiking_topo_live" hasRasterArchive />)

    expect(screen.getAllByText(OSM_CREDIT, { exact: false })).toHaveLength(1)
  })

  it('surfaces the offline state it was given', () => {
    render(<MapScreen {...PROPS} />)

    expect(screen.getByText(/offline/i)).toBeInTheDocument()
  })

  it('passes tab selection up to its owner', async () => {
    const user = userEvent.setup()
    render(<MapScreen {...PROPS} />)

    await user.click(screen.getByRole('tab', { name: 'More' }))

    expect(PROPS.onSelectTab).toHaveBeenCalledWith('more')
  })

  it('slots the elevation ribbon and waypoint lanes above the canvas', () => {
    render(<MapScreen {...PROPS} />)

    expect(screen.getByRole('img', { name: /elevation profile/i })).toBeInTheDocument()
    expect(screen.getByTestId('lane-water')).toBeInTheDocument()
  })

  it('omits the ribbon and lanes rather than showing empty ones when there is no data', () => {
    // An empty ribbon reads as "nothing ahead of you", which is a different and
    // much worse claim than "we don't have the profile for this stretch."
    render(<MapScreen {...PROPS} elevation={undefined} waypoints={undefined} />)

    expect(
      screen.queryByRole('img', { name: /elevation profile/i }),
    ).not.toBeInTheDocument()
    expect(screen.queryByTestId('lane-water')).not.toBeInTheDocument()
  })

  it('keeps the legend sheet closed until it is asked for', () => {
    render(<MapScreen {...PROPS} />)

    expect(screen.queryByRole('dialog', { name: /legend/i })).not.toBeInTheDocument()
  })

  it('shows the legend sheet over the map once open', () => {
    render(<MapScreen {...PROPS} legendOpen />)

    expect(screen.getByRole('dialog', { name: /legend/i })).toBeInTheDocument()
  })

  it('keeps search out of the way until the header asks for it', () => {
    render(<MapScreen {...PROPS} />)

    expect(screen.queryByRole('searchbox')).not.toBeInTheDocument()
  })

  it('lets search take over once opened', () => {
    render(<MapScreen {...PROPS} searchOpen />)

    expect(screen.getByRole('searchbox')).toBeInTheDocument()
  })

  it('wires the header buttons to the legend and search handlers', async () => {
    const user = userEvent.setup()
    render(<MapScreen {...PROPS} />)

    await user.click(screen.getByRole('button', { name: /legend/i }))
    await user.click(screen.getByRole('button', { name: /search/i }))

    expect(PROPS.onOpenLegend).toHaveBeenCalledTimes(1)
    expect(PROPS.onOpenSearch).toHaveBeenCalledTimes(1)
  })

  it('shows no waypoint card until a pin has been tapped', () => {
    render(<MapScreen {...PROPS} />)

    expect(screen.queryByRole('dialog', { name: /waypoint/i })).not.toBeInTheDocument()
  })

  it('puts the tapped pin’s detail over the map', () => {
    render(
      <MapScreen
        {...PROPS}
        selectedPoi={{
          id: 'atc_shelters:abc',
          name: 'Rocky Run Shelter',
          type: 'shelter',
          lat: 39.4,
          lon: -77.6,
          confidence: 'high',
          mile: 1043.2,
        }}
      />,
    )

    expect(screen.getByRole('dialog', { name: /waypoint/i })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Rocky Run Shelter' })).toBeInTheDocument()
  })

  it('hands the card the live map, so it anchors to the pin it describes', () => {
    // The shell above owns the POI data and MapView owns the canvas; this is
    // the screen that has to introduce them. A card that never projected the
    // POI's coordinates would render docked at the canvas origin - the exact
    // bottom-anchored posture this card replaced.
    render(
      <MapScreen
        {...PROPS}
        selectedPoi={{
          id: 'atc_shelters:abc',
          name: 'Rocky Run Shelter',
          type: 'shelter',
          lat: 39.4,
          lon: -77.6,
          confidence: 'high',
          mile: 1043.2,
        }}
      />,
    )

    expect(MockMap.live).toHaveLength(1)
    expect(MockMap.live[0].projectCalls).toContainEqual([-77.6, 39.4])
    expect(screen.getByRole('dialog', { name: /waypoint/i }).style.transform).not.toBe('')
  })

  it('carries the map’s source reports up to the shell', () => {
    // Half of a path that used to end here. This screen observed the error
    // and decided what it meant; since #334 it does neither, because the
    // downloads window needs the same fact and opens over the More tab where
    // this screen is not rendered at all. What is left is the wiring, and the
    // wiring is worth a test: an unpassed prop is exactly how the flag
    // reached nobody before #314.
    const reports: SourceReport[] = []
    const { unmount } = render(
      <MapScreen
        {...PROPS}
        online
        onLiveSourceHealth={(report) => reports.push(report)}
      />,
    )

    act(() => {
      MockMap.live[0].emit('error', {
        sourceId: 'osm',
        error: new Error('Failed to fetch'),
      })
    })

    expect(reports).toEqual([
      {
        unreachable: { basemap: true, elevation: false, archive: false },
        drew: HEALTHY,
        withdrawn: false,
      },
    ])

    // And the withdrawal on the way out, flagged as one: the shell remembers
    // failures past this screen, so it has to know that this `HEALTHY` is the
    // map leaving rather than the sheet arriving.
    unmount()

    expect(reports.at(-1)).toEqual({
      unreachable: HEALTHY,
      drew: HEALTHY,
      withdrawn: true,
    })
  })

  it('renders the background problem the shell hands it', () => {
    // The other half. This screen no longer works out what a failing source
    // means - it is told, and it shows it.
    render(<MapScreen {...PROPS} online backgroundProblem="live-unreachable" />)

    expect(screen.getByText(/no live map/i)).toBeInTheDocument()
  })

  it('says on the map screen when Data Saver is holding the live sheet back', () => {
    render(<MapScreen {...PROPS} backgroundOverride="data-saver" />)

    expect(screen.getByText(/data saver/i)).toBeInTheDocument()
  })

  it('puts the background choice in the legend, one tap from the map', () => {
    // It used to live only in Settings, three taps away behind a select. The
    // moment someone wants to change the background is the moment the map is
    // not showing what they expected, which is the worst moment to send them
    // hunting through a settings screen.
    render(
      <MapScreen
        {...PROPS}
        legendOpen
        backgroundChoice="usgs_topo_offline"
        onChangeBackground={vi.fn()}
      />,
    )

    const legend = screen.getByRole('dialog', { name: /legend/i })
    expect(within(legend).getByRole('radio', { name: /live/i })).toBeInTheDocument()
    expect(within(legend).getByRole('radio', { name: /downloaded/i })).toBeChecked()
  })

  it('reports a background change from the legend up to its owner', async () => {
    const user = userEvent.setup()
    const onChangeBackground = vi.fn()
    render(
      <MapScreen
        {...PROPS}
        legendOpen
        backgroundChoice="usgs_topo_offline"
        onChangeBackground={onChangeBackground}
      />,
    )

    await user.click(screen.getByRole('radio', { name: /live/i }))

    expect(onChangeBackground).toHaveBeenCalledWith('hiking_topo_live')
  })

  it('carries the way to the download, which is the only one left on this screen', async () => {
    // The Downloads tab is gone (chrome/tabs.ts). If this link does not reach
    // the shell, a hiker on the map has no route to the download at all.
    const user = userEvent.setup()
    const onOpenDownloads = vi.fn()
    render(
      <MapScreen
        {...PROPS}
        legendOpen
        backgroundChoice="usgs_topo_offline"
        onChangeBackground={vi.fn()}
        onOpenDownloads={onOpenDownloads}
      />,
    )

    await user.click(screen.getByRole('button', { name: /choose what to download/i }))

    expect(onOpenDownloads).toHaveBeenCalledTimes(1)
  })

  it('draws no picker when the shell has nowhere to write the choice', () => {
    // The legend is rendered in tests and stories without a shell behind it,
    // and a control that silently discards what it is told is worse than one
    // that is not there.
    render(<MapScreen {...PROPS} legendOpen />)

    expect(screen.queryByRole('radio', { name: /live/i })).not.toBeInTheDocument()
  })
})

// --- The safety alert strip (#232) ---------------------------------------
//
// Above the map, because a hiker who is walking has not opened anything: a
// closure that only appears on tapping a red band is a closure they walk
// into.

describe('MapScreen safety alerts', () => {
  it('says nothing when there is nothing to say', () => {
    render(<MapScreen {...PROPS} />)

    expect(screen.queryByRole('alert')).toBe(null)
  })

  it('shows a closure ahead', () => {
    render(
      <MapScreen {...PROPS} closureAhead="Trail closed 5.0 mi ahead · Storm damage" />,
    )

    expect(screen.getByRole('alert')).toHaveTextContent('Trail closed 5.0 mi ahead')
  })

  it('shows serious warnings on the route', () => {
    render(<MapScreen {...PROPS} warningsAhead="2 serious warnings on your route" />)

    expect(screen.getByRole('alert')).toHaveTextContent(
      '2 serious warnings on your route',
    )
  })

  it('shows both at once rather than picking one', () => {
    // A closure and a bear are different problems, and neither substitutes
    // for the other.
    render(
      <MapScreen
        {...PROPS}
        closureAhead="Trail closed 5.0 mi ahead · Storm damage"
        warningsAhead="1 serious warning on your route"
      />,
    )

    const alert = screen.getByRole('alert')
    expect(alert).toHaveTextContent('Trail closed 5.0 mi ahead')
    expect(alert).toHaveTextContent('1 serious warning on your route')
  })

  it('keeps the status strip above it, because the two are read together', () => {
    // The strip's sync age is the only thing separating "the way ahead is
    // clear" from "we could not check" - an alert area that appeared above
    // it would be a claim with no freshness attached.
    const { container } = render(
      <MapScreen {...PROPS} closureAhead="Trail closed 5.0 mi ahead · Storm damage" />,
    )

    const strip = container.querySelector('.status-strip')
    const alerts = container.querySelector('.map-screen__alerts')
    expect(strip).not.toBeNull()
    expect(alerts).not.toBeNull()
    expect(strip!.compareDocumentPosition(alerts!)).toBe(Node.DOCUMENT_POSITION_FOLLOWING)
  })
})

// --- The same two facts on the canvas -------------------------------------
//
// Four props rather than two, and the reason is in MapScreenProps: a banner
// says what is AHEAD of a hiker walking a known direction, and the canvas
// draws what is THERE. Tying them together would leave the map blank until
// the direction tracker had made up its mind.

describe('MapScreen safety overlays', () => {
  function loadStyle(map: MockMap): void {
    map.sourceIds = [CLOSURE_SOURCE_ID, WARNING_SOURCE_ID]
    map.emit('load')
  }

  it('hands the closure bands to the canvas', () => {
    const closures = [{ id: 'c1', lines: [[[-77.1, 39.3] as [number, number]]] }]

    render(<MapScreen {...PROPS} closures={closures} />)
    const [map] = MockMap.live
    loadStyle(map)

    expect(map.sourceData.get(CLOSURE_SOURCE_ID)).toEqual(
      closureFeatureCollection(closures),
    )
  })

  it('hands the warning pins to the canvas', () => {
    const warnings = [{ id: 'r1', lon: -77.2, lat: 39.4 }]

    render(<MapScreen {...PROPS} warnings={warnings} />)
    const [map] = MockMap.live
    loadStyle(map)

    expect(map.sourceData.get(WARNING_SOURCE_ID)).toEqual(
      warningFeatureCollection(warnings),
    )
  })

  it('draws a closure the banner is silent about', () => {
    // The case the four props exist for. `closureAhead` is null before the
    // direction tracker settles - and before then the band is the only thing
    // telling a hiker the trail is shut.
    const closures = [{ id: 'c1', lines: [[[-77.1, 39.3] as [number, number]]] }]

    render(<MapScreen {...PROPS} closures={closures} closureAhead={null} />)
    const [map] = MockMap.live
    loadStyle(map)

    expect(screen.queryByRole('alert')).toBe(null)
    expect(
      (map.sourceData.get(CLOSURE_SOURCE_ID) as { features: unknown[] }).features,
    ).toHaveLength(1)
  })
})
