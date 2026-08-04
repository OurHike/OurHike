import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { resetMapLibreMock } from '../test/mocks/maplibre-gl'
import { MapScreen } from './MapScreen'
import { ATTRIBUTION, LIVE_ATTRIBUTION } from '../map/style'

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

    expect(screen.getByText(ATTRIBUTION)).toBeInTheDocument()
  })

  it('credits the extra licences the live background brings with it', () => {
    // The live sheet adds two more conditions of use - OpenFreeMap's terms for
    // the hosting and AWS Terrain Tiles' attribution requirement for the
    // elevation - so the corner has to grow when the background changes. A
    // fixed string here would have gone quietly out of date the day the
    // default flipped.
    render(<MapScreen {...PROPS} background="hiking_topo_live" />)

    expect(screen.getByText(LIVE_ATTRIBUTION)).toBeInTheDocument()
  })

  it('credits the live sheet by default, because that is the default background', () => {
    render(<MapScreen {...PROPS} />)

    expect(screen.getByText(LIVE_ATTRIBUTION)).toBeInTheDocument()
  })

  it('surfaces the offline state it was given', () => {
    render(<MapScreen {...PROPS} />)

    expect(screen.getByText(/offline/i)).toBeInTheDocument()
  })

  it('passes tab selection up to its owner', async () => {
    const user = userEvent.setup()
    render(<MapScreen {...PROPS} />)

    await user.click(screen.getByRole('tab', { name: 'Downloads' }))

    expect(PROPS.onSelectTab).toHaveBeenCalledWith('downloads')
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

  it('shows no waypoint sheet until a pin has been tapped', () => {
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
})
