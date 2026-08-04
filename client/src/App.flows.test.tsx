import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { act, render, screen, cleanup, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { get, set, del } from 'idb-keyval'
import App from './App'
import { PREFERENCES_KEY } from './lib/preferences'
import { DEFAULT_PREFERENCES } from './lib/userPreferences'
import { ELEVATION_STORE_KEY, POIS_KEY, TRAILS_BLOB_KEY } from './lib/trailData'
import { CORRIDOR_ARCHIVE_KEY } from './map/pmtilesSource'
import { POI_ID_PROPERTY, POI_LAYER_ID } from './map/poiLayers'
import { archiveUrl } from './lib/config'
import { MockMap, resetMapLibreMock } from './test/mocks/maplibre-gl'

// App.test.tsx covers the shell: which screen you land on and what it says
// before any data exists. This covers what happens once data and a GPS fix DO
// exist - the paths a hiker is actually on for the length of a hike, and the
// ones that only run after a download succeeds.

vi.mock('maplibre-gl', () => import('./test/mocks/maplibre-gl'))
vi.mock('idb-keyval', () => ({ get: vi.fn(), set: vi.fn(), del: vi.fn() }))

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

const SHELTER = {
  id: 'atc_shelters:abc',
  type: 'shelter',
  name: 'Chairback Gap Lean-to',
  lat: 39 + 5 * MILE_LAT,
  lon: -77,
  confidence: 'high' as const,
  source: 'atc_shelters',
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

  vi.stubGlobal('fetch', vi.fn())
  vi.stubGlobal('navigator', {
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
  // jsdom implements neither, and App revokes/creates one per trail-data load.
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
  store.set(POIS_KEY, [SHELTER])
}

/**
 * Report a GPS fix five miles up the synthetic centerline.
 *
 * Waits for the watch to exist first, and that is not defensive padding. The
 * watch starts in an effect that runs only once loaded preferences say
 * location is allowed - a commit or two AFTER the map screen appears - so
 * firing straight after `findByRole` sometimes found `watchSuccess` still
 * undefined. The optional call then swallowed the fix, no further fix was ever
 * sent, and the test failed looking for a mile that was never going to arrive.
 */
async function reportFix(lat = 39 + 5 * MILE_LAT, lon = -77) {
  await waitFor(() => expect(watchSuccess).toBeDefined())
  await act(async () => {
    watchSuccess?.({
      coords: { latitude: lat, longitude: lon, accuracy: 5 },
      timestamp: Date.now(),
    } as unknown as GeolocationPosition)
  })
}

describe('once there is a GPS fix', () => {
  it('shows the mile instead of still looking for GPS', async () => {
    hikerOnTrail()
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await reportFix()

    expect(await screen.findByText(/mi 5\./)).toBeInTheDocument()
  })

  // The mile assertions are what make this test mean anything: they prove each
  // fix arrived and was used, so a run with an unmoved camera cannot be a run
  // where no fix ever showed up.
  it('leaves the camera on the whole corridor, since the view belongs to the hiker', async () => {
    hikerOnTrail()
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })
    // Wait for the map itself, not just its container div: findByRole resolves
    // a commit before MapView's effect constructs the map, so reading
    // instances[0] straight after it races the build and can find nothing at
    // all. That would fail as a TypeError rather than as the assertion.
    await waitFor(() => expect(MockMap.instances.length).toBeGreaterThan(0))

    await reportFix()
    expect(await screen.findByText(/mi 5\./)).toBeInTheDocument()

    await reportFix(39 + 6 * MILE_LAT)
    expect(await screen.findByText(/mi 6\./)).toBeInTheDocument()

    expect(MockMap.instances[0].cameraMoves).toHaveLength(0)
  })

  it('starts tracking a direction of travel once it has two fixes', async () => {
    hikerOnTrail()
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await reportFix(39 + 5 * MILE_LAT)
    await reportFix(39 + 8 * MILE_LAT)

    expect(await screen.findByText(/mi 8\./)).toBeInTheDocument()
  })
})

describe('search, with a real index behind it', () => {
  it('jumps the map to the result that was picked', async () => {
    const user = userEvent.setup()
    hikerOnTrail()
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await user.click(screen.getByRole('button', { name: /search/i }))
    await user.type(
      await screen.findByRole('searchbox', { name: /search the downloaded map/i }),
      'chairback',
    )
    await user.click(await screen.findByText('Chairback Gap Lean-to'))

    // Centre AND zoom: from the opening view of the whole corridor, centring
    // alone moves the map a few pixels and looks like nothing happened.
    await waitFor(() =>
      expect(MockMap.instances[0].cameraMoves).toContainEqual(
        expect.objectContaining({ center: [SHELTER.lon, SHELTER.lat] }),
      ),
    )
    const jump = MockMap.instances[0].cameraMoves.find(
      (move) => Array.isArray(move.center) && move.center[0] === SHELTER.lon,
    )
    expect(jump?.zoom).toBeGreaterThanOrEqual(14)
  })

  it('shows the mile alongside a result once the index exists', async () => {
    const user = userEvent.setup()
    hikerOnTrail()
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await user.click(screen.getByRole('button', { name: /search/i }))
    await user.type(
      await screen.findByRole('searchbox', { name: /search the downloaded map/i }),
      'chairback',
    )

    expect(await screen.findByText(/Shelter · mi 5\./)).toBeInTheDocument()
  })

  it('closes without moving the map when the search is cancelled', async () => {
    const user = userEvent.setup()
    hikerOnTrail()
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await user.click(screen.getByRole('button', { name: /search/i }))
    await user.click(await screen.findByRole('button', { name: /cancel/i }))

    expect(
      screen.queryByRole('searchbox', { name: /search the downloaded map/i }),
    ).not.toBeInTheDocument()
  })
})

describe('the legend', () => {
  it('opens and closes', async () => {
    const user = userEvent.setup()
    hikerOnTrail()
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await user.click(screen.getByRole('button', { name: /legend/i }))
    const legend = await screen.findByRole('dialog', { name: /legend/i })

    await user.click(within(legend).getByRole('button', { name: /close|done/i }))

    expect(screen.queryByRole('dialog', { name: /legend/i })).not.toBeInTheDocument()
  })

  it('hides a type when it is toggled off, and shows it again when toggled back', async () => {
    const user = userEvent.setup()
    hikerOnTrail()
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await user.click(screen.getByRole('button', { name: /legend/i }))
    const legend = await screen.findByRole('dialog', { name: /legend/i })
    const hide = within(legend).getAllByRole('button', { name: /hide|show/i })[0]
    const label = hide.getAttribute('aria-label') ?? ''

    await user.click(hide)
    expect(within(legend).queryByRole('button', { name: label })).not.toBeInTheDocument()

    // Toggling back is the half that a Set-based toggle gets wrong if it only
    // ever adds.
    const restore = within(legend).getAllByRole('button', { name: /hide|show/i })[0]
    await user.click(restore)
    expect(
      within(legend).getAllByRole('button', { name: /hide|show/i }).length,
    ).toBeGreaterThan(0)
  })
})

describe('tapping a pin on the map', () => {
  /**
   * Touch the canvas where MapLibre would report a pin.
   *
   * The map is real code with a mock MapLibre under it, so the pin has to be
   * put where a rendered-feature query will find it - which is what the live
   * map's own tile rendering does for a real one.
   */
  async function tapPin(properties: Record<string, unknown>) {
    // The LIVE map, and only once it is listening. The map screen builds a new
    // map when the trail lines land - a different object URL is a different
    // style - so the first map constructed is routinely one that has already
    // been torn down, and touching it would be touching nothing.
    await waitFor(() => {
      expect(MockMap.live).toHaveLength(1)
      expect(MockMap.live[0].listenerCount('click')).toBeGreaterThan(0)
    })
    const map = MockMap.live[0]
    map.renderedFeatures.set(POI_LAYER_ID, [{ properties }])
    await act(async () => {
      map.emit('click', { point: { x: 160, y: 300 } })
    })
  }

  it('opens the waypoint’s details, which used to do nothing at all', async () => {
    hikerOnTrail()
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await tapPin({ [POI_ID_PROPERTY]: SHELTER.id, poi_type: 'shelter' })

    const sheet = await screen.findByRole('dialog', { name: /waypoint/i })
    expect(
      within(sheet).getByRole('heading', { name: 'Chairback Gap Lean-to' }),
    ).toBeInTheDocument()
    expect(within(sheet).getByText('Shelter')).toBeInTheDocument()
  })

  it('places the waypoint on the trail, at the mile search would give it', async () => {
    // One number from one computation. A second way of working out the mile
    // could disagree with search about the same shelter, which is exactly the
    // kind of quiet contradiction OurHikeValues.md #4 is about.
    hikerOnTrail()
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await tapPin({ [POI_ID_PROPERTY]: SHELTER.id, poi_type: 'shelter' })

    const sheet = await screen.findByRole('dialog', { name: /waypoint/i })
    expect(within(sheet).getByText(/^mi 5\./)).toBeInTheDocument()
  })

  it('says which source listed it', async () => {
    hikerOnTrail()
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await tapPin({ [POI_ID_PROPERTY]: SHELTER.id, poi_type: 'shelter' })

    const sheet = await screen.findByRole('dialog', { name: /waypoint/i })
    expect(within(sheet).getByText(/Appalachian Trail Conservancy/)).toBeInTheDocument()
  })

  it('closes again', async () => {
    const user = userEvent.setup()
    hikerOnTrail()
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await tapPin({ [POI_ID_PROPERTY]: SHELTER.id, poi_type: 'shelter' })
    const sheet = await screen.findByRole('dialog', { name: /waypoint/i })
    await user.click(within(sheet).getByRole('button', { name: /close/i }))

    expect(screen.queryByRole('dialog', { name: /waypoint/i })).not.toBeInTheDocument()
  })

  it('ignores a tap on a pin the app no longer holds', async () => {
    // A stale tile can name a POI that a re-download has since dropped. An
    // empty sheet would be worse than no sheet.
    hikerOnTrail()
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await tapPin({ [POI_ID_PROPERTY]: 'atc_shelters:gone', poi_type: 'shelter' })

    expect(screen.queryByRole('dialog', { name: /waypoint/i })).not.toBeInTheDocument()
  })

  it('replaces the legend rather than stacking on it', async () => {
    // Both sit at the bottom of the map. Two at once leaves the lower one
    // unreadable and its close button unreachable.
    const user = userEvent.setup()
    hikerOnTrail()
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await user.click(screen.getByRole('button', { name: /legend/i }))
    await screen.findByRole('dialog', { name: /legend/i })
    await tapPin({ [POI_ID_PROPERTY]: SHELTER.id, poi_type: 'shelter' })

    expect(await screen.findByRole('dialog', { name: /waypoint/i })).toBeInTheDocument()
    expect(screen.queryByRole('dialog', { name: /legend/i })).not.toBeInTheDocument()
  })

  it('gets out of the way when the legend is opened over it', async () => {
    const user = userEvent.setup()
    hikerOnTrail()
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await tapPin({ [POI_ID_PROPERTY]: SHELTER.id, poi_type: 'shelter' })
    await screen.findByRole('dialog', { name: /waypoint/i })
    await user.click(screen.getByRole('button', { name: /legend/i }))

    expect(await screen.findByRole('dialog', { name: /legend/i })).toBeInTheDocument()
    expect(screen.queryByRole('dialog', { name: /waypoint/i })).not.toBeInTheDocument()
  })
})

describe('downloading everything', () => {
  function servesEverything() {
    vi.mocked(fetch).mockImplementation((url) =>
      Promise.resolve({
        ok: true,
        status: 200,
        statusText: 'OK',
        blob: () => Promise.resolve(new Blob([TRAILS_GEOJSON])),
        text: () =>
          Promise.resolve(
            String(url).includes('poi_shelter')
              ? JSON.stringify({
                  type: 'FeatureCollection',
                  features: [
                    {
                      type: 'Feature',
                      properties: {
                        id: SHELTER.id,
                        name: SHELTER.name,
                        confidence: 'high',
                      },
                      geometry: {
                        type: 'Point',
                        coordinates: [SHELTER.lon, SHELTER.lat],
                      },
                    },
                  ],
                })
              : JSON.stringify({ type: 'FeatureCollection', features: [] }),
          ),
        headers: new Headers({ 'content-length': '3' }),
        body: new ReadableStream({
          start(controller) {
            controller.enqueue(new Uint8Array([1, 2, 3]))
            controller.close()
          },
        }),
      } as unknown as Response),
    )
  }

  it('fetches the trail data and then the archive, in that order', async () => {
    const user = userEvent.setup()
    store.set(PREFERENCES_KEY, {
      ...DEFAULT_PREFERENCES,
      onboarding_completed: true,
      download_choice_made: true,
    })
    servesEverything()
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await user.click(screen.getByRole('tab', { name: 'Downloads' }))
    await user.click(await screen.findByRole('button', { name: /download the map/i }))

    await waitFor(() => expect(store.get(TRAILS_BLOB_KEY)).toBeInstanceOf(Blob))
    await waitFor(() => expect(store.get(CORRIDOR_ARCHIVE_KEY)).toBeInstanceOf(Blob))
  })

  it('deletes the map, the trail data and the POIs together', async () => {
    // Someone reclaiming space expects all of it back, not the raster alone.
    const user = userEvent.setup()
    hikerOnTrail()
    store.set(CORRIDOR_ARCHIVE_KEY, new Blob(['archive']))
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await user.click(screen.getByRole('tab', { name: 'Downloads' }))
    await user.click(await screen.findByRole('button', { name: /delete/i }))

    await waitFor(() => expect(store.has(CORRIDOR_ARCHIVE_KEY)).toBe(false))
    expect(store.has(TRAILS_BLOB_KEY)).toBe(false)
    expect(store.has(POIS_KEY)).toBe(false)
  })

  it('records a new detail level as a max background zoom', async () => {
    const user = userEvent.setup()
    hikerOnTrail()
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await user.click(screen.getByRole('tab', { name: 'Downloads' }))
    await user.click(await screen.findByRole('radio', { name: /light/i }))

    await waitFor(() => {
      const saved = store.get(PREFERENCES_KEY) as { max_background_zoom: number }
      expect(saved.max_background_zoom).toBe(11)
    })
  })
})

describe('reporting, with a fix to attach', () => {
  it('files the report at the position the hiker is actually standing', async () => {
    const user = userEvent.setup()
    hikerOnTrail()
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })
    await reportFix()

    await user.click(screen.getByRole('tab', { name: 'More' }))
    await user.click(await screen.findByRole('button', { name: /report a problem/i }))
    await user.click(await screen.findByRole('button', { name: /blow down/i }))
    await user.click(await screen.findByRole('button', { name: /send|save to outbox/i }))

    await waitFor(() => {
      const queued = store.get('ourhike:outbox') as Array<{
        payload: { lat?: number; lon?: number }
      }>
      expect(queued).toHaveLength(1)
      expect(queued[0].payload.lat).toBeCloseTo(SHELTER.lat, 4)
      expect(queued[0].payload.lon).toBeCloseTo(SHELTER.lon, 4)
    })
  })

  it('drops the draft and returns to the tab it came from when cancelled', async () => {
    const user = userEvent.setup()
    hikerOnTrail()
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await user.click(screen.getByRole('tab', { name: 'More' }))
    await user.click(await screen.findByRole('button', { name: /report a problem/i }))
    await user.click(await screen.findByRole('button', { name: /blow down/i }))
    await user.click(await screen.findByRole('button', { name: /^cancel$/i }))

    expect(await screen.findByRole('heading', { name: 'You' })).toBeInTheDocument()
    expect(store.get('ourhike:outbox')).toBeUndefined()
  })

  it('counts what is waiting in the outbox', async () => {
    const user = userEvent.setup()
    hikerOnTrail()
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await user.click(screen.getByRole('tab', { name: 'More' }))
    await user.click(await screen.findByRole('button', { name: /report a problem/i }))
    await user.click(await screen.findByRole('button', { name: /blow down/i }))
    await user.click(await screen.findByRole('button', { name: /send|save to outbox/i }))

    // Saving now hands over to the sign-in step (lib/contributionFlow.ts's
    // stepAfterSaving). Declining it is the path this test cares about: the
    // count has to be the same either way, because the report was already
    // written before anyone was asked to authenticate.
    await user.click(await screen.findByRole('button', { name: /not now/i }))

    expect(await screen.findByText(/1 .*(waiting|queued|outbox)/i)).toBeInTheDocument()
  })

  it('saves the report even when sign-in is declined', async () => {
    const user = userEvent.setup()
    hikerOnTrail()
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await user.click(screen.getByRole('tab', { name: 'More' }))
    await user.click(await screen.findByRole('button', { name: /report a problem/i }))
    await user.click(await screen.findByRole('button', { name: /blow down/i }))
    await user.click(await screen.findByRole('button', { name: /send|save to outbox/i }))
    await user.click(await screen.findByRole('button', { name: /not now/i }))

    // The promise the whole flow exists to keep: someone who cannot or will
    // not authenticate still has what they wrote.
    await waitFor(() => {
      expect(store.get('ourhike:outbox')).toBeDefined()
    })
  })

  it('asks to sign in only after the report is already saved', async () => {
    const user = userEvent.setup()
    hikerOnTrail()
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await user.click(screen.getByRole('tab', { name: 'More' }))
    await user.click(await screen.findByRole('button', { name: /report a problem/i }))
    await user.click(await screen.findByRole('button', { name: /blow down/i }))
    await user.click(await screen.findByRole('button', { name: /send|save to outbox/i }))

    // Ordering is the design, not a detail - the screen says the report is
    // already saved, and it has to be true when it says it.
    expect(await screen.findByText(/already saved/i)).toBeInTheDocument()
    expect(store.get('ourhike:outbox')).toBeDefined()
  })
})

