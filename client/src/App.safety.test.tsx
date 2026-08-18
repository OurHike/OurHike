import { describe, it, expect, vi, beforeEach } from 'vitest'
import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from './App'
import { MockMap, resetMapLibreMock } from './test/mocks/maplibre-gl'
import { renderedMap } from './test/liveMap'
import { appHarness, latOfMile } from './test/appHarness'
import { CORRIDOR_ARCHIVE_KEY } from './map/pmtilesSource'
import { readCamera } from './lib/cameraMemory'
import { fetchClosures, fetchReports } from './lib/api'
import { GeolocateControl } from './test/mocks/maplibre-gl'

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
vi.mock('idb-keyval', () => ({
  get: vi.fn(),
  set: vi.fn(),
  del: vi.fn(),
  update: vi.fn(),
}))
vi.mock('./map/archiveZooms', () => ({ readArchiveZooms: () => Promise.resolve(null) }))
vi.mock('./lib/api', () => ({
  API_CONFIGURED: true,
  accessToken: vi.fn(async () => null),
  sendReport: vi.fn(async () => undefined),
  permanentFailureReason: vi.fn(() => null),
  fetchReports: vi.fn(async () => []),
  fetchClosures: vi.fn(async () => []),
}))

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

// onLine, unlike App.flows' harness - the closure reads are gated on it.
const app = appHarness({
  navigator: { onLine: true, geolocation: true },
  objectUrls: true,
})
const store = app.store
const reportFixAtMile = app.reportFixAtMile

beforeEach(() => {
  vi.mocked(fetchClosures).mockResolvedValue([])
  vi.mocked(fetchReports).mockResolvedValue([])
})

/** Onboarded, location allowed, trail data already on the phone. */
function hikerOnTrail(overrides: Record<string, unknown> = {}) {
  app.onboard({ location_permission_requested: true, ...overrides })
  app.putTrailData()
}

/**
 * Fail one of the map's sources, the way MapLibre reports a tile that would
 * not load.
 *
 * The wait is the whole helper and it is not a hedge. The map is CONSTRUCTED
 * during the render that puts "trail map" on screen, and MapView's listeners
 * attach on the render after that - `setMap(created)` is what schedules them.
 * An error emitted in between reaches nobody, which is a test that fails while
 * the app works. Waiting on the listener itself is the observable proof that
 * the wiring is in place, rather than a longer timeout hoping it turns up.
 */
