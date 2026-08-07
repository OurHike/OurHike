import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { act, render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { get, set, del } from 'idb-keyval'
import App from './App'
import { MockMap, resetMapLibreMock } from './test/mocks/maplibre-gl'
import { PREFERENCES_KEY } from './lib/preferences'
import { DEFAULT_PREFERENCES } from './lib/userPreferences'
import { POIS_KEY, TRAILS_BLOB_KEY } from './lib/trailData'
import { CORRIDOR_ARCHIVE_KEY } from './map/pmtilesSource'
import { fetchClosures, fetchReports } from './lib/api'

// The on-trail safety battery. Every test here is one of the ways losing the
// map - or trusting a silent map - could hurt someone on a ridge, written as
// an invariant the shell has to keep:
//
//   - a closure is announced from INSIDE it before the app knows which way
//     the hiker walks, and announced ahead once it does;
//   - a failed closures read stays silent rather than reading as "all clear";
//   - the map renders without GPS at all;
//   - a background switch rebuilds the canvas where the hiker left it, not
//     back at the whole-trail view.
//
// A separate file from App.test.tsx because these need lib/api mocked as
// CONFIGURED (the closure reads are gated on it), which would flip on real
// sync behaviour for every unrelated test there - the same reason
// App.outboxRetry.test.tsx stands alone.

vi.mock('maplibre-gl', () => import('./test/mocks/maplibre-gl'))
vi.mock('idb-keyval', () => ({ get: vi.fn(), set: vi.fn(), del: vi.fn() }))
vi.mock('./map/archiveZooms', () => ({ readArchiveZooms: () => Promise.resolve(null) }))
vi.mock('./lib/api', () => ({
  API_CONFIGURED: true,
  accessToken: vi.fn(async () => null),
  sendReport: vi.fn(async () => undefined),
  permanentFailureReason: vi.fn(() => null),
  fetchReports: vi.fn(async () => []),
  fetchClosures: vi.fn(async () => []),
}))

const store = new Map<string, unknown>()

/** A centerline running due north, so a mile of latitude is about a mile. */
const MILE_LAT = 1 / 69.05
const TRAILS_GEOJSON = JSON.stringify({
  type: 'FeatureCollection',
  features: [
    {
      type: 'Feature',
      properties: { source: 'centerline' },
      geometry: {
        type: 'LineString',
        coordinates: Array.from({ length: 40 }, (_, i) => [-77, 39 + i * MILE_LAT]),
      },
    },
  ],
})

/** A verified closure between two miles of the synthetic centerline. */
function closure(startMile: number, endMile: number) {
  return {
    id: `closure-${startMile}`,
    reason_type: 'storm_damage' as const,
    note: null,
    status: 'closed' as const,
    start_mile_marker: startMile,
    end_mile_marker: endMile,
    reported_at: '2026-08-01T00:00:00Z',
    verified_at: '2026-08-01T12:00:00Z',
  }
}

let watchSuccess: ((position: GeolocationPosition) => void) | undefined

beforeEach(() => {
  store.clear()
  watchSuccess = undefined
  resetMapLibreMock()
  vi.mocked(get).mockImplementation((key) => Promise.resolve(store.get(key as string)))
  vi.mocked(set).mockImplementation((key, value) => {
    store.set(key as string, value)
    return Promise.resolve()
  })
  vi.mocked(del).mockImplementation((key) => {
    store.delete(key as string)
    return Promise.resolve()
  })
  vi.mocked(fetchClosures).mockResolvedValue([])
  vi.mocked(fetchReports).mockResolvedValue([])

  vi.stubGlobal('fetch', vi.fn())
  // onLine: true, unlike App.flows' stub - the closure reads are gated on it.
  vi.stubGlobal('navigator', {
    onLine: true,
    geolocation: {
      watchPosition: (success: (position: GeolocationPosition) => void) => {
        watchSuccess = success
        return 1
      },
      clearWatch: () => {},
    },
    userAgent: '',
    platform: '',
  })
  vi.stubGlobal('URL', {
    ...URL,
    createObjectURL: vi.fn(() => 'blob:trails'),
    revokeObjectURL: vi.fn(),
  })
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  vi.unstubAllGlobals()
})

/** Onboarded, location allowed, trail data already on the phone. */
function hikerOnTrail(overrides: Record<string, unknown> = {}) {
  store.set(PREFERENCES_KEY, {
    ...DEFAULT_PREFERENCES,
    onboarding_completed: true,
    download_choice_made: true,
    location_permission_requested: true,
    ...overrides,
  })
  store.set(TRAILS_BLOB_KEY, new Blob([TRAILS_GEOJSON]))
  store.set(POIS_KEY, [])
}

/** Report a GPS fix at a mile of the synthetic centerline. */
async function reportFixAtMile(mile: number) {
  await waitFor(() => expect(watchSuccess).toBeDefined())
  await act(async () => {
    watchSuccess?.({
      coords: { latitude: 39 + mile * MILE_LAT, longitude: -77, accuracy: 5 },
      timestamp: Date.now(),
    } as unknown as GeolocationPosition)
  })
}

/** Walk far enough north for the direction tracker to commit to NOBO. */
async function establishNobo(fromMile: number) {
  await reportFixAtMile(fromMile)
  await reportFixAtMile(fromMile + 1)
}

describe('the closure banner', () => {
  it('warns about the closure ahead once the direction is known', async () => {
    vi.mocked(fetchClosures).mockResolvedValue([closure(6.5, 7.5)])
    hikerOnTrail()
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await establishNobo(5)

    const banner = await screen.findByText(/trail closed .* ahead/i)
    expect(banner).toHaveTextContent(/storm damage/i)
    expect(banner).toHaveTextContent(/mi 6\.5 – 7\.5/)
  })

  it('says nothing about the closure already walked through', async () => {
    // A NOBO hiker north of it has been through it; warning them is noise,
    // and noise is what teaches someone to stop reading the banner.
    vi.mocked(fetchClosures).mockResolvedValue([closure(1, 2)])
    hikerOnTrail()
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await establishNobo(5)

    await waitFor(() => expect(screen.queryByText(/trail closed/i)).toBeNull())
  })

  it('warns from inside a closed section before any direction is known', async () => {
    // Direction takes a quarter mile of walking to establish
    // (lib/hikeDirection.ts). The banner used to be gated on it entirely, so
    // a hiker opening the app INSIDE a closure - the one place the warning
    // matters most - saw a clear header for their first quarter mile.
    vi.mocked(fetchClosures).mockResolvedValue([closure(4.5, 5.5)])
    hikerOnTrail()
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    // One fix. No second fix, no movement, no direction.
    await reportFixAtMile(5)

    const banner = await screen.findByText(/trail closed here/i)
    expect(banner).toHaveTextContent(/storm damage/i)
  })

  it('stays silent when the closures read fails, and keeps the map', async () => {
    // A failed read and an empty list draw the same map and mean opposite
    // things on the ground. The banner must not invent an all-clear - and
    // the map must not be taken down by an unreachable backend, which is the
    // ordinary condition out here.
    vi.mocked(fetchClosures).mockRejectedValue(new TypeError('Failed to fetch'))
    hikerOnTrail()
    render(<App />)

    await screen.findByRole('region', { name: /trail map/i })
    await establishNobo(5)

    expect(screen.queryByText(/trail closed/i)).toBeNull()
    expect(screen.getByRole('region', { name: /trail map/i })).toBeInTheDocument()
  })
})

describe('the serious-warnings banner', () => {
  it('counts the serious reports on the route ahead', async () => {
    vi.mocked(fetchReports).mockResolvedValue([
      {
        id: 'w1',
        type: 'wildlife',
        reporter_type: 'thru',
        status: 'verified',
        severity: 'serious',
        lat: 39 + 8 * MILE_LAT,
        lon: -77,
        poi_id: null,
        note: null,
        timestamp: '2026-08-01T00:00:00Z',
      },
    ])
    hikerOnTrail()
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await establishNobo(5)

    expect(
      await screen.findByText(/1 serious warning on your route/i),
    ).toBeInTheDocument()
  })
})

describe('the map without its sensors', () => {
  it('renders with no geolocation API at all', async () => {
    vi.stubGlobal('navigator', { onLine: true, userAgent: '', platform: '' })
    hikerOnTrail()
    render(<App />)

    expect(await screen.findByRole('region', { name: /trail map/i })).toBeInTheDocument()
  })

  it('renders when permission was skipped at onboarding', async () => {
    hikerOnTrail({ location_permission_requested: false })
    render(<App />)

    expect(await screen.findByRole('region', { name: /trail map/i })).toBeInTheDocument()
  })
})

describe('a background switch under the hiker', () => {
  it('rebuilds the map where the hiker left it, not back at the whole trail', async () => {
    // Switching Live <-> Downloaded is the one preference that costs a WebGL
    // rebuild (MapView's construction effect). The rebuild is tolerable; the
    // camera snapping back to the whole-corridor view mid-navigation is not -
    // a hiker reading a junction loses the junction.
    const user = userEvent.setup()
    hikerOnTrail()
    store.set(CORRIDOR_ARCHIVE_KEY, new Blob(['pmtiles']))
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    // The hiker pans somewhere that matters to them.
    const before = MockMap.live[0]!
    before.center = { lng: -77.2, lat: 41.5 }
    before.zoom = 13
    act(() => before.emit('moveend'))

    // Then switches background in the legend.
    await user.click(screen.getByRole('button', { name: /legend/i }))
    await user.click(await screen.findByRole('radio', { name: /downloaded/i }))

    await waitFor(() => {
      const rebuilt = MockMap.live[0]!
      expect(rebuilt).not.toBe(before)
      expect(rebuilt.options.center).toEqual([-77.2, 41.5])
      expect(rebuilt.options.zoom).toBe(13)
      expect(rebuilt.options.bounds).toBeUndefined()
    })
  })
})