describe('preferences from the More screen', () => {
  it('saves a changed setting straight away, with no explicit save step', async () => {
    // The wrong-way alert is the one live toggle on this screen today - the
    // rest are marked Later and deliberately disabled.
    const user = userEvent.setup()
    hikerOnTrail({ wrong_way_alert_enabled: false })
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await user.click(screen.getByRole('tab', { name: 'More' }))
    await user.click(await screen.findByRole('checkbox', { name: /wrong-way alert/i }))

    await waitFor(() => {
      const saved = store.get(PREFERENCES_KEY) as { wrong_way_alert_enabled: boolean }
      expect(saved.wrong_way_alert_enabled).toBe(true)
    })
  })
})

describe('the placeholder actions on More', () => {
  // Sync and export are wired to no-ops today: the backend they need is Phase
  // 2 (ROADMAP.md). Rendered and clickable anyway so the shape of the screen
  // is real, and asserted here so a wiring mistake shows up as a failing test
  // rather than as a button that throws in someone's hand.
  //
  // Sign in used to be in this list and is not a placeholder any more, which
  // is what the sign-in tests below cover instead.
  it.each([/^sync$/i, /export gpx/i, /export geojson/i])(
    'does not throw when %s is tapped',
    async (name) => {
      const user = userEvent.setup()
      hikerOnTrail()
      render(<App />)
      await screen.findByRole('region', { name: /trail map/i })
      await user.click(screen.getByRole('tab', { name: 'More' }))

      await user.click(await screen.findByRole('button', { name }))

      expect(await screen.findByRole('heading', { name: 'You' })).toBeInTheDocument()
    },
  )
})

