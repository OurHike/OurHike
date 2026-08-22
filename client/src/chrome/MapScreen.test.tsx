import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, act, fireEvent, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MockMap, ScaleControl, resetMapLibreMock } from '../test/mocks/maplibre-gl'
import { loadMapEngine } from '../map/mapEngineLoader'
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

  // The fix-anchored ribbon, which is what this screen's fixture has always
  // been - now arriving with the `source` and `domain` lib/ribbonView.ts
  // resolves (#910), because those decide which framing buttons appear.
  elevation: {
    samples: [
      { mile: 1400, elevationFt: 1200 },
      { mile: 1410, elevationFt: 1800 },
    ],
    currentMile: 1405,
    source: 'ahead' as const,
    domain: { startMile: 1400, endMile: 1410 },
  },
  waypoints: {
    points: [{ id: 'w1', type: 'water', mile: 1402 }],
    startMile: 1400,
    endMile: 1410,
  },
}

beforeEach(async () => {
  resetMapLibreMock()
  // The map engine arrives through `import()` in production (#722); primed
  // here so every render below builds its map synchronously, exactly as it did
  // before the deferral. After the test file's `vi.mock('maplibre-gl', ...)`,
  // so the engine closes over the mock rather than the real library.
  await loadMapEngine()
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

    await user.click(screen.getByRole('tab', { name: 'Settings' }))

    expect(PROPS.onSelectTab).toHaveBeenCalledWith('more')
  })

  it('slots the elevation ribbon and waypoint lanes above the canvas', () => {
    render(<MapScreen {...PROPS} />)

    expect(screen.getByRole('img', { name: /elevation profile/i })).toBeInTheDocument()
    expect(screen.getByTestId('lane-water')).toBeInTheDocument()
  })

  // #619. One preference, one prop, two consumers. The failure this guards is
  // not a crash: it is a canvas whose scale bar and contour interval read in
  // metres under a ribbon still labelled in feet, which nothing but a test
  // holding both at once would catch - each half is right on its own.
  it('sends one unit preference to the canvas and to the ribbon over it', () => {
    render(<MapScreen {...PROPS} units="metric" />)

    const [map] = MockMap.live
    const scale = map.controls
      .map((c) => c.control)
      .find((c) => c instanceof ScaleControl)
    expect(scale?.options?.unit).toBe('metric')

    // The ribbon's low mark: 1,200 ft is 366 m.
    expect(screen.getByText(/366 m/)).toBeInTheDocument()
  })

  it('draws both in feet for a hiker who has not changed the default', () => {
    render(<MapScreen {...PROPS} />)

    const [map] = MockMap.live
    const scale = map.controls
      .map((c) => c.control)
      .find((c) => c instanceof ScaleControl)
    expect(scale?.options?.unit).toBe('imperial')

    expect(screen.getByText(/1,200 ft/)).toBeInTheDocument()
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

  it('renders the removed-waypoint card in the slot the waypoint card would have used', () => {
    // #831: the card for a place that no longer exists stands in for the one
    // that would have opened, because that is exactly what it replaces — a
    // selection that renders NOTHING today.
    render(
      <MapScreen
        {...PROPS}
        removedPoiCard={<div role="dialog" aria-label="Removed waypoint" />}
      />,
    )

    expect(screen.getByRole('dialog', { name: /removed waypoint/i })).toBeInTheDocument()
    expect(screen.queryByRole('dialog', { name: /^waypoint$/i })).not.toBeInTheDocument()
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

// --- The count over the canvas (#528) -------------------------------------
//
// One arithmetic, two places it is said: this figure and the legend's own
// headline come from the same function with the same arguments, and what these
// assert is that this call site passes them - the arithmetic itself is pinned
// in lib/legendContents.test.ts.

describe('MapScreen dropped-waypoint count', () => {
  const point = (id: string, type: string) => ({
    id,
    type,
    lat: 39.5,
    lon: -77.5,
    confidence: 'high' as const,
  })

  it('counts only the categories the hiker is showing, as the panel does', () => {
    // Privy hidden: off the map by the hiker's own filter, not by collision,
    // so it belongs in neither half. Computed without `hiddenTypes` this read
    // "1 of 3" beside a panel saying "1 of 2" - the exact disagreement passing
    // the same arguments to one function exists to prevent (#777).
    render(
      <MapScreen
        {...PROPS}
        viewportPoints={[
          point('w1', 'water'),
          point('w2', 'water'),
          point('p1', 'privy'),
        ]}
        drawnCounts={new Map([['water', 1]])}
        hiddenTypes={new Set(['privy'])}
      />,
    )

    expect(screen.getByText('1 of 2 waypoints fit')).toBeInTheDocument()
  })

  it('says nothing once everything still shown is drawn', () => {
    // Counting the hidden privy kept `drawn < present` true at every camera,
    // parking this line on the map for as long as a filter was on (#777).
    render(
      <MapScreen
        {...PROPS}
        viewportPoints={[point('w1', 'water'), point('p1', 'privy')]}
        drawnCounts={new Map([['water', 1]])}
        hiddenTypes={new Set(['privy'])}
      />,
    )

    expect(screen.queryByText(/waypoints fit/)).not.toBeInTheDocument()
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

  // The third row (#485). A region-wide advisory is a standing condition, not a
  // next action, so it appears without competing for the line above it.
  it('shows a broad advisory under the closure rather than instead of it', () => {
    // THE CASE #485 REPORTS. Ranked into one line, the advisory scored "inside"
    // and the nine-mile closure three miles ahead never appeared at all.
    const { container } = render(
      <MapScreen
        {...PROPS}
        closureAhead="Trail closed 3.0 mi ahead · Storm damage · mi 245.0 – 254.0"
        advisoryAhead="Advisory along 398 mi of trail · Storm damage · mi 239.4 – 637.8"
      />,
    )

    const alert = screen.getByRole('alert')
    expect(alert).toHaveTextContent('Trail closed 3.0 mi ahead')
    expect(alert).toHaveTextContent('Advisory along 398 mi of trail')

    // Order is the point, not merely presence: the actionable line is read
    // first on a screen glanced at while walking.
    const closure = container.querySelector('.map-screen__alert--closure')
    const advisory = container.querySelector('.map-screen__alert--advisory')
    expect(closure!.compareDocumentPosition(advisory!)).toBe(
      Node.DOCUMENT_POSITION_FOLLOWING,
    )
  })

  it('shows an advisory on its own when nothing specific is ahead', () => {
    // Otherwise the fix would trade one silence for another: a hiker inside an
    // advisory on an otherwise clear stretch has to still be told.
    render(
      <MapScreen
        {...PROPS}
        advisoryAhead="Advisory along 398 mi of trail · Storm damage · mi 239.4 – 637.8"
      />,
    )

    expect(screen.getByRole('alert')).toHaveTextContent('Advisory along 398 mi of trail')
  })

  it('marks the advisory as its own kind of row', () => {
    // The class is what makes it quieter than the two above it (chrome.css).
    // Same colour and size - weight only - because this is still a safety line
    // on a screen read in direct sun.
    const { container } = render(
      <MapScreen {...PROPS} advisoryAhead="Advisory along 398 mi of trail" />,
    )

    expect(container.querySelector('.map-screen__alert--advisory')).not.toBeNull()
    expect(container.querySelector('.map-screen__alert--closure')).toBeNull()
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

describe('the way to every ATC notice, from the legend (#687)', () => {
  // This used to be a permanent button on this screen. It moved into the
  // legend - chrome/Legend.test.tsx covers the row itself, so what matters
  // here is only that MapScreen hands the count and the handler on honestly.

  it('is not there when the app holds no ATC notices', () => {
    render(<MapScreen {...PROPS} legendOpen />)

    expect(screen.queryByRole('button', { name: /ATC trail update/ })).toBe(null)
  })

  it('reaches the legend once open', () => {
    render(
      <MapScreen {...PROPS} legendOpen atcNoticeCount={6} onOpenAtcNotices={vi.fn()} />,
    )

    const legend = screen.getByRole('dialog', { name: /legend/i })
    expect(
      within(legend).getByRole('button', { name: 'Read all 6 ATC trail updates' }),
    ).toBeInTheDocument()
  })

  it('counts one notice without pluralising it', () => {
    render(
      <MapScreen {...PROPS} legendOpen atcNoticeCount={1} onOpenAtcNotices={vi.fn()} />,
    )

    const legend = screen.getByRole('dialog', { name: /legend/i })
    expect(
      within(legend).getByRole('button', { name: 'Read the 1 ATC trail update' }),
    ).toBeInTheDocument()
  })

  it('reports the tap up to the shell, which owns whether the list is open', async () => {
    const onOpenAtcNotices = vi.fn()
    render(
      <MapScreen
        {...PROPS}
        legendOpen
        atcNoticeCount={6}
        onOpenAtcNotices={onOpenAtcNotices}
      />,
    )

    await userEvent.click(screen.getByRole('button', { name: /ATC trail updates/ }))

    expect(onOpenAtcNotices).toHaveBeenCalledTimes(1)
  })

  it('renders the list the shell hands it, over the canvas', () => {
    render(
      <MapScreen
        {...PROPS}
        atcNoticeCount={6}
        onOpenAtcNotices={vi.fn()}
        atcNoticeList={<div data-testid="atc-notice-list" />}
      />,
    )

    expect(screen.getByTestId('atc-notice-list')).toBeInTheDocument()
  })

  it('shows nothing until the shell says the list is open', () => {
    render(<MapScreen {...PROPS} atcNoticeCount={6} onOpenAtcNotices={vi.fn()} />)

    expect(screen.queryByTestId('atc-notice-list')).toBe(null)
  })
})

describe('the bottom banner for new ATC alerts (#687)', () => {
  // Independent of atcNoticeCount above - a screen can hold six notices and
  // none of them new, which is the ordinary case now that the 72-hour gate
  // lives in lib/atcAlertsBanner.ts rather than here. MapScreen only renders
  // what it is told; the gate itself is that module's own test.

  it('is not there when nothing is new', () => {
    render(<MapScreen {...PROPS} atcNoticeCount={6} onOpenAtcNotices={vi.fn()} />)

    expect(screen.queryByRole('button', { name: /new alerts? issued/i })).toBe(null)
  })

  it('appears once something is, outside any legend or notice-count prop', () => {
    render(<MapScreen {...PROPS} newAtcAlertCount={2} onOpenAtcNotices={vi.fn()} />)

    expect(
      screen.getByRole('button', { name: 'ATC · 2 new alerts issued' }),
    ).toBeInTheDocument()
  })

  it('counts one alert without pluralising it', () => {
    render(<MapScreen {...PROPS} newAtcAlertCount={1} onOpenAtcNotices={vi.fn()} />)

    expect(
      screen.getByRole('button', { name: 'ATC · New alert issued' }),
    ).toBeInTheDocument()
  })

  it('opens the same list a tap on the legend row would', async () => {
    const onOpenAtcNotices = vi.fn()
    render(
      <MapScreen {...PROPS} newAtcAlertCount={2} onOpenAtcNotices={onOpenAtcNotices} />,
    )

    await userEvent.click(screen.getByRole('button', { name: /new alerts issued/ }))

    expect(onOpenAtcNotices).toHaveBeenCalledTimes(1)
  })

  it('offers a silence control that does not also open the list', async () => {
    const onOpenAtcNotices = vi.fn()
    const onSilenceNewAtcAlerts = vi.fn()
    render(
      <MapScreen
        {...PROPS}
        newAtcAlertCount={2}
        onOpenAtcNotices={onOpenAtcNotices}
        onSilenceNewAtcAlerts={onSilenceNewAtcAlerts}
      />,
    )

    await userEvent.click(screen.getByRole('button', { name: 'Silence new ATC alerts' }))

    expect(onSilenceNewAtcAlerts).toHaveBeenCalledTimes(1)
    expect(onOpenAtcNotices).not.toHaveBeenCalled()
  })

  it('omits the silence control when the shell offers none', () => {
    render(<MapScreen {...PROPS} newAtcAlertCount={2} onOpenAtcNotices={vi.fn()} />)

    expect(screen.queryByRole('button', { name: /silence/i })).toBe(null)
  })

  it('is announced politely rather than as a live safety alert', () => {
    // role="alert" is reserved for what changes what a hiker does next - the
    // strip above the header (#232), which already keeps that role to
    // itself and gets no button inside it. This banner is announced instead
    // through aria-live="polite", not role="status" - StatusStrip.tsx (the
    // "Offline" flag, sync age) already owns that role on this same screen,
    // and a second region claiming it would make "the status region"
    // ambiguous to a screen reader and to a role query alike.
    const { container } = render(
      <MapScreen
        {...PROPS}
        closureAhead="Trail closed 5.0 mi ahead · Storm damage"
        newAtcAlertCount={2}
        onOpenAtcNotices={vi.fn()}
      />,
    )

    expect(within(screen.getByRole('alert')).queryByRole('button')).toBe(null)
    expect(container.querySelector('.map-screen__new-alerts')).toHaveAttribute(
      'aria-live',
      'polite',
    )
  })
})

// --- The desktop chart (#135) ----------------------------------------------
//
// Above the breakpoint the thin ribbon and its lanes hand the slot to the
// full chart, which needs no GPS fix - the ribbon's `elevation` prop can be
// missing entirely (a desk has no fix) and the chart still renders from the
// published profile alone. The chart's hover and selection reach the map
// through converters the shell supplies, so this screen stays ignorant of
// mile axes; what it owns is attaching the focus overlay to the live map.

describe('the desktop chart (#135)', () => {
  function rampProfile() {
    const distanceMi = new Float32Array(101)
    const elevationFt = new Float32Array(101)
    for (let i = 0; i <= 100; i += 1) {
      distanceMi[i] = i
      elevationFt[i] = 1000 + i * 10
    }
    return { distanceMi, elevationFt }
  }

  function chartProps() {
    return {
      profile: rampProfile(),
      currentMile: null,
      mileToCoordinate: vi.fn((): [number, number] | null => [-77.5, 39.5]),
      stretchToRuns: vi.fn(() => [
        [[-77.5, 39.5] as [number, number], [-77.4, 39.6] as [number, number]],
      ]),
    }
  }

  /** The one thing the stylesheet cannot fake in jsdom: the breakpoint.
   *  Answers the desktop for width queries and leaves every other query
   *  (pointer, color-scheme) unmatched, the way a mouse-less 1440px window
   *  would. */
  function stubDesktop(): () => void {
    const original = window.matchMedia
    window.matchMedia = (query: string): MediaQueryList =>
      ({
        matches: query.includes('min-width: 900px'),
        media: query,
        onchange: null,
        addListener: () => {},
        removeListener: () => {},
        addEventListener: () => {},
        removeEventListener: () => {},
        dispatchEvent: () => false,
      }) as MediaQueryList
    return () => {
      window.matchMedia = original
    }
  }

  it('swaps the ribbon and the lanes for the chart above the breakpoint', () => {
    const restore = stubDesktop()
    try {
      render(<MapScreen {...PROPS} chart={chartProps()} />)

      expect(screen.getByTestId('elevation-chart')).toBeInTheDocument()
      // The ribbon and lanes are the phone's; misaligned pins under a
      // zoomable axis would be worse than none (see MapScreen's comment).
      expect(
        screen.queryByRole('img', { name: 'Elevation profile ahead' }),
      ).not.toBeInTheDocument()
      expect(screen.queryByTestId('lane-water')).not.toBeInTheDocument()
    } finally {
      restore()
    }
  })

  it('renders the chart from the profile alone, with no ribbon data at all', () => {
    const restore = stubDesktop()
    try {
      render(
        <MapScreen
          {...PROPS}
          elevation={undefined}
          waypoints={undefined}
          chart={chartProps()}
        />,
      )
      expect(screen.getByTestId('elevation-chart')).toBeInTheDocument()
    } finally {
      restore()
    }
  })

  it('keeps the phone exactly as it was: ribbon and lanes, no chart', () => {
    render(<MapScreen {...PROPS} chart={chartProps()} />)

    expect(
      screen.getByRole('img', { name: 'Elevation profile ahead' }),
    ).toBeInTheDocument()
    expect(screen.getByTestId('lane-water')).toBeInTheDocument()
    expect(screen.queryByTestId('elevation-chart')).not.toBeInTheDocument()
  })

  it('attaches the focus overlay and routes hover through the shell converters', () => {
    const restore = stubDesktop()
    const rectSpy = vi.spyOn(Element.prototype, 'getBoundingClientRect').mockReturnValue({
      x: 0,
      y: 0,
      left: 0,
      top: 0,
      right: 1000,
      bottom: 150,
      width: 1000,
      height: 150,
      toJSON: () => ({}),
    } as DOMRect)
    try {
      const chart = chartProps()
      render(<MapScreen {...PROPS} chart={chart} />)
      const [map] = MockMap.live

      // The overlay attached itself at runtime - the one module that does.
      expect(map.getSource('chart-focus')).toBeDefined()

      fireEvent.pointerMove(screen.getByRole('application'), {
        clientX: 500,
        pointerId: 1,
      })

      expect(chart.mileToCoordinate).toHaveBeenCalled()
      const data = map.sourceData.get('chart-focus') as {
        features: Array<{ geometry: { type: string; coordinates: unknown } }>
      }
      expect(data.features).toEqual([
        expect.objectContaining({
          geometry: { type: 'Point', coordinates: [-77.5, 39.5] },
        }),
      ])
    } finally {
      rectSpy.mockRestore()
      restore()
    }
  })

  // --- The controlled selection and the camera (PR #885 review) -----------

  it('draws the band from the controlled selection, so a route stop entered in the builder lands on the canvas', () => {
    const restore = stubDesktop()
    try {
      const chart = chartProps()
      const { rerender } = render(
        <MapScreen {...PROPS} chart={{ ...chart, selection: null }} />,
      )
      const [map] = MockMap.live

      rerender(
        <MapScreen
          {...PROPS}
          chart={{ ...chart, selection: { startMile: 20, endMile: 70 } }}
        />,
      )

      expect(chart.stretchToRuns).toHaveBeenCalledWith(20, 70)
      const data = map.sourceData.get('chart-focus') as {
        features: Array<{ geometry: { type: string } }>
      }
      expect(data.features).toEqual([
        expect.objectContaining({
          geometry: expect.objectContaining({ type: 'MultiLineString' }),
        }),
      ])
    } finally {
      restore()
    }
  })

  it("threads the hiker's pace through to the chart's figures", () => {
    // The screen's ramp climbs 10 ft/mi, so 20-70 is 50 mi and 500 ft: at
    // 2.5 mph flat that reads ≈20h 15m against a ≈16h 20m standard (#886).
    const restore = stubDesktop()
    try {
      render(
        <MapScreen
          {...PROPS}
          chart={{
            ...chartProps(),
            selection: { startMile: 20, endMile: 70 },
            southbound: false,
            pace: {
              flatPaceMph: 2.5,
              ascentMetersPerHour: 600,
              descentMinutesPer1000m: 0,
            },
          }}
        />,
      )

      expect(screen.getByText('≈20h 15m walking')).toBeInTheDocument()
      expect(screen.getByText('was ≈16h 20m · 1.2× standard')).toBeInTheDocument()
    } finally {
      restore()
    }
  })

  it('moves the camera with "Zoom to stretch" and back out with "Whole trail"', async () => {
    const restore = stubDesktop()
    try {
      const wholeTrail: [[number, number], [number, number]] = [
        [-84.73, 34.2],
        [-68.3, 46.34],
      ]
      const chart = chartProps()
      render(
        <MapScreen
          {...PROPS}
          chart={{
            ...chart,
            selection: { startMile: 20, endMile: 70 },
            southbound: false,
            wholeTrailBounds: wholeTrail,
          }}
        />,
      )
      const [map] = MockMap.live

      await userEvent.click(screen.getByRole('button', { name: 'Zoom to stretch' }))

      // Framed from the stretch's own centerline runs - the geometry the
      // band draws - not a straight line between two mileposts.
      expect(map.cameraMoves).toContainEqual(
        expect.objectContaining({
          fitBounds: [
            [-77.5, 39.5],
            [-77.4, 39.6],
          ],
        }),
      )

      await userEvent.click(screen.getByRole('button', { name: 'Whole trail' }))
      expect(map.cameraMoves).toContainEqual(
        expect.objectContaining({ fitBounds: wholeTrail }),
      )
    } finally {
      restore()
    }
  })
})
