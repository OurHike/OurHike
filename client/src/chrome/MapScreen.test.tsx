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
  mile: 1407.2,
  direction: 'NOBO' as const,
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

  it('carries a failed live background from the map up into the strip', () => {
    // The whole path in one test: MapLibre reports a source error, the map
    // view observes it, and the strip says so. PROPS is offline by default,
    // so `online` is forced here - the point of this flag is the case where
    // the phone believes it has a connection and the tiles never come.
    render(<MapScreen {...PROPS} online />)

    expect(screen.queryByText(/no live map/i)).not.toBeInTheDocument()

    act(() => {
      MockMap.live[0].emit('error', {
        sourceId: 'osm',
        error: new Error('Failed to fetch'),
      })
    })

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

describe('the safety layers (#232)', () => {
  // WIREFRAMES.md §7 and §8: the banners under the header, and the sheets a
  // tap opens. The bands and pins themselves are map layers, tested with the
  // style and the attach modules - what this screen owns is saying the
  // notices and mounting the sheets.

  const CLOSURE_DETAIL = {
    id: 'c1',
    reason_type: 'storm_damage' as const,
    note: null,
    status: 'closed' as const,
    start_mile_marker: 1408.6,
    end_mile_marker: 1411.0,
    closed_since: null,
    expected_reopen: null,
    marked_by: null,
    reroute_url: null,
  }

  const WARNING_DETAIL = {
    id: 'r1',
    type: 'animals',
    note: 'A bear has been taking hung food bags overnight.',
    mile: 1045.2,
    confirmedAt: null,
    corroboration: null,
    aboutAPerson: false,
    reporterName: null,
  }

  it('says the closure-ahead banner it was worded', () => {
    render(
      <MapScreen
        {...PROPS}
        closureNotice="Trail closed 1.4 mi ahead · Storm damage · mi 1,408.6 – 1,411.0"
      />,
    )

    expect(screen.getByText(/trail closed 1\.4 mi ahead/i)).toBeInTheDocument()
  })

  it('shows no banner strip at all on a trail with nothing to say', () => {
    render(<MapScreen {...PROPS} />)

    expect(screen.queryByText(/trail closed/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/on your route/i)).not.toBeInTheDocument()
  })

  it('offers See and Dismiss on the route-warnings banner', async () => {
    const user = userEvent.setup()
    const onSee = vi.fn()
    const onDismiss = vi.fn()
    render(
      <MapScreen
        {...PROPS}
        warningNotice={{
          text: '2 serious warnings on your route',
          onSee,
          onDismiss,
        }}
      />,
    )

    expect(screen.getByText(/2 serious warnings on your route/i)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /see/i }))
    await user.click(screen.getByRole('button', { name: /dismiss/i }))

    expect(onSee).toHaveBeenCalled()
    expect(onDismiss).toHaveBeenCalled()
  })

  it('mounts the closure sheet for the tapped band', () => {
    render(
      <MapScreen
        {...PROPS}
        selectedClosure={CLOSURE_DETAIL}
        onCloseClosure={vi.fn()}
        closuresSyncedAt={new Date('2026-07-26T12:00:00')}
      />,
    )

    const sheet = screen.getByRole('dialog', { name: /trail closure/i })
    expect(within(sheet).getByText(/storm damage/i)).toBeInTheDocument()
    // The sync age is the closures fetch, not the outbox flush - three days
    // against PROPS.time, not the three hours lastSyncedAt would say.
    expect(within(sheet).getByText(/3d ago/)).toBeInTheDocument()
  })

  it('mounts the warning sheet for the tapped pin', () => {
    render(
      <MapScreen {...PROPS} selectedWarning={WARNING_DETAIL} onCloseWarning={vi.fn()} />,
    )

    const sheet = screen.getByRole('dialog', { name: /serious warning/i })
    expect(within(sheet).getByText(/bear/i)).toBeInTheDocument()
  })

  it('mounts no sheet until something is tapped', () => {
    render(<MapScreen {...PROPS} />)

    expect(screen.queryByRole('dialog', { name: /closure/i })).not.toBeInTheDocument()
    expect(
      screen.queryByRole('dialog', { name: /serious warning/i }),
    ).not.toBeInTheDocument()
  })
})