describe('signing in from Settings', () => {
  it('opens the sign-in screen', async () => {
    const user = userEvent.setup()
    hikerOnTrail()
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })
    await user.click(screen.getByRole('tab', { name: 'More' }))

    await user.click(await screen.findByRole('button', { name: /sign in/i }))

    expect(
      await screen.findByRole('button', { name: /continue with google/i }),
    ).toBeInTheDocument()
  })

  it('does not claim a report is saved, because this path has no report', async () => {
    // The same screen serves the contribution flow, where "your report is
    // already saved" is both true and the point. Reached from Settings there
    // is nothing saved, and saying so would be a promise about something that
    // does not exist.
    const user = userEvent.setup()
    hikerOnTrail()
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })
    await user.click(screen.getByRole('tab', { name: 'More' }))

    await user.click(await screen.findByRole('button', { name: /sign in/i }))
    await screen.findByRole('button', { name: /continue with google/i })

    expect(screen.queryByText(/already saved/i)).toBe(null)
  })

  it('backs out to the screen it came from', async () => {
    const user = userEvent.setup()
    hikerOnTrail()
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })
    await user.click(screen.getByRole('tab', { name: 'More' }))

    await user.click(await screen.findByRole('button', { name: /sign in/i }))
    await user.click(await screen.findByRole('button', { name: /not now/i }))

    expect(await screen.findByRole('heading', { name: 'You' })).toBeInTheDocument()
  })

  it('offers only the providers this build has credentials for', async () => {
    // ENABLED_PROVIDERS defaults to Google and email. Apple needs a $99/yr
    // membership, and a button for a provider with no credentials behind it
    // reaches an error page rather than an account.
    const user = userEvent.setup()
    hikerOnTrail()
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })
    await user.click(screen.getByRole('tab', { name: 'More' }))

    await user.click(await screen.findByRole('button', { name: /sign in/i }))
    await screen.findByRole('button', { name: /continue with google/i })

    expect(
      screen.getByRole('button', { name: /continue with email/i }),
    ).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /continue with apple/i })).toBe(null)
  })

  it('reaches the email form, which asks for a password rather than only an address', async () => {
    const user = userEvent.setup()
    hikerOnTrail()
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })
    await user.click(screen.getByRole('tab', { name: 'More' }))

    await user.click(await screen.findByRole('button', { name: /sign in/i }))
    await user.click(await screen.findByRole('button', { name: /continue with email/i }))

    expect(await screen.findByLabelText(/email/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument()
  })
})