async function sourceFails(sourceId: string): Promise<void> {
  const map = await waitFor(() => {
    const live = MockMap.live[0]
    expect(live?.listenerCount('error')).toBeGreaterThan(0)
    return live!
  })

  act(() => {
    map.emit('error', { sourceId, error: new Error(`${sourceId} unavailable`) })
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

  // #485, end to end through the shell. The lane rule is unit-tested in
  // lib/closureBanner.test.ts; what only this file can catch is App.tsx handing
  // one lane's winner to the other line, or dropping a lane on the floor.
  it('does not let a region-wide advisory bury the closure inside it', async () => {
    // A 60-mile advisory (over MAX_BAND_MILES) with a specific closure inside
    // it, which is ATC's Helene against the Creeper Trail at this harness's
    // scale. Ranked into one line, the advisory scores "inside" and wins - so
    // the closure a mile and a half ahead never reached the header at all.
    vi.mocked(fetchClosures).mockResolvedValue([closure(0, 60), closure(6.5, 7.5)])
    hikerOnTrail()
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await establishNobo(5)

    // The actionable line is the nine-mile closure ahead...
    const specific = await screen.findByText(/trail closed .* ahead/i)
    expect(specific).toHaveTextContent(/mi 6\.5 – 7\.5/)
    // ...and the advisory is still said, on its own line, without claiming the
    // trail is closed underfoot.
    const advisory = screen.getByText(/advisory along 60 mi of trail/i)
    expect(advisory).toHaveTextContent(/mi 0\.0 – 60\.0/)
    expect(screen.queryByText(/trail closed here/i)).toBeNull()
  })

  it('still says an advisory alone when the way ahead is otherwise clear', async () => {
    vi.mocked(fetchClosures).mockResolvedValue([closure(0, 60)])
    hikerOnTrail()
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await establishNobo(5)

    expect(await screen.findByText(/advisory along 60 mi of trail/i)).toBeInTheDocument()
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
        lat: latOfMile(8),
        lon: -77,
        poi_id: null,
        mile: null,
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

  it('counts one filed against a POI, which has no coordinates to snap', async () => {
    // #244. The banner used to place reports by snapping lat/lon to the
    // centerline, so a report with a `poi_id` and no fix could never appear on
    // anybody's route however serious a moderator had marked it - the warning
    // reaching nobody, which is the failure HIKER_SAFETY.md §1 exists to stop.
    // The reporting phone's own mile is what answers it.
    vi.mocked(fetchReports).mockResolvedValue([
      {
        id: 'w-poi',
        type: 'bad_hikers',
        reporter_type: 'thru',
        status: 'verified',
        severity: 'serious',
        lat: null,
        lon: null,
        poi_id: 'shelter-42',
        mile: 8,
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

  it('names the settled states instead of telling the hiker to keep waiting', async () => {
    // Three of the six situations behind the old "Looking for GPS…" never
    // resolve, and this is the one a hiker can walk into by tapping "Not now"
    // once during setup (#312). It is a safety case rather than a wording one:
    // someone standing at a junction waiting for a mile number that is never
    // coming is worse off than someone told the switch is off.
    hikerOnTrail({ location_permission_requested: false })
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    expect(screen.getByText(/location is off/i)).toBeInTheDocument()
    expect(screen.queryByText(/looking for gps/i)).not.toBeInTheDocument()
  })

  it('does not offer the map’s own locate control while location is off', async () => {
    // The gate the control used to bypass entirely. Attached regardless, it
    // prompted for browser permission behind the preference's back and fed its
    // fix to MapLibre's blue dot only - so the canvas drew a position the
    // header knew nothing about, on a second high-accuracy watch.
    hikerOnTrail({ location_permission_requested: false })
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    const map = await waitFor(() => {
      const live = MockMap.live[0]
      expect(live).toBeDefined()
      return live!
    })

    await waitFor(() => {
      expect(
        map.controls.filter(({ control }) => control instanceof GeolocateControl),
      ).toHaveLength(0)
    })
  })

  it('offers it again once location is switched back on', async () => {
    // The recovery path the Settings row exists for, proven from the shell:
    // the same preference that starts the watch is what puts the control back.
    hikerOnTrail({ location_permission_requested: true })
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    const map = await waitFor(() => {
      const live = MockMap.live[0]
      expect(live).toBeDefined()
      return live!
    })

    await waitFor(() => {
      expect(
        map.controls.filter(({ control }) => control instanceof GeolocateControl),
      ).toHaveLength(1)
    })
  })
})

describe('a map that cannot draw says so', () => {
  // #314's whole subject: the worst screen this app can produce is a hiker
  // offline on blank paper with every indicator green. Both paths are wired
  // end to end here rather than only in lib/backgroundHealth.test.ts, because
  // what failed before was never the decision - it was that nothing carried
  // the answer to the strip. #232 is the standing lesson: every component in
  // that list existed too.

  it('says a downloaded archive is not drawing, rather than nothing at all', async () => {
    // The blob is under the key, so the shell holds `downloaded`, the offline
    // background is honoured, and the card shows a finished download. The
    // archive is damaged, so every tile read against it fails.
    hikerOnTrail({ background_source: 'usgs_topo_offline' })
    store.set(CORRIDOR_ARCHIVE_KEY, new Blob(['truncated']))
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await sourceFails('usgs-topo')

    // findBy rather than getBy, and not as a timing hedge: the flag needs BOTH
    // the failing source and the archive status read out of IndexedDB, and
    // those land in either order. What is asserted is that the two meet,
    // whichever arrives second.
    expect(await screen.findByText(/downloaded map not drawing/i)).toBeInTheDocument()
  })

  it('names the missing download when offline with nothing to draw', async () => {
    // The hiking sheet deleted an hour ago, and no signal. "Offline" was the
    // only thing the strip said, and it does not tell anyone that a download
    // is the missing half.
    vi.stubGlobal('navigator', { onLine: false, userAgent: '', platform: '' })
    hikerOnTrail()
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await sourceFails('osm')

    expect(await screen.findByText(/no downloaded map/i)).toBeInTheDocument()
    expect(screen.getByText(/offline/i)).toBeInTheDocument()
  })

  it('stays quiet while the archive draws under a live sheet that cannot', async () => {
    // The stacking working as designed (features/MAP_OPTIONS.md §1): offline,
    // the live layers draw nothing and the download shows through. A hiker
    // with a working map must not be told their map is missing.
    vi.stubGlobal('navigator', { onLine: false, userAgent: '', platform: '' })
    hikerOnTrail()
    store.set(CORRIDOR_ARCHIVE_KEY, new Blob(['pmtiles']))
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    // Waited for rather than assumed: the archive status is an IndexedDB read,
    // and asserting a silence before it lands would pass for the wrong reason.
    // The USGS credit is the observable proof it landed - map/credits.ts names
    // that survey only while its tiles are on the phone.
    await screen.findByText(/USGS US Topo/i)

    await sourceFails('osm')

    expect(screen.queryByText(/no downloaded map/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/not drawing/i)).not.toBeInTheDocument()
  })
})

describe('a background switch under the hiker', () => {
  it('opens where the hiker left it after a reload they did not ask for', async () => {
    // #311's other half. lib/useAppUpdate.ts now waits for a moment nobody is
    // watching before it reloads, but the restart itself still forgets the
    // view - so a hiker who put the phone away reading a junction took it out
    // again looking at the whole trail. The camera is kept in session storage
    // across exactly that restart (lib/cameraMemory.ts).
    hikerOnTrail()
    const { unmount } = render(<App />)
    const before = await renderedMap()

    before.center = { lng: -77.2, lat: 41.5 }
    before.zoom = 13

    // The emit is RETRIED, and that is the fix for a real flake rather than a
    // hedge. `renderedMap()` resolves as soon as the map is constructed, but
    // the shell only records a move once `onMapReady` has handed it that map -
    // a commit or two later. A single `moveend` in the gap is dropped, the
    // view is never written, and the test failed with the mock's default
    // [0, 0] on roughly one run in three. Emitting until the write lands is
    // the observable proof that the shell was listening when it happened.
    await waitFor(() => {
      act(() => before.emit('moveend'))
      expect(readCamera()).toEqual({ center: [-77.2, 41.5], zoom: 13 })
    })

    // A reload, as far as this app can be made to have one: everything React
    // holds is gone, and only what was written down survives.
    unmount()
    resetMapLibreMock()
    render(<App />)

    const reopened = await renderedMap()
    expect(reopened.options.center).toEqual([-77.2, 41.5])
    expect(reopened.options.zoom).toBe(13)
    expect(reopened.options.bounds).toBeUndefined()
  })

  it('opens a fresh session on the whole corridor, not on last week’s view', async () => {
    // The reason it is session storage. Restoring a durable camera would show
    // someone starting in Maine the Georgia view they left on Tuesday, and
    // the opening view is a deliberate decision (App.tsx's CORRIDOR_BOUNDS).
    window.sessionStorage.clear()
    hikerOnTrail()
    render(<App />)

    const opened = await renderedMap()
    expect(opened.options.bounds).toBeDefined()
    expect(opened.options.center).toBeUndefined()
  })

  it('rebuilds the map where the hiker left it, not back at the whole trail', async () => {
    // Switching Live <-> Downloaded is the one preference that costs a WebGL
    // rebuild (MapView's construction effect). The rebuild is tolerable; the
    // camera snapping back to the whole-corridor view mid-navigation is not -
    // a hiker reading a junction loses the junction.
    const user = userEvent.setup()
    hikerOnTrail()
    store.set(CORRIDOR_ARCHIVE_KEY, new Blob(['pmtiles']))
    render(<App />)

    // `renderedMap`, not `findByRole` then `MockMap.live[0]`: the container div
    // commits before the effect that builds the map runs, so the bare read was
    // a race that wins on a quiet machine and loses under a full-suite run
    // (#331, test/liveMap.ts).
    const before = await renderedMap()

    // The hiker pans somewhere that matters to them.
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