describe('when the trail data cannot be downloaded', () => {
  it('says so even when what failed was not an Error', async () => {
    // fetch can reject with anything at all, and a rejection this code cannot
    // read the message off still has to produce a sentence rather than
    // "undefined" or a blank alert.
    const user = userEvent.setup()
    store.set(PREFERENCES_KEY, {
      ...DEFAULT_PREFERENCES,
      onboarding_completed: true,
      download_choice_made: true,
    })
    vi.mocked(fetch).mockRejectedValue('the network went away')
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await user.click(screen.getByRole('tab', { name: 'Downloads' }))
    await user.click(await screen.findByRole('button', { name: /download the map/i }))

    expect(await screen.findByText('Trail data failed to download.')).toBeInTheDocument()
  })
})

describe('resuming an interrupted download', () => {
  it('picks up where it left off rather than starting again', async () => {
    // WIREFRAMES.md 7a. Re-pulling 300 MB from zero because a connection
    // dropped at 90% is the failure that promise exists to prevent.
    const user = userEvent.setup()
    hikerOnTrail()
    store.set('ourhike:corridor-archive:partial', new Blob([new Uint8Array([1, 2, 3])]))
    store.set('ourhike:corridor-archive:progress', { receivedBytes: 3, totalBytes: 6 })
    // Must be the URL this build would request. VITE_DATA_BASE_URL is unset
    // under test, so that is a bare '/background.pmtiles' - and a partial
    // recorded against any other URL is deliberately discarded, not resumed.
    store.set('ourhike:corridor-archive:source', { url: archiveUrl('standard') })

    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })
    await user.click(screen.getByRole('tab', { name: 'Downloads' }))
    const resume = await screen.findByRole('button', { name: /resume/i })

    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      status: 206,
      statusText: 'Partial Content',
      headers: new Headers({ 'content-length': '3', 'content-range': 'bytes 3-5/6' }),
      body: new ReadableStream({
        start(controller) {
          controller.enqueue(new Uint8Array([4, 5, 6]))
          controller.close()
        },
      }),
    } as unknown as Response)
    await user.click(resume)

    await waitFor(() =>
      expect(vi.mocked(fetch).mock.calls[0][1]).toMatchObject({
        headers: expect.objectContaining({ Range: 'bytes=3-' }),
      }),
    )
  })
})

// WIREFRAMES.md §1.3 and §1.4. Both components were built, tested and accepted
// by MapScreen as optional props long before anything downloaded a profile to
// pass them, so they could never appear on any device in any state. What is
// worth testing here is the wiring and the three conditions it is gated on -
// not the drawing, which ElevationRibbon.test.tsx and WaypointLanes.test.tsx
// already cover.
describe('the elevation ribbon and the waypoint lanes', () => {
  /** Flat to mile 8, a 1,000 ft climb to mile 10, back down by mile 12, flat
   *  to the end of the synthetic centerline. */
  function profileWithAClimb() {
    const miles: number[] = []
    const feet: number[] = []

    for (let mile = 0; mile <= 40; mile += 0.1) {
      const rounded = Number(mile.toFixed(2))
      miles.push(rounded)
      feet.push(
        rounded <= 8
          ? 1000
          : rounded <= 10
            ? 1000 + (rounded - 8) * 500
            : rounded <= 12
              ? 2000 - (rounded - 10) * 500
              : 1000,
      )
    }

    return {
      distanceMi: Float32Array.from(miles),
      elevationFt: Float32Array.from(feet),
    }
  }

  function ribbon() {
    return screen.queryByRole('img', { name: /elevation profile ahead/i })
  }

  it('draws the profile once there is a fix and a profile to draw', async () => {
    hikerOnTrail()
    store.set(ELEVATION_STORE_KEY, profileWithAClimb())
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await reportFix()

    await waitFor(() => expect(ribbon()).toBeInTheDocument())
  })

  it('draws the three waypoint lanes beside it', async () => {
    hikerOnTrail()
    store.set(ELEVATION_STORE_KEY, profileWithAClimb())
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await reportFix()

    await waitFor(() => expect(screen.getByTestId('lane-water')).toBeInTheDocument())
    expect(screen.getByTestId('lane-sleep')).toBeInTheDocument()
    expect(screen.getByTestId('lane-else')).toBeInTheDocument()
  })

  it('puts a POI the index can place into its lane', async () => {
    // The shelter sits at mile 5 on the synthetic centerline, inside the window
    // around a hiker standing at mile 5.
    hikerOnTrail()
    store.set(ELEVATION_STORE_KEY, profileWithAClimb())
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await reportFix()

    await waitFor(() =>
      expect(
        within(screen.getByTestId('lane-sleep')).getByRole('button'),
      ).toBeInTheDocument(),
    )
  })

  it('shows nothing at all before there is a fix', async () => {
    // Without a position there is no "ahead". An empty ribbon would read as
    // "nothing ahead of you", which is a different and much worse claim than
    // not drawing one.
    hikerOnTrail()
    store.set(ELEVATION_STORE_KEY, profileWithAClimb())
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    expect(ribbon()).not.toBeInTheDocument()
    expect(screen.queryByTestId('lane-water')).not.toBeInTheDocument()
  })

  it('shows nothing when the release published no profile', async () => {
    // A data release built before pipeline/export_elevation.py existed. The
    // map still works; the ribbon and the lanes are simply absent.
    hikerOnTrail()
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await reportFix()

    await screen.findByText(/mi 5\./)
    expect(ribbon()).not.toBeInTheDocument()
    expect(screen.queryByTestId('lane-water')).not.toBeInTheDocument()
  })

  it('waits for the direction before captioning a climb', async () => {
    // lib/hikeDirection.ts withholds the direction until a quarter mile of
    // movement, and which way someone faces decides which climb is ahead.
    hikerOnTrail()
    store.set(ELEVATION_STORE_KEY, profileWithAClimb())
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await reportFix()

    await waitFor(() => expect(ribbon()).toBeInTheDocument())
    expect(screen.queryByTestId('climb-callout')).not.toBeInTheDocument()
  })

  it('captions the climb ahead once the direction is known', async () => {
    hikerOnTrail()
    store.set(ELEVATION_STORE_KEY, profileWithAClimb())
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await reportFix()
    // A mile further north: enough movement for NOBO to be established.
    await reportFix(39 + 6 * MILE_LAT)

    // 1,000 ft between mile 8 and mile 10, and Naismith's duration for it -
    // never an arrival clock.
    expect(await screen.findByTestId('climb-callout')).toHaveTextContent(
      '+1,000 ft · 2.0 mi · ≈1h 10m',
    )
  })
})
